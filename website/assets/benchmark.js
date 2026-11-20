/* Benchmark page: runs the Python evaluation (escape_room/evaluation.py) mission by mission,
 * yielding to the browser between missions so the page stays responsive. */
(function () {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const UI = window.UI;
  const CFG_COL = { unit7: '#2563eb', snapshot: '#93c5fd', crisp: '#15803d', dijkstra: '#7c3aed', greedy: '#ca8a04', bfs: '#db2777', script: '#9ca3af' };
  const fmt = (v, d = 0) => (Number.isFinite(v) ? v.toFixed(d) : '–');
  const yieldUI = () => new Promise((r) => setTimeout(r, 0));
  let py = null, info = null, stop = false, lastRows = [];
  const buttons = ['benchRun', 'microRun', 'cspRun'];
  buttons.forEach((id) => { $(id).disabled = true; });

  function section(id, title, sub) {
    const out = $('benchOut');
    let el = $(id);
    if (!el) { el = document.createElement('div'); el.id = id; el.className = 'panel'; out.insertBefore(el, out.firstChild); }
    el.scrollIntoView({ behavior: 'smooth', block: 'start' });
    el.innerHTML = `<header><h2>${title}</h2><small>${sub || ''}</small></header>`;
    return el;
  }
  const busy = (on) => buttons.forEach((id) => { $(id).disabled = on; });

  $('benchRun').onclick = async () => {
    const ids = [...document.querySelectorAll('#benchCfgs input:checked')].map((i) => i.value);
    if (!ids.length) { $('benchStatus').textContent = 'Select at least one agent design.'; return; }
    const n = Math.max(1, Math.min(100, +$('benchN').value || 10));
    const s0 = Math.max(1, +$('benchSeed').value || 5000);
    const dyn = $('benchDyn').value;
    const jobs = [];
    for (const id of ids) for (let k = 0; k < n; k++) jobs.push([id, s0 + k]);
    const rows = [];
    stop = false;
    busy(true); $('benchStop').disabled = false; $('benchCsv').disabled = true;
    const t0 = performance.now();
    let k = 0;
    while (k < jobs.length && !stop) {
      const slice = performance.now();
      while (k < jobs.length && performance.now() - slice < 60) { rows.push(py('bench_mission', jobs[k][0], jobs[k][1], dyn)); k++; }
      $('benchProg').style.width = ((100 * k) / jobs.length).toFixed(1) + '%';
      $('benchStatus').textContent = `${k} of ${jobs.length} missions`;
      await yieldUI();
    }
    $('benchStatus').textContent = `${stop ? 'Stopped after' : 'Finished'} ${k} missions in ${((performance.now() - t0) / 1000).toFixed(1)} s.`;
    busy(false); $('benchStop').disabled = true; $('benchCsv').disabled = !rows.length;
    lastRows = rows;
    if (rows.length) renderMissions(rows, dyn, n);
  };
  $('benchStop').onclick = () => { stop = true; };
  $('benchCsv').onclick = () => {
    const cols = Object.keys(lastRows[0]);
    UI.download('unit7-missions.csv', cols.join(',') + '\n' + lastRows.map((r) => cols.map((c) => r[c]).join(',')).join('\n') + '\n');
  };

  function renderMissions(rows, dyn, n) {
    const el = section('outMission', `Mission experiment: ${info.dynamics[dyn]} facility`, `${n} facilities per design · mean ± std`);
    const sums = py('bench_summary', JSON.stringify(rows));
    const S = info.configs.filter((c) => sums[c.id]).map((c) => ({ c, s: sums[c.id] }));
    const cols = [
      ['Success', (s) => s.success.mean * 100, (v) => fmt(v) + '%', 'max'],
      ['Ticks', (s) => s.ticks_ok.mean, (v, s) => `${fmt(v)} ± ${fmt(s.ticks_ok.std)}`, 'min'],
      ['Path cost', (s) => s.cost_ok.mean, (v, s) => `${fmt(v)} ± ${fmt(s.cost_ok.std)}`, 'min'],
      ['States explored', (s) => s.expanded.mean, (v) => Math.round(v).toLocaleString(), 'min'],
      ['Replans', (s) => s.replans.mean, (v) => fmt(v, 1), null],
      ['Drone hits', (s) => s.hits.mean, (v) => fmt(v, 2), 'min'],
      ['Laser zaps', (s) => s.zaps.mean, (v) => fmt(v, 2), 'min'],
      ['Final hull', (s) => s.integrity.mean, (v) => fmt(v), 'max'],
    ];
    // Only designs that usually succeed compete for "best" (a 10%-success agent is not the fastest).
    const best = cols.map(([, get, , dir], j) => {
      if (!dir) return null;
      const vs = S.filter(({ s }) => j === 0 || s.success.mean >= 0.5).map(({ s }) => get(s)).filter(Number.isFinite);
      return dir === 'max' ? Math.max(...vs) : Math.min(...vs);
    });
    let h = '<div class="tablewrap"><table><thead><tr><th>Agent design</th>' + cols.map((c) => `<th>${c[0]}</th>`).join('') + '<th>Failures</th></tr></thead><tbody>';
    for (const { c, s } of S) {
      h += `<tr><td><i class="swatch" style="background:${CFG_COL[c.id]}"></i>${UI.esc(c.label)}</td>`;
      cols.forEach(([, get, show], j) => {
        const v = get(s);
        const isBest = best[j] != null && Number.isFinite(v) && (j === 0 || s.success.mean >= 0.5) && Math.abs(v - best[j]) < 1e-9 && S.length > 1;
        h += `<td class="${isBest ? 'best' : ''}">${show(v, s)}</td>`;
      });
      const fails = Object.entries(s.reasons).filter(([r]) => r !== 'escaped').map(([r, k]) => `${k} ${r}`).join(', ');
      h += `<td>${fails || 'none'}</td></tr>`;
    }
    h += '</tbody></table></div><p class="hint" style="margin-top:8px">Ticks and path cost are averaged over successful runs. Green marks the best value in each column.</p><div class="charts"><canvas id="ch1"></canvas><canvas id="ch2"></canvas><canvas id="ch3"></canvas><canvas id="ch4"></canvas></div>';
    el.innerHTML += h;
    const labels = S.map(({ c }) => c.label), colors = S.map(({ c }) => CFG_COL[c.id]);
    UI.barChart($('ch1'), { title: 'Success rate (%)', labels, colors, values: S.map(({ s }) => s.success.mean * 100), max: 100, fmt: (v) => fmt(v) + '%' });
    UI.barChart($('ch2'), { title: 'Completion time, ticks (successful runs)', labels, colors, values: S.map(({ s }) => s.ticks_ok.mean || 0), errors: S.map(({ s }) => s.ticks_ok.std || 0), fmt: (v) => fmt(v) });
    UI.barChart($('ch3'), { title: 'States explored per mission', labels, colors, values: S.map(({ s }) => s.expanded.mean), fmt: (v) => (v >= 1000 ? (v / 1000).toFixed(1) + 'k' : fmt(v)) });
    UI.barChart($('ch4'), { title: 'Final hull integrity (%)', labels, colors, values: S.map(({ s }) => s.integrity.mean), max: 100, fmt: (v) => fmt(v) });
  }

  $('microRun').onclick = async () => {
    const el = section('outMicro', 'Planner comparison', 'running…');
    busy(true);
    await yieldUI(); await yieldUI();
    const res = py('bench_planners', 20);
    busy(false);
    const names = info.planners, order = ['astar', 'dijkstra', 'greedy', 'bfs', 'astar_snapshot', 'astar_spacetime'];
    el.querySelector('small').textContent = `${res.astar.n} identical queries per planner on 20 maps with 40 coolant cells`;
    let h = '<div class="tablewrap"><table><thead><tr><th>Planner</th><th>States explored</th><th>Path cost</th><th>Optimal</th><th>Cost above optimal</th><th>Time ms</th></tr></thead><tbody>';
    for (const a of order) {
      const s = res[a];
      h += `<tr><td>${names[a]}</td><td>${fmt(s.expanded.mean)} ± ${fmt(s.expanded.std)}</td><td>${fmt(s.cost.mean, 1)}</td><td>${Number.isFinite(s.optimal) ? fmt(s.optimal * 100) + '%' : 'n/a'}</td><td>${Number.isFinite(s.gap) ? '+' + fmt(s.gap * 100, 1) + '%' : 'n/a'}</td><td>${fmt(s.ms.mean, 2)}</td></tr>`;
    }
    h += '</tbody></table></div><p class="hint" style="margin-top:8px">A* and Dijkstra are always optimal; A* gets there with far fewer states because its Manhattan heuristic never overestimates. Greedy explores least but returns costlier paths, and BFS ignores step costs. The last two rows switch the laser gates on: planning over (cell, time) costs more states but never walks into a firing gate.</p><div class="charts"><canvas id="mc1"></canvas><canvas id="mc2"></canvas></div>';
    el.innerHTML += h;
    const four = ['astar', 'dijkstra', 'greedy', 'bfs'], cols = ['#2563eb', '#7c3aed', '#ca8a04', '#db2777'];
    UI.barChart($('mc1'), { title: 'States explored per query', labels: four.map((a) => names[a]), colors: cols, values: four.map((a) => res[a].expanded.mean), fmt: (v) => fmt(v) });
    UI.barChart($('mc2'), { title: 'Queries solved optimally (%)', labels: four.map((a) => names[a]), colors: cols, values: four.map((a) => res[a].optimal * 100), max: 100, fmt: (v) => fmt(v) });
  };

  $('cspRun').onclick = async () => {
    const el = section('outCsp', 'Lock solver comparison', 'running…');
    busy(true);
    await yieldUI(); await yieldUI();
    const res = py('bench_solvers', 40);
    busy(false);
    const modes = Object.keys(info.solvers), labels = modes.map((m) => info.solvers[m]);
    el.querySelector('small').textContent = `40 generated locks, mean ${fmt(res.bt.clues.mean, 1)} clues each`;
    let h = '<div class="tablewrap"><table><thead><tr><th>Solver</th><th>Assignments</th><th>Backtracks</th><th>Constraint checks</th><th>Time ms</th><th>Correct</th></tr></thead><tbody>';
    modes.forEach((m, j) => {
      const s = res[m];
      h += `<tr><td>${labels[j]}</td><td>${fmt(s.assignments.mean, 1)}</td><td>${fmt(s.backtracks.mean, 1)}</td><td>${fmt(s.checks.mean)}</td><td>${fmt(s.ms.mean, 2)}</td><td>${fmt(s.correct * 100)}%</td></tr>`;
    });
    h += '</tbody></table></div><p class="hint" style="margin-top:8px">In the simulator, dialling in the code takes one tick per four assignments, so the solver choice directly changes escape time.</p><div class="charts"><canvas id="cc1"></canvas><canvas id="cc2"></canvas></div>';
    el.innerHTML += h;
    const cols = ['#9ca3af', '#ca8a04', '#7c3aed', '#2563eb'];
    UI.barChart($('cc1'), { title: 'Assignments tried', labels, colors: cols, values: modes.map((m) => res[m].assignments.mean), fmt: (v) => fmt(v) });
    UI.barChart($('cc2'), { title: 'Constraint checks', labels, colors: cols, values: modes.map((m) => res[m].checks.mean), fmt: (v) => fmt(v) });
  };

  PY.boot(null, $('pynote')).then((p) => {
    py = p;
    info = py('bench_info');
    $('benchCfgs').innerHTML = info.configs.map((c) =>
      `<label><input type="checkbox" value="${c.id}" checked><span><i class="swatch" style="background:${CFG_COL[c.id]}"></i>${UI.esc(c.label)}</span></label>`).join('');
    busy(false);
  }).catch(() => {});
})();
