# n71_warm.py -- n=71 maximize WARM-STARTED from a corpus n=70 solution
# (140 points embedded in [71]^2). Skips the 0->140 climb that stalls at
# ~125 and spends the whole budget on the 140 -> 141/142 region, the only
# place the f(71) answer lives. Stop at >= 141, always save best-so-far.
#
# Usage: python n71_warm.py [--time 28800] [--workers 4] [--seed 13]
#                           [--out n71_deadend_b.json] [--sol SOLFILE] [--idx 0]
import argparse
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import fast_lines
from ortools.sat.python import cp_model

M = 71


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--time', type=float, default=28800)
    ap.add_argument('--workers', type=int, default=4)
    ap.add_argument('--seed', type=int, default=13)
    ap.add_argument('--feas', action='store_true',
                    help='add sum >= 141 as a hard constraint (presolve sees a '
                         'tighter lower bound; different search behavior)')
    ap.add_argument('--out', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'n71_deadend_b.json'))
    ap.add_argument('--sol', default=os.path.join(os.path.dirname(os.path.abspath(__file__)), 'solutions_n70_rot4.json'))
    ap.add_argument('--idx', type=int, default=0)
    a = ap.parse_args()
    print(f"=== n71_warm: maximize with 140-pt warm start (sol={os.path.basename(a.sol)}"
          f"[{a.idx}], time={a.time}s workers={a.workers} seed={a.seed}) ===",
          flush=True)
    t0 = time.time()

    sd = json.load(open(a.sol))
    cfg = sd['configs'][a.idx]
    seed_pts = [tuple(p) for p in cfg['points']]
    assert len(seed_pts) == 140 and cfg['n'] == 70, (len(seed_pts), cfg['n'])
    # all coords are on [70]^2 -> embed in [71]^2 as-is
    assert max(r for r, c in seed_pts) <= 69 and max(c for r, c in seed_pts) <= 69
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
    if a.feas:
        model.add(sum(x[r][c] for r in range(M) for c in range(M)) >= 141)
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
            if val >= 141:
                self.stop_search()

    cb = Cb(x)
    solver = cp_model.CpSolver()
    solver.parameters.num_search_workers = a.workers
    solver.parameters.max_time_in_seconds = a.time
    solver.parameters.max_memory_in_mb = 3500
    solver.parameters.random_seed = a.seed
    # Watchdog: under heavy machine load CP-SAT's wall-clock cap can overrun
    # (observed 3.6x on 2026-08-16); force StopSearch at deadline + 30 s, and
    # hard-exit at deadline + 120 s after saving best-so-far.
    if hasattr(solver, 'StopSearch'):
        import threading
        def _wd():
            time.sleep(a.time + 30)
            print(f"  [wd] firing StopSearch at t={time.time() - t0:.0f}s",
                  flush=True)
            try:
                solver.StopSearch()
            except Exception as e:
                print(f"  [wd] StopSearch raised: {e!r}", flush=True)
            time.sleep(90)
            if cb.pts is not None and not os.path.exists(a.out):
                try:
                    json.dump({'m': M, 'size': len(cb.pts),
                               'points': sorted(cb.pts)},
                              open(a.out, 'w'), indent=1)
                    print("  [wd] hard-saved best-so-far", flush=True)
                except Exception as e:
                    print(f"  [wd] hard-save failed: {e!r}", flush=True)
            os._exit(0)
        threading.Thread(target=_wd, daemon=True).start()
    st = solver.solve(model, cb)
    print(f"  [solve] status={solver.status_name(st)} "
          f"best={cb.best} wall={time.time() - t0:.0f}s", flush=True)
    if cb.pts is not None:
        if os.path.exists(a.out):
            try:
                prev = json.load(open(a.out))
                if prev.get('size', 0) >= 141 and len(cb.pts) < 141:
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
