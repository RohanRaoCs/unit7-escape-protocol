"""What the panels show, shared by the desktop demo (main.py) and the website (web.py)."""
from .csp import CSP_MODES, UNSET
from .fuzzy import rule_text

GLYPH = {"selector": "?", "sequence": "→", "condition": "◇", "action": "▸"}


def tree_view(sim):
    """Behaviour tree rows: name, kind glyph, depth and the status of the last tick
    ("running" / "success" / "failure"), or None if the node was not reached."""
    tree = sim.agent.tree
    if tree is None:
        return None
    return [dict(name=n.name, glyph=GLYPH[n.kind], depth=d, status=n.status if n.stamp == sim.t - 1 else None)
            for n, d in tree.walk()]


def lock_view(sim):
    """Dials, clues (with whether the shown dials satisfy them) and a one-line explanation."""
    a, lock = sim.agent, sim.lock
    dials, state = [UNSET] * lock.n, "idle"
    if a.hack and a.hack["result"].trace:
        # Replay the solver's real search in step with the dialling progress.
        trace = a.hack["result"].trace
        upto = int(a.hack["progress"] / a.hack["need"] * len(trace))
        for dial, value in trace[:upto]:
            dials[dial] = value
        state = "solving"
        r = a.hack["result"]
        info = (f"Solving with {CSP_MODES[a.csp_mode]}: replaying search step {upto} of {len(trace)}. "
                f"Total {r.assignments} assignments, {r.backtracks} backtracks, {r.prunes} values pruned.")
    elif a.code_version == lock.version and a.code:
        dials, state = list(a.code), "solved"
        r = a.last_hack["result"]
        info = f"Cracked with {r.assignments} assignments, {r.backtracks} backtracks and {r.checks} constraint checks in {r.ms:.2f} ms."
    elif a.code_version >= 0:
        info = "A power surge rewired the lock, so the known code no longer works. UNIT-7 must solve it again at the terminal."
    elif a.keys < len(sim.world.keys):
        info = f"Locked. UNIT-7 needs all {len(sim.world.keys)} keycards before the terminal shows these clues."
    else:
        info = "Heading to the terminal to solve the lock."
    fresh = set(sim.last_surge[1]) if sim.last_surge and sim.t - sim.last_surge[0] < 80 else set()
    clues = []
    for c in lock.constraints:
        full = all(dials[v] != UNSET for v in c.vars)
        ok = c.ok(dials)
        clues.append(dict(text=c.text, new=c.text in fresh, status="bad" if not ok else "ok" if full else ""))
    return dict(dials=[None if v == UNSET else v for v in dials], state=state, clues=clues, info=info,
                version=lock.version, fresh=bool(fresh))


def route_view(sim):
    """The route the agent intends to follow, as a list of (x, y)."""
    a = sim.agent
    if a.adaptive:
        return a.plan["path"][a.plan["idx"]:] if a.plan else []
    return a.path_ahead(0, 999)


def fuzzy_static(sim):
    """Membership curves (sampled) and rule texts; these never change during a run."""
    f = sim.fuzzy

    def curves(var, n=101):
        lo, hi = var.range
        xs = [lo + (hi - lo) * k / (n - 1) for k in range(n)]
        return dict(label=var.label, range=var.range, sets={s: [round(fn(x), 4) for x in xs] for s, fn in var.sets.items()})

    short = lambda r: " and ".join(f"{dict(distance='distance', alert='drone', integrity='hull')[v]} {s}" for v, s in r[0]) + f" ⇒ {r[1]}"
    return dict(inputs={k: curves(v) for k, v in f.inputs.items()}, output=curves(f.output),
                rules=[dict(short=short(r), full=rule_text(r)) for r in f.rules])


def fuzzy_view(sim):
    """The fuzzy inference at the agent's cell, right now."""
    a, d = sim.agent, sim.drone
    if d is None:
        return None
    values = dict(distance=sim.drone_dist_at(sim.world.idx(a.x, a.y)), alert=d.alertness(), integrity=max(0, a.integrity))
    res = sim.fuzzy.infer(values)
    return dict(values=values, value=res["value"], mu=res["mu"], fired=res["fired"], agg=res["agg"],
                threshold=a.risk_threshold, evading=a.evading)
