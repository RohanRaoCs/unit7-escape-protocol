"""Path planning: A*, Dijkstra, greedy best-first and breadth-first search behind one function.

- A*       : priority = g + h, with h = Manhattan distance (admissible, since every step costs >= 1)
- Dijkstra : priority = g (uniform-cost search, no heuristic)
- Greedy   : priority = h only (fast, but ignores what the path has cost so far)
- BFS      : first-in first-out queue; ignores step costs (fewest steps, not cheapest path)

Two state spaces:
- snapshot   : state = cell. Laser gates are frozen in their state at planning time t0.
- space-time : state = (cell, time mod GATE_PERIOD). A WAIT action is allowed and each arrival
               is checked against the gate timetable at the real arrival time, so the agent
               can time its way through a gate instead of detouring.
"""
import heapq
import math
import time
from collections import deque
from dataclasses import dataclass, field

from .world import FLOOR, GATE_ON, GATE_PERIOD

ALGOS = {"astar": "A*", "dijkstra": "Dijkstra", "greedy": "Greedy best-first", "bfs": "Breadth-first"}


@dataclass
class PlanResult:
    found: bool
    path: list = field(default_factory=list)  # list of (x, y), start first; a repeated cell is a wait
    cum: list = field(default_factory=list)  # cumulative cost along the path
    cost: float = math.inf
    expanded: int = 0  # states taken off the frontier and expanded
    order: list = field(default_factory=list)  # cells in the order they were expanded
    ms: float = 0.0
    time_aware: bool = False


def plan(world, start, goal, algo="astar", cost_fn=None, time_aware=False, t0=0, ignore_gates=False, max_expand=200000):
    """Plan from start (x, y) to goal (x, y). cost_fn(cell) gives the cost of entering a cell;
    returning math.inf means "never enter this cell"."""
    clock = time.perf_counter()
    cost_fn = cost_fn or world.cell_cost
    W, N, tiles = world.W, world.N, world.tiles
    gates = world.gates_active and bool(world.gates) and not ignore_gates
    time_aware = time_aware and gates
    P = GATE_PERIOD if time_aware else 1
    gx, gy = goal
    goal_cell = world.idx(*goal)
    s0 = world.idx(*start) * P + (t0 % P if time_aware else 0)
    inf = math.inf

    # Step cost of entering each cell, computed once per search (inf = wall or forbidden).
    cost = [cost_fn(i) if tiles[i] == FLOOR else inf for i in range(N)]
    # Manhattan distance to the goal; A* and greedy add a tiny tie-break on g.
    h = [abs(i % W - gx) + abs(i // W - gy) for i in range(N)] if algo in ("astar", "greedy") else None
    # Which ticks of the gate cycle each gate cell is on (None = never blocked).
    gate_on = None
    if gates:
        gate_on = [None] * N
        for gt in world.gates:
            if time_aware:
                gate_on[world.idx(gt.x, gt.y)] = [(t + gt.phase) % GATE_PERIOD < GATE_ON for t in range(GATE_PERIOD)]
            elif world.gate_on(gt.x, gt.y, t0):
                cost[world.idx(gt.x, gt.y)] = inf  # snapshot: frozen in its current state

    S = N * P
    g = [inf] * S
    steps = [0] * S if time_aware else None
    parent = [-1] * S
    closed = bytearray(S)
    order = []
    moves = (1, -1, W, -W, 0) if time_aware else (1, -1, W, -W)
    first_wins = algo in ("bfs", "greedy")
    g[s0] = 0
    frontier = deque([s0]) if algo == "bfs" else [(0, 0, s0)]
    pop, push = heapq.heappop, heapq.heappush
    tie = expanded = 0
    found = -1

    while frontier:
        s = frontier.popleft() if algo == "bfs" else pop(frontier)[2]
        if closed[s]:
            continue
        closed[s] = 1
        expanded += 1
        c = s // P
        order.append(c)
        if c == goal_cell:
            found = s
            break
        if expanded >= max_expand:
            break
        gs = g[s]
        if time_aware:
            phase = s % P
            nphase = (phase + 1) % P
            gate_tick = (t0 + steps[s] + 1) % GATE_PERIOD
        for m in moves:
            n = c + m
            step = cost[n]
            if step == inf:
                continue
            if time_aware:
                cycle = gate_on[n]
                if cycle is not None and cycle[gate_tick]:
                    continue
                ns = n * P + nphase
            else:
                ns = n
            if closed[ns]:
                continue
            new_g = gs + step
            if first_wins:
                if g[ns] != inf:
                    continue
            elif new_g >= g[ns]:
                continue
            g[ns] = new_g
            parent[ns] = s
            if time_aware:
                steps[ns] = steps[s] + 1
            if algo == "bfs":
                frontier.append(ns)
            else:
                tie += 1
                if algo == "astar":
                    pri = new_g + h[n] - new_g * 1e-6  # ties go to the deeper node, which saves expansions
                elif algo == "greedy":
                    pri = h[n] + new_g * 1e-6
                else:
                    pri = new_g
                push(frontier, (pri, tie, ns))

    result = PlanResult(found=found >= 0, expanded=expanded, order=order, time_aware=time_aware)
    if found >= 0:
        s = found
        while s >= 0:
            result.path.append(world.xy(s // P))
            s = parent[s]
        result.path.reverse()
        total = 0
        result.cum.append(0)
        for x, y in result.path[1:]:
            total += cost[world.idx(x, y)]
            result.cum.append(total)
        result.cost = g[found]
    result.ms = (time.perf_counter() - clock) * 1000
    return result
