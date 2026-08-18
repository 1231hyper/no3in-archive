"""Independent verifier for the paper's [DB-Exh] headline claims.

This package deliberately shares NO code with src/parser/ or src/census/.
Every algorithm here (decoder, D4 machinery, cycle spectra, corner
statistics, window census, near-neighbor graph) is implemented from the
published format specification and from the paper's definitions, so a
bug in the primary pipeline cannot be reproduced by the verifier.

Run:

    python -m src.independent_verifier.run --snapshot data/raw/all_known_solutions.txt
"""
