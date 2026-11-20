/* Learning lab: Q-learning training (escape_room/qlearn.py), value map, policy playback and the
 * learning-versus-planning test. */
(function () {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const UI = window.UI;
  const cv = $('qCanvas'), ctx = cv.getContext('2d');
  const WALL = 1, RUBBLE = 2;
  let py = null, L = null, show = null, anim = null, busy = false, cs = 30;
  const controls = ['qTrain', 'qNew', 'qPlay', 'qAstar', 'qMutate'];
  const enable = (on) => controls.forEach((id) => { $(id).disabled = !on; });
  enable(false);

  const readout = (h) => { $('qReadout').innerHTML = h; };
  const refresh = () => { L = py('lab_state', +$('qMask').value || 0); };

  function newLab() {
    L = py('lab_new', JSON.stringify({ seed: Math.max(1, +$('qSeed').value || 1), alpha: +$('qAlpha').value, gamma: +$('qGamma').value, eps_decay: +$('qDecay').value }));
    show = null; anim = null;
    const sel = $('qMask');
    sel.innerHTML = '';
    for (let m = 0; m < L.masks; m++) {
      const held = L.keys.filter((_, i) => m & (1 << i)).map((k) => k.name.toLowerCase());
      sel.add(new Option(held.length ? 'holding ' + held.join(' + ') : 'no keycards held', m));
    }
    readout('Untrained: the Q-table is all zeros, so the policy has no preferences yet.');
    draw(); curve();
  }

  function size() {
    const avail = cv.parentElement.clientWidth - 24;
    cs = Math.max(12, Math.min(44, Math.floor(avail / L.W)));
    const dpr = window.devicePixelRatio || 1;
    cv.width = L.W * cs * dpr; cv.height = L.H * cs * dpr;
    cv.style.width = L.W * cs + 'px'; cv.style.height = L.H * cs + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function draw() {
    if (!L) return;
    size();
    const mask = +$('qMask').value || 0, V = L.values;
    let lo = Infinity, hi = -Infinity;
    for (const v of V) if (v) { lo = Math.min(lo, v[0]); hi = Math.max(hi, v[0]); }
    const trained = L.episodes > 0 && hi > lo;
    for (let y = 0; y < L.H; y++) for (let x = 0; x < L.W; x++) {
      const i = y * L.W + x, X = x * cs, Y = y * cs, t = L.tiles[i];
      if (t === WALL) { ctx.fillStyle = '#2f3b48'; ctx.fillRect(X, Y, cs, cs); continue; }
      if (t === RUBBLE) { ctx.fillStyle = '#b08559'; ctx.fillRect(X, Y, cs, cs); continue; }
      ctx.fillStyle = '#ffffff'; ctx.fillRect(X, Y, cs, cs);
      if (trained && V[i]) {
        const f = (V[i][0] - lo) / (hi - lo);
        ctx.globalAlpha = 0.04 + 0.42 * f * f;
        ctx.fillStyle = '#2563eb'; ctx.fillRect(X + 1, Y + 1, cs - 2, cs - 2);
        ctx.globalAlpha = 1;
        const [dx, dy] = L.actions[V[i][1]];
        const cx = X + cs / 2, cy = Y + cs / 2, Ln = cs * 0.28;
        ctx.strokeStyle = 'rgba(31,41,51,0.55)'; ctx.lineWidth = 1.3;
        ctx.beginPath(); ctx.moveTo(cx - dx * Ln, cy - dy * Ln); ctx.lineTo(cx + dx * Ln, cy + dy * Ln);
        ctx.lineTo(cx + dx * Ln - (dx * 0.4 + dy * 0.35) * Ln, cy + dy * Ln - (dy * 0.4 - dx * 0.35) * Ln);
        ctx.moveTo(cx + dx * Ln, cy + dy * Ln);
        ctx.lineTo(cx + dx * Ln - (dx * 0.4 - dy * 0.35) * Ln, cy + dy * Ln - (dy * 0.4 + dx * 0.35) * Ln);
        ctx.stroke();
      }
      ctx.strokeStyle = '#eef0f3'; ctx.lineWidth = 1; ctx.strokeRect(X + 0.5, Y + 0.5, cs - 1, cs - 1);
    }
    L.keys.forEach((k, i) => {
      ctx.globalAlpha = mask & (1 << i) ? 0.25 : 1;
      ctx.fillStyle = k.color; ctx.fillRect(k.x * cs + cs * 0.22, k.y * cs + cs * 0.3, cs * 0.56, cs * 0.4);
      ctx.globalAlpha = 1;
    });
    ctx.strokeStyle = '#15803d'; ctx.lineWidth = 2; ctx.strokeRect(L.exit[0] * cs + 3, L.exit[1] * cs + 3, cs - 6, cs - 6);
    ctx.strokeStyle = '#9aa3ae'; ctx.lineWidth = 1; ctx.strokeRect(L.start[0] * cs + 4.5, L.start[1] * cs + 4.5, cs - 9, cs - 9);
    if (show && show.path.length > 1) {
      const upto = anim ? Math.min(show.path.length, anim.k + 1) : show.path.length;
      ctx.strokeStyle = show.color; ctx.lineWidth = 2.5; ctx.globalAlpha = 0.9; ctx.beginPath();
      for (let k = 0; k < upto; k++) { const [x, y] = show.path[k], X = x * cs + cs / 2, Y = y * cs + cs / 2; if (k) ctx.lineTo(X, Y); else ctx.moveTo(X, Y); }
      ctx.stroke(); ctx.globalAlpha = 1;
      const [px, pyy] = show.path[upto - 1];
      ctx.fillStyle = show.color; ctx.beginPath(); ctx.arc(px * cs + cs / 2, pyy * cs + cs / 2, cs * 0.28, 0, 7); ctx.fill();
    }
  }

  function movingAvg(xs, k) {
    const out = []; let s = 0;
    for (let i = 0; i < xs.length; i++) { s += xs[i]; if (i >= k) s -= xs[i - k]; out.push(s / Math.min(i + 1, k)); }
    return out;
  }
  let optimum = null;
  function curve() {
    const steps = L.curve.steps, succ = L.curve.success.map((v) => v * 100);
    if (optimum === null) optimum = py('lab_optimal').steps;
    UI.lineChart($('qCurve'), {
      title: 'Learning curve: steps per episode', h: 240, xlabel: steps.length ? `episode (1–${steps.length})` : 'episode',
      ymax: L.max_steps,
      series: [
        { data: steps, color: '#9aa3ae', alpha: 0.5, width: 1, label: 'raw' },
        { data: movingAvg(steps, 50), color: '#2563eb', width: 2, label: '50-episode mean' },
        { data: movingAvg(succ, 50).map((v) => (v / 100) * L.max_steps), color: '#15803d', width: 1.5, label: 'success rate (scaled)' },
        { data: steps.length ? steps.map(() => optimum) : [], color: '#7c3aed', width: 1, label: 'A* optimum' },
      ],
      marks: L.collapses.map((m) => ({ i: m, color: '#ea580c', label: 'collapse' })),
    });
  }

  async function train(n) {
    if (busy) return;
    busy = true; anim = null; show = null;
    enable(false);
    for (let done = 0; done < n; done += 50) {
      const r = py('lab_train', 50);
      refresh(); draw(); curve();
      readout(`Episode <b>${r.episodes}</b>, ε = ${r.eps.toFixed(3)}. Last 50 episodes: ${Math.round(r.success * 100)}% reached the exit, mean ${Math.round(r.steps)} steps.`);
      await new Promise((res) => setTimeout(res, 0));
    }
    busy = false; enable(true);
  }

  function play(path, color, done) {
    show = { path, color };
    anim = { k: 0 };
    const go = () => {
      if (!anim) return;
      draw();
      if (anim.k >= path.length - 1) { anim = null; draw(); if (done) done(); return; }
      anim.k++;
      setTimeout(go, 70);
    };
    go();
  }

  $('qTrain').onclick = () => train(500);
  $('qNew').onclick = () => { optimum = null; newLab(); };
  $('qMask').onchange = () => { refresh(); draw(); };
  for (const id of ['qSeed', 'qAlpha', 'qGamma', 'qDecay']) $(id).onchange = () => { if (py) { optimum = null; newLab(); } };
  $('qPlay').onclick = () => {
    const g = py('lab_greedy'), opt = py('lab_optimal');
    play(g.path, g.success ? '#2563eb' : '#dc2626', () => readout(g.success
      ? `<span class="good">The learned policy escapes in <b>${g.steps}</b> steps</span> (A* optimum: ${opt.steps}). No search while it runs, just a table lookup per step.`
      : `<span class="bad">The learned policy fails: ${g.reason}</span> after ${g.steps} steps. ${L.episodes ? 'It needs more training, or the map has changed under it.' : 'Train it first.'}`));
  };
  $('qAstar').onclick = () => {
    const t0 = performance.now(), opt = py('lab_optimal'), ms = performance.now() - t0;
    play(opt.path, '#7c3aed', () => readout(`A* (trying every keycard order) finds a <b>${opt.steps}</b>-step escape, exploring ${opt.expanded} states in ${ms.toFixed(1)} ms. It needs no training, but it has to search every time.`));
  };
  $('qMutate').onclick = () => {
    const r = py('lab_collapse');
    if (!r.ok) {
      readout({ untrained: 'Train the policy first, so it has a learned route to collapse.',
        'no policy': 'The policy does not reach the exit yet. Train more before testing it against a change.',
        'no cell': 'No cell on the learned route can collapse without sealing off the exit.' }[r.why]);
      return;
    }
    optimum = r.optimal.steps;
    refresh(); curve();
    const [x, y] = r.cell, after = r.after;
    play(after.path, after.success ? '#2563eb' : '#dc2626', () => readout(
      `Rubble fell at (${x}, ${y}). ${after.success ? '<span class="good">The policy still escapes.</span>' : `<span class="bad">The learned policy now fails: ${after.reason}.</span>`} ` +
      `A* replanned around it at once: <b>${r.optimal.steps}</b> steps. Train again to watch the policy re-learn.`));
  };

  let rt = 0;
  window.addEventListener('resize', () => { clearTimeout(rt); rt = setTimeout(() => { if (L) { draw(); curve(); } }, 120); });
  PY.boot($('pyload'), $('pynote')).then((p) => { py = p; newLab(); enable(true); }).catch(() => {});
})();
