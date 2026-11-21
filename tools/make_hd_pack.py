#!/usr/bin/env python
"""Build an HD texture pack for TEX_REPLACE from TEX_DUMP output.

Usage:
  python make_hd_pack.py --in DUMP_DIR [DUMP_DIR ...] --out PACK_DIR
      [--work TMP_DIR] [--esrgan realesrgan-ncnn-vulkan.exe] [--models MODELS_DIR]
      [--model realesrgan-x4plus] [--pad 32] [--batch-mpx 6] [--limit N]
      [--large-scale 4] [--lock BUILD.lock --owner NAME]

Needs only the standard library, ffmpeg/ffprobe on PATH and realesrgan-ncnn-vulkan.
Dumps are merged by file name (<hash16>_<w>x<h>_f<fmt>.png); output keeps the names.

Per texture:
  skip   max side <= 16, min side <= 8, max side > 1024, flat colour, 1-D gradient,
         noise (mean neighbour delta > 60/255), normal maps (mean ~ 128,128,255+); every skip is logged.
  pad    per axis: if the wrap-around seam looks continuous the texture is tiled with
         a wrap pad, otherwise the edge pixels are smeared; --pad px on each side.
  alpha  realesrgan-ncnn-vulkan keeps and resizes the alpha plane of RGBA PNGs
         (checked), so alpha is passed through; fully opaque textures are written RGB.
  bleed  (needs numpy+Pillow) before upscaling, the RGB of transparent/mostly transparent texels
         (alpha < 128) is filled from the nearest opaque texels. Otherwise their black RGB bleeds
         into the visible edge and the upscaled leaf/fence textures come out 20-50 levels too dark.
  match  (needs numpy+Pillow) after upscaling, each output is shifted per channel so its mean (and,
         up to a 1.25x gain, its std) at source size equals the source's, weighted by the source
         alpha. Real-ESRGAN darkens opaque textures by 2-20 levels. Alpha is never touched.
  scale  4x for long side <= 256, else 2x by default. --large-scale 4 keeps 4x for
         larger sources too, so a 1024px source becomes 4096px. The padded center is
         cropped back, so output is exactly (w*s, h*s): same aspect as the original.
Resumable: files already in --out are skipped when their wrap policy and dimensions match.
Batches are bounded (--batch-mpx input megapixels per esrgan process) and, with --lock,
each batch waits for and holds the shared lock file (created exclusively, removed only
if it still names --owner).
"""
import argparse, os, re, shutil, struct, subprocess, sys, time, json

NAME = re.compile(r'^([0-9a-f]{16})_(\d+)x(\d+)_f([0-9a-f]+)\.png$', re.I)
NOWIN = getattr(subprocess, 'CREATE_NO_WINDOW', 0)
BELOW = 0x4000  # BELOW_NORMAL_PRIORITY_CLASS


def png_size(path):
    try:
        with open(path, 'rb') as f:
            header = f.read(24)
        if header[:8] == b'\x89PNG\r\n\x1a\n':
            return struct.unpack('>II', header[16:24])
    except OSError:
        pass
    return None


def run(cmd, **kw):
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=NOWIN | BELOW, **kw)


def raw_rgba(path, w, h):
    r = run(['ffmpeg', '-v', 'error', '-i', path, '-f', 'rawvideo', '-pix_fmt', 'rgba', '-'])
    if r.returncode or len(r.stdout) != w * h * 4:
        return None
    return r.stdout


def analyze(path, w, h):
    """Return (skip_reason|None, has_alpha, seam_x, inner_x, seam_y, inner_y): mean abs gray delta across the
    wrap-around seam vs between neighbouring columns/rows (all 0 for skipped textures)."""
    d = raw_rgba(path, w, h)
    if d is None:
        return 'decode failed', False, 0, 0, 0, 0
    alpha = d[3::4]
    has_alpha = min(alpha) < 255
    chans = [d[c::4] for c in range(4)]
    if all(max(c) - min(c) <= 4 for c in chans):
        return 'flat colour', has_alpha, 0, 0, 0, 0
    mr, mg, mb = (sum(chans[c][::7]) / len(chans[c][::7]) for c in range(3))
    if 110 < mr < 146 and 110 < mg < 146 and mb > 190:
        return 'normal map', has_alpha, 0, 0, 0, 0
    g = bytes((d[i] * 77 + d[i + 1] * 150 + d[i + 2] * 29) >> 8 for i in range(0, len(d), 4)) if w * h <= 1 << 20 else None
    if g is None:
        return 'too large to analyze', has_alpha, 0, 0, 0, 0
    rows = [g[y * w:(y + 1) * w] for y in range(h)]
    cols = [g[x::w] for x in range(w)]

    def dif(a, b):
        return sum(abs(p - q) for p, q in zip(a, b)) / len(a)
    ys = range(0, h - 1, max(1, (h - 1) // 24)); xs = range(0, w - 1, max(1, (w - 1) // 24))
    row_in = sum(dif(rows[y], rows[y + 1]) for y in ys) / len(ys)
    col_in = sum(dif(cols[x], cols[x + 1]) for x in xs) / len(xs)
    # 1-D gradient: every row equal (varies only along x) or every column equal
    row_var = sum(dif(rows[y], rows[0]) for y in ys) / len(ys)
    col_var = sum(dif(cols[x], cols[0]) for x in xs) / len(xs)
    if row_var < 2 or col_var < 2:
        return '1-D gradient/LUT', has_alpha, 0, 0, 0, 0
    # noise: neighbour delta in both directions is large
    if row_in > 60 and col_in > 60:
        return 'noise (delta %.0f)' % ((row_in + col_in) / 2), has_alpha, 0, 0, 0, 0
    return None, has_alpha, dif(cols[0], cols[-1]), col_in, dif(rows[0], rows[-1]), row_in


def pad_graph(w, h, p, wrap_x, wrap_y, has_alpha):
    """One ffmpeg filter_complex graph: wrap pad (continuous seam) or edge smear, per axis."""
    px, py = min(p, w), min(p, h)
    g = '[0:v]format=%s[s0];' % ('rgba' if has_alpha else 'rgb24')
    if wrap_x:
        g += '[s0]split=3[a][b][c];[a][b][c]hstack=inputs=3,crop=%d:%d:%d:0[s1];' % (w + 2 * px, h, w - px)
    else:
        g += '[s0]pad=%d:%d:%d:0,fillborders=left=%d:right=%d:mode=smear[s1];' % (w + 2 * px, h, px, px, px)
    if wrap_y:
        g += '[s1]split=3[d][e][f];[d][e][f]vstack=inputs=3,crop=%d:%d:0:%d[o]' % (w + 2 * px, h + 2 * py, h - py)
    else:
        g += '[s1]pad=%d:%d:0:%d,fillborders=top=%d:bottom=%d:mode=smear[o]' % (w + 2 * px, h + 2 * py, py, py, py)
    return g, px, py


def ff(src, dst, graph):
    r = run(['ffmpeg', '-v', 'error', '-y', '-i', src, '-filter_complex', graph, '-map', '[o]', '-frames:v', '1', '-update', '1', dst])
    if r.returncode:
        raise RuntimeError(r.stderr.decode(errors='replace')[:300])


def _np():
    try:
        import numpy as np
        from PIL import Image
        return np, Image
    except ImportError:
        return None, None


def bleed_rgb(path, thr=128, maxit=512):
    """Fill RGB of texels with alpha < thr from the nearest texels with alpha >= thr (alpha unchanged)."""
    np, Image = _np()
    if np is None: return
    im = np.array(Image.open(path).convert('RGBA'))
    known = im[..., 3] >= thr
    if known.all() or not known.any(): return
    rgb = im[..., :3].astype(np.float32); k = known.copy()
    for _ in range(maxit):
        if k.all(): break
        kf = k.astype(np.float32)[..., None]
        acc = np.zeros_like(rgb); cnt = np.zeros(k.shape + (1,), np.float32)
        pr = np.pad(rgb * kf, ((1, 1), (1, 1), (0, 0))); pk = np.pad(kf, ((1, 1), (1, 1), (0, 0)))
        H, W = k.shape
        for dy in (0, 1, 2):
            for dx in (0, 1, 2):
                if dy == 1 and dx == 1: continue
                acc += pr[dy:dy + H, dx:dx + W]; cnt += pk[dy:dy + H, dx:dx + W]
        new = (~k) & (cnt[..., 0] > 0)
        if not new.any(): break
        rgb[new] = acc[new] / cnt[new]; k |= new
    im[..., :3] = np.clip(rgb + 0.5, 0, 255).astype(np.uint8)
    Image.fromarray(im, 'RGBA').save(path)


def match_color(src_png, out_png, max_gain=1.25):
    """Shift/scale the output's RGB so its mean/std at source size match the source. Returns (dmean, gain) or None."""
    np, Image = _np()
    if np is None: return None
    o = np.asarray(Image.open(src_png).convert('RGBA'), np.float32)
    u_img = Image.open(out_png); has_a = u_img.mode == 'RGBA'
    u = np.asarray(u_img.convert('RGBA'), np.float32)
    H, W = o.shape[:2]; k = u.shape[0] // H
    if k < 1 or u.shape[0] != H * k or u.shape[1] != W * k: return None
    d = u.reshape(H, k, W, k, 4).mean((1, 3))
    w = o[..., 3:] / 255.0 if has_a else np.ones((H, W, 1), np.float32)
    sw = float(w.sum())
    if sw < 0.02 * H * W: return None
    def stats(a):
        m = (a[..., :3] * w).sum((0, 1)) / sw
        return m, np.sqrt((((a[..., :3] - m) ** 2) * w).sum((0, 1)) / sw)
    mo, so = stats(o); md, sd = stats(d)
    g = np.clip(so / np.maximum(sd, 1e-3), 1.0, max_gain)
    out = np.clip((u[..., :3] - md) * g + mo, 0, 255)
    res = np.concatenate([out, u[..., 3:]], 2) if has_a else out
    Image.fromarray(np.clip(res + 0.5, 0, 255).astype(np.uint8), 'RGBA' if has_a else 'RGB').save(out_png)
    return (mo - md).round(1).tolist(), g.round(2).tolist()


def acquire(lock, owner, log):
    t0 = time.time()
    while True:
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.write(fd, ('%s %s\n' % (owner, time.strftime('%Y-%m-%dT%H:%M:%S'))).encode()); os.close(fd)
            return
        except FileExistsError:
            if time.time() - t0 > 3600:
                raise SystemExit('lock wait timed out')
            time.sleep(15)


def release(lock, owner):
    try:
        with open(lock) as f:
            mine = f.read().startswith(owner + ' ')
        if mine:
            os.remove(lock)
    except OSError:
        pass


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='ins', nargs='+', required=True)
    ap.add_argument('--out', required=True)
    ap.add_argument('--work')
    ap.add_argument('--esrgan', default='realesrgan-ncnn-vulkan')
    ap.add_argument('--models')
    ap.add_argument('--model', default='realesrgan-x4plus')
    ap.add_argument('--pad', type=int, default=32)
    ap.add_argument('--batch-mpx', type=float, default=6.0)
    ap.add_argument('--limit', type=int, default=0)
    ap.add_argument('--large-scale', type=int, choices=(2, 4), default=2,
                    help='output scale for sources wider or taller than 256px (default 2; 4 permits 4K)')
    ap.add_argument('--wrap-k', type=float, default=2.2, help='wrap pad an axis when seam delta <= k*inner delta + 2')
    ap.add_argument('--prev-k', type=float, default=2.2, help='k used for outputs that have no manifest entry')
    ap.add_argument('--only-alpha', action='store_true', help='process only textures that have an alpha channel')
    ap.add_argument('--no-match', action='store_true', help='skip the post-upscale colour match')
    ap.add_argument('--rematch', action='store_true', help='only colour-match the files already in --out (no upscaling)')
    ap.add_argument('--lock'); ap.add_argument('--owner', default='make_hd_pack')
    a = ap.parse_args()
    out = os.path.abspath(a.out); os.makedirs(out, exist_ok=True)
    work = os.path.abspath(a.work or (out.rstrip('\\/') + '_work')); os.makedirs(work, exist_ok=True)
    logf = open(os.path.join(work, 'pack.log'), 'a', buffering=1)

    def log(s):
        print(s, flush=True); logf.write(s + '\n')

    files = {}
    for d in a.ins:
        for n in sorted(os.listdir(d)):
            if NAME.match(n) and n not in files:
                files[n] = os.path.join(d, n)
    log('unique textures: %d' % len(files))
    todo = []  # texture jobs
    skips = {}
    cpath = os.path.join(work, 'analysis.json'); mpath = os.path.join(work, 'manifest.json')
    cache = json.load(open(cpath)) if os.path.exists(cpath) else {}
    manifest = json.load(open(mpath)) if os.path.exists(mpath) else {}
    for n, path in files.items():
        m = NAME.match(n); w, h = int(m.group(2)), int(m.group(3))
        mx, mn = max(w, h), min(w, h)
        why = None
        if mx <= 16: why = 'tiny (<=16)'
        elif mn <= 8: why = 'strip/LUT (min side <=8)'
        elif mx > 1024: why = 'too big (>1024)'
        has_alpha = False; wx = wy = False
        if not why:
            if n not in cache:
                cache[n] = list(analyze(path, w, h)); json.dump(cache, open(cpath, 'w'))
            why, has_alpha, sx, ix, sy, iy = cache[n]
            wx = sx <= a.wrap_k * ix + 2; wy = sy <= a.wrap_k * iy + 2
        if why:
            skips[n] = why; log('SKIP %s: %s' % (n, why)); continue
        if a.only_alpha and not has_alpha: continue
        if a.rematch: continue
        scale = 4 if mx <= 256 else a.large_scale
        out_path = os.path.join(out, n)
        if os.path.exists(out_path):
            prev = manifest.get(n)
            if prev is None:
                prev = [sx <= a.prev_k * ix + 2, sy <= a.prev_k * iy + 2]
            actual = png_size(out_path)
            if list(prev) == [wx, wy] and actual == (w * scale, h * scale):
                continue
            log('REDO %s: wrap %s -> %s, size %s -> %s' %
                (n, prev, [wx, wy], actual, (w * scale, h * scale)))
        graph, px, py = pad_graph(w, h, a.pad, wx, wy, has_alpha)
        todo.append(dict(n=n, path=path, w=w, h=h, scale=scale, px=px, py=py, g=graph, alpha=has_alpha, wx=wx, wy=wy))
        if a.limit and len(todo) >= a.limit: break
    log('to process: %d, skipped: %d' % (len(todo), len(skips)))
    for k in sorted(set(skips.values())):
        log('  skip reason %-30s %d' % (k, sum(1 for v in skips.values() if v == k)))

    batches, cur, mpx = [], [], 0.0
    for t in todo:
        px = (t['w'] + 2 * t['px']) * (t['h'] + 2 * t['py']) / 1e6
        if cur and mpx + px > a.batch_mpx:
            batches.append(cur); cur, mpx = [], 0.0
        cur.append(t); mpx += px
    if cur: batches.append(cur)
    exe = os.path.abspath(a.esrgan) if os.path.exists(a.esrgan) else a.esrgan
    for bi, b in enumerate(batches):
        din = os.path.join(work, 'in'); dout = os.path.join(work, 'out')
        for d in (din, dout):
            shutil.rmtree(d, ignore_errors=True); os.makedirs(d)
        for t in b:
            ff(t['path'], os.path.join(din, t['n']), t['g'])
            if t['alpha']: bleed_rgb(os.path.join(din, t['n']))
        cmd = [exe, '-i', din, '-o', dout, '-n', a.model, '-f', 'png']
        if a.models: cmd += ['-m', a.models]
        t0 = time.time()
        if a.lock: acquire(a.lock, a.owner, log)
        try:
            p = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, creationflags=NOWIN | BELOW)
            try:
                p.wait(timeout=540)
            except subprocess.TimeoutExpired:
                subprocess.run(['taskkill', '/PID', str(p.pid), '/T', '/F'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                log('batch %d timed out' % bi)
        finally:
            if a.lock: release(a.lock, a.owner)
        okc = 0
        for t in b:
            up = os.path.join(dout, t['n'])
            if not os.path.exists(up):
                log('FAIL (no esrgan output) %s' % t['n']); continue
            W, H, s = t['w'], t['h'], t['scale']
            g = '[0:v]crop=%d:%d:%d:%d' % (W * 4, H * 4, t['px'] * 4, t['py'] * 4)
            if s != 4: g += ',scale=%d:%d:flags=lanczos' % (W * s, H * s)
            g += ',format=%s[o]' % ('rgba' if t['alpha'] else 'rgb24')
            try:
                ff(up, os.path.join(out, t['n']), g); okc += 1
                if not a.no_match:
                    r = match_color(t['path'], os.path.join(out, t['n']))
                    if r: log('match %s dmean %s gain %s' % (t['n'], r[0], r[1]))
                manifest[t['n']] = [t['wx'], t['wy']]; json.dump(manifest, open(mpath, 'w'))
            except RuntimeError as e:
                log('FAIL %s %s' % (t['n'], e))
        log('batch %d/%d: %d files, %.1f Mpx in, %.0f s, ok %d' % (bi + 1, len(batches), len(b), sum((x['w'] + 2 * x['px']) * (x['h'] + 2 * x['py']) for x in b) / 1e6, time.time() - t0, okc))
    shutil.rmtree(os.path.join(work, 'in'), ignore_errors=True); shutil.rmtree(os.path.join(work, 'out'), ignore_errors=True)

    if a.rematch:
        for n, path in files.items():
            if os.path.exists(os.path.join(out, n)):
                r = match_color(path, os.path.join(out, n))
                if r: log('rematch %s dmean %s gain %s' % (n, r[0], r[1]))
    # stats
    tot = 0; gpu = 0; n = 0
    for f in os.listdir(out):
        m = NAME.match(f)
        if not m: continue
        path = os.path.join(out, f)
        size = png_size(path)
        if size is None: continue
        w, h = size
        tot += os.path.getsize(path); gpu += w * h * 4 * 4 // 3; n += 1
    log('pack: %d files, %.1f MB on disk, est GPU %.0f MB (RGBA8 + mips) vs default cap 768 MB' % (n, tot / 1048576, gpu / 1048576))


if __name__ == '__main__':
    main()
