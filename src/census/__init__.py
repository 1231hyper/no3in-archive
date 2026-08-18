"""Paper-side census: derived-table writer.

Streams the pinned snapshot once with the primary (vendored) parser and
writes the machine-readable census tables under data/derived_tables/.
The independent verifier (src/independent_verifier/) is the second,
code-disjoint implementation that cross-checks these numbers.

    python -m src.census.tables --snapshot data/raw/all_known_solutions.txt

Tables written (deterministic content, no timestamps):
    snapshot_stats.json   line counts, per-n counts, SHA-256 of the file
    census_n2_20.csv      per-n class/labeled/marker census, n = 2..20
    n20_marker_census.csv marker decomposition at n = 20
    l_values.csv          L(n), min spectrum, minimizer counts, n = 2..20
    n3_series.csv         labeled max-spectrum <= 3 counts, n = 2..20
    corner_barrier.csv    corner-barrier stats, n = 8..20
    corner_small_n.csv    open-share at n = 2..7
    scan_min_spectra.csv  scan minima 21..57 (incl. the n = 57 corpus section)
    asym_21_56.csv        iden-marked class counts, n = 21..56
    corpus_stats.json     full corpus table, n = 57..76
"""
