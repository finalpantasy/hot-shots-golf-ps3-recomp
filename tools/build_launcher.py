#!/usr/bin/env python3
"""Freeze tools/hsg_launcher.py into one windowed exe with PyInstaller.

usage: .venv/Scripts/python.exe tools/build_launcher.py [--out dist] [--clean]

Needs PyInstaller in the Python you run this with (python -m pip install pyinstaller).
Result: <out>/HotShotsGolfLauncher.exe (default dist/, which git ignores).

Bundled inside the exe:
  tools/build_ultimate_data.py and tools/jp127_english.py   Ultimate setup (--ultimate-setup)
  translations/jp127/message_text.tsv                       English table for the JP strings
  external/ps3recomp/tools/pkg_extract.py (when present)    PKG extractor (--pkg-extract)
The exe holds no game data, keys or textures. The build files go to work/launcher-build.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TOOLS = ROOT / "tools"
VERSION = "0.2.0"

VERSION_FILE = """VSVersionInfo(
  ffi=FixedFileInfo(filevers=({a}, {b}, {c}, 0), prodvers=({a}, {b}, {c}, 0), mask=0x3f, flags=0x0,
    OS=0x40004, fileType=0x1, subtype=0x0, date=(0, 0)),
  kids=[StringFileInfo([StringTable('040904B0', [
    StringStruct('CompanyName', 'finalpantasy'),
    StringStruct('FileDescription', 'Hot Shots Golf PC recompilation launcher'),
    StringStruct('FileVersion', '{v}'),
    StringStruct('InternalName', 'HotShotsGolfLauncher'),
    StringStruct('OriginalFilename', 'HotShotsGolfLauncher.exe'),
    StringStruct('ProductName', 'Hot Shots Golf PC recompilation launcher'),
    StringStruct('ProductVersion', '{v}')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])])
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "dist"))
    ap.add_argument("--clean", action="store_true", help="drop PyInstaller's cache first")
    a = ap.parse_args()
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller is not installed: python -m pip install pyinstaller", file=sys.stderr)
        return 2
    work = ROOT / "work" / "launcher-build"
    work.mkdir(parents=True, exist_ok=True)
    a1, b1, c1 = (int(x) for x in VERSION.split("."))
    vf = work / "version.txt"
    vf.write_text(VERSION_FILE.format(a=a1, b=b1, c=c1, v=VERSION), encoding="utf-8")
    sep = os.pathsep
    cmd = [sys.executable, "-m", "PyInstaller", "--noconfirm", "--onefile", "--windowed",
           "--name", "HotShotsGolfLauncher", "--distpath", a.out,
           "--workpath", str(work / "build"), "--specpath", str(work),
           "--paths", str(TOOLS), "--version-file", str(vf),
           "--hidden-import", "build_ultimate_data", "--hidden-import", "jp127_english",
           "--hidden-import", "Crypto.Cipher.AES",
           "--add-data", "%s%s%s" % (ROOT / "translations" / "jp127" / "message_text.tsv", sep,
                                     "translations/jp127"),
           "--exclude-module", "numpy", "--exclude-module", "PIL", "--exclude-module", "matplotlib",
           "--exclude-module", "pydoc_data", "--exclude-module", "pydoc", "--exclude-module", "xml"]
    pkg = ROOT / "external" / "ps3recomp" / "tools" / "pkg_extract.py"
    if pkg.is_file():
        cmd += ["--add-data", "%s%s." % (pkg, sep)]
    else:
        print("note: pkg_extract.py not found; the PKG extract button will be unavailable")
    if a.clean:
        cmd.append("--clean")
    cmd.append(str(TOOLS / "hsg_launcher.py"))
    print(" ".join(cmd))
    rc = subprocess.call(cmd, cwd=str(ROOT))
    exe = Path(a.out) / "HotShotsGolfLauncher.exe"
    if rc == 0 and exe.is_file():
        print("built %s (%.1f MB)" % (exe, exe.stat().st_size / 1e6))
    return rc


if __name__ == "__main__":
    sys.exit(main())
