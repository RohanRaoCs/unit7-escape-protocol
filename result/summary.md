# Evaluation results

100 generated facilities per cell (seeds 5000-5099), 31 × 21 grid, time limit 900 ticks. Completion time and path cost are averaged over successful runs. Values are mean ± standard deviation.

## Missions: Static facility

| Agent design | Success | Ticks | Path cost | States explored | Replans | Drone hits | Laser zaps | Final hull | Failures |
|---|---|---|---|---|---|---|---|---|---|
| UNIT-7 full: A* + fuzzy + space-time + BT | **100%** | 133 ± 23 | 130 ± 23 | 303 ± 113 | 0.0 | 0.00 | 0.00 | 100 | none |
| A* + fuzzy, snapshot planning | **100%** | 133 ± 23 | 130 ± 23 | 303 ± 113 | 0.0 | 0.00 | 0.00 | 100 | none |
| A* + crisp avoidance (no fuzzy) | **100%** | 133 ± 23 | 130 ± 23 | 303 ± 113 | 0.0 | 0.00 | 0.00 | 100 | none |
| Dijkstra + fuzzy + space-time | **100%** | 133 ± 23 | 130 ± 23 | 908 ± 151 | 0.0 | 0.00 | 0.00 | 100 | none |
| Greedy best-first + fuzzy + space-time | **100%** | 147 ± 28 | 146 ± 28 | 197 ± 62 | 0.0 | 0.00 | 0.00 | 99 | none |
| BFS + fuzzy + space-time | **100%** | 132 ± 23 | 132 ± 23 | 908 ± 154 | 0.0 | 0.00 | 0.00 | 99 | none |
| Fixed script (plans once, never adapts) | **100%** | 133 ± 23 | 130 ± 23 | 303 ± 113 | 0.0 | 0.00 | 0.00 | 100 | none |

## Missions: Dynamic facility

| Agent design | Success | Ticks | Path cost | States explored | Replans | Drone hits | Laser zaps | Final hull | Failures |
|---|---|---|---|---|---|---|---|---|---|
| UNIT-7 full: A* + fuzzy + space-time + BT | **99%** | 209 ± 78 | 214 ± 85 | 17,619 ± 14,707 | 9.7 | 0.17 | 0.00 | 89 | 1 destroyed |
| A* + fuzzy, snapshot planning | **92%** | 220 ± 83 | 222 ± 87 | 6,133 ± 12,955 | 18.0 | 0.27 | 0.15 | 84 | 3 destroyed, 5 timeout |
| A* + crisp avoidance (no fuzzy) | **99%** | 196 ± 74 | 191 ± 74 | 12,255 ± 17,770 | 4.9 | 0.10 | 0.01 | 92 | 1 destroyed |
| Dijkstra + fuzzy + space-time | **99%** | 212 ± 77 | 219 ± 84 | 27,759 ± 17,982 | 9.8 | 0.16 | 0.00 | 89 | 1 destroyed |
| Greedy best-first + fuzzy + space-time | **94%** | 205 ± 63 | 217 ± 74 | 3,735 ± 4,975 | 10.8 | 0.47 | 0.01 | 76 | 5 destroyed, 1 timeout |
| BFS + fuzzy + space-time | **94%** | 192 ± 62 | 201 ± 68 | 19,056 ± 11,722 | 9.3 | 0.61 | 0.00 | 74 | 6 destroyed |
| Fixed script (plans once, never adapts) | **22%** | 124 ± 23 | 128 ± 21 | 303 ± 113 | 0.0 | 1.54 | 0.33 | 56 | 46 timeout, 32 destroyed |

## Missions: Chaos facility

| Agent design | Success | Ticks | Path cost | States explored | Replans | Drone hits | Laser zaps | Final hull | Failures |
|---|---|---|---|---|---|---|---|---|---|
| UNIT-7 full: A* + fuzzy + space-time + BT | **91%** | 246 ± 90 | 262 ± 101 | 24,940 ± 21,273 | 15.8 | 0.40 | 0.01 | 72 | 8 destroyed, 1 timeout |
| A* + fuzzy, snapshot planning | **67%** | 277 ± 122 | 286 ± 127 | 10,426 ± 14,660 | 28.5 | 0.53 | 0.33 | 57 | 12 timeout, 21 destroyed |
| A* + crisp avoidance (no fuzzy) | **97%** | 250 ± 103 | 249 ± 105 | 21,693 ± 25,785 | 7.9 | 0.16 | 0.08 | 80 | 3 destroyed |
| Dijkstra + fuzzy + space-time | **91%** | 242 ± 84 | 259 ± 99 | 35,316 ± 20,660 | 14.1 | 0.43 | 0.00 | 72 | 9 destroyed |
| Greedy best-first + fuzzy + space-time | **82%** | 246 ± 98 | 269 ± 116 | 7,016 ± 7,250 | 14.6 | 0.76 | 0.02 | 58 | 18 destroyed |
| BFS + fuzzy + space-time | **81%** | 227 ± 91 | 251 ± 105 | 26,045 ± 16,233 | 13.1 | 0.72 | 0.02 | 57 | 19 destroyed |
| Fixed script (plans once, never adapts) | **7%** | 123 ± 20 | 133 ± 34 | 303 ± 113 | 0.0 | 1.65 | 0.42 | 53 | 56 timeout, 37 destroyed |

### Why UNIT-7 replanned (Dynamic facility, mean per mission)

| Route blocked by a collapse | Laser gate timing | Threat drift or drone | Pushed off route (evasion or zap) |
|---|---|---|---|
| 1.59 | 0.00 | 7.12 | 1.01 |

## Planners on identical queries

The same start-to-goal queries (exit, keycards, terminal) on 40 maps with 40 extra coolant cells (step cost 6). Optimal means the cost equals Dijkstra's.

| Planner | Queries | States explored | Path cost | Optimal | Mean cost above optimal | Time (ms) |
|---|---|---|---|---|---|---|
| A* | 200 | 109 ± 81 | 43.6 ± 17.9 | 100% | 0.0% | 0.624 |
| Dijkstra | 200 | 201 ± 98 | 43.6 ± 17.9 | 100% | 0.0% | 0.671 |
| Greedy best-first | 200 | 50 ± 26 | 51.0 ± 22.9 | 34% | 16.4% | 0.583 |
| Breadth-first | 200 | 205 ± 100 | 46.3 ± 19.1 | 55% | 6.2% | 0.515 |
| A* snapshot (gates frozen at t=0) | 200 | 111 ± 79 | 44.6 ± 18.0 | n/a | n/a | 0.680 |
| A* space-time (gate timetable) | 200 | 724 ± 734 | 43.9 ± 18.0 | n/a | n/a | 3.695 |

## Lock solvers

100 generated vault locks (5 dials, minimal clue sets, mean 6.2 clues).

| Solver | Assignments | Backtracks | Constraint checks | Time (ms) | Correct |
|---|---|---|---|---|---|
| Plain backtracking | 1,850.8 ± 4,057.0 | 1,845.8 ± 4,057.0 | 3,698 ± 7,338 | 8.779 | 100% |
| Backtracking + forward checking | 53.5 ± 88.3 | 48.5 ± 88.3 | 1,445 ± 2,362 | 3.112 | 100% |
| MRV + forward checking | 13.7 ± 10.5 | 8.7 ± 10.5 | 715 ± 639 | 1.797 | 100% |
| MRV + FC + AC-3 | 7.7 ± 5.3 | 2.7 ± 5.3 | 817 ± 359 | 0.971 | 100% |

## Learning vs planning (Q-learning lab)

17 × 11 facility, 2 keycards. The policy is trained for 2,500 episodes, then rubble is dropped on its learned route.

| Seed | Episodes to first success | Learned steps | A* optimal steps | Policy after collapse | A* after collapse | Episodes to recover |
|---|---|---|---|---|---|---|
| 1 | 100 | 44 | 44 | the policy walks into a wall | 64 (replanned at once) | 100 |
| 2 | 250 | 62 | 52 | the policy walks into a wall | 82 (replanned at once) | 200 |
| 3 | 50 | 36 | 36 | the policy walks into a wall | 52 (replanned at once) | 250 |
| 4 | 100 | 42 | 42 | the policy walks into a wall | 42 (replanned at once) | 50 |
| 5 | 100 | 42 | 42 | the policy walks into a wall | 46 (replanned at once) | 100 |
| 6 | 100 | 42 | 42 | the policy walks into a wall | 42 (replanned at once) | 50 |
| 7 | 150 | 42 | 42 | the policy walks into a wall | 46 (replanned at once) | 100 |
| 8 | 50 | 34 | 34 | the policy walks into a wall | 36 (replanned at once) | 100 |
