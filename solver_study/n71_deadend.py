# n71_deadend.py -- unrestricted from-scratch maximize for n=71, stop at the
# 2n-1 = 141 dead-end, save it. The dead-end is then handed to the ladder-
# repair machinery (qw2's pivot: k removals + k+1 additions closing the
# row/col deficits) -- the dead-end structure at small n says these need
# k >= 3 removals; at n=71 a k<=3 success would settle f(71)=142.
#
# Usage: python n71_deadend.py [--time 7200] [--workers 4] [--out n71_deadend.json]
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fast_lines
import ortools
from ortools.sat.python import cp_model

M = 71


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--time', type=float, default=7200)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--seed', type=int, default=7)
    ap.add_argument('--out', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'n71_deadend.json'))
    a = ap.parse_args()
    print(f"=== n71_deadend: unrestricted maximize, stop at 141, "
          f"time={a.time}s workers={a.workers} ===", flush=True)
    print(f"  OR-Tools {ortools.__version__}; Python "
          f"{sys.version.split()[0]}", flush=True)
    t0 = time.time()

    model = cp_model.CpModel()
    x = [[model.new_bool_var(f"x_{r}_{c}") for c in range(M)] for r in range(M)]
    tab = fast_lines.cached_table(M)
    for cells in tab.lines:
        model.add(sum(x[r][c] for (r, c) in cells) <= 2)
    tab.cell_lines = None
    tab.line_rowcol = None
    for r in range(M):
        model.add(sum(x[r][c] for c in range(M)) <= 2)
        model.add(sum(x[rr][r] for rr in range(M)) <= 2)
    model.maximize(sum(x[r][c] for r in range(M) for c in range(M)))

    class Cb(cp_model.CpSolverSolutionCallback):
        def __init__(self, xx):
            cp_model.CpSolverSolutionCallback.__init__(self)
            self.xx = xx
            self.best = 0
            self.pts = None

        def on_solution_callback(self):
            val = int(self.objective_value)
            if val > self.best:
                self.best = val
                # keep the best-so-far points so a timeout below 141 still
                # lands a usable partial (qw2's repair runs on 140 too)
                self.pts = [(r, c) for r in range(M) for c in range(M)
                            if self.value(self.xx[r][c])]
                print(f"  [cb] size={val} at t={self.wall_time:.1f}s", flush=True)
            if val >= 141:          # dead-end reached: capture and stop
                self.stop_search()

    cb = Cb(x)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = a.workers
    solver.parameters.max_time_in_seconds = a.time
    solver.parameters.max_memory_in_mb = 3500
    solver.parameters.random_seed = a.seed
    st = solver.solve(model, cb)
    print(f"  [solve] status={solver.status_name(st)} "
          f"best={cb.best} wall={time.time() - t0:.0f}s", flush=True)
    if cb.pts is not None:
        # do not clobber a better capture (>= 141) from a parallel run
        if os.path.exists(a.out):
            try:
                prev = json.load(open(a.out))
                if prev.get('size', 0) >= 141 and len(cb.pts) < 141:
                    print(f"  keeping existing {a.out} (size {prev['size']}), "
                          f"discarding own best {len(cb.pts)}", flush=True)
                    return
            except Exception:
                pass
        json.dump({'m': M, 'size': len(cb.pts),
                   'points': sorted(cb.pts)}, open(a.out, 'w'), indent=1)
        print(f"  saved dead-end {a.out} ({len(cb.pts)} pts)", flush=True)
    else:
        print("  no solution captured", flush=True)


if __name__ == '__main__':
    main()
