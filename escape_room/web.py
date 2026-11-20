"""Bridge between the website and the Python code.

On the website the Python package runs in the browser through Pyodide (Python compiled to
WebAssembly). The pages call these functions and receive JSON strings back, so the browser
only draws; every decision is made by the same Python code as the desktop demo and tests.
"""
import json
import math

from . import evaluation
from .checks import CHECKS
from .csp import CSP_MODES
from .qlearn import ACTIONS, QLab
from .sim import DYNAMICS, Simulation
from .view import fuzzy_static, fuzzy_view, lock_view, route_view, tree_view
from .world import FLOOR

_sim = None
_lab = None
_ctx = {}


def _clean(x):
    """JSON has no NaN or infinity (e.g. the mean of an empty list): send null instead."""
    if isinstance(x, float) and (x != x or x in (math.inf, -math.inf)):
        return None
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    return x


def _json(x, clean=False):
    return json.dumps(_clean(x) if clean else x, separators=(",", ":"))


# ---------------------------------------------------------------- simulator
def new_sim(config_json):
    """Start a new simulation. config: seed, algo, csp, fuzzy, time_aware, adaptive, dynamics."""
    global _sim
    _sim = Simulation(verbose=True, **json.loads(config_json))
    return snapshot()


def step(n=1):
    for _ in range(int(n)):
        if _sim.done:
            break
        _sim.step()
    return snapshot()


def collapse():
    if not _sim.done:
        _sim.collapse(by_user=True)
    return snapshot()


def surge():
    if not _sim.done:
        _sim.surge(by_user=True)
    return snapshot()


def alarm(bring_close=False):
    """Sound the alarm. With bring_close, first move the drone about 6 cells from the agent
    (used by the guided scenario, so the reaction is easy to see)."""
    s = _sim
    if s.done or s.drone is None:
        return snapshot()
    if bring_close:
        w = s.world
        d = w.bfs(w.idx(s.agent.x, s.agent.y))
        cell = next((i for i in range(w.N) if 5 <= d[i] <= 7 and not w.is_object_cell(i)), None)
        if cell is not None:
            s.move_drone(*w.xy(cell))
    s.alert_drone()
    s.say("EVENT", "[you] Alarm sounded: the drone is hunting")
    return snapshot()


def tool(kind, x, y):
    """Map click: 'rubble' toggles rubble, 'hazard' toggles coolant, 'drone' moves the drone."""
    s, x, y = _sim, int(x), int(y)
    if not s.done:
        {"rubble": s.toggle_rubble, "hazard": s.toggle_hazard, "drone": s.move_drone}[kind](x, y)
        s.update_sensors()
    return snapshot()


def fuzzy_rules():
    return _json(fuzzy_static(_sim))


def snapshot():
    s, w, a, d = _sim, _sim.world, _sim.agent, _sim.drone
    searched = None
    if a.last_search and s.t - a.last_search[1] < 15:
        order, first = a.last_search[0], {}
        for k, c in enumerate(order):
            first.setdefault(c, k)
        n = max(1, len(order) - 1)
        searched = dict(age=s.t - a.last_search[1], cells=[[c, round(k / n, 2)] for c, k in first.items()])
    fx, s.fx = s.fx, []
    state = dict(
        t=s.t, done=s.done, result=s.result, max_ticks=s.max_ticks, W=w.W, H=w.H, config=s.config,
        tiles=w.tiles, hazard=w.hazard, start=w.start, terminal=w.terminal, exit=w.exit,
        gates=[dict(x=g.x, y=g.y, on=w.gate_on(g.x, g.y, s.t), o=w.gate_orientation(g)) for g in w.gates] if w.gates_active else [],
        risk=[round(s.risk_at(i)) if w.tiles[i] == FLOOR else 0 for i in range(w.N)] if d else None,
        drone_dist=[s.drone_dist_at(i) for i in range(w.N)] if d else None,
        searched=searched,
        agent=dict(x=a.x, y=a.y, px=a.px, py=a.py, hull=max(0, a.integrity), mode=a.mode, adaptive=a.adaptive,
                   evading=a.evading, stun=a.stun, hacking=a.hack is not None),
        drone=dict(x=d.x, y=d.y, px=d.px, py=d.py, state=d.state, detect=d.detect, transitions=d.transitions,
                   alert=d.alertness()) if d else None,
        keys=[dict(x=k.x, y=k.y, name=k.name, color=k.color, taken=k.taken) for k in w.keys],
        exit_open=a.exit_unlocked(), code_ok=a.code_version == s.lock.version,
        route=route_view(s), tree=tree_view(s), lock=lock_view(s), fuzzy=fuzzy_view(s),
        stats={k: v for k, v in a.stats.items() if k != "replans_by"},
        logs=s.logs[-90:], fx=fx,
    )
    return _json(state)


# ---------------------------------------------------------------- learning lab
def lab_new(config_json):
    global _lab
    cfg = json.loads(config_json)
    _lab = QLab(int(cfg.get("seed", 4)), float(cfg.get("alpha", 0.2)), float(cfg.get("gamma", 0.97)), float(cfg.get("eps_decay", 0.993)))
    return lab_state(0)


def lab_train(n):
    _lab.train(int(n))
    last = _lab.curve[-50:]
    return _json(dict(episodes=_lab.episodes, eps=_lab.eps, success=sum(r["success"] for r in last) / max(1, len(last)),
                      steps=sum(r["steps"] for r in last) / max(1, len(last))))


def lab_state(mask):
    w = _lab.world
    return _json(dict(
        W=w.W, H=w.H, tiles=w.tiles, start=w.start, exit=w.exit, episodes=_lab.episodes, eps=_lab.eps, max_steps=_lab.max_steps,
        keys=[dict(x=k.x, y=k.y, name=k.name, color=k.color) for k in w.keys], masks=_lab.M,
        values=_lab.values(int(mask)), actions=ACTIONS,
        curve=dict(steps=[r["steps"] for r in _lab.curve], success=[r["success"] for r in _lab.curve]),
        collapses=_lab.collapses,
    ))


def lab_greedy():
    return _json(_lab.greedy())


def lab_optimal():
    return _json(_lab.optimal())


def lab_collapse():
    if not _lab.episodes:
        return _json(dict(ok=False, why="untrained"))
    if not _lab.greedy()["success"]:
        return _json(dict(ok=False, why="no policy"))
    cell = _lab.collapse_route()
    if cell is None:
        return _json(dict(ok=False, why="no cell"))
    return _json(dict(ok=True, cell=cell, after=_lab.greedy(), optimal=_lab.optimal()))


# ---------------------------------------------------------------- benchmark
def bench_info():
    return _json(dict(configs=[dict(id=c["id"], label=c["label"]) for c in evaluation.AGENT_CONFIGS],
                      dynamics={k: v["label"] for k, v in DYNAMICS.items()}, planners=evaluation.PLANNER_NAMES, solvers=CSP_MODES))


def bench_mission(config_id, seed, dynamics):
    return _json(evaluation.run_mission(config_id, int(seed), dynamics))


def bench_summary(rows_json):
    rows = json.loads(rows_json)
    out = {}
    for cid in dict.fromkeys(r["config"] for r in rows):
        out[cid] = evaluation.summarize([r for r in rows if r["config"] == cid])
    return _json(out, clean=True)


def bench_planners(n_maps):
    _, summary = evaluation.planner_compare(range(5000, 5000 + int(n_maps)))
    return _json(summary, clean=True)


def bench_solvers(n_locks):
    _, summary = evaluation.csp_compare(int(n_locks))
    return _json(summary, clean=True)


# ---------------------------------------------------------------- tests
def tests_list():
    return _json([dict(group=g, name=n, proves=p) for g, n, p, _ in CHECKS])


def test_run(i):
    try:
        passed, detail = CHECKS[int(i)][3](_ctx)
    except Exception as e:  # report, don't crash the page
        passed, detail = False, f"Error: {e}"
    return _json(dict(passed=bool(passed), detail=detail))
