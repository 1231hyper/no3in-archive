#!/usr/bin/env python3
"""Derived-table writer: streams the snapshot once, computes the
census-level tables with the primary implementation, and writes
machine-readable tables to data/derived_tables/.
"""

import argparse
import csv
import hashlib
import json
import os
import sys
from collections import Counter, defaultdict

from src.parser.decode import decode_line
from src.parser.geom import (stabilizer_type, cycle_spectrum,
                             corner_secants4, A755)

MARKERS = ['iden', 'rot2', 'dia1', 'ort1', 'rot4', 'rct4', 'dia2',
           'ort2', 'full']


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--snapshot", default="data/raw/all_known_solutions.txt")
    ap.add_argument("--out", default="data/derived_tables")
    ap.add_argument("--log-dir", default="results/execution_logs")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)
    os.makedirs(args.log_dir, exist_ok=True)
    logpath = os.path.join(args.log_dir, "census_tables_run.log")
    lf = open(logpath, "w", encoding="utf-8")

    def both(msg):
        print(msg, flush=True)
        lf.write(msg + "\n")
        lf.flush()

    both("census tables writer  snapshot %s" % args.snapshot)

    sha = hashlib.sha256()
    size = 0
    per_n = Counter()
    census = {}          # n -> aggregate row
    scan = {}            # n (21..56) -> aggregate
    corpus = []          # (n, marker, pts) for n = 57..76

    def new_census_row(n):
        return {"classes": 0, "labeled": 0, "r180_labeled": 0,
                "any_labeled": 0, "trivial_stab": 0, "markers": Counter(),
                "center_r180": 0, "center_nonr180": 0, "center_classes": 0,
                "L": None, "min_count": 0,
                "min_candidates": [], "l2_labeled": 0, "n3_labeled": 0,
                "bhist": Counter(), "open_labeled": 0,
                "sec_num": 0, "sec_den": 0, "sec_max": 0}

    with open(args.snapshot, "rb") as f:
        for raw in f:
            size += len(raw)
            sha.update(raw)
            d = decode_line(raw.decode("ascii"))
            if d is None:
                continue
            n, sym, pts = d
            per_n[n] += 1
            if n <= 20:
                row = census.setdefault(n, new_census_row(n))
                orbit, fixing = stabilizer_type(pts, n)
                row["classes"] += 1
                row["labeled"] += orbit
                row["markers"][sym] += 1
                if 2 in fixing:
                    row["r180_labeled"] += orbit
                if len(fixing) > 1:
                    row["any_labeled"] += orbit
                if len(fixing) == 1:
                    row["trivial_stab"] += 1
                spec = cycle_spectrum(pts, n)
                L = spec[-1]
                if row["L"] is None or L < row["L"]:
                    row["L"] = L
                    row["min_candidates"] = [spec]
                    row["min_count"] = 1
                elif L == row["L"]:
                    row["min_candidates"].append(spec)
                    row["min_count"] += 1
                if L <= 3:
                    row["n3_labeled"] += orbit
                if L == 2:
                    row["l2_labeled"] += orbit
                sec4 = corner_secants4(pts, n)
                # corner (a,b) blocked iff some direction carries >= 2
                # points; secant count = # directions with >= 2 points
                b = sum(1 for s in sec4 if any(v >= 2 for v in s.values()))
                row["bhist"][b] += 1
                row["open_labeled"] += orbit * (4 - b) // 4
                sec_sums = [sum(1 for v in s.values() if v >= 2)
                            for s in sec4]
                row["sec_num"] += orbit * sum(sec_sums)
                row["sec_den"] += 4 * orbit
                row["sec_max"] = max(row["sec_max"], max(sec_sums))
                if n % 2 == 1:
                    cc = (n - 1) // 2
                    if (cc, cc) in pts:
                        row["center_classes"] += 1
                        if 2 in fixing:
                            row["center_r180"] += 1
                        else:
                            row["center_nonr180"] += 1
            elif 21 <= n <= 56:
                agg = scan.setdefault(n, {"count": 0, "labeled": 0,
                                          "iden": 0, "minL": None,
                                          "min_spec": None})
                agg["count"] += 1
                orbit, fixing = stabilizer_type(pts, n)
                agg["labeled"] += orbit
                if sym == "iden":
                    agg["iden"] += 1
                spec = cycle_spectrum(pts, n)
                L = spec[-1]
                if agg["minL"] is None or L < agg["minL"] or \
                        (L == agg["minL"] and spec < agg["min_spec"]):
                    agg["minL"] = L
                    agg["min_spec"] = spec
            else:
                corpus.append((n, sym, pts))

    digest = sha.hexdigest()
    both("  %d lines, %d bytes, sha256 %s, n %s..%s" %
         (sum(per_n.values()), size, digest, min(per_n), max(per_n)))

    # ---------------- snapshot_stats.json ----------------
    snapshot_stats = {
        "file": os.path.basename(args.snapshot),
        "size_bytes": size,
        "sha256": digest,
        "lines": sum(per_n.values()),
        "n_min": min(per_n), "n_max": max(per_n),
        "lines_le20": sum(per_n[n] for n in range(2, 21)),
        "lines_21_57": sum(per_n[n] for n in range(21, 58)),
        "lines_58_76": sum(per_n[n] for n in range(58, 77)),
        "per_n_lines": {str(k): v for k, v in sorted(per_n.items())},
    }
    _write_json(args.out, "snapshot_stats.json", snapshot_stats)

    # ---------------- census_n2_20.csv + n3_series.csv + l_values.csv ----
    with open(os.path.join(args.out, "census_n2_20.csv"), "w",
              newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        header = (["n", "classes", "labeled", "r180_labeled",
                   "any_labeled", "trivial_stab", "center_r180",
                   "center_nonr180"] +
                  ["m_" + m for m in MARKERS] +
                  ["labeled_ref", "labeled_ok"])
        w.writerow(header)
        for n in sorted(census):
            row = census[n]
            ref = A755.get(n)
            w.writerow([n, row["classes"], row["labeled"],
                        row["r180_labeled"], row["any_labeled"],
                        row["trivial_stab"], row["center_r180"],
                        row["center_nonr180"]] +
                       [row["markers"][m] for m in MARKERS] +
                       [ref if ref is not None else "",
                        "" if ref is None else
                        (row["labeled"] == ref)])

    with open(os.path.join(args.out, "n3_series.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["n", "n3_labeled"])
        for n in sorted(census):
            w.writerow([n, census[n]["n3_labeled"]])

    with open(os.path.join(args.out, "l_values.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["n", "L", "min_spectrum", "minimizer_classes",
                    "minimizer_labeled"])
        for n in sorted(census):
            row = census[n]
            w.writerow([n, row["L"], ";".join(str(x) for x in
                                              min(row["min_candidates"])),
                        row["min_count"],
                        row["l2_labeled"] if row["L"] == 2 else ""])

    # ---------------- n20_marker_census.csv -----------------------------
    if 20 in census:
        with open(os.path.join(args.out, "n20_marker_census.csv"), "w",
                  newline="", encoding="utf-8") as f:
            w = csv.writer(f, lineterminator="\n")
            w.writerow(["marker", "classes", "labeled"])
            row = census[20]
            for m in MARKERS:
                w.writerow([m, row["markers"][m],
                            row["markers"][m] * _orbit_of(m)])
            w.writerow(["total", row["classes"], row["labeled"]])

    # ---------------- corner_barrier.csv + corner_small_n.csv -----------
    with open(os.path.join(args.out, "corner_barrier.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["n", "blocked_pct", "b4_share", "open_labeled",
                    "sec_mean", "sec_max", "bhist"])
        for n in sorted(census):
            if n < 8:
                continue
            row = census[n]
            bhist = {str(k): v for k, v in sorted(row["bhist"].items())}
            w.writerow([n,
                        round(100.0 * (1 - row["open_labeled"] /
                                       row["labeled"]), 4),
                        round(100.0 * row["bhist"][4] / row["classes"], 4),
                        row["open_labeled"],
                        round(row["sec_num"] / row["sec_den"], 6),
                        row["sec_max"],
                        json.dumps(bhist)])

    with open(os.path.join(args.out, "corner_small_n.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["n", "open_pct"])
        for n in sorted(census):
            if n > 7:
                continue
            row = census[n]
            w.writerow([n, round(100.0 * row["open_labeled"] /
                                 row["labeled"], 4)])

    # ---------------- scan_min_spectra.csv ------------------------------
    with open(os.path.join(args.out, "scan_min_spectra.csv"), "w",
              newline="", encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["n", "classes", "labeled", "minL", "min_spectrum"])
        for n in sorted(scan):
            agg = scan[n]
            w.writerow([n, agg["count"], agg["labeled"], agg["minL"],
                        ";".join(str(x) for x in agg["min_spec"])])

    # ---------------- asym_21_56.csv ------------------------------------
    with open(os.path.join(args.out, "asym_21_56.csv"), "w", newline="",
              encoding="utf-8") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(["n", "iden_classes"])
        for n in sorted(scan):
            w.writerow([n, scan[n]["iden"]])

    # ---------------- corpus_stats.json ---------------------------------
    corpus_stats = {
        "classes": len(corpus), "labeled": 0, "orbit_hist": {},
        "markers": {}, "n57_classes": 0, "n57_labeled": 0,
        "rct4_spread": {}, "minL": {},
        "b4_classes": 0, "open_labeled": 0, "blocked_pct": 0.0,
        "sec_mean_57": 0.0, "sec_mean_76": 0.0, "sec_mean_all": 0.0,
        "sec_max": 0, "rct4_audit": [0, 0], "iden57_orbit": None,
        "iden57_spectrum": None, "n": []}
    sec_num = sec_den = sec_num_57 = sec_den_57 = 0
    sec_num_76 = sec_den_76 = 0
    nmin = {}
    for (n, sym, pts) in corpus:
        orbit, fixing = stabilizer_type(pts, n)
        corpus_stats["labeled"] += orbit
        corpus_stats["orbit_hist"][str(orbit)] = \
            corpus_stats["orbit_hist"].get(str(orbit), 0) + 1
        corpus_stats["markers"][sym] = corpus_stats["markers"].get(
            sym, 0) + 1
        corpus_stats["n"].append(n)
        if n == 57:
            corpus_stats["n57_classes"] += 1
            corpus_stats["n57_labeled"] += orbit
        if sym == "rct4":
            corpus_stats["rct4_spread"][str(n)] = \
                corpus_stats["rct4_spread"].get(str(n), 0) + 1
            corpus_stats["rct4_audit"][0] += 1
            if tuple(fixing) == (0, 2):
                corpus_stats["rct4_audit"][1] += 1
        if sym == "iden" and n == 57:
            corpus_stats["iden57_orbit"] = orbit
            corpus_stats["iden57_spectrum"] = list(cycle_spectrum(pts, n))
        spec = cycle_spectrum(pts, n)
        L = spec[-1]
        if n not in nmin or L < nmin[n]:
            nmin[n] = L
        sec4 = corner_secants4(pts, n)
        b = sum(1 for s in sec4 if any(v >= 2 for v in s.values()))
        if b == 4:
            corpus_stats["b4_classes"] += 1
        corpus_stats["open_labeled"] += orbit * (4 - b) // 4
        sec_sums = [sum(1 for v in s.values() if v >= 2) for s in sec4]
        sec_num += orbit * sum(sec_sums)
        sec_den += 4 * orbit
        if n == 57:
            sec_num_57 += orbit * sum(sec_sums)
            sec_den_57 += 4 * orbit
        if n == 76:
            sec_num_76 += orbit * sum(sec_sums)
            sec_den_76 += 4 * orbit
        corpus_stats["sec_max"] = max(corpus_stats["sec_max"],
                                      max(sec_sums))
    corpus_stats["minL"] = {str(k): v for k, v in nmin.items()}
    corpus_stats["blocked_pct"] = 100.0 * (
        1 - corpus_stats["open_labeled"] / corpus_stats["labeled"])
    corpus_stats["sec_mean_57"] = sec_num_57 / sec_den_57
    corpus_stats["sec_mean_76"] = sec_num_76 / sec_den_76
    corpus_stats["sec_mean_all"] = sec_num / sec_den
    _write_json(args.out, "corpus_stats.json", corpus_stats)

    both("  tables written to %s" % args.out)
    both("  done")
    lf.close()


def _orbit_of(marker):
    """D4 orbit size of a class with the marker's declared symmetry."""
    return {'iden': 8, 'rot2': 4, 'dia1': 4, 'ort1': 4, 'rot4': 2,
            'rct4': 4, 'dia2': 2, 'ort2': 2, 'full': 1}[marker]


def _write_json(out_dir, name, obj):
    with open(os.path.join(out_dir, name), "w", newline="\n",
              encoding="utf-8") as f:
        json.dump(obj, f, indent=1, sort_keys=True, default=str)


if __name__ == "__main__":
    sys.exit(main())
