#!/usr/bin/env python3
"""Grind capsule simulator for the JP 1.27 build (HSG_UNLOCKS=grind, port/hsg_jp127_unlocks.cpp).

usage: grind_sim.py [--runs N] [--seed S] [--blue B --purple P --red R] [--pity N]
       grind_sim.py --replay SEED [--tickets N]      exact draw sequence the game makes for
                                                     HSG_UNLOCKS_SEED=SEED (same RNG and call order)
       grind_sim.py --check-log FILE                 replay every "[hsg-unlocks] draw:" line of a
                                                     game log against the rule and compare the
                                                     colour counts with the odds
       grind_sim.py --tune                           sweep the red weight for a mean near --target

The rule is the one the C++ uses (it mirrors the game's capsule result code, 0x0044ABF4 block
0x0044B0A8-0x0044B1A0):
  - one capsule per ticket: a character picked uniformly among the 15 rares below 7 stars
    (the game's pick 0x004496F0 starts every candidate at weight 1.0 and multiplies in the
    modifier vectors of two server-fed lists, calc+0x40 and calc+0x50; offline those lists are
    empty, so the pick is uniform), then a colour by weight: blue 1-3 stars, purple 4-6, red 7,
    star uniform inside the colour;
    (the capsule machine's odds table shows exactly this model: the C++ feeds the same weights to
    the game's table, and our roll decides because the game's own roll rounds every chance to
    whole percents, rand % 100 against the cumulative table: star 1 ~25%, star 7 ~7%);
  - capsule star > level: level = star;
  - otherwise, level 1-6: gauge += T(star - 1); if gauge >= T(level): gauge -= T(level), level + 1
    (one step); gauge clamped 0-63 (the game's 6-bit field). The game works in star - 1 and
    level - 1 (0x0044B0A8-0x0044B1A0, level from 0x00444FF8 = saved level - 1), so a duplicate
    can also lift 6 stars to 7 (T(6) = 20 points);
  - level 7: no change;
  - T = 0x00444924: T(0..6) = 1, 2, 4, 8, 12, 16, 20.
  (Checked 11-24 against the game's own draw in the capsule machine; the M3 rule was one off.)
  - pity: after PITY draws without a red the next capsule is red (counter in the store);
    --pity 0 turns pity off.
No game data here: only the rule and its numbers.
"""
import argparse, random, re, statistics, sys

T = [1, 2, 4, 8, 12, 16, 20]
CHARS, MAX_STARS, GAUGE_MAX = 15, 7, 63
# Chosen odds (same numbers as kOddsBlue/kOddsPurple/kOddsRed in the C++).
BLUE, PURPLE, RED, PITY = 72, 20, 8, 25


def t(n):
    return T[n] if 0 <= n <= 6 else 0


def apply_capsule(level, gauge, star):
    """Returns the new (level, gauge) for one capsule of `star` on a character."""
    if star > level:
        return star, gauge
    if level <= 6:                       # the game works in star - 1 (0x0044B0A8)
        gauge = min(gauge + t(star - 1), GAUGE_MAX)
        need = t(level)
        if gauge >= need:
            return level + 1, gauge - need
    return level, gauge


class XorShift:
    """The C++ rng(): xorshift32 on an unsigned 32-bit state."""
    def __init__(self, seed):
        self.s = seed & 0xFFFFFFFF or 1

    def __call__(self):
        s = self.s
        s ^= (s << 13) & 0xFFFFFFFF
        s ^= s >> 17
        s ^= (s << 5) & 0xFFFFFFFF
        self.s = s
        return s


def draw(state, rnd, blue, purple, red, pity):
    """One capsule in the C++ call order. state: dict(levels, gauges, pity). Returns a record or None."""
    pool = [pc for pc in range(CHARS) if state["levels"][pc] < MAX_STARS]
    if not pool:
        return None
    pc = pool[rnd() % len(pool)]
    forced = pity > 0 and state["pity"] >= pity   # pity 0 = no pity
    if forced:
        colour, star = "red", 7
    else:
        roll = rnd() % (blue + purple + red)
        if roll < blue:
            colour, star = "blue", 1 + rnd() % 3
        elif roll < blue + purple:
            colour, star = "purple", 4 + rnd() % 3
        else:
            colour, star = "red", 7
    state["pity"] = 0 if colour == "red" else state["pity"] + 1
    lv0, g0 = state["levels"][pc], state["gauges"][pc]
    state["levels"][pc], state["gauges"][pc] = apply_capsule(lv0, g0, star)
    return dict(pc=pc, colour=colour, star=star, g0=g0, g1=state["gauges"][pc], l0=lv0,
                l1=state["levels"][pc], forced=forced)


def new_state():
    return dict(levels=[0] * CHARS, gauges=[0] * CHARS, pity=0)


def tickets_to_max(rnd, blue, purple, red, pity):
    st, n = new_state(), 0
    while draw(st, rnd, blue, purple, red, pity) is not None:
        n += 1
    return n


def pct(sorted_vals, p):
    return sorted_vals[min(len(sorted_vals) - 1, int(p / 100 * len(sorted_vals)))]


def run(runs, seed, blue, purple, red, pity):
    r = random.Random(seed)
    rnd = lambda: r.getrandbits(32)
    vals = sorted(tickets_to_max(rnd, blue, purple, red, pity) for _ in range(runs))
    return dict(mean=statistics.fmean(vals), p10=pct(vals, 10), p50=pct(vals, 50), p90=pct(vals, 90),
                min=vals[0], max=vals[-1])


def check_log(path, blue, purple, red, pity):
    pat = re.compile(r"\[hsg-unlocks\] draw: pc=(\d+) capsule=(\w+) star=(\d+) gauge (\d+)->(\d+) "
                     r"level (\d+)->(\d+)(?:.*?pity (\d+))?")
    n = bad = 0
    counts = {"blue": 0, "purple": 0, "red": 0}
    forced = 0
    stars = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            m = pat.search(line)
            if not m:
                continue
            pc, colour, star, g0, g1, l0, l1 = (m.group(1), m.group(2), *map(int, m.group(3, 4, 5, 6, 7)))
            n += 1
            if "pity" in line and "forced" in line:
                forced += 1
            else:
                counts[colour] += 1
            stars[star] = stars.get(star, 0) + 1
            want = apply_capsule(l0, g0, star)
            ok_colour = (colour == "blue" and 1 <= star <= 3) or (colour == "purple" and 4 <= star <= 6) \
                or (colour == "red" and star == 7)
            if want != (l1, g1) or not ok_colour:
                bad += 1
                if bad <= 10:
                    print("MISMATCH:", line.strip(), "expected level/gauge", want)
    tot = sum(counts.values())
    print("draw lines: %d, rule mismatches: %d, pity-forced reds: %d" % (n, bad, forced))
    w = blue + purple + red
    for c, wt in (("blue", blue), ("purple", purple), ("red", red)):
        exp = tot * wt / w
        print("  %-6s observed %4d  expected %7.1f (%.1f%%)" % (c, counts[c], exp, 100 * wt / w))
    chi = sum((counts[c] - tot * wt / w) ** 2 / (tot * wt / w) for c, wt in
              (("blue", blue), ("purple", purple), ("red", red)) if tot)
    print("  chi-square (2 dof) = %.2f  (5%% critical value 5.99)" % chi)
    print("  stars:", " ".join("%d:%d" % (k, stars[k]) for k in sorted(stars)))
    return bad


def replay(seed, tickets, blue, purple, red, pity):
    rnd = XorShift(seed)
    st = new_state()
    for i in range(tickets):
        d = draw(st, rnd, blue, purple, red, pity)
        if d is None:
            print("all %d at %d stars after %d draws; %d ticket(s) left" % (CHARS, MAX_STARS, i, tickets - i))
            return
        print("draw: pc=%d capsule=%s star=%d gauge %d->%d level %d->%d%s" % (
            d["pc"], d["colour"], d["star"], d["g0"], d["g1"], d["l0"], d["l1"], " (pity)" if d["forced"] else ""))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--runs", type=int, default=100000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--blue", type=int, default=BLUE)
    ap.add_argument("--purple", type=int, default=PURPLE)
    ap.add_argument("--red", type=int, default=RED)
    ap.add_argument("--pity", type=int, default=PITY)
    ap.add_argument("--tune", action="store_true")
    ap.add_argument("--target", type=float, default=140)
    ap.add_argument("--check-log")
    ap.add_argument("--replay", type=int)
    ap.add_argument("--tickets", type=int, default=200)
    a = ap.parse_args()
    if a.check_log:
        sys.exit(1 if check_log(a.check_log, a.blue, a.purple, a.red, a.pity) else 0)
    if a.replay is not None:
        replay(a.replay, a.tickets, a.blue, a.purple, a.red, a.pity)
        return
    if a.tune:
        for red in range(6, 15):
            r = run(max(2000, a.runs // 20), a.seed, 100 - red - a.purple, a.purple, red, a.pity)
            print("red %2d: mean %.1f p10 %d p50 %d p90 %d" % (red, r["mean"], r["p10"], r["p50"], r["p90"]))
        return
    r = run(a.runs, a.seed, a.blue, a.purple, a.red, a.pity)
    print("odds blue %d / purple %d / red %d, pity %d, %d runs (seed %d)" % (
        a.blue, a.purple, a.red, a.pity, a.runs, a.seed))
    print("tickets to max all %d rares at %d stars: mean %.1f  p10 %d  p50 %d  p90 %d  (min %d, max %d)" % (
        CHARS, MAX_STARS, r["mean"], r["p10"], r["p50"], r["p90"], r["min"], r["max"]))
    r0 = run(max(2000, a.runs // 10), a.seed, a.blue, a.purple, a.red, 10 ** 9)
    print("same odds without pity (%d runs): mean %.1f  p10 %d  p50 %d  p90 %d" % (
        max(2000, a.runs // 10), r0["mean"], r0["p10"], r0["p50"], r0["p90"]))


if __name__ == "__main__":
    main()
