# UNIT-7 Escape Protocol

**CSCI218 Group Project (Topic 10: AI Escape Room).** Group 2, Abdullah Wed 10:30–12:30 lab.

| Member | Student ID | Role |
|---|---|---|
| Rohan | 8853666 | Project setup, backend (core AI modules) |
| Ibraam | 9001591 | Backend (agent, simulation, learning, evaluation) |
| Vidhi | 8960008 | Frontend |
| Zia | 9619951 | Frontend |
| Yousif | 9851501 | Testing and evaluation |

An AI agent, UNIT-7, escapes a facility that keeps changing around it. It collects three keycards, solves a lock puzzle at a terminal and reaches the exit. Meanwhile a drone hunts it, laser gates switch on and off, coolant spreads, ceilings collapse onto its route, and power surges rewrite the lock's rules.

## AI techniques

| Technique | Job | Module |
|---|---|---|
| **A\* search** (in space and time) | Plans every route and times its way through laser gates. Dijkstra, greedy best-first and BFS are included for comparison. | `escape_room/search.py` |
| **Constraint satisfaction** (backtracking, forward checking, MRV, AC-3) | Generates the vault lock, solves it, and rewires it during a power surge | `escape_room/csp.py` |
| **Behaviour tree** | Picks what the agent does each tick, with higher-priority branches interrupting lower ones | `escape_room/bt.py` |
| **Fuzzy logic** (Mamdani) | Rates how dangerous a cell is, from drone distance, drone alertness and hull integrity | `escape_room/fuzzy.py` |
| **Finite state machine** | Controls the drone: Patrol, Alert, Chase, Cooldown | `escape_room/drone.py` |

## Tech stack

| Layer | Technology |
|---|---|
| Language | Python 3.9+ |
| Dependencies | Standard library only (`heapq`, `collections`, `dataclasses`, `random`) |
| Desktop demo | Tkinter (ships with Python) |
| Website | Static HTML, CSS and JavaScript, running the Python package in the browser with Pyodide |
| Hosting | Vercel (static, no build step) |
| Version control | Git and GitHub |

## Setup

1. Install Python 3.9 or later from [python.org](https://www.python.org/downloads/). On Windows, tick **Add Python to PATH**.
2. Clone the repository:

   ```bash
   git clone <repository-url>
   cd <repository-folder>
   ```

3. (Optional) Create a virtual environment:

   ```bash
   python -m venv .venv
   .venv\Scripts\activate        # Windows
   source .venv/bin/activate     # macOS / Linux
   ```

There is nothing to install: the project uses only the standard library.

## Using the core modules

```python
import random
from escape_room.world import generate_world
from escape_room.search import plan
from escape_room.csp import make_lock, solve
from escape_room.fuzzy import make_risk_fuzzy

w = generate_world(7)                                       # seeded 31 x 21 facility
route = plan(w, w.start, w.exit, "astar", time_aware=True)  # space-time A*, avoids live laser gates
print(len(route.path) - 1, "steps,", route.expanded, "states expanded")

lock = make_lock(random.Random(1))                          # vault lock with exactly one solution
print(solve(lock, "mrv_fc_ac3").solution)

threat = make_risk_fuzzy().infer(dict(distance=3, alert=1.0, integrity=60))
print(threat["value"])                                      # 0-100
```

Planners: `astar`, `dijkstra`, `greedy`, `bfs`. Lock solvers: `bt`, `fc`, `mrv_fc`, `mrv_fc_ac3`.

## Project structure

```
escape_room/
  __init__.py
  world.py    seeded facility: maze, rooms, keycards, terminal, laser gates, coolant
  search.py   A*, Dijkstra, greedy best-first, BFS; snapshot or space-time planning
  csp.py      lock puzzle: generation, four solvers, power-surge changes
  fuzzy.py    Mamdani fuzzy threat controller
  bt.py       behaviour tree nodes (selector, sequence, condition, action)
  drone.py    security drone finite state machine
```

## Still to come

| Part | Owner |
|---|---|
| Agent, simulation loop, Q-learning lab, evaluation, desktop demo | Backend, part 2 |
| Website (simulator, benchmark, learning lab, how-it-works pages) | Frontend |
| Correctness tests and the evaluation runs | Testing and evaluation |
