#!/usr/bin/env python3
"""Verify SHA-256 hashes of data files against the manifest.

Usage:
    python scripts/verify_hashes.py --check            # check files
    python scripts/verify_hashes.py --gen              # regenerate

The manifest is results/expected_hashes.txt, one line per file:

    <sha256-hex>  <path relative to the archive root>

--check reads the manifest and reports PASS/FAIL per file, exiting
non-zero if any file is missing or mismatched.  --gen recomputes the
manifest from the files that currently exist; the raw snapshot entry is
always written from its pinned hash (see snapshot_manifest.txt) so the
manifest is deterministic even in a clone without the snapshot (the
snapshot itself is third-party data and is not redistributed).
"""

import argparse
import hashlib
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MANIFEST = os.path.join("results", "expected_hashes.txt")
# pinned hash of the raw snapshot (data/snapshot_manifest.txt, identical
# to scripts/reproduce_all.sh PIN_SHA256)
RAW_REL = "data/raw/all_known_solutions.txt"
RAW_SHA256 = ("6c385257c34af354a596b718002e2ef552b52da54b8e"
              "5065ec6a8b8c4d5026e0")
# files that are always part of the archive (if present)
TRACKED = [
    RAW_REL,
    "data/derived_tables/snapshot_stats.json",
    "data/derived_tables/census_n2_20.csv",
    "data/derived_tables/n3_series.csv",
    "data/derived_tables/l_values.csv",
    "data/derived_tables/n20_marker_census.csv",
    "data/derived_tables/corner_barrier.csv",
    "data/derived_tables/corner_small_n.csv",
    "data/derived_tables/scan_min_spectra.csv",
    "data/derived_tables/asym_21_56.csv",
    "data/derived_tables/corpus_stats.json",
    "data/derived_tables/windows_n4_13.csv",
    "data/derived_tables/nearneighbor_n8_17.csv",
    "data/derived_tables/corpus_windows.csv",
    "data/derived_tables/n20_sample.csv",
    "data/derived_tables/claims_summary.csv",
    "data/derived_tables/conditioning_joint_n5_7.csv",
    "data/derived_tables/conditioning_mc_n8.csv",
    "data/derived_tables/conditioning_summary.json",
    "data/derived_tables/poisson_fits.json",
    "results/verifier_report.json",
]


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_manifest(path):
    out = {}
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            hexd, _, rel = line.partition(" ")
            out[rel.strip()] = hexd.strip()
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--gen", action="store_true")
    args = ap.parse_args()
    if args.check == args.gen:
        ap.error("exactly one of --check / --gen is required")

    manifest = os.path.join(ROOT, MANIFEST)
    if args.gen:
        lines = ["# expected SHA-256 of archive data files",
                 "# <sha256>  <path>"]
        for rel in TRACKED:
            path = os.path.join(ROOT, rel)
            if rel == RAW_REL:
                lines.append("%s  %s" % (RAW_SHA256, rel))
            elif os.path.exists(path):
                lines.append("%s  %s" % (sha256_file(path), rel))
            else:
                print("  (missing, skipped) %s" % rel)
        with open(manifest, "w", encoding="utf-8", newline="\n") as f:
            f.write("\n".join(lines) + "\n")
        print("wrote %s (%d entries)" % (manifest, len(lines) - 2))
        return 0

    # --check
    entries = read_manifest(manifest)
    nfail = 0
    nskip = 0
    for rel, hexd in sorted(entries.items()):
        path = os.path.join(ROOT, rel)
        if not os.path.exists(path):
            if rel == RAW_REL:
                # expected: clones lack the third-party snapshot; the
                # pinned hash in the manifest is checked once downloaded
                print("SKIP  missing (third-party snapshot, run "
                      "python data/download_snapshot.py)  %s" % rel)
                nskip += 1
                continue
            print("FAIL  missing  %s" % rel)
            nfail += 1
            continue
        actual = sha256_file(path)
        if actual == hexd:
            print("PASS  %s" % rel)
        else:
            print("FAIL  %s\n      expected %s\n      actual   %s"
                  % (rel, hexd, actual))
            nfail += 1
    print("%d/%d files OK (%d skipped)" % (len(entries) - nfail - nskip,
                                           len(entries), nskip))
    return 1 if nfail else 0


if __name__ == "__main__":
    sys.exit(main())
