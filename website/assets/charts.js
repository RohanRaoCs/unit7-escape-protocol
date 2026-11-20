/* Tiny canvas chart helpers (no dependencies, so the app runs offline from file://). */
(function (G) {
  'use strict';
  const UI = (G.UI = G.UI || {});
  const C = {
    text: '#4b5563', faint: '#9aa3ae', rule: '#eceef1', chalk: '#1f2933',
  };
  UI.colors = C;

  function setup(canvas, h) {
    const dpr = window.devicePixelRatio || 1;
    const w = canvas.clientWidth || canvas.parentElement.clientWidth || 400;
    canvas.style.height = h + 'px';
    canvas.width = Math.round(w * dpr);
    canvas.height = Math.round(h * dpr);
    const ctx = canvas.getContext('2d');
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    ctx.font = '12px "IBM Plex Sans", system-ui, sans-serif';
    return { ctx, w, h };
  }
  UI.setupCanvas = setup;

  const niceMax = (v) => {
    if (!(v > 0)) return 1;
    const p = Math.pow(10, Math.floor(Math.log10(v)));
    for (const m of [1, 2, 2.5, 5, 10]) if (m * p >= v) return m * p;
    return 10 * p;
  };

  /* Horizontal bars with optional ±std whiskers. opts: {title, labels, values, errors, colors, fmt, max} */
  UI.barChart = function (canvas, o) {
    const rowH = 26, top = 30, labelW = Math.min(230, (canvas.clientWidth || 400) * 0.45);
    const h = top + o.labels.length * rowH + 24;
    const { ctx, w } = setup(canvas, h);
    ctx.fillStyle = C.chalk; ctx.font = '600 13px "IBM Plex Sans", system-ui, sans-serif';
    ctx.fillText(o.title, 0, 16);
    ctx.font = '12px "IBM Plex Sans", system-ui, sans-serif';
    const x0 = labelW + 8, x1 = w - 56;
    const vmax = o.max || niceMax(Math.max(...o.values.map((v, i) => v + ((o.errors && o.errors[i]) || 0))));
    const X = (v) => x0 + ((x1 - x0) * Math.max(0, v)) / vmax;
    // grid
    ctx.strokeStyle = C.rule; ctx.lineWidth = 1;
    for (let k = 0; k <= 4; k++) {
      const gx = Math.round(x0 + ((x1 - x0) * k) / 4) + 0.5;
      ctx.beginPath(); ctx.moveTo(gx, top - 6); ctx.lineTo(gx, top + o.labels.length * rowH); ctx.stroke();
      ctx.fillStyle = C.faint; ctx.textAlign = 'center';
      ctx.fillText(o.fmt ? o.fmt((vmax * k) / 4, true) : String(+((vmax * k) / 4).toFixed(1)), gx, top + o.labels.length * rowH + 15);
    }
    o.labels.forEach((lab, i) => {
      const y = top + i * rowH;
      ctx.textAlign = 'right'; ctx.fillStyle = C.text;
      let s = lab;
      while (ctx.measureText(s).width > labelW && s.length > 4) s = s.slice(0, -2);
      if (s !== lab) s = s.trimEnd() + '…';
      ctx.fillText(s, labelW, y + rowH / 2 + 4);
      const v = o.values[i];
      const col = Array.isArray(o.colors) ? o.colors[i % o.colors.length] : o.colors || '#2563eb';
      ctx.fillStyle = col;
      ctx.fillRect(x0, y + 5, Math.max(1, X(v) - x0), rowH - 10);
      if (o.errors && o.errors[i] > 0) {
        ctx.strokeStyle = C.chalk; ctx.globalAlpha = 0.5;
        const a = X(v - o.errors[i]), b = X(v + o.errors[i]), cy = y + rowH / 2;
        ctx.beginPath(); ctx.moveTo(a, cy); ctx.lineTo(b, cy); ctx.moveTo(a, cy - 4); ctx.lineTo(a, cy + 4); ctx.moveTo(b, cy - 4); ctx.lineTo(b, cy + 4); ctx.stroke();
        ctx.globalAlpha = 1;
      }
      ctx.textAlign = 'left'; ctx.fillStyle = C.chalk;
      ctx.fillText(o.fmt ? o.fmt(v) : String(+v.toFixed(1)), Math.min(X(v), x1) + 6, y + rowH / 2 + 4);
    });
    ctx.textAlign = 'left';
  };

  /* Line chart. opts: {title, series:[{data:[y], color, label}], ylabel, xlabel, h, ymax, ymin} */
  UI.lineChart = function (canvas, o) {
    const H = o.h || 220;
    const { ctx, w, h } = setup(canvas, H);
    const L = 46, R = 12, T = 28, B = 30;
    ctx.fillStyle = C.chalk; ctx.font = '600 13px "IBM Plex Sans", system-ui, sans-serif';
    ctx.fillText(o.title, 0, 16);
    ctx.font = '12px "IBM Plex Sans", system-ui, sans-serif';
    const n = Math.max(1, ...o.series.map((s) => s.data.length));
    let ymax = o.ymax != null ? o.ymax : niceMax(Math.max(1, ...o.series.flatMap((s) => s.data.filter(Number.isFinite))));
    const ymin = o.ymin || 0;
    const X = (i) => L + ((w - L - R) * i) / Math.max(1, n - 1);
    const Y = (v) => T + (h - T - B) * (1 - (v - ymin) / (ymax - ymin));
    ctx.strokeStyle = C.rule; ctx.fillStyle = C.faint; ctx.textAlign = 'right';
    for (let k = 0; k <= 4; k++) {
      const v = ymin + ((ymax - ymin) * k) / 4, y = Math.round(Y(v)) + 0.5;
      ctx.beginPath(); ctx.moveTo(L, y); ctx.lineTo(w - R, y); ctx.stroke();
      ctx.fillText(o.yfmt ? o.yfmt(v) : String(+v.toFixed(1)), L - 6, y + 4);
    }
    ctx.textAlign = 'center';
    if (o.xlabel) ctx.fillText(o.xlabel, (L + w - R) / 2, h - 6);
    ctx.textAlign = 'left';
    for (const s of o.series) {
      if (!s.data.length) continue;
      ctx.strokeStyle = s.color; ctx.lineWidth = s.width || 1.6; ctx.globalAlpha = s.alpha || 1;
      ctx.beginPath();
      s.data.forEach((v, i) => { const y = Y(Math.min(ymax, v)); if (i) ctx.lineTo(X(i), y); else ctx.moveTo(X(i), y); });
      ctx.stroke();
      ctx.globalAlpha = 1; ctx.lineWidth = 1;
    }
    // legend
    let lx = w - R;
    ctx.textAlign = 'right';
    for (const s of o.series.slice().reverse()) {
      if (!s.label) continue;
      ctx.fillStyle = C.text; ctx.fillText(s.label, lx, 16);
      lx -= ctx.measureText(s.label).width + 6;
      ctx.fillStyle = s.color; ctx.fillRect(lx - 12, 10, 12, 3);
      lx -= 24;
    }
    ctx.textAlign = 'left';
    if (o.marks) for (const m of o.marks) {
      const x = X(m.i);
      ctx.strokeStyle = m.color; ctx.setLineDash([4, 3]);
      ctx.beginPath(); ctx.moveTo(x, T); ctx.lineTo(x, h - B); ctx.stroke(); ctx.setLineDash([]);
      ctx.fillStyle = m.color; ctx.fillText(m.label, Math.min(x + 4, w - 120), T + 12);
    }
  };

  UI.download = function (name, text, type) {
    const blob = new Blob([text], { type: type || 'text/csv' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = name;
    document.body.appendChild(a); a.click(); a.remove();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  };
  UI.esc = (s) => String(s).replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
})(window);
