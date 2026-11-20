/* Home page: a small live run of the Python simulation that loops through a few facilities. */
(function () {
  'use strict';
  const cv = document.getElementById('heroCanvas');
  if (!cv) return;
  const ctx = cv.getContext('2d');
  const info = document.getElementById('heroInfo');
  const SEEDS = [5007, 5011, 5003, 5020];
  const CS = 20, WALL = 1, RUBBLE = 2;
  let py = null, S = null, k = 0, last = 0, acc = 0, pause = 0;
  const reduced = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  function start() {
    S = py('new_sim', JSON.stringify({ seed: SEEDS[k++ % SEEDS.length], dynamics: 'normal' }));
    const dpr = window.devicePixelRatio || 1;
    cv.width = S.W * CS * dpr; cv.height = S.H * CS * dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  function draw() {
    const W = S.W, cs = CS, a = S.agent;
    for (let y = 0; y < S.H; y++) for (let x = 0; x < W; x++) {
      const i = y * W + x, t = S.tiles[i];
      ctx.fillStyle = t === WALL ? '#2f3b48' : t === RUBBLE ? '#b08559' : '#ffffff';
      ctx.fillRect(x * cs, y * cs, cs, cs);
      if (t === 0) {
        ctx.strokeStyle = '#eef0f3'; ctx.strokeRect(x * cs + 0.5, y * cs + 0.5, cs - 1, cs - 1);
        if (S.hazard[i]) { ctx.fillStyle = 'rgba(20,184,166,0.22)'; ctx.fillRect(x * cs, y * cs, cs, cs); }
        if (S.risk && S.risk[i] > 24) { ctx.fillStyle = `rgba(220,38,38,${((S.risk[i] - 24) / 76) * 0.25})`; ctx.fillRect(x * cs, y * cs, cs, cs); }
      }
    }
    for (const g of S.gates) {
      ctx.strokeStyle = g.on ? '#dc2626' : '#c4c9d0'; ctx.lineWidth = g.on ? 2.5 : 1;
      ctx.beginPath();
      if (g.o === 'v') { ctx.moveTo(g.x * cs + cs / 2, g.y * cs + 2); ctx.lineTo(g.x * cs + cs / 2, g.y * cs + cs - 2); }
      else { ctx.moveTo(g.x * cs + 2, g.y * cs + cs / 2); ctx.lineTo(g.x * cs + cs - 2, g.y * cs + cs / 2); }
      ctx.stroke();
    }
    ctx.lineWidth = 1;
    ctx.fillStyle = '#7c3aed'; ctx.fillRect(S.terminal[0] * cs + 4, S.terminal[1] * cs + 4, cs - 8, cs - 9);
    ctx.strokeStyle = S.exit_open ? '#15803d' : '#dc2626'; ctx.lineWidth = 2;
    ctx.strokeRect(S.exit[0] * cs + 3, S.exit[1] * cs + 3, cs - 6, cs - 6); ctx.lineWidth = 1;
    for (const key of S.keys) if (!key.taken) { ctx.fillStyle = key.color; ctx.fillRect(key.x * cs + 4, key.y * cs + 6, cs - 8, cs - 12); }
    if (S.route.length > 1) {
      ctx.strokeStyle = '#2563eb'; ctx.setLineDash([4, 3]); ctx.lineWidth = 1.5; ctx.beginPath();
      S.route.forEach(([x, y], j) => { const X = x * cs + cs / 2, Y = y * cs + cs / 2; if (j) ctx.lineTo(X, Y); else ctx.moveTo(X, Y); });
      ctx.stroke(); ctx.setLineDash([]); ctx.lineWidth = 1;
    }
    if (S.drone) { ctx.fillStyle = '#ea580c'; ctx.beginPath(); ctx.arc(S.drone.x * cs + cs / 2, S.drone.y * cs + cs / 2, cs * 0.3, 0, 7); ctx.fill(); }
    ctx.fillStyle = '#2563eb'; ctx.beginPath(); ctx.arc(a.x * cs + cs / 2, a.y * cs + cs / 2, cs * 0.34, 0, 7); ctx.fill();
    ctx.fillStyle = '#fff'; ctx.beginPath(); ctx.arc(a.x * cs + cs / 2, a.y * cs + cs / 2, cs * 0.12, 0, 7); ctx.fill();
    const status = S.done ? (S.result.success ? 'escaped' : 'failed') : a.mode;
    info.innerHTML = `seed ${S.config.seed} · tick <b>${S.t}</b> · ${status}`;
  }

  function frame(ts) {
    const dt = Math.min(0.1, (ts - last) / 1000 || 0); last = ts;
    if (S.done) { pause += dt; if (pause > 2.5) { pause = 0; start(); } }
    else {
      acc += dt * 12;
      const n = Math.floor(acc);
      if (n > 0) { acc -= n; S = py('step', n); }
    }
    draw();
    if (!reduced) requestAnimationFrame(frame);
  }

  PY.boot(document.getElementById('pyload')).then((p) => {
    py = p;
    start();
    if (reduced) { S = py('step', 60); draw(); } else requestAnimationFrame(frame);
  }).catch(() => {});
})();
