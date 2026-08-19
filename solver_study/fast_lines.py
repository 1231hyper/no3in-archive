# fast_lines.py — fast line-table builder with canonical boundary starts,
# plus pickle caching. Verified to agree with no3in.LineTables (see build_and_cache).
# Speedup over no3in.LineTables for n=65: ~10-20x (canonical starts instead of
# enumerating every cell as a line start).
import pickle, time, os
from math import gcd

CACHE_DIR = os.path.dirname(os.path.abspath(__file__))

def build_lines(n, wrap_mod=None):
    """Same output format as no3in.LineTables: (line_cells, cell_lines)."""
    if wrap_mod:
        # torus: keep the reference implementation semantics (small grids only)
        import no3in
        return no3in.LineTables(1, wrap_mod=wrap_mod)
    dirs = []
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
        # canonical start = cell from which one step backwards leaves the grid
        # (only cells with x < a or y < b when a,b >= 0; the sign of b handled below)
        for x in range(n):
            for y in range(n):
                if a >= 0:
                    if b >= 0:
                        if not (x - a < 0 or y - b < 0):
                            continue
                    else:
                        if not (x - a < 0 or y - b >= n):
                            continue
                pts = []
                cx, cy = x, y
                while 0 <= cx < n and 0 <= cy < n:
                    pts.append((cx, cy))
                    cx += a
                    cy += b
                if len(pts) >= 3:
                    line_cells.append(tuple(pts))
    # cell_lines: per cell, ids of lines through it
    cell_lines = [[] for _ in range(n * n)]
    for li, cells in enumerate(line_cells):
        for (r, c) in cells:
            cell_lines[r * n + c].append(li)
    return line_cells, cell_lines

class Tab:
    """Drop-in compatible with no3in.LineTables (attributes .lines, .cell_lines, .L)."""
    def __init__(self, lines, cell_lines):
        self.lines = lines
        self.cell_lines = cell_lines
        self.L = len(lines)

def cached_table(n, wrap_mod=None):
    name = f'line_table_{"x".join(map(str, wrap_mod)) if wrap_mod else n}.pkl'
    path = os.path.join(CACHE_DIR, name)
    if os.path.exists(path):
        with open(path, 'rb') as f:
            loaded = pickle.load(f)
        if isinstance(loaded, Tab):
            return loaded
        return Tab(loaded[0], loaded[1])
    t0 = time.time()
    table = build_lines(n, wrap_mod)
    with open(path, 'wb') as f:
        pickle.dump(table, f)
    print(f'built and cached {name}: {len(table[0])} lines in {time.time()-t0:.1f}s', flush=True)
    return Tab(table[0], table[1])

if __name__ == '__main__':
    # verification for small n against the reference implementation
    import no3in
    for n in (8, 10, 14):
        ref = no3in.LineTables(n)
        fast = build_lines(n)
        s_ref = set(map(frozenset, ref.lines))
        s_fast = set(map(frozenset, fast[0]))
        same = s_ref == s_fast
        print(f'n={n}: reference lines {len(ref.lines)}, fast lines {len(fast[0])}, identical={same}')
        if not same:
            print('  only in ref:', list(s_ref - s_fast)[:3])
            print('  only in fast:', list(s_fast - s_ref)[:3])
    for n in (22, 26, 65):
        cached_table(n)
    print('fast_lines DONE')
