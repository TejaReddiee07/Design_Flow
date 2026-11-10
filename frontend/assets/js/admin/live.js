/* "See in live": watch the agents build one request in real time.
   Served at /admin/live/<request id>. Loads the stored event feed, then follows the WebSocket:
   pipeline_event (every agent step), agent_stream (the model writing), agent_status, agent_log, request_update. */
import { api, errorMessage, fileUrl, downloadFile } from "../core/api.js";
import { requireAuth } from "../core/auth.js";
import { ws } from "../core/ws.js";
import { esc, icon, qs, qsa, nl2br, fmtDateTime, statusBadge, priorityBadge, toast, initTheme, titleCase, promptDialog, confirmDialog, debounce } from "../core/ui.js";
import { AgentOrb, agentColor } from "../core/agent-orb.js";

const REQUEST_ID = Number(location.pathname.replace(/\/+$/, "").split("/").pop());

const AGENTS = {
  project_manager: { key: "project_manager", name: "Project Manager Agent", icon: "briefcase", does: "Reads the brief, writes the work plan, sets the priority" },
  strategy: { key: "strategy", name: "Strategy Agent", icon: "target", does: "Positioning, audience insights, competitors, creative direction" },
  content: { key: "content", name: "Content Agent", icon: "type", does: "Headlines, body copy, captions and calls to action" },
  design: { key: "design", name: "Design Agent", icon: "palette", does: "Two concept directions and a rendered draft" },
  qa: { key: "qa", name: "QA Agent", icon: "shield", does: "Scores the draft against the brief and the brand" },
  revision: { key: "revision", name: "Revision Agent", icon: "repeat", does: "Turns client feedback into a checkable change list" },
  delivery: { key: "delivery", name: "Delivery Agent", icon: "send", does: "Packages the files and notifies the client" },
};
const SYSTEM = { key: "system", name: "Pipeline", icon: "cpu", does: "" };
const CLOSERS = new Set(["agent_completed", "agent_failed", "agent_stopped", "agent_skipped"]);
const REFRESH_ON = new Set(["agent_completed", "design_rendered", "qa_scored", "awaiting_approval", "approved", "rework", "delivered", "completed", "failed", "stopped", "pipeline_started", "pipeline_resumed"]);

const state = { user: null, req: null, llm: null, agents: {}, events: [], logs: [], seen: new Set(), lastEventId: 0, stream: null, selectedVersion: null };

initTheme();

/* ---------- helpers ---------- */
const agentMeta = (key) => AGENTS[key] || SYSTEM;
const canAct = () => Boolean(state.user && state.user.role !== "client");
const avatar = (key, cls = "") => `<span class="agent-avatar ${esc(agentMeta(key).key)} ${cls}">${icon(agentMeta(key).icon)}</span>`;
const label = (k) => titleCase(String(k).replace(/_/g, " "));
const isHex = (v) => typeof v === "string" && /^#?[0-9a-f]{3,8}$/i.test(v.trim());

function fmtTime(iso) {
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "" : d.toLocaleTimeString(undefined, { hour: "2-digit", minute: "2-digit", second: "2-digit" });
}

function secondsLabel(s) {
  s = Math.max(0, Math.round(s));
  return s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, "0")}s`;
}

const fmtDuration = (ms) => (ms || ms === 0 ? secondsLabel(ms / 1000) : "");
const elapsedLabel = (startIso) => secondsLabel((Date.now() - new Date(startIso).getTime()) / 1000);

function parseJson(text) {
  if (!text || typeof text !== "string") return null;
  try {
    const v = JSON.parse(text);
    return v && typeof v === "object" ? v : null;
  } catch {
    return null;
  }
}

function swatches(list) {
  return `<div class="swatches">${list
    .map((c) => {
      const hex = c.trim().startsWith("#") ? c.trim() : `#${c.trim()}`;
      return `<span class="swatch"><i style="background:${esc(hex)}"></i>${esc(hex)}</span>`;
    })
    .join("")}</div>`;
}

function renderValue(v) {
  if (Array.isArray(v)) {
    if (v.length && v.every(isHex)) return swatches(v);
    return `<ul>${v.map((x) => `<li>${x && typeof x === "object" ? renderData(x) : esc(String(x))}</li>`).join("")}</ul>`;
  }
  if (typeof v === "boolean") return v ? `<span class="badge badge-success">yes</span>` : `<span class="badge">no</span>`;
  return nl2br(String(v));
}

/** Structured agent output (JSON) as aligned key / value rows. */
function renderData(obj) {
  if (obj === null || obj === undefined) return "";
  if (Array.isArray(obj)) return renderValue(obj);
  if (typeof obj !== "object") return esc(String(obj));
  const rows = Object.entries(obj).filter(([, v]) => v !== null && v !== undefined && v !== "" && !(Array.isArray(v) && !v.length));
  if (!rows.length) return `<span class="text-3">No details</span>`;
  return `<dl class="kvlist">${rows
    .map(([k, v]) => {
      if (v && typeof v === "object" && !Array.isArray(v)) return `<div class="sub"><h4>${esc(label(k))}</h4>${renderData(v)}</div>`;
      if (Array.isArray(v) && v.every((x) => x && typeof x === "object")) {
        return `<div class="sub"><h4>${esc(label(k))}</h4>${v.map((x) => `<div class="mb-3">${renderData(x)}</div>`).join("")}</div>`;
      }
      return `<dt>${esc(label(k))}</dt><dd>${renderValue(v)}</dd>`;
    })
    .join("")}</dl>`;
}

function scoreRing(score, pass) {
  const s = Math.max(0, Math.min(100, Number(score) || 0));
  const r = 30;
  const c = 2 * Math.PI * r;
  const color = pass ? "var(--success)" : s >= 60 ? "var(--warning)" : "var(--danger)";
  return `<div class="score">
    <svg viewBox="0 0 72 72" aria-hidden="true">
      <circle cx="36" cy="36" r="${r}" fill="none" stroke="var(--border)" stroke-width="6"/>
      <circle cx="36" cy="36" r="${r}" fill="none" stroke="${color}" stroke-width="6" stroke-linecap="round" stroke-dasharray="${c.toFixed(2)}" stroke-dashoffset="${(c * (1 - s / 100)).toFixed(2)}" transform="rotate(-90 36 36)"/>
      <text x="36" y="41" text-anchor="middle" font-size="16" font-weight="700" fill="currentColor">${Math.round(s)}</text>
    </svg>
    <div><div class="num">${Math.round(s)}<small> / 100</small></div><div class="text-xs text-3">${pass ? "Passed the quality bar (80 or more)" : "Below the quality bar (80): the Design Agent reworks it"}</div></div>
  </div>`;
}

function chipsFor(d = {}) {
  const parts = [];
  if (d.duration_ms) parts.push(`${icon("clock", "icon-sm")} ${fmtDuration(d.duration_ms)}`);
  if (d.tokens_in || d.tokens_out) parts.push(`${icon("hash", "icon-sm")} ${d.tokens_in || 0} in · ${d.tokens_out || 0} out`);
  if (d.model) parts.push(`${icon("bot", "icon-sm")} ${esc(d.model)}`);
  return parts.length ? `<div class="ev-chips">${parts.map((p) => `<span class="chip">${p}</span>`).join("")}</div>` : "";
}

function downloadList(links) {
  if (!links || !links.length) return "";
  return `<div class="deliver-list">${links
    .map((l) => `<button type="button" data-download="${Number(l.file_id) || ""}" data-name="${esc(l.name || "file")}">${icon("download", "icon-sm")}<span class="truncate">${esc(l.name || "file")}</span></button>`)
    .join("")}</div>`;
}

function approvalButtons() {
  if (!canAct() || !state.req || state.req.status !== "review") return "";
  return `<div class="ev-actions"><button class="btn btn-success-soft" data-approve>${icon("send", "icon-sm")} Approve &amp; deliver</button><button class="btn btn-secondary" data-rework>${icon("repeat", "icon-sm")} Send back with a note</button></div>`;
}

/* ---------- derived state ---------- */
/** The agent that is working right now: last agent_started without a closing event. */
function currentAgent() {
  const open = new Map();
  for (const e of state.events) {
    if (e.type === "agent_started") open.set(e.agent_key, e);
    else if (CLOSERS.has(e.type)) open.delete(e.agent_key);
    else if (e.type === "completed" || e.type === "failed" || e.type === "stopped") open.clear();
  }
  if (!open.size) return null;
  const e = [...open.values()].pop();
  const ag = state.agents[e.agent_key];
  const ageMin = (Date.now() - new Date(e.created_at).getTime()) / 60000;
  if (ag && ag.status !== "running" && ageMin > 15) return null; // stale start without a finish (e.g. the server restarted)
  return { key: e.agent_key, since: e.created_at, activity: e.title };
}

function bestScore() {
  const scores = (state.req?.designs || []).map((d) => d.qa_score).filter((s) => s !== null && s !== undefined);
  return scores.length ? Math.round(Math.max(...scores)) : null;
}

function steps(r) {
  return [
    { key: "request", label: "Request", icon: "inbox" },
    ...(r.revision_count ? [{ key: "revision", label: "Revision", icon: "repeat" }] : []),
    { key: "project_manager", label: "Project Manager", icon: "briefcase" },
    { key: "strategy", label: "Strategy", icon: "target" },
    { key: "content", label: "Content", icon: "type" },
    { key: "design", label: "Design", icon: "palette" },
    { key: "qa", label: "QA", icon: "shield" },
    { key: "admin_approval", label: "Your approval", icon: "user", human: true },
    { key: "delivery", label: "Delivery", icon: "send" },
    { key: "complete", label: "Complete", icon: "check-circle" },
  ];
}

function activeStepKey(r) {
  if (r.status === "completed") return "complete";
  if (r.status === "pending" || r.status === "rejected") return "request";
  const run = currentAgent();
  if (run && AGENTS[run.key]) return run.key === "revision" && !r.revision_count ? "project_manager" : run.key;
  const st = r.pipeline_stage;
  if (!st) return "request";
  if (st === "approved") return "delivery";
  if (st === "rework") return "design";
  if (st === "error" || st === "stopped") {
    const last = [...state.events].reverse().find((e) => e.agent_key && AGENTS[e.agent_key]);
    return last ? last.agent_key : "project_manager";
  }
  return st;
}

function stageLabel(r) {
  if (r.status === "completed") return "Completed";
  if (r.status === "rejected") return "Rejected";
  if (r.status === "pending") return "Waiting for Accept";
  const run = currentAgent();
  if (run) return agentMeta(run.key).name.replace(" Agent", "");
  const map = {
    project_manager: "Project Manager", strategy: "Strategy", content: "Content", design: "Design", qa: "QA", revision: "Revision",
    admin_approval: "Your approval", approved: "Approved · Delivery next", rework: "Rework · Design next", delivery: "Delivery", error: "Error", stopped: "Stopped",
  };
  if (!r.pipeline_stage) return r.status === "accepted" ? "Queued for the agents" : "Manual work";
  return map[r.pipeline_stage] || titleCase(r.pipeline_stage);
}

function idleText(r) {
  const st = r.pipeline_stage;
  if (r.status === "pending") return "<b>Waiting for you to accept the request.</b><br>Accepting starts the agents automatically.";
  if (r.status === "rejected") return "<b>This request was rejected.</b>";
  if (r.status === "accepted") return "<b>Accepted.</b><br>The Project Manager Agent starts in a moment.";
  if (st === "approved") return "<b>Approved.</b><br>The Delivery Agent is about to package the files.";
  if (st === "rework") return "<b>Sent back.</b><br>The Design Agent is about to rework the draft.";
  if (st === "error") return "<b>The pipeline stopped with an error.</b><br>Check the feed below, fix the cause, then press Run pipeline.";
  if (st === "stopped") return "<b>Pipeline stopped by admin.</b><br>Start the agent in the Control Center, then press Run pipeline.";
  return "<b>No agent is running right now.</b><br>Press Run pipeline to start the agents, or work on it manually in the dashboard.";
}

/* ---------- renderers ---------- */
function renderTop() {
  const r = state.req;
  qs("#top-title").innerHTML = r ? `#${r.id} · ${esc(r.title)} <span class="text-4">·</span> ${esc(r.company_name)}` : "";
  document.title = r ? `Live · ${r.title} — Designflow` : "Live — Designflow";
  const run = currentAgent();
  qs("#live-pill").classList.toggle("idle", !run && r?.status !== "review");
  qs("#top-actions").innerHTML = topActions();
}

function topActions() {
  const r = state.req;
  if (!r) return "";
  const out = [];
  if (canAct()) {
    if (r.status === "pending") out.push(`<button class="btn btn-success-soft btn-sm" data-accept>${icon("check", "icon-sm")} Accept &amp; start agents</button>`);
    else if (r.status === "review") {
      out.push(`<button class="btn btn-success-soft btn-sm" data-approve>${icon("send", "icon-sm")} Approve &amp; deliver</button>`);
      out.push(`<button class="btn btn-secondary btn-sm" data-rework>${icon("repeat", "icon-sm")} Send back</button>`);
    } else if ((r.status === "accepted" || r.status === "in_progress") && !currentAgent()) {
      out.push(`<button class="btn btn-secondary btn-sm" data-run>${icon("cpu", "icon-sm")} Run pipeline</button>`);
    }
  }
  const back = state.user?.role === "client" ? `/portal#/requests/${r.id}` : `/admin#/requests/${r.id}`;
  out.push(`<a class="btn btn-ghost btn-sm" href="${back}" target="_blank" rel="noopener">${icon("external", "icon-sm")} Open request</a>`);
  return out.join("");
}

function renderHero() {
  const r = state.req;
  const run = currentAgent();
  const llm = state.llm || {};
  const model = llm.provider === "mock" || !llm.provider ? "built-in placeholder model" : `${llm.provider} · ${llm.model}`;
  const score = bestScore();
  qs("#hero").innerHTML = `<div class="card-body">
    <div class="hero-main">
      <div class="eyebrow">${esc(r.service_name)} · request #${r.id}</div>
      <h1>${esc(r.title)}</h1>
      <div class="flex gap-2 wrap">${statusBadge(r.status)}${priorityBadge(r.priority)}${r.is_paid ? '<span class="badge badge-success">paid</span>' : '<span class="badge badge-warning">unpaid</span>'}${r.revision_count ? `<span class="badge">${icon("repeat", "icon-sm")} revision ${r.revision_count}</span>` : ""}</div>
      <div class="meta">
        <span>${icon("users")} ${esc(r.company_name)}${r.client_name && r.client_name !== r.company_name ? ` (${esc(r.client_name)})` : ""}</span>
        <span>${icon("clock")} Submitted ${fmtDateTime(r.submitted_at)}</span>
        ${r.accepted_at ? `<span>${icon("check")} Accepted ${fmtDateTime(r.accepted_at)}</span>` : ""}
        ${r.completed_at ? `<span>${icon("check-circle")} Completed ${fmtDateTime(r.completed_at)}</span>` : ""}
        <span>${icon("bot")} Model: ${esc(model)}</span>
      </div>
    </div>
    <div class="hero-side">
      <div class="hero-stat"><div class="l">Stage</div><div class="v" title="${esc(stageLabel(r))}">${esc(stageLabel(r))}</div></div>
      <div class="hero-stat"><div class="l">Working now</div><div class="v">${run ? esc(agentMeta(run.key).name.replace(" Agent", "")) : r.status === "review" ? "You (approval)" : "—"}</div></div>
      <div class="hero-stat"><div class="l">Drafts</div><div class="v">${(r.designs || []).length}${score !== null ? `<span class="text-3" style="font-size:12px;font-weight:600"> · QA ${score}/100</span>` : ""}</div></div>
    </div>
  </div>`;
}

function renderSteps() {
  const r = state.req;
  const list = steps(r);
  const active = activeStepKey(r);
  let idx = list.findIndex((s) => s.key === active);
  if (idx < 0) idx = 0;
  const allDone = r.status === "completed";
  const errored = (r.pipeline_stage === "error" || r.pipeline_stage === "stopped") && !allDone && !currentAgent();
  qs("#steps").innerHTML = `<div class="stepper">${list
    .map((s, i) => {
      const cls = allDone || i < idx ? "done" : i === idx ? (errored ? "error" : "active") : "upcoming";
      const link = i ? `<span class="step-link ${allDone || i <= idx ? "done" : ""}"></span>` : "";
      const tint = AGENTS[s.key] ? ` style="--step-agent:${agentColor(s.key).main};--step-agent-deep:${agentColor(s.key).deep}"` : "";
      return `${link}<div class="step ${cls} ${s.human ? "human" : ""}"${tint}><span class="step-node"><span class="ico">${icon(cls === "done" ? "check" : s.icon)}</span>${esc(s.label)}</span></div>`;
    })
    .join("")}</div>`;
  // keep the active step in view when the stepper scrolls horizontally
  const scroller = qs("#steps");
  const activeEl = qs(".step.active, .step.error", scroller);
  if (activeEl && scroller.scrollWidth > scroller.clientWidth) {
    scroller.scrollLeft = Math.max(0, activeEl.offsetLeft - (scroller.clientWidth - activeEl.offsetWidth) / 2);
  }
}

function agentRows(run) {
  const r = state.req;
  return Object.keys(AGENTS)
    .filter((k) => k !== "revision" || r.revision_count)
    .map((k) => {
      const a = AGENTS[k];
      const ag = state.agents[k] || {};
      const isRun = Boolean(run && run.key === k);
      const done = state.events.filter((e) => e.type === "agent_completed" && e.agent_key === k).length;
      const status = isRun ? "running" : ["paused", "stopped", "error"].includes(ag.status) ? ag.status : done ? "done" : "waiting";
      const text = isRun ? (ag.status === "running" && ag.current_activity) || run.activity || "Working…" : status === "done" ? `Finished ${done} step${done > 1 ? "s" : ""}` : status === "waiting" ? "Waiting for its turn" : titleCase(status);
      const badge = isRun ? "badge-success" : status === "done" ? "badge-info" : status === "waiting" ? "" : "badge-warning";
      const c = agentColor(k);
      return `<div class="agent-row ${isRun ? "running" : ""} ${status}" style="--agent:${c.main};--agent-light:${c.light};--agent-deep:${c.deep}">
        <span class="agent-dot" aria-hidden="true"><i></i></span>
        <div class="min-w-0"><div class="n">${esc(a.name)}</div><div class="a" title="${esc(text)}">${esc(text)}</div></div><span class="badge ${badge}">${esc(status)}</span></div>`;
    })
    .join("");
}

/* ---------- the orb (one persistent canvas, recoloured per agent) ---------- */
let orbStage = null;
let orb = null;

function orbElement() {
  if (!orbStage) {
    orbStage = document.createElement("div");
    orbStage.className = "orb-stage";
    orbStage.innerHTML = `<canvas class="orb-canvas" aria-hidden="true"></canvas>
      <div class="orb-caption"><span class="orb-dot" aria-hidden="true"></span><div class="orb-text" role="status" aria-live="polite" aria-atomic="true"><div class="orb-name"></div><div class="orb-sub" data-activity></div></div><span class="orb-time" aria-hidden="true"></span></div>`;
    orb = new AgentOrb(qs("canvas", orbStage));
    window.dfOrb = { orb, update: updateOrb }; // handy in the browser console: dfOrb.update({key:"design", mode:"running", name:"Design Agent"})
  }
  return orbStage;
}

function updateOrb({ key, mode, name, sub, since }) {
  const el = orbElement();
  const c = agentColor(key);
  el.style.setProperty("--agent", c.main);
  el.style.setProperty("--agent-light", c.light);
  el.dataset.mode = mode;
  qs(".orb-name", el).textContent = name;
  qs(".orb-sub", el).textContent = sub || "";
  const time = qs(".orb-time", el);
  if (since) {
    time.classList.add("elapsed");
    time.dataset.start = since;
    time.textContent = elapsedLabel(since);
  } else {
    time.classList.remove("elapsed");
    delete time.dataset.start;
    time.textContent = "";
  }
  orb.set(key, mode);
}

function renderNow() {
  const r = state.req;
  const run = currentAgent();
  let header;
  let body;
  if (run) {
    const a = agentMeta(run.key);
    const st = state.stream && state.stream.agent_key === run.key ? state.stream : null;
    const ag = state.agents[run.key];
    const activity = ag && ag.status === "running" && ag.current_activity ? ag.current_activity : run.activity;
    updateOrb({ key: run.key, mode: "running", name: a.name, sub: activity, since: run.since });
    header = `<span class="badge badge-success">${icon("activity", "icon-sm")} running</span>`;
    body = `<div class="stream-head" id="stream-head">${streamHead(st)}</div>
      <div class="stream-box" id="stream-box">${st ? esc(st.text) : "Preparing the brief and brand context for the model…"}${st && !st.done ? '<span class="caret"></span>' : ""}</div>`;
  } else if ((r.status === "in_progress" || r.status === "accepted") && !["error", "stopped"].includes(r.pipeline_stage || "")) {
    // the pipeline is alive but between two agents (or just accepted): keep the next agent's colour, never "No agent running"
    const st_ = r.pipeline_stage || "";
    const nextKey = AGENTS[st_] ? st_ : st_ === "rework" ? "design" : st_ === "approved" ? "delivery" : "project_manager";
    const a = agentMeta(nextKey);
    updateOrb({ key: nextKey, mode: "waiting", name: a.name, sub: r.status === "accepted" ? "Starting in a moment…" : "Handing over…" });
    header = `<span class="badge badge-info">${icon("activity", "icon-sm")} ${r.status === "accepted" ? "starting" : "handing over"}</span>`;
    body = `<div class="now-note">${esc(a.name)} is up next. The orb lights up the moment it starts working.</div>`;
  } else if (r.status === "review") {
    updateOrb({ key: "approval", mode: "waiting", name: "Your approval", sub: "The agents finished a draft" });
    header = `<span class="badge badge-warning">your turn</span>`;
    body = `<div class="now-note">Approve to deliver it to the client, or send it back with a note.</div>${approvalButtons()}`;
  } else if (r.status === "completed") {
    updateOrb({ key: "done", mode: "done", name: "All done", sub: "Delivered to the client" });
    header = `<span class="badge badge-success">done</span>`;
    body = `<div class="now-note">The client has been notified and can download everything from Your designs.</div>`;
  } else {
    updateOrb({ key: "idle", mode: "idle", name: "No agent running", sub: stageLabel(r) });
    header = `<span class="badge">idle</span>`;
    body = `<div class="now-note">${idleText(r)}</div>`;
  }
  qs("#now").innerHTML = `<div class="card now-card"><div class="card-header"><h3>Working now</h3>${header}</div><div data-orb-slot></div><div class="card-body">${body}</div></div>
    <div class="card"><div class="card-header"><h3>Agents on this request</h3><span class="text-xs text-3">${Object.keys(AGENTS).filter((k) => k !== "revision" || r.revision_count).length} agents</span></div><div class="card-body"><div class="agent-list" id="agent-list">${agentRows(run)}</div></div></div>`;
  qs("[data-orb-slot]").replaceWith(orbElement());
}

function streamHead(st) {
  const left = st && !st.done ? "Writing…" : st ? "Finished writing" : "Thinking…";
  const right = st ? `${(st.chars || st.text.length).toLocaleString()} characters${st.model ? ` · ${esc(st.model)}` : ""}` : "";
  return `<span>${left}</span><b>${right}</b>`;
}

function eventCard(e) {
  const a = agentMeta(e.agent_key);
  const who = e.agent_key ? a.name : "Pipeline";
  const compact = e.type === "agent_started" || e.type === "agent_skipped";
  let title = e.title || label(e.type);
  let body = "";
  const d = e.data || {};
  switch (e.type) {
    case "agent_started":
      title = `Started: ${e.title}`;
      break;
    case "agent_completed": {
      title = `Finished: ${e.title}`;
      const data = parseJson(e.body);
      body = (data ? renderData(data) : e.body ? `<p>${nl2br(e.body)}</p>` : "") + chipsFor(d);
      if (data) body += `<button type="button" class="raw-toggle" data-raw>Show raw model output</button><pre class="raw hidden">${esc(e.body)}</pre>`;
      break;
    }
    case "design_rendered": {
      const imgs = (d.files || []).filter((f) => f.format === "png" && f.role !== "board");
      const docs = (d.files || []).filter((f) => f.format === "pdf" || f.format === "zip");
      body = (d.file_id ? `<figure class="ev-figure"><img src="${fileUrl(d.file_id)}" alt="Draft v${d.version}" loading="lazy"></figure>` : "") +
        (imgs.length
          ? `<div class="ev-thumbs">${imgs.slice(0, 12).map((f) => `<button type="button" class="ev-thumb" data-open-file="${f.file_id}" title="${esc(f.label || f.name)}"><img src="${fileUrl(f.thumb_file_id || f.file_id)}" alt="" loading="lazy"></button>`).join("")}${imgs.length > 12 ? `<span class="ev-more">+${imgs.length - 12} more</span>` : ""}</div>`
          : "") +
        (docs.length ? `<div class="ev-chips">${docs.map((f) => `<button type="button" class="chip chip-brand" data-download="${f.file_id}" data-name="${esc(f.name)}">${icon("download", "icon-sm")} ${esc(f.label || f.name)}</button>`).join("")}</div>` : "") +
        renderData({ delivered: e.body, palette: d.palette, typefaces: d.typography, direction: d.title, rationale: d.rationale }) +
        (Array.isArray(d.concepts) && d.concepts.length > 1
          ? `<div class="ev-chips">${d.concepts.map((c, i) => `<span class="chip ${i === d.recommended ? "chip-brand" : ""}">${i === d.recommended ? icon("star", "icon-sm") : ""}${esc(c.title || `Concept ${i + 1}`)}</span>`).join("")}</div>`
          : "") +
        `<div class="ev-actions"><button type="button" class="btn btn-secondary btn-sm" data-show-version="${d.version}">${icon("eye", "icon-sm")} Show in preview</button></div>`;
      break;
    }
    case "qa_scored":
      body = scoreRing(d.score, d.pass) + (e.body ? `<p class="mb-3">${nl2br(e.body)}</p>` : "") + renderData({ strengths: d.strengths, issues: d.issues, suggestions: d.suggestions });
      break;
    case "awaiting_approval":
      body = `<p>${nl2br(e.body || "")}</p>${approvalButtons()}`;
      break;
    case "delivered":
      body = `<p>${nl2br(e.body || "")}</p>${downloadList(d.links)}`;
      break;
    default:
      body = e.body ? `<p>${nl2br(e.body)}</p>` : "";
  }
  return `<article class="ev ev-${esc(e.type)} lvl-${esc(e.level || "info")} ${compact ? "compact" : ""}" data-ev="${e.id}">
    <div class="ev-rail">${avatar(e.agent_key, "sm")}</div>
    <div class="ev-main">
      <header class="ev-head"><span class="who">${esc(who)}</span><span class="title">${esc(title)}</span><time datetime="${esc(e.created_at || "")}" title="${esc(fmtDateTime(e.created_at))}">${fmtTime(e.created_at)}</time></header>
      ${body ? `<div class="ev-body">${body}</div>` : ""}
    </div>
  </article>`;
}

function renderFeed() {
  const feed = qs("#feed");
  feed.innerHTML = state.events.length ? state.events.map(eventCard).join("") : `<div class="live-empty">Nothing has happened yet. Events appear here the moment an agent starts.</div>`;
  qs("#feed-count").textContent = state.events.length ? `${state.events.length} event${state.events.length === 1 ? "" : "s"}` : "";
  followScroll(true);
}

function appendEvent(e) {
  const feed = qs("#feed");
  const empty = qs(".live-empty", feed);
  if (empty) empty.remove();
  feed.insertAdjacentHTML("beforeend", eventCard(e));
  qs("#feed-count").textContent = `${state.events.length} event${state.events.length === 1 ? "" : "s"}`;
  followScroll();
}

function followScroll(force = false) {
  const feed = qs("#feed");
  if (force || qs("#follow").checked) feed.scrollTop = feed.scrollHeight;
}

function renderPreview() {
  const r = state.req;
  const designs = (r.designs || []).slice().sort((x, y) => x.version - y.version);
  const run = currentAgent();
  const building = Boolean(run && run.key === "design");
  const sel = designs.find((d) => d.version === state.selectedVersion) || designs[designs.length - 1] || null;
  if (sel) state.selectedVersion = sel.version;
  const frame = sel && sel.file_id ? `<img src="${fileUrl(sel.file_id)}" alt="Draft v${sel.version}">` : sel && sel.preview_url ? `<img src="${esc(sel.preview_url)}" alt="">` : building ? "" : `<span>No draft yet.<br>The Design Agent renders one after Strategy and Content.</span>`;
  const delivery = (r.deliveries || []).slice(-1)[0];
  const selFiles = sel && sel.files ? sel.files : [];
  const selImgs = selFiles.filter((f) => f.format === "png" && f.role !== "board");
  const selPkg = selFiles.find((f) => f.role === "package");
  qs("#preview").innerHTML = `<div class="card preview-card">
    <div class="card-header"><h3>Design preview</h3>${sel ? `<span class="badge ${sel.status === "approved" ? "badge-success" : "badge-cyan"}">${esc(sel.status)}</span>` : ""}</div>
    <div class="card-body">
      <div class="preview-frame">${frame}${building ? `<div class="building">Design Agent is building draft v${designs.length + 1}…</div>` : ""}</div>
      ${designs.length > 1 ? `<div class="version-tabs">${designs.map((d) => `<button type="button" class="${d.version === sel.version ? "active" : ""}" data-version="${d.version}">v${d.version}${d.qa_score !== null && d.qa_score !== undefined ? ` · QA ${Math.round(d.qa_score)}` : ""}</button>`).join("")}</div>` : ""}
      ${selImgs.length ? `<div class="preview-grid">${selImgs.slice(0, 18).map((f) => `<button type="button" class="ev-thumb" data-open-file="${f.file_id}" title="${esc(f.label || f.name)}"><img src="${fileUrl(f.thumb_file_id || f.file_id)}" alt="" loading="lazy"></button>`).join("")}</div>
        <div class="text-xs text-3">${selImgs.length} image${selImgs.length === 1 ? "" : "s"} in this version${selFiles.some((f) => f.format === "pdf") ? " · PDF included" : ""}</div>` : ""}
      ${selPkg ? `<button type="button" class="btn btn-secondary btn-sm" data-download="${selPkg.file_id}" data-name="${esc(selPkg.name)}">${icon("download", "icon-sm")} Download v${sel.version} (ZIP)</button>` : ""}
      ${sel ? `<div class="preview-meta"><div class="hero-stat"><div class="l">Draft</div><div class="v" title="${esc(sel.title || "Concept")}">v${sel.version} · ${esc(sel.title || "Concept")}</div></div><div class="hero-stat"><div class="l">QA score</div><div class="v">${sel.qa_score !== null && sel.qa_score !== undefined ? `${Math.round(sel.qa_score)} / 100` : "pending"}</div></div></div>` : ""}
      ${sel && sel.qa_notes ? `<div class="text-sm text-2"><b>QA notes:</b> ${nl2br(sel.qa_notes)}</div>` : ""}
      ${sel && sel.concept ? `<details><summary>Concept description</summary><div class="text-sm text-2 mt-2" style="white-space:pre-wrap">${esc(sel.concept)}</div></details>` : ""}
    </div>
  </div>
  ${delivery ? `<div class="card"><div class="card-header"><h3>Delivered to the client</h3><span class="badge badge-success">delivery ${delivery.version}</span></div><div class="card-body"><p class="text-sm text-2 mb-3" style="margin-top:0">${nl2br(delivery.message || "")}</p>${downloadList(delivery.download_links)}</div></div>` : ""}
  <div class="card"><div class="card-header"><h3>The brief the agents follow</h3></div><div class="card-body text-sm">${renderData(orderedBrief(r.brief))}</div></div>`;
}

function orderedBrief(brief) {
  if (!brief || typeof brief !== "object") return {};
  const out = {};
  if (brief.about_and_wishes) out.about_and_wishes = brief.about_and_wishes;
  Object.entries(brief).forEach(([k, v]) => {
    if (k !== "about_and_wishes") out[k] = v;
  });
  return out;
}

function logRow(l) {
  const st = l.status || "";
  return `<tr><td>${fmtTime(l.created_at)}</td><td class="k">${esc(agentMeta(l.agent_key).name.replace(" Agent", ""))}</td><td class="s s-${esc(st)}">${esc(st)}</td><td>${esc(l.message || "")}${l.duration_ms ? ` <span class="text-4">· ${fmtDuration(l.duration_ms)}</span>` : ""}${l.tokens_in || l.tokens_out ? ` <span class="text-4">· ${l.tokens_in || 0}/${l.tokens_out || 0} tokens</span>` : ""}</td></tr>`;
}

function renderLogs() {
  qs("#logs").innerHTML = `<details class="live-logs-details"><summary>${icon("list")} Raw agent log <span class="text-3" id="log-count">(${state.logs.length})</span></summary><div class="table-wrap"><table class="log-table"><tbody id="log-body">${state.logs.map(logRow).join("")}</tbody></table></div></details>`;
}

function appendLog(l) {
  const body = qs("#log-body");
  if (!body) return renderLogs();
  body.insertAdjacentHTML("beforeend", logRow(l));
  const c = qs("#log-count");
  if (c) c.textContent = `(${state.logs.length})`;
}

function renderAll() {
  renderTop();
  renderHero();
  renderSteps();
  renderNow();
  renderFeed();
  renderPreview();
  renderLogs();
}

function renderDerived() {
  renderTop();
  renderHero();
  renderSteps();
  renderNow();
  renderPreview();
}

/* ---------- data ---------- */
function addEvent(e) {
  if (!e || e.id === null || e.id === undefined || state.seen.has(e.id)) return false;
  state.seen.add(e.id);
  state.events.push(e);
  state.lastEventId = Math.max(state.lastEventId, Number(e.id) || 0);
  return true;
}

async function loadAll() {
  const data = await api.get(`/requests/${REQUEST_ID}/live`);
  state.req = data.request;
  state.llm = data.llm;
  state.logs = data.logs || [];
  (data.agents || []).forEach((a) => (state.agents[a.key] = a));
  state.events = [];
  state.seen = new Set();
  (data.events || []).forEach(addEvent);
  renderAll();
}

async function refreshRequest() {
  try {
    state.req = await api.get(`/requests/${REQUEST_ID}`);
    renderDerived();
  } catch (err) {
    console.warn("refresh failed", err);
  }
}
const refreshSoon = debounce(refreshRequest, 350);

/* ---------- actions ---------- */
function openImage(fileId) {
  const all = qsa("[data-open-file]").map((el) => Number(el.dataset.openFile));
  const ids = [...new Set(all)];
  let i = Math.max(0, ids.indexOf(fileId));
  const wrap = document.createElement("div");
  wrap.className = "live-lightbox";
  const draw = () => {
    wrap.innerHTML = `<button type="button" class="lb-close" aria-label="Close">${icon("x")}</button>
      ${ids.length > 1 ? `<button type="button" class="lb-nav lb-prev" aria-label="Previous">${icon("chevron-left")}</button><button type="button" class="lb-nav lb-next" aria-label="Next">${icon("chevron-right")}</button>` : ""}
      <img src="${fileUrl(ids[i])}" alt=""><div class="lb-count">${i + 1} / ${ids.length}</div>`;
  };
  draw();
  const close = () => {
    wrap.remove();
    document.removeEventListener("keydown", onKey);
  };
  const onKey = (ev) => {
    if (ev.key === "Escape") close();
    if (ev.key === "ArrowRight") { i = (i + 1) % ids.length; draw(); }
    if (ev.key === "ArrowLeft") { i = (i - 1 + ids.length) % ids.length; draw(); }
  };
  wrap.addEventListener("click", (ev) => {
    if (ev.target.closest(".lb-close") || ev.target === wrap) return close();
    if (ev.target.closest(".lb-next")) { i = (i + 1) % ids.length; draw(); }
    if (ev.target.closest(".lb-prev")) { i = (i - 1 + ids.length) % ids.length; draw(); }
  });
  document.addEventListener("keydown", onKey);
  document.body.appendChild(wrap);
}

document.addEventListener("click", async (e) => {
  const opener = e.target.closest("[data-open-file]");
  if (opener) {
    openImage(Number(opener.dataset.openFile));
    return;
  }
  const t = e.target.closest("[data-approve],[data-rework],[data-run],[data-accept],[data-download],[data-show-version],[data-version],[data-raw]");
  if (!t) return;
  if (t.hasAttribute("data-raw")) {
    const pre = t.nextElementSibling;
    if (!pre) return;
    pre.classList.toggle("hidden");
    t.textContent = pre.classList.contains("hidden") ? "Show raw model output" : "Hide raw model output";
    return;
  }
  if (t.dataset.showVersion || t.dataset.version) {
    state.selectedVersion = Number(t.dataset.showVersion || t.dataset.version);
    renderPreview();
    if (t.dataset.showVersion) qs("#preview").scrollIntoView({ behavior: "smooth", block: "start" });
    return;
  }
  if (t.dataset.download) {
    try {
      await downloadFile(Number(t.dataset.download), t.dataset.name || "file");
    } catch (err) {
      toast({ title: "Download failed", body: errorMessage(err), type: "error" });
    }
    return;
  }
  if (!canAct()) return;
  try {
    if (t.hasAttribute("data-approve")) {
      const note = await promptDialog({ title: "Approve & deliver", label: "Note to the client (optional)", placeholder: "Anything the Delivery Agent should mention", multiline: true, confirmText: "Approve & deliver" });
      if (note === null) return;
      await api.post(`/requests/${REQUEST_ID}/approve`, null, { message: note || undefined });
      toast({ title: "Approved", body: "The Delivery Agent is packaging the files.", type: "success" });
    } else if (t.hasAttribute("data-rework")) {
      const note = await promptDialog({ title: "Send back for rework", label: "What should the Design Agent change?", placeholder: "e.g. warmer palette, bigger headline, less text", multiline: true, confirmText: "Send back" });
      if (note === null) return;
      if (!note.trim()) {
        toast({ title: "Please write a note for the Design Agent", type: "info" });
        return;
      }
      await api.post(`/requests/${REQUEST_ID}/rework`, null, { message: note.trim() });
      toast({ title: "Sent back", body: "The Design Agent is reworking the draft.", type: "info" });
    } else if (t.hasAttribute("data-run")) {
      const ok = await confirmDialog({ title: "Run the agent pipeline?", body: "Project Manager → Strategy → Content → Design → QA, then your approval.", confirmText: "Run" });
      if (!ok) return;
      await api.post(`/requests/${REQUEST_ID}/run-pipeline`);
      toast({ title: "Pipeline queued", type: "success" });
    } else if (t.hasAttribute("data-accept")) {
      await api.post(`/requests/${REQUEST_ID}/accept`);
      toast({ title: "Accepted", body: "The agents start now.", type: "success" });
    }
    refreshSoon();
  } catch (err) {
    toast({ title: "Action failed", body: errorMessage(err), type: "error" });
  }
});

/* ---------- real-time ---------- */
ws.on("status", ({ status }) => {
  const el = qs("#ws-indicator");
  el.classList.toggle("offline", status === "closed");
  el.classList.toggle("connecting", status === "connecting");
  qs(".ws-label", el).textContent = status === "open" ? "Live" : status === "connecting" ? "Connecting…" : "Reconnecting…";
});

ws.on("pipeline_event", (p) => {
  if (Number(p.request_id) !== REQUEST_ID || !addEvent(p)) return;
  appendEvent(p);
  if (p.type === "agent_started") state.stream = null;
  if (REFRESH_ON.has(p.type)) refreshSoon();
  renderDerived();
  if (p.type === "awaiting_approval") toast({ title: "Draft ready for your approval", body: "Review the preview, then approve or send it back.", type: "info", timeout: 8000 });
  if (p.type === "completed") toast({ title: "Request completed", body: "Files delivered to the client.", type: "success" });
  if (p.type === "failed" || p.type === "agent_failed") toast({ title: "Pipeline error", body: p.body || p.title, type: "error", timeout: 8000 });
});

ws.on("agent_stream", (p) => {
  if (Number(p.request_id) !== REQUEST_ID) return;
  state.stream = p;
  const run = currentAgent();
  const box = qs("#stream-box");
  if (box && run && run.key === p.agent_key) {
    box.innerHTML = esc(p.text || "") + (p.done ? "" : '<span class="caret"></span>');
    box.scrollTop = box.scrollHeight;
    const head = qs("#stream-head");
    if (head) head.innerHTML = streamHead(p);
  } else {
    renderNow();
  }
});

ws.on("agent_status", (p) => {
  const a = p.agent;
  if (!a || !AGENTS[a.key]) return;
  state.agents[a.key] = a;
  const run = currentAgent();
  const act = qs(".orb-stage [data-activity]");
  if (act && run && run.key === a.key && a.status === "running" && a.current_activity) act.textContent = a.current_activity;
  const list = qs("#agent-list");
  if (list) list.innerHTML = agentRows(run);
  else renderNow();
});

ws.on("agent_log", (p) => {
  if (Number(p.request_id) !== REQUEST_ID) return;
  state.logs.push(p);
  appendLog(p);
});

ws.on("request_update", (p) => {
  if (Number(p.request_id) === REQUEST_ID) refreshSoon();
});

/* ---------- boot ---------- */
(async function boot() {
  if (!REQUEST_ID) {
    qs("#hero").innerHTML = `<div class="card-body"><b>No request selected.</b> Open this page from a request's "See in live" button.</div>`;
    return;
  }
  state.user = await requireAuth(["admin", "staff", "client"]);
  if (!state.user) return;
  try {
    await loadAll();
  } catch (err) {
    qs("#hero").innerHTML = `<div class="card-body"><b>Could not load request #${REQUEST_ID}.</b> ${esc(errorMessage(err))}</div>`;
    return;
  }
  ws.connect();
  setInterval(() => qsa(".elapsed[data-start]").forEach((el) => (el.textContent = elapsedLabel(el.dataset.start))), 1000);
  // Safety net when the socket is down: pick up anything new every 15 seconds.
  setInterval(async () => {
    if (ws.status() === "open") return;
    try {
      const d = await api.get(`/requests/${REQUEST_ID}/live`, { since_id: state.lastEventId });
      const fresh = (d.events || []).filter(addEvent);
      if (fresh.length) {
        fresh.forEach(appendEvent);
        state.req = d.request;
        renderDerived();
      }
    } catch {}
  }, 15000);
})();
