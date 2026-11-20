"""UNIT-7 Escape Protocol: interactive demo (Tkinter, part of the Python standard library).

Run:  python main.py

The window shows the facility, the agent's behaviour tree, the fuzzy threat assessment,
the lock puzzle, the drone's state machine and a log. Click the map to drop rubble, spill
coolant or move the drone, and watch the agent adapt.
"""
import random
import tkinter as tk
from tkinter import ttk

from escape_room.csp import CSP_MODES
from escape_room.search import ALGOS
from escape_room.sim import DYNAMICS, Simulation
from escape_room.view import fuzzy_view, lock_view, route_view, tree_view
from escape_room.world import FLOOR, RUBBLE, WALL

CELL = 24
COLORS = dict(floor="#ffffff", grid="#eef0f3", wall="#2f3b48", rubble="#b08559", coolant="#a7ece2",
              searched="#dbe7fd", agent="#2563eb", patrol="#ea580c", alert="#d97706", chase="#dc2626", cooldown="#9ca3af",
              threat="#fbd5d5", gate_on="#dc2626", gate_off="#c4c9d0",
              terminal="#7c3aed", exit_open="#15803d", exit_locked="#dc2626", route="#2563eb", script_route="#6b7280")
TEAM = ["Rohan", "Ibraam", "Vidhi", "Zia", "Yousif"]
STUDENT_IDS = ["8853666", "9001591", "8960008", "9619951", "9851501"]


class App:
    def __init__(self, root):
        self.root = root
        root.title("UNIT-7 Escape Protocol · CSCI218 Group 2")
        root.configure(bg="#f3f4f6")
        self.running = False
        self.sim = None
        self.cells = []
        style = ttk.Style()
        style.configure("TFrame", background="#f3f4f6")
        style.configure("TLabel", background="#f3f4f6")
        style.configure("Card.TFrame", background="#ffffff")
        style.configure("Card.TLabel", background="#ffffff")

        self.build_header()
        body = ttk.Frame(root, padding=(12, 0, 12, 12))
        body.pack(fill="both", expand=True)
        left = ttk.Frame(body)
        left.pack(side="left", fill="y")
        right = ttk.Frame(body, width=380)
        right.pack(side="left", fill="both", expand=True, padx=(12, 0))
        self.build_toolbar(left)
        self.canvas = tk.Canvas(left, width=31 * CELL, height=21 * CELL, bg="white", highlightthickness=1, highlightbackground="#dde1e6")
        self.canvas.pack()
        self.canvas.bind("<Button-1>", self.on_click)
        ttk.Label(left, text="Blue: agent · Orange/amber/red/grey: drone (patrol/alert/chase/cooldown) · Pink, gold, green: keycards · "
                             "Purple: terminal · Square: exit (red = locked) · Red bar: laser gate (thin grey = off) · Teal: coolant · "
                             "Brown: rubble · Pink shading: fuzzy threat · Light blue: cells the last search explored", wraplength=31 * CELL, foreground="#4b5563").pack(anchor="w", pady=(6, 0))
        self.build_options(left)
        self.build_side(right)
        self.new_sim()
        self.loop()

    # ---------- layout ----------
    def build_header(self):
        top = ttk.Frame(self.root, padding=12)
        top.pack(fill="x")
        text = ttk.Frame(top)
        text.pack(side="left", fill="x", expand=True)
        ttk.Label(text, text="UNIT-7 Escape Protocol", font=("Segoe UI", 16, "bold")).pack(anchor="w")
        ttk.Label(text, wraplength=640, foreground="#4b5563", text=(
            "The agent collects three keycards, cracks the lock at the terminal and reaches the exit, while a drone "
            "hunts it, laser gates switch on and off, ceilings collapse onto its route and the lock's rules change. "
            "It plans with A* search (in space and time), solves the lock as a constraint satisfaction problem, "
            "judges danger with fuzzy logic and decides with a behaviour tree. The drone is a finite state machine. "
            "Q-learning is compared in the web version's Learning lab.")).pack(anchor="w")
        card = ttk.Frame(top, style="Card.TFrame", padding=10, relief="solid", borderwidth=1)
        card.pack(side="right")
        ttk.Label(card, text="CSCI218 Group Project", style="Card.TLabel", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=5, sticky="w")
        ttk.Label(card, text="Made for Dr. Abdullah and Dr. Milan by Group 2, Abdullah Wed 10:30–12:30 lab",
                  style="Card.TLabel", foreground="#4b5563").grid(row=1, column=0, columnspan=5, sticky="w", pady=(0, 6))
        for col, (name, sid) in enumerate(zip(TEAM, STUDENT_IDS)):
            ttk.Label(card, text=name, style="Card.TLabel", font=("Segoe UI", 9, "bold")).grid(row=2, column=col, sticky="w", padx=(0, 14))
            ttk.Label(card, text=sid, style="Card.TLabel", foreground="#7b8591").grid(row=3, column=col, sticky="w", padx=(0, 14))

    def build_toolbar(self, parent):
        bar = ttk.Frame(parent)
        bar.pack(fill="x", pady=(0, 8))
        self.run_btn = ttk.Button(bar, text="Run", command=self.toggle_run)
        self.run_btn.pack(side="left")
        ttk.Button(bar, text="Step", command=self.step_once).pack(side="left", padx=4)
        ttk.Button(bar, text="Restart", command=lambda: self.new_sim(run=True)).pack(side="left")
        ttk.Button(bar, text="New map", command=self.new_map).pack(side="left", padx=4)
        ttk.Label(bar, text="  Speed").pack(side="left")
        self.speed = tk.IntVar(value=8)
        ttk.Scale(bar, from_=1, to=40, variable=self.speed, orient="horizontal", length=120).pack(side="left", padx=4)
        ttk.Label(bar, text="  Seed").pack(side="left")
        self.seed = tk.IntVar(value=5007)
        seed_box = ttk.Spinbox(bar, from_=1, to=99999, textvariable=self.seed, width=7, command=lambda: self.new_sim(run=True))
        seed_box.pack(side="left", padx=4)
        seed_box.bind("<Return>", lambda e: self.new_sim(run=True))

    def build_options(self, parent):
        box = ttk.Frame(parent)
        box.pack(fill="x", pady=(8, 0))
        ttk.Label(box, text="Path planner").pack(side="left")
        self.algo = tk.StringVar(value="A*")
        ttk.Combobox(box, textvariable=self.algo, values=list(ALGOS.values()), state="readonly", width=16).pack(side="left", padx=(4, 12))
        ttk.Label(box, text="Lock solver").pack(side="left")
        self.csp = tk.StringVar(value=CSP_MODES["mrv_fc_ac3"])
        ttk.Combobox(box, textvariable=self.csp, values=list(CSP_MODES.values()), state="readonly", width=28).pack(side="left", padx=(4, 12))
        ttk.Label(box, text="Facility").pack(side="left")
        self.dyn = tk.StringVar(value=DYNAMICS["normal"]["label"])
        ttk.Combobox(box, textvariable=self.dyn, values=[d["label"] for d in DYNAMICS.values()], state="readonly", width=9).pack(side="left", padx=4)
        checks = ttk.Frame(parent)
        checks.pack(fill="x", pady=(6, 0))
        self.fuzzy = tk.BooleanVar(value=True)
        self.time_aware = tk.BooleanVar(value=True)
        self.adaptive = tk.BooleanVar(value=True)
        for var, text in ((self.fuzzy, "Fuzzy threat (off = crisp rule)"), (self.time_aware, "Space-time planning (laser gate timetable)"),
                          (self.adaptive, "Behaviour tree + replanning (off = fixed script)")):
            ttk.Checkbutton(checks, text=text, variable=var, command=lambda: self.new_sim(run=True)).pack(side="left", padx=(0, 10))
        for var in (self.algo, self.csp, self.dyn):
            var.trace_add("write", lambda *_: self.new_sim(run=True))
        events = ttk.Frame(parent)
        events.pack(fill="x", pady=(6, 0))
        ttk.Button(events, text="Collapse the route", command=lambda: self.event("collapse")).pack(side="left")
        ttk.Button(events, text="Power surge", command=lambda: self.event("surge")).pack(side="left", padx=4)
        ttk.Button(events, text="Sound the alarm", command=lambda: self.event("alarm")).pack(side="left")
        ttk.Label(events, text="   Clicking the map will:").pack(side="left")
        self.tool = tk.StringVar(value="rubble")
        for value, text in (("rubble", "drop rubble"), ("hazard", "spill coolant"), ("drone", "move drone")):
            ttk.Radiobutton(events, text=text, value=value, variable=self.tool).pack(side="left", padx=3)

    def build_side(self, parent):
        status = ttk.Frame(parent, style="Card.TFrame", padding=10, relief="solid", borderwidth=1)
        status.pack(fill="x")
        self.tick_label = ttk.Label(status, style="Card.TLabel", font=("Segoe UI", 13, "bold"))
        self.tick_label.pack(anchor="w")
        self.mode_label = ttk.Label(status, style="Card.TLabel", foreground="#4b5563", wraplength=340)
        self.mode_label.pack(anchor="w")
        self.hull = ttk.Progressbar(status, maximum=100, length=340)
        self.hull.pack(anchor="w", pady=6)
        self.stats_label = ttk.Label(status, style="Card.TLabel", justify="left", font=("Consolas", 9))
        self.stats_label.pack(anchor="w")

        tabs = ttk.Notebook(parent)
        tabs.pack(fill="both", expand=True, pady=(10, 0))
        self.tree_text = self.text_tab(tabs, "Decisions", "The behaviour tree is checked from the top every tick. "
                                       "Blue = running now, green = succeeded, red = failed this tick.")
        self.fuzzy_text = self.text_tab(tabs, "Threat", "Fuzzy logic turns drone distance, drone alertness and hull "
                                        "integrity into one threat score (0-100). Above the threshold, the agent evades.")
        self.lock_text = self.text_tab(tabs, "Lock", "The lock is a CSP: five different digits that satisfy every clue. "
                                       "While cracking, the dials replay the solver's search.")
        self.drone_text = self.text_tab(tabs, "Drone", "The drone is a finite state machine: Patrol -> Alert -> Chase -> "
                                        "Cooldown -> Patrol. The current state is highlighted.")
        self.log_text = self.text_tab(tabs, "Log", "What the agent decided and what happened, newest first.")
        for t in (self.tree_text, self.lock_text, self.fuzzy_text, self.drone_text):
            t.tag_configure("running", foreground="#2563eb", font=("Consolas", 10, "bold"))
            t.tag_configure("success", foreground="#15803d")
            t.tag_configure("failure", foreground="#be123c")
            t.tag_configure("idle", foreground="#9aa3ae")
            t.tag_configure("dials", font=("Consolas", 20, "bold"), foreground="#2563eb")
            t.tag_configure("solved", font=("Consolas", 20, "bold"), foreground="#15803d")
            t.tag_configure("new", foreground="#7c3aed")

    def text_tab(self, notebook, title, intro):
        frame = ttk.Frame(notebook, padding=8)
        notebook.add(frame, text=title)
        ttk.Label(frame, text=intro, wraplength=340, foreground="#4b5563").pack(anchor="w", pady=(0, 6))
        text = tk.Text(frame, width=46, height=22, font=("Consolas", 10), relief="flat", wrap="word")
        text.pack(fill="both", expand=True)
        return text

    # ---------- simulation control ----------
    def new_sim(self, run=False):
        algo = next(k for k, v in ALGOS.items() if v == self.algo.get())
        csp = next(k for k, v in CSP_MODES.items() if v == self.csp.get())
        try:
            seed = max(1, int(self.seed.get()))
        except (tk.TclError, ValueError):
            seed = 5007
        dyn = next(k for k, v in DYNAMICS.items() if v["label"] == self.dyn.get())
        self.sim = Simulation(seed=seed, algo=algo, csp=csp, fuzzy=self.fuzzy.get(), time_aware=self.time_aware.get(),
                              adaptive=self.adaptive.get(), dynamics=dyn, verbose=True)
        self.draw_static()
        self.refresh()
        self.set_running(run)

    def new_map(self):
        self.seed.set(random.randint(1, 9999))
        self.new_sim(run=True)

    def set_running(self, value):
        self.running = value and not self.sim.done
        self.run_btn.configure(text="Pause" if self.running else "Run")

    def toggle_run(self):
        self.set_running(not self.running)

    def step_once(self):
        self.set_running(False)
        self.sim.step()
        self.refresh()

    def event(self, kind):
        if not self.sim.done:
            if kind == "collapse":
                self.sim.collapse(by_user=True)
            elif kind == "surge":
                self.sim.surge(by_user=True)
            elif self.sim.alert_drone():
                self.sim.say("EVENT", "[you] Alarm sounded: the drone is hunting")
            self.refresh()

    def on_click(self, e):
        if not self.sim.done:
            x, y = e.x // CELL, e.y // CELL
            {"rubble": self.sim.toggle_rubble, "hazard": self.sim.toggle_hazard, "drone": self.sim.move_drone}[self.tool.get()](x, y)
            self.sim.update_sensors()
            self.refresh()

    def loop(self):
        if self.running and not self.sim.done:
            self.sim.step()
            self.refresh()
            if self.sim.done:
                self.set_running(False)
        self.root.after(max(20, 1000 // max(1, int(self.speed.get()))), self.loop)

    # ---------- drawing ----------
    def draw_static(self):
        """Create one rectangle per cell; refresh() only changes their colours."""
        c, w = self.canvas, self.sim.world
        c.delete("all")
        self.cells = [c.create_rectangle(x * CELL, y * CELL, (x + 1) * CELL, (y + 1) * CELL, outline=COLORS["grid"])
                      for y in range(w.H) for x in range(w.W)]

    def refresh(self):
        s, w, a, c = self.sim, self.sim.world, self.sim.agent, self.canvas
        searched = set()
        if a.last_search and s.t - a.last_search[1] < 15:
            searched = set(a.last_search[0])
        for i, rect in enumerate(self.cells):
            tile = w.tiles[i]
            color = COLORS["wall"] if tile == WALL else COLORS["rubble"] if tile == RUBBLE else \
                COLORS["coolant"] if w.hazard[i] else COLORS["searched"] if i in searched else \
                COLORS["threat"] if s.drone and s.risk_at(i) >= 50 else COLORS["floor"]
            c.itemconfigure(rect, fill=color, outline=COLORS["grid"] if tile == FLOOR else color)

        c.delete("dyn")
        def box(x, y, pad, **kw):
            return c.create_rectangle(x * CELL + pad, y * CELL + pad, (x + 1) * CELL - pad, (y + 1) * CELL - pad, tags="dyn", **kw)
        def dot(x, y, r, color):
            cx, cy = x * CELL + CELL / 2, y * CELL + CELL / 2
            c.create_oval(cx - r, cy - r, cx + r, cy + r, fill=color, outline="", tags="dyn")

        if w.gates_active:
            for g in w.gates:
                on = w.gate_on(g.x, g.y, s.t)
                cx, cy = g.x * CELL + CELL / 2, g.y * CELL + CELL / 2
                pts = (cx, g.y * CELL + 2, cx, (g.y + 1) * CELL - 2) if w.gate_orientation(g) == "v" else (g.x * CELL + 2, cy, (g.x + 1) * CELL - 2, cy)
                c.create_line(*pts, fill=COLORS["gate_on" if on else "gate_off"], width=4 if on else 1, tags="dyn")
        box(*w.terminal, 4, fill=COLORS["terminal"], outline="")
        box(*w.exit, 3, outline=COLORS["exit_open"] if a.exit_unlocked() else COLORS["exit_locked"], width=2)
        for k in w.keys:
            if not k.taken:
                box(k.x, k.y, 6, fill=k.color, outline="")
        route = route_view(s)
        if len(route) > 1:
            pts = [v for x, y in route for v in (x * CELL + CELL / 2, y * CELL + CELL / 2)]
            c.create_line(*pts, fill=COLORS["route" if a.adaptive else "script_route"], width=2, dash=(5, 3), tags="dyn")
        if s.drone:
            dot(s.drone.x, s.drone.y, CELL * 0.32, COLORS[s.drone.state.lower()])
        dot(a.x, a.y, CELL * 0.36, COLORS["agent"])
        dot(a.x, a.y, CELL * 0.12, "white")
        if s.done:
            msg = f"Escaped in {s.t} ticks" if s.result["success"] else f"Mission failed ({s.result['reason']})"
            c.create_rectangle(31 * CELL / 2 - 150, 21 * CELL / 2 - 24, 31 * CELL / 2 + 150, 21 * CELL / 2 + 24, fill="white", outline="#dde1e6", tags="dyn")
            c.create_text(31 * CELL / 2, 21 * CELL / 2, text=msg, font=("Segoe UI", 14, "bold"),
                          fill="#15803d" if s.result["success"] else "#dc2626", tags="dyn")
        self.update_side()

    def update_side(self):
        s, a = self.sim, self.sim.agent
        st = a.stats
        self.tick_label.configure(text=f"Tick {s.t} / {s.max_ticks}")
        drone = f" · drone: {s.drone.state.lower()}" if s.drone else ""
        self.mode_label.configure(text=("Escaped" if s.result["success"] else "Failed: " + s.result["reason"]) if s.done else a.mode + drone)
        self.hull["value"] = max(0, a.integrity)
        keys = " ".join(("■" if k.taken else "□") + k.name for k in s.world.keys)
        self.stats_label.configure(text=(
            f"Keycards     {keys}\nHull         {max(0, a.integrity)}%\n"
            f"Path cost    {st['path_cost']:<6} States explored {st['expanded']}\n"
            f"Replans      {st['replans']:<6} Plans made      {st['plan_calls']}\n"
            f"Drone hits   {st['hits']:<6} Laser zaps      {st['zaps']}\n"
            f"Waits        {st['waits']:<6} CSP assignments {st['csp_assignments']}"))

        t = self.tree_text
        t.delete("1.0", "end")
        rows = tree_view(s)
        if rows is None:
            t.insert("end", "Replanning is off, so there is no behaviour tree.\nThe agent follows a fixed plan made at tick 0.", "idle")
        else:
            for r in rows:
                t.insert("end", "    " * r["depth"] + f"{r['glyph']} {r['name']}\n", r["status"] or "idle")

        t = self.lock_text
        t.delete("1.0", "end")
        lock = lock_view(s)
        t.insert("end", "  ".join("–" if d is None else str(d) for d in lock["dials"]) + "\n", "solved" if lock["state"] == "solved" else "dials")
        t.insert("end", "  ".join(f"D{i + 1}" for i in range(5)) + "\n\nClues:\n", "idle")
        for clue in lock["clues"]:
            mark = {"ok": "✓", "bad": "✗"}.get(clue["status"], "·")
            tag = "new" if clue["new"] else {"ok": "success", "bad": "failure"}.get(clue["status"], "")
            t.insert("end", f"  {mark} {clue['text']}\n", tag)
        t.insert("end", "\n" + lock["info"])

        t = self.fuzzy_text
        t.delete("1.0", "end")
        f = fuzzy_view(s)
        if f is None:
            t.insert("end", "No drone in the Static facility, so the threat is always zero.", "idle")
        else:
            v, mu = f["values"], f["mu"]
            t.insert("end", f"Threat {f['value']:.0f} / 100", "running" if f["evading"] else "")
            t.insert("end", f"   (evade above {f['threshold']})\n\n" if a.fuzzy else "   (crisp rule in use)\n\n", "idle")
            labels = dict(distance=f"Distance {v['distance']} cells", alert=f"Drone alertness {v['alert']}", integrity=f"Hull {v['integrity']}%")
            for name, label in labels.items():
                t.insert("end", label + "\n")
                t.insert("end", "   " + "   ".join(f"{k} {m:.2f}" for k, m in mu[name].items()) + "\n", "idle")
            t.insert("end", "\nRules (firing strength):\n")
            for rule, strength in zip(s.fuzzy.rules, f["fired"]):
                conds = " and ".join(f"{n} {st_}" for n, st_ in rule[0])
                t.insert("end", f"  {strength:.2f}  {conds} => {rule[1]}\n", "success" if strength > 0 else "idle")

        t = self.drone_text
        t.delete("1.0", "end")
        if s.drone is None:
            t.insert("end", "No drone in the Static facility.", "idle")
        else:
            for state in ("PATROL", "ALERT", "CHASE", "COOLDOWN"):
                here = s.drone.state == state
                t.insert("end", ("> " if here else "  ") + state.title() + "\n", "running" if here else "idle")
            t.insert("end", f"\n{s.drone.transitions} transitions, alertness {s.drone.alertness()}, sees {s.drone.detect} cells.")

        t = self.log_text
        t.delete("1.0", "end")
        for tick, cat, msg in reversed(s.logs[-80:]):
            t.insert("end", f"{tick:>4} {cat:<6} {msg}\n")


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
