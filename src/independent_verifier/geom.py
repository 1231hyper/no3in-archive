"""Geometric and group-theoretic primitives, fresh implementation.

All algorithms here are written from the definitions in the paper
(Sections 2.1, 2.2, 5, 7), independently of src/parser/.

Conventions
-----------
- Cells are (row, column), both in 0..n-1.
- D4 acts on the [n]^2 square; the group is generated below by the
  quarter-turn R90: (r,c) -> (c, n-1-r) and the horizontal-axis
  reflection H: (r,c) -> (r, n-1-c).
- The "corner-secant barrier" uses the four exterior points
  {(n,n), (-1,n), (-1,-1), (n,-1)} — the orbit of the frontier corner
  (n,n) of the embedding in [n+1]^2 under the D4 of the n-square.
"""

from math import gcd
from functools import reduce

# ---------------------------------------------------------------- D4 ---

def _compose(f, g):
    return lambda p: f(g(p))


def d4_transforms(n):
    """The 8 elements of D4 acting on (row, col) coordinates.

    Index convention (matches the paper / primary parser):
      0 id, 1 R90, 2 R180, 3 R270, 4 H, 5 V, 6 D1, 7 D2
    where H(r,c) = (r, n-1-c), V(r,c) = (n-1-r, c),
    D1(r,c) = (c, r), D2(r,c) = (n-1-c, n-1-r).
    """
    ident = lambda p: p
    r90 = lambda p: (p[1], n - 1 - p[0])
    hflip = lambda p: (p[0], n - 1 - p[1])
    out = []
    cur = ident
    for _ in range(4):            # rotations R0, R90, R180, R270
        out.append(cur)
        cur = _compose(r90, cur)
    for rot_idx in (0, 2, 3, 1):  # reflections: H, V, D1, D2
        out.append(_compose(out[rot_idx], hflip))
    return out


def images(pts, transforms):
    return [frozenset(f(p) for p in pts) for f in transforms]


def stabilizer(pts, n):
    """(orbit_size, tuple of transform indices fixing pts)."""
    tr = d4_transforms(n)
    imgs = images(pts, tr)
    fp = frozenset(pts)
    fixing = tuple(i for i in range(8) if imgs[i] == fp)
    return len(set(imgs)), fixing


def canonical(pts, n):
    """D4-canonical form: lexicographically smallest image."""
    tr = d4_transforms(n)
    best = None
    for f in tr:
        img = tuple(sorted(f(p) for p in pts))
        if best is None or img < best:
            best = img
    return best


# ------------------------------------------------------- cycle spectra ---

def cycle_spectrum(pts, n):
    """Sorted half-lengths of the 2-regular bipartite graph rows<->cols.

    Equivalently the cycle lengths of the relative permutation
    pi = sigma^-1 tau of the two row/column perfect matchings
    (Section 2.1 of the paper).  A component on k rows and k columns is
    a C_{2k} of the bipartite graph; the half-length is k.
    """
    rows = {}
    cols = {}
    for r, c in pts:
        rows.setdefault(r, []).append(c)
        cols.setdefault(c, []).append(r)
    seen_rows = set()
    half = []
    for start in range(n):
        if start in seen_rows:
            continue
        stack = [start]
        seen_rows.add(start)
        size = 0
        while stack:
            r = stack.pop()
            size += 1
            for c in rows[r]:
                for r2 in cols[c]:
                    if r2 not in seen_rows:
                        seen_rows.add(r2)
                        stack.append(r2)
        half.append(size)
    return tuple(sorted(half))


# ---------------------------------------------------- collinearity test ---

def _canon_dir(dr, dc):
    """Normalized direction, identified with its negative."""
    g = gcd(abs(dr), abs(dc))
    dr //= g
    dc //= g
    if dr < 0 or (dr == 0 and dc < 0):
        dr, dc = -dr, -dc
    return (dr, dc)


def direction_counts(pts):
    """m_S(v): pairs of points on common v-lines, per primitive v.

    With no collinear triples this equals the number of 2-point v-lines
    (Section 5, Theorem C).
    """
    P = sorted(pts)
    cnt = {}
    for i in range(len(P)):
        r1, c1 = P[i]
        for j in range(i + 1, len(P)):
            r2, c2 = P[j]
            key = _canon_dir(r2 - r1, c2 - c1)
            cnt[key] = cnt.get(key, 0) + 1
    return cnt


def has_collinear_triple(pts):
    """True iff three points of pts are collinear.

    Per-anchor test: for each point p, two other points with the same
    primitive direction from p are collinear with p.  (Pair-per-direction
    counts — direction_counts — are NOT a valid triple test: the two
    points of one row share the axis direction without a triple.)
    """
    P = list(pts)
    for i, (r1, c1) in enumerate(P):
        seen = set()
        for j in range(len(P)):
            if j == i:
                continue
            r2, c2 = P[j]
            key = _canon_dir(r2 - r1, c2 - c1)
            if key in seen:
                return True
            seen.add(key)
    return False


def is_valid_solution(pts, n):
    """Full validity: 2 per row/column, in-grid, and no collinear triple."""
    if len(pts) != 2 * n:
        return False
    rc = [0] * n
    cc = [0] * n
    for r, c in pts:
        if not (0 <= r < n and 0 <= c < n):
            return False
        rc[r] += 1
        cc[c] += 1
    if any(x != 2 for x in rc) or any(x != 2 for x in cc):
        return False
    return not has_collinear_triple(pts)


# --------------------------------------------------- corner secants ------

def corner_positions(n):
    """The four exterior corners of the [n+1]^2 embedding — the D4 orbit
    of the frontier corner (n, n)."""
    return ((n, n), (-1, n), (-1, -1), (n, -1))


def corner_secant_counts(pts, n):
    """Per-corner secant counts for the four orbit corners of (n,n).

    For exterior corner (a, b), the secants are the primitive directions
    (toward the grid) with 2+ points of pts on the ray.  Returns a list
    of four integers in the order of corner_positions(n).
    """
    out = []
    for ax, ay in corner_positions(n):
        groups = {}
        for r, c in pts:
            key = _canon_dir(r - ax, c - ay)
            groups[key] = groups.get(key, 0) + 1
        out.append(sum(1 for v in groups.values() if v >= 2))
    return out


# ------------------------------------------------------------- windows ----

def window_col_masks(n):
    """All C(n,4) column 4-subsets as bit masks."""
    masks = []
    for a in range(n):
        for b in range(a + 1, n):
            for c in range(b + 1, n):
                for d in range(c + 1, n):
                    masks.append((1 << a) | (1 << b) | (1 << c) | (1 << d))
    return masks


def windows_of(pts, n):
    """All (row_4subset, col_4subset) windows: 8 points, 2 per row/col.

    A window is a set R of 4 rows and C of 4 columns whose induced
    8 points are 2-regular.  Since every row of the solution carries
    exactly 2 points, this holds iff the 8 points of the 4 rows lie in
    exactly 4 distinct columns (each column then receives exactly 2).
    Enumerated via column 4-subsets C: rows with both columns in C;
    every 4-subset of those rows gives a window.
    """
    rowmask = []
    for r in range(n):
        m = 0
        for rr, c in pts:
            if rr == r:
                m |= 1 << c
        rowmask.append(m)
    windows = []
    for cmask in window_col_masks(n):
        fit = [r for r in range(n) if rowmask[r] & ~cmask == 0]
        if len(fit) >= 4:
            for i in range(len(fit)):
                for j in range(i + 1, len(fit)):
                    for k in range(j + 1, len(fit)):
                        for l in range(k + 1, len(fit)):
                            windows.append(((fit[i], fit[j], fit[k], fit[l]), cmask))
    return windows
