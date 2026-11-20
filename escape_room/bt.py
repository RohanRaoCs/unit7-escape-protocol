"""A minimal reactive behaviour tree.

Composite nodes are re-evaluated from their first child on every tick (no memory), so a
higher-priority branch such as "Survive" interrupts a running action the moment its
condition becomes true. Each node remembers its last status and tick for the GUI.
"""
SUCCESS, FAILURE, RUNNING = "success", "failure", "running"


class Node:
    def __init__(self, kind, name, children=None, fn=None):
        self.kind = kind  # "selector" | "sequence" | "condition" | "action"
        self.name = name
        self.children = children or []
        self.fn = fn
        self.status = None
        self.stamp = -1

    def run(self, tick):
        if self.kind == "selector":  # try children until one does not fail
            status = FAILURE
            for child in self.children:
                status = child.run(tick)
                if status != FAILURE:
                    break
        elif self.kind == "sequence":  # run children in order until one does not succeed
            status = SUCCESS
            for child in self.children:
                status = child.run(tick)
                if status != SUCCESS:
                    break
        elif self.kind == "condition":
            status = SUCCESS if self.fn() else FAILURE
        else:
            status = self.fn()
        self.status, self.stamp = status, tick
        return status

    def walk(self, depth=0):
        """Yield (node, depth) for every node, depth-first."""
        yield self, depth
        for child in self.children:
            yield from child.walk(depth + 1)


def selector(name, children):
    return Node("selector", name, children)


def sequence(name, children):
    return Node("sequence", name, children)


def condition(name, fn):
    return Node("condition", name, fn=fn)


def action(name, fn):
    return Node("action", name, fn=fn)
