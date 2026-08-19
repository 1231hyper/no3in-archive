#!/usr/bin/env python3
"""Run and audit the k<=3 repair search on all six archived N=71 seeds.

The aggregate status is EXHAUSTED only when every child report says
EXHAUSTED.  A timeout, candidate cap, crash, or missing report makes the
aggregate INCOMPLETE; absence of a witness in such a run is not evidence for
the deletion-distance claim.
"""

import argparse
import json
import os
import subprocess
import sys
import time


HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SEEDS = [
    "n71_deadend_b.json",
    "n71_deadend_c.json",
    "n71_deadend_d2.json",
    "n71_deadend_d4.json",
    "n71_deadend_d5.json",
    "n71_deadend_d6.json",
]


def write_json(path, value):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(value, f, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--cap", type=float, default=0,
        help="wall-clock seconds per seed; 0 means no deadline (default)")
    ap.add_argument(
        "--candidate-cap", type=int, default=0,
        help="diagnostic exact-gate cap per seed; 0 disables it")
    ap.add_argument(
        "--log-dir",
        default=os.path.join(ROOT, "results", "execution_logs",
                             "n71_repair_campaign"))
    ap.add_argument(
        "--summary",
        default=os.path.join(ROOT, "results", "execution_logs",
                             "n71_repair_campaign_summary.json"))
    args = ap.parse_args()
    if args.cap < 0 or args.candidate_cap < 0:
        ap.error("--cap and --candidate-cap must be nonnegative")

    os.makedirs(args.log_dir, exist_ok=True)
    runs = []
    campaign_start = time.monotonic()
    for seed_name in SEEDS:
        stem = os.path.splitext(seed_name)[0]
        seed = os.path.join(HERE, seed_name)
        log_path = os.path.join(args.log_dir, stem + ".stdout")
        report_path = os.path.join(args.log_dir, stem + "_report.json")
        print(f"[campaign] starting {seed_name}", flush=True)
        cmd = [
            sys.executable,
            os.path.join(HERE, "n71_repair.py"),
            "--deadend", seed,
            "--cap", str(args.cap),
            "--candidate-cap", str(args.candidate_cap),
            "--report", report_path,
        ]
        started = time.monotonic()
        with open(log_path, "w", encoding="utf-8", newline="\n") as log:
            proc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT,
                                  text=True, check=False)
        child = None
        if os.path.exists(report_path):
            with open(report_path, "r", encoding="utf-8") as f:
                child = json.load(f)
        status = child.get("status") if child else "MISSING_REPORT"
        runs.append({
            "seed": seed_name,
            "status": status,
            "return_code": proc.returncode,
            "wall_seconds": round(time.monotonic() - started, 6),
            "log": os.path.relpath(log_path, ROOT),
            "report": os.path.relpath(report_path, ROOT),
            "input_sha256": (child or {}).get("input", {}).get("sha256"),
            "counters": (child or {}).get("counters"),
        })
        print(f"[campaign] {seed_name}: {status} (exit {proc.returncode})",
              flush=True)

    statuses = [run["status"] for run in runs]
    if "FOUND" in statuses:
        overall = "FOUND"
    elif all(status == "EXHAUSTED" for status in statuses):
        overall = "EXHAUSTED"
    else:
        overall = "INCOMPLETE"
    summary = {
        "schema_version": 1,
        "overall_status": overall,
        "parameters": {
            "wall_clock_cap_seconds_per_seed": args.cap,
            "exact_gate_candidate_cap_per_seed": args.candidate_cap,
        },
        "wall_seconds": round(time.monotonic() - campaign_start, 6),
        "runs": runs,
    }
    write_json(args.summary, summary)
    print(f"[campaign] overall={overall}; summary={args.summary}", flush=True)
    if overall == "INCOMPLETE":
        print("[campaign] NO EXHAUSTIVE CONCLUSION may be drawn", flush=True)
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
