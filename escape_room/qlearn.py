"""Reinforcement learning lab: tabular Q-learning on a smaller facility.

State   = (cell, which keycards are held)      Actions = up / right / down / left
Reward  = -1 per step, -5 for walking into a wall, +30 per new keycard,
          +100 for reaching the exit holding every keycard
Update  : Q(s,a) += alpha * (r + gamma * max_a' Q(s',a') - Q(s,a)), with epsilon-greedy
          exploration; epsilon starts at 1 and decays every episode.

It is used to contrast learning with planning: the learned policy works well on the map it
was trained on, but when a collapse blocks its route it fails until it is retrained, whereas
the A* planner adapts straight away.
"""
import random
from itertools import permutations

from .search import plan
from .world import RUBBLE, generate_world

ACTIONS = [(0, -1), (1, 0), (0, 1), (-1, 0)]  # up, right, down, left


class QLab:
    def __init__(self, seed=4, alpha=0.2, gamma=0.97, eps_decay=0.993, max_steps=400):
        self.seed = seed
        self.world = w = generate_world(seed, 17, 11, n_keys=2, terminal=False, gates=0, rooms=1, loops=0.22, hazard=False)
        w.gates_active = False
        self.K = len(w.keys)
        self.M = 1 << self.K  # keycard combinations
        self.full = self.M - 1
        self.key_bit = [-1] * w.N
        for i, k in enumerate(w.keys):
            self.key_bit[w.idx(k.x, k.y)] = i
        self.start_cell, self.exit_cell = w.idx(*w.start), w.idx(*w.exit)
        self.alpha, self.gamma, self.eps_decay, self.max_steps = alpha, gamma, eps_decay, max_steps
        self.eps_min = 0.05
        self.rng = random.Random(seed * 97 + 3)
        self.reset()

    def reset(self):
        self.Q = [0.0] * (self.world.N * self.M * 4)
        self.episodes = 0
        self.eps = 1.0
        self.curve = []  # one dict per episode: steps, return, success, eps
        self.collapses = []  # episode numbers at which the map changed

    def base(self, cell, mask):
        return (cell * self.M + mask) * 4

    def env_step(self, cell, mask, a):
        w = self.world
        dx, dy = ACTIONS[a]
        x, y = cell % w.W + dx, cell // w.W + dy
        if not w.is_free(x, y):
            return cell, mask, -5, False
        n = y * w.W + x
        r = -1
        b = self.key_bit[n]
        if b >= 0 and not mask & (1 << b):
            mask |= 1 << b
            r += 30
        done = n == self.exit_cell and mask == self.full
        return n, mask, r + (100 if done else 0), done

    def best_action(self, b):
        Q = self.Q
        return max(range(4), key=lambda a: Q[b + a])

    def train_episode(self):
        Q, rng = self.Q, self.rng
        cell, mask, ret, steps, done = self.start_cell, 0, 0, 0, False
        while not done and steps < self.max_steps:
            b = self.base(cell, mask)
            a = rng.randrange(4) if rng.random() < self.eps else self.best_action(b)
            cell2, mask2, r, done = self.env_step(cell, mask, a)
            nb = self.base(cell2, mask2)
            target = r if done else r + self.gamma * max(Q[nb], Q[nb + 1], Q[nb + 2], Q[nb + 3])
            Q[b + a] += self.alpha * (target - Q[b + a])
            cell, mask, ret, steps = cell2, mask2, ret + r, steps + 1
        self.episodes += 1
        self.eps = max(self.eps_min, self.eps * self.eps_decay)
        rec = dict(episode=self.episodes, steps=steps, ret=ret, success=int(done), eps=self.eps)
        self.curve.append(rec)
        return rec

    def train(self, n):
        last = None
        for _ in range(n):
            last = self.train_episode()
        return last

    def greedy(self):
        """Follow the learned policy with no exploration. Detects loops and walls."""
        cell, mask, steps = self.start_cell, 0, 0
        path, seen = [self.world.xy(cell)], set()
        while steps < self.max_steps:
            if (cell, mask) in seen:
                return dict(success=False, steps=steps, path=path, reason="the policy goes round in a loop")
            seen.add((cell, mask))
            cell2, mask2, _, done = self.env_step(cell, mask, self.best_action(self.base(cell, mask)))
            steps += 1
            if cell2 == cell:
                return dict(success=False, steps=steps, path=path, reason="the policy walks into a wall")
            cell, mask = cell2, mask2
            path.append(self.world.xy(cell))
            if done:
                return dict(success=True, steps=steps, path=path)
        return dict(success=False, steps=steps, path=path, reason="step limit")

    def optimal(self):
        """Shortest escape found by A*, trying every keycard order."""
        w = self.world
        best, expanded = None, 0
        for order in permutations(w.keys):
            stops = [w.start] + [(k.x, k.y) for k in order] + [w.exit]
            path, ok = [w.start], True
            for a, b in zip(stops, stops[1:]):
                r = plan(w, a, b, "astar")
                expanded += r.expanded
                if not r.found:
                    ok = False
                    break
                path += r.path[1:]
            if ok and (best is None or len(path) < len(best)):
                best = path
        if best is None:
            return dict(steps=None, path=[], expanded=expanded)
        return dict(steps=len(best) - 1, path=best, expanded=expanded)

    def collapse_route(self):
        """Drop rubble on the learned route, on a cell whose loss keeps everything reachable."""
        w = self.world
        route = [w.idx(x, y) for x, y in self.greedy()["path"][2:-2]]
        self.rng.shuffle(route)
        for i in route:
            if self.key_bit[i] >= 0 or i in (self.exit_cell, self.start_cell):
                continue
            d = w.bfs(self.start_cell, i)
            if d[self.exit_cell] >= 0 and all(d[w.idx(k.x, k.y)] >= 0 for k in w.keys):
                w.set_tile(i, RUBBLE)
                self.collapses.append(self.episodes)
                return w.xy(i)
        return None

    def values(self, mask):
        """Best learned value and best action of every floor cell, for the given keycards held."""
        w, Q = self.world, self.Q
        out = []
        for i in range(w.N):
            if not w.is_free(i % w.W, i // w.W):
                out.append(None)
                continue
            b = self.base(i, mask)
            q = Q[b:b + 4]
            out.append(None if not any(q) else (max(q), self.best_action(b)))
        return out
