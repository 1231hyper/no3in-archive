# Release checklist for v1.0.1

Run these checks from a clean clone or the GitHub release-candidate ZIP.  Do
not describe a capped repair run as exhaustive: only an `EXHAUSTED` status for
all six seeds supports the Section 8 deletion-distance statement.

1. Confirm that `CITATION.cff`, `.zenodo.json`, `README.md`, and
   `src/independent_verifier/run.py` all identify version `1.0.1`.
2. Validate citation metadata:

   ```bash
   cffconvert --validate
   python -m json.tool .zenodo.json >/dev/null
   ```

3. Run the standard-library quick checks:

   ```bash
   python -m compileall -q src scripts solver_study
   python scripts/verify_hashes.py --check
   python solver_study/secant_blocked_check.py
   python solver_study/n71_repair.py --selftest
   ```

4. Run all six N=71 repairs without a deadline or candidate cap:

   ```bash
   python solver_study/run_n71_repairs.py --cap 0 --candidate-cap 0
   ```

   Check that `results/execution_logs/n71_repair_campaign_summary.json`
   reports `"overall_status": "EXHAUSTED"`.  Commit the campaign summary,
   child reports, and stdout logs used by the paper, then add their hashes to
   the archive manifest.  If any status is `TIMED_OUT`, `CANDIDATE_CAP`,
   `MISSING_REPORT`, or `INCOMPLETE`, the `[Local-Exh]` claim must not be made.
5. Check that the manuscript limits the N=73 and N=75 claims to the direct
   frontier-secant calculation.  It must not claim a reproduced long-run
   CP-SAT stall or a repair exhaustion at those target sizes unless the exact
   commands, stdout, outputs, software versions, worker counts, random seeds,
   and time budgets are added to a later archive release.
6. Rebuild the manuscript and search it for superseded Hamming/refill values.
7. Regenerate the hash manifest and immediately check it:

   ```bash
   python scripts/verify_hashes.py --gen
   python scripts/verify_hashes.py --check
   ```

8. Commit, create Git tag and GitHub release `v1.0.1`, download its ZIP, and
   repeat steps 2--3 on that ZIP.
9. Publish the GitHub release through the existing Zenodo integration as a
   new version of concept DOI `10.5281/zenodo.21997173`.  Record the new
   version-specific DOI in the manuscript's data-availability statement.
