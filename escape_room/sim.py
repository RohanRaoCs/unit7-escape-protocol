"""Simulation loop and dynamic events.

Each tick:
  1. scheduled events fire: ceiling collapses (aimed at the agent's route) and power surges
  2. the coolant leak may spread one cell
  3. sensors update: corridor distance to the drone and the fuzzy threat of every distance
  4. the agent acts (behaviour tree, or the fixed script)
  5. the drone acts (finite state machine)
  6. collisions, laser zaps and win/lose checks
A mission fails if the hull reaches 0 or the time limit (900 ticks) passes.
"""
import random

from .agent import Agent
from .csp import make_lock, mutate_lock
from .drone import Drone
from .fuzzy import make_risk_fuzzy
from .world import DIRS, FLOOR, HAZARD_COST, RUBBLE, generate_world

DYNAMICS = {
    "off": dict(label="Static", drone=False, gates=False, collapses=0, surges=0, hazard_every=0, hazard_max=0, detect=5),
    "normal": dict(label="Dynamic", drone=True, gates=True, collapses=3, surges=1, hazard_every=14, hazard_max=14, detect=5),
    "chaos": dict(label="Chaos", drone=True, gates=True, collapses=6, surges=2, hazard_every=7, hazard_max=30, detect=6),
}
MAX_TICKS = 900


class Simulation:
    def __init__(self, seed=1, algo="astar", csp="mrv_fc_ac3", fuzzy=True, time_aware=True, adaptive=True,
                 dynamics="normal", risk_threshold=68, risk_weight=30, max_ticks=MAX_TICKS, verbose=False):
        self.seed, self.dynamics, self.verbose, self.max_ticks = seed, dynamics, verbose, max_ticks
        self.config = dict(seed=seed, algo=algo, csp=csp, fuzzy=fuzzy, time_aware=time_aware, adaptive=adaptive, dynamics=dynamics)
        self.dyn = DYNAMICS[dynamics]
        self.world = generate_world(seed)
        self.world.gates_active = self.dyn["gates"]
        self.rng = random.Random(seed * 7919 + 13)
        self.lock = make_lock(random.Random(seed * 31 + 101))
        self.fuzzy = make_risk_fuzzy()
        self.risk_cache = {}
        self.sensor_key = None
        self.drone = Drone(self.world, self.dyn["detect"]) if self.dyn["drone"] else None
        self.t = 0
        self.done = False
        self.result = None
        self.logs = []
        self.fx = []  # short-lived visual effects for the GUI
        self.last_surge = None
        self.collapses = self.surges = 0
        self.hazard_cells = [i for i in range(self.world.N) if self.world.hazard[i]]
        self.schedule = sorted([(self.rng.randint(20, 300), "collapse") for _ in range(self.dyn["collapses"])]
                               + [(self.rng.randint(70, 330), "surge") for _ in range(self.dyn["surges"])])
        self.agent = None
        self.update_sensors()
        self.agent = Agent(self, algo, csp, fuzzy, time_aware, adaptive, risk_threshold, risk_weight)
        self.say("SYS", f"Seed {seed}, {self.dyn['label']} facility. Mission: {len(self.world.keys)} keycards, then the terminal, then the exit")

    def say(self, category, message):
        if self.verbose:
            self.logs.append((self.t, category, message))
            del self.logs[:-300]

    def emit(self, kind, x=0, y=0, color=None):
        if self.verbose:
            self.fx.append(dict(type=kind, x=x, y=y, color=color, t=self.t))
            del self.fx[:-40]

    # ---------- sensors ----------
    def update_sensors(self):
        """Corridor distance from every cell to the drone, and the fuzzy threat for each distance."""
        d = self.drone
        if d is None:
            return
        key = (d.x, d.y, self.world.version)
        if key != self.sensor_key:  # only recompute when the drone moved or the map changed
            self.sensor_key = key
            self.drone_dist = self.world.bfs(self.world.idx(d.x, d.y))
        alert = d.alertness()
        hull = max(0, round((self.agent.integrity if self.agent else 100) / 5) * 5)
        key = (alert, hull)
        if key not in self.risk_cache:
            self.risk_cache[key] = [self.fuzzy.infer(dict(distance=k, alert=alert, integrity=hull))["value"] for k in range(21)]
        self.risk_table = self.risk_cache[key]

    def drone_dist_at(self, cell):
        """Corridor distance from a cell to the drone, capped at 20 (20 if no drone or no path)."""
        if self.drone is None:
            return 20
        d = self.drone_dist[cell]
        return 20 if d < 0 or d > 20 else d

    def risk_at(self, cell):
        """Fuzzy threat (0-100) of a cell, given the drone's distance and mood and the agent's hull."""
        return self.risk_table[self.drone_dist_at(cell)] if self.drone else 0.0

    # ---------- main loop ----------
    def step(self):
        if self.done:
            return
        while self.schedule and self.schedule[0][0] <= self.t:
            _, event = self.schedule.pop(0)
            self.collapse() if event == "collapse" else self.surge()
        self.spread_coolant()
        self.update_sensors()
        self.agent.update()
        if self.drone:
            self.drone.update(self)
        self.t += 1
        self.interactions()
        self.update_sensors()
        self.check_end()

    def interactions(self):
        a, d, w = self.agent, self.drone, self.world
        if d and d.state != "COOLDOWN":
            same = (d.x, d.y) == (a.x, a.y)
            swapped = (d.x, d.y) == (a.px, a.py) and (d.px, d.py) == (a.x, a.y)
            if same or swapped:
                a.integrity -= 25
                a.stun = 2
                a.stats["hits"] += 1
                d.set_state("COOLDOWN", self, "hit the agent")
                d.timer = 15
                self.say("HIT", f"Drone hit UNIT-7. Hull at {a.integrity}%, stunned for 2 ticks")
                self.emit("hit", a.x, a.y)
        if w.gate_on(a.x, a.y, self.t):
            a.integrity -= 12
            a.stats["zaps"] += 1
            self.say("HIT", f"Laser gate fired while crossing ({a.x},{a.y}). Hull at {a.integrity}%")
            self.emit("zap", a.x, a.y)
            if w.is_free(a.px, a.py) and not w.gate_on(a.px, a.py, self.t):
                a.x, a.y = a.px, a.py  # knocked back

    def check_end(self):
        a, w = self.agent, self.world
        if a.integrity <= 0:
            self.end(False, "destroyed")
        elif (a.x, a.y) == w.exit and a.exit_unlocked():
            self.end(True, "escaped")
        elif self.t >= self.max_ticks:
            self.end(False, "timeout")

    def end(self, success, reason):
        s = self.agent.stats
        by = s["replans_by"]
        self.done = True
        self.result = dict(
            seed=self.seed, success=int(success), reason=reason, ticks=self.t, moves=s["moves"], waits=s["waits"],
            path_cost=s["path_cost"], expanded=s["expanded"], plan_calls=s["plan_calls"], replans=s["replans"],
            hits=s["hits"], zaps=s["zaps"], hazard_steps=s["hazard_steps"], evade_ticks=s["evade_ticks"],
            integrity=max(0, self.agent.integrity), csp_assignments=s["csp_assignments"], csp_backtracks=s["csp_backtracks"],
            hack_ticks=s["hack_ticks"], collapses=self.collapses, surges=self.surges,
            replans_blocked=by.get("route blocked", 0), replans_gate=by.get("laser gate", 0) + by.get("gate timing", 0),
            replans_threat=by.get("threat drift", 0) + by.get("drone on route", 0), replans_deviated=by.get("pushed off route", 0),
        )
        self.say("SYS", f"ESCAPED in {self.t} ticks (path cost {s['path_cost']})" if success else f"Mission failed: {reason} at tick {self.t}")

    # ---------- dynamic events ----------
    def collapse(self, by_user=False):
        """Drop rubble 2-12 steps ahead on the agent's route, never sealing off an objective."""
        w, a = self.world, self.agent
        here = w.idx(a.x, a.y)
        drone = w.idx(self.drone.x, self.drone.y) if self.drone else -1

        def ok(i):
            return (w.tiles[i] == FLOOR and not w.is_object_cell(i) and i not in (here, drone)
                    and w.objectives_reachable(here, i))

        ahead = [w.idx(x, y) for x, y in a.path_ahead(2, 12)]
        self.rng.shuffle(ahead)
        target = next((i for i in ahead if ok(i)), None)
        on_route = target is not None
        for _ in range(120):
            if target is not None:
                break
            x, y = self.rng.randint(1, w.W - 2), self.rng.randint(1, w.H - 2)
            if 3 <= abs(x - a.x) + abs(y - a.y) <= 14 and ok(w.idx(x, y)):
                target = w.idx(x, y)
        if target is None:
            return False
        w.set_tile(target, RUBBLE)
        w.hazard[target] = 0
        self.collapses += 1
        x, y = w.xy(target)
        self.say("EVENT", f"{'[you] ' if by_user else ''}Ceiling collapse at ({x},{y}){', on the planned route' if on_route else ''}")
        self.emit("collapse", x, y)
        return True

    def surge(self, by_user=False):
        """Power surge: the lock's constraints change; any known code stops working."""
        ch = mutate_lock(self.lock, self.rng)
        self.surges += 1
        self.last_surge = (self.t, ch["added"])
        self.say("EVENT", f"{'[you] ' if by_user else ''}Power surge: dials {' and '.join('D%d' % d for d in ch['changed_dials'])} rewired. "
                          f"Removed: {'; '.join(ch['removed']) or 'none'}. Added: {'; '.join(ch['added']) or 'none'}")
        if self.agent and self.agent.code_version == self.lock.version - 1:
            self.say("BT", 'The known code is now wrong, so "Vault unlocked?" fails and the tree falls back to "Crack the lock"')
        self.emit("surge")

    def spread_coolant(self):
        dy, w = self.dyn, self.world
        if not dy["hazard_every"] or self.t == 0 or self.t % dy["hazard_every"] or not self.hazard_cells or len(self.hazard_cells) >= dy["hazard_max"]:
            return
        for _ in range(8):
            c = self.rng.choice(self.hazard_cells)
            dx, dyy = self.rng.choice(DIRS)
            nx, ny = c % w.W + dx, c // w.W + dyy
            n = w.idx(nx, ny)
            if w.is_free(nx, ny) and not w.hazard[n] and not w.is_object_cell(n):
                w.hazard[n] = 1
                w.version += 1
                self.hazard_cells.append(n)
                if len(self.hazard_cells) % 4 == 0:
                    self.say("EVENT", f"Coolant leak spreading ({len(self.hazard_cells)} cells). Step cost there is {1 + HAZARD_COST}")
                return

    # ---------- operator tools (used by the GUIs) ----------
    def toggle_rubble(self, x, y):
        """Drop rubble on a floor cell, or clear rubble."""
        w, a = self.world, self.agent
        if not (0 < x < w.W - 1 and 0 < y < w.H - 1):
            return False
        i = w.idx(x, y)
        if w.tiles[i] == FLOOR and not w.is_object_cell(i) and (x, y) != (a.x, a.y):
            w.set_tile(i, RUBBLE)
            w.hazard[i] = 0
            self.say("EVENT", f"[you] Rubble dropped at ({x},{y})")
            self.emit("collapse", x, y)
        elif w.tiles[i] == RUBBLE:
            w.set_tile(i, FLOOR)
            self.say("EVENT", f"[you] Rubble cleared at ({x},{y})")
        else:
            return False
        return True

    def toggle_hazard(self, x, y):
        """Spill or mop up coolant on a floor cell."""
        w = self.world
        if not w.is_free(x, y):
            return False
        i = w.idx(x, y)
        w.hazard[i] ^= 1
        w.version += 1
        if w.hazard[i]:
            self.hazard_cells.append(i)
        else:
            self.hazard_cells = [c for c in self.hazard_cells if c != i]
        self.say("EVENT", f"[you] Coolant {'spilled' if w.hazard[i] else 'mopped up'} at ({x},{y})")
        return True

    def move_drone(self, x, y):
        if self.drone is None or not self.world.is_free(x, y):
            return False
        d = self.drone
        d.x, d.y, d.px, d.py = x, y, x, y
        self.say("EVENT", f"[you] Drone moved to ({x},{y})")
        self.update_sensors()
        return True

    def alert_drone(self):
        """Sound the alarm: the drone switches straight to Chase."""
        if self.drone is None:
            return False
        self.drone.set_state("CHASE", self, "alarm")
        self.drone.chase_ticks = self.drone.lost = 0
        self.update_sensors()
        return True


def run_episode(**config):
    sim = Simulation(**config)
    while not sim.done:
        sim.step()
    return sim.result
