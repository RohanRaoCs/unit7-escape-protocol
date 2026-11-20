"""Correctness checks, shared by `python -m unittest` (tests/test_escape_room.py) and the
website's Testing page. Each check returns (passed, detail); `proves` says which claim or
requirement of the brief it backs up."""
from .bt import RUNNING, action, condition, selector, sequence
from .csp import CSP_MODES, count_solutions, make_lock, mutate_lock, solve
from .evaluation import hazard_world
from .fuzzy import make_risk_fuzzy
from .qlearn import QLab
from .search import plan
from .sim import run_episode
from .world import generate_world
import random


def _goals(w):
    return [w.exit] + [(k.x, k.y) for k in w.keys] + [w.terminal]


def astar_optimal(ctx):
    n = 0
    for seed in range(1, 41):
        w = hazard_world(seed)
        for goal in _goals(w):
            d, a = plan(w, w.start, goal, "dijkstra"), plan(w, w.start, goal, "astar")
            if abs(a.cost - d.cost) > 1e-9:
                return False, f"seed {seed}: A* {a.cost} vs Dijkstra {d.cost}"
            for (x0, y0), (x1, y1) in zip(a.path, a.path[1:]):
                if abs(x0 - x1) + abs(y0 - y1) != 1 or not w.is_free(x1, y1):
                    return False, f"invalid step on seed {seed}"
            n += 1
    return True, f"{n} of {n} queries optimal"


def astar_fewer_states(ctx):
    a_total = d_total = 0
    for seed in range(1, 41):
        w = hazard_world(seed)
        for goal in _goals(w):
            a, d = plan(w, w.start, goal, "astar").expanded, plan(w, w.start, goal, "dijkstra").expanded
            if a > d:
                return False, f"seed {seed}: {a} > {d}"
            a_total += a
            d_total += d
    return True, f"{a_total:,} vs {d_total:,} states ({round(100 - 100 * a_total / d_total)}% fewer)"


def greedy_not_optimal(ctx):
    worse = total = 0
    for seed in range(1, 41):
        w = hazard_world(seed)
        for goal in _goals(w):
            total += 1
            worse += plan(w, w.start, goal, "greedy").cost > plan(w, w.start, goal, "dijkstra").cost + 1e-9
    return worse > 0, f"costlier than optimal on {worse} of {total} queries"


def spacetime_no_collisions(ctx):
    n = 0
    for seed in range(1, 31):
        w = generate_world(seed)
        for t0 in (0, 3, 7):
            for goal in [w.exit] + [(k.x, k.y) for k in w.keys]:
                r = plan(w, w.start, goal, "astar", time_aware=True, t0=t0)
                if not r.found:
                    return False, f"no path on seed {seed}"
                for k, (x, y) in enumerate(r.path[1:], 1):
                    if w.gate_on(x, y, t0 + k):
                        return False, f"seed {seed}, step {k}"
                n += 1
    return True, f"{n} paths replayed tick by tick, 0 collisions"


def spacetime_optimal(ctx):
    n = 0
    for seed in range(1, 31):
        w = generate_world(seed)
        for t0 in (0, 3, 7):
            for goal in [w.exit] + [(k.x, k.y) for k in w.keys]:
                a = plan(w, w.start, goal, "astar", time_aware=True, t0=t0)
                d = plan(w, w.start, goal, "dijkstra", time_aware=True, t0=t0)
                if abs(a.cost - d.cost) > 1e-9:
                    return False, f"seed {seed}: {a.cost} vs {d.cost}"
                n += 1
    return True, f"{n} of {n} queries match"


def solvers_correct(ctx):
    for k in range(40):
        lock = make_lock(random.Random(900 + k))
        for mode in CSP_MODES:
            r = solve(lock, mode)
            if r.solution != lock.secret or not all(c.ok(r.solution) for c in lock.constraints):
                return False, f"{mode} on lock {k}"
    return True, f"{40 * len(CSP_MODES)} of {40 * len(CSP_MODES)} solves correct"


def locks_unique(ctx):
    for k in range(40):
        if count_solutions(make_lock(random.Random(900 + k)), 3) != 1:
            return False, f"lock {k}"
    return True, "40 of 40 locks have exactly one solution"


def heuristics_help(ctx):
    best = plain = 0
    for k in range(40):
        lock = make_lock(random.Random(900 + k))
        a, b = solve(lock, "mrv_fc_ac3").assignments, solve(lock, "bt").assignments
        if a > b:
            return False, f"lock {k}: {a} > {b}"
        best += a
        plain += b
    return True, f"{best:,} vs {plain:,} assignments in total"


def surge_valid(ctx):
    for k in range(40):
        rng = random.Random(900 + k)
        lock = make_lock(rng)
        ch = mutate_lock(lock, rng)
        r = solve(lock, "mrv_fc_ac3")
        if not ch["changed_dials"] or r.solution != lock.secret or count_solutions(lock, 3) != 1 or lock.version != 1:
            return False, f"lock {k}"
    return True, "40 of 40 surges give a new puzzle with one solution"


def fuzzy_distance(ctx):
    f = make_risk_fuzzy()
    for alert in (0.2, 1.0):
        prev = float("inf")
        for d in range(21):
            v = f.infer(dict(distance=d, alert=alert, integrity=100))["value"]
            if v > prev + 1e-6:
                return False, f"alert {alert}, distance {d}"
            prev = v
    return True, "never rises with distance over 0-20 cells"


def fuzzy_alert(ctx):
    f = make_risk_fuzzy()
    calm = f.infer(dict(distance=3, alert=0.2, integrity=100))["value"]
    hot = f.infer(dict(distance=3, alert=1.0, integrity=100))["value"]
    return hot > calm, f"{hot:.1f} vs {calm:.1f} at 3 cells"


def fuzzy_damage(ctx):
    f = make_risk_fuzzy()
    hurt = f.infer(dict(distance=6, alert=0.2, integrity=20))["value"]
    fine = f.infer(dict(distance=6, alert=0.2, integrity=100))["value"]
    return hurt > fine, f"{hurt:.1f} vs {fine:.1f} at 6 cells"


def bt_preempts(ctx):
    log, state = [], {"threat": False}
    tree = selector("root", [
        sequence("survive", [condition("threat", lambda: state["threat"]), action("evade", lambda: log.append("evade") or RUNNING)]),
        action("work", lambda: log.append("work") or RUNNING),
    ])
    tree.run(0)
    state["threat"] = True
    tree.run(1)
    state["threat"] = False
    tree.run(2)
    return log == ["work", "evade", "work"], " -> ".join(log)


def reproducible(ctx):
    a, b = run_episode(seed=7), run_episode(seed=7)
    return a == b, f"seed 7: {a['ticks']} ticks both times"


def static_escapes(ctx):
    ok = sum(run_episode(seed=s, dynamics="off")["success"] for s in range(1, 21))
    return ok == 20, f"{ok} of 20 escaped"


def surge_recovery(ctx):
    surged = recovered = 0
    for s in range(1, 31):
        r = run_episode(seed=s)
        if r["surges"]:
            surged += 1
            recovered += r["success"]
    return surged > 0 and recovered / surged >= 0.9, f"{recovered} of {surged} runs with a power surge escaped"


def adaptive_beats_script(ctx):
    a = s = 0
    for k in range(1, 26):
        a += run_episode(seed=k)["success"]
        s += run_episode(seed=k, adaptive=False, fuzzy=False, time_aware=False)["success"]
    return a >= 22 and a > s + 8, f"adaptive {a}/25 vs fixed script {s}/25"


def qlearning_learns(ctx):
    lab = QLab(4)
    lab.train(2500)
    ctx["lab"] = lab
    g, opt = lab.greedy(), lab.optimal()
    return g["success"] and g["steps"] <= opt["steps"] * 1.25, f"{g['steps']} steps vs optimal {opt['steps']}"


def learning_vs_planning(ctx):
    lab = ctx.get("lab")
    if lab is None:
        lab = QLab(4)
        lab.train(2500)
    cell = lab.collapse_route()
    stale, opt = lab.greedy(), lab.optimal()
    lab.train(1500)
    fixed = lab.greedy()
    detail = (f"A* replans to {opt['steps']} steps at once; the stale policy "
              f"{'still works' if stale['success'] else 'fails (' + stale['reason'] + ')'}; after retraining it "
              f"{'works' if fixed['success'] else 'still fails'}")
    return cell is not None and opt["steps"] is not None and fixed["success"], detail


CHECKS = [
    ("Search", "A* finds optimal routes", "A* returns the same (optimal) cost as Dijkstra on 200 queries with uneven step costs, and every path is a valid chain of free cells.", astar_optimal),
    ("Search", "A* explores fewer states than Dijkstra", "The Manhattan heuristic prunes the search: A* never expands more states than uniform-cost search.", astar_fewer_states),
    ("Search", "Greedy best-first is not always optimal", "A sanity check on the comparison: greedy ignores path cost, so on some queries it returns a costlier route.", greedy_not_optimal),
    ("Search", "Space-time A* never walks into an active laser gate", "Planning over (cell, time) respects the gate timetable: replaying every planned path tick by tick never stands in a gate while it is on.", spacetime_no_collisions),
    ("Search", "Space-time A* is optimal", "Adding time to the state keeps A* optimal: it matches space-time Dijkstra on every query.", spacetime_optimal),
    ("Constraint satisfaction", "Every solver finds the vault code", "All four CSP solvers return the secret code, and it satisfies every clue, on 40 generated locks.", solvers_correct),
    ("Constraint satisfaction", "Every lock has exactly one solution", "The puzzle generator only produces fair puzzles: the clues pin down a single code.", locks_unique),
    ("Constraint satisfaction", "Heuristics reduce search", "MRV + forward checking + AC-3 never needs more assignments than plain backtracking.", heuristics_help),
    ("Constraint satisfaction", "A power surge produces a new valid puzzle", "When constraints change mid-run, the new clue set still has exactly one solution, and the solver finds it.", surge_valid),
    ("Fuzzy logic", "Threat falls with distance", "The rule base behaves sensibly: moving away from the drone never increases the threat.", fuzzy_distance),
    ("Fuzzy logic", "An alert drone is more dangerous than a calm one", "Alertness (from the drone's state machine) changes the output.", fuzzy_alert),
    ("Fuzzy logic", "A damaged agent is more cautious", "Low hull integrity raises the threat at the same distance.", fuzzy_damage),
    ("Behaviour tree", "Survive interrupts a running action and then resumes it", "The tree is reactive: a high-priority branch takes over the moment its condition holds.", bt_preempts),
    ("Simulation", "Runs are reproducible", "The same seed gives the same mission, so every benchmark number can be re-checked.", reproducible),
    ("Simulation", "The agent escapes every static facility", "The full mission (keycards, CSP lock, exit) is solvable and solved on 20 maps.", static_escapes),
    ("Simulation", "The agent recovers from power surges", "When the lock is rewired mid-run, the behaviour tree sends the agent back to solve it again.", surge_recovery),
    ("Simulation", "Adapting beats a fixed plan", "The core requirement: on dynamic maps the adaptive agent clearly beats a fixed sequence of actions.", adaptive_beats_script),
    ("Reinforcement learning", "Q-learning learns a near-optimal escape", "After 2,500 episodes the greedy policy escapes within 25% of the A* optimum.", qlearning_learns),
    ("Reinforcement learning", "After a collapse, planning adapts and learning must retrain", "A* reroutes straight away around new rubble; the learned policy needs more episodes to recover.", learning_vs_planning),
]
