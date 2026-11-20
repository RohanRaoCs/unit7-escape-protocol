"""World model: a seeded grid facility with walls, rubble, keycards, a terminal, an exit,
laser gates and coolant.

- Tiles are FLOOR, WALL or RUBBLE (rubble is a wall that appears during a run).
- Laser gates sit in corridors and are ON for GATE_ON ticks out of every GATE_PERIOD. The
  timetable is known to the agent, which is what makes planning in time possible.
- Coolant cells cost more to cross, so "path cost" is different from "number of steps".
"""
import random
from collections import deque
from dataclasses import dataclass

FLOOR, WALL, RUBBLE = 0, 1, 2
DIRS = [(1, 0), (-1, 0), (0, 1), (0, -1)]
GATE_PERIOD, GATE_ON = 10, 4
HAZARD_COST = 5  # a coolant cell costs 1 + 5
KEY_DEFS = [("ROSE", "#db2777"), ("GOLD", "#ca8a04"), ("GREEN", "#059669"), ("SKY", "#0284c7")]


@dataclass
class Key:
    id: int
    x: int
    y: int
    name: str
    color: str
    taken: bool = False


@dataclass
class Gate:
    x: int
    y: int
    phase: int


class World:
    def __init__(self, width, height):
        self.W, self.H, self.N = width, height, width * height
        self.tiles = [WALL] * self.N
        self.hazard = [0] * self.N
        self.gate_idx = [-1] * self.N
        self.gates = []
        self.gates_active = True
        self.keys = []
        self.start = (1, 1)
        self.exit = None
        self.terminal = None
        self.hazard_source = None
        self.drone_waypoints = []
        self.version = 0  # increases whenever the map changes

    def idx(self, x, y):
        return y * self.W + x

    def xy(self, i):
        return i % self.W, i // self.W

    def inside(self, x, y):
        return 0 <= x < self.W and 0 <= y < self.H

    def is_free(self, x, y):
        return 0 <= x < self.W and 0 <= y < self.H and self.tiles[y * self.W + x] == FLOOR

    def gate_on(self, x, y, t):
        if not self.gates_active:
            return False
        g = self.gate_idx[y * self.W + x]
        return g >= 0 and (t + self.gates[g].phase) % GATE_PERIOD < GATE_ON

    def passable(self, x, y, t):
        return self.is_free(x, y) and not self.gate_on(x, y, t)

    def cell_cost(self, i):
        return 1 + (HAZARD_COST if self.hazard[i] else 0)

    def gate_orientation(self, g):
        """'v' when the beam is vertical (the corridor runs left-right), otherwise 'h'."""
        return "v" if self.is_free(g.x - 1, g.y) or self.is_free(g.x + 1, g.y) else "h"

    def bfs(self, start, blocked=-1, t=None):
        """Distance in steps from cell index `start` to every cell (-1 = unreachable).
        Laser gates are ignored unless a time t is given. The border is always wall, so
        neighbours can be found with index offsets."""
        tiles, W = self.tiles, self.W
        dist = [-1] * self.N
        dist[start] = 0
        queue = deque([start])
        offsets = (1, -1, W, -W)
        check_gates = t is not None and self.gates_active and self.gates
        while queue:
            c = queue.popleft()
            d = dist[c] + 1
            for o in offsets:
                n = c + o
                if dist[n] < 0 and tiles[n] == FLOOR and n != blocked:
                    if check_gates and self.gate_on(n % W, n // W, t):
                        continue
                    dist[n] = d
                    queue.append(n)
        return dist

    def objectives(self):
        """Cells the agent still needs: untaken keycards, the terminal and the exit."""
        cells = [self.idx(k.x, k.y) for k in self.keys if not k.taken]
        if self.terminal:
            cells.append(self.idx(*self.terminal))
        return cells + [self.idx(*self.exit)]

    def objectives_reachable(self, from_cell, blocked_cell):
        dist = self.bfs(from_cell, blocked_cell)
        return all(dist[i] >= 0 for i in self.objectives())

    def is_object_cell(self, i):
        pos = self.xy(i)
        if pos in (self.start, self.exit, self.terminal) or any((k.x, k.y) == pos for k in self.keys):
            return True
        return self.gate_idx[i] >= 0

    def key_at(self, x, y):
        return next((k for k in self.keys if not k.taken and k.x == x and k.y == y), None)

    def set_tile(self, i, value):
        if self.tiles[i] != value:
            self.tiles[i] = value
            self.version += 1


def generate_world(seed, width=31, height=21, n_keys=3, terminal=True, gates=4, rooms=3, loops=0.16, hazard=True):
    rng = random.Random(seed)
    w = World(width, height)
    w.seed = seed
    T, idx = w.tiles, w.idx

    # 1. Maze by randomised depth-first carving on odd coordinates.
    stack = [(1, 1)]
    T[idx(1, 1)] = FLOOR
    while stack:
        cx, cy = stack[-1]
        options = [(cx + 2 * dx, cy + 2 * dy, dx, dy) for dx, dy in DIRS
                   if 0 < cx + 2 * dx < width - 1 and 0 < cy + 2 * dy < height - 1 and T[idx(cx + 2 * dx, cy + 2 * dy)] == WALL]
        if not options:
            stack.pop()
            continue
        nx, ny, dx, dy = rng.choice(options)
        T[idx(cx + dx, cy + dy)] = FLOOR
        T[idx(nx, ny)] = FLOOR
        stack.append((nx, ny))

    # 2. Remove some walls to create loops, so a blocked route usually has an alternative.
    for y in range(1, height - 1):
        for x in range(1, width - 1):
            if T[idx(x, y)] != WALL:
                continue
            horizontal = T[idx(x - 1, y)] == FLOOR and T[idx(x + 1, y)] == FLOOR and T[idx(x, y - 1)] == WALL and T[idx(x, y + 1)] == WALL
            vertical = T[idx(x, y - 1)] == FLOOR and T[idx(x, y + 1)] == FLOOR and T[idx(x - 1, y)] == WALL and T[idx(x + 1, y)] == WALL
            if (horizontal or vertical) and rng.random() < loops:
                T[idx(x, y)] = FLOOR

    # 3. A few open rooms (labs).
    for _ in range(rooms):
        rw, rh = rng.randint(3, 5), rng.randint(3, 4)
        rx, ry = rng.randint(1, width - 1 - rw), rng.randint(1, height - 1 - rh)
        for y in range(ry, ry + rh):
            for x in range(rx, rx + rw):
                T[idx(x, y)] = FLOOR

    # 4. Objects: exit at the farthest reachable cell; keycards and terminal spread far apart.
    start = idx(1, 1)
    dist = w.bfs(start)
    far = max(range(w.N), key=lambda i: dist[i])
    w.exit = w.xy(far)
    candidates = [i for i in range(w.N) if dist[i] >= dist[far] // 4 and i not in (start, far)]

    def manhattan(a, b):
        return abs(a % width - b % width) + abs(a // width - b // width)

    anchors = [start, far]

    def pick_spread():
        ranked = sorted(candidates, key=lambda c: -min(manhattan(a, c) for a in anchors))[:5]
        cell = rng.choice(ranked)
        candidates.remove(cell)
        anchors.append(cell)
        return cell

    for k in range(n_keys):
        name, color = KEY_DEFS[k % len(KEY_DEFS)]
        x, y = w.xy(pick_spread())
        w.keys.append(Key(k, x, y, name, color))
    if terminal:
        w.terminal = w.xy(pick_spread())

    # 5. Laser gates in corridors, never on a cell that would cut off an objective.
    gate_cands = candidates.copy()
    rng.shuffle(gate_cands)
    for i in gate_cands:
        if len(w.gates) >= gates:
            break
        x, y = w.xy(i)
        lr = w.is_free(x - 1, y) and w.is_free(x + 1, y) and not w.is_free(x, y - 1) and not w.is_free(x, y + 1)
        ud = w.is_free(x, y - 1) and w.is_free(x, y + 1) and not w.is_free(x - 1, y) and not w.is_free(x + 1, y)
        if dist[i] < 4 or not (lr or ud):
            continue
        if any(manhattan(w.idx(g.x, g.y), i) < 5 for g in w.gates):
            continue
        if not w.objectives_reachable(start, i):
            continue
        w.gate_idx[i] = len(w.gates)
        w.gates.append(Gate(x, y, rng.randint(0, GATE_PERIOD - 1)))
        candidates.remove(i)

    # 6. Coolant leak source and drone patrol waypoints, away from the start.
    far_cells = [i for i in candidates if dist[i] >= 8]
    rng.shuffle(far_cells)
    if hazard and far_cells:
        w.hazard[far_cells[0]] = 1
        w.hazard_source = w.xy(far_cells[0])
    w.drone_waypoints = [w.xy(i) for i in far_cells[1:5]]
    return w
