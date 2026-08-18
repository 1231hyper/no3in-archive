"""Geometric and group-theoretic primitives (vendored from
r7_census_laws.py; the corner-secant helpers are extended to all four
orbit corners of (n,n) for the corner-barrier tables).

Conventions: cells are (row, col) in 0..n-1; D4 transform indices are
    0 id, 1 R90, 2 R180, 3 R270, 4 H (horizontal axis flip),
    5 V (vertical axis flip), 6 D1 (main diagonal), 7 D2 (anti diagonal).
"""

import math
from collections import Counter, defaultdict

# ------------------------------------------------------------ D4 ---------

def d4_transforms(pts, n):
    """All 8 images of pts under the D4 of the [n]^2 square."""
    out = []
    for f in range(8):
        img = set()
        for (r, c) in pts:
            if f == 0:   img.add((r, c))
            elif f == 1: img.add((c, n - 1 - r))          # R90
            elif f == 2: img.add((n - 1 - r, n - 1 - c))  # R180
            elif f == 3: img.add((n - 1 - c, r))          # R270
            elif f == 4: img.add((r, n - 1 - c))          # H
            elif f == 5: img.add((n - 1 - r, c))          # V
            elif f == 6: img.add((c, r))                  # D1
            else:        img.add((n - 1 - c, n - 1 - r))  # D2
        out.append(frozenset(img))
    return out


def stabilizer_type(pts, n):
    """(orbit_size, tuple of transform indices fixing pts)."""
    imgs = d4_transforms(pts, n)
    fixing = tuple(f for f in range(8) if imgs[f] == pts)
    return len(set(imgs)), fixing


# --------------------------------------------- bipartite cycle spectrum ---

def cycle_spectrum(pts, n):
    """Sorted half-lengths of the row<->column 2-regular bipartite graph
    (cycle structure of the relative permutation pi = sigma^-1 tau)."""
    rows = defaultdict(list)
    cols = defaultdict(list)
    for (r, c) in pts:
        rows[r].append(c)
        cols[c].append(r)
    seen = set()
    lengths = []
    for r in range(n):
        if r in seen:
            continue
        stack = [r]
        seen.add(r)
        cnt = 0
        while stack:
            x = stack.pop()
            cnt += 1
            for c in rows[x]:
                for r2 in cols[c]:
                    if r2 not in seen:
                        seen.add(r2)
                        stack.append(r2)
        lengths.append(cnt)
    return tuple(sorted(lengths))


# ------------------------------------------------- corner-secant barrier ---

def corner_secants(pts, n):
    """Primitive directions of points of pts toward the corner (n, n) of
    the [n+1]^2 embedding; returns dict direction -> multiplicity."""
    groups = {}
    for (r, c) in pts:
        dr, dc = r - n, c - n
        g = math.gcd(abs(dr), abs(dc))
        dr //= g
        dc //= g
        if dr < 0 or (dr == 0 and dc < 0):
            dr, dc = -dr, -dc
        groups[(dr, dc)] = groups.get((dr, dc), 0) + 1
    return groups


def corner_secants4(pts, n):
    """Per-corner primitive-direction multiplicities toward the four
    exterior corners of the [n+1]^2 embedding — (n,n), (-1,n), (-1,-1),
    (n,-1), the D4 orbit of the frontier corner (n,n).  Returns four
    dicts in that order."""
    corners = ((n, n), (-1, n), (-1, -1), (n, -1))
    out = []
    for (ax, ay) in corners:
        groups = {}
        for (r, c) in pts:
            dr, dc = r - ax, c - ay
            g = math.gcd(abs(dr), abs(dc))
            dr //= g
            dc //= g
            if dr < 0 or (dr == 0 and dc < 0):
                dr, dc = -dr, -dc
            groups[(dr, dc)] = groups.get((dr, dc), 0) + 1
        out.append(groups)
    return out


def secant_stats(pts, n):
    """(number of 2-point secants through (n, n), blocked?)."""
    groups = corner_secants(pts, n)
    nsec = sum(1 for v in groups.values() if v >= 2)
    return nsec, (nsec >= 1)


# -------------------------------------------------- direction multiplicities

def dir_mult(pts):
    """m_S(v): multiplicity of each primitive direction over point pairs."""
    cnt = Counter()
    P = list(pts)
    for i in range(len(P)):
        r1, c1 = P[i]
        for j in range(i + 1, len(P)):
            r2, c2 = P[j]
            dr, dc = r2 - r1, c2 - c1
            g = math.gcd(abs(dr), abs(dc))
            dr //= g
            dc //= g
            if dr < 0 or (dr == 0 and dc < 0):
                dr, dc = -dr, -dc
            cnt[(dr, dc)] += 1
    return cnt


# ------------------------------------------------------------ diagonal laws

def diag_laws(pts, n):
    """Diagonal occupancy laws L1/L2/L3 (paper Section 8)."""
    occ = {
        'D+m':  sum(1 for r, c in pts if r - c == 0),
        'D-m':  sum(1 for r, c in pts if r + c == n - 1),
        'D+p1': sum(1 for r, c in pts if r - c == 1),
        'D+m1': sum(1 for r, c in pts if r - c == -1),
        'D-p1': sum(1 for r, c in pts if r + c == n - 2),
        'D-m1': sum(1 for r, c in pts if r + c == n),
    }
    L1 = occ['D+m'] in (0, 2) and occ['D-m'] in (0, 2) \
        and all(occ[k] <= 2 for k in ('D+p1', 'D+m1', 'D-p1', 'D-m1'))
    L2 = (occ['D+m'], occ['D-m']) == (2, 0) if n % 2 == 1 \
        else (occ['D+m'], occ['D-m']) in ((2, 2), (0, 0))
    L3 = len({occ['D+p1'], occ['D+m1'], occ['D-p1'], occ['D-m1']}) == 1
    return L1, L2, L3, occ


# -------------------------------------------- reference tables (OEIS) -----

# A000755 (labeled no-three-in-line, D4 classes on the n x n torus? no:
# A000755 = number of solutions for n x n grid, n = 2..19)
A755 = {2: 1, 3: 2, 4: 11, 5: 32, 6: 50, 7: 132, 8: 380, 9: 368,
        10: 1135, 11: 1120, 12: 4348, 13: 3622, 14: 10568, 15: 30634,
        16: 46304, 17: 55576, 18: 152210, 19: 258176,
        20: 941580}   # n = 20 continues the sequence (A000755(20))
