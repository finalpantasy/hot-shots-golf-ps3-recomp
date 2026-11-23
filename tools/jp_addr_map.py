#!/usr/bin/env python3
"""Map US 1.03 game addresses to the JP 1.27 program by matching the code around them.

usage: jp_addr_map.py ADDR [ADDR ...]            (hex code addresses in the US 1.03 EBOOT)
       jp_addr_map.py --json OUT ADDR [ADDR ...]

For each address, the US function containing it (analysis/official-1.03/EBOOT.functions.json)
is turned into a masked instruction pattern: relative branch displacements, TOC (r2)
displacements and lis/addis immediates (absolute data addresses, which move between the two
builds) are masked, along with the displacement of a D-form access whose base came from a lis
in the previous 8 instructions. The JP functions (A:/hsg-ultimate/analysis/jp127.functions.json)
of the same length are searched for the same pattern. A unique match gives the JP address at
the same offset; several matches are narrowed by the neighbouring functions. The instruction
word itself is reported for both builds so a patch's "orig" word can be checked.
"""
import json, struct, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
US_ELF = ROOT / "work/extracted/update-1.03/USRDIR/EBOOT.elf"
US_FN = ROOT / "analysis/official-1.03/EBOOT.functions.json"
JP_ELF = Path("A:/hsg-ultimate/eboot/jp127.elf")
JP_FN = Path("A:/hsg-ultimate/analysis/jp127.functions.json")
TEXT_VADDR = 0x10000   # both builds: first PT_LOAD, file offset 0


def load(elf, fn):
    data = elf.read_bytes()
    funcs = [(int(f["start"], 16), int(f["end"], 16)) for f in json.loads(fn.read_text())]
    funcs.sort()
    return data, funcs


def word(data, a):
    return struct.unpack_from(">I", data, a - TEXT_VADDR)[0]


def masked(data, start, end):
    out, lis = [], {}
    for i, a in enumerate(range(start, end, 4)):
        w = word(data, a)
        op, rt, ra = w >> 26, (w >> 21) & 31, (w >> 16) & 31
        m = w
        if op == 18:
            m = w & 0xFC000003
        elif op == 16:
            m = w & 0xFFFF0003
        elif op == 15:                       # lis / addis: absolute address high half
            m = w & 0xFFFF0000
            lis[rt] = i
        elif op in (14, 24, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47,
                    48, 49, 50, 51, 52, 53, 54, 55, 58, 62):
            if ra == 2 or (ra in lis and i - lis[ra] <= 8):
                m = w & 0xFFFF0000
        out.append(m)
    return tuple(out)


class Matcher:
    def __init__(self):
        self.us, self.usf = load(US_ELF, US_FN)
        self.jp, self.jpf = load(JP_ELF, JP_FN)
        self.jp_by_len = {}
        for idx, (s, e) in enumerate(self.jpf):
            self.jp_by_len.setdefault(e - s, []).append(idx)
        self.cache = {}

    def us_func(self, a):
        lo, hi = 0, len(self.usf)
        while lo < hi:
            mid = (lo + hi) // 2
            if self.usf[mid][0] <= a: lo = mid + 1
            else: hi = mid
        i = lo - 1
        if i >= 0 and self.usf[i][0] <= a < self.usf[i][1]:
            return i
        return None

    def jp_pat(self, idx):
        if idx not in self.cache:
            s, e = self.jpf[idx]
            self.cache[idx] = masked(self.jp, s, e)
        return self.cache[idx]

    def candidates(self, ui):
        s, e = self.usf[ui]
        pat = masked(self.us, s, e)
        return [j for j in self.jp_by_len.get(e - s, []) if self.jp_pat(j) == pat]

    def map(self, a):
        ui = self.us_func(a)
        if ui is None:
            return {"us": hex(a), "status": "not in a US function"}
        cands = self.candidates(ui)
        how = "function match"
        if len(cands) > 1:   # neighbours decide: previous and next function must match too
            keep = []
            for j in cands:
                ok = 0
                for d in (-1, 1):
                    if 0 <= ui + d < len(self.usf) and 0 <= j + d < len(self.jpf):
                        us_n, jp_n = self.usf[ui + d], self.jpf[j + d]
                        if us_n[1] - us_n[0] == jp_n[1] - jp_n[0] and \
                           masked(self.us, *us_n) == self.jp_pat(j + d):
                            ok += 1
                if ok: keep.append(j)
            cands, how = keep, "function + neighbour match"
        s, e = self.usf[ui]
        if len(cands) != 1:
            w = self.window(a, s, e)
            if w: return w
        r = {"us": "0x%08X" % a, "us_func": "0x%08X" % s, "us_len": e - s,
             "us_word": "0x%08X" % word(self.us, a)}
        if len(cands) != 1:
            r.update(status="ambiguous" if cands else "no match",
                     jp_candidates=["0x%08X" % (self.jpf[j][0] + a - s) for j in cands[:8]])
            return r
        js = self.jpf[cands[0]][0]
        ja = js + (a - s)
        r.update(status=how, jp="0x%08X" % ja, jp_func="0x%08X" % js, delta="%+#x" % (ja - a),
                 jp_word="0x%08X" % word(self.jp, ja),
                 word_same=word(self.jp, ja) == word(self.us, a))
        return r


def _window(self, a, s, e):
    """Fallback for a function whose length changed: match the masked instructions around
    the address (same function only), growing the window until one JP place matches."""
    if not hasattr(self, "jp_all"):
        n = (len(self.jp) // 4) * 4
        end = TEXT_VADDR + min(n, max(f[1] for f in self.jpf) - TEXT_VADDR)
        self.jp_all = masked(self.jp, TEXT_VADDR, end)
        self.jp_blob = b"".join(struct.pack(">I", x) for x in self.jp_all)
    us_m = masked(self.us, s, e)
    i = (a - s) // 4
    for k in (6, 10, 16, 24, 40, 64):
        lo, hi = max(0, i - k), min(len(us_m), i + k + 1)
        needle = b"".join(struct.pack(">I", x) for x in us_m[lo:hi])
        hits, pos = [], self.jp_blob.find(needle)
        while pos >= 0 and len(hits) < 4:
            if pos % 4 == 0: hits.append(pos)
            pos = self.jp_blob.find(needle, pos + 1)
        if len(hits) == 1:
            ja = TEXT_VADDR + hits[0] + (i - lo) * 4
            return {"us": "0x%08X" % a, "us_func": "0x%08X" % s, "us_len": e - s,
                    "us_word": "0x%08X" % word(self.us, a), "status": "window match (+-%d insns)" % k,
                    "jp": "0x%08X" % ja, "delta": "%+#x" % (ja - a), "jp_word": "0x%08X" % word(self.jp, ja),
                    "word_same": word(self.jp, ja) == word(self.us, a)}
        if not hits and k > 6:
            break
    return None


Matcher.window = _window


def main():
    args = sys.argv[1:]
    out = None
    if args[:1] == ["--json"]:
        out, args = args[1], args[2:]
    m = Matcher()
    res = [m.map(int(x, 16)) for x in args]
    for r in res:
        print(json.dumps(r))
    if out:
        Path(out).write_text(json.dumps(res, indent=1) + "\n")


if __name__ == "__main__":
    main()
