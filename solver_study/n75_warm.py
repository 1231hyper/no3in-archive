# n75_warm.py -- n=75 maximize WARM-STARTED from the corpus n=74 solution
# (148 points embedded in [74]^2). Same design as n71_warm.py: spend the
# whole budget on the 148 -> 149/150 region, the only place the f(75)
# answer lives. Stop at >= 149, always save best-so-far.
#
# Usage: python n75_warm.py [--time 25200] [--workers 4] [--seed 13]
#                           [--out n75_deadend.json] [--sol SOLFILE] [--idx 0]
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fast_lines
from ortools.sat.python import cp_model

M = 75


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--time', type=float, default=25200)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--seed', type=int, default=13)
    ap.add_argument('--out', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'n75_deadend.json'))
    ap.add_argument('--sol', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solutions_n74_rot4.json'))
    ap.add_argument('--idx', type=int, default=0)
    a = ap.parse_args()
    print(f"=== n75_warm: maximize with 144-pt warm start (sol={os.path.basename(a.sol)}"
          f"[{a.idx}], time={a.time}s workers={a.workers} seed={a.seed}) ===",
          flush=True)
    t0 = time.time()

    sd = json.load(open(a.sol))
    cfg = sd['configs'][a.idx]
    seed_pts = [tuple(p) for p in cfg['points']]
    assert len(seed_pts) == 148 and cfg["n"] == 74, (len(seed_pts), cfg['n'])
    # all coords are on [74]^2 -> embed in [75]^2 as-is
    assert max(r for r, c in seed_pts) <= 73 and max(c for r, c in seed_pts) <= 73
    print(f"  warm start: {len(seed_pts)} pts from {os.path.basename(a.sol)}[{a.idx}]",
          flush=True)

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
    for (r, c) in seed_pts:
        model.add_hint(x[r][c], 1)
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
                self.pts = [(r, c) for r in range(M) for c in range(M)
                            if self.value(self.xx[r][c])]
                print(f"  [cb] size={val} at t={self.wall_time:.1f}s", flush=True)
            if val >= 149:
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
        if os.path.exists(a.out):
            try:
                prev = json.load(open(a.out))
                if prev.get('size', 0) >= 145 and len(cb.pts) < 145:
                    print(f"  keeping existing {a.out} (size {prev['size']}), "
                          f"discarding own best {len(cb.pts)}", flush=True)
                    return
            except Exception:
                pass
        json.dump({'m': M, 'size': len(cb.pts), 'points': sorted(cb.pts)},
                  open(a.out, 'w'), indent=1)
        print(f"  saved {a.out} ({len(cb.pts)} pts)", flush=True)
    else:
        print("  no solution captured", flush=True)


if __name__ == '__main__':
    main()
