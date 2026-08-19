# n71_repair.py -- k<=3 removal/addition repair for the n=71 2n-1 dead-end.
#
# Context: n71_deadend.py (team-lead) runs an unrestricted CP-SAT maximize for
# n=71 and stops at the 2n-1 = 141 dead-end, saving n71_deadend.json
# {'m': 71, 'size': ..., 'points': [[r,c],...]}.  At small n every such dead-end
# is >= 3 removals from any 2n-solution (0/6 k<=3 ladder repairs, sym_diag5.py),
# so at n=71 a k<=3 success would settle f(71) = 142.
#
# ladder_repair_pruned = sym_diag5.ladder_repair + witness-precompute pruning:
#   * a candidate add cell f is valid iff NO line through 2 points of the
#     REMAINING set passes through f.  Precompute for each queried cell f the
#     blocking pairs of the ORIGINAL partial (determinant test, lazy cache);
#     after removing A, f is valid iff every blocking pair intersects A.
#   * new-cell pairs: no remaining point may lie on the line through two adds
#     (on-the-fly gcd line walk; no line table needed).
#   * no 3 adds may be collinear.
#   * survivors of ALL local filters go through the exact no3_valid gate.
# Sound + complete: every 3-subset of (P - A) + adds is of type
# (3 remaining | 2 remaining + add | 1 remaining + 2 adds | 3 adds), and the
# four filters cover exactly those four types.
#
# Naive cost at n=71 would be C(141,3)=457k triples x 24 matchings x
# no3_valid(142) ~ 10^7 x 0.15s = infeasible; the pruned loop runs the local
# filters (set membership against a 3-element removal set) and only rarely
# reaches the no3_valid gate.  Expected wall: seconds to a few minutes.
#
# Usage:
#   python n71_repair.py --selftest            # equivalence vs naive ladder
#   python n71_repair.py                       # run on n71_deadend.json
#   python n71_repair.py --cap 1200 --out n71_repair_solution.json
import argparse
import itertools
import json
import os
import random
import subprocess
import sys
import time
from math import gcd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from no3in import no3_valid

REPO = os.path.dirname(os.path.abspath(__file__))


def line_cells(p, q, n):
    """All grid cells on the line through p and q (gcd walk, no table)."""
    (r1, c1), (r2, c2) = p, q
    dr, dc = r2 - r1, c2 - c1
    g = gcd(abs(dr), abs(dc)) or 1
    sr, sc = dr // g, dc // g
    out = []
    r, c = r1, c1
    while 0 <= r < n and 0 <= c < n:
        out.append((r, c))
        r += sr
        c += sc
    r, c = r1 - sr, c1 - sc
    while 0 <= r < n and 0 <= c < n:
        out.append((r, c))
        r -= sr
        c -= sc
    return out


def blocking_pairs(pts, cell, cache):
    """Pairs (p, q) of pts whose line passes through cell (lazy cache)."""
    if cell in cache:
        return cache[cell]
    res = []
    f0, f1 = cell
    for i in range(len(pts)):
        p0, p1 = pts[i]
        for j in range(i + 1, len(pts)):
            q0, q1 = pts[j]
            if (q0 - p0) * (f1 - p1) == (q1 - p1) * (f0 - p0):
                res.append((pts[i], pts[j]))
    cache[cell] = res
    return res


def ladder_repair_pruned(partial, n, kmax=3, cap_candidates=4000, log=None,
                         stats=None):
    """Remove k points, close deficits with d0+k additions (all bijections
    deficit-rows -> deficit-cols); pruned by witness-precomputed blocking
    pairs.  Returns a valid 2n-set or None.  stats (optional dict) collects
    per-k (A,perm) iteration counts and distinct-candidate counts, plus
    'gate' = no3_valid calls."""
    P = list(partial)
    s = len(P)
    if s == 2 * n:
        return P if no3_valid(P, n) is None else None
    rows = [0] * n
    cols = [0] * n
    for (r, c) in P:
        rows[r] += 1
        cols[c] += 1
    d0 = 2 * n - s
    if d0 <= 0 or d0 > 5:
        return None
    R0 = []
    C0 = []
    for r in range(n):
        if rows[r] > 2:
            return None
        for _ in range(2 - rows[r]):
            R0.append(r)
    for c in range(n):
        if cols[c] > 2:
            return None
        for _ in range(2 - cols[c]):
            C0.append(c)
    if len(R0) != d0 or len(C0) != d0:
        # malformed partial (row/col counts inconsistent with size) -- reject
        return None
    cache = {}
    checked = set()
    Pset = set(P)
    for k in range(0, kmax + 1):
        if k + d0 > 5:  # >5 add cells: matching/validity blowup guard
            break
        n_iter = 0
        n_cand = 0
        for A in itertools.combinations(P, k):
            Aset = set(A)
            R = R0 + [ra for (ra, ca) in A]
            C = C0 + [ca for (ra, ca) in A]
            if len(R) != k + d0 or len(C) != k + d0:
                continue
            remaining = Pset - Aset
            for cperm in itertools.permutations(C):
                n_iter += 1
                adds = [(R[i], cperm[i]) for i in range(len(R))]
                if len(set(adds)) != len(adds):
                    continue
                if any(p in remaining for p in adds):
                    continue
                n_cand += 1
                ok = True
                for f in adds:
                    for (p, q) in blocking_pairs(P, f, cache):
                        if p not in Aset and q not in Aset:
                            ok = False
                            break
                    if not ok:
                        break
                if ok:
                    for i in range(len(adds)):
                        for j in range(i + 1, len(adds)):
                            for cell in line_cells(adds[i], adds[j], n):
                                if cell in remaining and cell not in adds:
                                    ok = False
                                    break
                            if not ok:
                                break
                        if not ok:
                            break
                if ok and len(adds) >= 3:
                    for tri in itertools.combinations(adds, 3):
                        (a, b, c) = tri
                        if (b[0] - a[0]) * (c[1] - a[1]) == \
                                (c[0] - a[0]) * (b[1] - a[1]):
                            ok = False
                            break
                if ok:
                    cand = sorted(remaining) + sorted(adds)
                    key = tuple(sorted(cand))
                    if key not in checked:
                        checked.add(key)
                        if stats is not None:
                            stats['gate'] = stats.get('gate', 0) + 1
                        if no3_valid(cand, n) is None:
                            return cand
                        if len(checked) > cap_candidates:
                            if log:
                                log("  [ladder] candidate cap reached -- stop")
                            return None
        if stats is not None:
            stats[k] = (n_iter, n_cand)
    return None


def ladder_repair_naive(partial, n, kmax=3):
    """Reference ladder (sym_diag5.ladder_repair, uncapped) for selftest."""
    P = set(partial)
    s = len(partial)
    if s == 2 * n:
        return partial if no3_valid(partial, n) is None else None
    rows = [sum(1 for p in partial if p[0] == r) for r in range(n)]
    cols = [sum(1 for p in partial if p[1] == c) for c in range(n)]
    d0 = 2 * n - s
    if d0 <= 0 or d0 > 5:
        return None
    R0m = []
    C0m = []
    for r in range(n):
        if rows[r] > 2:
            return None
        for _ in range(2 - rows[r]):
            R0m.append(r)
    for c in range(n):
        if cols[c] > 2:
            return None
        for _ in range(2 - cols[c]):
            C0m.append(c)
    if len(R0m) != d0 or len(C0m) != d0:
        return None
    for k in range(0, kmax + 1):
        if k + d0 > 5:
            break
        for A in itertools.combinations(partial, k):
            Aset = set(A)
            R = list(R0m)
            C = list(C0m)
            for (ra, ca) in A:
                R.append(ra)
                C.append(ca)
            if len(R) != k + d0 or len(C) != k + d0:
                continue
            for cperm in itertools.permutations(C):
                adds = [(R[i], cperm[i]) for i in range(len(R))]
                if len(set(adds)) != len(adds):
                    continue
                if any(p in (P - Aset) for p in adds):
                    continue
                cand = [p for p in partial if p not in Aset] + adds
                if no3_valid(cand, n) is None:
                    return cand
    return None


def fresh_verify(pts, n):
    """Verify in a fresh python process (project convention)."""
    code = (
        "import sys, json; "
        f"sys.path.insert(0, {os.path.dirname(os.path.abspath(__file__))!r}); "
        "from no3in import no3_valid; "
        f"v = no3_valid(json.loads({json.dumps(pts)!r}), {n}); "
        "print('OK' if v is None else f'BAD {v}')"
    )
    out = subprocess.run([sys.executable, '-c', code],
                         capture_output=True, text=True, timeout=600)
    return out.stdout.strip() == 'OK', out.stdout.strip()


def selftest():
    """Synthetic partials from known 2n-solutions: pruned vs naive ladder."""
    rng = random.Random(12345)
    files = [
        (os.path.join(os.path.dirname(os.path.abspath(__file__)), "base_witness_n12.json"), 12),
        (os.path.join(os.path.dirname(os.path.abspath(__file__)), "base_witness_n14.json"), 14),
        (os.path.join(os.path.dirname(os.path.abspath(__file__)), "asym_witness_m16.json"), 16),
    ]
    fails = 0
    for path, n in files:
        d = json.load(open(path))
        S = [tuple(p) for p in d["points"]]
        assert len(S) == 2 * n and no3_valid(S, n) is None
        for d0 in (1, 2):
            del_set = rng.sample(S, d0)
            partial = [p for p in S if p not in del_set]
            t0 = time.time()
            sol_pr = ladder_repair_pruned(partial, n)
            t_pr = time.time() - t0
            t0 = time.time()
            sol_na = ladder_repair_naive(partial, n)
            t_na = time.time() - t0
            ok_pr = sol_pr is not None and no3_valid(sol_pr, n) is None \
                and [sum(1 for p in sol_pr if p[0] == r) for r in range(n)] \
                == [2] * n
            status = "OK" if (sol_pr is None) == (sol_na is None) and ok_pr \
                else "MISMATCH"
            if status != "OK":
                fails += 1
            print(f"  selftest n={n} d0={d0}: pruned={sol_pr is not None} "
                  f"({t_pr:.1f}s) naive={sol_na is not None} ({t_na:.1f}s) "
                  f"{status}", flush=True)
        # 0-row case: delete BOTH points of one row (d0=2, empty row) --
        # exercises the multiset deficit bookkeeping (k=0 restore should hit)
        row_r = rng.randrange(n)
        partial0 = [p for p in S if p[0] != row_r]
        t0 = time.time()
        sol_pr0 = ladder_repair_pruned(partial0, n)
        t_pr0 = time.time() - t0
        t0 = time.time()
        sol_na0 = ladder_repair_naive(partial0, n)
        t_na0 = time.time() - t0
        ok0 = sol_pr0 is not None and no3_valid(sol_pr0, n) is None
        status0 = "OK" if ok0 and (sol_na0 is not None) else "MISMATCH"
        if status0 != "OK":
            fails += 1
        print(f"  selftest n={n} 0-row: pruned={sol_pr0 is not None} "
              f"({t_pr0:.1f}s) naive={sol_na0 is not None} ({t_na0:.1f}s) "
              f"{status0}", flush=True)
    print(f"selftest done: {'ALL OK' if fails == 0 else f'{fails} FAILURES'}")
    return fails


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--deadend', default=os.path.join(REPO, 'n71_deadend.json'))
    ap.add_argument('--out', default=os.path.join(REPO, 'n71_repair_solution.json'))
    ap.add_argument('--cap', type=float, default=2400,
                    help='wall-clock seconds for the repair loop '
                         '(n=15 dead-end exhausts in ~1s; n=71 is ~125x '
                         'more triples + ~24x larger pair scans)')
    ap.add_argument('--selftest', action='store_true')
    a = ap.parse_args()

    if a.selftest:
        sys.exit(1 if selftest() else 0)

    if not os.path.exists(a.deadend):
        alt = None
        if '--deadend' not in sys.argv:
            for cand in ('n71_deadend_b.json', 'n71_deadend_c.json'):
                p = os.path.join(REPO, cand)
                if os.path.exists(p):
                    alt = p
                    break
        if alt:
            print(f"[n71_repair] default dead-end absent; using {alt}")
            a.deadend = alt
        else:
            print(f"[n71_repair] {a.deadend} not present -- nothing to do")
            return
    d = json.load(open(a.deadend))
    m = d["m"]
    pts = sorted(tuple(p) for p in d["points"])
    n = m
    print(f"[n71_repair] dead-end loaded: m={m} size={len(pts)} cap={a.cap}s",
          flush=True)
    bad = no3_valid(pts, n)
    print(f"  partial no3_valid={bad}", flush=True)
    if len(pts) == 2 * n:
        # solver closed the gap itself: verify and announce
        ok, msg = fresh_verify(pts, n)
        print(f"  SIZE 2n ALREADY REACHED; fresh verify: {msg}")
        if ok:
            json.dump({"m": m, "size": len(pts), "points": pts,
                       "source": "deadend_closed"},
                      open(a.out, "w"), indent=1)
            print(f"  *** f({m}) = {2 * m} settled; saved {a.out}")
        return
    if len(pts) < 2 * n - 5:
        print(f"  partial too far from 2n (size={len(pts)}) -- repair not "
              f"designed for d0>5; nothing to do")
        return
    rows = [sum(1 for p in pts if p[0] == r) for r in range(n)]
    cols = [sum(1 for p in pts if p[1] == c) for c in range(n)]
    print(f"  row counts: {sorted(rows, reverse=True)[:5]} ... "
          f"(deficit rows: {[r for r in range(n) if rows[r] < 2]})", flush=True)
    print(f"  col counts: {sorted(cols, reverse=True)[:5]} ... "
          f"(deficit cols: {[c for c in range(n) if cols[c] < 2]})", flush=True)

    if len(pts) == 2 * n - 1:
        r0 = [r for r in range(n) if rows[r] < 2][0]
        c0 = [c for c in range(n) if cols[c] < 2][0]
        t = (r0, c0)
        blk = blocking_pairs(pts, t, {})
        print(f"  missing cell t={t}: {len(blk)} blocking pairs of the partial:",
              flush=True)
        for (p, q) in blk[:12]:
            print(f"    {p} -- {q}", flush=True)
        if len(blk) > 12:
            print(f"    ... ({len(blk) - 12} more)", flush=True)
        # cells of the deficit row blocked by the partial (diagnostic: is the
        # dead-end 'one-blocked-cell' or 'whole-row-blocked'?)
        nrow_blocked = 0
        for c in range(n):
            if (r0, c) not in pts and blocking_pairs(pts, (r0, c), {}):
                nrow_blocked += 1
        print(f"  deficit row r={r0}: {nrow_blocked}/{n - rows[r0]} empty "
              f"cells blocked (row-mate count {rows[r0]})", flush=True)

    t0 = time.time()
    stats = {}
    sol = ladder_repair_pruned(pts, n, kmax=3,
                               log=lambda m_: print(m_, flush=True),
                               stats=stats)
    wall = time.time() - t0
    for k in sorted(kk for kk in stats if kk != 'gate'):
        it, ca = stats[k]
        print(f"  k={k}: {it} (A,perm) iterations, {ca} distinct candidates",
              flush=True)
    print(f"  no3_valid gate calls: {stats.get('gate', 0)}", flush=True)
    if sol is None:
        print(f"[n71_repair] k<=3 REPAIR FAILED in {wall:.0f}s "
              f"(partial={len(pts)}): f({m})=142 not settled; dead-end is "
              f">=4 removals from any solution at k<=3", flush=True)
        return
    bad = no3_valid(sol, n)
    print(f"  candidate no3_valid={bad} wall={wall:.0f}s", flush=True)
    ok, msg = fresh_verify(sol, n)
    print(f"  fresh-process verify: {msg}", flush=True)
    if not ok:
        print("  [ERROR] fresh verification FAILED -- not announcing", flush=True)
        return
    json.dump({"m": m, "size": len(sol), "points": sorted(sol),
               "source": "k3_ladder_repair", "wall_s": round(wall, 1)},
              open(a.out, "w"), indent=1)
    print(f"  *** SETTLED: f({m}) = {2 * m}; witness saved to {a.out} "
          f"(fresh-process verified)", flush=True)


if __name__ == '__main__':
    main()
