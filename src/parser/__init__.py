"""Primary (paper-side) snapshot parser.

Vendored from the research scripts that produced the paper's numbers
(round-7 full-population census, _research_tmp/r7_census_laws.py),
repackaged as modules.  The independent verifier
(src/independent_verifier/) implements the same format specification and
geometry from scratch with no shared code; the two code paths are
intentionally disjoint and cross-check each other.

    src/parser/decode.py   database line decoder (90-char column alphabet)
    src/parser/geom.py     D4 transforms, stabilizer, cycle spectra,
                           corner secants, direction multiplicities,
                           diagonal laws, A000755 reference table
"""
