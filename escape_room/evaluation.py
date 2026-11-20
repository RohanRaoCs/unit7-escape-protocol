"""Evaluation using the measures from the brief: success rate, completion time (ticks),
path cost and states explored, plus replans, damage and component experiments.

Shared by evaluate.py (command line) and the website's Benchmark page."""
import math
import random

from .csp import CSP_MODES, make_lock, solve
from .qlearn import QLab
from .search import ALGOS, plan
from .sim import run_episode
from .world import generate_world

AGENT_CONFIGS = [
    dict(id="unit7", label="UNIT-7 full: A* + fuzzy + space-time + BT", algo="astar", fuzzy=True, time_aware=True, adaptive=True),
    dict(id="snapshot", label="A* + fuzzy, snapshot planning", algo="astar", fuzzy=True, time_aware=False, adaptive=True),
    dict(id="crisp", label="A* + crisp avoidance (no fuzzy)", algo="astar", fuzzy=False, time_aware=True, adaptive=True),
    dict(id="dijkstra", label="Dijkstra + fuzzy + space-time", algo="dijkstra", fuzzy=True, time_aware=True, adaptive=True),
    dict(id="greedy", label="Greedy best-first + fuzzy + space-time", algo="greedy", fuzzy=True, time_aware=True, adaptive=True),
    dict(id="bfs", label="BFS + fuzzy + space-time", algo="bfs", fuzzy=True, time_aware=True, adaptive=True),
    dict(id="script", label="Fixed script (plans once, never adapts)", algo="astar", fuzzy=False, time_aware=False, adaptive=False),
]
CONFIG_BY_ID = {c["id"]: c for c in AGENT_CONFIGS}


def mean_std(xs):
    xs = [x for x in xs if x is not None and not (isinstance(x, float) and math.isnan(x))]
    if not xs:
        return dict(mean=float("nan"), std=float("nan"))
    m = sum(xs) / len(xs)
    var = sum((x - m) ** 2 for x in xs) / max(1, len(xs) - 1)
    return dict(mean=m, std=math.sqrt(var))


def run_mission(config_id, seed, dynamics):
    """One full mission for one agent design. Returns a flat result row."""
    cfg = {k: v for k, v in CONFIG_BY_ID[config_id].items() if k not in ("id", "label")}
    return dict(config=config_id, dynamics=dynamics, **run_episode(seed=seed, dynamics=dynamics, **cfg))


def summarize(rows):
    """Ticks and path cost are averaged over successful runs only (failures are capped at the time limit)."""
    ok = [r for r in rows if r["success"]]
    out = {k: mean_std([r[k] for r in rows]) for k in ("success", "expanded", "replans", "hits", "zaps", "integrity", "csp_assignments")}
    out["ticks_ok"] = mean_std([r["ticks"] for r in ok])
    out["cost_ok"] = mean_std([r["path_cost"] for r in ok])
    out["n"] = len(rows)
    reasons = {}
    for r in rows:
        reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1
    out["reasons"] = reasons
    return out


def hazard_world(seed, n_cells=40):
    """A map with extra coolant cells, so the cheapest path is not always the shortest."""
    w = generate_world(seed)
    w.gates_active = False
    rng = random.Random(seed + 555)
    for _ in range(n_cells):
        x, y = rng.randint(1, w.W - 2), rng.randint(1, w.H - 2)
        if w.is_free(x, y) and not w.is_object_cell(w.idx(x, y)):
            w.hazard[w.idx(x, y)] = 1
    return w


def planner_compare(seeds):
    """Identical start -> goal queries for every planner. Also compares snapshot and space-time
    A* with the laser gates switched on."""
    rows = []
    for seed in seeds:
        w = hazard_world(seed)
        for goal in [w.exit] + [(k.x, k.y) for k in w.keys] + [w.terminal]:
            best = plan(w, w.start, goal, "dijkstra").cost
            for algo in ALGOS:
                r = plan(w, w.start, goal, algo)
                rows.append(dict(seed=seed, planner=algo, expanded=r.expanded, cost=r.cost, optimal=int(abs(r.cost - best) < 1e-9),
                                 gap=(r.cost - best) / best, ms=r.ms))
            w.gates_active = True
            for name, ta in (("astar_snapshot", False), ("astar_spacetime", True)):
                r = plan(w, w.start, goal, "astar", time_aware=ta, t0=0)
                rows.append(dict(seed=seed, planner=name, expanded=r.expanded, cost=r.cost, optimal=None, gap=None, ms=r.ms))
            w.gates_active = False
    summary = {}
    for name in list(ALGOS) + ["astar_snapshot", "astar_spacetime"]:
        rs = [r for r in rows if r["planner"] == name]
        summary[name] = dict(n=len(rs), expanded=mean_std([r["expanded"] for r in rs]), cost=mean_std([r["cost"] for r in rs]),
                             optimal=mean_std([r["optimal"] for r in rs])["mean"], gap=mean_std([r["gap"] for r in rs])["mean"],
                             ms=mean_std([r["ms"] for r in rs]))
    return rows, summary


PLANNER_NAMES = dict(ALGOS, astar_snapshot="A* snapshot (gates frozen at t=0)", astar_spacetime="A* space-time (gate timetable)")


def csp_compare(n_locks, seed0=7):
    """All lock solvers on the same generated locks."""
    rows = []
    for k in range(n_locks):
        lock = make_lock(random.Random(seed0 * 1000 + k))
        for mode in CSP_MODES:
            r = solve(lock, mode)
            rows.append(dict(lock=k, solver=mode, clues=len(lock.constraints), assignments=r.assignments, backtracks=r.backtracks,
                             checks=r.checks, prunes=r.prunes, ms=r.ms, correct=int(r.solution == lock.secret)))
    summary = {}
    for mode in CSP_MODES:
        rs = [r for r in rows if r["solver"] == mode]
        summary[mode] = {k: mean_std([r[k] for r in rs]) for k in ("assignments", "backtracks", "checks", "ms", "clues")}
        summary[mode]["correct"] = mean_std([r["correct"] for r in rs])["mean"]
        summary[mode]["n"] = len(rs)
    return rows, summary


def learning_vs_planning(seed, episodes=2500, recover_limit=3000):
    """Train Q-learning, drop rubble on the learned route, and see how planning and learning cope."""
    lab = QLab(seed)
    first = None
    for _ in range(0, episodes, 50):
        lab.train(50)
        if first is None and lab.greedy()["success"]:
            first = lab.episodes
    learned, optimal = lab.greedy(), lab.optimal()
    cell = lab.collapse_route()
    after, optimal_after = lab.greedy(), lab.optimal()
    recover = 0 if after["success"] else None
    if not after["success"]:
        for done in range(50, recover_limit + 1, 50):
            lab.train(50)
            if lab.greedy()["success"]:
                recover = done
                break
    return dict(seed=seed, first_success=first, learned_steps=learned["steps"] if learned["success"] else None,
                optimal_steps=optimal["steps"], collapsed=cell is not None,
                after_collapse="still works" if after["success"] else after.get("reason"),
                astar_after=optimal_after["steps"], recover_episodes=recover)
