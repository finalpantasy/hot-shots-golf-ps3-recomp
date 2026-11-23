#!/usr/bin/env python3
"""Split hooked functions out of the JP 1.27 lift (run after ppu_lifter.py in pipeline-jp127.toml).

usage: jp_lift_hooks.py RECOMP_DIR

For each address in HOOKS, the lifted definition `void func_X(ppu_context* ctx) {` is renamed
to `func_X_lifted` (with a prototype ahead of it). Every lifted call, the function table and
indirect calls keep the name func_X, which port/hsg_jp127_hooks.cpp defines and which calls
func_X_lifted. Idempotent: an already renamed definition is left alone. Fails if a hook's
definition is not found exactly once, so a lift that moved the function cannot build silently.
"""
import re, sys
from pathlib import Path

HOOKS = {
    0x00788B64: "FB_FindEntryByPath (US 0x00779228): archive name fallback, data/chara|course -> *_localize",
}


def main():
    d = Path(sys.argv[1])
    srcs = sorted(d.glob("ppu_recomp_*.cpp"))
    for addr, why in HOOKS.items():
        name = "func_%08X" % addr
        pat = re.compile(r"^void %s\(ppu_context\* ctx\) \{$" % name, re.M)
        done = re.compile(r"^void %s_lifted\(ppu_context\* ctx\) \{$" % name, re.M)
        hits, already = [], []
        for p in srcs:
            s = p.read_text(encoding="utf-8", errors="surrogateescape")
            if pat.search(s): hits.append(p)
            if done.search(s): already.append(p)
        if already and not hits:
            print(f"[jp_lift_hooks] {name}: already split in {already[0].name}")
            continue
        if len(hits) != 1:
            sys.exit(f"[jp_lift_hooks] {name}: {len(hits)} definitions found, expected 1")
        p = hits[0]
        s = p.read_text(encoding="utf-8", errors="surrogateescape")
        s = pat.sub(f"/* {why}: split out by tools/jp_lift_hooks.py */\n"
                    f"void {name}_lifted(ppu_context* ctx);\n"
                    f"void {name}_lifted(ppu_context* ctx) {{", s, count=1)
        p.write_text(s, encoding="utf-8", errors="surrogateescape")
        print(f"[jp_lift_hooks] {name} -> {name}_lifted in {p.name} ({why})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
