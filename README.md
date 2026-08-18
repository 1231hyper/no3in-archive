# no3in-archive

Reproducible code and data archive for the paper
*"Cycle structure and the Hamming geometry of no-three-in-line solutions"*.

This repository pins the exact snapshot of Flammenkamp's no-three-in-line
database used in the paper, recomputes every `[DB-Exh]` headline claim from
that snapshot with two independent code paths, and emits machine-readable
tables for the derived statistics.

**Status of the raw database.** The source database is Flammenkamp's
no-three-in-line collection (URL below). Its page states that the
*algorithms* are downloadable for free but gives no explicit licence for
the *data file*, so this repository does **not** redistribute the raw
snapshot. It archives instead:

- the download recipe (`data/download_snapshot.py`) and the pin
  (`data/snapshot_manifest.txt`: URL, revision date, byte count,
  SHA-256 digest, format specification);
- all derived tables (`data/derived_tables/`), which are facts computed
  from the pinned snapshot;
- the full verification pipeline (parser, census, independent verifier,
  conditioning enumeration, Monte Carlo, Poisson fits);
- a one-command reproduction script (`scripts/reproduce_all.sh`) and the
  hashes of every artifact it produces (`results/expected_hashes.txt`).

## Quick start

```bash
# 1. obtain the snapshot (or point the script at a local copy):
python data/download_snapshot.py --out data/raw/all_known_solutions.txt
#    (--from-local /path/to/copy uses an already-downloaded file)

# 2. one-command reproduction (verifies hashes, runs everything, writes logs):
bash scripts/reproduce_all.sh --snapshot data/raw/all_known_solutions.txt

# 3. inspect the outcome:
cat results/verifier_report.json      # per-claim PASS/FAIL
cat results/execution_logs/*.log      # full logs of the run
python scripts/verify_hashes.py --check   # re-check hashes of all artifacts
```

`reproduce_all.sh` runs in roughly 2.5 h on a single core
(Python 3.9+, standard library only). The time is dominated by the
independent verifier's near-neighbor phase (~1.5 h; everything else is a
few minutes, the conditioning enumeration ~30 min, measured on an
i7-class laptop with the pinned snapshot). Heavy steps can be
skipped with `--skip-conditioning` (exact n = 7 enumeration + n = 8
Monte Carlo) and `--skip-verifier` (the full verification run).

## Layout

```
data/
    snapshot_manifest.txt        pin of the raw snapshot (URL, date, size, SHA-256)
    download_snapshot.py         fetch or copy + verify the snapshot
    derived_tables/              machine-readable tables (CSV/JSON), all committed
src/
    parser/                      primary parser + census code (project lineage)
    census/                      census recomputation -> derived_tables/
    independent_verifier/        fresh, non-shared implementation of every
                                 [DB-Exh] claim -> results/verifier_report.json
    analysis/                    conditioning enumeration (n = 5..7), n = 8
                                 Monte Carlo (fixed seed), Poisson fits
scripts/
    reproduce_all.sh             one-command reproduction
    verify_hashes.py             hash check of all artifacts
results/
    expected_hashes.txt          pinned SHA-256 of every artifact
    verifier_report.json         per-claim verdicts (generated)
    execution_logs/              full logs of clean-environment runs
```

## What is verified (claim list)

The independent verifier re-implements the parser from Flammenkamp's format
specification and re-derives, without importing any `src/parser` module:

1. Snapshot integrity: 430,991 lines, n = 2..76, pinned SHA-256.
2. Per-n class counts, labeled totals and marker census for n ≤ 20
   (cross-checked against OEIS A000755 / A000769).
3. The n = 20 decomposition: 675 rot2 + 16 rot4 + 2 dia2 + 17 dia1 +
   117,347 iden = 118,057 classes; 693 true rot180-invariant classes,
   710 any-symmetry classes; 941,580 labeled solutions.
4. The full L(n) table for n = 2..20 (minimum spectra, minimizer counts),
   including the n = 17 anomaly and the L = 2 extinction at {2, 4, 8, 10}.
5. The corner-secant barrier table (labeled blocked share, n = 8..20) and
   the small-n open shares (n = 2..7).
6. The N₃ series (labeled counts of max-cycle ≤ 3 solutions, n = 8..20).
7. The min max-spectrum scan over all stored classes for 21 ≤ n ≤ 57
   (L(21) = 3 exact; L(22) ≤ 4; L(23) ≤ 4; L(26) = L(28) = 2).
8. The corpus statistics (959 classes, orbit histogram {2:112, 4:846,
   8:1}, 3,616 labeled, rct4 spread over n = 57..69).
9. The conditioning mechanism (joint (T, X) distribution over all
   A001499 matrices): the verifier independently re-derives the n = 5, 6
   enumerations and the exact E_pair formula checks; the analysis
   scripts (`src/analysis/`) extend the same machinery to n = 7 (exact,
   3,110,940 matrices) and n = 8 (10⁶-sample Monte Carlo, seed
   20260818), cross-checked against the verifier's n = 5..7 DB counts.

## Software environment

Python 3.9+, **standard library only** — no third-party dependencies
(`requirements.txt` documents this; an `environment.yml` is provided for
conda users). The Monte Carlo sampler uses Python's `random` with a fixed
seed (20260818, 10⁶ samples); its parameters are written into the log.

## Source database and citation

- Source database: Flammenkamp's no-three-in-line page,
  https://wwwhomes.uni-bielefeld.de/achim/no3in/ (download directory:
  https://wwwhomes.uni-bielefeld.de/achim/no3in/download/),
  revision 2026-08-11, `all_known_solutions` = 23,832,810 bytes,
  SHA-256 `6c385257c34af354a596b718002e2ef552b52da54b8e5065ec6a8b8c4d5026e0`.
- Paper: *Cycle structure and the Hamming geometry of no-three-in-line
  solutions* (in preparation; see `CITATION.cff`).
- Archive: Zenodo, https://doi.org/10.5281/zenodo.21997174.

## Licence

- Code (`src/`, `scripts/`, `data/download_snapshot.py`): MIT, see `LICENSE`.
- Derived tables (`data/derived_tables/`): CC BY 4.0, see `LICENSE.data`.
- The raw database is third-party material; see `data/snapshot_manifest.txt`
  for its provenance and redistribution status.
