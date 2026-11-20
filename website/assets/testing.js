/* Testing guide: runs the Python checks (escape_room/checks.py) in the browser, and the
 * requirement checklist. */
(function () {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const esc = window.UI.esc;
  let py = null, TESTS = [];
  $('runTests').disabled = true;

  function renderList(results) {
    let html = '', group = '';
    TESTS.forEach((t, i) => {
      if (t.group !== group) {
        if (group) html += '</ul>';
        group = t.group;
        html += `<div class="testgroup">${esc(group)}</div><ul class="testlist">`;
      }
      const r = results[i];
      const cls = !r ? '' : r === 'run' ? 'run' : r.passed ? 'pass' : 'fail';
      const mark = !r ? '' : r === 'run' ? '…' : r.passed ? '✓' : '✗';
      html += `<li><span class="st ${cls}">${mark}</span><span><span class="nm">${esc(t.name)}</span><span class="pv">${esc(t.proves)}</span></span><span class="dt">${r && r !== 'run' ? esc(r.detail) : ''}</span></li>`;
    });
    $('testOut').innerHTML = html + (group ? '</ul>' : '');
  }

  $('runTests').onclick = async () => {
    const btn = $('runTests');
    btn.disabled = true;
    const results = [], t0 = performance.now();
    let pass = 0;
    for (let i = 0; i < TESTS.length; i++) {
      results[i] = 'run';
      renderList(results);
      $('testStatus').textContent = `Running ${i + 1} of ${TESTS.length}: ${TESTS[i].name}`;
      await new Promise((r) => setTimeout(r, 30)); // let the page repaint between tests
      results[i] = py('test_run', i);
      if (results[i].passed) pass++;
      $('testProg').style.width = ((100 * (i + 1)) / TESTS.length).toFixed(0) + '%';
    }
    renderList(results);
    const fail = TESTS.length - pass;
    $('testStatus').innerHTML = `<b style="color:${fail ? 'var(--alarm)' : 'var(--ok)'}">${pass} passed, ${fail} failed</b> in ${((performance.now() - t0) / 1000).toFixed(1)} s`;
    btn.disabled = false;
    btn.textContent = 'Run again';
  };

  /* ---------- requirement checklist ---------- */
  const CHECKS = [
    { req: 'An agent navigates an environment, overcomes obstacles, solves a challenge and reaches a goal',
      todo: '<a href="simulator.html?scenario=escape">Open "Watch a full escape"</a> and let it run.',
      see: 'The agent collects three keycards, cracks the lock at the purple terminal and reaches the exit. The banner says <b>Escaped</b>.' },
    { req: 'Technique: A* search for navigation and path planning',
      todo: '<a href="simulator.html?scenario=block">Open "Block the planned route"</a>.',
      see: 'At tick 25 rubble lands on the dashed route, and the route immediately redraws around it. The blue squares show the cells A* explored. The Log says <b>Replan (route blocked)</b>.' },
    { req: 'Technique: constraint satisfaction for puzzle rules',
      todo: '<a href="simulator.html?scenario=csp">Open "Crack the lock the slow way"</a>, then switch the lock solver to MRV + FC + AC-3.',
      see: 'In the Lock tab the dials replay the real search. Plain backtracking needs far more assignments, and the agent waits at the terminal much longer.' },
    { req: 'Technique: a behaviour tree controls the agent',
      todo: 'In any run, open the <b>Decisions</b> tab.',
      see: 'The highlighted path through the tree changes from Collect keycards to Crack the lock to Escape, and Survive takes over whenever the drone gets close.' },
    { req: 'Technique: fuzzy logic for decisions under uncertainty',
      todo: '<a href="simulator.html?scenario=alarm">Open "Escape a hunting drone"</a> and watch the <b>Threat</b> tab.',
      see: 'As the drone closes in, the "Near" and "Alert" memberships rise, rules fire, and the threat crosses the red line. The agent switches to <b>Evade drone</b>.' },
    { req: 'Technique: a finite state machine (the drone)',
      todo: 'Same scenario, <b>Drone</b> tab.',
      see: 'The drone moves through Patrol, Alert, Chase and Cooldown, with the current state highlighted.' },
    { req: 'Technique: reinforcement learning',
      todo: 'Open the <a href="learning.html">Learning lab</a>, train 1,000 episodes, then press "Collapse the learned route".',
      see: 'The learning curve falls to the A* optimum. After the collapse the learned policy fails, while A* reroutes at once.' },
    { req: 'Dynamic: an obstacle changes position',
      todo: 'In the simulator, choose <b>move drone</b> under Operator and click a cell next to the agent.',
      see: 'The red threat field moves with the drone, and the agent replans or evades.' },
    { req: 'Dynamic: a route becomes unavailable',
      todo: 'Choose <b>drop rubble</b> and click a cell on the dashed route, or press <b>Collapse the route</b>.',
      see: 'The route is replaced at once; the Log records the replan and its reason.' },
    { req: 'Dynamic: a constraint changes during execution',
      todo: '<a href="simulator.html?scenario=surge">Open "Change the lock after it is cracked"</a>.',
      see: 'After the code is found, the clues change (new ones in purple). "Vault unlocked?" fails, and the agent returns to the terminal and solves the new puzzle.' },
    { req: 'The agent responds to change instead of following a fixed sequence',
      todo: '<a href="simulator.html?scenario=script">Open "A fixed plan in a changing world"</a>, then compare with "Watch a full escape" on the same seed.',
      see: 'The fixed script gets stuck at a collapse or is caught by the drone. The adaptive agent escapes the same facility.' },
    { req: 'Evaluation: completion time, path cost, states explored, success rate',
      todo: 'Open the <a href="benchmark.html">Benchmark</a> page and press Run experiment.',
      see: 'A table and charts with every measure for seven agent designs, plus a CSV of every individual run.' },
  ];
  const KEY = 'unit7-checklist';
  let saved = {};
  try { saved = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { saved = {}; }
  $('checklist').innerHTML = CHECKS.map((c, i) =>
    `<tr><td><input type="checkbox" data-i="${i}" aria-label="Checked: ${esc(c.req)}"${saved[i] ? ' checked' : ''}></td><td><b>${esc(c.req)}</b></td><td>${c.todo}</td><td>${c.see}</td></tr>`).join('');
  const count = () => { $('checkCount').textContent = `${document.querySelectorAll('#checklist input:checked').length} of ${CHECKS.length} checked.`; };
  $('checklist').addEventListener('change', (e) => {
    if (!e.target.dataset.i) return;
    saved[e.target.dataset.i] = e.target.checked;
    try { localStorage.setItem(KEY, JSON.stringify(saved)); } catch (err) { /* storage unavailable: ticks just won't persist */ }
    count();
  });
  count();

  PY.boot(null, $('pynote')).then((p) => {
    py = p;
    TESTS = py('tests_list');
    renderList([]);
    $('runTests').disabled = false;
  }).catch(() => {});
})();
