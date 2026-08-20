# Changelog

## 1.1.0 - 2026-08-20

- Re-pinned the snapshot to Flammenkamp's 2026-08-19 revision
  (431,004 lines, 23,833,984 bytes, SHA-256
  `557645ec...bd9023`); updated `data/snapshot_manifest.txt` and
  `data/download_snapshot.py` accordingly.
- Recomputed the affected derived tables against the new snapshot: the
  scan aggregates at n = 33, 36, 37, 39 (13 new classes: ten rot2 by
  Kudriashov) and the corpus statistics (962 classes / 3,628 labeled,
  rct4 spread now 833@57, 2@59, 1@61..67, 2@69, 1@71, 1@73; the Heule
  record classes at n = 71, 73).
- Updated the independent-verifier expected values (C01 totals,
  C09/C10/C11 corpus claims) and reran the full verification against the
  new snapshot.
- Manuscript v1.1.0: f(71) = 142 and f(73) = 146 now established
  (Heule, 17/19 Aug 2026); the N = 71 repair-seed paragraph reports the
  exact distances to the actual solutions (deletion 132-138, Hamming
  266-278); only f(75) remains open.
- Updated CFF/Zenodo metadata (version 1.1.0, ORCID, institutional
  email) and the README claim list.

## 1.0.1 - 2026-08-18

- Enforced LF output and removed machine-specific paths and runtime fields
  from deterministic census artifacts.
- Corrected the arbitrary-refill totals at n=6 and n=7.
- Corrected the n=15--17 near-neighbor graphs and recomputed the full n=57
  corpus including six rot2 and one iden class.
- Added the Section 8 solver-study code and seed data.
- Replaced the repair search's ineffective wall-clock option and silent
  4,000-candidate truncation with explicit FOUND, EXHAUSTED, TIMED_OUT,
  CANDIDATE_CAP, and INVALID_INPUT outcomes.
- Added an audited six-seed campaign driver.  The archived uncapped run is
  EXHAUSTED for every seed: 323,663,772 matching iterations and 287,514,384
  admissible fill attempts in aggregate, with no completion.
- Pinned the optional solver dependency to OR-Tools 9.15.6755.
- Added Python 3.9/3.12 quick checks and citation-metadata validation in
  GitHub Actions.
- Updated CFF and Zenodo metadata for archive version 1.0.1 and the persistent
  concept DOI 10.5281/zenodo.21997173.
- Updated the author affiliation to the School of Artificial Intelligence,
  Nanjing University.
- Limited the N=73 and N=75 manuscript claims to the directly verified
  frontier-secant obstruction; no unarchived long-run CP-SAT or local-repair
  exhaustion is claimed at those sizes.
