"""Constraint Satisfaction: the vault lock.

Variables  : D1..D5 (lock dials), each with domain {0..9}
Constraints: "all dials differ", sometimes a checksum, plus clues such as "D1 is odd",
             "D3 > 4", "D2 + D4 = 11", "D3 > D5" and "|D1 - D2| = 3".
The generator adds true clues until exactly one code fits, then removes every clue it can
without losing uniqueness, so each puzzle is fair and minimal.

Four solvers are compared:
  bt          plain backtracking (assign dials in order, undo on conflict)
  fc          backtracking + forward checking
  mrv_fc      + minimum-remaining-values ordering (ties broken by degree)
  mrv_fc_ac3  + node consistency and AC-3 arc consistency before the search starts
A power surge (mutate_lock) changes two dials and their clues while the agent is running.
"""
import time
from dataclasses import dataclass, field

PRIMES = {2, 3, 5, 7}
CSP_MODES = {
    "bt": "Plain backtracking",
    "fc": "Backtracking + forward checking",
    "mrv_fc": "MRV + forward checking",
    "mrv_fc_ac3": "MRV + FC + AC-3",
}
UNSET = -1


@dataclass
class Constraint:
    vars: tuple
    text: str
    test: callable = None  # called only when every variable in `vars` is assigned
    kind: str = "clue"  # "alldiff" | "sum" | "clue"
    total: int = 0  # for the checksum

    def ok(self, a):
        """False only if the values assigned so far already break this constraint."""
        if self.kind == "alldiff":
            values = [v for v in a if v != UNSET]
            return len(values) == len(set(values))
        if self.kind == "sum":
            unset = sum(1 for v in a if v == UNSET)
            s = sum(v for v in a if v != UNSET)
            return s == self.total if unset == 0 else s <= self.total <= s + 9 * unset
        if any(a[v] == UNSET for v in self.vars):
            return True
        return self.test(*(a[v] for v in self.vars))


def D(i):
    return f"D{i + 1}"


def all_diff(n):
    return Constraint(tuple(range(n)), "All dials differ", kind="alldiff")


def checksum(n, total):
    return Constraint(tuple(range(n)), f"Checksum D1+...+D{n} = {total}", kind="sum", total=total)


def random_clue(rng, s):
    """A random clue that is true for the secret code s, or None."""
    i, j = rng.sample(range(len(s)), 2)
    lo, hi = min(i, j), max(i, j)
    r = rng.random()
    if r < 0.10:
        p = s[i] % 2
        return Constraint((i,), f"{D(i)} is {'odd' if p else 'even'}", lambda x, p=p: x % 2 == p)
    if r < 0.18:
        yes = s[i] in PRIMES
        return Constraint((i,), f"{D(i)} is {'' if yes else 'not '}prime", lambda x, yes=yes: (x in PRIMES) == yes)
    if r < 0.26:
        if s[i] == 0:
            return None
        k = rng.randint(max(0, s[i] - 4), s[i] - 1)
        return Constraint((i,), f"{D(i)} > {k}", lambda x, k=k: x > k)
    if r < 0.34:
        if s[i] == 9:
            return None
        k = rng.randint(s[i] + 1, min(9, s[i] + 4))
        return Constraint((i,), f"{D(i)} < {k}", lambda x, k=k: x < k)
    if r < 0.62:
        k = s[i] + s[j]
        return Constraint((lo, hi), f"{D(lo)} + {D(hi)} = {k}", lambda x, y, k=k: x + y == k)
    if r < 0.82:
        a, b = (i, j) if s[i] > s[j] else (j, i)
        return Constraint((a, b), f"{D(a)} > {D(b)}", lambda x, y: x > y)
    k = abs(s[i] - s[j])
    return Constraint((lo, hi), f"|{D(lo)} - {D(hi)}| = {k}", lambda x, y, k=k: abs(x - y) == k)


def equals(i, v):
    return Constraint((i,), f"{D(i)} = {v}", lambda x, v=v: x == v)


@dataclass
class Lock:
    secret: list
    constraints: list
    n: int = 5
    version: int = 0


@dataclass
class SolveResult:
    solution: list
    solutions: list
    mode: str = "mrv_fc_ac3"
    assignments: int = 0
    backtracks: int = 0
    checks: int = 0  # constraint checks
    prunes: int = 0  # values removed from domains by forward checking / AC-3
    trace: list = field(default_factory=list)  # (dial, value) steps, value -1 = undo; used by the GUI
    ms: float = 0.0


def solve(lock, mode="mrv_fc_ac3", limit=1, trace=False):
    t0 = time.perf_counter()
    use_mrv, use_fc, use_ac3 = "mrv" in mode, "fc" in mode, "ac3" in mode
    n, cons = lock.n, lock.constraints
    by_var = [[c for c in cons if v in c.vars] for v in range(n)]
    neighbours = [sorted({u for c in by_var[v] for u in c.vars if u != v}) for v in range(n)]
    a = [UNSET] * n
    res = SolveResult(None, [], mode)
    domains = [list(range(10)) for _ in range(n)]

    def consistent(v):
        for c in by_var[v]:
            res.checks += 1
            if not c.ok(a):
                return False
        return True

    # Node consistency on one-dial clues (part of the forward-checking configurations).
    if use_fc:
        for v in range(n):
            unary = [c for c in by_var[v] if len(c.vars) == 1]
            keep = []
            for x in domains[v]:
                a[v] = x
                res.checks += len(unary)
                if all(c.ok(a) for c in unary):
                    keep.append(x)
            a[v] = UNSET
            res.prunes += len(domains[v]) - len(keep)
            domains[v] = keep

    def ac3():
        """Make every arc (i -> j) consistent: each value of Di needs a supporting value in Dj."""
        arcs = []
        for c in cons:
            if c.kind == "clue" and len(c.vars) == 2:
                i, j = c.vars
                arcs.append((i, j, lambda x, y, c=c, i=i, j=j: c.test(x, y)))
                arcs.append((j, i, lambda y, x, c=c, i=i, j=j: c.test(x, y)))
            elif c.kind == "alldiff":
                arcs += [(i, j, lambda x, y: x != y) for i in c.vars for j in c.vars if i != j]
        queue = list(arcs)
        while queue:
            i, j, test = queue.pop(0)
            keep = []
            for x in domains[i]:
                for y in domains[j]:
                    res.checks += 1
                    if test(x, y):
                        keep.append(x)
                        break
            if len(keep) < len(domains[i]):
                res.prunes += len(domains[i]) - len(keep)
                domains[i] = keep
                if not keep:
                    return False
                queue += [arc for arc in arcs if arc[1] == i and arc[0] != j]
        return True

    def select_var():
        unassigned = [v for v in range(n) if a[v] == UNSET]
        if not unassigned:
            return None
        if not use_mrv:
            return unassigned[0]  # next dial in order
        # fewest remaining values first; ties go to the dial involved in most clues
        return min(unassigned, key=lambda v: (len(domains[v]), -sum(1 for u in neighbours[v] if a[u] == UNSET)))

    def forward_check(v):
        """Remove values from unassigned neighbours that would now break a clue."""
        for u in neighbours[v]:
            if a[u] != UNSET:
                continue
            keep = []
            for x in domains[u]:
                a[u] = x
                if consistent(u):
                    keep.append(x)
            a[u] = UNSET
            res.prunes += len(domains[u]) - len(keep)
            domains[u] = keep
            if not keep:
                return False
        return True

    def backtrack():
        nonlocal domains
        v = select_var()
        if v is None:
            res.solutions.append(a.copy())
            return len(res.solutions) >= limit
        for val in list(domains[v]):
            a[v] = val
            res.assignments += 1
            if trace and len(res.trace) < 4000:
                res.trace.append((v, val))
            if consistent(v):
                saved = domains
                if use_fc:
                    domains = [d.copy() for d in saved]
                if (not use_fc or forward_check(v)) and backtrack():
                    return True
                domains = saved
            a[v] = UNSET
            res.backtracks += 1
            if trace and len(res.trace) < 4000:
                res.trace.append((v, UNSET))
        return False

    if all(domains) and (not use_ac3 or ac3()):
        backtrack()
    res.solution = res.solutions[0] if res.solutions else None
    res.ms = (time.perf_counter() - t0) * 1000
    return res


def count_solutions(lock, limit=2):
    return len(solve(lock, "mrv_fc", limit=limit).solutions)


def make_unique(lock, rng):
    texts = {c.text for c in lock.constraints}
    for _ in range(80):
        if count_solutions(lock) == 1:
            break
        c = random_clue(rng, lock.secret)
        if c and c.text not in texts:
            texts.add(c.text)
            lock.constraints.append(c)
    i = 0
    while count_solutions(lock) != 1:
        lock.constraints.append(equals(i, lock.secret[i]))
        i += 1
    # Drop every clue (except "all differ") that is not needed for a unique answer.
    for k in range(len(lock.constraints) - 1, 0, -1):
        c = lock.constraints.pop(k)
        if count_solutions(lock) != 1:
            lock.constraints.insert(k, c)


def make_lock(rng, n=5):
    secret = rng.sample(range(10), n)
    lock = Lock(secret, [all_diff(n)], n)
    if rng.random() < 0.6:
        lock.constraints.append(checksum(n, sum(secret)))
    make_unique(lock, rng)
    return lock


def mutate_lock(lock, rng):
    """Power surge: rewire two dials, drop clues that no longer hold, add new ones."""
    s = lock.secret.copy()
    positions = rng.sample(range(lock.n), 2)
    unused = rng.sample([d for d in range(10) if d not in s], 2)
    for p, d in zip(positions, unused):
        s[p] = d
    before = [c.text for c in lock.constraints]
    lock.secret = s
    lock.constraints = [c for c in lock.constraints if c.kind == "alldiff" or c.ok(s)]
    kept = {c.text for c in lock.constraints}
    removed = [t for t in before if t not in kept]
    make_unique(lock, rng)
    added = [c.text for c in lock.constraints if c.text not in before]
    lock.version += 1
    return {"changed_dials": [p + 1 for p in positions], "removed": removed, "added": added}
