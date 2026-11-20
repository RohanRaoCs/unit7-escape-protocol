"""Security drone: a moving obstacle controlled by a finite state machine.

    PATROL   --sees the agent-->                              ALERT
    ALERT    --still sees it after 2 ticks-->                 CHASE
    ALERT    --reached the last-seen spot and found nothing--> PATROL
    CHASE    --lost sight for 6 ticks, or 30-tick battery-->  COOLDOWN
    any      --touches the agent (agent loses 25% hull)-->    COOLDOWN
    COOLDOWN --timer runs out-->                              PATROL

"Sees" means within the detection range (Manhattan distance) with a clear line of sight.
Alertness (used by the fuzzy threat controller) depends on the state.
"""
ALERTNESS = {"PATROL": 0.2, "ALERT": 0.7, "CHASE": 1.0, "COOLDOWN": 0.05}


class Drone:
    def __init__(self, world, detect=5):
        self.w = world
        self.waypoints = world.drone_waypoints or [world.exit]
        self.x, self.y = self.waypoints[0]
        self.px, self.py = self.x, self.y
        self.wp = 1 % len(self.waypoints)
        self.state = "PATROL"
        self.detect = detect
        self.timer = self.chase_ticks = self.lost = self.transitions = 0
        self.last_seen = None
        self.field_key = self.field = None

    def alertness(self):
        return ALERTNESS[self.state]

    def line_of_sight(self, x1, y1):
        """Bresenham line from the drone to (x1, y1); walls and rubble block it."""
        x0, y0 = self.x, self.y
        dx, dy = abs(x1 - x0), -abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = dx + dy
        while (x0, y0) != (x1, y1):
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy
            if not self.w.is_free(x0, y0):
                return False
        return True

    def sees(self, agent):
        return (self.state != "COOLDOWN"
                and abs(agent.x - self.x) + abs(agent.y - self.y) <= self.detect
                and self.line_of_sight(agent.x, agent.y))

    def step_toward(self, tx, ty):
        """Move one cell along a shortest path toward (tx, ty)."""
        w = self.w
        key = (tx, ty, w.version)
        if key != self.field_key:  # reuse the distance field while the target and map are unchanged
            self.field_key, self.field = key, w.bfs(w.idx(tx, ty))
        dist = self.field
        here = dist[w.idx(self.x, self.y)]
        if here <= 0:
            return
        for nx, ny in ((self.x + 1, self.y), (self.x - 1, self.y), (self.x, self.y + 1), (self.x, self.y - 1)):
            if w.is_free(nx, ny) and dist[w.idx(nx, ny)] == here - 1:
                self.x, self.y = nx, ny
                return

    def set_state(self, state, sim, why):
        if state != self.state:
            self.state = state
            self.transitions += 1
            if sim:
                sim.say("DRONE", f"{state.title()} ({why})")

    def update(self, sim):
        t, agent = sim.t, sim.agent
        self.px, self.py = self.x, self.y
        wx, wy = self.waypoints[self.wp]
        if not self.w.is_free(wx, wy) or (self.x, self.y) == (wx, wy):  # reached it, or it was buried
            self.wp = (self.wp + 1) % len(self.waypoints)
            wx, wy = self.waypoints[self.wp]

        if self.state == "PATROL":
            if self.sees(agent):
                self.set_state("ALERT", sim, "agent spotted")
                self.timer = 2
                self.last_seen = (agent.x, agent.y)
            elif t % 2 == 0:  # patrols at half speed
                self.step_toward(wx, wy)
        elif self.state == "ALERT":
            # Investigate: drift toward where the agent was last seen.
            if self.sees(agent):
                self.last_seen = (agent.x, agent.y)
            if self.last_seen:
                self.step_toward(*self.last_seen)
            self.timer -= 1
            if self.timer <= 0 and self.sees(agent):
                self.set_state("CHASE", sim, "target confirmed")
                self.chase_ticks = self.lost = 0
            elif self.timer <= -6 or (self.timer <= 0 and (self.x, self.y) == self.last_seen):
                self.set_state("PATROL", sim, "search found nothing")
        elif self.state == "CHASE":
            self.chase_ticks += 1
            if t % 3 != 2:  # chases at two-thirds speed
                self.step_toward(agent.x, agent.y)
            self.lost = 0 if self.sees(agent) else self.lost + 1
            if self.lost > 5 or self.chase_ticks > 30:
                self.set_state("COOLDOWN", sim, "lost the agent" if self.lost > 5 else "battery low")
                self.timer = 12
        else:  # COOLDOWN
            if t % 2 == 0:
                self.step_toward(wx, wy)
            self.timer -= 1
            if self.timer <= 0:
                self.set_state("PATROL", sim, "recharged")
