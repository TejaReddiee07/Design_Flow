/* AI Agent Control Center */
import { api, errorMessage } from "../core/api.js";
import { esc, icon, qs, qsa, h, toast, modal, drawer, confirmDialog, promptDialog, setLoading, timeAgo, fmtNum, agentBadge, titleCase } from "../core/ui.js";
import { pageHeader, loadingBlock, errorBlock, logLine, pct, emptyState } from "./shared.js";

const AGENT_ICONS = { lead: "target", outreach: "mail", onboarding: "rocket", project_manager: "kanban", strategy: "globe", content: "type", design: "palette", revision: "repeat", qa: "shield", delivery: "send", marketing: "sparkles" };
const PIPELINE_AGENTS = new Set(["project_manager", "strategy", "content", "design", "qa", "delivery", "revision"]);
const SCHEDULED = new Set(["lead", "outreach", "marketing"]);
const PIPELINE = [
  ["Request", "inbox", null], ["Project Manager", "kanban", "project_manager"], ["Strategy", "globe", "strategy"], ["Content", "type", "content"], ["Design", "palette", "design"],
  ["QA", "shield", "qa"], ["Admin approval", "user", "human"], ["Delivery", "send", "delivery"], ["Revision", "repeat", "revision"], ["Complete", "check-circle", null],
];

export async function render(page) {
  let agents = [];
  let logs = [];
  page.innerHTML = pageHeader("AI Agent Control Center", "Eleven agents, one pipeline. Start, pause, stop or restart any of them.", `<button class="btn btn-secondary" id="refresh">${icon("refresh")} Refresh</button>`) +
    `<div class="kpi-grid" id="summary">${loadingBlock(5)}</div>
     <div class="agent-grid mt-6" id="grid">${loadingBlock(6)}</div>
     <div class="card mt-6"><div class="card-header"><h3>Request pipeline</h3><span class="text-xs text-3">Nodes light up while an agent is running</span></div><div class="pipeline-strip" id="pipeline"></div></div>
     <div class="card mt-6"><div class="card-header"><h3>Live activity log</h3><div class="flex gap-2"><span class="ws-indicator"><span class="live-dot"></span>streaming</span><button class="btn btn-ghost btn-sm" id="clear-log">Clear</button></div></div><div class="log-stream" id="log-stream">${loadingBlock(3)}</div></div>`;

  function summary() {
    const running = agents.filter((a) => a.status === "running").length;
    const paused = agents.filter((a) => a.status === "paused").length;
    const stopped = agents.filter((a) => a.status === "stopped").length;
    const errors = agents.filter((a) => a.status === "error").length;
    const done = agents.reduce((s, a) => s + a.tasks_completed, 0);
    const failed = agents.reduce((s, a) => s + a.tasks_failed, 0);
    qs("#summary", page).innerHTML = `
      <div class="stat"><div class="stat-label"><span class="stat-icon">${icon("play", "icon-sm")}</span>Running</div><div class="stat-value">${running}<small>/ ${agents.length}</small></div></div>
      <div class="stat"><div class="stat-label"><span class="stat-icon">${icon("pause", "icon-sm")}</span>Paused</div><div class="stat-value">${paused}</div></div>
      <div class="stat"><div class="stat-label"><span class="stat-icon">${icon("stop", "icon-sm")}</span>Stopped</div><div class="stat-value">${stopped}</div>${errors ? `<div class="stat-delta down">${errors} in error</div>` : ""}</div>
      <div class="stat"><div class="stat-label"><span class="stat-icon">${icon("check-circle", "icon-sm")}</span>Tasks completed</div><div class="stat-value">${fmtNum(done)}</div><div class="stat-delta">${fmtNum(failed)} failed</div></div>
      <div class="stat"><div class="stat-label"><span class="stat-icon">${icon("award", "icon-sm")}</span>Success rate</div><div class="stat-value">${pct(done + failed ? (100 * done) / (done + failed) : 100)}</div></div>`;
  }

  function agentCard(a) {
    const canStart = a.status === "stopped" || a.status === "paused" || a.status === "error" || !a.enabled;
    return `<div class="card agent-card" data-status="${esc(a.status)}" data-agent="${esc(a.key)}">
      <div class="agent-status-bar"></div>
      <div class="card-body">
        <div class="agent-head"><span class="agent-ico">${icon(AGENT_ICONS[a.key] || "cpu")}</span><div class="flex-1 min-w-0"><div class="flex items-center justify-between gap-2"><b>${esc(a.name)}</b>${agentBadge(a.status)}</div><div class="agent-desc">${esc(a.description || "")}</div></div></div>
        <div class="agent-metrics">
          <div class="agent-metric"><div class="l">Completed</div><div class="v">${fmtNum(a.tasks_completed)}</div></div>
          <div class="agent-metric"><div class="l">Failed</div><div class="v">${fmtNum(a.tasks_failed)}</div></div>
          <div class="agent-metric"><div class="l">Last run</div><div class="v" style="font-size:var(--fs-sm)">${a.last_run_at ? timeAgo(a.last_run_at) : "never"}</div></div>
        </div>
        <div class="mt-3"><div class="flex justify-between text-xs text-3 mb-1"><span>Success rate</span><b>${pct(a.success_rate)}</b></div><div class="progress"><span style="width:${Math.min(100, a.success_rate)}%"></span></div></div>
        <div class="agent-activity">${a.status === "running" ? '<span class="live-dot"></span>' : icon("clock", "icon-sm")}<span class="truncate">${esc(a.current_activity || "Idle")}</span></div>
        ${a.last_error ? `<div class="agent-error">${icon("alert", "icon-sm")} ${esc(a.last_error.slice(0, 160))}</div>` : ""}
        ${SCHEDULED.has(a.key) ? `<div class="text-xs text-3 mt-2 flex items-center gap-2">${icon("calendar", "icon-sm")} Schedule: <code>${esc(a.schedule || "none")}</code><button class="btn btn-ghost btn-sm" data-schedule="${a.key}">${icon("edit", "icon-sm")}</button></div>` : ""}
        <div class="agent-buttons">
          <button class="btn btn-sm btn-success-soft" data-cmd="start" data-key="${a.key}" ${canStart ? "" : "disabled"}>${icon("play", "icon-sm")} Start</button>
          <button class="btn btn-sm btn-warning-soft" data-cmd="pause" data-key="${a.key}" ${a.status === "paused" || a.status === "stopped" ? "disabled" : ""}>${icon("pause", "icon-sm")} Pause</button>
          <button class="btn btn-sm btn-danger-soft" data-cmd="stop" data-key="${a.key}" ${a.status === "stopped" ? "disabled" : ""}>${icon("stop", "icon-sm")} Stop</button>
          <button class="btn btn-sm btn-secondary" data-cmd="restart" data-key="${a.key}">${icon("refresh", "icon-sm")} Restart</button>
          <button class="btn btn-sm btn-primary" data-run="${a.key}" ${a.status === "stopped" || !a.enabled ? "disabled" : ""}>${icon("zap", "icon-sm")} Run now</button>
          <button class="btn btn-sm btn-ghost" data-logs="${a.key}">${icon("list", "icon-sm")} Logs</button>
        </div>
      </div>
    </div>`;
  }

  function drawGrid() {
    const grid = qs("#grid", page);
    grid.innerHTML = agents.map(agentCard).join("");
    summary();
    drawPipeline();
  }

  function patchAgent(a) {
    const idx = agents.findIndex((x) => x.key === a.key);
    if (idx >= 0) agents[idx] = { ...agents[idx], ...a };
    else agents.push(a);
    const el = qs(`[data-agent="${a.key}"]`, page);
    if (el) el.outerHTML = agentCard(agents[idx >= 0 ? idx : agents.length - 1]);
    summary();
    drawPipeline();
  }

  function drawPipeline() {
    const running = new Set(agents.filter((a) => a.status === "running").map((a) => a.key));
    qs("#pipeline", page).innerHTML = PIPELINE.map(([label, ic, key], i) => `${i ? '<span class="arrow">→</span>' : ""}<span class="node ${key === "human" ? "human" : ""} ${key && running.has(key) ? "running" : ""}">${icon(ic)}${esc(label)}</span>`).join("");
  }

  async function command(key, cmd) {
    if (cmd === "stop") {
      const ok = await confirmDialog({ title: `Stop ${titleCase(key)} Agent?`, body: "Running work is aborted at the next step and the agent stays off until you press Start.", confirmText: "Stop", danger: true });
      if (!ok) return;
    }
    try {
      const a = await api.post(`/agents/${key}/${cmd}`);
      patchAgent(a);
      toast({ title: `${a.name}: ${cmd}`, type: "success", timeout: 2000 });
    } catch (err) {
      toast({ title: "Command failed", body: errorMessage(err), type: "error" });
    }
  }

  async function runNow(key) {
    const a = agents.find((x) => x.key === key);
    let payload = {};
    if (PIPELINE_AGENTS.has(key)) {
      const rid = await promptDialog({ title: `Run ${a.name}`, label: "Request ID", placeholder: "e.g. 12", confirmText: "Run" });
      if (rid === null) return;
      if (!rid.trim()) return toast({ title: "Request ID required", type: "warning" });
      payload = { request_id: Number(rid) };
    } else if (key === "lead") {
      const services = await api.get("/services").catch(() => []);
      const body = h(`<div class="form-grid"><div class="field span-2"><label class="label">Service to sell</label><select class="select" id="r-svc"><option value="">Any (rotate services)</option>${services.map((s) => `<option value="${esc(s.slug)}">${esc(s.name)}</option>`).join("")}</select></div><div class="field"><label class="label">Industry</label><input class="input" id="r-ind" placeholder="optional"></div><div class="field"><label class="label">Location</label><input class="input" id="r-loc" placeholder="optional"></div><div class="field span-2"><label class="label">Count</label><input class="input" type="number" min="1" max="25" value="5" id="r-count"></div><p class="hint span-2">Searches the web for matching businesses, extracts contact emails and scores them.</p></div>`);
      const res = await new Promise((resolve) => {
        const footer = h(`<div class="flex gap-2 justify-end w-full"><button class="btn btn-secondary" data-close>Cancel</button><button class="btn btn-primary" id="r-ok">Run</button></div>`);
        const m = modal({ title: "Run Lead Agent", body, footer, onClose: () => resolve(null) });
        qs("#r-ok", footer).onclick = () => { resolve({ industry: qs("#r-ind", body).value || null, location: qs("#r-loc", body).value || null, count: Number(qs("#r-count", body).value) || 5, service_slug: qs("#r-svc", body).value || null }); m.el.remove(); };
      });
      if (!res) return;
      payload = res;
    } else if (key === "onboarding") {
      const cid = await promptDialog({ title: "Run Onboarding Agent", label: "Client ID", placeholder: "e.g. 3", confirmText: "Run" });
      if (cid === null) return;
      payload = { client_id: Number(cid) };
    } else {
      const ok = await confirmDialog({ title: `Run ${a.name} now?`, body: key === "outreach" ? "Processes pending follow-ups and approved drafts." : key === "marketing" ? "Generates a fresh batch of social posts." : "Queues a manual run.", confirmText: "Run" });
      if (!ok) return;
    }
    try {
      const res = await api.post(`/agents/${key}/run`, { payload });
      patchAgent(res);
      toast({ title: `${res.name} queued`, body: "Watch the live log for progress.", type: "success" });
    } catch (err) {
      toast({ title: "Run failed", body: errorMessage(err), type: "error" });
    }
  }

  async function editSchedule(key) {
    const a = agents.find((x) => x.key === key);
    const val = await promptDialog({ title: `Schedule for ${a.name}`, label: "Cron expression (UTC). Leave empty to disable.", placeholder: "0 9 * * *", value: a.schedule || "", confirmText: "Save" });
    if (val === null) return;
    try {
      const res = await api.patch(`/agents/${key}`, { schedule: val.trim() || null });
      patchAgent(res);
      toast({ title: "Schedule saved", body: "Applied within 10 minutes by the scheduler.", type: "success" });
    } catch (err) {
      toast({ title: "Failed", body: errorMessage(err), type: "error" });
    }
  }

  async function openLogs(key) {
    const a = agents.find((x) => x.key === key);
    const body = h(`<div class="log-stream" style="max-height:none" id="agent-log-${key}">${loadingBlock(4)}</div>`);
    const d = drawer({ title: `${a.name} logs`, body });
    try {
      const rows = await api.get(`/agents/${key}/logs`, { limit: 100 });
      body.innerHTML = rows.length ? rows.map((l) => logLine(l)).join("") : emptyState("list", "No logs yet");
    } catch (err) {
      body.innerHTML = errorBlock(err);
    }
    const onLog = (e) => {
      const l = e.detail;
      if (!l || l.agent_key !== key) return;
      if (qs(".empty", body)) body.innerHTML = "";
      body.insertAdjacentHTML("afterbegin", logLine(l, true));
    };
    document.addEventListener("df:agent_log", onLog);
    const origClose = d.close;
    d.close = () => { document.removeEventListener("df:agent_log", onLog); origClose(); };
    qs("[data-close]", d.el).onclick = d.close;
  }

  page.addEventListener("click", (e) => {
    const cmd = e.target.closest("[data-cmd]");
    if (cmd) return command(cmd.dataset.key, cmd.dataset.cmd);
    const run = e.target.closest("[data-run]");
    if (run) return runNow(run.dataset.run);
    const sch = e.target.closest("[data-schedule]");
    if (sch) return editSchedule(sch.dataset.schedule);
    const lg = e.target.closest("[data-logs]");
    if (lg) return openLogs(lg.dataset.logs);
  });

  async function loadAll() {
    try {
      [agents, logs] = await Promise.all([api.get("/agents"), api.get("/agents/logs", { limit: 50 })]);
      drawGrid();
      qs("#log-stream", page).innerHTML = logs.length ? logs.map((l) => logLine(l)).join("") : emptyState("cpu", "No activity yet", "Accept a request to start the pipeline.");
    } catch (err) {
      qs("#grid", page).innerHTML = errorBlock(err);
    }
  }

  qs("#refresh", page).onclick = loadAll;
  qs("#clear-log", page).onclick = () => (qs("#log-stream", page).innerHTML = "");

  const onStatus = (e) => e.detail && e.detail.agent && patchAgent(e.detail.agent);
  const onLog = (e) => {
    const l = e.detail;
    if (!l) return;
    const stream = qs("#log-stream", page);
    if (!stream) return;
    if (qs(".empty", stream)) stream.innerHTML = "";
    stream.insertAdjacentHTML("afterbegin", logLine(l, true));
    while (stream.children.length > 200) stream.lastElementChild.remove();
  };
  document.addEventListener("df:agent_status", onStatus);
  document.addEventListener("df:agent_log", onLog);
  await loadAll();
  return () => {
    document.removeEventListener("df:agent_status", onStatus);
    document.removeEventListener("df:agent_log", onLog);
  };
}
