"""Overlay Hot Shots Golf update data (1.01 then 1.02; 1.03 has none) onto an hdd0 USRDIR.
usage: overlay_updates.py <hdd0 USRDIR dir> [--src DIR]   (dry run with --dry)
Each source is an extracted update package dir (default work/verify-toro/x_A0101, x_A0102, made with
external/ps3recomp/tools/pkg_extract.py <UP9000-...-A010x-...pkg> <dir>). EBOOT.BIN is never copied.
Later sources overwrite earlier ones."""
import os, shutil, sys
root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
dest = sys.argv[1]
dry = "--dry" in sys.argv
srcs = [os.path.join(root, "work", "verify-toro", d) for d in ("x_A0101", "x_A0102")]
if "--src" in sys.argv:
    srcs = sys.argv[sys.argv.index("--src") + 1:]
n = 0
for s in srcs:
    u = os.path.join(s, "USRDIR")
    for dp, _, fs in os.walk(u):
        for f in fs:
            if dp == u and f.upper() == "EBOOT.BIN": continue
            rel = os.path.relpath(os.path.join(dp, f), u)
            t = os.path.join(dest, rel)
            if not dry:
                os.makedirs(os.path.dirname(t), exist_ok=True)
                shutil.copy2(os.path.join(dp, f), t)
            n += 1
print(("would copy" if dry else "copied"), n, "files ->", dest)
