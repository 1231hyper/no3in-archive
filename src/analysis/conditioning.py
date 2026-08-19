#!/usr/bin/env python3
"""Conditioning analysis of the (T, X) mechanism (paper Section 3).

For every A001499 admissible n x n 0-1 matrix with row and column sums
2 (a 2-regular bipartite graph, the *unlabeled* population behind the
census), compute

    T = number of collinear triples
    X = number of corner secant pairs at the (n, n) corner: cells
        grouped by normalized direction (n-r, n-c) to the apex,
        X = sum over rays of C(v, 2)  (v = points on the ray).

Exact enumeration for n = 5, 6, 7 (3,110,940 matrices at n = 7) and a
uniform Monte Carlo sample of 10^6 matrices at n = 8 (exact-weight
sequential sampler, fixed seed 20260818).

Cross-checks (reproduced from the research run r11b):
  * T = 0 count equals the DB labeled solution count at n = 5, 6, 7
    (32, 50, 132) -- asserted exactly;
  * unconditional mean X equals the closed form
    E_pair * (sum m^2 - n^2) / 2 with E_pair = 2(2n-3)/(n(n-1)^2)
    -- asserted to 1e-9;
  * no-triple mean X matches the four-corner measured means of the DB
    (0.94, 2.16, 1.47 at n = 5..7) -- asserted to 0.01.

Deterministic: the exact part has no randomness; the MC part uses the
fixed seed below.  Runtime ~20 min (n = 7 exact ~6 min; MC ~11 min).
"""

import argparse
import csv
import json
import math
import os
import random
import sys
import time
from collections import defaultdict
from functools import lru_cache

from src.parser.decode import decode_line
from src.parser.geom import stabilizer_type

SEED = 20260818
MC_N8 = 10 ** 6
# literature no-triple mean X (four-corner means from the DB census)
LIT_T0_MEAN = {5: 0.94, 6: 2.16, 7: 1.47}


def matrices(n):
    """All n x n 0-1 matrices with row and column sums 2, row by row,
    as tuples of (c1, c2) column pairs."""
    def rec(r, colcnt, acc):
        if r == n:
            yield tuple(acc)
            return
        for c1 in range(n - 1):
            for c2 in range(c1 + 1, n):
                if colcnt[c1] < 2 and colcnt[c2] < 2:
                    nc = list(colcnt)
                    nc[c1] += 1
                    nc[c2] += 1
                    acc.append((c1, c2))
                    yield from rec(r + 1, tuple(nc), acc)
                    acc.pop()
    yield from rec(0, (0,) * n, [])


def build_tables(n):
    """Direction lookup tables: dirid[a][b] = direction id of cell b as
    seen from a (for the triple count T), cidx[cell] = corner-ray id of
    the cell as seen from the apex (n-1, n-1) (for X)."""
    nn = n * n
    dmap = {}
    dirid = [[-1] * nn for _ in range(nn)]
    for a in range(nn):
        ra, ca = divmod(a, n)
        for b in range(nn):
            if a == b:
                continue
            rb, cb = divmod(b, n)
            dr, dc = rb - ra, cb - ca
            g = math.gcd(abs(dr), abs(dc))
            k = (dr // g, dc // g)
            if k not in dmap:
                dmap[k] = len(dmap)
            dirid[a][b] = dmap[k]
    cd = {}
    cidx = [-1] * nn
    for b in range(nn):
        rb, cb = divmod(b, n)
        dr, dc = n - rb, n - cb
        g = math.gcd(dr, dc)
        k = (dr // g, dc // g)
        if k not in cd:
            cd[k] = len(cd)
        cidx[b] = cd[k]
    return dirid, cidx, len(dmap)


def stats(vals):
    if not vals:
        return None, None, None
    m = sum(vals) / len(vals)
    v = sum((x - m) ** 2 for x in vals) / len(vals)
    return m, v, v / m if m else float('nan')


def sum_m2(n):
    """Sum of m^2 over the (n, n) corner rays; cross-checks the closed
    form n^2 + 2 * sum_{q >= 2} phi(q) floor(n/q)^2."""
    rays = {}
    for r in range(n):
        for c in range(n):
            dr, dc = n - r, n - c
            g = math.gcd(dr, dc)
            k = (dr // g, dc // g)
            rays[k] = rays.get(k, 0) + 1
    return sum(m * m for m in rays.values())


def e_pair_formula(n):
    p2 = 2.0 * (2 * n - 3) / (n * (n - 1) ** 2)
    return p2 * (sum_m2(n) - n * n) / 2


def joint_stats(n, dirid, cidx, nd):
    """Stream the enumeration, returning per-t X aggregates plus the
    ray-clean and no-triple X lists."""
    nc = max(cidx) + 1
    byt = defaultdict(list)
    rayclean = []
    solX = []
    for mat in matrices(n):
        pts = [r * n + c for r, cs in enumerate(mat) for c in cs]
        freq = [0] * nc
        for p in pts:
            freq[cidx[p]] += 1
        x = sum(v * (v - 1) // 2 for v in freq)
        t = 0
        for a in pts:
            f = [0] * nd
            for b in pts:
                if b != a:
                    f[dirid[a][b]] += 1
            t += sum(v * (v - 1) // 2 for v in f)
        t //= 2
        byt[t].append(x)
        if max(freq) <= 2:
            rayclean.append(x)
        if t == 0:
            solX.append(x)
    return byt, rayclean, solX


def summarize(n, byt, rayclean, solX):
    xs_all = [x for xs in byt.values() for x in xs]
    ts = [t for t, xs in byt.items() for _ in xs]
    m_all, v_all, f_all = stats(xs_all)
    m_rc, v_rc, f_rc = stats(rayclean)
    m_sol, v_sol, f_sol = stats(solX)
    mT = sum(ts) / len(ts)
    vT = sum((t - mT) ** 2 for t in ts) / len(ts)
    cov = (sum(x * t for x, t in zip(xs_all, ts)) / len(xs_all)
           - m_all * mT)
    corr = cov / math.sqrt(v_all * vT) if v_all and vT else float('nan')
    rows = [{"t": t, "count": len(xs), "mean_x": round(sum(xs) / len(xs), 6),
             "var_x": round(stats(xs)[1], 6)}
            for t, xs in sorted(byt.items())]
    return {
        "n": n, "matrices": sum(r["count"] for r in rows),
        "ray_clean": len(rayclean),
        "ray_clean_mean_x": m_rc, "ray_clean_var_x": v_rc,
        "t0_count": len(solX), "t0_mean_x": m_sol, "t0_var_x": v_sol,
        "t0_fano": f_sol,
        "mean_x": m_all, "var_x": v_all, "fano_x": f_all,
        "mean_t": mT, "var_t": vT, "cov_tx": cov, "corr_tx": corr,
        "e_pair_formula": e_pair_formula(n), "sum_m2": sum_m2(n),
        "per_t": rows,
    }


def w_table(n):
    @lru_cache(maxsize=None)
    def W(r, c0, c1, c2):
        if r == 0:
            return 1 if c1 == 0 and c2 == 0 else 0
        s = 0
        if c2 >= 2:
            s += c2 * (c2 - 1) // 2 * W(r - 1, c0, c1 + 2, c2 - 2)
        if c2 >= 1 and c1 >= 1:
            s += c2 * c1 * W(r - 1, c0 + 1, c1, c2 - 1)
        if c1 >= 2:
            s += c1 * (c1 - 1) // 2 * W(r - 1, c0 + 2, c1 - 2, c2)
        return s
    return W


def sample_matrix(n, W, rng):
    caps = [2] * n
    mat = []
    for r in range(n):
        c2 = [i for i in range(n) if caps[i] == 2]
        c1 = [i for i in range(n) if caps[i] == 1]
        c0 = n - len(c2) - len(c1)
        nr = n - r - 1
        w22 = (len(c2) * (len(c2) - 1) // 2 *
               W(nr, c0, len(c1) + 2, len(c2) - 2)
               if len(c2) >= 2 else 0)
        w21 = (len(c2) * len(c1) * W(nr, c0 + 1, len(c1), len(c2) - 1)
               if len(c2) >= 1 and len(c1) >= 1 else 0)
        w11 = (len(c1) * (len(c1) - 1) // 2 *
               W(nr, c0 + 2, len(c1) - 2, len(c2))
               if len(c1) >= 2 else 0)
        u = rng.random() * (w22 + w21 + w11)
        if u < w22:
            i, j = rng.sample(c2, 2)
        elif u < w22 + w21:
            i = rng.choice(c2)
            j = rng.choice(c1)
        else:
            i, j = rng.sample(c1, 2)
        caps[i] -= 1
        caps[j] -= 1
        mat.append((i, j))
    return mat


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--snapshot",
                    default="data/raw/all_known_solutions.txt")
    ap.add_argument("--out", default="data/derived_tables")
    ap.add_argument("--mc-n8", type=int, default=MC_N8)
    ap.add_argument("--log-dir", default="results/execution_logs")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    os.makedirs(args.log_dir, exist_ok=True)
    logpath = os.path.join(args.log_dir, "conditioning_run.log")
    lf = open(logpath, "w", encoding="utf-8")

    def both(msg):
        print(msg, flush=True)
        lf.write(msg + "\n")
        lf.flush()

    t0 = time.time()
    both("conditioning analysis  snapshot %s" % args.snapshot)

    # DB labeled solution counts at n = 5..7 (primary implementation)
    db_lab = {}
    with open(args.snapshot, "rb") as f:
        for raw in f:
            d = decode_line(raw.decode("ascii"))
            if d is None:
                continue
            n, sym, pts = d
            if n not in (5, 6, 7):
                continue
            db_lab[n] = db_lab.get(n, 0) + stabilizer_type(pts, n)[0]
    both("  DB labeled solutions n = 5..7: %s" %
         {k: db_lab[k] for k in sorted(db_lab)})

    # ---- exact enumeration n = 5..7 ----
    results = {}
    for n in (5, 6, 7):
        tA = time.time()
        dirid, cidx, nd = build_tables(n)
        byt, rayclean, solX = joint_stats(n, dirid, cidx, nd)
        s = summarize(n, byt, rayclean, solX)
        results[n] = s
        # assertions
        assert s["matrices"] in (2040, 67950, 3110940), \
            "matrix count mismatch at n=%d: %d" % (n, s["matrices"])
        assert s["t0_count"] == db_lab[n], \
            "T=0 count %d != DB labeled %d at n=%d" % (s["t0_count"],
                                                       db_lab[n], n)
        assert abs(s["mean_x"] - s["e_pair_formula"]) < 1e-9, \
            "mean X vs formula mismatch at n=%d" % n
        assert abs(s["t0_mean_x"] - LIT_T0_MEAN[n]) < 0.01, \
            "no-triple mean X mismatch at n=%d" % n
        both("  n=%d: matrices=%d ray-clean=%d T=0=%d  mean X=%.4f "
             "(formula %.4f)  no-triple mean X=%.4f (lit %.2f)  "
             "E[T]=%.3f  Corr(T,X)=%.3f" %
             (n, s["matrices"], s["ray_clean"], s["t0_count"],
              s["mean_x"], s["e_pair_formula"], s["t0_mean_x"],
              LIT_T0_MEAN[n], s["mean_t"], s["corr_tx"]))

    # ---- n = 8 Monte Carlo ----
    n = 8
    tA = time.time()
    W = w_table(8)
    dirid, cidx, nd = build_tables(n)
    nc = max(cidx) + 1
    total = W(8, 0, 0, 8)
    assert total == 187530840
    both("  n=8: A001499(8) = %d (W-table cross-check)" % total)
    rng = random.Random(SEED)
    byt = defaultdict(list)
    for k in range(args.mc_n8):
        mat = sample_matrix(8, W, rng)
        pts = [r * 8 + c for r, cs in enumerate(mat) for c in cs]
        freq = [0] * nc
        for p in pts:
            freq[cidx[p]] += 1
        x = sum(v * (v - 1) // 2 for v in freq)
        t = 0
        for a in pts:
            f = [0] * nd
            for b in pts:
                if b != a:
                    f[dirid[a][b]] += 1
            t += sum(v * (v - 1) // 2 for v in f)
        t //= 2
        byt[t].append(x)
        if (k + 1) % 200000 == 0:
            both("    ... %d sampled" % (k + 1))
    s8 = summarize(8, byt, [], [])
    s8["seed"] = SEED
    s8["mc_samples"] = args.mc_n8
    results[8] = s8
    both("  n=8 MC: mean X=%.4f (formula %.4f) E[T]=%.3f Corr(T,X)=%.3f"
         % (s8["mean_x"], s8["e_pair_formula"], s8["mean_t"],
            s8["corr_tx"]))

    # ---- write outputs ----
    with open(os.path.join(args.out, "conditioning_joint_n5_7.csv"),
              "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["n", "t", "count", "mean_x", "var_x"])
        for n in (5, 6, 7):
            for r in results[n]["per_t"]:
                w.writerow([n, r["t"], r["count"], r["mean_x"], r["var_x"]])
    with open(os.path.join(args.out, "conditioning_mc_n8.csv"),
              "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["n", "seed", "t", "count", "mean_x", "var_x"])
        for r in results[8]["per_t"]:
            w.writerow([8, SEED, r["t"], r["count"], r["mean_x"],
                        r["var_x"]])
    out = {str(k): {kk: vv for kk, vv in v.items() if kk != "per_t"}
           for k, v in results.items()}
    out["_meta"] = {"seed": SEED, "mc_n8_samples": args.mc_n8}
    with open(os.path.join(args.out, "conditioning_summary.json"), "w",
              newline="\n", encoding="utf-8") as f:
        json.dump(out, f, indent=1, sort_keys=True, default=str)
    both("  wrote conditioning_joint_n5_7.csv, conditioning_mc_n8.csv, "
         "conditioning_summary.json")
    both("  done")
    lf.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
