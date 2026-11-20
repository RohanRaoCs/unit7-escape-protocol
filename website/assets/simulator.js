/* Simulator page. The simulation is the Python package (escape_room/web.py); this script
 * draws the state it returns, shows the instrument panels and sends button presses back. */
(function () {
  'use strict';
  const $ = (id) => document.getElementById(id);
  const UI = window.UI;
  const COL = {
    floor: '#ffffff', grid: '#eef0f3', wall: '#2f3b48', rubble: '#b08559', rubbleLine: '#7a5a3a',
    agent: '#2563eb', drone: '#ea580c', alert: '#d97706', alarm: '#dc2626', cool: '#9ca3af', coolant: '#14b8a6',
    ok: '#15803d', violet: '#7c3aed', faint: '#9aa3ae', ink: '#1f2933',
  };
  const DRONE_COL = { PATROL: COL.drone, ALERT: COL.alert, CHASE: COL.alarm, COOLDOWN: COL.cool };
  const WALL = 1, RUBBLE = 2;
  const CSP_NAMES = { bt: 'Plain backtracking', fc: 'Forward checking', mrv_fc: 'MRV + forward checking', mrv_fc_ac3: 'MRV + FC + AC-3' };

  let py = null, S = null, FZ = null;
  const app = { running: false, acc: 0, last: 0, speed: 8, cs: 24, ov: { explored: true, risk: true, path: true }, tool: 'inspect', hover: null, fx: [], logSig: '' };

  /* ---------------- setup ---------------- */
  function cfgFromUI() {
    return {
      seed: Math.max(1, +$('seed').value || 1), algo: $('cfgAlgo').value, csp: $('cfgCsp').value, dynamics: $('cfgDyn').value,
      fuzzy: $('cfgFuzzy').checked, time_aware: $('cfgTime').checked, adaptive: $('cfgAdaptive').checked,
    };
  }
  function newSim() {
    if (!py) return;
    S = py('new_sim', JSON.stringify(cfgFromUI()));
    FZ = py('fuzzy_rules');
    app.acc = 0; app.fx = []; app.logSig = '';
    $('banner').hidden = true;
    buildRules(); buildFSM();
    resize();
    refreshPanels();
  }
  function setRunning(v) {
    app.running = !!(v && S && !S.done);
    $('btnRun').textContent = app.running ? 'Pause' : 'Run';
  }
  function take(state) {
    S = state;
    const now = performance.now();
    for (const f of S.fx) app.fx.push(Object.assign({ born: now }, f));
  }

  /* ---------------- canvas ---------------- */
  const canvas = $('world');
  const ctx = canvas.getContext('2d');
  function resize() {
    if (!S) return;
    const avail = $('stage').clientWidth - 20;
    app.cs = Math.max(10, Math.min(34, Math.floor(avail / S.W)));
    const dpr = window.devicePixelRatio || 1;
    const cw = S.W * app.cs, ch = S.H * app.cs;
    canvas.width = cw * dpr; canvas.height = ch * dpr;
    canvas.style.width = cw + 'px'; canvas.style.height = ch + 'px';
    canvas.style.margin = '0 auto';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }
  new ResizeObserver(() => resize()).observe($('stage'));
  const lerp = (a, b, f) => a + (b - a) * f;

  function draw(frac) {
    if (!S) return;
    const W = S.W, H = S.H, cs = app.cs, a = S.agent;
    const now = performance.now(), T = now / 1000;
    ctx.clearRect(0, 0, W * cs, H * cs);

    for (let y = 0; y < H; y++) for (let x = 0; x < W; x++) {
      const i = y * W + x, t = S.tiles[i], X = x * cs, Y = y * cs;
      if (t === WALL) { ctx.fillStyle = COL.wall; ctx.fillRect(X, Y, cs, cs); continue; }
      if (t === RUBBLE) {
        ctx.fillStyle = COL.rubble; ctx.fillRect(X, Y, cs, cs);
        ctx.strokeStyle = COL.rubbleLine; ctx.lineWidth = 1.5; ctx.beginPath();
        ctx.moveTo(X + cs * 0.15, Y + cs * 0.3); ctx.lineTo(X + cs * 0.5, Y + cs * 0.55); ctx.lineTo(X + cs * 0.85, Y + cs * 0.25);
        ctx.moveTo(X + cs * 0.5, Y + cs * 0.55); ctx.lineTo(X + cs * 0.45, Y + cs * 0.9); ctx.stroke();
        continue;
      }
      ctx.fillStyle = COL.floor; ctx.fillRect(X, Y, cs, cs);
      ctx.strokeStyle = COL.grid; ctx.lineWidth = 1; ctx.strokeRect(X + 0.5, Y + 0.5, cs - 1, cs - 1);
      if (S.hazard[i]) { ctx.globalAlpha = 0.2; ctx.fillStyle = COL.coolant; ctx.fillRect(X + 1, Y + 1, cs - 2, cs - 2); ctx.globalAlpha = 1; }
    }

    // fuzzy threat field
    if (app.ov.risk && S.risk) {
      ctx.fillStyle = COL.alarm;
      for (let i = 0; i < S.risk.length; i++) {
        const r = S.risk[i];
        if (r < 24) continue;
        ctx.globalAlpha = ((r - 24) / 76) * 0.28;
        ctx.fillRect((i % W) * cs + 1, Math.floor(i / W) * cs + 1, cs - 2, cs - 2);
      }
      ctx.globalAlpha = 1;
    }

    // states explored by the most recent search (fades over 15 ticks)
    if (app.ov.explored && S.searched) {
      const fade = 1 - S.searched.age / 15, pad = cs * 0.22;
      for (const [c, k] of S.searched.cells) {
        ctx.globalAlpha = 0.22 * fade;
        ctx.fillStyle = k < 0.5 ? '#8b5cf6' : '#3b82f6';
        ctx.fillRect((c % W) * cs + pad, Math.floor(c / W) * cs + pad, cs - 2 * pad, cs - 2 * pad);
      }
      ctx.globalAlpha = 1;
    }

    // laser gates
    for (const g of S.gates) {
      const X = g.x * cs, Y = g.y * cs;
      ctx.fillStyle = g.on ? COL.alarm : '#d1d5db';
      if (g.o === 'v') { ctx.fillRect(X + cs / 2 - 3, Y, 6, 3); ctx.fillRect(X + cs / 2 - 3, Y + cs - 3, 6, 3); }
      else { ctx.fillRect(X, Y + cs / 2 - 3, 3, 6); ctx.fillRect(X + cs - 3, Y + cs / 2 - 3, 3, 6); }
      ctx.strokeStyle = g.on ? COL.alarm : '#c4c9d0'; ctx.lineWidth = g.on ? 2.5 : 1; ctx.setLineDash(g.on ? [] : [3, 3]);
      ctx.beginPath();
      if (g.o === 'v') { ctx.moveTo(X + cs / 2, Y + 2); ctx.lineTo(X + cs / 2, Y + cs - 2); }
      else { ctx.moveTo(X + 2, Y + cs / 2); ctx.lineTo(X + cs - 2, Y + cs / 2); }
      ctx.stroke(); ctx.setLineDash([]);
    }

    // start pad
    ctx.strokeStyle = COL.faint; ctx.lineWidth = 1; ctx.setLineDash([2, 2]);
    ctx.strokeRect(S.start[0] * cs + 3.5, S.start[1] * cs + 3.5, cs - 7, cs - 7); ctx.setLineDash([]);

    // terminal
    {
      const X = S.terminal[0] * cs, Y = S.terminal[1] * cs;
      ctx.fillStyle = COL.violet;
      ctx.globalAlpha = a.hacking ? 0.6 + 0.4 * Math.sin(T * 12) : 1;
      ctx.fillRect(X + cs * 0.18, Y + cs * 0.16, cs * 0.64, cs * 0.46);
      ctx.fillRect(X + cs * 0.42, Y + cs * 0.62, cs * 0.16, cs * 0.12);
      ctx.fillRect(X + cs * 0.28, Y + cs * 0.74, cs * 0.44, cs * 0.08);
      ctx.globalAlpha = 1;
      ctx.fillStyle = '#ffffff'; ctx.fillRect(X + cs * 0.26, Y + cs * 0.24, cs * 0.48, cs * 0.3);
      ctx.fillStyle = COL.violet; ctx.font = `600 ${Math.round(cs * 0.26)}px "IBM Plex Sans", sans-serif`; ctx.textAlign = 'center';
      ctx.fillText(S.code_ok ? 'OK' : '?', X + cs / 2, Y + cs * 0.48); ctx.textAlign = 'left';
    }

    // exit
    {
      const X = S.exit[0] * cs, Y = S.exit[1] * cs, open = S.exit_open, c = open ? COL.ok : COL.alarm;
      ctx.strokeStyle = c; ctx.lineWidth = 2;
      ctx.globalAlpha = open ? 0.75 + 0.25 * Math.sin(T * 4) : 1;
      ctx.strokeRect(X + 3, Y + 3, cs - 6, cs - 6);
      ctx.fillStyle = c; ctx.globalAlpha *= 0.3; ctx.fillRect(X + 3, Y + 3, cs - 6, cs - 6); ctx.globalAlpha = 1;
      if (!open) {
        ctx.beginPath();
        for (let k = 1; k <= 3; k++) { ctx.moveTo(X + 3 + ((cs - 6) * k) / 4, Y + 4); ctx.lineTo(X + 3 + ((cs - 6) * k) / 4, Y + cs - 4); }
        ctx.stroke();
      }
    }

    // keycards
    for (const k of S.keys) {
      if (k.taken) continue;
      ctx.save(); ctx.translate(k.x * cs + cs / 2, k.y * cs + cs / 2); ctx.rotate(-0.25);
      ctx.fillStyle = k.color; ctx.fillRect(-cs * 0.3, -cs * 0.2, cs * 0.6, cs * 0.4);
      ctx.fillStyle = '#ffffff'; ctx.fillRect(-cs * 0.2, -cs * 0.06, cs * 0.22, cs * 0.12);
      ctx.restore();
    }

    // planned route
    if (app.ov.path && S.route.length > 1) {
      const pts = S.route;
      ctx.strokeStyle = a.adaptive ? COL.agent : '#6b7280';
      ctx.globalAlpha = 0.85; ctx.lineWidth = 2; ctx.setLineDash([5, 4]); ctx.lineDashOffset = -T * 18;
      ctx.beginPath();
      pts.forEach(([x, y], k) => { const X = x * cs + cs / 2, Y = y * cs + cs / 2; if (k) ctx.lineTo(X, Y); else ctx.moveTo(X, Y); });
      ctx.stroke(); ctx.setLineDash([]); ctx.globalAlpha = 1;
      // a ring where the plan waits (space-time planning)
      for (let k = 1; k < pts.length; k++) if (pts[k][0] === pts[k - 1][0] && pts[k][1] === pts[k - 1][1]) {
        ctx.strokeStyle = COL.agent; ctx.beginPath(); ctx.arc(pts[k][0] * cs + cs / 2, pts[k][1] * cs + cs / 2, cs * 0.3, 0, 7); ctx.stroke();
      }
    }

    // drone
    if (S.drone) {
      const d = S.drone, c = DRONE_COL[d.state];
      const dx = lerp(d.px, d.x, frac) * cs + cs / 2, dy = lerp(d.py, d.y, frac) * cs + cs / 2;
      if (d.state !== 'COOLDOWN') {
        const r = (d.detect + 0.5) * cs;
        ctx.globalAlpha = 0.06; ctx.fillStyle = c;
        ctx.beginPath(); ctx.moveTo(dx, dy - r); ctx.lineTo(dx + r, dy); ctx.lineTo(dx, dy + r); ctx.lineTo(dx - r, dy); ctx.closePath(); ctx.fill();
        ctx.globalAlpha = 0.4; ctx.strokeStyle = c; ctx.lineWidth = 1; ctx.setLineDash([3, 3]); ctx.stroke(); ctx.setLineDash([]);
        ctx.globalAlpha = 1;
      }
      ctx.fillStyle = c; ctx.beginPath(); ctx.arc(dx, dy, cs * 0.26, 0, 7); ctx.fill();
      ctx.strokeStyle = c; ctx.lineWidth = 1.5;
      const spin = T * 9;
      for (let k = 0; k < 4; k++) {
        const ang = (Math.PI / 2) * k + Math.PI / 4, rx = dx + Math.cos(ang) * cs * 0.36, ry = dy + Math.sin(ang) * cs * 0.36;
        ctx.beginPath(); ctx.moveTo(rx - Math.cos(spin) * cs * 0.1, ry - Math.sin(spin) * cs * 0.1); ctx.lineTo(rx + Math.cos(spin) * cs * 0.1, ry + Math.sin(spin) * cs * 0.1); ctx.stroke();
      }
      ctx.fillStyle = '#ffffff'; ctx.beginPath(); ctx.arc(dx, dy, cs * 0.09, 0, 7); ctx.fill();
    }

    // agent
    {
      const ax = lerp(a.px, a.x, frac) * cs + cs / 2, ay = lerp(a.py, a.y, frac) * cs + cs / 2;
      ctx.fillStyle = COL.agent; ctx.beginPath(); ctx.arc(ax, ay, cs * 0.3, 0, 7); ctx.fill();
      ctx.strokeStyle = a.hull > 50 ? COL.ok : a.hull > 25 ? COL.drone : COL.alarm; ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(ax, ay, cs * 0.42, -Math.PI / 2, -Math.PI / 2 + (Math.PI * 2 * a.hull) / 100); ctx.stroke();
      const vx = a.x - a.px, vy = a.y - a.py, len = Math.hypot(vx, vy) || 1;
      ctx.fillStyle = '#ffffff'; ctx.beginPath(); ctx.arc(ax + (vx / len) * cs * 0.1, ay + (vy / len) * cs * 0.1, cs * 0.11, 0, 7); ctx.fill();
      if (a.evading) { ctx.strokeStyle = COL.drone; ctx.setLineDash([3, 3]); ctx.beginPath(); ctx.arc(ax, ay, cs * 0.55, 0, 7); ctx.stroke(); ctx.setLineDash([]); }
      if (a.stun > 0) {
        ctx.strokeStyle = COL.alert;
        for (let k = 0; k < 3; k++) { const ang = T * 8 + k * 2.1; ctx.beginPath(); ctx.moveTo(ax + Math.cos(ang) * cs * 0.35, ay + Math.sin(ang) * cs * 0.35); ctx.lineTo(ax + Math.cos(ang) * cs * 0.55, ay + Math.sin(ang) * cs * 0.55); ctx.stroke(); }
      }
    }

    // short-lived effects
    app.fx = app.fx.filter((f) => now - f.born < 1100);
    for (const f of app.fx) {
      const age = (now - f.born) / 1100, X = (f.x + 0.5) * cs, Y = (f.y + 0.5) * cs;
      ctx.globalAlpha = 1 - age;
      if (f.type === 'collapse') { ctx.strokeStyle = COL.rubble; ctx.lineWidth = 2; const r = cs * (0.5 + age * 1.6); ctx.strokeRect(X - r, Y - r, 2 * r, 2 * r); }
      else if (f.type === 'hit' || f.type === 'zap') { ctx.strokeStyle = COL.alarm; ctx.lineWidth = 3; ctx.beginPath(); ctx.arc(X, Y, cs * (0.4 + age * 1.5), 0, 7); ctx.stroke(); }
      else if (f.type === 'key') { ctx.strokeStyle = f.color; ctx.lineWidth = 2; ctx.beginPath(); ctx.arc(X, Y, cs * (0.3 + age * 2), 0, 7); ctx.stroke(); }
      else if (f.type === 'replan') { ctx.strokeStyle = COL.agent; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.arc(X, Y, cs * (0.4 + age), 0, 7); ctx.stroke(); }
      else if (f.type === 'surge' || f.type === 'unlock') { ctx.strokeStyle = f.type === 'surge' ? COL.violet : COL.ok; ctx.lineWidth = 8; ctx.strokeRect(4, 4, W * cs - 8, H * cs - 8); }
      ctx.globalAlpha = 1;
    }

    if (app.hover) {
      ctx.strokeStyle = COL.ink; ctx.lineWidth = 1.5; ctx.globalAlpha = 0.6;
      ctx.strokeRect(app.hover.x * cs + 0.5, app.hover.y * cs + 0.5, cs - 1, cs - 1); ctx.globalAlpha = 1;
    }
  }

  /* ---------------- panels ---------------- */
  function refreshPanels() {
    if (!S) return;
    const a = S.agent, st = S.stats;
    $('stTick').innerHTML = `${S.t} <small>/ ${S.max_ticks} ticks</small>`;
    $('stMode').textContent = S.done ? (S.result.success ? 'escaped' : 'mission failed: ' + S.result.reason) : a.mode;
    $('stInteg').style.width = a.hull + '%';
    $('stInteg').style.background = a.hull > 50 ? 'var(--ok)' : a.hull > 25 ? 'var(--drone)' : 'var(--alarm)';
    $('stKeys').innerHTML = 'Keycards ' + S.keys.map((k) => `<span class="kc${k.taken ? ' held' : ''}" title="${k.name}" style="border-color:${k.color};background:${k.taken ? k.color : 'transparent'}"></span>`).join('') +
      ` <span style="margin-left:auto">Hull ${a.hull}%</span>`;
    const m = [[st.moves, 'moves'], [st.path_cost, 'path cost'], [st.expanded.toLocaleString(), 'states explored'], [st.plan_calls, 'plans made'],
      [st.replans, 'replans'], [st.waits, 'waits'], [st.hits, 'drone hits'], [st.zaps, 'laser zaps']];
    $('stMetrics').innerHTML = m.map(([v, l]) => `<div><b>${v}</b><span>${l}</span></div>`).join('');
    updateBT(); updateFuzzy(); updateCSP(); updateFSM(); updateLog(); updateDots();
  }

  // Behaviour tree: nested list built from the (name, depth, status) rows Python sends.
  function updateBT() {
    const host = $('btTree');
    if (!S.tree) {
      host.innerHTML = '<p class="hint">Fixed-script mode has no behaviour tree. The agent follows one route planned at tick 0 and never reconsiders it.</p>';
      return;
    }
    let h = '', depth = -1;
    for (const n of S.tree) {
      if (n.depth > depth) h += '<ul>'.repeat(n.depth - depth);
      else { h += '</li>'; if (n.depth < depth) h += '</ul></li>'.repeat(depth - n.depth); }
      h += `<li><span class="node${n.status ? ' ' + n.status : ''}"><span class="glyph">${n.glyph}</span>${UI.esc(n.name)}</span>`;
      depth = n.depth;
    }
    h += '</li>' + '</ul></li>'.repeat(depth) + '</ul>';
    host.innerHTML = h;
  }

  // Fuzzy logic: membership curves, current reading, fired rules.
  function buildRules() {
    $('fzRules').innerHTML = FZ.rules.map((r, k) => `<div class="rule" id="fzr${k}" title="${UI.esc(r.full)}"><span>${UI.esc(r.short)}</span><div class="str"><div style="width:0"></div></div></div>`).join('');
  }
  function updateFuzzy() {
    if ($('fzCanvas').closest('.ppanel').hidden) return;
    const { ctx: c, w } = UI.setupCanvas($('fzCanvas'), 236);
    const F = S.fuzzy;
    if (!F) {
      c.fillStyle = UI.colors.faint; c.fillText('No drone in the Static facility, so the threat is always zero.', 0, 20);
      $('fzOut').textContent = 'threat 0';
      return;
    }
    $('fzOut').textContent = `threat ${F.value.toFixed(0)} / 100${F.evading ? ', evading' : ''}`;
    const setCols = ['#dc2626', '#ea580c', '#ca8a04', '#2563eb', '#15803d'];
    const rows = [['distance', ['#dc2626', '#ea580c', '#15803d']], ['alert', ['#15803d', '#dc2626']], ['integrity', ['#dc2626', '#15803d']]];
    const rh = 56, L = 0, R = w - 4;
    rows.forEach(([name, cols], k) => {
      const v = FZ.inputs[name], top = k * rh + 14, bot = top + 30, [lo, hi] = v.range;
      const X = (x) => L + ((R - L) * (x - lo)) / (hi - lo);
      c.fillStyle = UI.colors.text; c.font = '11px "IBM Plex Sans", sans-serif';
      c.fillText(v.label, 0, top - 3);
      const names = Object.keys(v.sets);
      names.forEach((sn, j) => {
        const ys = v.sets[sn];
        c.strokeStyle = cols[j]; c.lineWidth = 1.4; c.beginPath();
        ys.forEach((m, p) => { const x = X(lo + ((hi - lo) * p) / (ys.length - 1)), y = bot - m * 28; if (p) c.lineTo(x, y); else c.moveTo(x, y); });
        c.stroke();
        c.fillStyle = cols[j]; c.textAlign = 'right';
        c.fillText(`${sn} ${F.mu[name][sn].toFixed(2)}`, R - (names.length - 1 - j) * 82, top - 3);
        c.textAlign = 'left';
      });
      const xv = X(F.values[name]);
      c.strokeStyle = UI.colors.chalk; c.setLineDash([3, 2]); c.beginPath(); c.moveTo(xv, top); c.lineTo(xv, bot + 2); c.stroke(); c.setLineDash([]);
      c.strokeStyle = UI.colors.rule; c.beginPath(); c.moveTo(L, bot + 0.5); c.lineTo(R, bot + 0.5); c.stroke();
    });
    const top = 3 * rh + 14, bot = top + 44, X = (x) => L + ((R - L) * x) / 100;
    c.fillStyle = UI.colors.text; c.fillText('Threat level: clipped rule outputs, combined, centre of mass', 0, top - 3);
    Object.keys(FZ.output.sets).forEach((sn, j) => {
      const ys = FZ.output.sets[sn];
      c.strokeStyle = setCols[4 - j] || '#888'; c.globalAlpha = 0.5; c.lineWidth = 1; c.beginPath();
      ys.forEach((m, p) => { const y = bot - m * 40; if (p) c.lineTo(X(p), y); else c.moveTo(X(p), y); });
      c.stroke(); c.globalAlpha = 1;
    });
    c.fillStyle = 'rgba(234,88,12,0.22)'; c.beginPath(); c.moveTo(X(0), bot);
    F.agg.forEach((m, p) => c.lineTo(X(p), bot - m * 40));
    c.lineTo(X(100), bot); c.closePath(); c.fill();
    c.strokeStyle = UI.colors.chalk; c.lineWidth = 2; c.beginPath(); c.moveTo(X(F.value), top); c.lineTo(X(F.value), bot + 2); c.stroke();
    if (S.config.fuzzy) {
      c.strokeStyle = '#dc2626'; c.lineWidth = 1; c.setLineDash([2, 3]); c.beginPath(); c.moveTo(X(F.threshold), top); c.lineTo(X(F.threshold), bot); c.stroke(); c.setLineDash([]);
      c.fillStyle = '#dc2626'; c.fillText('evade', X(F.threshold) + 3, top + 10);
    }
    c.strokeStyle = UI.colors.rule; c.beginPath(); c.moveTo(L, bot + 0.5); c.lineTo(R, bot + 0.5); c.stroke();
    F.fired.forEach((st, k) => {
      const el = $('fzr' + k);
      if (!el) return;
      el.className = 'rule' + (st > 0 ? ' fired' : '');
      el.querySelector('.str div').style.width = (st * 100).toFixed(0) + '%';
    });
  }

  // Lock (CSP)
  function updateCSP() {
    const L = S.lock, cls = L.state === 'solved' ? 'solved' : L.state === 'solving' ? 'set' : '';
    $('cspDials').innerHTML = L.dials.map((v, i) => `<div class="dial ${v === null ? '' : cls}">${v === null ? '–' : v}<small>D${i + 1}</small></div>`).join('');
    $('cspClues').innerHTML = L.clues.map((c) => `<li class="${c.status}${c.new ? ' new' : ''}"><b>${c.status === 'bad' ? '✗' : c.status === 'ok' ? '✓' : '·'}</b>${UI.esc(c.text)}</li>`).join('');
    $('cspVer').textContent = `clue set v${L.version}${L.fresh ? ', new clues in purple' : ''}`;
    $('cspStats').textContent = L.info;
  }

  // Drone state machine diagram
  const FSM_POS = { PATROL: [62, 75], ALERT: [180, 28], CHASE: [298, 75], COOLDOWN: [180, 124] };
  const FSM_EDGES = [['PATROL', 'ALERT', 'spots agent'], ['ALERT', 'CHASE', 'confirmed'], ['ALERT', 'PATROL', ''], ['CHASE', 'COOLDOWN', 'lost / battery'], ['COOLDOWN', 'PATROL', 'recharged']];
  function buildFSM() {
    let h = '<defs><marker id="fa" markerWidth="7" markerHeight="7" refX="6" refY="3.5" orient="auto"><path d="M0,0 L7,3.5 L0,7 z" fill="#9aa3ae"/></marker></defs>';
    for (const [a, b, lab] of FSM_EDGES) {
      const [x1, y1] = FSM_POS[a], [x2, y2] = FSM_POS[b];
      const dx = x2 - x1, dy = y2 - y1, Ln = Math.hypot(dx, dy);
      const off = a === 'ALERT' && b === 'PATROL' ? 10 : a === 'PATROL' && b === 'ALERT' ? -10 : 0;
      const nx = (-dy / Ln) * off, ny = (dx / Ln) * off;
      const sx = x1 + (dx / Ln) * 46 + nx, sy = y1 + (dy / Ln) * 20 + ny, ex = x2 - (dx / Ln) * 46 + nx, ey = y2 - (dy / Ln) * 20 + ny;
      h += `<line x1="${sx}" y1="${sy}" x2="${ex}" y2="${ey}" stroke="#9aa3ae" stroke-width="1.2" marker-end="url(#fa)"/>`;
      if (lab) h += `<text x="${(sx + ex) / 2 + (dy > 0 ? 6 : -6) * (dx > 0 ? 1 : -1)}" y="${(sy + ey) / 2 - 4}" font-size="10" fill="#7b8591" text-anchor="middle" font-family="IBM Plex Sans, sans-serif">${lab}</text>`;
    }
    for (const st in FSM_POS) {
      const [x, y] = FSM_POS[st];
      h += `<g id="fsm-${st}"><rect x="${x - 46}" y="${y - 15}" width="92" height="30" rx="15" fill="#ffffff" stroke="#d1d5db"/><text x="${x}" y="${y + 4}" font-size="12" text-anchor="middle" fill="#4b5563" font-family="IBM Plex Sans, sans-serif" font-weight="600">${st.charAt(0) + st.slice(1).toLowerCase()}</text></g>`;
    }
    $('fsmSvg').innerHTML = h;
  }
  function updateFSM() {
    const d = S.drone;
    for (const st in FSM_POS) {
      const g = $('fsm-' + st);
      if (!g) continue;
      const on = d && d.state === st;
      g.querySelector('rect').setAttribute('fill', on ? DRONE_COL[st] : '#ffffff');
      g.querySelector('rect').setAttribute('stroke', on ? DRONE_COL[st] : '#d1d5db');
      g.querySelector('text').setAttribute('fill', on ? '#ffffff' : '#4b5563');
    }
    $('fsmInfo').textContent = d ? `${d.transitions} transitions, alertness ${d.alert}` : 'no drone (Static)';
  }

  function updateLog() {
    const Lg = S.logs, last = Lg[Lg.length - 1];
    const sig = Lg.length + ':' + (last ? last[0] + last[2] : '');
    if (sig === app.logSig) return;
    app.logSig = sig;
    $('log').innerHTML = Lg.slice().reverse().map(([t, cat, msg]) => `<li><span class="t">${t}</span><span class="c c-${cat}">${cat}</span><span>${UI.esc(msg)}</span></li>`).join('');
  }

  function showBanner() {
    const r = S.result, b = $('banner');
    const why = { destroyed: 'Hull integrity reached zero.', timeout: `Ran out of time after ${S.max_ticks} ticks.` };
    b.className = 'banner ' + (r.success ? 'win' : 'lose');
    b.innerHTML = (r.success
      ? `<h2>Escaped</h2><p>${r.ticks} ticks, path cost ${r.path_cost}, ${r.replans} replans, ${r.expanded.toLocaleString()} states explored</p>`
      : `<h2>Mission failed</h2><p>${why[r.reason] || r.reason}${!S.config.adaptive ? ' The fixed script cannot adapt to a changing facility.' : ''}</p>`) +
      '<div class="btnrow" style="justify-content:center"><button class="btn primary" data-act="again">Run again</button><button class="btn" data-act="new">New facility</button></div>';
    b.hidden = false;
  }
  $('banner').addEventListener('click', (e) => {
    const act = e.target.dataset.act;
    if (act === 'again') { newSim(); setRunning(true); }
    if (act === 'new') { $('seed').value = 1 + Math.floor(Math.random() * 99999); newSim(); setRunning(true); }
  });

  /* ---------------- loop ---------------- */
  function advance(n) {
    // Scenario events must fire on an exact tick, so step up to it first.
    const sc = scenario;
    if (sc && !sc.fired && sc.at != null && S.t < sc.at && S.t + n >= sc.at) n = sc.at - S.t;
    take(py('step', n));
    scenarioTick();
    refreshPanels();
    if (S.done) { setRunning(false); showBanner(); }
    return n;
  }
  function frame(ts) {
    const dt = Math.min(0.1, (ts - app.last) / 1000 || 0);
    app.last = ts;
    if (py && app.running && !S.done) {
      app.acc += dt * app.speed;
      const n = Math.min(30, Math.floor(app.acc));
      if (n > 0) app.acc -= advance(n);
    }
    draw(app.running ? Math.min(1, app.acc) : 1);
    requestAnimationFrame(frame);
  }

  /* ---------------- input ---------------- */
  const ready = () => !!py && !!S;
  $('btnRun').onclick = () => { if (ready()) setRunning(!app.running); };
  $('btnStep').onclick = () => { if (ready()) { setRunning(false); if (!S.done) advance(1); } };
  $('btnReset').onclick = () => { if (ready()) { const r = app.running; newSim(); setRunning(r); } };
  $('btnNew').onclick = () => { if (ready()) { $('seed').value = 1 + Math.floor(Math.random() * 99999); newSim(); setRunning(true); } };
  $('speed').oninput = (e) => { app.speed = +e.target.value; $('speedOut').textContent = e.target.value; };
  $('seed').onchange = () => newSim();
  for (const id of ['cfgAlgo', 'cfgCsp', 'cfgDyn', 'cfgFuzzy', 'cfgTime', 'cfgAdaptive']) $(id).onchange = () => { if (ready()) { const r = app.running; newSim(); setRunning(r); } };
  $('ovExplored').onchange = (e) => { app.ov.explored = e.target.checked; };
  $('ovRisk').onchange = (e) => { app.ov.risk = e.target.checked; };
  $('ovPath').onchange = (e) => { app.ov.path = e.target.checked; };
  document.querySelectorAll('input[name=tool]').forEach((r) => { r.onchange = () => { app.tool = r.value; }; });
  $('evCollapse').onclick = () => { if (ready() && !S.done) { take(py('collapse')); refreshPanels(); } };
  $('evSurge').onclick = () => { if (ready() && !S.done) { take(py('surge')); refreshPanels(); } };
  $('evAlarm').onclick = () => { if (ready() && !S.done) { take(py('alarm', false)); refreshPanels(); } };

  function cellAt(e) {
    const r = canvas.getBoundingClientRect();
    const x = Math.floor((e.clientX - r.left) / app.cs), y = Math.floor((e.clientY - r.top) / app.cs);
    return S && x >= 0 && y >= 0 && x < S.W && y < S.H ? { x, y } : null;
  }
  canvas.addEventListener('mousemove', (e) => {
    const c = cellAt(e); app.hover = c;
    const tip = $('tip');
    if (!c) { tip.hidden = true; return; }
    const i = c.y * S.W + c.x, t = S.tiles[i];
    const gate = S.gates.some((g) => g.x === c.x && g.y === c.y);
    const kind = t === WALL ? 'wall' : t === RUBBLE ? 'rubble' : gate ? 'laser gate' : S.hazard[i] ? 'floor with coolant' : 'floor';
    let html = `<b>(${c.x}, ${c.y})</b> ${kind}`;
    if (t === 0) {
      html += `<br>step cost ${S.hazard[i] ? 6 : 1}`;
      if (S.risk) html += `, drone ${S.drone_dist[i]} cells away, threat ${S.risk[i]}`;
    }
    tip.innerHTML = html; tip.hidden = false;
    const sr = $('stage').getBoundingClientRect();
    let left = e.clientX - sr.left + 14, top = e.clientY - sr.top + 14;
    if (left + tip.offsetWidth > sr.width) left = e.clientX - sr.left - tip.offsetWidth - 10;
    if (top + tip.offsetHeight > sr.height) top = e.clientY - sr.top - tip.offsetHeight - 10;
    tip.style.left = left + 'px'; tip.style.top = top + 'px';
  });
  canvas.addEventListener('mouseleave', () => { app.hover = null; $('tip').hidden = true; });
  canvas.addEventListener('click', (e) => {
    const c = cellAt(e);
    if (!c || !ready() || S.done) return;
    const kind = { rubble: 'rubble', hazard: 'hazard', drone: 'drone' }[app.tool];
    if (!kind) return;
    take(py('tool', kind, c.x, c.y));
    refreshPanels();
  });
  document.addEventListener('keydown', (e) => {
    if (!ready() || /INPUT|SELECT|TEXTAREA|BUTTON|SUMMARY/.test(document.activeElement.tagName)) return;
    if (e.key === ' ') { e.preventDefault(); setRunning(!app.running); }
    else if (e.key === 's') { setRunning(false); if (!S.done) advance(1); }
    else if (e.key === 'r') newSim();
  });

  /* ---------------- instrument tabs ---------------- */
  function showPanel(p) {
    document.querySelectorAll('.ptabs button').forEach((b) => b.setAttribute('aria-selected', String(b.dataset.p === p)));
    document.querySelectorAll('.ppanel').forEach((s) => { s.hidden = s.dataset.p !== p; });
    refreshPanels();
  }
  document.querySelectorAll('.ptabs button').forEach((b) => { b.onclick = () => showPanel(b.dataset.p); });
  function updateDots() {
    const a = S.agent;
    const live = { csp: a.hacking, fz: a.evading, fsm: !!(S.drone && S.drone.state === 'CHASE') };
    document.querySelectorAll('.ptabs button').forEach((b) => {
      let dot = b.querySelector('.dot');
      const on = live[b.dataset.p] && b.getAttribute('aria-selected') !== 'true';
      if (on && !dot) { dot = document.createElement('span'); dot.className = 'dot'; b.appendChild(dot); }
      if (!on && dot) dot.remove();
    });
  }

  /* ---------------- guided scenarios ---------------- */
  const SCENARIOS = [
    { id: 'escape', title: 'Watch a full escape', tag: 'All techniques together', cfg: { seed: 5007, dyn: 'normal' }, panel: 'bt',
      desc: 'The complete agent on a Dynamic facility: keycards, lock, exit, with the drone and gates active.',
      note: 'Watch the <b>Decisions</b> tab. The blue node is what UNIT-7 is doing right now. It moves from "Collect keycards" to "Crack the lock" to "Escape" as the mission progresses.' },
    { id: 'block', title: 'Block the planned route', tag: 'A* replanning', cfg: { seed: 5007, dyn: 'off' }, at: 25, action: 'collapse', panel: 'log',
      desc: 'At tick 25 the ceiling collapses directly on the route the agent is following.',
      note: 'At tick 25 rubble lands on the dashed route. Within the same tick the route snaps to a detour, and the <b>Log</b> shows "Replan (route blocked)". Dynamics are off so nothing else interferes.' },
    { id: 'surge', title: 'Change the lock after it is cracked', tag: 'Constraint satisfaction + behaviour tree', cfg: { seed: 5007, dyn: 'off' }, onCrack: 'surge', panel: 'csp',
      desc: 'As soon as the agent cracks the code, a power surge rewires the lock and changes the clues.',
      note: 'Watch the <b>Lock</b> tab. Once the code is found, a surge changes the clues (new ones in purple). "Vault unlocked?" fails, the tree falls back to "Crack the lock", and the solver runs again on the new constraints.' },
    { id: 'script', title: 'A fixed plan in a changing world', tag: 'Why adapting matters', cfg: { seed: 5007, dyn: 'normal', adaptive: false, fuzzy: false, time: false }, panel: 'log',
      desc: 'The same facility, but the agent follows a script planned once at the start and never updates it.',
      note: 'The grey dashed line is a script planned at tick 0. When a collapse blocks it, the agent just waits in front of the rubble until time runs out. Compare with "Watch a full escape", which uses the same seed.' },
    { id: 'gates', title: 'Laser gates without timing', tag: 'Space-time planning', cfg: { seed: 5033, dyn: 'normal', time: false }, panel: 'log',
      desc: 'Space-time planning off: the agent treats each gate as frozen in its current state.',
      note: 'Keep an eye on <b>laser zaps</b> in Status, and on "Replan (laser gate)" in the Log. Then tick <b>Space-time planning</b> back on: the agent plans around the gate timetable and waits for gates to switch off.' },
    { id: 'alarm', title: 'Escape a hunting drone', tag: 'Fuzzy logic + state machine', cfg: { seed: 5007, dyn: 'normal' }, at: 15, action: 'alarm', panel: 'fz',
      desc: 'At tick 15 the alarm sounds and the drone switches straight to Chase.',
      note: 'In the <b>Threat</b> tab the drone becomes "Alert" and the threat score jumps past the red evade line. The behaviour tree switches to "Evade drone" until the drone\'s battery runs out.' },
    { id: 'csp', title: 'Crack the lock the slow way', tag: 'CSP heuristics', cfg: { seed: 5007, dyn: 'off', csp: 'bt' }, panel: 'csp',
      desc: 'The lock solver is set to plain backtracking, with no forward checking, MRV or AC-3.',
      note: 'Dialling in the code takes one tick per four solver assignments. Plain backtracking makes UNIT-7 stand at the terminal much longer; switch the lock solver back to "MRV + FC + AC-3" to compare.' },
    { id: 'chaos', title: 'Chaos mode', tag: 'Stress test', cfg: { seed: 5011, dyn: 'chaos' }, panel: 'log',
      desc: 'Six collapses, two power surges, a faster coolant leak and a sharper-eyed drone.',
      note: 'Everything at once. The Log shows each disruption and how the agent responded to it.' },
  ];
  let scenario = null;
  function scenarioTick() {
    const sc = scenario;
    if (!sc || sc.fired) return;
    if (sc.at != null && S.t === sc.at) fire(sc);
    else if (sc.onCrack && S.code_ok) fire(sc);
  }
  function fire(sc) {
    sc.fired = true;
    const act = sc.action || sc.onCrack;
    if (act === 'collapse') take(py('collapse'));
    if (act === 'surge') take(py('surge'));
    if (act === 'alarm') take(py('alarm', true));
  }
  function applyCfg(c) {
    $('seed').value = c.seed || 5007;
    $('cfgDyn').value = c.dyn || 'normal';
    $('cfgAlgo').value = c.algo || 'astar';
    $('cfgCsp').value = c.csp || 'mrv_fc_ac3';
    $('cfgFuzzy').checked = c.fuzzy !== false;
    $('cfgTime').checked = c.time !== false;
    $('cfgAdaptive').checked = c.adaptive !== false;
  }
  function startScenario(id, scroll) {
    const def = SCENARIOS.find((x) => x.id === id);
    if (!def) return;
    scenario = Object.assign({}, def, { fired: false });
    applyCfg(def.cfg);
    const note = $('scenarioNote');
    note.innerHTML = `<b>${def.title}.</b> ${def.note}`;
    note.hidden = false;
    document.querySelectorAll('.scenario').forEach((el) => el.classList.toggle('active', el.dataset.id === id));
    if (scroll) note.scrollIntoView({ behavior: 'smooth', block: 'start' });
    if (!py) return; // started once Python is ready
    newSim();
    showPanel(def.panel);
    setRunning(true);
  }
  $('scenarios').innerHTML = SCENARIOS.map((s) =>
    `<div class="scenario" data-id="${s.id}"><span class="tag">${s.tag}</span><h3>${s.title}</h3><p>${s.desc}</p><button class="btn" data-id="${s.id}">Run this scenario</button></div>`).join('');
  $('scenarios').addEventListener('click', (e) => { if (e.target.dataset.id && e.target.tagName === 'BUTTON') startScenario(e.target.dataset.id, true); });
  for (const id of ['cfgAlgo', 'cfgCsp', 'cfgDyn', 'cfgFuzzy', 'cfgTime', 'cfgAdaptive', 'seed']) $(id).addEventListener('change', () => { if (scenario) scenario.fired = true; });

  /* ---------------- start: URL parameters let other pages link to exact setups ---------------- */
  const q = new URLSearchParams(location.search);
  if (q.get('scenario')) startScenario(q.get('scenario'), false);
  else applyCfg({
    seed: +q.get('seed') || 5007, dyn: q.get('dyn') || 'normal', algo: q.get('algo') || 'astar', csp: q.get('csp') || 'mrv_fc_ac3',
    fuzzy: q.get('fuzzy') !== '0', time: q.get('time') !== '0', adaptive: q.get('adaptive') !== '0',
  });
  requestAnimationFrame(frame);
  PY.boot($('pyload')).then((p) => {
    py = p;
    newSim();
    if (scenario) showPanel(scenario.panel);
    setRunning(q.get('autoplay') !== '0');
  }).catch(() => {});
})();
