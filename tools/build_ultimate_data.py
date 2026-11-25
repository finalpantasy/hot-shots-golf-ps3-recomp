#!/usr/bin/env python3
"""Assemble the game data for the JP 1.27 build (Minna no Golf 6, BCJS30089).

usage: build_ultimate_data.py [--base us|asia] [--out A:/hsg-ultimate] [--lang en|ja] [--dry]
           [--base-dir <game folder with USRDIR and PARAM.SFO>]   (default work/game/base-1.00 for us)
           [--updates <folder holding the extracted JP updates 01.01 .. 01.27>]
                                                                  (default A:/hsg-updates/x/BCJS30089)
           [--us-updates <folder holding extracted US updates 01.01 .. 01.03>]   (English source, optional)
           [--asia-dir <Asia PS3_GAME folder>] [--asia-updates <folder>]         (English source, optional)
           [--translations <message_text.tsv>]
Missing inputs end the run with "[error] ..." and exit code 2 before anything is written.

Writes (nothing goes into git; every path is outside the repo):
  <out>/game/                      the "disc" (/dev_bdvd, --game-dir):
      PARAM.SFO                    the base's PARAM.SFO with TITLE_ID BCJS30089, CATEGORY DG
                                   (disc game), APP_VER 01.27, TITLE Minna no Golf 6
      USRDIR/...                   base data with the region renames below, then the JP
                                   updates 01.01 .. 01.27 copied over it in order
  <out>/hdd0/game/BCJS30089/       the installed JP update, as on a console (/dev_hdd0):
      PARAM.SFO                    from 01.27
      USRDIR/...                   updates 01.01 .. 01.27 layered in order (no EBOOT.BIN)

Region renames applied to the base (the JP program asks for JP names):
  us:   xbdata/chara_localize/  -> xbdata/chara/
        xbdata/course_localize/ -> xbdata/course/
        *.US_01.xb              -> *.JP_00.xb   (English text and menus under the JP name)
        movie_US/, contents_US/ -> movie/, contents/
  asia: xbdata/chara_asia/      -> xbdata/chara/
        xbdata/course_localize/ -> xbdata/course/
        *.AS_01.xb              -> *.JP_00.xb
        movie_AS/, contents_AS/ -> movie/, contents/
Other localized variants (US_02/03/07, EU_*, AS_09/10) are left out. A JP update file always
wins over a renamed base file. Archive entry keys inside the renamed base archives still hash
the base's internal paths (data/chara_localize/..., data/course_localize/...); the JP build
retries those names at run time (port/hsg_jp127_hooks.cpp), so the archives are not rewritten.

--lang en (default) then rebuilds the JP updates' localized archives with English text and
textures (tools/jp127_english.py); --lang ja leaves the Japanese update files as they are.

Files on the same volume as <out> are hard-linked, others copied. Existing files with the same
size and mtime are kept, so a second run only adds what changed.
"""
import argparse, os, re, shutil, struct, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))   # jp127_english sits beside this file

ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False)     else Path(__file__).resolve().parent.parent
UPD = Path("A:/hsg-updates/x/BCJS30089")
BASES = {
    "us": dict(usrdir=ROOT / "work/game/base-1.00/USRDIR", sfo=ROOT / "work/game/base-1.00/PARAM.SFO",
               dirs={"chara_localize": "chara", "course_localize": "course"}, loc="US_01",
               top={"movie_US": "movie", "contents_US": "contents"}, skip_top={"game"}),
    "asia": dict(usrdir=Path("A:/Everybody's Golf 6 (Asia) (En,Zh,Ko)/PS3_GAME/USRDIR"),
                 sfo=Path("A:/Everybody's Golf 6 (Asia) (En,Zh,Ko)/PS3_GAME/PARAM.SFO"),
                 dirs={"chara_asia": "chara", "course_localize": "course"}, loc="AS_01",
                 top={"movie_AS": "movie", "contents_AS": "contents"}, skip_top=set()),
}
LOC_RE = re.compile(r"\.(JP_00|US_0\d|EU_0\d|AS_\d\d)\.xb$", re.I)


# ---- PARAM.SFO --------------------------------------------------------------
def sfo_read(path):
    d = Path(path).read_bytes()
    magic, ver, kt, dt, n = struct.unpack_from("<4sIIII", d, 0)
    if magic != b"\0PSF":
        raise ValueError(f"{path}: not a PARAM.SFO")
    out = []
    for i in range(n):
        ko, fmt, ln, mx, do = struct.unpack_from("<HHIII", d, 20 + 16 * i)
        key = d[kt + ko:d.index(b"\0", kt + ko)].decode()
        out.append([key, fmt, d[dt + do:dt + do + ln], mx])
    return ver, out


def sfo_write(path, ver, entries):
    entries = sorted(entries, key=lambda e: e[0])
    keys, idx, data = b"", b"", b""
    for key, fmt, val, mx in entries:
        mx = max(mx, len(val))
        mx = (mx + 3) & ~3
        idx += struct.pack("<HHIII", len(keys), fmt, len(val), mx, len(data))
        keys += key.encode() + b"\0"
        data += val + b"\0" * (mx - len(val))
    kt = 20 + len(idx)
    keys += b"\0" * ((-len(keys)) % 4)
    dt = kt + len(keys)
    Path(path).write_bytes(struct.pack("<4sIIII", b"\0PSF", ver, kt, dt, len(entries)) + idx + keys + data)


def sfo_set(entries, key, value):
    val = value.encode("utf-8") + b"\0" if isinstance(value, str) else struct.pack("<I", value)
    fmt = 0x0204 if isinstance(value, str) else 0x0404
    for e in entries:
        if e[0] == key:
            e[1], e[2] = fmt, val
            return
    entries.append([key, fmt, val, len(val)])


# ---- file placement ---------------------------------------------------------
class Placer:
    def __init__(self, dry, total=0):
        self.dry, self.linked, self.copied, self.kept = dry, 0, 0, 0
        self.total, self.n = total, 0

    def put(self, src, dst):
        self.n += 1
        if self.total and self.n % 2000 == 0:
            print(f"[data] progress {self.n}/{self.total} files", flush=True)
        st = src.stat()
        if dst.exists():
            dt = dst.stat()
            if dt.st_size == st.st_size and int(dt.st_mtime) == int(st.st_mtime):
                self.kept += 1
                return
            if not self.dry:
                dst.unlink()
        if self.dry:
            self.copied += 1
            return
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.drive.upper() == dst.drive.upper():
            try:
                os.link(src, dst)
                self.linked += 1
                return
            except OSError:
                pass
        shutil.copy2(src, dst)
        self.copied += 1


def base_target(rel, cfg):
    """Base-relative path -> JP-named path, or None to leave the file out."""
    parts = rel.split("/")
    if parts[0] in cfg["skip_top"]:
        return None
    parts[0] = cfg["top"].get(parts[0], parts[0])
    if len(parts) > 1 and parts[0] == "xbdata" and parts[1] in cfg["dirs"]:
        parts[1] = cfg["dirs"][parts[1]]
    name = parts[-1]
    m = LOC_RE.search(name)
    if m:
        if m.group(1).upper() != cfg["loc"]:
            return None
        parts[-1] = name[:m.start()] + ".JP_00.xb"
    return "/".join(parts)


def update_files():
    """rel path -> source file, updates 01.01 .. 01.27 layered in order (EBOOT.BIN excluded)."""
    vers = sorted(p.name for p in UPD.iterdir() if re.fullmatch(r"01\.\d\d", p.name))
    files = {}
    for v in vers:
        u = UPD / v / "USRDIR"
        for dp, _, fs in os.walk(u):
            for f in fs:
                rel = Path(dp, f).relative_to(u).as_posix()
                if rel.upper() == "EBOOT.BIN":
                    continue
                files[rel] = Path(dp, f)
    return vers, files


def check_inputs(a, cfg):
    """Return a list of plain-English problems with the inputs (empty = good)."""
    bad = []
    if not (cfg["usrdir"].is_dir() and cfg["sfo"].is_file()):
        bad.append(f"Base game folder is missing or incomplete: need USRDIR/ and PARAM.SFO in "
                   f"{cfg['sfo'].parent}")
    vers = []
    if UPD.is_dir():
        vers = sorted(p.name for p in UPD.iterdir() if re.fullmatch(r"01\.\d\d", p.name) and (p / "USRDIR").is_dir())
    if not vers:
        bad.append(f"JP update folder has no extracted updates: {UPD} must hold folders 01.01 .. 01.27, "
                   f"each with a USRDIR folder (extract the JP update PKGs first)")
    elif vers[-1] != "01.27" or len(vers) != 27:
        bad.append(f"JP updates in {UPD} are incomplete: found {len(vers)} (01.01 .. {vers[-1]}), need all 27 up to 01.27")
    elif not (UPD / "01.27" / "PARAM.SFO").is_file():
        bad.append(f"{UPD / '01.27' / 'PARAM.SFO'} is missing")
    if a.lang == "en" and not Path(a.translations).is_file():
        bad.append(f"Translation table not found: {a.translations}")
    return bad


def main():
    global UPD
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", choices=sorted(BASES), default="us")
    ap.add_argument("--out", default="A:/hsg-ultimate")
    ap.add_argument("--lang", choices=["en", "ja"], default="en")
    ap.add_argument("--dry", action="store_true")
    ap.add_argument("--base-dir", help="base game folder (holds USRDIR and PARAM.SFO); default per --base")
    ap.add_argument("--updates", help="extracted JP updates (01.01 .. 01.27); default " + str(UPD))
    ap.add_argument("--us-updates", help="extracted US updates NPUA80864 (01.01 .. 01.03); English source")
    ap.add_argument("--asia-dir", help="Asia PS3_GAME folder; English source")
    ap.add_argument("--asia-updates", help="extracted Asia updates BCAS20276; English source")
    ap.add_argument("--translations", default=None, help="message_text.tsv (default: the bundled one)")
    a = ap.parse_args()
    cfg, out = dict(BASES[a.base]), Path(a.out)
    if a.base_dir:
        b = Path(a.base_dir)
        cfg["usrdir"], cfg["sfo"] = b / "USRDIR", b / "PARAM.SFO"
    if a.updates:
        UPD = Path(a.updates)
    import jp127_english
    jp127_english.configure(jp_updates=UPD, base_usrdir=cfg["usrdir"] if a.base == "us" else None,
                            us_updates=a.us_updates, asia_dir=a.asia_dir, asia_updates=a.asia_updates,
                            translations=a.translations)
    if a.translations is None:
        a.translations = str(jp127_english.TRANS)
    bad = check_inputs(a, cfg)
    if bad:
        for b in bad:
            print("[error] " + b, flush=True)
        return 2
    if out.drive and not Path(out.drive + "/").exists():
        print(f"[error] Output drive {out.drive} does not exist", flush=True)
        return 2
    game, hdd = out / "game", out / "hdd0/game/BCJS30089"

    vers, upd = update_files()
    print(f"[data] JP updates {vers[0]}..{vers[-1]}: {len(upd)} files after layering", flush=True)

    base = {}
    for dp, _, fs in os.walk(cfg["usrdir"]):
        for f in fs:
            rel = Path(dp, f).relative_to(cfg["usrdir"]).as_posix()
            if rel.upper() == "EBOOT.BIN":
                continue
            t = base_target(rel, cfg)
            if t is not None:
                base[t] = Path(dp, f)
    print(f"[data] {a.base} base {cfg['usrdir']}: {len(base)} files after renames")

    merged = dict(base)
    merged.update(upd)
    pl = Placer(a.dry, len(merged) + len(upd))
    # A stale file from an earlier run with another base must not survive.
    want = {(game / "USRDIR" / r).as_posix().lower() for r in merged}
    want_hdd = {(hdd / "USRDIR" / r).as_posix().lower() for r in upd}
    stale = 0
    for top, keep in ((game / "USRDIR", want), (hdd / "USRDIR", want_hdd)):
        if top.exists():
            for dp, _, fs in os.walk(top):
                for f in fs:
                    p = Path(dp, f)
                    if p.as_posix().lower() not in keep:
                        stale += 1
                        if not a.dry:
                            p.unlink()
    for rel, src in merged.items():
        pl.put(src, game / "USRDIR" / rel)
    for rel, src in upd.items():
        pl.put(src, hdd / "USRDIR" / rel)

    ver, ent = sfo_read(cfg["sfo"])
    sfo_set(ent, "TITLE_ID", "BCJS30089")
    sfo_set(ent, "CATEGORY", "DG")
    sfo_set(ent, "APP_VER", "01.27")
    sfo_set(ent, "TITLE", "Minna no Golf 6 (JP 1.27, %s base data)" % a.base.upper())
    ent = [e for e in ent if not e[0].startswith("TITLE_") or e[0] == "TITLE_ID"]
    if not a.dry:
        game.mkdir(parents=True, exist_ok=True)
        sfo_write(game / "PARAM.SFO", ver, ent)
        hdd.mkdir(parents=True, exist_ok=True)
        shutil.copy2(UPD / vers[-1] / "PARAM.SFO", hdd / "PARAM.SFO")
        (out / "game" / "BASE.txt").write_text(
            f"base={a.base}\nusrdir={cfg['usrdir']}\nupdates={vers[0]}..{vers[-1]}\n", encoding="utf-8")
    print(f"[data] {'would place' if a.dry else 'placed'}: {pl.linked} linked, {pl.copied} copied, "
          f"{pl.kept} unchanged, {stale} stale removed -> {game} and {hdd}")
    marker = out / "game" / jp127_english.LANG_MARKER
    if a.lang != "en" and not a.dry and marker.exists():
        marker.unlink()     # the port then keeps the Japanese ordinal suffix
    if a.lang == "en":
        print("[data] building English archives ...", flush=True)
        print("[data] english:", jp127_english.build(out, a.dry), flush=True)
    print("[data] done" + (" (dry run, nothing written)" if a.dry else ""), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
