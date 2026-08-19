#!/usr/bin/env python3
"""Extract machine-readable tables from the verifier's JSON report.

Reads results/verifier_report.json (written by
src/independent_verifier/run.py) and writes human-and-CI-friendly CSVs
into data/derived_tables/:

    windows_n4_13.csv       per-n Move 1 / Move 1' window census
    nearneighbor_n8_17.csv  per-n near-neighbor graph summary
    corpus_windows.csv      per-n Move 1 window census, corpus n = 57..76
    n20_sample.csv          n = 20 window sample (seed, counts)
    claims_summary.csv      one row per verifier claim (PASS/FAIL/SKIP)

The verifier report itself (results/verifier_report.json) remains the
machine-readable source of truth; these CSVs are derived views.
"""

import argparse
import csv
import json
import os
import sys


def _js(v):
    if v is None or isinstance(v, (str, int, float)):
        return "" if v is None else v
    return json.dumps(v, sort_keys=True, default=str)


def _flat(d, *path):
    """Descend d along path; return None if any key is missing."""
    for k in path:
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--report",
                    default="results/verifier_report.json")
    ap.add_argument("--out", default="data/derived_tables")
    args = ap.parse_args()

    with open(args.report, "r", encoding="utf-8") as f:
        res = json.load(f)
    os.makedirs(args.out, exist_ok=True)

    def wcsv(name, header, rows):
        path = os.path.join(args.out, name)
        with open(path, "w", newline="", encoding="utf-8") as f:
            wr = csv.writer(f, lineterminator="\n")
            wr.writerow(header)
            wr.writerows(rows)
        print("  wrote %s (%d rows)" % (path, len(rows)))

    # ---------------- windows_n4_13.csv ----------------
    rows = []
    for n in sorted(_flat(res, "tables", "windows") or {}):
        r = res["tables"]["windows"][n]
        comps = r.get("refill_comps") or []
        rows.append([
            n, r["windows"], r["c4"], r["2c2"],
            r["valid_flips"], r["same_class_flips"], r["cross_flips"],
            sum(1 for x in r.get("classes_with_flip", []) if x),
            r["nonid_total"], r["cross_total"], r["refill_edges"],
            r["undirected_edges"], r["flip_spectra_ok"],
            comps[0] if comps else 0, len(comps), _js(r["v_hist"]),
        ])
    wcsv("windows_n4_13.csv",
         ["n", "windows", "c4", "2c2", "valid_flips", "same_class_flips",
          "cross_flips", "classes_with_flip", "nonid_total", "cross_total",
          "refill_edges", "undirected_edges", "flip_spectra_ok",
          "largest_component", "n_components", "v_hist"], rows)

    # ---------------- nearneighbor_n8_17.csv ----------------
    rows = []
    near = _flat(res, "tables", "near") or {}
    for n in sorted(near):
        r = near[n]
        comps = r.get("components") or []
        rows.append([
            n, r["edges"], r["min_dist"], r["dist4_certified"],
            round(r["density_pct"], 4), r["largest_comp"],
            len(comps), _js(comps),
        ])
    wcsv("nearneighbor_n8_17.csv",
         ["n", "edges", "min_dist", "dist4_certified", "density_pct",
          "largest_comp", "n_components", "component_sizes"], rows)

    # ---------------- corpus_windows.csv ----------------
    rows = []
    cw = _flat(res, "tables", "corpus_windows") or {}
    for n in sorted(cw):
        r = cw[n]
        rows.append([n, r["windows"], r["valid_flips"]])
    wcsv("corpus_windows.csv", ["n", "windows", "valid_flips"], rows)

    # ---------------- n20_sample.csv ----------------
    s = _flat(res, "tables", "n20_sample")
    if s is not None:
        pct = (100.0 * s["valid_flips"] / s["windows"]
               if s["windows"] else "")
        rows = [[s["seed"], s["classes"], s["windows"],
                 s["valid_flips"], round(pct, 4) if pct != "" else ""]]
        wcsv("n20_sample.csv",
             ["seed", "classes", "windows", "valid_flips",
              "valid_flip_pct"], rows)

    # ---------------- claims_summary.csv ----------------
    rows = []
    for c in res.get("claims", []):
        rows.append([c["id"], c["section"], c["status"],
                     c["description"], _js(c["expected"]),
                     _js(c["measured"]), c.get("detail", "")])
    wcsv("claims_summary.csv",
         ["id", "section", "status", "description", "expected",
          "measured", "detail"], rows)

    npass = sum(1 for c in res.get("claims", []) if c["status"] == "PASS")
    nfail = sum(1 for c in res.get("claims", []) if c["status"] == "FAIL")
    nskip = sum(1 for c in res.get("claims", []) if c["status"] == "SKIP")
    print("claims: %d PASS, %d FAIL, %d SKIP" % (npass, nfail, nskip))
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main())
