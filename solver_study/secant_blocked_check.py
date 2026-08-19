#!/usr/bin/env python3
"""Frontier-corner secant blocking of the archived warm-start dead-ends
(paper Section 8, claim 1).

For a partial P of 2(N-1) points embedded in [N]^2 with rows 0..N-2 and
columns 0..N-2 full, the maximality criterion says: P is maximal in
[N]^2 iff the frontier corner (N-1, N-1) lies on a 2-point line of P
(the corner is secant-blocked).  This script re-checks that criterion
directly on every archived seed:

  * six N = 71 dead-ends:  n71_deadend_{b,c,d2,d4,d5,d6}.json
    (140 points each; paper reports 3-8 blocking secants),
  * the N = 73 seed:       solutions_n72_rot4.json  (144 points),
  * the N = 75 seed:       solutions_n74_rot4.json  (148 points).

A "secant" is a distinct line through the corner carrying >= 2 points of
P (same normalized direction from the corner).  All archived N = 71
dead-ends have exactly 8, 3, 4, 5, 6, 6 secants (checked at archive
time), and the N = 73 / 75 seeds have 5 / 6.  Every dead-end passes the
criterion (>= 1 secant), so each is inclusion-maximal in its board.

Usage: python secant_blocked_check.py [--n71 n71_deadend_b.json ...]
Runs on all six archived N = 71 files plus the N = 73, 75 seeds by
default; exit code 0 iff every check passes.
"""

import argparse
import json
import os
import sys
from math import gcd

HERE = os.path.dirname(os.path.abspath(__file__))

N71_FILES = ["n71_deadend_b.json", "n71_deadend_c.json", "n71_deadend_d2.json",
             "n71_deadend_d4.json", "n71_deadend_d5.json", "n71_deadend_d6.json"]


def secants_through_corner(points, N):
    """Number of distinct lines through the frontier corner (N-1, N-1)
    carrying >= 2 points of `points`."""
    corner = (N - 1, N - 1)
    rays = {}
    for (r, c) in points:
        dr, dc = r - corner[0], c - corner[1]
        if dr == 0 and dc == 0:
            continue
        g = gcd(abs(dr), abs(dc))
        rays[(dr // g, dc // g)] = rays.get((dr // g, dc // g), 0) + 1
    return [v for v in rays.values() if v >= 2]


def check_file(path, N, expect_pts, what):
    d = json.load(open(path, encoding="utf-8"))
    # dead-end files carry {"points": ...}; corpus solution files carry
    # {"configs": [{"n": ..., "points": ...}]}
    if "points" in d:
        pts = [tuple(p) for p in d["points"]]
    else:
        cfg = d["configs"][0]
        pts = [tuple(p) for p in cfg["points"]]
    if len(pts) != expect_pts:
        print(f"FAIL {os.path.basename(path)}: {len(pts)} points, "
              f"expected {expect_pts}")
        return 1
    if not all(0 <= r < N and 0 <= c < N for r, c in pts):
        print(f"FAIL {os.path.basename(path)}: points outside [N]^2")
        return 1
    rays = secants_through_corner(pts, N)
    nsec = len(rays)
    ok = nsec >= 1 and all(v == 2 for v in rays)
    print(f"  {what} ({os.path.basename(path)}): {len(pts)} pts, "
          f"{nsec} secants thru corner {rays} -> "
          f"{'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--n71", nargs="+", default=[os.path.join(HERE, f)
                                                 for f in N71_FILES])
    args = ap.parse_args()
    fails = 0
    print("N = 71 dead-ends (140 pts, frontier corner (70, 70)):")
    for path in args.n71:
        fails += check_file(path, 71, 140, "N=71 dead-end")
    print("N = 73 seed (144 pts from solutions_n72_rot4.json):")
    fails += check_file(os.path.join(HERE, "solutions_n72_rot4.json"),
                        73, 144, "N=73 seed")
    print("N = 75 seed (148 pts from solutions_n74_rot4.json):")
    fails += check_file(os.path.join(HERE, "solutions_n74_rot4.json"),
                        75, 148, "N=75 seed")
    print("ALL PASS" if fails == 0 else f"{fails} FAILURES")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
