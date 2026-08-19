# solver_study/ — CP-SAT observations and k ≤ 3 repair at N = 71, 73, 75

Materials for **paper Section 8** ("Embedded-solution repair barriers at
N = 71, 73, 75"), the `[Solver]` claim. The claims of that section are
*solver observations*, not certified theorems: the archive's independent
verifier does not cover them. Everything here is the actual code and data
used for the section, made self-contained (no absolute paths, no
external files).

**Dependencies.** The three `*_warm.py` scripts and `n71_deadend.py`
require Google OR-Tools (`pip install ortools`). The repair machinery,
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

2. **CP-SAT maximization warm-started from an embedded 2(N−1)-solution
   stalls at 2N−2 points.** Reproduce with, e.g.:

   ```
   python n71_warm.py --time 600 --workers 4          # N = 71, from solutions_n70_rot4.json
   python n73_warm.py --time 600 --workers 4          # N = 73, from solutions_n72_rot4.json
   python n75_warm.py --time 600 --workers 4          # N = 75, from solutions_n74_rot4.json
   ```

   Each embeds a corpus 2(N−1)-solution into [N]² (rows/columns 0..N−2
   full), hands it to CP-SAT as hints, and maximizes the point count with
   a time budget; it saves the best-so-far partial as
   `n71_deadend_b.json` / `n73_deadend.json` / `n75_deadend.json`. With
   the `--sol`/`--idx` flags you can pick a different seed configuration
   (15 for N = 71). `n71_deadend.py` is the unrestricted cold run (no
   warm start) that stops at the 2N−1 = 141 dead-end. The paper's runs
   used 2–8 h budgets; short budgets show the stall, not the fix.

3. **Exhaustive k ≤ 3 repair finds zero completions (deletion distance
   ≥ 4; Hamming distance ≥ 10 to any solution that might exist).** The
   repair machinery, with pruned and naive variants, a synthetic-partial
   selftest, and fresh-process verification:

   ```
   python n71_repair.py --selftest          # n = 12, 14, 16 synthetic partials
   python n71_repair.py --deadend n71_deadend_b.json --cap 120
   ```

   The paper's exhaustive count (~47.7 M candidates over all six seeds)
   came from a long campaign run; the archived script reproduces the
   machinery with a wall-clock cap and a self-test that pins the
   pruned/naive agreement (both succeed on the synthetic partials; a
   `MISMATCH` line means the pruning is broken). A `k<=3 REPAIR FAILED`
   line for an archived dead-end is the expected outcome — it is the
   content of the claim.

## Files

Scripts:

| file | purpose |
| --- | --- |
| `n71_warm.py` / `n73_warm.py` / `n75_warm.py` | CP-SAT maximize warm-started from an embedded 2(N−1)-solution (OR-Tools) |
| `n71_deadend.py` | unrestricted cold CP-SAT run stopping at the 2N−1 dead-end |
| `n71_repair.py` | k ≤ 3 ladder repair (deletions + completions), pruned and naive, selftest, fresh-process verify |
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
