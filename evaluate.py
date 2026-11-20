"""Run the full evaluation and write results/summary.md plus one CSV per experiment.

Usage:  python evaluate.py              (100 maps per agent design and facility level)
        python evaluate.py --maps 20    (quicker)

Missions run in parallel on all CPU cores; every run is seeded, so the numbers are the same
on any machine.
"""
import argparse
import csv
import os
import time
from multiprocessing import Pool

from escape_room.csp import CSP_MODES
from escape_room.evaluation import (AGENT_CONFIGS, PLANNER_NAMES, csp_compare, learning_vs_planning, planner_compare,
                                    run_mission, summarize)
from escape_room.sim import DYNAMICS, MAX_TICKS


def fmt(x, digits=0):
    return "-" if x is None or x != x else f"{x:,.{digits}f}"  # x != x is True only for NaN


def pm(s, digits=0):
    return f"{fmt(s['mean'], digits)} ± {fmt(s['std'], digits)}"


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def job(args):
    return run_mission(*args)


def main():
    parser = argparse.ArgumentParser(description="Evaluate the escape-room agents.")
    parser.add_argument("--maps", type=int, default=100, help="maps per agent design and facility level (default 100)")
    args = parser.parse_args()
    seeds = list(range(5000, 5000 + args.maps))
    os.makedirs("results", exist_ok=True)
    started = time.time()

    md = [f"# Evaluation results\n\n{args.maps} generated facilities per cell (seeds {seeds[0]}-{seeds[-1]}), 31 × 21 grid, "
          f"time limit {MAX_TICKS} ticks. Completion time and path cost are averaged over successful runs. "
          "Values are mean ± standard deviation.\n"]

    jobs = [(c["id"], s, dyn) for dyn in DYNAMICS for c in AGENT_CONFIGS for s in seeds]
    print(f"Running {len(jobs)} missions on {os.cpu_count()} cores...", flush=True)
    with Pool() as pool:
        rows = pool.map(job, jobs, chunksize=4)
    write_csv("results/missions.csv", rows)

    for dyn, level in DYNAMICS.items():
        md.append(f"\n## Missions: {level['label']} facility\n\n"
                  "| Agent design | Success | Ticks | Path cost | States explored | Replans | Drone hits | Laser zaps | Final hull | Failures |\n"
                  "|---|---|---|---|---|---|---|---|---|---|\n")
        for c in AGENT_CONFIGS:
            s = summarize([r for r in rows if r["config"] == c["id"] and r["dynamics"] == dyn])
            fails = ", ".join(f"{k} {r}" for r, k in s["reasons"].items() if r != "escaped") or "none"
            md.append(f"| {c['label']} | **{fmt(s['success']['mean'] * 100)}%** | {pm(s['ticks_ok'])} | {pm(s['cost_ok'])} | "
                      f"{pm(s['expanded'])} | {fmt(s['replans']['mean'], 1)} | {fmt(s['hits']['mean'], 2)} | "
                      f"{fmt(s['zaps']['mean'], 2)} | {fmt(s['integrity']['mean'])} | {fails} |\n")
        print(f"  {level['label']} done", flush=True)

    unit7 = [r for r in rows if r["config"] == "unit7" and r["dynamics"] == "normal"]
    avg = lambda k: sum(r[k] for r in unit7) / len(unit7)
    md.append("\n### Why UNIT-7 replanned (Dynamic facility, mean per mission)\n\n"
              "| Route blocked by a collapse | Laser gate timing | Threat drift or drone | Pushed off route (evasion or zap) |\n|---|---|---|---|\n"
              f"| {avg('replans_blocked'):.2f} | {avg('replans_gate'):.2f} | {avg('replans_threat'):.2f} | {avg('replans_deviated'):.2f} |\n")

    print("Comparing planners...", flush=True)
    prow, psum = planner_compare(seeds[:40])
    write_csv("results/planners.csv", prow)
    md.append(f"\n## Planners on identical queries\n\nThe same start-to-goal queries (exit, keycards, terminal) on {min(40, len(seeds))} maps "
              "with 40 extra coolant cells (step cost 6). Optimal means the cost equals Dijkstra's.\n\n"
              "| Planner | Queries | States explored | Path cost | Optimal | Mean cost above optimal | Time (ms) |\n|---|---|---|---|---|---|---|\n")
    for name, s in psum.items():
        opt = "n/a" if s["optimal"] != s["optimal"] else f"{s['optimal'] * 100:.0f}%"
        gap = "n/a" if s["gap"] != s["gap"] else f"{s['gap'] * 100:.1f}%"
        md.append(f"| {PLANNER_NAMES[name]} | {s['n']} | {pm(s['expanded'])} | {pm(s['cost'], 1)} | {opt} | {gap} | {fmt(s['ms']['mean'], 3)} |\n")

    print("Comparing lock solvers...", flush=True)
    crow, csum = csp_compare(100)
    write_csv("results/csp.csv", crow)
    md.append(f"\n## Lock solvers\n\n100 generated vault locks (5 dials, minimal clue sets, mean {csum['bt']['clues']['mean']:.1f} clues).\n\n"
              "| Solver | Assignments | Backtracks | Constraint checks | Time (ms) | Correct |\n|---|---|---|---|---|---|\n")
    for mode, s in csum.items():
        md.append(f"| {CSP_MODES[mode]} | {pm(s['assignments'], 1)} | {pm(s['backtracks'], 1)} | {pm(s['checks'])} | "
                  f"{fmt(s['ms']['mean'], 3)} | {s['correct'] * 100:.0f}% |\n")

    print("Learning vs planning...", flush=True)
    qrows = [learning_vs_planning(seed) for seed in range(1, 9)]
    write_csv("results/qlearning.csv", qrows)
    md.append("\n## Learning vs planning (Q-learning lab)\n\n17 × 11 facility, 2 keycards. The policy is trained for 2,500 episodes, "
              "then rubble is dropped on its learned route.\n\n"
              "| Seed | Episodes to first success | Learned steps | A* optimal steps | Policy after collapse | A* after collapse | Episodes to recover |\n"
              "|---|---|---|---|---|---|---|\n")
    for q in qrows:
        md.append(f"| {q['seed']} | {q['first_success'] or '>2500'} | {q['learned_steps'] or 'fails'} | {q['optimal_steps']} | "
                  f"{q['after_collapse']} | {q['astar_after']} (replanned at once) | "
                  f"{q['recover_episodes'] if q['recover_episodes'] is not None else '>3000'} |\n")

    with open("results/summary.md", "w", encoding="utf-8") as f:
        f.write("".join(md))
    print("".join(md))
    print(f"Wrote results/ in {time.time() - started:.0f} s")


if __name__ == "__main__":
    main()
