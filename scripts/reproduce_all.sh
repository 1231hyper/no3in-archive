#!/usr/bin/env bash
# One-click reproduction of every derived table, analysis, and
# verification result in this archive.
#
#   bash scripts/reproduce_all.sh
#
# Requires: python 3.8+, the pinned snapshot at data/raw/
# (download with:  python data/download_snapshot.py).  No third-party
# packages are needed.
#
# Stages (deterministic; MC uses fixed seed 20260818):
#   1. snapshot integrity (size + SHA-256 vs pin)
#   2. census derived tables        (~4 min)
#   3. Poisson regressions          (~15 s)
#   4. conditioning (T, X) exact + MC   (~20 min)
#   5. independent verifier full run    (~1 h; phase 4 dominates)
#   6. extract report tables
#   7. verify hashes vs manifest
#
# Total wall time: roughly 2.5 h on a single core.  Logs are written
# to results/execution_logs/.
#
# Optional flags:
#   --snapshot <path>   use a different snapshot location (default
#                       data/raw/all_known_solutions.txt)
#   --skip-conditioning skip stage 4
#   --skip-verifier     skip stage 5 (for quick checks)
set -euo pipefail

cd "$(dirname "$0")/.."
ROOT="$(pwd)"
LOGDIR="results/execution_logs"
SNAPSHOT="data/raw/all_known_solutions.txt"
PIN_SHA256="6c385257c34af354a596b718002e2ef552b52da54b8e5065ec6a8b8c4d5026e0"
PIN_SIZE=23832810

SKIP_COND=0
SKIP_VER=0
while [ $# -gt 0 ]; do
    case "$1" in
        --skip-conditioning) SKIP_COND=1; shift ;;
        --skip-verifier)     SKIP_VER=1; shift ;;
        --snapshot)          SNAPSHOT="$2"; shift 2 ;;
        *) echo "unknown flag: $1" >&2; exit 2 ;;
    esac
done

mkdir -p "$LOGDIR"
stamp() { date "+%Y-%m-%d %H:%M:%S"; }
section() { echo; echo "==== [$(stamp)] $1 ===="; }

run_stage() {
    # run_stage <logfile> <cmd...>
    local log="$1"; shift
    echo "--- [$(stamp)] $*"
    if "$@" > "$log" 2>&1; then
        echo "    ok ($(wc -l < "$log") log lines) -> $log"
    else
        echo "    FAILED — see $log" >&2
        tail -30 "$log" >&2
        exit 1
    fi
}

section "stage 1: snapshot integrity"
if [ ! -f "$SNAPSHOT" ]; then
    echo "snapshot missing: $SNAPSHOT" >&2
    echo "run:  python data/download_snapshot.py" >&2
    exit 1
fi
size=$(wc -c < "$SNAPSHOT")
echo "  size: $size (pin $PIN_SIZE)"
[ "$size" -eq "$PIN_SIZE" ] || { echo "  SIZE MISMATCH" >&2; exit 1; }
if command -v sha256sum > /dev/null; then
    actual=$(sha256sum "$SNAPSHOT" | cut -d' ' -f1)
elif command -v shasum > /dev/null; then
    actual=$(shasum -a 256 "$SNAPSHOT" | cut -d' ' -f1)
else
    echo "  no sha256 tool found" >&2; exit 1
fi
echo "  sha256: $actual"
[ "$actual" = "$PIN_SHA256" ] || { echo "  SHA-256 MISMATCH" >&2; exit 1; }
echo "  snapshot OK (matches pin)"

section "stage 2: census derived tables"
run_stage "$LOGDIR/census_tables_run.stdout" \
    python -m src.census.tables --snapshot "$SNAPSHOT" --out data/derived_tables

section "stage 3: Poisson regressions"
run_stage "$LOGDIR/poisson_run.stdout" \
    python -m src.analysis.poisson --snapshot "$SNAPSHOT" --out data/derived_tables

if [ "$SKIP_COND" -ne 1 ]; then
    section "stage 4: conditioning (exact n=5..7 + MC n=8)"
    run_stage "$LOGDIR/conditioning_run.stdout" \
        python -m src.analysis.conditioning --snapshot "$SNAPSHOT" \
        --out data/derived_tables
else
    echo "  (skipped by --skip-conditioning)"
fi

if [ "$SKIP_VER" -ne 1 ]; then
    section "stage 5: independent verifier (full)"
    run_stage "$LOGDIR/verifier_run.stdout" \
        python -m src.independent_verifier.run --snapshot "$SNAPSHOT" \
        --out results/verifier_report.json --seed 20260818 --n20-sample 3000
    section "stage 6: extract report tables"
    run_stage "$LOGDIR/extract_report_tables.stdout" \
        python scripts/extract_report_tables.py --report results/verifier_report.json
else
    echo "  (stage 5/6 skipped by --skip-verifier)"
fi

section "stage 7: verify hashes vs manifest"
run_stage "$LOGDIR/verify_hashes_run.stdout" \
    python scripts/verify_hashes.py --check

echo
echo "==== [$(stamp)] reproduction complete ===="
