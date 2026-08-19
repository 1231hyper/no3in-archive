# no3in.py — exact solver + experiments for the no-three-in-line problem (Dudeney 1917)
# Supports the research monograph: verifies f(n)=2n for small n, reproduces OEIS counts,
# tests constructions (Erdos parabola, HJSW-type quadrants, torus, block-structured variants).
import itertools, time, sys
from math import gcd, log

# ---------------------------------------------------------------- line enumeration
def gen_lines(n, wrap_mod=None):
    """Maximal collinear sets with >=3 cells of the n x n grid, as bitmasks.
    If wrap_mod=(m,n) is given, lines of the torus Z_m x Z_n are generated instead."""
    m, nn = (wrap_mod if wrap_mod else (n, n))
    masks = set()
    cell_lines = [[] for _ in range(m * nn)]
    dirs = []
    if wrap_mod:
        # torus: all direction vectors d != 0 mod (m,n); line = orbit of p under +d
        for a in range(m):
            for b in range(nn):
                if (a, b) == (0, 0):
                    continue
                dirs.append((a, b))
    else:
        for a in range(n):
            for b in range(n):
                if a == 0 and b == 0:
                    continue
                if gcd(a, b) != 1:
                    continue
                dirs.append((a, b))
                if a > 0 and b > 0:
                    dirs.append((a, -b))
    line_cells = []
    for (a, b) in dirs:
        for x in range(m):
            for y in range(nn):
                if wrap_mod:
                    # each coset generated from each point; dedupe by mask
                    pts = []
                    cx, cy = x, y
                    while True:
                        pts.append((cx, cy))
                        cx = (cx + a) % m
                        cy = (cy + b) % nn
                        if (cx, cy) == (x, y):
                            break
                else:
                    px, py = x - a, y - b
                    if 0 <= px < n and 0 <= py < n:
                        continue  # not the canonical first point
                    pts = []
                    cx, cy = x, y
                    while 0 <= cx < n and 0 <= cy < n:
                        pts.append((cx, cy))
                        cx += a
                        cy += b
                if len(pts) >= 3:
                    mask = 0
                    for (px, py) in pts:
                        mask |= 1 << (px * nn + py)
                    masks.add(mask)
    for mask in masks:
        cells = []
        k = 0
        t = mask
        while t:
            if t & 1:
                cells.append((k // nn, k % nn))
            t >>= 1
            k += 1
        line_cells.append(tuple(cells))
    return line_cells, cell_lines

def no3_valid(points, n):
    """Direct O(k^3) check that a point set has no 3 collinear."""
    pts = list(points)
    k = len(pts)
    for i in range(k):
        x1, y1 = pts[i]
        for j in range(i + 1, k):
            x2, y2 = pts[j]
            for l in range(j + 1, k):
                x3, y3 = pts[l]
                if (x2 - x1) * (y3 - y1) == (x3 - x1) * (y2 - y1):
                    return (pts[i], pts[j], pts[l])
    return None

# ---------------------------------------------------------------- backtracking core
class LineTables:
    """Precomputed line info for fast backtracking."""
    def __init__(self, n, wrap_mod=None):
        self.n = n
        m, nn = (wrap_mod if wrap_mod else (n, n))
        self.m, self.nn = m, nn
        lines, _ = gen_lines(n, wrap_mod)
        self.lines = lines
        self.L = len(lines)
        self.cell_lines = [[] for _ in range(m * nn)]
        for li, cells in enumerate(lines):
            for (r, c) in cells:
                self.cell_lines[r * nn + c].append(li)
        # line id -> dict row -> col (each non-horizontal line has <=1 cell per row)
        self.line_rowcol = []
        for li, cells in enumerate(lines):
            d = {}
            for (r, c) in cells:
                d.setdefault(r, []).append(c)
            self.line_rowcol.append(d)

def find_solution(n, wrap_mod=None, per_row=2, blocks=None, limit_rows=None,
                  per_row_list=None):
    """Find ONE configuration with per_row points in each of `n` groups
    (rows of the grid, or 2x2 blocks if blocks=True), no 3 in line.
    per_row_list: optional per-group point counts (len = #groups).
    Returns list of (r,c) or None."""
    t0 = time.time()
    if blocks:
        tab = LineTables(2 * n)          # lines of the 2n x 2n grid
    else:
        tab = LineTables(n, wrap_mod)
    if blocks:
        # groups = 2x2 blocks of the 2n x 2n grid
        groups = []
        for bi in range(n):
            for bj in range(n):
                groups.append([(2 * bi, 2 * bj), (2 * bi, 2 * bj + 1),
                               (2 * bi + 1, 2 * bj), (2 * bi + 1, 2 * bj + 1)])
        nn = 2 * n
        m = 2 * n
    elif wrap_mod:
        m, nn = wrap_mod
        groups = [[(r, c) for c in range(nn)] for r in range(m)]
    else:
        m = nn = n
        groups = [[(r, c) for c in range(n)] for r in range(n)]
    if per_row_list:
        per = list(per_row_list) + [0] * (len(groups) - len(per_row_list))
    else:
        per = [per_row] * len(groups)
    ng = len(groups)
    ncell = m * nn
    idx = lambda r, c: r * nn + c
    count = [0] * tab.L
    chosen = []
    node_count = [0]

    def line_cells_of(li, r):
        return tab.line_rowcol[li].get(r, ())

    def rec(gi):
        node_count[0] += 1
        if gi == ng:
            return True
        if per[gi] == 0:
            return rec(gi + 1)
        cells = groups[gi]
        # candidate pairs (respecting current forbidden columns)
        free = []
        for (r, c) in cells:
            if forbidden.get((r, c), False):
                continue
            free.append((r, c))
        if len(free) < per[gi]:
            return False
        # heuristic: try pairs that complete few lines first (soft)
        cand = list(itertools.combinations(free, per[gi]))
        if gi < 3:  # keep early choices in natural order
            pass
        else:
            def key(pr):
                s = 0
                for (r, c) in pr:
                    for li in tab.cell_lines[idx(r, c)]:
                        if count[li] == 1:
                            s += 1
                return s
            cand.sort(key=key)
        for pr in cand:
            # place
            bad = False
            for (r, c) in pr:
                for li in tab.cell_lines[idx(r, c)]:
                    count[li] += 1
                    if count[li] >= 3:
                        bad = True
            if bad:
                for (r, c) in pr:
                    for li in tab.cell_lines[idx(r, c)]:
                        count[li] -= 1
                continue
            for (r, c) in pr:
                chosen.append((r, c))
                forbidden[(r, c)] = True
            # propagate: lines with count 2 forbid all other cells on them
            undo = []
            for (r, c) in pr:
                for li in tab.cell_lines[idx(r, c)]:
                    if count[li] == 2:
                        for (r2, c2) in tab.lines[li]:
                            if not forbidden.get((r2, c2), False):
                                forbidden[(r2, c2)] = True
                                undo.append((r2, c2))
            # check each future group still has enough free cells
            ok = True
            for gj in range(gi + 1, ng):
                fr = sum(1 for (r, c) in groups[gj] if not forbidden.get((r, c), False))
                if fr < per[gj]:
                    ok = False
                    break
            if ok and rec(gi + 1):
                return True
            for (r2, c2) in undo:
                del forbidden[(r2, c2)]
            for (r, c) in pr:
                del forbidden[(r, c)]
                chosen.pop()
                for li in tab.cell_lines[idx(r, c)]:
                    count[li] -= 1
        return False

    forbidden = {}
    ok = rec(0)
    return (chosen if ok else None)

def count_solutions(n, timeout=None):
    """Count ALL 2n-point solutions on the n x n grid (A000755) and
    inequivalent ones under D4 (A000769)."""
    t0 = time.time()
    tab = LineTables(n)
    ncell = n * n
    idx = lambda r, c: r * n + c
    count = [0] * tab.L
    total = [0]
    classes = set()

    def canon(mask):
        def trans(mask, f):
            out = 0
            for x in range(n):
                for y in range(n):
                    if mask >> (x * n + y) & 1:
                        a, b = f(x, y)
                        out |= 1 << (a * n + b)
            return out
        cands = []
        cands.append(mask)
        cands.append(trans(mask, lambda x, y: (y, n - 1 - x)))  # rot90
        cands.append(trans(mask, lambda x, y: (n - 1 - x, n - 1 - y)))
        cands.append(trans(mask, lambda x, y: (n - 1 - y, x)))
        cands.append(trans(mask, lambda x, y: (n - 1 - x, y)))  # refl
        cands.append(trans(mask, lambda x, y: (x, n - 1 - y)))
        cands.append(trans(mask, lambda x, y: (y, x)))
        cands.append(trans(mask, lambda x, y: (n - 1 - y, n - 1 - x)))
        return min(cands)

    def rec(r, mask):
        if timeout and time.time() - t0 > timeout:
            raise TimeoutError
        if r == n:
            total[0] += 1
            classes.add(canon(mask))
            return
        avail = [c for c in range(n) if not (forbbit[r] >> c) & 1]
        if len(avail) < 2:
            return
        snapshot = list(forbbit)
        for c1, c2 in itertools.combinations(avail, 2):
            ok = True
            touched = []
            for c in (c1, c2):
                for li in tab.cell_lines[idx(r, c)]:
                    count[li] += 1
                    touched.append(li)
                    if count[li] >= 3:
                        ok = False
            if ok:
                # propagate: count==2 lines forbid their remaining cells in later rows
                for c in (c1, c2):
                    for li in tab.cell_lines[idx(r, c)]:
                        if count[li] == 2:
                            for (r2, c2b) in tab.lines[li]:
                                if r2 > r:
                                    forbbit[r2] |= 1 << c2b
                rec(r + 1, mask | (1 << idx(r, c1)) | (1 << idx(r, c2)))
                forbbit[:] = snapshot
            for li in touched:
                count[li] -= 1
        return

    forbbit = [0] * n
    try:
        rec(0, 0)
    except TimeoutError:
        return total[0], len(classes), True
    return total[0], len(classes), False

# ---------------------------------------------------------------- constructions
def parabola(p):
    return [(x, (x * x) % p) for x in range(p)]

def parabola_fq(q, basis_rev=False):
    """Parabola over F_q (q=p^e) embedded in [q]^2 by digit order (optionally reversed)."""
    p = 2
    e = 0
    while q % p:
        p += 1
    while q % p == 0:
        q //= p
        e += 1
    q = p ** e
    # represent F_q = F_p^e with basis 1,t,...,t^{e-1} (t a root of an irreducible poly)
    # for the tests we only need q=9: t^2 = 2 (i.e. t^2+1)
    if q == 9:
        # F_9 = {a + b t : t^2 = 2}
        def sq(a, b):
            return ((a * a + 2 * b * b) % 3, (2 * a * b) % 3)
        def embed(a, b):
            return (b + 3 * a) if basis_rev else (a + 3 * b)
        pts = []
        for a in range(3):
            for b in range(3):
                x = embed(a, b)
                s = sq(a, b)
                pts.append((x, embed(*s)))
        return pts
    return None

def hsjw_quadrant(p, remove, c_tr, d_bl):
    """Candidate HJSW-type design on the 2p x 2p grid: 3(p-1) points in 3 quadrants.
    TL: parabola minus point `remove`; TR: {(x+p, (x^2+c) mod p)}; BL: {(x, p+(x^2+d) mod p)}."""
    pts = []
    for x in range(p):
        if x != remove:
            pts.append((x, (x * x) % p))          # TL
    for x in range(p):
        pts.append((x + p, (x * x + c_tr) % p))   # TR
    for x in range(p):
        pts.append((x, p + (x * x + d_bl) % p))   # BL
    return pts

# ---------------------------------------------------------------- triple counting
def count_triples(n):
    tab = LineTables(n)
    t = 0
    for cells in tab.lines:
        k = len(cells)
        t += k * (k - 1) * (k - 2) // 6
    return t

# ---------------------------------------------------------------- torus max
def torus_max(m, n, timeout=120):
    t0 = time.time()
    tab = LineTables(1, wrap_mod=(m, n))
    best = [0]
    count = [0] * tab.L
    ncell = m * n
    def rec(cell, sz):
        if time.time() - t0 > timeout:
            raise TimeoutError
        if cell == ncell:
            if sz > best[0]:
                best[0] = sz
            return
        if sz + (ncell - cell) <= best[0]:
            return
        r, c = cell // n, cell % n
        # try exclude
        rec(cell + 1, sz)
        # try include
        ok = True
        touched = []
        for li in tab.cell_lines[cell]:
            count[li] += 1
            touched.append(li)
            if count[li] >= 3:
                ok = False
        if ok:
            rec(cell + 1, sz + 1)
        for li in touched:
            count[li] -= 1
    try:
        rec(0, 0)
    except TimeoutError:
        return best[0], True
    return best[0], False

# ---------------------------------------------------------------- main battery
if __name__ == "__main__":
    print("=" * 70)
    print("E1: count 2n-point solutions, n=2..8 (A000755 / A000769)")
    print("=" * 70)
    oeis755 = {2: 1, 3: 2, 4: 11, 5: 32, 6: 50, 7: 132, 8: 380, 9: 368}
    oeis769 = {2: 1, 3: 1, 4: 4, 5: 5, 6: 11, 7: 22, 8: 57, 9: 51}
    for n in range(2, 9):
        t = time.time()
        tot, cls, _ = count_solutions(n, timeout=300)
        print(f"n={n}: total={tot} (OEIS {oeis755.get(n)}), inequiv={cls} "
              f"(OEIS {oeis769.get(n)})  [{time.time()-t:.1f}s]")

    print()
    print("=" * 70)
    print("E2: first-solution search, n=9..16 (f(n)=2n?)")
    print("=" * 70)
    for n in range(9, 17):
        t = time.time()
        sol = find_solution(n)
        if sol is None:
            print(f"n={n}: NO SOLUTION FOUND in {time.time()-t:.1f}s")
        else:
            assert no3_valid(sol, n) is None
            print(f"n={n}: 2n-point solution found [{time.time()-t:.1f}s] "
                  f"e.g. {sorted(sol)[:6]}...")

    print()
    print("=" * 70)
    print("E3: Erdos parabola (x, x^2 mod p) for primes p")
    print("=" * 70)
    for p in (3, 5, 7, 11, 13, 17):
        s = parabola(p)
        bad = no3_valid(s, p)
        print(f"p={p}: |S|={len(s)}, collinear triple? {bad}")

    print()
    print("=" * 70)
    print("E3b: conic caps {(x,y): x^2 - d y^2 = 1 mod p}, d a non-residue")
    print("=" * 70)
    for p in (3, 5, 7, 11):
        sq = {z * z % p for z in range(p)}
        d = next(k for k in range(2, p) if k % p not in sq) if p > 2 else 2
        pts = [(x, y) for x in range(p) for y in range(p)
               if (x * x - d * y * y) % p == 1]
        bad = no3_valid(pts, p)
        print(f"p={p}: d={d}, |S|={len(pts)} (expected p+1={p+1}), "
              f"collinear triple? {bad}")

    print()
    print("=" * 70)
    print("E4: parabola over F_9 with digit-order embedding (does it fail?)")
    print("=" * 70)
    for rev in (False, True):
        pts = parabola_fq(9, basis_rev=rev)
        bad = no3_valid(pts, 9)
        print(f"digit order (reversed={rev}): |S|={len(pts)}, collinear triple? {bad}")

    print()
    print("=" * 70)
    print("E5: cycle decomposition of a 2n solution into two permutation graphs")
    print("=" * 70)
    sol = find_solution(8)
    cols = {}
    for (r, c) in sol:
        cols.setdefault(r, []).append(c)
    # build bipartite degree-2 graph, 2-colour its cycles
    import collections
    adj = collections.defaultdict(list)
    for (r, c) in sol:
        adj[('r', r)].append(('c', c))
        adj[('c', c)].append(('r', r))
    color = {}
    for node in adj:
        if node not in color:
            color[node] = 0
            stack = [node]
            while stack:
                u = stack.pop()
                for v in adj[u]:
                    if v not in color:
                        color[v] = 1 - color[u]
                        stack.append(v)
                    else:
                        assert color[v] == 1 - color[u], "odd cycle!"
    red = [(r, c) for (r, c) in sol if color[('r', r)] == 0]
    blue = [(r, c) for (r, c) in sol if color[('r', r)] == 1]
    print(f"n=8 solution: {len(sol)} pts; red={len(red)}, blue={len(blue)};")
    print(f"  red has no 3 in line: {no3_valid(red, 8) is None}; "
          f"blue has no 3 in line: {no3_valid(blue, 8) is None}")
    print(f"  red is a permutation graph: {len(set(c for r,c in red))==8 and len(set(r for r,c in red))==8}")

    print()
    print("=" * 70)
    print("E6: HJSW-type quadrant designs on 2p x 2p (3(p-1) points)")
    print("=" * 70)
    for p in (5, 7):
        found = 0
        t = time.time()
        for rem in range(p):
            for c_tr in range(p):
                for d_bl in range(p):
                    pts = hsjw_quadrant(p, rem, c_tr, d_bl)
                    if no3_valid(pts, 2 * p) is None:
                        found += 1
                        if found <= 4:
                            print(f"p={p}: VALID 3(p-1)={3*(p-1)}pt design: "
                                  f"remove={rem}, c_TR={c_tr}, d_BL={d_bl}")
        print(f"p={p}: {found} valid designs of {p**3} tested [{time.time()-t:.1f}s]")

    print()
    print("=" * 70)
    print("E7: number t_n of collinear triples vs (3/pi^2) n^4 log n")
    print("=" * 70)
    import math
    for n in list(range(2, 16)) + [20, 25, 30]:
        t = count_triples(n)
        pred = (3 / math.pi ** 2) * n ** 4 * math.log(n)
        print(f"n={n:2d}: t_n={t:9d}   t_n/((3/pi^2)n^4 log n) = {t/pred:.4f}")

    print()
    print("=" * 70)
    print("E8: torus T(Z_m x Z_n) — max no-3-in-line (lines wrap)")
    print("=" * 70)
    for (m, nn, expect) in [(2, 2, 4), (2, 3, 2), (3, 3, 4), (3, 6, 4), (4, 4, None),
                            (3, 9, 6), (5, 5, 6)]:
        t = time.time()
        v, to = torus_max(m, nn, timeout=180)
        print(f"T({m},{nn}) = {v}{' (TIMEOUT, lower bound only)' if to else ''} "
              f"[expected {expect}] [{time.time()-t:.1f}s]")

    print()
    print("=" * 70)
    print("E8b: conic caps of p+1 points on the torus Z_p x Z_p (modular lines)")
    print("=" * 70)
    for p in (3, 5, 7):
        sq = {z * z % p for z in range(p)}
        d = next(k for k in range(2, p) if k % p not in sq) if p > 2 else 2
        pts = [(x, y) for x in range(p) for y in range(p)
               if (x * x - d * y * y) % p == 1]
        # check against ALL modular lines (cosets of cyclic subgroups) of Z_p^2
        tab = LineTables(1, wrap_mod=(p, p))
        bad = None
        for cells in tab.lines:
            on = [c for c in cells if c in pts]
            if len(on) >= 3:
                bad = on[:3]
                break
        print(f"Z_{p}^2 conic: |S|={len(pts)}, 3 pts on a modular line? {bad}")

    print()
    print("=" * 70)
    print("E9: block variant B(n): 4n points on 2n x 2n, exactly 2 per 2x2 block")
    print("=" * 70)
    for n in (2, 3, 4):
        t = time.time()
        sol = find_solution(n, blocks=True)
        if sol:
            assert no3_valid(sol, 2 * n) is None
            print(f"B({n}): SOLVABLE ({4*n} points on {2*n}x{2*n}) [{time.time()-t:.1f}s]")
        else:
            print(f"B({n}): no solution found [{time.time()-t:.1f}s]")
