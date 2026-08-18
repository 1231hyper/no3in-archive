"""Move 1 / Move 1' window census (paper Section 6), fresh implementation.

A *window* is a set R of 4 rows and C of 4 columns whose induced 8
points form a 2-regular graph — type c4 (one 8-cycle) or 2c2 (two
4-cycles).  Move 1 complements the window pairing; Move 1' replaces the
window by any of the A001499(4) = 90 admissible 4x4 fills.
"""

from .geom import has_collinear_triple, window_col_masks, canonical

# -------------------------------------------------------------- fills ----

def _refill_matrices():
    """All 90 four-by-four 0-1 matrices with row and column sums 2,
    as tuples of four (col0, col1) row pairs."""
    pairs = [(a, b) for a in range(4) for b in range(a + 1, 4)]
    mats = []
    for r0 in pairs:
        for r1 in pairs:
            for r2 in pairs:
                for r3 in pairs:
                    cs = [0] * 4
                    for (x, y) in (r0, r1, r2, r3):
                        cs[x] += 1
                        cs[y] += 1
                    if all(v == 2 for v in cs):
                        mats.append((r0, r1, r2, r3))
    assert len(mats) == 90
    return mats


REFILLS = _refill_matrices()

# -------------------------------------------------------------- utils ---

def window_cols_list(cmask):
    """Column indices (0..n-1) of the 4-bit window column mask."""
    out = []
    c = 0
    while cmask:
        if cmask & 1:
            out.append(c)
        cmask >>= 1
        c += 1
    return out


def window_type(pts, R, C):
    """'c4' (single 8-cycle) or '2c2' (two 4-cycles)."""
    Cset = frozenset(C)
    per_row = {}
    for r, c in pts:
        if r in R and c in Cset:
            per_row.setdefault(r, []).append(c)
    adj = {}
    rows = list(R)
    for i in range(4):
        for j in range(i + 1, 4):
            if set(per_row[rows[i]]) & set(per_row[rows[j]]):
                adj.setdefault(rows[i], set()).add(rows[j])
                adj.setdefault(rows[j], set()).add(rows[i])
    seen = {rows[0]}
    stack = [rows[0]]
    while stack:
        x = stack.pop()
        for y in adj.get(x, ()):
            if y not in seen:
                seen.add(y)
                stack.append(y)
    return 'c4' if len(seen) == 4 else '2c2'


def _replace_window(pts, R, Cset, fill_rows):
    """Solution with the window cells replaced by the given row fills.

    Fill entries are *positions* within the window's sorted column list
    (0..3), not absolute column indices; they are relabeled here.
    """
    cols = sorted(Cset)
    keep = []
    for r, c in pts:
        if r in R and c in Cset:
            continue
        keep.append((r, c))
    out = list(keep)
    for r, fill in zip(R, fill_rows):
        for i in fill:
            out.append((r, cols[i]))
    return tuple(sorted(out))


# --------------------------------------------------------- window scan --

def scan_windows(pts, n):
    """All (R, C) windows of a solution, C as a 4-bit column mask."""
    per_row = {}
    for r, c in pts:
        per_row.setdefault(r, 0)
        per_row[r] |= 1 << c
    windows = []
    for cmask in window_col_masks(n):
        fit = [r for r in range(n) if per_row[r] & ~cmask == 0]
        m = len(fit)
        if m >= 4:
            for i in range(m):
                for j in range(i + 1, m):
                    for k in range(j + 1, m):
                        for l in range(k + 1, m):
                            windows.append(((fit[i], fit[j], fit[k], fit[l]), cmask))
    return windows


def count_windows_pairs(pts, n):
    """Window count via column-pair grouping (fast path for large n).

    The four window rows' column pairs must form a 2-regular multigraph
    on exactly four distinct columns: either a 4-cycle (c4) or two
    double edges (2c2).  Returns the count.
    """
    per_row = {}
    for r, c in pts:
        per_row.setdefault(r, []).append(c)
    rows_by_pair = {}
    for r, cs in per_row.items():
        key = tuple(sorted(cs))
        rows_by_pair.setdefault(key, []).append(r)
    pairs = [k for k in rows_by_pair if k[0] != k[1]]
    total = 0
    m = len(pairs)
    # double edges: two disjoint pairs used twice
    for i in range(m):
        a, b = pairs[i]
        for j in range(i + 1, m):
            c, d = pairs[j]
            if len({a, b, c, d}) == 4:
                total += (len(rows_by_pair[(a, b)]) *
                          (len(rows_by_pair[(a, b)]) - 1) // 2 *
                          len(rows_by_pair[(c, d)]) *
                          (len(rows_by_pair[(c, d)]) - 1) // 2)
    # 4-cycles a-b-c-d-a through each edge
    adj = {}
    for (a, b) in pairs:
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    for a, b in pairs:
        ca = len(rows_by_pair[(a, b)])
        for c in adj.get(b, ()):
            if c == a:
                continue
            for d in adj.get(c, ()):
                if d in (a, b):
                    continue
                if (d, a) in rows_by_pair or (a, d) in rows_by_pair:
                    total += (ca * len(rows_by_pair[tuple(sorted((b, c)))]) *
                              len(rows_by_pair[tuple(sorted((c, d)))]) *
                              len(rows_by_pair[tuple(sorted((d, a)))]))
    return total


def find_windows_pairs(pts, n):
    """All windows (R tuple, C 4-bit mask) via the pair method."""
    per_row = {}
    for r, c in pts:
        per_row.setdefault(r, []).append(c)
    rows_by_pair = {}
    for r, cs in per_row.items():
        rows_by_pair.setdefault(tuple(sorted(cs)), []).append(r)
    windows = []
    pkeys = [k for k in rows_by_pair]
    m = len(pkeys)
    for i in range(m):
        a, b = pkeys[i]
        for j in range(i + 1, m):
            c, d = pkeys[j]
            if len({a, b, c, d}) == 4:
                cmask = (1 << a) | (1 << b) | (1 << c) | (1 << d)
                ra, rb = rows_by_pair[(a, b)], rows_by_pair[(c, d)]
                for r1 in ra:
                    for r2 in ra:
                        if r2 <= r1:
                            continue
                        for r3 in rb:
                            for r4 in rb:
                                if r4 <= r3:
                                    continue
                                windows.append(((r1, r2, r3, r4), cmask))
    adj = {}
    for k in pkeys:
        for x in k:
            adj.setdefault(x, []).append(k)
    for (a, b) in pkeys:
        ca = rows_by_pair[(a, b)]
        for kc in adj.get(b, ()):
            if kc == (a, b):
                continue
            c = kc[0] if kc[0] != b else kc[1]
            for kd in adj.get(c, ()):
                if kd == kc:
                    continue
                d = kd[0] if kd[0] != c else kd[1]
                if d in (a, b):
                    continue
                if (d, a) in rows_by_pair or (a, d) in rows_by_pair:
                    ka = tuple(sorted((a, b)))
                    kb = tuple(sorted((b, c)))
                    kc2 = tuple(sorted((c, d)))
                    kd2 = tuple(sorted((d, a)))
                    cmask = (1 << a) | (1 << b) | (1 << c) | (1 << d)
                    for r1 in rows_by_pair[ka]:
                        for r2 in rows_by_pair[kb]:
                            for r3 in rows_by_pair[kc2]:
                                for r4 in rows_by_pair[kd2]:
                                    windows.append(((r1, r2, r3, r4), cmask))
    return windows


# ------------------------------------------------------------ Move 1 ----

def move1_flip(pts, R, cmask):
    """Complement the window pairing; returns the new point set."""
    C = window_cols_list(cmask)
    Cset = frozenset(C)
    per_row = {}
    for r, c in pts:
        if r in R and c in Cset:
            per_row.setdefault(r, []).append(c)
    out = [p for p in pts if not (p[0] in R and p[1] in Cset)]
    for r in R:
        used = set(per_row[r])
        for c in C:
            if c not in used:
                out.append((r, c))
    return tuple(sorted(out))


def window_stats(pts, n):
    """Per-window Move 1 and Move 1' statistics.

    Returns (windows, move1_valid, move1_same, move1_types,
             v_list, refill_edges) where v_list has one entry per window
    (the window's valid-refill count including the identity, 1..90) and
    refill_edges is a list of one-char codes per non-identity valid
    refill: 'W' within class, 'X' cross class.
    """
    windows = scan_windows(pts, n)
    move1_valid = []
    move1_same = []
    move1_types = []
    v_list = []
    edges = []
    orig_canon = canonical(pts, n)
    for (R, cmask) in windows:
        t = window_type(pts, R, window_cols_list(cmask))
        move1_types.append(t)
        flipped = move1_flip(pts, R, cmask)
        if not has_collinear_triple(flipped):
            move1_valid.append(1)
            fc = canonical(flipped, n)
            move1_same.append(fc == orig_canon)
        else:
            move1_valid.append(0)
            move1_same.append(None)
        Cset = frozenset(window_cols_list(cmask))
        cols = sorted(Cset)
        orig_pattern = tuple(
            tuple(sorted(cols.index(c) for (rr, c) in pts
                         if rr == r and c in Cset))
            for r in R)
        vw = 0
        for fill in REFILLS:
            newpts = _replace_window(pts, R, Cset, fill)
            if not has_collinear_triple(newpts):
                vw += 1
                if fill != orig_pattern:  # non-identity refill
                    fc = canonical(newpts, n)
                    edges.append('W' if fc == orig_canon else 'X')
        v_list.append(vw)
    return (windows, move1_valid, move1_same, move1_types, v_list, edges)
