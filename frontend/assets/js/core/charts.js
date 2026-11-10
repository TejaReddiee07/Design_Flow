/* Lightweight canvas charts, theme-aware (reads CSS tokens), with hover tooltips.
   Forms: lineChart, barChart, donutChart, sparkline. One axis per chart by design. */

function cssVar(name, fallback) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  return v || fallback;
}

export function palette() {
  return [1, 2, 3, 4, 5, 6].map((i) => cssVar(`--chart-${i}`, "#6366f1"));
}

function theme() {
  return {
    grid: cssVar("--chart-grid", "#e4e6ef"),
    text: cssVar("--chart-text", "#6b7085"),
    textStrong: cssVar("--text", "#0f1220"),
    surface: cssVar("--surface", "#fff"),
    border: cssVar("--border", "#e4e6ef"),
    font: cssVar("--font-sans", "Inter, system-ui, sans-serif"),
  };
}

// The whole UI scales with the root font size on large (4K) screens; charts draw in the same
// design units so labels, padding and strokes scale with everything else.
function uiScale() {
  return (parseFloat(getComputedStyle(document.documentElement).fontSize) || 16) / 16;
}

function setupCanvas(canvas) {
  const dpr = window.devicePixelRatio || 1;
  const k = uiScale();
  const rect = canvas.getBoundingClientRect();
  const w = Math.max(10, rect.width || canvas.clientWidth || 300);
  const h = Math.max(10, rect.height || canvas.clientHeight || 160);
  canvas.width = Math.round(w * dpr);
  canvas.height = Math.round(h * dpr);
  const ctx = canvas.getContext("2d");
  ctx.setTransform(dpr * k, 0, 0, dpr * k, 0, 0);
  return { ctx, w: w / k, h: h / k };
}

function niceTicks(max, count = 4) {
  if (max <= 0) return [0, 1];
  const raw = max / count;
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const norm = raw / mag;
  const step = (norm <= 1 ? 1 : norm <= 2 ? 2 : norm <= 5 ? 5 : 10) * mag;
  const ticks = [];
  for (let v = 0; v <= max + step * 0.999; v += step) ticks.push(v);
  return ticks;
}

function ensureTooltip(canvas) {
  let tip = canvas.parentElement.querySelector(".chart-tip");
  if (!tip) {
    tip = document.createElement("div");
    tip.className = "chart-tip";
    tip.style.cssText =
      "position:absolute;pointer-events:none;z-index:5;padding:0.5rem 0.625rem;border-radius:0.5rem;font-size:0.75rem;" +
      "background:var(--text);color:var(--bg);box-shadow:var(--shadow-md);opacity:0;transition:opacity .12s;white-space:nowrap;";
    const parent = canvas.parentElement;
    if (getComputedStyle(parent).position === "static") parent.style.position = "relative";
    parent.appendChild(tip);
  }
  return tip;
}

function showTip(tip, canvas, x, y, html) {
  const k = uiScale();
  x *= k;
  y *= k;
  tip.innerHTML = html;
  tip.style.opacity = "1";
  const pw = canvas.parentElement.clientWidth;
  const tw = tip.offsetWidth;
  let left = x + 12;
  if (left + tw > pw) left = x - tw - 12;
  tip.style.left = `${Math.max(0, left)}px`;
  tip.style.top = `${Math.max(0, y - 10)}px`;
}

function hideTip(tip) {
  tip.style.opacity = "0";
}

function attachResize(canvas, draw) {
  if (!("ResizeObserver" in window)) return;
  const ro = new ResizeObserver(() => draw());
  ro.observe(canvas.parentElement);
  canvas._ro = ro;
  const rerender = () => draw();
  document.addEventListener("themechange", rerender);
  canvas._themeHandler = rerender;
}

export function destroyChart(canvas) {
  if (canvas._ro) canvas._ro.disconnect();
  if (canvas._themeHandler) document.removeEventListener("themechange", canvas._themeHandler);
}

/* ---------- Line / area ---------- */
export function lineChart(canvas, { labels = [], series = [], area = true, yFormat = (v) => v, xTicks = 6, smooth = true } = {}) {
  const colors = palette();
  const tip = ensureTooltip(canvas);
  let geom = null;

  function draw() {
    const { ctx, w, h } = setupCanvas(canvas);
    const t = theme();
    const maxVal = Math.max(1, ...series.flatMap((s) => s.data));
    const ticks = niceTicks(maxVal);
    // margins fit the actual labels, so axis text is never clipped
    ctx.font = `11px ${t.font}`;
    const widest = Math.max(...ticks.map((v) => ctx.measureText(String(yFormat(v))).width));
    const lastX = ctx.measureText(String(labels[labels.length - 1] ?? "")).width;
    const pad = { l: Math.max(36, Math.ceil(widest) + 14), r: Math.max(12, Math.ceil(lastX / 2) + 4), t: 12, b: 26 };
    const pw = w - pad.l - pad.r;
    const ph = h - pad.t - pad.b;
    const yMax = ticks[ticks.length - 1] || 1;
    const n = Math.max(1, labels.length);
    const xAt = (i) => pad.l + (n === 1 ? pw / 2 : (i / (n - 1)) * pw);
    const yAt = (v) => pad.t + ph - (v / yMax) * ph;
    ctx.clearRect(0, 0, w, h);
    ctx.font = `11px ${t.font}`;
    ctx.fillStyle = t.text;
    ctx.strokeStyle = t.grid;
    ctx.lineWidth = 1;
    ticks.forEach((v) => {
      const y = yAt(v);
      ctx.beginPath();
      ctx.moveTo(pad.l, y);
      ctx.lineTo(pad.l + pw, y);
      ctx.stroke();
      ctx.textAlign = "right";
      ctx.textBaseline = "middle";
      ctx.fillText(String(yFormat(v)), pad.l - 8, y);
    });
    const every = Math.max(1, Math.ceil(n / xTicks));
    ctx.textAlign = "center";
    ctx.textBaseline = "top";
    labels.forEach((l, i) => {
      if (i % every === 0 || i === n - 1) ctx.fillText(String(l), xAt(i), pad.t + ph + 8);
    });
    series.forEach((s, si) => {
      const color = s.color || colors[si % colors.length];
      const pts = s.data.map((v, i) => [xAt(i), yAt(v)]);
      if (area && pts.length > 1) {
        const g = ctx.createLinearGradient(0, pad.t, 0, pad.t + ph);
        g.addColorStop(0, color + "33");
        g.addColorStop(1, color + "00");
        ctx.beginPath();
        pathThrough(ctx, pts, smooth);
        ctx.lineTo(pts[pts.length - 1][0], pad.t + ph);
        ctx.lineTo(pts[0][0], pad.t + ph);
        ctx.closePath();
        ctx.fillStyle = g;
        ctx.fill();
      }
      ctx.beginPath();
      pathThrough(ctx, pts, smooth);
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.lineJoin = "round";
      ctx.lineCap = "round";
      ctx.stroke();
      if (pts.length === 1) {
        ctx.beginPath();
        ctx.arc(pts[0][0], pts[0][1], 4, 0, Math.PI * 2);
        ctx.fillStyle = color;
        ctx.fill();
      }
    });
    geom = { pad, pw, ph, xAt, yAt, n, colors };
  }

  function pathThrough(ctx, pts, smooth) {
    if (!pts.length) return;
    ctx.moveTo(pts[0][0], pts[0][1]);
    if (!smooth || pts.length < 3) {
      pts.slice(1).forEach((p) => ctx.lineTo(p[0], p[1]));
      return;
    }
    for (let i = 0; i < pts.length - 1; i++) {
      const p0 = pts[i - 1] || pts[i];
      const p1 = pts[i];
      const p2 = pts[i + 1];
      const p3 = pts[i + 2] || p2;
      // control points stay within this segment's range: smooth, but never overshoots (no fake dips below 0)
      const lo = Math.min(p1[1], p2[1]);
      const hi = Math.max(p1[1], p2[1]);
      const clampY = (v) => Math.min(hi, Math.max(lo, v));
      const cp1x = p1[0] + (p2[0] - p0[0]) / 6;
      const cp1y = clampY(p1[1] + (p2[1] - p0[1]) / 6);
      const cp2x = p2[0] - (p3[0] - p1[0]) / 6;
      const cp2y = clampY(p2[1] - (p3[1] - p1[1]) / 6);
      ctx.bezierCurveTo(cp1x, cp1y, cp2x, cp2y, p2[0], p2[1]);
    }
  }

  function onMove(e) {
    if (!geom) return;
    const rect = canvas.getBoundingClientRect();
    const k = uiScale();
    const x = (e.clientX - rect.left) / k;
    const y = (e.clientY - rect.top) / k;
    const i = Math.round(((x - geom.pad.l) / Math.max(1, geom.pw)) * (geom.n - 1));
    if (i < 0 || i >= geom.n) return hideTip(tip);
    draw();
    const { ctx } = setupCanvas(canvas);
    draw();
    const cx = geom.xAt(i);
    ctx.save();
    ctx.strokeStyle = theme().border;
    ctx.setLineDash([3, 3]);
    ctx.beginPath();
    ctx.moveTo(cx, geom.pad.t);
    ctx.lineTo(cx, geom.pad.t + geom.ph);
    ctx.stroke();
    ctx.restore();
    series.forEach((s, si) => {
      const color = s.color || geom.colors[si % geom.colors.length];
      ctx.beginPath();
      ctx.arc(cx, geom.yAt(s.data[i] || 0), 4.5, 0, Math.PI * 2);
      ctx.fillStyle = color;
      ctx.fill();
      ctx.lineWidth = 2;
      ctx.strokeStyle = theme().surface;
      ctx.stroke();
    });
    const rows = series
      .map((s, si) => {
        const color = s.color || geom.colors[si % geom.colors.length];
        return `<div style="display:flex;gap:8px;align-items:center"><i style="width:8px;height:8px;border-radius:2px;background:${color};display:inline-block"></i>${s.name ? s.name + ": " : ""}<b>${yFormat(s.data[i] || 0)}</b></div>`;
      })
      .join("");
    showTip(tip, canvas, x, y, `<div style="opacity:.75;margin-bottom:4px">${labels[i]}</div>${rows}`);
  }

  canvas.onmousemove = onMove;
  canvas.onmouseleave = () => {
    hideTip(tip);
    draw();
  };
  draw();
  attachResize(canvas, draw);
  return { update: (opts) => { Object.assign({ labels, series }, opts); labels = opts.labels || labels; series = opts.series || series; draw(); }, redraw: draw };
}

/* ---------- Bars ---------- */
export function barChart(canvas, { labels = [], series = [], stacked = false, horizontal = false, yFormat = (v) => v, xTicks = 8 } = {}) {
  const colors = palette();
  const tip = ensureTooltip(canvas);
  let rects = [];

  function draw() {
    const { ctx, w, h } = setupCanvas(canvas);
    const t = theme();
    const n = Math.max(1, labels.length);
    const totals = labels.map((_, i) => (stacked ? series.reduce((a, s) => a + (s.data[i] || 0), 0) : Math.max(...series.map((s) => s.data[i] || 0))));
    const maxVal = Math.max(1, ...totals);
    const ticks = niceTicks(maxVal);
    // margins fit the actual labels, so axis text is never clipped
    ctx.font = `11px ${t.font}`;
    const measure = (txt) => ctx.measureText(String(txt)).width;
    const tickW = Math.max(...ticks.map((v) => measure(yFormat(v))));
    const pad = horizontal
      ? { l: Math.min(w * 0.4, Math.ceil(Math.max(...labels.map((l) => measure(truncate(String(l), 18))))) + 18), r: Math.max(16, Math.ceil(measure(yFormat(ticks[ticks.length - 1])) / 2) + 4), t: 8, b: 20 }
      : { l: Math.max(36, Math.ceil(tickW) + 14), r: 12, t: 12, b: 26 };
    const pw = w - pad.l - pad.r;
    const ph = h - pad.t - pad.b;
    const vMax = ticks[ticks.length - 1] || 1;
    ctx.clearRect(0, 0, w, h);
    ctx.font = `11px ${t.font}`;
    ctx.fillStyle = t.text;
    ctx.strokeStyle = t.grid;
    ctx.lineWidth = 1;
    rects = [];
    if (horizontal) {
      ticks.forEach((v) => {
        const x = pad.l + (v / vMax) * pw;
        ctx.beginPath();
        ctx.moveTo(x, pad.t);
        ctx.lineTo(x, pad.t + ph);
        ctx.stroke();
        ctx.textAlign = "center";
        ctx.textBaseline = "top";
        ctx.fillText(String(yFormat(v)), x, pad.t + ph + 6);
      });
      const band = ph / n;
      const barH = Math.min(22, band * 0.6);
      labels.forEach((l, i) => {
        const y = pad.t + band * i + (band - barH) / 2;
        ctx.textAlign = "right";
        ctx.textBaseline = "middle";
        ctx.fillStyle = t.text;
        ctx.fillText(truncate(String(l), 18), pad.l - 10, y + barH / 2);
        let x0 = pad.l;
        series.forEach((s, si) => {
          const v = s.data[i] || 0;
          const bw = (v / vMax) * pw;
          const x = stacked ? x0 : pad.l;
          const yy = stacked ? y : y + (barH / series.length) * si;
          const hh = stacked ? barH : barH / series.length - 2;
          roundRect(ctx, x + (stacked && si > 0 ? 2 : 0), yy, Math.max(0, bw - (stacked && si > 0 ? 2 : 0)), hh, 4, s.color || colors[si % colors.length]);
          rects.push({ x, y: yy, w: bw, h: hh, label: l, name: s.name, value: v, color: s.color || colors[si % colors.length] });
          x0 += bw;
        });
      });
    } else {
      ticks.forEach((v) => {
        const y = pad.t + ph - (v / vMax) * ph;
        ctx.beginPath();
        ctx.moveTo(pad.l, y);
        ctx.lineTo(pad.l + pw, y);
        ctx.stroke();
        ctx.textAlign = "right";
        ctx.textBaseline = "middle";
        ctx.fillText(String(yFormat(v)), pad.l - 8, y);
      });
      const band = pw / n;
      const groupW = Math.min(band * 0.68, 48);
      const every = Math.max(1, Math.ceil(n / xTicks));
      labels.forEach((l, i) => {
        const cx = pad.l + band * i + band / 2;
        if (i % every === 0 || i === n - 1) {
          ctx.textAlign = "center";
          ctx.textBaseline = "top";
          ctx.fillStyle = t.text;
          ctx.fillText(truncate(String(l), 10), cx, pad.t + ph + 8);
        }
        let yTop = pad.t + ph;
        series.forEach((s, si) => {
          const v = s.data[i] || 0;
          const bh = (v / vMax) * ph;
          if (stacked) {
            const y = yTop - bh;
            const gap = si > 0 && bh > 2 ? 2 : 0;
            roundRect(ctx, cx - groupW / 2, y, groupW, Math.max(0, bh - gap), si === series.length - 1 ? 4 : 0, s.color || colors[si % colors.length]);
            rects.push({ x: cx - groupW / 2, y, w: groupW, h: bh, label: l, name: s.name, value: v, color: s.color || colors[si % colors.length] });
            yTop = y;
          } else {
            const bw = groupW / series.length - 2;
            const x = cx - groupW / 2 + si * (bw + 2);
            const y = pad.t + ph - bh;
            roundRect(ctx, x, y, bw, bh, 4, s.color || colors[si % colors.length]);
            rects.push({ x, y, w: bw, h: bh, label: l, name: s.name, value: v, color: s.color || colors[si % colors.length] });
          }
        });
      });
    }
  }

  function roundRect(ctx, x, y, w, h, r, color) {
    if (w <= 0 || h <= 0) return;
    const rr = Math.min(r, w / 2, h / 2);
    ctx.beginPath();
    ctx.moveTo(x, y + h);
    ctx.lineTo(x, y + rr);
    ctx.quadraticCurveTo(x, y, x + rr, y);
    ctx.lineTo(x + w - rr, y);
    ctx.quadraticCurveTo(x + w, y, x + w, y + rr);
    ctx.lineTo(x + w, y + h);
    ctx.closePath();
    ctx.fillStyle = color;
    ctx.fill();
  }

  function truncate(s, n) {
    return s.length > n ? s.slice(0, n - 1) + "…" : s;
  }

  canvas.onmousemove = (e) => {
    const rect = canvas.getBoundingClientRect();
    const k = uiScale();
    const x = (e.clientX - rect.left) / k;
    const y = (e.clientY - rect.top) / k;
    const hit = rects.find((r) => x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h);
    if (!hit) return hideTip(tip);
    showTip(tip, canvas, x, y, `<div style="opacity:.75;margin-bottom:4px">${hit.label}</div><div style="display:flex;gap:8px;align-items:center"><i style="width:8px;height:8px;border-radius:2px;background:${hit.color};display:inline-block"></i>${hit.name ? hit.name + ": " : ""}<b>${yFormat(hit.value)}</b></div>`);
  };
  canvas.onmouseleave = () => hideTip(tip);
  draw();
  attachResize(canvas, draw);
  return { update: (opts) => { labels = opts.labels || labels; series = opts.series || series; draw(); }, redraw: draw };
}

/* ---------- Donut ---------- */
export function donutChart(canvas, { items = [], total = null, centerLabel = "", valueFormat = (v) => v } = {}) {
  const colors = palette();
  const tip = ensureTooltip(canvas);
  let arcs = [];

  function draw() {
    const { ctx, w, h } = setupCanvas(canvas);
    const t = theme();
    const sum = total ?? items.reduce((a, i) => a + (i.value || 0), 0);
    const cx = w / 2;
    const cy = h / 2;
    const r = Math.min(w, h) / 2 - 6;
    const thick = Math.max(10, r * 0.28);
    ctx.clearRect(0, 0, w, h);
    arcs = [];
    let a = -Math.PI / 2;
    if (!sum) {
      ctx.beginPath();
      ctx.arc(cx, cy, r - thick / 2, 0, Math.PI * 2);
      ctx.strokeStyle = t.grid;
      ctx.lineWidth = thick;
      ctx.stroke();
    }
    items.forEach((it, i) => {
      const frac = sum ? (it.value || 0) / sum : 0;
      const end = a + frac * Math.PI * 2;
      const gap = items.length > 1 ? 0.03 : 0;
      ctx.beginPath();
      ctx.arc(cx, cy, r - thick / 2, a + gap / 2, Math.max(a + gap / 2, end - gap / 2));
      ctx.strokeStyle = it.color || colors[i % colors.length];
      ctx.lineWidth = thick;
      ctx.lineCap = "butt";
      ctx.stroke();
      arcs.push({ start: a, end, ...it, color: it.color || colors[i % colors.length], frac });
      a = end;
    });
    ctx.fillStyle = t.textStrong;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.font = `700 ${Math.max(14, r * 0.42)}px ${t.font}`;
    ctx.fillText(String(valueFormat(sum)), cx, cy - (centerLabel ? 6 : 0));
    if (centerLabel) {
      ctx.font = `11px ${t.font}`;
      ctx.fillStyle = t.text;
      ctx.fillText(centerLabel, cx, cy + Math.max(12, r * 0.22));
    }
  }

  canvas.onmousemove = (e) => {
    const rect = canvas.getBoundingClientRect();
    const k = uiScale();
    const x = (e.clientX - rect.left) / k;
    const y = (e.clientY - rect.top) / k;
    const cx = rect.width / k / 2;
    const cy = rect.height / k / 2;
    const dx = x - cx;
    const dy = y - cy;
    const dist = Math.sqrt(dx * dx + dy * dy);
    const r = Math.min(rect.width, rect.height) / 2 - 6;
    const thick = Math.max(10, r * 0.28);
    if (dist < r - thick || dist > r) return hideTip(tip);
    let ang = Math.atan2(dy, dx);
    if (ang < -Math.PI / 2) ang += Math.PI * 2;
    const hit = arcs.find((a) => ang >= a.start && ang <= a.end);
    if (!hit) return hideTip(tip);
    showTip(tip, canvas, x, y, `<div style="display:flex;gap:8px;align-items:center"><i style="width:8px;height:8px;border-radius:2px;background:${hit.color};display:inline-block"></i>${hit.label}: <b>${valueFormat(hit.value)}</b> (${Math.round(hit.frac * 100)}%)</div>`);
  };
  canvas.onmouseleave = () => hideTip(tip);
  draw();
  attachResize(canvas, draw);
  return { update: (opts) => { items = opts.items || items; draw(); }, redraw: draw };
}

/* ---------- Sparkline ---------- */
export function sparkline(canvas, data = [], color) {
  function draw() {
    const { ctx, w, h } = setupCanvas(canvas);
    const c = color || palette()[0];
    const max = Math.max(1, ...data);
    const min = Math.min(0, ...data);
    const n = Math.max(1, data.length);
    const xAt = (i) => (n === 1 ? w / 2 : (i / (n - 1)) * (w - 4) + 2);
    const yAt = (v) => h - 3 - ((v - min) / (max - min || 1)) * (h - 6);
    ctx.clearRect(0, 0, w, h);
    ctx.beginPath();
    data.forEach((v, i) => (i ? ctx.lineTo(xAt(i), yAt(v)) : ctx.moveTo(xAt(i), yAt(v))));
    ctx.strokeStyle = c;
    ctx.lineWidth = 2;
    ctx.lineJoin = "round";
    ctx.stroke();
    if (data.length) {
      ctx.lineTo(xAt(n - 1), h);
      ctx.lineTo(xAt(0), h);
      ctx.closePath();
      ctx.fillStyle = c + "22";
      ctx.fill();
    }
  }
  draw();
  attachResize(canvas, draw);
  return { redraw: draw };
}

/* Legend helper: returns HTML for a series legend (identity never color-alone). */
export function legendHtml(items) {
  const colors = palette();
  return `<div class="chart-legend" style="display:flex;flex-wrap:wrap;gap:0.75rem;font-size:0.75rem;color:var(--text-3)">${items
    .map((it, i) => `<span style="display:inline-flex;align-items:center;gap:6px"><i style="width:10px;height:10px;border-radius:3px;background:${it.color || colors[i % colors.length]};display:inline-block"></i>${it.label ?? it.name}${it.value !== undefined ? ` <b style="color:var(--text)">${it.value}</b>` : ""}</span>`)
    .join("")}</div>`;
}
