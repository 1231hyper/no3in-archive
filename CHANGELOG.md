# Changelog

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
