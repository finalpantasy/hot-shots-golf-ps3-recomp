#!/usr/bin/env python3
"""English menus and text for the JP 1.27 build (Minna no Golf 6, BCJS30089).

usage: jp127_english.py apply  [--out A:/hsg-ultimate] [--dry]
       jp127_english.py needs  OUT.tsv          (JP strings with no English source, for translating)
       jp127_english.py report OUT.tsv          (per-archive texture swap list)

The JP updates 01.01 .. 01.27 replace almost every localized menu archive (*.JP_00.xb) with a
Japanese one, so the US base data renamed to JP_00 by build_ultimate_data.py is shadowed. This
tool rebuilds each of those JP update archives with English content and writes the result over
<out>/game/USRDIR/<rel> and <out>/hdd0/game/BCJS30089/USRDIR/<rel> (both: the VFS reads hdd0
first). The outputs are unlinked before writing, so the hard-linked update extraction under
A:/hsg-updates is never modified. Nothing is written into git.

English sources, newest layer wins:
  US:   work/game/base-1.00/USRDIR + A:/hsg-updates/x/NPUA80864/01.01..01.03/USRDIR   (*.US_01.xb)
  Asia: A:/Everybody's Golf 6 (Asia)/PS3_GAME/USRDIR + A:/hsg-updates/x/BCAS20276/01.01..01.03 (*.AS_01.xb)

message_text (TO1 string tables, one per entry hash): the JP table layout is kept (the JP program
indexes it), every string takes the US string at the same (table, group, index), else Asia, else
the translation in translations/jp127/message_text.tsv; anything left keeps the JP string and is
listed by `needs`. A US/Asia string that is only a placeholder (" ", "???") does not count.

Layout archives (FB entries: .lay layouts, .map chip maps, .dds textures): JP layouts and maps
are kept; a JP texture is replaced by the English texture with the same entry hash when the size
matches and its chip map is equal in both (or absent), or when the JP map's chips are all in the
English map at the same rectangles. Other JP textures stay (listed by `report`).

TO1 layout: "TO1\\0", u32 hash, u32 ngroups, u32 maxlen, ngroups x {u32 offset, u32 count,
u32 maxlen}; then the u32 string-offset tables; then NUL-terminated UTF-8 strings. maxlen is the
longest string in code points (group) and over all groups (header). All little-endian.
"""
import argparse, hashlib, os, re, struct, sys, zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
UPD_JP = Path("A:/hsg-updates/x/BCJS30089")
US_LAYERS = [ROOT / "work/game/base-1.00/USRDIR"] + \
    [Path("A:/hsg-updates/x/NPUA80864") / v / "USRDIR" for v in ("01.01", "01.02", "01.03")]
AS_LAYERS = [Path("A:/Everybody's Golf 6 (Asia) (En,Zh,Ko)/PS3_GAME/USRDIR")] + \
    [Path("A:/hsg-updates/x/BCAS20276") / v / "USRDIR" for v in ("01.01", "01.02", "01.03")]
TRANS = ROOT / "translations/jp127/message_text.tsv"
MSG_REL = "xbdata/menu/message_text.JP_00.xb"
PLACEHOLDER = {"", " ", "???", "？？？", "-", "－"}


# ---- FB archives --------------------------------------------------------------
class FB:
    """FB archive: rows {hash, ordinal, stored, raw}; row k also sizes payload k; the payload
    of a name is payload[ordinal of the row whose hash matches]."""

    def __init__(self, data):
        if data[:3] != b"FB\0":
            raise ValueError("not an FB archive")
        self.magic = data[:4]
        n, e = struct.unpack_from("<II", data, 4)
        self.extra = data[12:12 + e]
        self.rows = [list(struct.unpack_from("<5I", data, 12 + e + 20 * i)) for i in range(n)]
        pos = 12 + e + 20 * n
        self.blobs = []
        for r in self.rows:
            pos = (pos + 3) & ~3
            self.blobs.append(data[pos:pos + r[3]])
            pos += r[3]
        self.index = {r[0]: r[2] for r in self.rows}

    def keys(self):
        return list(self.index)

    def get(self, h):
        k = self.index[h]
        z = self.blobs[k]
        if not z:
            return b""
        return zlib.decompress(z) if z[:1] == b"\x78" and self.rows[k][3] != self.rows[k][4] else z

    def put(self, h, raw):
        k = self.index[h]
        self.blobs[k] = zlib.compress(raw, 9)
        self.rows[k][3], self.rows[k][4] = len(self.blobs[k]), len(raw)

    def bytes(self):
        out = bytearray(self.magic + struct.pack("<II", len(self.rows), len(self.extra)) + self.extra)
        for r in self.rows:
            out += struct.pack("<5I", *r)
        for b in self.blobs:
            out += b"\0" * (-len(out) % 4)
            out += b
        return bytes(out)


def fb_load(p):
    return FB(Path(p).read_bytes())


# ---- TO1 string tables ----------------------------------------------------------
def to1_read(d):
    if d[:4] != b"TO1\0":
        return None
    h, n = struct.unpack_from("<II", d, 4)
    groups = []
    for g in range(n):
        off, cnt, _ml = struct.unpack_from("<III", d, 16 + g * 12)
        ss = []
        for i in range(cnt):
            so = struct.unpack_from("<I", d, off + i * 4)[0]
            ss.append(d[so:d.index(b"\0", so)].decode("utf-8", "surrogateescape"))
        groups.append(ss)
    return h, groups


def to1_write(h, groups):
    n = len(groups)
    head = 16 + 12 * n
    tables = head + 4 * sum(len(g) for g in groups)
    strs, offs, cache = bytearray(), [], {}
    for g in groups:
        o = []
        for s in g:
            if s not in cache:
                cache[s] = tables + len(strs)
                strs += s.encode("utf-8", "surrogateescape") + b"\0"
            o.append(cache[s])
        offs.append(o)
    mls = [max((len(s) for s in g), default=0) for g in groups]
    out = bytearray(b"TO1\0" + struct.pack("<III", h, n, max(mls, default=0)))
    t = head
    for g, ml in zip(groups, mls):
        out += struct.pack("<III", t, len(g), ml)
        t += 4 * len(g)
    for o in offs:
        out += struct.pack("<%dI" % len(o), *o)
    out += strs
    out += b"\0" * (-len(out) % 4)
    return bytes(out)


# ---- sources --------------------------------------------------------------------
def layered(layers, rel):
    """Newest layer holding rel (case-insensitive file name match within the dir)."""
    hit = None
    for top in layers:
        p = top / rel
        if p.exists():
            hit = p
    return hit


def jp_update_files():
    vers = sorted(p.name for p in UPD_JP.iterdir() if re.fullmatch(r"01\.\d\d", p.name))
    files = {}
    for v in vers:
        u = UPD_JP / v / "USRDIR"
        for dp, _, fs in os.walk(u):
            for f in fs:
                if ".JP_00." in f:
                    files[Path(dp, f).relative_to(u).as_posix()] = Path(dp, f)
    return files


def english_sources(rel):
    us = layered(US_LAYERS, rel.replace(".JP_00.", ".US_01.").replace("chara/", "chara_localize/"))
    asia = layered(AS_LAYERS, rel.replace(".JP_00.", ".AS_01."))
    return us, asia


# ---- translation table ------------------------------------------------------------
def esc(s):
    out = []
    for c in s:
        if c == "\\": out.append("\\\\")
        elif c == "\n": out.append("\\n")
        elif c == "\t": out.append("\\t")
        elif ord(c) < 0x20: out.append("\\x%02x" % ord(c))
        else: out.append(c)
    return "".join(out)


def unesc(s):
    return re.sub(r"\\(x[0-9a-fA-F]{2}|n|t|\\)",
                  lambda m: {"n": "\n", "t": "\t", "\\": "\\"}.get(m.group(1)) or chr(int(m.group(1)[1:], 16)), s)


def jp_hash(s):
    """First 16 hex of SHA-1 over the string's UTF-8 bytes; the table stores this, not game text."""
    return hashlib.sha1(s.encode("utf-8", "surrogateescape")).hexdigest()[:16]


def load_translations(path=TRANS):
    """key 'table:group:index' -> (jp_hash, en). Lines: key<TAB>jp-hash<TAB>en; '#' comments."""
    tr = {}
    if not path.exists():
        return tr
    for ln in path.read_text(encoding="utf-8").splitlines():
        if not ln.strip() or ln.startswith("#"):
            continue
        k, jp, en = ln.split("\t")
        tr[k] = (jp.strip().lower(), unesc(en))
    return tr


# ---- message_text -------------------------------------------------------------------
DUMMY_RE = re.compile(r"^[（(]?\s*dummy\s*[）)]?$", re.I)


def real(s):
    return s is not None and s.strip() not in PLACEHOLDER and not DUMMY_RE.match(s.strip())


CODE_RE = re.compile(r"%[-+ #0-9.]*[a-zA-Z%]|[\x00-\x06\x08\x09\x0b-\x1f].")


def codes(s):
    """printf specifiers and button/icon codes (control byte + selector), in order; colour
    codes (\x07X) may move. A translation must keep these the same as the Japanese string."""
    return CODE_RE.findall(s)


def has_japanese(s):
    """Kana, kanji or full-width forms (U+3000-U+9FFF, U+FF00-U+FFEF)."""
    return any(0x3000 <= ord(c) <= 0x9FFF or 0xFF00 <= ord(c) <= 0xFFEF for c in s)


def merge_messages(jp_fb, us_fb, as_fb, tr, needs=None, stats=None):
    stats = stats if stats is not None else {}
    for h in jp_fb.keys():
        t = to1_read(jp_fb.get(h))
        if t is None:
            continue
        _, jg = t
        ug = to1_read(us_fb.get(h))[1] if us_fb and h in us_fb.index and to1_read(us_fb.get(h)) else []
        ag = to1_read(as_fb.get(h))[1] if as_fb and h in as_fb.index and to1_read(as_fb.get(h)) else []
        new = []
        for gi, ss in enumerate(jg):
            row = []
            for i, s in enumerate(ss):
                key = "%08x:%d:%d" % (h, gi, i)
                us = ug[gi][i] if gi < len(ug) and i < len(ug[gi]) else None
                asi = ag[gi][i] if gi < len(ag) and i < len(ag[gi]) else None
                if not real(s):
                    pick, src = (us if us is not None else s), "blank"
                elif real(us):
                    pick, src = us, "us"
                elif key in tr and tr[key][0] == jp_hash(s) and codes(s) == codes(tr[key][1]):
                    pick, src = tr[key][1], "translated"   # also overrides Asia slots reused for Asia-only items
                elif real(asi):
                    pick, src = asi, "asia"
                elif not has_japanese(s):
                    pick, src = s, "neutral"      # icon codes, numbers, Latin names
                else:
                    pick, src = s, "japanese"
                    if needs is not None:
                        needs.append((key, s))
                stats[src] = stats.get(src, 0) + 1
                row.append(pick)
            new.append(row)
        if new != jg:
            jp_fb.put(h, to1_write(h, new))
    return stats


# ---- layout archives ------------------------------------------------------------------
MAP_DELTA = 0x2169   # hash(name.map) - hash(name.dds): same name, extension d,d,s -> m,a,p
MODEL_DELTA = 0x1188  # banner motion entry hash - banner model entry hash (same name, other extension)


def fb_hash(name):
    """FB entry key: h = h*31 + c over the ASCII-lowercased name (32-bit)."""
    h = 0
    for c in name.lower().encode("latin-1"):
        h = (h * 31 + c) & 0xFFFFFFFF
    return h


def is_dds(b):
    return b[:4] == b"DDS "


def dds_dims(b):
    h, w = struct.unpack_from("<II", b, 12)
    return w, h


def map_chips(b):
    """MAP1 chip map -> {chip name: rect tuple}."""
    out = {}
    for ln in b.decode("utf-8", "replace").splitlines()[2:]:
        p = ln.split(",")
        if len(p) >= 5:
            out[p[0]] = tuple(p[1:5])
    return out


def chip_rects(b):
    return [ln.split(",")[1:5] for ln in b.decode("utf-8", "replace").splitlines()[1:] if ln.strip()]


def chip_names(b):
    return [ln.split(",")[0] for ln in b.decode("utf-8", "replace").splitlines()[2:] if ln.strip()]


def merge_layout(jp_fb, en_fb, texdir=None):
    """Swap JP textures for English ones in place. Returns (swapped, kept_jp list).

    Layouts address chips by index in the texture's MAP1 chip map; chip rectangles are in the
    map's logical size, so a texture of another pixel size is fine when its map comes along.
    Swapped: same-size texture whose JP chips sit at the same rectangles in the English map, or
    any texture whose English map lists the same chips (names, or rectangles incl. the logical
    size) in the same order (texture + map swapped).
    """
    swapped, kept = 0, []
    done = set()
    # 3D banner models (e.g. "WATER HAZARD", "UNPLAYABLE"): a model entry plus a motion entry
    # (model hash + MODEL_DELTA) whose texture list names "<name>.tga"; the texture entry is
    # data/<archive dir>/<name>.dds. JP and US lay the letters out differently, so the model,
    # motion and textures are taken from the English archive together.
    for h in jp_fb.keys():
        if h not in en_fb.index:
            continue
        jb, eb = jp_fb.get(h), en_fb.get(h)
        if jb == eb or is_dds(jb) or jb[:4] in (b"LAY1", b"MAP1"):
            continue
        names = sorted(set(re.findall(rb"([A-Za-z0-9_]+)\.tga", eb)))
        if not names or not texdir:
            continue
        texs = [fb_hash(texdir + n.decode() + ".dds") for n in names]
        if not all(t in en_fb.index and t in jp_fb.index and is_dds(en_fb.get(t)) for t in texs):
            continue
        group = [h] + [m for m in ((h - MODEL_DELTA) & 0xFFFFFFFF,) if m in jp_fb.index and m in en_fb.index]
        for e in group + texs:
            if jp_fb.get(e) != en_fb.get(e):
                jp_fb.put(e, en_fb.get(e))
            done.add(e)
        swapped += len(texs)
    for h in jp_fb.keys():
        if h in done:
            continue
        jb = jp_fb.get(h)
        if not is_dds(jb):
            continue
        if h not in en_fb.index:
            kept.append((h, "jp-only", dds_dims(jb)))
            continue
        eb = en_fb.get(h)
        if eb == jb or not is_dds(eb):
            continue
        m = (h + MAP_DELTA) & 0xFFFFFFFF
        jm = jp_fb.get(m) if m in jp_fb.index else None
        em = en_fb.get(m) if m in en_fb.index else None
        if dds_dims(eb) == dds_dims(jb) and (jm == em or (jm is not None and em is not None and all(
                map_chips(em).get(k) == v for k, v in map_chips(jm).items()))):
            jp_fb.put(h, eb)
        elif jm is not None and em is not None and (chip_names(jm) == chip_names(em) or
                                                    chip_rects(jm) == chip_rects(em)):
            jp_fb.put(h, eb)
            jp_fb.put(m, em)
        else:
            why = "chip map differs" if jm is not None or em is not None else                 "size %dx%d vs en %dx%d, no chip map" % (dds_dims(jb) + dds_dims(eb))
            kept.append((h, why, dds_dims(jb)))
            continue
        swapped += 1
    return swapped, kept


# ---- driver -----------------------------------------------------------------------------
def write_out(data, dsts, dry):
    for d in dsts:
        if dry:
            continue
        d.parent.mkdir(parents=True, exist_ok=True)
        if d.exists():
            d.unlink()      # may be a hard link into A:/hsg-updates; never write through it
        d.write_bytes(data)


def build(out, dry=False, needs=None, report=None):
    tr = load_translations()
    files = jp_update_files()
    tot = {"archives": 0, "textures_swapped": 0}
    msg_stats = {}
    for rel, src in sorted(files.items()):
        us, asia = english_sources(rel)
        if us is None and asia is None:
            if report is not None:
                fb = fb_load(src)
                for h in fb.keys():
                    b = fb.get(h)
                    if is_dds(b):
                        report.append((rel, h, "no English archive", dds_dims(b)))
            continue
        jp = fb_load(src)
        if rel == MSG_REL:
            merge_messages(jp, fb_load(us) if us else None, fb_load(asia) if asia else None, tr, needs, msg_stats)
        else:
            en = fb_load(us or asia)
            texdir = "data/" + rel.split("/", 1)[1].rsplit("/", 1)[0] + "/"
            sw, kept = merge_layout(jp, en, texdir)
            tot["textures_swapped"] += sw
            if report is not None:
                report.extend((rel,) + k for k in kept)
        tot["archives"] += 1
        write_out(jp.bytes(), [out / "game/USRDIR" / rel, out / "hdd0/game/BCJS30089/USRDIR" / rel], dry)
    tot.update({"msg_" + k: v for k, v in msg_stats.items()})
    return tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["apply", "needs", "report"])
    ap.add_argument("file", nargs="?")
    ap.add_argument("--out", default="A:/hsg-ultimate")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    out = Path(a.out)
    if a.cmd == "apply":
        print("[english]", build(out, a.dry))
        return 0
    if a.cmd == "needs":
        needs = []
        print("[english]", build(out, True, needs=needs))
        with open(a.file, "w", encoding="utf-8", newline="\n") as f:
            for k, s in needs:
                f.write("%s\t%s\t\n" % (k, esc(s)))
        print("[english] %d strings without an English source -> %s" % (len(needs), a.file))
        return 0
    rep = []
    print("[english]", build(out, True, report=rep))
    with open(a.file, "w", encoding="utf-8", newline="\n") as f:
        f.write("archive\tentry_hash\treason\twidth\theight\n")
        for rel, h, why, (w, hh) in rep:
            f.write("%s\t%08x\t%s\t%d\t%d\n" % (rel, h, why, w, hh))
    print("[english] %d JP textures kept -> %s" % (len(rep), a.file))
    return 0


if __name__ == "__main__":
    sys.exit(main())
