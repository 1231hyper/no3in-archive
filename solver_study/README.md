# solver_study/ — frontier checks and N = 71 repair

Materials for **paper Section 8** ("Embedded-solution repair barriers at
N = 71, 73, 75").  The revised manuscript limits its N = 73 and N = 75
claims to the direct frontier-secant check; it makes no archived long-run
CP-SAT-stall or repair-exhaustion claim at those sizes.  The N = 71 local
repair result is supported by the six machine-readable exhaustive reports
described below.  Everything here is self-contained (no absolute paths, no
external files).

**Dependencies.** The three `*_warm.py` scripts and `n71_deadend.py`
require the pinned Google OR-Tools environment
(`pip install -r ../requirements-solver.txt`). The repair machinery,
the selftest, `fast_lines.py` and `no3in.py` use the standard library
only.

## What the section claims, and where it lives

1. **Maximality criterion (frontier corner secant-blocked).** Each
   archived seed passes the criterion. Re-verify directly:

   ```
   python secant_blocked_check.py
   ```

   Output: the six N = 71 dead-ends are blocked by **8, 3, 4, 5, 6, 6**
   secants through the frontier corner (70, 70); the N = 73 seed by 5
   secants; the N = 75 seed by 6. These are the exact numbers quoted in
   the paper ("3–8 secants"). Each check requires all points on blocking
   rays to be exactly 2-point lines, so the counts are genuine secants
   (no 3-point rays).

2. **Exploratory CP-SAT scripts.** The archive retains the warm-start
   programs so that future solver experiments can be run with, e.g.:

   ```
   python n71_warm.py --time 600 --workers 4          # N = 71, from solutions_n70_rot4.json
   python n73_warm.py --time 600 --workers 4          # N = 73, from solutions_n72_rot4.json
   python n75_warm.py --time 600 --workers 4          # N = 75, from solutions_n74_rot4.json
   ```

   Each program embeds a corpus 2(N−1)-solution into [N]² (rows/columns 0..N−2
   full), hands it to CP-SAT as hints, and maximizes the point count with
   a time budget; it saves the best-so-far partial as
   `n71_deadend_b.json` / `n73_deadend.json` / `n75_deadend.json`. With
   the `--sol`/`--idx` flags you can pick a different seed configuration
   (15 for N = 71). `n71_deadend.py` is an unrestricted cold-run program.
   Solver output depends on the time budget, worker count, random seed,
   software version, and hardware.  The revised manuscript does not cite
   an N = 73 or N = 75 long-run outcome; a future claim would require the
   exact command, stdout, generated output, and environment to be archived.

3. **Exhaustive k ≤ 3 repair finds zero completions (deletion distance
   ≥ 4; Hamming distance ≥ 10 to any solution that might exist).** The
   repair machinery has pruned and naive variants, a synthetic-partial
   selftest, fresh-process verification, real wall-clock deadlines, and
   machine-readable status/counter reports:

   ```
   python n71_repair.py --selftest          # n = 12, 14, 16 synthetic partials
   python n71_repair.py --deadend n71_deadend_b.json --cap 120
   python run_n71_repairs.py --cap 0 --candidate-cap 0  # all six, exhaustive
   ```

   The `--cap` value is seconds per run and is enforced.  `--cap 0`
   disables the deadline.  The optional `--candidate-cap` is also enforced;
   its default 0 disables it.  Each child run reports exactly one of
   `FOUND`, `EXHAUSTED`, `TIMED_OUT`, `CANDIDATE_CAP`, or `INVALID_INPUT`.
   Only `EXHAUSTED` establishes a negative result.  A `TIMED_OUT` or
   `CANDIDATE_CAP` run exits nonzero, prints `NO EXHAUSTIVE CONCLUSION`, and
   must never be cited for the deletion-distance claim.

   The six-seed driver writes stdout and JSON reports under
   `results/execution_logs/n71_repair_campaign/` and an aggregate summary at
   `results/execution_logs/n71_repair_campaign_summary.json`.  The aggregate
   is `EXHAUSTED` only if all six children are exhaustive; any missing,
   capped, timed-out, or failed child makes it `INCOMPLETE`.  The complete
   campaign summary, counters, input hashes, and stdout logs used for the
   manuscript are archived with release v1.0.1.

   **Archived v1.0.1 result.** All six child reports and the aggregate report
   have status `EXHAUSTED`.  The aggregate counters are 323,663,772 matching
   iterations and 287,514,384 admissible fill attempts.  No attempt survives
   the complete local filters to the redundant final exact gate, and no
   completion is found.

## Files

Scripts:

| file | purpose |
| --- | --- |
| `n71_warm.py` / `n73_warm.py` / `n75_warm.py` | CP-SAT maximize warm-started from an embedded 2(N−1)-solution (OR-Tools) |
| `n71_deadend.py` | unrestricted cold CP-SAT run stopping at the 2N−1 dead-end |
| `n71_repair.py` | k ≤ 3 ladder repair (deletions + completions), pruned and naive, selftest, fresh-process verify |
| `run_n71_repairs.py` | audited six-seed campaign driver; writes per-seed logs/reports and refuses to aggregate incomplete runs as exhaustive |
| `secant_blocked_check.py` | frontier-corner secant-blocking check for every archived seed |
| `fast_lines.py` | line-table builder with pickle cache (verified equal to `no3in.LineTables`; ~10–20× faster at n = 65) |
| `no3in.py` | reference exact solver and line tables used by the repair code |

Data:

| file | role |
| --- | --- |
| `n71_deadend_{b,c,d2,d4,d5,d6}.json` | the six N = 71 warm-start dead-ends (140 points each; the seeds of the paper) |
| `solutions_n70_rot4.json` | 15 corpus n = 70 rot4 solutions — warm starts for N = 71 |
| `solutions_n72_rot4.json` / `solutions_n74_rot4.json` | corpus n = 72 / 74 rot4 solutions — warm starts for N = 73 / 75 |
| `base_witness_n12.json` / `base_witness_n14.json` / `asym_witness_m16.json` | known 2n-solutions used to build synthetic partials for the repair selftest |

All JSON files are derived data (computed from the pinned snapshot
corpus or from the solver runs), committed under the repository licence;
none is part of Flammenkamp's raw database.
