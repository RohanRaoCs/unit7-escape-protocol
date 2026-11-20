"""Fuzzy logic: a Mamdani controller that rates how dangerous a cell is.

Inputs (all uncertain, so crisp thresholds would be brittle):
  distance   corridor distance from the cell to the security drone (0-20 cells)
  alert      how alert the drone is, taken from its state machine (0-1)
  integrity  the agent's remaining hull (0-100 %)
Output:
  threat     0-100

Inference: AND = min, rule outputs are clipped and combined with max, and the crisp threat
is the centroid of the combined shape. The threat is used twice: as an extra step cost in
A* (routes keep away from danger) and in the behaviour tree's "Threat high?" condition.
"""


def trap(a, b, c, d):
    """Trapezoid membership function: 0 below a, rises to 1 at b, stays 1 to c, 0 after d."""
    def mu(x):
        if x < a or x > d:
            return 0.0
        if b <= x <= c:
            return 1.0
        if x < b:
            return (x - a) / (b - a)
        return (d - x) / (d - c)
    return mu


def tri(a, b, c):
    return trap(a, b, b, c)


class FuzzyVar:
    def __init__(self, label, lo, hi, sets):
        self.label, self.range, self.sets = label, (lo, hi), sets  # sets: {name: membership function}


class FuzzySystem:
    def __init__(self, inputs, output, rules, samples=101):
        self.inputs, self.output, self.rules, self.samples = inputs, output, rules, samples

    def fuzzify(self, values):
        mu = {}
        for name, var in self.inputs.items():
            x = min(max(values[name], var.range[0]), var.range[1])
            mu[name] = {s: fn(x) for s, fn in var.sets.items()}
        return mu

    def infer(self, values):
        mu = self.fuzzify(values)
        fired, strength = [], {}
        for conds, out in self.rules:
            st = min(mu[v][s] for v, s in conds)
            fired.append(st)
            if st > 0:
                strength[out] = max(strength.get(out, 0), st)
        lo, hi = self.output.range
        agg, num, den = [], 0.0, 0.0
        for k in range(self.samples):
            x = lo + (hi - lo) * k / (self.samples - 1)
            m = max((min(st, self.output.sets[s](x)) for s, st in strength.items()), default=0.0)
            agg.append(m)
            num += m * x
            den += m
        return dict(value=num / den if den > 0 else lo, mu=mu, fired=fired, agg=agg, strength=strength)


def make_risk_fuzzy():
    return FuzzySystem(
        inputs={
            "distance": FuzzyVar("Drone distance (cells)", 0, 20,
                                 {"Near": trap(0, 0, 2, 5), "Medium": tri(3, 7, 11), "Far": trap(9, 13, 20, 20)}),
            "alert": FuzzyVar("Drone alertness", 0, 1,
                              {"Calm": trap(0, 0, 0.25, 0.55), "Alert": trap(0.45, 0.75, 1, 1)}),
            "integrity": FuzzyVar("Hull integrity (%)", 0, 100,
                                  {"Critical": trap(0, 0, 30, 55), "Healthy": trap(40, 70, 100, 100)}),
        },
        output=FuzzyVar("Threat level", 0, 100, {
            "VeryLow": trap(0, 0, 8, 22), "Low": tri(12, 28, 44), "Medium": tri(35, 50, 65),
            "High": tri(58, 74, 90), "VeryHigh": trap(82, 94, 100, 100),
        }),
        rules=[
            ([("distance", "Near"), ("alert", "Alert")], "VeryHigh"),
            ([("distance", "Near"), ("alert", "Calm")], "Medium"),
            ([("distance", "Medium"), ("alert", "Alert")], "High"),
            ([("distance", "Medium"), ("alert", "Calm")], "Low"),
            ([("distance", "Far"), ("alert", "Alert")], "Low"),
            ([("distance", "Far"), ("alert", "Calm")], "VeryLow"),
            ([("distance", "Near"), ("integrity", "Critical")], "VeryHigh"),
            ([("distance", "Medium"), ("integrity", "Critical")], "Medium"),
            ([("distance", "Far"), ("integrity", "Healthy")], "VeryLow"),
        ],
    )


NAMES = {"distance": "distance", "alert": "drone", "integrity": "hull"}


def rule_text(rule):
    conds, out = rule
    return "IF " + " AND ".join(f"{NAMES[v]} is {s}" for v, s in conds) + f" THEN threat is {out}"
