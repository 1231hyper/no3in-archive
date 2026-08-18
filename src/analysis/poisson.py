#!/usr/bin/env python3
"""Poisson (log-link) regressions of the even-n max-cycle <= 3 series
(paper Section 3), recomputed from the snapshot.

* labeled counts of max-<=-3 solutions at even n = 8..20;
* class counts of max-<=-3 classes at even n = 8..20.

Both are Poisson-style log-linear fits with the corrected fitter
(score with backtracking line search on the deviance, per r11c).
The fits extrapolate lambda at n = 21, 22, 23 and the fitted model is
used to calibrate the n = 17 zero and the N3(21) = 8 known-class count.

Asserted against the paper's published numbers:
  * the labeled even-n series is 48, 31, 24, 18, 18, 16, 8 (exact);
  * the full labeled series n = 8..20 is 48, 20, 31, 24, 24, 20, 18, 8,
    18, 0, 16, 4, 8 (exact);
  * labeled slope ~ -0.125 per unit n, class slope ~ -0.11 (tol 0.005);
  * extrapolated N3(21..23) ~ 8.5, 7.5, 6.6 labeled and 2.1, 1.9, 1.7
    classes (tol 0.3);
  * P(N3 = 8 | lambda(21)) ~ 0.14 and P(N3 = 0 | lambda(17)) ~ 0.04
    (tol 0.02).
"""

import argparse
import json
import math
import os
import sys
import time

from src.parser.decode import decode_line
from src.parser.geom import stabilizer_type, cycle_spectrum

EVEN_NS = [8, 10, 12, 14, 16, 18, 20]
FULL_NS = list(range(8, 21))
# paper series
LIT_FULL_LABELED = [48, 20, 31, 24, 24, 20, 18, 8, 18, 0, 16, 4, 8]
LIT_LABELED_SLOPE = -0.125
LIT_CLASS_SLOPE = -0.11
LIT_LABELED_LAMBDA_21_23 = (8.5, 7.5, 6.6)
LIT_CLASS_LAMBDA_21_23 = (2.1, 1.9, 1.7)


def poisson_fit(ns, ys):
    """Poisson log-link fit (a + b*n) by score iteration with
    backtracking line search on the deviance (r11c corrected fitter)."""
    a, b = math.log(ys[0]), 0.0
    if len(ys) > 1 and ns[-1] != ns[0]:
        b = (math.log(ys[-1]) - math.log(ys[0])) / (ns[-1] - ns[0])

    def nll(aa, bb):
        return sum(math.exp(aa + bb * nn) - yy * (aa + bb * nn)
                   for nn, yy in zip(ns, ys))

    f0 = nll(a, b)
    for _ in range(100):
        mu = [math.exp(a + b * nn) for nn in ns]
        z = [yy - mm for yy, mm in zip(ys, mu)]
        s00 = sum(mu)
        s01 = sum(mu[i] * ns[i] for i in range(len(ns)))
        s11 = sum(mu[i] * ns[i] * ns[i] for i in range(len(ns)))
        sc0 = sum(z)
        sc1 = sum(z[i] * ns[i] for i in range(len(ns)))
        det = s00 * s11 - s01 * s01
        da = (sc0 * s11 - sc1 * s01) / det
        db = (sc1 * s00 - sc0 * s01) / det
        t = 1.0
        while t > 1e-10:
            an, bn = a + t * da, b + t * db
            if nll(an, bn) < f0:
                a, b, f0 = an, bn, nll(an, bn)
                break
            t *= 0.5
        if t <= 1e-10 or (abs(da) < 1e-12 and abs(db) < 1e-12):
            break
    return a, b, f0


def poisson_pmf(k, lam):
    return math.exp(-lam) * lam ** k / math.factorial(k)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--snapshot",
                    default="data/raw/all_known_solutions.txt")
    ap.add_argument("--out", default="data/derived_tables")
    ap.add_argument("--log-dir", default="results/execution_logs")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    os.makedirs(args.log_dir, exist_ok=True)
    logpath = os.path.join(args.log_dir, "poisson_run.log")
    lf = open(logpath, "w", encoding="utf-8")

    def both(msg):
        print(msg, flush=True)
        lf.write(msg + "\n")
        lf.flush()

    t0 = time.time()
    both("poisson analysis  snapshot %s" % args.snapshot)

    # ---- series from the snapshot ----
    lab = {n: 0 for n in FULL_NS}
    cls = {n: 0 for n in FULL_NS}
    with open(args.snapshot, "rb") as f:
        for raw in f:
            d = decode_line(raw.decode("ascii"))
            if d is None:
                continue
            n, sym, pts = d
            if not (8 <= n <= 20):
                continue
            if max(cycle_spectrum(pts, n)) <= 3:
                lab[n] += stabilizer_type(pts, n)[0]
                cls[n] += 1
    full_lab = [lab[n] for n in FULL_NS]
    both("  labeled max<=3 series n = 8..20: %s" % full_lab)
    both("  class  max<=3 series n = 8..20: %s"
         % [cls[n] for n in FULL_NS])
    assert full_lab == LIT_FULL_LABELED, \
        "labeled series %s != paper %s" % (full_lab, LIT_FULL_LABELED)

    # ---- fits ----
    ylab = [lab[n] for n in EVEN_NS]
    ycl = [cls[n] for n in EVEN_NS]
    a1, b1, nll1 = poisson_fit(EVEN_NS, ylab)
    a2, b2, nll2 = poisson_fit(EVEN_NS, ycl)
    lam_lab = [math.exp(a1 + b1 * nn) for nn in (21, 22, 23)]
    lam_cls = [math.exp(a2 + b2 * nn) for nn in (21, 22, 23)]
    p8_at_21 = poisson_pmf(8, lam_lab[0])
    p0_at_17 = poisson_pmf(0, math.exp(a2 + b2 * 17))

    both("  labeled fit: slope=%.4f e^slope=%.4f NLL=%.6f" %
         (b1, math.exp(b1), nll1))
    both("    lambda(21..23) = %.2f, %.2f, %.2f   P(N3=8|lam21)=%.3f" %
         (lam_lab[0], lam_lab[1], lam_lab[2], p8_at_21))
    both("  class  fit: slope=%.4f e^slope=%.4f NLL=%.6f" %
         (b2, math.exp(b2), nll2))
    both("    lambda(21..23) = %.2f, %.2f, %.2f   P(N3=0|lam17)=%.3f" %
         (lam_cls[0], lam_cls[1], lam_cls[2],
          poisson_pmf(0, math.exp(a2 + b2 * 17))))
    both("    labeled-per-class n=21..23: %.2f, %.2f, %.2f" %
         tuple(lam_lab[i] / lam_cls[i] for i in range(3)))

    # ---- assertions vs the paper ----
    assert abs(b1 - LIT_LABELED_SLOPE) < 0.005, "labeled slope %f" % b1
    assert abs(b2 - LIT_CLASS_SLOPE) < 0.005, "class slope %f" % b2
    for i, lit in enumerate(LIT_LABELED_LAMBDA_21_23):
        assert abs(lam_lab[i] - lit) < 0.3, "labeled lambda21_23"
    for i, lit in enumerate(LIT_CLASS_LAMBDA_21_23):
        assert abs(lam_cls[i] - lit) < 0.3, "class lambda21_23"
    assert abs(p8_at_21 - 0.14) < 0.02, "P(N3=8|lam21)"
    assert abs(p0_at_17 - 0.04) < 0.02, "P(N3=0|lam17)"

    # ---- outputs ----
    out = {
        "labeled_series_n8_20": full_lab,
        "class_series_n8_20": [cls[n] for n in FULL_NS],
        "even_ns": EVEN_NS,
        "labeled": {"ys": ylab, "a": a1, "b": b1, "exp_b": math.exp(b1),
                    "nll": nll1,
                    "lambda_21_23": [round(x, 4) for x in lam_lab],
                    "p_N3_eq_8_at_21": p8_at_21},
        "class": {"ys": ycl, "a": a2, "b": b2, "exp_b": math.exp(b2),
                  "nll": nll2,
                  "lambda_21_23": [round(x, 4) for x in lam_cls],
                  "lambda_17": math.exp(a2 + b2 * 17),
                  "p_N3_eq_0_at_17": p0_at_17},
        "labeled_per_class_21_23": [round(lam_lab[i] / lam_cls[i], 4)
                                    for i in range(3)],
    }
    with open(os.path.join(args.out, "poisson_fits.json"), "w",
              encoding="utf-8") as f:
        json.dump(out, f, indent=1, sort_keys=True, default=str)
    both("  wrote poisson_fits.json")
    both("  done in %.1fs" % (time.time() - t0))
    lf.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
