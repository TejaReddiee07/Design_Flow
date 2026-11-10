/* Agent orb: the animated "AI core" shown while an agent works on the See-in-live page.
   A rotating wireframe sphere, a glowing core, light rays, a swirling particle cloud and orbit rings,
   drawn on a canvas with additive blending. Each agent has its own colour; the orb runs at full energy
   while that agent is working and settles into a slow idle glow otherwise.

   Performance notes: styles are bucketed (particles, edges and dots are drawn in batches per colour/alpha
   level, not one style per element), nothing is allocated inside the frame loop, and in waiting/idle/done
   modes the canvas repaints at ~15 fps instead of 60. The loop pauses when the orb is off-screen or the
   tab is hidden, and restarts on visibilitychange. */

// One colour per agent, in pipeline order. All are tones the dashboard already uses (info blue, cyan,
// violet, pink, brand indigo, yellow, orange, the amber "your turn" warning and the success emerald),
// so the orbs match the rest of the interface. The first agent is blue; QA deliberately avoids the
// success green so a *running* QA never looks like a *finished* step.
export const AGENT_COLORS = {
  project_manager: { main: "#2563EB", light: "#93C5FD", deep: "#1D4ED8", name: "Blue" },
  strategy: { main: "#06B6D4", light: "#67E8F9", deep: "#0E7490", name: "Cyan" },
  content: { main: "#8B5CF6", light: "#C4B5FD", deep: "#6D28D9", name: "Violet" },
  design: { main: "#EC4899", light: "#F9A8D4", deep: "#BE185D", name: "Pink" },
  qa: { main: "#6366F1", light: "#A5B4FC", deep: "#4338CA", name: "Indigo" },
  revision: { main: "#EAB308", light: "#FDE047", deep: "#A16207", name: "Yellow" },
  delivery: { main: "#F97316", light: "#FDBA74", deep: "#C2410C", name: "Orange" },
  approval: { main: "#F59E0B", light: "#FCD34D", deep: "#B45309", name: "Amber" },
  done: { main: "#10B981", light: "#A7F3D0", deep: "#065F46", name: "Emerald" },
  idle: { main: "#64748B", light: "#CBD5E1", deep: "#334155", name: "Slate" },
};

export function agentColor(key) {
  return AGENT_COLORS[key] || AGENT_COLORS.idle;
}

const ENERGY = { running: 1, waiting: 0.55, done: 0.42, idle: 0.32 };
const N_PARTICLES = 760;
const ALPHA_BUCKETS = 10;
const COLOR_VARIANTS = 8; // 4 warmth levels x (towards light | towards white)
const SLOW_FRAME_MS = 64; // ~15 fps when not running

const hex = (h) => {
  const v = h.replace("#", "");
  return [parseInt(v.slice(0, 2), 16), parseInt(v.slice(2, 4), 16), parseInt(v.slice(4, 6), 16)];
};
const mix = (a, b, t) => [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
const rgba = (c, a) => `rgba(${c[0] | 0},${c[1] | 0},${c[2] | 0},${Math.max(0, Math.min(1, a)).toFixed(3)})`;
const WHITE = [255, 255, 255];

/** Deterministic pseudo-random numbers so every orb looks the same on every load. */
function rng(seed) {
  let s = seed >>> 0;
  return () => {
    s = (s * 1664525 + 1013904223) >>> 0;
    return s / 4294967296;
  };
}

export class AgentOrb {
  /** Options (defaults = the admin live view): particles, maxDpr (canvas resolution cap), fps (cap while running). */
  constructor(canvas, { seed = 7, particles = N_PARTICLES, maxDpr = 2, fps = 60 } = {}) {
    this.canvas = canvas;
    this.nParticles = Math.max(60, particles | 0);
    this.maxDpr = maxDpr;
    this.minGap = fps >= 60 ? 0 : 1000 / fps - 2;
    this.ctx = canvas.getContext("2d");
    this.mq = window.matchMedia ? window.matchMedia("(prefers-reduced-motion: reduce)") : null;
    this.reduced = Boolean(this.mq && this.mq.matches);
    const c = AGENT_COLORS.idle;
    this.col = { main: hex(c.main), light: hex(c.light), deep: hex(c.deep) };
    this.target = { main: hex(c.main), light: hex(c.light), deep: hex(c.deep) };
    this.energy = ENERGY.idle;
    this.targetEnergy = ENERGY.idle;
    this.state = "idle";
    this.t = 0;
    this.last = 0;
    this.lastPaint = 0;
    this.pending = 0;
    this.frameCount = 0;
    this.visible = true;
    this.running = false;
    this.raf = 0;
    this._drawn = false;
    this._build(seed);
    this._frame = this._frame.bind(this);
    this._resize = this._resize.bind(this);
    this._onVis = () => {
      if (!document.hidden) this.start();
    };
    this._onMotion = (e) => {
      this.reduced = e.matches;
      if (this.reduced) {
        this.stop();
        this.col = { main: this.target.main.slice(), light: this.target.light.slice(), deep: this.target.deep.slice() };
        this.energy = this.targetEnergy;
        this._draw(0);
      } else {
        this.start();
      }
    };
    document.addEventListener("visibilitychange", this._onVis);
    if (this.mq && this.mq.addEventListener) this.mq.addEventListener("change", this._onMotion);
    this.ro = new ResizeObserver(this._resize);
    this.ro.observe(canvas);
    this.io = new IntersectionObserver((entries) => {
      this.visible = entries.some((e) => e.isIntersecting);
      if (this.visible) this.start();
    });
    this.io.observe(canvas);
    this._resize();
  }

  /* ---------- geometry (built once, no allocation per frame) ---------- */
  _build(seed) {
    const r = rng(seed);
    // wireframe: Fibonacci sphere points, each joined to its nearest neighbours
    const n = 72;
    const pts = [];
    const golden = Math.PI * (3 - Math.sqrt(5));
    for (let i = 0; i < n; i++) {
      const y = 1 - (i / (n - 1)) * 2;
      const rad = Math.sqrt(1 - y * y);
      const th = golden * i;
      pts.push([Math.cos(th) * rad, y, Math.sin(th) * rad]);
    }
    const edgeSet = new Set();
    pts.forEach((p, i) => {
      pts
        .map((q, j) => [j, (p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 + (p[2] - q[2]) ** 2])
        .filter(([j]) => j !== i)
        .sort((a, b) => a[1] - b[1])
        .slice(0, 4)
        .forEach(([j]) => edgeSet.add(i < j ? i * 100 + j : j * 100 + i));
    });
    this.sphN = n;
    this.sphX = new Float32Array(n);
    this.sphY = new Float32Array(n);
    this.sphZ = new Float32Array(n);
    pts.forEach(([x, y, z], i) => {
      this.sphX[i] = x;
      this.sphY[i] = y;
      this.sphZ[i] = z;
    });
    const edges = [...edgeSet];
    this.edgeA = new Int16Array(edges.map((e) => (e / 100) | 0));
    this.edgeB = new Int16Array(edges.map((e) => e % 100));
    this.projX = new Float32Array(n);
    this.projY = new Float32Array(n);
    this.projZ = new Float32Array(n);

    // particle cloud: a soft shell around the sphere, each particle orbiting on its own tilt
    const P = this.nParticles;
    this.pA = new Float32Array(P); // current angle
    this.pSp = new Float32Array(P); // angular speed
    this.pCi = new Float32Array(P); // cos(inclination)
    this.pSi = new Float32Array(P); // sin(inclination)
    this.pRad = new Float32Array(P);
    this.pSize = new Float32Array(P);
    this.pTw = new Float32Array(P); // twinkle phase
    this.pVar = new Uint8Array(P); // colour variant 0..7
    this.varMixT = new Float32Array(COLOR_VARIANTS);
    this.varToWhite = new Uint8Array(COLOR_VARIANTS);
    for (let v = 0; v < COLOR_VARIANTS; v++) {
      const level = v % 4;
      this.varMixT[v] = 0.08 + level * 0.14; // mix amount towards light/white
      this.varToWhite[v] = v >= 4 ? 1 : 0;
    }
    for (let i = 0; i < P; i++) {
      const inc = (r() - 0.5) * Math.PI * 0.95;
      const shell = r() < 0.72 ? 0.62 + r() * 0.5 : 1.12 + r() * 0.55;
      this.pA[i] = r() * Math.PI * 2;
      this.pSp[i] = (0.08 + r() * 0.22) * (r() < 0.5 ? 1 : -1);
      this.pCi[i] = Math.cos(inc);
      this.pSi[i] = Math.sin(inc);
      this.pRad[i] = shell;
      this.pSize[i] = 0.45 + r() * 1.35;
      this.pTw[i] = r() * Math.PI * 2;
      const warm = r();
      this.pVar[i] = (warm > 0.7 ? 4 : 0) + Math.min(3, (warm * 4) | 0);
    }
    // reusable draw buffers and buckets
    this.bufX = new Float32Array(P);
    this.bufY = new Float32Array(P);
    this.bufS = new Float32Array(P);
    this.pBuckets = Array.from({ length: COLOR_VARIANTS * ALPHA_BUCKETS }, () => []);
    this.eBuckets = Array.from({ length: 8 }, () => []);
    this.dBuckets = Array.from({ length: 8 }, () => []);
    this.varRGB = Array.from({ length: COLOR_VARIANTS }, () => [0, 0, 0]);

    // light rays from the core (the signature of the reference look)
    this.rays = Array.from({ length: 26 }, (_, i) => ({ a: (i / 26) * Math.PI * 2 + r() * 0.3, len: 1.1 + r() * 0.8, ph: r() * Math.PI * 2,
                                                       fr: 0.6 + r() * 1.4, w: 0.6 + r() * 1.3 }));
    // orbit rings: partial arcs on different tilts
    this.rings = [
      { rad: 1.16, tilt: -0.5, squash: 0.36, span: 2.4, sp: 0.55, w: 7 },
      { rad: 1.3, tilt: 0.85, squash: 0.28, span: 1.6, sp: -0.38, w: 4 },
      { rad: 1.05, tilt: 0.12, squash: 0.92, span: 4.6, sp: 0.22, w: 1.4 },
    ];
  }

  _resize() {
    const rect = this.canvas.getBoundingClientRect();
    const raw = window.devicePixelRatio || 1;
    this.rawDpr = raw;
    const dpr = Math.min(raw, this.maxDpr);
    const w = Math.max(1, Math.round(rect.width * dpr));
    const h = Math.max(1, Math.round(rect.height * dpr));
    if (this.canvas.width !== w || this.canvas.height !== h) {
      this.canvas.width = w;
      this.canvas.height = h;
    }
    this.dpr = dpr;
    // repaint immediately so the orb never blanks while the window is resized
    this._draw(this._drawn ? 1e-4 : 0);
  }

  /* ---------- public API ---------- */
  /** state: running | waiting | done | idle; key: agent key (colour) */
  set(key, state = "running") {
    const c = agentColor(key);
    this.target = { main: hex(c.main), light: hex(c.light), deep: hex(c.deep) };
    this.targetEnergy = ENERGY[state] ?? ENERGY.idle;
    this.key = key;
    this.state = state;
    if (this.reduced) {
      this.col = { main: this.target.main.slice(), light: this.target.light.slice(), deep: this.target.deep.slice() };
      this.energy = this.targetEnergy;
      this._draw(0);
    } else {
      this.start();
    }
  }

  start() {
    if (this.reduced || this.running || !this.visible || document.hidden || !this.canvas.isConnected) return;
    this.running = true;
    this.last = performance.now();
    this.lastPaint = 0;
    this.pending = 0;
    this.raf = requestAnimationFrame(this._frame);
  }

  stop() {
    this.running = false;
    if (this.raf) cancelAnimationFrame(this.raf);
    this.raf = 0;
  }

  destroy() {
    this.stop();
    this.ro.disconnect();
    this.io.disconnect();
    document.removeEventListener("visibilitychange", this._onVis);
    if (this.mq && this.mq.removeEventListener) this.mq.removeEventListener("change", this._onMotion);
  }

  _frame(now) {
    if (!this.running) return;
    if (!this.visible || document.hidden || !this.canvas.isConnected) {
      this.running = false;
      this.raf = 0;
      return;
    }
    this.raf = requestAnimationFrame(this._frame);
    this.pending = Math.min(0.12, this.pending + Math.min(0.05, (now - this.last) / 1000));
    this.last = now;
    // when nothing is running, repaint gently (~15 fps) instead of every frame
    if (now - this.lastPaint < (this.state !== "running" ? SLOW_FRAME_MS : this.minGap)) return;
    // follow browser zoom / monitor changes
    if (++this.frameCount % 30 === 0 && (window.devicePixelRatio || 1) !== this.rawDpr) this._resize();
    const dt = this.pending;
    this.pending = 0;
    this.lastPaint = now;
    this._draw(dt);
  }

  /* ---------- drawing ---------- */
  _draw(dt) {
    const { ctx, canvas } = this;
    const W = canvas.width;
    const H = canvas.height;
    if (!W || !H) return;
    this._drawn = true;
    // ease colour and energy towards the target state (dt = 0 snaps)
    const k = dt ? 1 - Math.pow(0.0025, dt) : 1;
    this.col.main = mix(this.col.main, this.target.main, k);
    this.col.light = mix(this.col.light, this.target.light, k);
    this.col.deep = mix(this.col.deep, this.target.deep, k);
    this.energy += (this.targetEnergy - this.energy) * k;
    const e = this.energy;
    this.t += dt * (0.25 + e * 0.95);
    const t = this.t;
    const { main, light, deep } = this.col;
    const cx = W / 2;
    const cy = H * 0.42; // the caption sits below, so the orb rides high
    const R = Math.min(W, H * 0.86) * 0.27;
    const px = this.dpr;

    // deep space background tinted with the agent colour
    ctx.globalCompositeOperation = "source-over";
    const bg = ctx.createRadialGradient(cx, cy, R * 0.2, cx, cy, Math.max(W, H) * 0.75);
    bg.addColorStop(0, rgba(mix([5, 7, 15], deep, 0.35), 1));
    bg.addColorStop(1, "rgba(4,5,12,1)");
    ctx.fillStyle = bg;
    ctx.fillRect(0, 0, W, H);

    ctx.globalCompositeOperation = "lighter";

    // halo
    const halo = ctx.createRadialGradient(cx, cy, 0, cx, cy, R * 1.9);
    halo.addColorStop(0, rgba(main, 0.3 * e + 0.06));
    halo.addColorStop(0.45, rgba(deep, 0.15 * e + 0.03));
    halo.addColorStop(1, rgba(deep, 0));
    ctx.fillStyle = halo;
    ctx.fillRect(0, 0, W, H);

    const rotY = t * 0.42;
    const rotX = -0.42 + Math.sin(t * 0.21) * 0.12;
    const cyR = Math.cos(rotY);
    const syR = Math.sin(rotY);
    const cxR = Math.cos(rotX);
    const sxR = Math.sin(rotX);

    /* particles: project, bucket by (colour variant, alpha level), then draw one style per bucket */
    for (let v = 0; v < COLOR_VARIANTS; v++) {
      const target = this.varToWhite[v] ? WHITE : light;
      const rgb = this.varRGB[v];
      rgb[0] = main[0] + (target[0] - main[0]) * this.varMixT[v];
      rgb[1] = main[1] + (target[1] - main[1]) * this.varMixT[v];
      rgb[2] = main[2] + (target[2] - main[2]) * this.varMixT[v];
    }
    const pB = this.pBuckets;
    for (let b = 0; b < pB.length; b++) pB[b].length = 0;
    const eGain = 0.3 + 0.7 * e;
    const spGain = dt * (0.35 + e * 1.4);
    for (let i = 0; i < this.nParticles; i++) {
      this.pA[i] += this.pSp[i] * spGain;
      const ca = Math.cos(this.pA[i]);
      const sa = Math.sin(this.pA[i]);
      const x0 = ca * this.pCi[i] * this.pRad[i];
      const y0 = this.pSi[i] * this.pRad[i] * 0.9;
      const z0 = sa * this.pCi[i] * this.pRad[i];
      const x1 = x0 * cyR + z0 * syR;
      const z1 = -x0 * syR + z0 * cyR;
      const y2 = y0 * cxR - z1 * sxR;
      const z2 = y0 * sxR + z1 * cxR;
      const depth = (z2 + 1.6) / 3.2;
      const twinkle = 0.65 + 0.35 * Math.sin(t * 3 + this.pTw[i]);
      const alpha = (0.18 + 0.72 * depth) * twinkle * eGain;
      this.bufX[i] = cx + x1 * R;
      this.bufY[i] = cy + y2 * R;
      this.bufS[i] = this.pSize[i] * px * (0.7 + depth * 0.6);
      const ai = Math.min(ALPHA_BUCKETS - 1, (alpha * ALPHA_BUCKETS) | 0);
      pB[this.pVar[i] * ALPHA_BUCKETS + ai].push(i);
    }
    for (let b = 0; b < pB.length; b++) {
      const list = pB[b];
      if (!list.length) continue;
      const a = ((b % ALPHA_BUCKETS) + 0.5) / ALPHA_BUCKETS;
      ctx.fillStyle = rgba(this.varRGB[(b / ALPHA_BUCKETS) | 0], a);
      for (let j = 0; j < list.length; j++) {
        const i = list[j];
        const s = this.bufS[i];
        ctx.fillRect(this.bufX[i] - s / 2, this.bufY[i] - s / 2, s, s);
      }
    }

    /* wireframe sphere: project 72 points once, draw edges in 8 depth buckets */
    for (let i = 0; i < this.sphN; i++) {
      const x0 = this.sphX[i] * 0.86;
      const y0 = this.sphY[i] * 0.86;
      const z0 = this.sphZ[i] * 0.86;
      const x1 = x0 * cyR + z0 * syR;
      const z1 = -x0 * syR + z0 * cyR;
      this.projX[i] = cx + x1 * R;
      this.projY[i] = cy + (y0 * cxR - z1 * sxR) * R;
      this.projZ[i] = y0 * sxR + z1 * cxR;
    }
    const eB = this.eBuckets;
    for (let b = 0; b < 8; b++) eB[b].length = 0;
    for (let i = 0; i < this.edgeA.length; i++) {
      const depth = ((this.projZ[this.edgeA[i]] + this.projZ[this.edgeB[i]]) / 2 + 1) / 2;
      eB[Math.min(7, (depth * 8) | 0)].push(i);
    }
    ctx.lineWidth = Math.max(1, 0.9 * px);
    const eAlphaGain = 0.35 + 0.65 * e;
    for (let b = 0; b < 8; b++) {
      const list = eB[b];
      if (!list.length) continue;
      const depth = (b + 0.5) / 8;
      ctx.strokeStyle = rgba(mix(main, light, depth), (0.08 + 0.5 * depth) * eAlphaGain);
      ctx.beginPath();
      for (let j = 0; j < list.length; j++) {
        const i = list[j];
        ctx.moveTo(this.projX[this.edgeA[i]], this.projY[this.edgeA[i]]);
        ctx.lineTo(this.projX[this.edgeB[i]], this.projY[this.edgeB[i]]);
      }
      ctx.stroke();
    }
    const dB = this.dBuckets;
    for (let b = 0; b < 8; b++) dB[b].length = 0;
    for (let i = 0; i < this.sphN; i++) {
      const depth = (this.projZ[i] / 0.86 + 1) / 2;
      dB[Math.min(7, (Math.max(0, depth) * 8) | 0)].push(i);
    }
    for (let b = 0; b < 8; b++) {
      const list = dB[b];
      if (!list.length) continue;
      const depth = (b + 0.5) / 8;
      ctx.fillStyle = rgba(light, (0.15 + 0.6 * depth) * eAlphaGain);
      const s = (1 + depth * 1.6) * px;
      for (let j = 0; j < list.length; j++) {
        const i = list[j];
        ctx.fillRect(this.projX[i] - s / 2, this.projY[i] - s / 2, s, s);
      }
    }

    /* glowing core (drawn before the rays so they stay visible across it) */
    const pulse = 1 + Math.sin(t * 3.2) * 0.07 * e;
    const coreR = R * (0.2 + 0.1 * e) * pulse;
    const core = ctx.createRadialGradient(cx, cy, 0, cx, cy, coreR * 1.55);
    core.addColorStop(0, rgba(WHITE, 0.95));
    core.addColorStop(0.3, rgba(mix(light, WHITE, 0.5), 0.85 * (0.5 + 0.5 * e)));
    core.addColorStop(0.62, rgba(main, 0.5 * (0.4 + 0.6 * e)));
    core.addColorStop(1, rgba(main, 0));
    ctx.fillStyle = core;
    ctx.beginPath();
    ctx.arc(cx, cy, coreR * 1.55, 0, Math.PI * 2);
    ctx.fill();

    /* light rays: long spokes that reach past the wireframe, the reference image's signature */
    for (const ray of this.rays) {
      const rp = 0.55 + 0.45 * Math.sin(t * ray.fr * 2 + ray.ph);
      const len = R * ray.len * (0.8 + 0.3 * rp) * (0.55 + 0.45 * e);
      const ang = ray.a + t * 0.08;
      const x2 = cx + Math.cos(ang) * len;
      const y2 = cy + Math.sin(ang) * len;
      const grad = ctx.createLinearGradient(cx, cy, x2, y2);
      grad.addColorStop(0, rgba(WHITE, 0.6 * e * rp));
      grad.addColorStop(0.55, rgba(light, 0.42 * e * rp));
      grad.addColorStop(0.85, rgba(main, 0.18 * e * rp));
      grad.addColorStop(1, rgba(main, 0));
      ctx.strokeStyle = grad;
      ctx.lineWidth = ray.w * px * (0.8 + e);
      ctx.beginPath();
      ctx.moveTo(cx, cy);
      ctx.lineTo(x2, y2);
      ctx.stroke();
    }

    /* orbit rings: even-width elliptical arcs with a bright travelling head */
    ctx.lineCap = "round";
    for (const ring of this.rings) {
      const rot = ring.tilt + Math.sin(t * 0.15) * 0.05;
      const start = t * ring.sp * (0.4 + e);
      const rx2 = R * ring.rad;
      const ry2 = R * ring.rad * ring.squash;
      ctx.strokeStyle = rgba(mix(main, light, 0.35), (0.22 + 0.55 * e) * (ring.w > 2 ? 1 : 0.7));
      ctx.lineWidth = ring.w * px;
      ctx.beginPath();
      ctx.ellipse(cx, cy, rx2, ry2, rot, start, start + ring.span);
      ctx.stroke();
      const cosA = Math.cos(start + ring.span);
      const sinA = Math.sin(start + ring.span);
      const cosR = Math.cos(rot);
      const sinR = Math.sin(rot);
      ctx.fillStyle = rgba(WHITE, 0.5 * e);
      ctx.beginPath();
      ctx.arc(cx + rx2 * cosA * cosR - ry2 * sinA * sinR, cy + rx2 * cosA * sinR + ry2 * sinA * cosR, ring.w * 0.55 * px, 0, Math.PI * 2);
      ctx.fill();
    }
    // thin outer guide ring
    ctx.strokeStyle = rgba(light, 0.12 + 0.12 * e);
    ctx.lineWidth = px;
    ctx.beginPath();
    ctx.arc(cx, cy, R * 1.42, 0, Math.PI * 2);
    ctx.stroke();

    ctx.globalCompositeOperation = "source-over";
  }
}
