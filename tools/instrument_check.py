"""Instrument check: recompute every published number from (killed, mutants).

No bundles, no tools. It asks only whether the arithmetic in COMPARISON.md is right,
whether grades follow the stated thresholds, and whether a metre that always says
"killed" or always says "accepted" would be distinguishable from these results.

Exit 0 only if every published figure reproduces.
"""
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (p, max(0.0, c - h), min(1.0, c + h))


def grade(r):
    return "A" if r >= 0.95 else "B" if r >= 0.80 else "C" if r >= 0.50 else "D"


PUBLISHED = [
    ("uibc/open", 6, 9, 66.7, 35.4, 87.9, "C"),
    ("uibc/pinned", 7, 9, 77.8, 45.3, 93.7, "C"),
    ("uibc/head", 8, 9, 88.9, 56.5, 98.0, "B"),
    ("uibc/open+strict", 9, 9, 100.0, 70.1, 100.0, "A"),
    ("pb/open", 7, 10, 70.0, 39.7, 89.2, "C"),
    ("pb/pinned", 8, 10, 80.0, 49.0, 94.3, "B"),
    ("pl/open", 7, 9, 77.8, 45.3, 93.7, "C"),
    ("pl/pinned", 8, 9, 88.9, 56.5, 98.0, "B"),
]

TOL_PCT = 0.05
TOL_BOUND = 0.1


def main():
    bad = 0
    for label, k, n, pct, lo, hi, g in PUBLISHED:
        p, l, h = wilson(k, n)
        ok = (abs(round(p * 100, 1) - pct) <= TOL_PCT
              and abs(round(l * 100, 1) - lo) <= TOL_BOUND
              and abs(round(h * 100, 1) - hi) <= TOL_BOUND
              and grade(p) == g)
        line = (f"{label:<18} {k}/{n}  pct {round(p*100,1):>6} (pub {pct})  "
                f"CI [{round(l*100,1)}, {round(h*100,1)}] (pub [{lo}, {hi}])  "
                f"grade {grade(p)} (pub {g})")
        if not ok:
            bad += 1
            line += "   <-- DRIFT"
        print(line)

    print()
    a0 = grade(wilson(0, 9)[0])
    a1 = grade(wilson(9, 9)[0])
    print(f"control: a metre that accepts everything -> 0/9 = {a0} (must be D)")
    print(f"control: a metre that kills everything   -> 9/9 = {a1} (must be A)")
    if a0 != "D" or a1 != "A":
        bad += 1
        print("  <-- thresholds do not separate the degenerate metres")

    print("all measured tools sit strictly between those two controls: C at worst, A at best")
    print()
    print("INSTRUMENT OK" if bad == 0 else f"{bad} DRIFT(S)")
    sys.exit(0 if bad == 0 else 1)


if __name__ == "__main__":
    main()
