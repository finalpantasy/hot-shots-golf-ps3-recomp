#!/usr/bin/env python3
"""English menus and text for the JP 1.27 build (Minna no Golf 6, BCJS30089).

usage: jp127_english.py apply  [--out A:/hsg-ultimate] [--dry]
       jp127_english.py labels                 (regenerate translations/jp127/rare_labels.dxt5.z)
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

if getattr(sys, "frozen", False):          # PyInstaller launcher: bundled data sits in _MEIPASS
    ROOT = Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
else:
    ROOT = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(ROOT / "tools"))
UPD_JP = Path("A:/hsg-updates/x/BCJS30089")
US_LAYERS = [ROOT / "work/game/base-1.00/USRDIR"] + \
    [Path("A:/hsg-updates/x/NPUA80864") / v / "USRDIR" for v in ("01.01", "01.02", "01.03")]
AS_LAYERS = [Path("A:/Everybody's Golf 6 (Asia) (En,Zh,Ko)/PS3_GAME/USRDIR")] + \
    [Path("A:/hsg-updates/x/BCAS20276") / v / "USRDIR" for v in ("01.01", "01.02", "01.03")]
TRANS = ROOT / "translations/jp127/message_text.tsv"


def configure(jp_updates=None, base_usrdir=None, us_updates=None, asia_dir=None,
              asia_updates=None, translations=None):
    """Point the tool at other folders (the launcher's Ultimate setup). None keeps the default.
    us_updates / asia_updates hold the extracted updates 01.01..01.03 of NPUA80864 / BCAS20276;
    asia_dir is the Asia PS3_GAME folder. A missing layer is skipped."""
    global UPD_JP, US_LAYERS, AS_LAYERS, TRANS
    if jp_updates:
        UPD_JP = Path(jp_updates)
    if base_usrdir or us_updates:
        base = Path(base_usrdir) if base_usrdir else US_LAYERS[0]
        up = Path(us_updates) if us_updates else US_LAYERS[1].parent.parent
        US_LAYERS = [base] + [up / v / "USRDIR" for v in ("01.01", "01.02", "01.03")]
    if asia_dir or asia_updates:
        base = Path(asia_dir) / "USRDIR" if asia_dir else AS_LAYERS[0]
        up = Path(asia_updates) if asia_updates else AS_LAYERS[1].parent.parent
        AS_LAYERS = [base] + [up / v / "USRDIR" for v in ("01.01", "01.02", "01.03")]
    if translations:
        TRANS = Path(translations)


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


def load_translations(path=None):
    path = path or TRANS
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


# ---- rare / normal character labels (character select help bar) -------------------------
# The SELECT prompt on character select ("switch to rare / normal characters") is drawn from
# chips 1-2 of the help-label texture common_help05 in menu/info. US never shipped English for
# it, so those two chips stay Japanese. translations/jp127/rare_labels.dxt5.z holds our own
# English rendering of the two labels ("Normal Characters", "Rare Characters"; system font, no
# game pixels): the DXT5 blocks of texture rows 0..83 (block rows 0..20, 64 blocks of 16 bytes
# each), zlib-compressed. `labels` regenerates it (needs Pillow; the launcher does not).
INFO_REL = "xbdata/menu/info.JP_00.xb"
LABEL_MAP = 0xD51E9AD9                       # common_help05.map
LABEL_MAP_TEXT = ("MAP1\ncommon_help05,128,128,32\ncommon_help05@mess01_001,0,0,127,19\n"
                  "common_help05@mess01_002,0,21,127,40\n")
LABEL_TEXTS = ("Normal Characters", "Rare Characters")   # chip 1 (normal), chip 2 (rare)
LABEL_ROWS = 21                              # DXT block rows replaced (pixels 0..83)


def label_asset():
    return TRANS.parent / "rare_labels.dxt5.z"


def paint_rare_labels(fb):
    """Replace the two Japanese chips of common_help05 with the English asset. Returns 1 when
    patched, 0 when the asset or the expected texture is missing (left as is)."""
    tex = (LABEL_MAP - MAP_DELTA) & 0xFFFFFFFF
    p = label_asset()
    if LABEL_MAP not in fb.index or tex not in fb.index or not p.exists():
        return 0
    if not fb.get(LABEL_MAP).decode("utf-8", "replace").replace(chr(13), "").startswith(LABEL_MAP_TEXT):
        return 0
    b = bytearray(fb.get(tex))
    if not is_dds(b) or dds_dims(b) != (256, 256) or b[84:88] != b"DXT5" or len(b) < 128 + 65536:
        return 0
    blocks = zlib.decompress(p.read_bytes())
    if len(blocks) != LABEL_ROWS * 64 * 16:
        return 0
    b[128:128 + len(blocks)] = blocks
    fb.put(tex, bytes(b))
    return 1


def make_label_asset(font="C:/Windows/Fonts/bahnschrift.ttf"):
    """Render LABEL_TEXTS (white, dark outline, like the US help labels) and write the asset."""
    from PIL import Image, ImageDraw, ImageFilter, ImageFont
    import io
    img = Image.new("RGBA", (256, LABEL_ROWS * 4), (0, 0, 0, 0))
    for i, text in enumerate(LABEL_TEXTS):
        y0, h = i * 42, 40                   # chip rects 0..19 / 21..40 at 2x (256 px texture)
        f = ImageFont.truetype(font, 29)
        try:
            f.set_variation_by_name("SemiBold Condensed")
        except Exception:
            pass
        tile = Image.new("L", (256, h), 0)
        d = ImageDraw.Draw(tile)
        bb = d.textbbox((0, 0), text, font=f)
        d.text((3 - bb[0], (h - (bb[3] - bb[1])) // 2 - bb[1]), text, font=f, fill=255)
        t = Image.new("RGBA", (256, h), (0, 0, 0, 0))
        t.paste((33, 32, 33, 255), (0, 0), tile.filter(ImageFilter.MaxFilter(5)))
        t.paste((255, 255, 255, 255), (0, 0), tile)
        img.alpha_composite(t, (0, y0))
    buf = io.BytesIO()
    img.save(buf, "DDS", pixel_format="DXT5")
    dds = buf.getvalue()
    if dds[84:88] != b"DXT5":
        raise SystemExit("Pillow did not write DXT5")
    blocks = dds[128:128 + LABEL_ROWS * 64 * 16]
    label_asset().write_bytes(zlib.compress(blocks, 9))
    return label_asset()


# ---- capsule machine labels (lobby capsule shop hosted offline, HSG_UNLOCKS=grind) ----------
# The capsule machine screens draw their words from texture atlases that US never localized
# (lobby_shop_layout, ticket_attention/history; the merged archives keep Japanese there).
# translations/jp127/capsule_labels.tsv lists each label: archive, texture (its chip-map name,
# or "#<texture entry hash>"), chip (or "-"), the chip rectangle as the map gives it (so a
# changed map is skipped), the painted rectangle in map units (or "-" = the chip), the
# background ("clear" = transparent, "fill:<n>" = repeat the texture column n pixels inside the
# left edge, for labels on a coloured box), a style name and the English.
# translations/jp127/capsule_labels.rgba.z holds our own renderings of those English labels
# (system font, no game pixels): per row u16 width, u16 height, RGBA. At apply time the
# DXT5 blocks under each painted rectangle are decoded, the old label replaced by the
# background, our label laid over it, and the blocks encoded again (pure Python, no Pillow).
# `labels` regenerates the asset (needs Pillow and the game files for the chip sizes).
CAPSULE_FIELDS = ("archive", "texture", "chip", "chip_rect", "paint_rect", "bg", "style", "english")


def capsule_paths():
    return TRANS.parent / "capsule_labels.tsv", TRANS.parent / "capsule_labels.rgba.z"


def capsule_rows():
    tsv, _ = capsule_paths()
    rows = []
    if not tsv.exists():
        return rows
    for ln in tsv.read_text(encoding="utf-8").splitlines():
        if not ln.strip() or ln.startswith("#"):
            continue
        p = ln.split("\t")
        if len(p) == len(CAPSULE_FIELDS):
            rows.append(dict(zip(CAPSULE_FIELDS, p)))
    return rows


def capsule_images():
    _, asset = capsule_paths()
    if not asset.exists():
        return None
    raw = zlib.decompress(asset.read_bytes())
    out, pos = [], 0
    while pos < len(raw):
        w, h = struct.unpack_from("<HH", raw, pos)
        pos += 4
        out.append((w, h, raw[pos:pos + w * h * 4]))
        pos += w * h * 4
    return out


def find_texture(fb, name):
    """(texture hash, chip map text or None) for a chip-map name or "#hash"."""
    if name.startswith("#"):
        h = int(name[1:], 16)
        return (h, None) if h in fb.index else (None, None)
    for h in fb.keys():
        b = fb.get(h)
        if b[:4] == b"MAP1":
            t = b.decode("utf-8", "replace").replace("\r", "")
            if t.split("\n")[1].split(",")[0] == name:
                tex = (h - MAP_DELTA) & 0xFFFFFFFF
                if tex in fb.index:
                    return tex, t
    return None, None


def label_rect_px(row, tex, mapt):
    """Painted rectangle in texture pixels [x0, y0, x1, y1), or None when the map changed."""
    w, h = dds_dims(tex)
    if mapt is None:
        lw, lh = w, h
        rect = row["paint_rect"]
    else:
        head = mapt.split("\n")[1].split(",")
        lw, lh = int(head[1]), int(head[2])
        chips = map_chips(mapt.encode("utf-8"))
        key = mapt.split("\n")[1].split(",")[0] + "@" + row["chip"]
        if ",".join(chips.get(key, ())) != row["chip_rect"]:
            return None
        rect = row["chip_rect"] if row["paint_rect"] == "-" else row["paint_rect"]
    x0, y0, x1, y1 = (int(v) for v in rect.split(","))
    sx, sy = w / lw, h / lh
    if mapt is None:                           # pixel rectangle, end exclusive
        return x0, y0, x1, y1
    return round(x0 * sx), round(y0 * sy), round((x1 + 1) * sx), round((y1 + 1) * sy)


def _c565(c):
    return ((c >> 11 & 31) * 255 // 31, (c >> 5 & 63) * 255 // 63, (c & 31) * 255 // 31)


def dxt5_decode(b):
    a0, a1 = b[0], b[1]
    if a0 > a1:
        al = [a0, a1] + [((7 - i) * a0 + i * a1) // 7 for i in range(1, 7)]
    else:
        al = [a0, a1] + [((5 - i) * a0 + i * a1) // 5 for i in range(1, 5)] + [0, 255]
    ab = int.from_bytes(b[2:8], "little")
    c0, c1 = struct.unpack_from("<HH", b, 8)
    p0, p1 = _c565(c0), _c565(c1)
    cols = [p0, p1, tuple((2 * x + y) // 3 for x, y in zip(p0, p1)), tuple((x + 2 * y) // 3 for x, y in zip(p0, p1))]
    cb = struct.unpack_from("<I", b, 12)[0]
    return [cols[cb >> (2 * i) & 3] + (al[ab >> (3 * i) & 7],) for i in range(16)]


def _to565(c):
    return (c[0] * 31 + 127) // 255 << 11 | (c[1] * 63 + 127) // 255 << 5 | (c[2] * 31 + 127) // 255


def dxt5_encode(px):
    alphas = [p[3] for p in px]
    a0, a1 = max(alphas), min(alphas)
    if a0 == a1:
        ab = 0
    else:
        pal = [a0, a1] + [((7 - i) * a0 + i * a1) // 7 for i in range(1, 7)]
        ab = 0
        for i, a in enumerate(alphas):
            ab |= min(range(8), key=lambda k: abs(pal[k] - a)) << (3 * i)
    vis = [p for p in px if p[3] > 8] or px
    # endpoints: the two colours farthest apart along the main luminance spread
    lum = [p[0] * 2 + p[1] * 4 + p[2] for p in vis]
    hi, lo = vis[lum.index(max(lum))], vis[lum.index(min(lum))]
    c0, c1 = _to565(hi), _to565(lo)
    if c0 < c1:
        c0, c1 = c1, c0
    if c0 == c1:
        cb = 0
    else:
        q0, q1 = _c565(c0), _c565(c1)
        cols = [q0, q1, tuple((2 * x + y) // 3 for x, y in zip(q0, q1)), tuple((x + 2 * y) // 3 for x, y in zip(q0, q1))]
        cb = 0
        for i, p in enumerate(px):
            cb |= min(range(4), key=lambda k: sum((cols[k][j] - p[j]) ** 2 for j in range(3))) << (2 * i)
    return bytes([a0, a1]) + ab.to_bytes(6, "little") + struct.pack("<HHI", c0, c1, cb)


def dxt3_decode(b):
    px = dxt5_decode(bytes([255, 255]) + bytes(6) + bytes(b[8:16]))
    ab = int.from_bytes(b[:8], "little")
    return [p[:3] + ((ab >> (4 * i) & 15) * 17,) for i, p in enumerate(px)]


def dxt3_encode(px):
    ab = 0
    for i, p in enumerate(px):
        ab |= min(15, (p[3] + 8) // 17) << (4 * i)
    return ab.to_bytes(8, "little") + dxt5_encode(px)[8:]


def paint_label(tex, rect, bg, img):
    """Paint one label into a DXT5 or DXT3 DDS (bytearray, first mip level) in place."""
    dec, enc = (dxt3_decode, dxt3_encode) if tex[84:88] == b"DXT3" else (dxt5_decode, dxt5_encode)
    w, h = dds_dims(tex)
    bw = (w + 3) // 4
    x0, y0, x1, y1 = rect
    iw, ih, rgba = img
    if (iw, ih) != (x1 - x0, y1 - y0):
        return False
    blocks = {}

    def block(bx, by):
        k = (bx, by)
        if k not in blocks:
            o = 128 + (by * bw + bx) * 16
            blocks[k] = dec(tex[o:o + 16])
        return blocks[k]

    def pixel(x, y):
        return block(x // 4, y // 4)[(y % 4) * 4 + x % 4]

    fill = bg.startswith("fill")
    ref = x0 + (int(bg.split(":")[1]) if fill else 0)
    lo, hi = (ref + 1, x1 - (ref - x0) - 1) if fill else (x0, x1)
    base = {}
    for y in range(y0, y1):
        r = pixel(ref, y) if fill else (0, 0, 0, 0)
        for x in range(lo, hi):
            base[(x, y)] = r
    for (x, y), b0 in base.items():
        o = ((y - y0) * iw + (x - x0)) * 4
        sr, sg, sb, sa = rgba[o:o + 4]
        da = b0[3]
        oa = sa + da * (255 - sa) // 255
        if oa == 0:
            out = (0, 0, 0, 0)
        else:
            out = tuple((s * sa + d * da * (255 - sa) // 255) // oa for s, d in zip((sr, sg, sb), b0[:3])) + (oa,)
        blk = block(x // 4, y // 4)
        blk[(y % 4) * 4 + x % 4] = out
    for (bx, by), px in blocks.items():
        o = 128 + (by * bw + bx) * 16
        tex[o:o + 16] = enc(px)
    return True


def paint_capsule_labels(rel, fb, stats):
    rows = [r for r in capsule_rows()]
    if not rows:
        return
    imgs = capsule_images()
    if imgs is None or len(imgs) != len(rows):
        stats["capsule_labels_missing_asset"] = len(rows)
        return
    tex_cache = {}
    for row, img in zip(rows, imgs):
        if row["archive"] != rel:
            continue
        th, mapt = find_texture(fb, row["texture"])
        if th is None:
            stats["capsule_labels_skipped"] = stats.get("capsule_labels_skipped", 0) + 1
            continue
        if th not in tex_cache:
            tex_cache[th] = bytearray(fb.get(th))
        tex = tex_cache[th]
        rect = label_rect_px(row, tex, mapt) if is_dds(tex) and tex[84:88] in (b"DXT5", b"DXT3") else None
        if rect is None or not paint_label(tex, rect, row["bg"], img):
            stats["capsule_labels_skipped"] = stats.get("capsule_labels_skipped", 0) + 1
            continue
        stats["capsule_labels"] = stats.get("capsule_labels", 0) + 1
    for th, tex in tex_cache.items():
        fb.put(th, bytes(tex))


# Styles: fill top, fill bottom, outline (None = no outline), outline width in 1/100 of the height.
CAPSULE_STYLES = {
    "gold": ((255, 246, 150), (255, 150, 10), (100, 40, 0), 9),
    "orange": ((255, 214, 70), (245, 80, 20), (80, 20, 0), 9),
    "get": ((255, 214, 60), (255, 128, 0), (70, 25, 10), 8),
    "white": ((255, 255, 255), (255, 255, 255), (35, 35, 40), 9),
    "whiteblue": ((255, 255, 255), (235, 240, 255), (30, 70, 170), 10),
    "navy": ((30, 50, 140), (20, 35, 110), (255, 255, 255), 9),
    "purple": ((140, 50, 180), (100, 25, 140), (255, 255, 255), 9),
    "red": ((220, 30, 30), (190, 15, 15), (255, 255, 255), 10),
    "brown": ((110, 70, 60), (80, 45, 40), None, 0),
    "dark": ((70, 70, 80), (60, 60, 70), (255, 255, 255), 8),
    "box": ((255, 255, 255), (255, 255, 255), (30, 30, 50), 8),
    "stat_red": ((230, 40, 40), (200, 20, 20), (255, 255, 255), 10),
    "stat_gold": ((220, 160, 20), (190, 120, 0), (255, 255, 255), 10),
    "stat_green": ((40, 170, 40), (20, 130, 20), (255, 255, 255), 10),
    "stat_blue": ((30, 120, 220), (20, 90, 190), (255, 255, 255), 10),
    "stat_purple": ((150, 50, 200), (115, 30, 165), (255, 255, 255), 10),
    "strength": ((255, 150, 30), (235, 100, 0), (255, 255, 255), 10),
    "weakness": ((40, 100, 220), (20, 70, 190), (255, 255, 255), 10),
}


def render_label(text, w, h, style, font="C:/Windows/Fonts/ARLRDBD.TTF"):
    """Our own rendering of one English label (Pillow): RGBA bytes of w x h."""
    from PIL import Image, ImageDraw, ImageFont
    top, bot, outl, ow = CAPSULE_STYLES[style]
    scale = 0.80                               # text height / label height; "{s=0.5}" first sets it
    if text.startswith("{s="):
        scale, text = float(text[3:text.index("}")]), text[text.index("}") + 1:]
    lines = text.replace("\\n", "\n").split("\n")
    pad = max(1, h // 14)
    ow_px = max(1, round(h * scale / 0.8 / len(lines) * ow / 100)) if outl else 0
    size = int(h / len(lines) * scale)
    while True:
        f = ImageFont.truetype(font, size)
        boxes = [f.getbbox(t) for t in lines]
        tw = max(b[2] - b[0] for b in boxes) + 2 * ow_px
        lh = max(b[3] - b[1] for b in [f.getbbox("Ag")]) + 2 * ow_px
        if lh * len(lines) <= h - 2 * pad or size <= 6:
            break
        size -= 1
    th = lh * len(lines)
    big = Image.new("L", (tw + 4, th + 4), 0)
    d = ImageDraw.Draw(big)
    y = 2
    for t, b in zip(lines, boxes):
        d.text(((tw + 4 - (b[2] - b[0])) // 2 - b[0], y + ow_px - f.getbbox("Ag")[1]), t, font=f, fill=255)
        y += lh
    mask = big
    from PIL import ImageFilter
    edge = mask.filter(ImageFilter.MaxFilter(2 * ow_px + 1)) if ow_px else None
    grad = Image.new("RGBA", mask.size)
    for yy in range(mask.size[1]):
        k = yy / max(1, mask.size[1] - 1)
        c = tuple(int(a + (b - a) * k) for a, b in zip(top, bot)) + (255,)
        grad.paste(c, (0, yy, mask.size[0], yy + 1))
    lab = Image.new("RGBA", mask.size, (0, 0, 0, 0))
    if edge is not None:
        lab.paste(outl + (255,), (0, 0), edge)
    lab.paste(grad, (0, 0), mask)
    maxw = w - 2 * pad
    if lab.size[0] > maxw:                     # condense to fit
        lab = lab.resize((maxw, lab.size[1]), Image.LANCZOS)
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    out.alpha_composite(lab, ((w - lab.size[0]) // 2, (h - lab.size[1]) // 2))
    return out.tobytes()


def make_capsule_asset():
    rows = capsule_rows()
    files = jp_update_files()
    blobs = bytearray()
    for row in rows:
        src = files[row["archive"]]
        jp = fb_load(src)
        us, asia = english_sources(row["archive"])
        if us or asia:
            merge_layout(jp, fb_load(us or asia), "data/" + row["archive"].split("/", 1)[1].rsplit("/", 1)[0] + "/")
        th, mapt = find_texture(jp, row["texture"])
        if th is None:
            raise SystemExit("capsule label: no texture %s in %s" % (row["texture"], row["archive"]))
        rect = label_rect_px(row, jp.get(th), mapt)
        if rect is None:
            raise SystemExit("capsule label: chip %s rect differs" % row["chip"])
        w, h = rect[2] - rect[0], rect[3] - rect[1]
        if row["bg"].startswith("fill"):
            n = int(row["bg"].split(":")[1])
            img = render_label(row["english"], w - 2 * (n + 1), h, row["style"])
            from PIL import Image
            full = Image.new("RGBA", (w, h), (0, 0, 0, 0))
            full.paste(Image.frombytes("RGBA", (w - 2 * (n + 1), h), img), (n + 1, 0))
            img = full.tobytes()
        else:
            img = render_label(row["english"], w, h, row["style"])
        blobs += struct.pack("<HH", w, h) + img
    _, asset = capsule_paths()
    asset.write_bytes(zlib.compress(bytes(blobs), 9))
    return asset


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
            if rel == INFO_REL:
                tot["rare_labels"] = paint_rare_labels(jp)
            paint_capsule_labels(rel, jp, tot)
            if report is not None:
                report.extend((rel,) + k for k in kept)
        tot["archives"] += 1
        write_out(jp.bytes(), [out / "game/USRDIR" / rel, out / "hdd0/game/BCJS30089/USRDIR" / rel], dry)
    tot.update({"msg_" + k: v for k, v in msg_stats.items()})
    return tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["apply", "needs", "report", "labels"])
    ap.add_argument("file", nargs="?")
    ap.add_argument("--out", default="A:/hsg-ultimate")
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    out = Path(a.out)
    if a.cmd == "labels":
        print("[english] wrote", make_label_asset())
        print("[english] wrote", make_capsule_asset())
        return 0
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
