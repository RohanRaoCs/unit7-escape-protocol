"""UNIT-7, the escape agent.

Decisions  : a behaviour tree re-evaluated from the root every tick:
               Survive > Escape > Crack the lock > Collect keycards > Hold position
Navigation : A* (or Dijkstra / greedy / BFS) over a cost map that adds the fuzzy threat of
             each cell, optionally planning in space and time around the laser gates.
Monitoring : every tick the rest of the route is re-checked. A new plan is made when rubble
             blocks it, a laser gate would fire on it, the agent was pushed off it, or the
             threat along it has grown well beyond what was planned for.
Puzzle     : the CSP solver cracks the vault lock; a power surge invalidates the code.

With fuzzy=False the threat is a crisp rule ("flee if the drone is chasing within 3 cells")
and cells next to the drone are simply blocked. With adaptive=False the agent is the "fixed
script" baseline: it plans the whole mission once at the start and follows it blindly.
"""
import math
from itertools import permutations

from . import bt
from .csp import CSP_MODES, solve
from .search import plan


class Agent:
    def __init__(self, sim, algo="astar", csp="mrv_fc_ac3", fuzzy=True, time_aware=True, adaptive=True,
                 risk_threshold=68, risk_weight=30):
        self.sim, self.w = sim, sim.world
        self.algo, self.csp_mode, self.fuzzy, self.time_aware, self.adaptive = algo, csp, fuzzy, time_aware, adaptive
        self.risk_threshold, self.risk_weight = risk_threshold, risk_weight
        self.x, self.y = self.w.start
        self.px, self.py = self.x, self.y
        self.integrity = 100
        self.keys = 0
        self.code_version = -1  # lock version the agent has cracked
        self.code = None
        self.plan = None  # {"tag", "goal", "path", "cum", "idx", "risk_check"}
        self.last_search = None  # (expanded cells, tick, reason) for drawing
        self.hack = None  # lock-solving progress
        self.last_hack = None
        self.target_key = None
        self.target_at = -999
        self.stun = 0
        self.evading = False
        self.risk = 0.0
        self.failed_at = {}
        self.mode = "starting"
        self.stats = dict(moves=0, waits=0, path_cost=0, expanded=0, plan_calls=0, replans=0, plan_ms=0.0,
                          hits=0, zaps=0, hazard_steps=0, evade_ticks=0, csp_assignments=0, csp_backtracks=0,
                          csp_checks=0, hack_ticks=0, replans_by={})
        if adaptive:
            self.tree = self.build_tree()
        else:
            self.tree = None
            self.build_script()

    # ---------- behaviour tree ----------
    def build_tree(self):
        w = self.w
        return bt.selector("Root", [
            bt.sequence("Survive", [
                bt.condition("Threat high? (fuzzy)" if self.fuzzy else "Drone chasing nearby?", self.threat_high),
                bt.action("Evade drone", self.evade),
            ]),
            bt.sequence("Escape", [
                bt.condition("Vault unlocked?", self.exit_unlocked),
                bt.action("Go to exit", lambda: self.navigate(w.exit, "exit")),
            ]),
            bt.sequence("Crack the lock", [
                bt.condition("All keycards held?", lambda: self.keys == len(w.keys)),
                bt.action("Go to terminal", lambda: self.navigate(w.terminal, "terminal")),
                bt.action("Solve lock (CSP)", self.solve_lock),
            ]),
            bt.sequence("Collect keycards", [
                bt.action("Choose keycard order", self.choose_key),
                bt.action("Go to keycard", lambda: self.navigate((self.target_key.x, self.target_key.y), "keycard " + self.target_key.name)),
            ]),
            bt.action("Hold position", self.hold),
        ])

    def update(self):
        self.px, self.py = self.x, self.y
        if self.stun > 0:
            self.stun -= 1
            self.mode = "stunned"
        elif self.adaptive:
            self.tree.run(self.sim.t)
        else:
            self.script_step()

    def exit_unlocked(self):
        return self.keys == len(self.w.keys) and self.code_version == self.sim.lock.version

    def threat_high(self):
        sim = self.sim
        if sim.drone is None:
            self.risk = 0.0
            return False
        here = self.w.idx(self.x, self.y)
        self.risk = sim.risk_at(here)
        if self.fuzzy:
            # Hysteresis: once evading, keep going until the threat has dropped a little further.
            yes = self.risk >= (self.risk_threshold - 12 if self.evading else self.risk_threshold)
        else:
            yes = sim.drone.state == "CHASE" and sim.drone_dist_at(here) <= 3
        if yes != self.evading:
            sim.say("BT", f"Threat {self.risk:.0f}/100: switching to Evade" if yes else f"Threat down to {self.risk:.0f}: resuming the mission")
            self.evading = yes
        return yes

    def hold(self):
        self.mode = "holding (no route right now)"
        self.stats["waits"] += 1
        return bt.RUNNING

    # ---------- navigation with A* and replanning ----------
    def cost_fn(self):
        w, sim = self.w, self.sim
        if sim.drone is None:
            return w.cell_cost
        if self.fuzzy:
            weight = self.risk_weight

            def cost(i):
                r = sim.risk_at(i)
                return w.cell_cost(i) + ((r - 15) / 85 * weight if r > 15 else 0)
            return cost
        return lambda i: math.inf if sim.drone_dist_at(i) <= 1 else w.cell_cost(i)  # keep clear of the drone

    def replan(self, goal, tag, why):
        sim, st = self.sim, self.stats
        r = plan(self.w, (self.x, self.y), goal, self.algo, self.cost_fn(), time_aware=self.time_aware, t0=sim.t)
        st["plan_calls"] += 1
        st["expanded"] += r.expanded
        st["plan_ms"] += r.ms
        if why != "new goal":
            st["replans"] += 1
            st["replans_by"][why] = st["replans_by"].get(why, 0) + 1
        self.last_search = (r.order, sim.t, why)
        if not r.found:
            self.plan = None
            self.failed_at[tag] = sim.t
            sim.say("PLAN", f"No route to {tag} right now ({r.expanded} states searched), waiting")
            return False
        self.plan = {"tag": tag, "goal": goal, "path": r.path, "cum": r.cum, "idx": 0, "risk_check": sim.t}
        if why != "new goal":
            sim.emit("replan", self.x, self.y)
        label = "Plan" if why == "new goal" else f"Replan ({why})"
        sim.say("PLAN", f"{label} to {tag}: {len(r.path) - 1} steps, cost {r.cost:.1f}, {r.expanded} states searched")
        return True

    def check_plan(self, p):
        """Why the current plan can no longer be followed, or None if it is still fine."""
        w, sim, t = self.w, self.sim, self.sim.t
        if p["path"][p["idx"]] != (self.x, self.y):
            return "pushed off route"
        crisp = self.cost_fn() if not self.fuzzy and sim.drone else None
        for k, (x, y) in enumerate(p["path"][p["idx"] + 1:], 1):
            if not w.is_free(x, y):
                return "route blocked"
            if self.time_aware:
                if w.gate_on(x, y, t + k):
                    return "gate timing"
            elif w.gate_on(x, y, t):
                return "laser gate"
            if crisp and crisp(w.idx(x, y)) == math.inf:
                return "drone on route"
        if self.fuzzy and sim.drone and t - p["risk_check"] >= 2:
            p["risk_check"] = t
            cost = self.cost_fn()
            now = sum(cost(w.idx(x, y)) for x, y in p["path"][p["idx"] + 1:])
            planned = p["cum"][-1] - p["cum"][p["idx"]]
            if now > planned * 1.2 + 2:
                return "threat drift"
        return None

    def navigate(self, goal, tag):
        if (self.x, self.y) == tuple(goal):
            self.plan = None
            return bt.SUCCESS
        self.mode = "going to " + tag
        if self.plan is None or self.plan["tag"] != tag:
            if self.sim.t - self.failed_at.get(tag, -99) < 3:  # don't re-search every tick
                return bt.FAILURE
            if not self.replan(goal, tag, "new goal"):
                return bt.FAILURE
        else:
            why = self.check_plan(self.plan)
            if why and not self.replan(goal, tag, why):
                return bt.FAILURE
        return self.follow_plan(self.plan)

    def follow_plan(self, p):
        w, t = self.w, self.sim.t
        if p["idx"] + 1 >= len(p["path"]):
            return bt.SUCCESS
        nx, ny = p["path"][p["idx"] + 1]
        if (nx, ny) == (self.x, self.y):  # a planned wait (space-time plan)
            p["idx"] += 1
            self.stats["waits"] += 1
            self.mode = "waiting for a laser gate"
            return bt.RUNNING
        gate = w.gate_on(nx, ny, t + 1) if self.time_aware else w.gate_on(nx, ny, t)
        if not w.is_free(nx, ny) or gate:
            self.stats["waits"] += 1
            return bt.RUNNING
        self.move_to(nx, ny)
        p["idx"] += 1
        return bt.RUNNING

    def move_to(self, x, y):
        w, st = self.w, self.stats
        i = w.idx(x, y)
        self.x, self.y = x, y
        st["moves"] += 1
        st["path_cost"] += w.cell_cost(i)
        if w.hazard[i]:
            self.integrity -= 3  # coolant damages the hull
            st["hazard_steps"] += 1
        key = w.key_at(x, y)
        if key:
            key.taken = True
            self.keys += 1
            if self.target_key is key:
                self.target_key = None
            self.sim.say("KEY", f"Picked up the {key.name} keycard ({self.keys}/{len(w.keys)})")
            self.sim.emit("key", x, y, key.color)

    def path_ahead(self, start, end):
        if self.adaptive:
            return self.plan["path"][self.plan["idx"] + start:self.plan["idx"] + end] if self.plan else []
        sc = self.script
        if sc["leg"] >= len(sc["legs"]):
            return []
        return sc["legs"][sc["leg"]]["path"][sc["i"] + start:sc["i"] + end]

    # ---------- keycard order: try every order, keep the shortest tour ----------
    def best_tour(self, remaining):
        if not remaining:
            return []
        w = self.w
        from_me = w.bfs(w.idx(self.x, self.y))
        from_key = [w.bfs(w.idx(k.x, k.y)) for k in remaining]
        end = w.idx(*(w.terminal or w.exit))
        best, best_len = None, math.inf
        for order in permutations(range(len(remaining))):
            legs = [from_me[w.idx(remaining[order[0]].x, remaining[order[0]].y)]]
            legs += [from_key[a][w.idx(remaining[b].x, remaining[b].y)] for a, b in zip(order, order[1:])]
            legs.append(from_key[order[-1]][end])
            if min(legs) >= 0 and sum(legs) < best_len:
                best, best_len = order, sum(legs)
        if best is None:  # some keycard is cut off for now: go for the nearest reachable one
            return sorted((k for k in remaining if from_me[w.idx(k.x, k.y)] >= 0), key=lambda k: from_me[w.idx(k.x, k.y)])
        return [remaining[i] for i in best]

    def choose_key(self):
        remaining = [k for k in self.w.keys if not k.taken]
        if not remaining:
            return bt.FAILURE
        if self.target_key and not self.target_key.taken and self.sim.t - self.target_at < 30:
            return bt.SUCCESS
        order = self.best_tour(remaining)
        if not order:
            self.target_key = None
            return bt.FAILURE
        if order[0] is not self.target_key:
            self.sim.say("BT", f"Best keycard order ({len(order)}! orders tried): " + " -> ".join(k.name for k in order) + " -> terminal")
        self.target_key, self.target_at = order[0], self.sim.t
        return bt.SUCCESS

    # ---------- crack the lock with the CSP solver ----------
    def solve_lock(self):
        sim, lock, st = self.sim, self.sim.lock, self.stats
        if self.code_version == lock.version:
            return bt.SUCCESS
        self.mode = "cracking the lock"
        if self.hack is None or self.hack["version"] != lock.version:
            if self.hack:
                sim.say("CSP", "The clues changed while solving: starting again")
            r = solve(lock, self.csp_mode, trace=sim.verbose)
            st["csp_assignments"] += r.assignments
            st["csp_backtracks"] += r.backtracks
            st["csp_checks"] += r.checks
            # Dialling in takes 1 tick per 4 solver assignments, so a smarter solver escapes sooner.
            self.hack = self.last_hack = {"version": lock.version, "result": r, "progress": 0, "need": max(2, math.ceil(r.assignments / 4))}
            sim.say("CSP", f"{CSP_MODES[self.csp_mode]}: {len(lock.constraints)} clues, {r.assignments} assignments, "
                           f"{r.backtracks} backtracks, {r.prunes} values pruned -> {self.hack['need']} ticks to dial in")
        self.hack["progress"] += 1
        st["hack_ticks"] += 1
        if self.hack["progress"] < self.hack["need"]:
            return bt.RUNNING
        self.code_version, self.code = lock.version, self.hack["result"].solution
        self.hack = None
        sim.say("CSP", f"Lock cracked: {'-'.join(map(str, self.code))}. The exit is open")
        sim.emit("unlock")
        return bt.SUCCESS

    # ---------- evade: move toward the safest cell within 5 steps ----------
    def evade(self):
        w, sim = self.w, self.sim
        start = w.idx(self.x, self.y)
        drone = w.idx(sim.drone.x, sim.drone.y) if sim.drone else -1
        dist, parent = {start: 0}, {}
        queue = [start]

        def score(c):
            danger = sim.risk_at(c) if self.fuzzy else 100 - 5 * min(20, sim.drone_dist_at(c))
            return danger + 3 * dist[c] + (8 if w.hazard[c] else 0)

        best, best_score = start, score(start)
        for c in queue:
            if dist[c] >= 5:
                continue
            for n in (c + 1, c - 1, c + w.W, c - w.W):
                if n in dist or n == drone or not w.passable(n % w.W, n // w.W, sim.t + 1):
                    continue
                dist[n], parent[n] = dist[c] + 1, c
                queue.append(n)
                s = score(n)
                if s < best_score:
                    best, best_score = n, s
        self.stats["evade_ticks"] += 1
        self.mode = "evading the drone"
        if best == start:
            self.stats["waits"] += 1
            return bt.RUNNING
        while parent[best] != start:
            best = parent[best]
        self.move_to(*w.xy(best))
        return bt.RUNNING

    # ---------- baseline: fixed script ----------
    def build_script(self):
        w = self.w
        stops = [((k.x, k.y), "key") for k in self.best_tour(w.keys)] + [(w.terminal, "terminal"), (w.exit, "exit")]
        self.script = {"legs": [], "leg": 0, "i": 0}
        here = (self.x, self.y)
        for pos, kind in stops:
            r = plan(w, here, pos, self.algo, ignore_gates=True)
            self.stats["plan_calls"] += 1
            self.stats["expanded"] += r.expanded
            self.script["legs"].append({"path": r.path if r.found else [here], "kind": kind})
            here = pos
        moves = sum(len(leg["path"]) - 1 for leg in self.script["legs"])
        self.sim.say("PLAN", f"Fixed script planned once from the blueprint: {moves} moves. It will not replan")

    def script_step(self):
        sc, sim = self.script, self.sim
        while sc["leg"] < len(sc["legs"]) and sc["i"] >= len(sc["legs"][sc["leg"]]["path"]) - 1:
            kind = sc["legs"][sc["leg"]]["kind"]
            if kind == "terminal" and self.code_version != sim.lock.version:
                self.solve_lock()
                return
            if kind == "exit":
                self.mode = "stuck at a locked exit"
                self.stats["waits"] += 1
                return
            sc["leg"] += 1
            sc["i"] = 0
        if sc["leg"] >= len(sc["legs"]):
            return
        nx, ny = sc["legs"][sc["leg"]]["path"][sc["i"] + 1]
        if not self.w.passable(nx, ny, sim.t):
            self.mode = "blocked: the script has no alternative"
            self.stats["waits"] += 1
            return
        self.move_to(nx, ny)
        sc["i"] += 1
        self.mode = "following the fixed script"
