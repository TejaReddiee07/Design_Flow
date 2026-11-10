/* Shared helpers for the admin app: caches, tables, pagination, request actions, board, uploads, charts. */
import { api, errorMessage } from "../core/api.js";
import {
  icon, esc, h, qs, qsa, toast, modal, confirmDialog, promptDialog, timeAgo, fmtDate, fmtBytes,
  statusBadge, priorityBadge, emptyState, STATUS_LABELS, titleCase, setLoading,
} from "../core/ui.js";
import { lineChart, barChart, donutChart, legendHtml, destroyChart } from "../core/charts.js";

/* ---------- caches ---------- */
let _services = null;
let _clients = null;

export async function getServices(force = false) {
  if (!_services || force) _services = await api.get("/services", { include_inactive: true });
  return _services;
}

export function invalidateServices() {
  _services = null;
}

export async function getClients(force = false) {
  if (!_clients || force) {
    const page = await api.get("/clients", { page_size: 200 });
    _clients = page.items;
  }
  return _clients;
}

export function invalidateClients() {
  _clients = null;
}

export function serviceIcon(svc, cls = "") {
  return icon("svc-" + (svc && svc.icon ? svc.icon : "custom"), cls);
}

/* ---------- page chrome ---------- */
export function setTitle(t) {
  const el = qs("#page-title");
  if (el) el.textContent = t;
  document.title = `${t} — Designflow Admin`;
}

export function pageHeader(title, sub = "", actions = "") {
  return `<div class="page-header"><div><h1>${esc(title)}</h1>${sub ? `<div class="sub">${sub}</div>` : ""}</div>${actions ? `<div class="flex gap-2 wrap">${actions}</div>` : ""}</div>`;
}

export function statTile({ label, value, delta = "", dir = "", iconName = "", small = "" }) {
  return `<div class="stat">
    <div class="stat-label">${iconName ? `<span class="stat-icon">${icon(iconName, "icon-sm")}</span>` : ""}${esc(label)}</div>
    <div class="stat-value">${value}${small ? `<small>${esc(small)}</small>` : ""}</div>
    ${delta ? `<div class="stat-delta ${dir}">${delta}</div>` : ""}
  </div>`;
}

export function pct(n) {
  return `${Number(n || 0).toFixed(1)}%`;
}

export function hoursLabel(hours) {
  if (hours === null || hours === undefined) return "—";
  if (hours < 48) return `${Math.round(hours)}h`;
  return `${(hours / 24).toFixed(1)}d`;
}

export function card(title, body, { actions = "", id = "", cls = "" } = {}) {
  return `<div class="card ${cls}" ${id ? `id="${id}"` : ""}>
    ${title ? `<div class="card-header"><h3>${title}</h3>${actions ? `<div class="flex gap-2">${actions}</div>` : ""}</div>` : ""}
    ${body}
  </div>`;
}

/* ---------- tables ---------- */
export function dataTable({ columns, rows, sortKey = null, sortDir = "desc", empty = "Nothing here yet", emptyIcon = "inbox", rowAttrs = null }) {
  if (!rows.length) return emptyState(emptyIcon, empty);
  const head = columns
    .map((c) => {
      const cls = c.sortable ? `sortable ${sortKey === c.key ? sortDir : ""}` : "";
      return `<th class="${cls}" ${c.sortable ? `data-sort="${c.key}"` : ""} ${c.width ? `style="width:${c.width}"` : ""}>${esc(c.label)}</th>`;
    })
    .join("");
  const body = rows
    .map((r) => {
      const attrs = rowAttrs ? rowAttrs(r) : "";
      return `<tr ${attrs}>${columns.map((c) => `<td class="${c.cls || ""}">${c.render ? c.render(r) : esc(r[c.key] ?? "")}</td>`).join("")}</tr>`;
    })
    .join("");
  return `<div class="table-wrap"><table class="table"><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

export function sortRows(rows, key, dir) {
  if (!key) return rows;
  const mul = dir === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    const va = a[key];
    const vb = b[key];
    if (va === vb) return 0;
    if (va === null || va === undefined) return 1;
    if (vb === null || vb === undefined) return -1;
    if (typeof va === "number" && typeof vb === "number") return (va - vb) * mul;
    return String(va).localeCompare(String(vb)) * mul;
  });
}

export function pager({ page, total, pageSize, onPage }) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  const el = h(`<div class="pager">
    <span>${total ? `Showing ${(page - 1) * pageSize + 1}–${Math.min(total, page * pageSize)} of ${total}` : "No results"}</span>
    <div class="btns">
      <button class="btn btn-secondary btn-sm" data-prev ${page <= 1 ? "disabled" : ""}>${icon("chevron-left", "icon-sm")} Prev</button>
      <span class="btn btn-ghost btn-sm" style="pointer-events:none">Page ${page} / ${pages}</span>
      <button class="btn btn-secondary btn-sm" data-next ${page >= pages ? "disabled" : ""}>Next ${icon("chevron-right", "icon-sm")}</button>
    </div></div>`);
  qs("[data-prev]", el).onclick = () => onPage(page - 1);
  qs("[data-next]", el).onclick = () => onPage(page + 1);
  return el;
}

/* ---------- request actions ---------- */
export const ACTION_DEFS = {
  accept: { label: "Accept", cls: "btn-success-soft", icon: "check", next: "accepted", endpoint: "accept" },
  reject: { label: "Reject", cls: "btn-danger-soft", icon: "x", next: "rejected", endpoint: "reject", prompt: true },
  complete: { label: "Completed", cls: "btn-primary", icon: "check-circle", next: "completed", endpoint: "complete" },
  start: { label: "Start", cls: "btn-secondary", icon: "play", next: "in_progress", endpoint: "start" },
  review: { label: "Send to review", cls: "btn-secondary", icon: "eye", next: "review", endpoint: "review" },
  approve: { label: "Approve & deliver", cls: "btn-success-soft", icon: "send", next: null, endpoint: "approve" },
  reopen: { label: "Reopen", cls: "btn-secondary", icon: "repeat", next: "in_progress", endpoint: "start" },
  pipeline: { label: "Run pipeline", cls: "btn-secondary", icon: "cpu", next: null, endpoint: "run-pipeline" },
  markpaid: { label: "Mark paid", cls: "btn-warning-soft", icon: "credit-card", next: null, endpoint: "mark-paid" },
};

/** Price + payment state for a request. */
export function priceBadge(r, { withAmount = true } = {}) {
  if (r.price_amount === null || r.price_amount === undefined) return "";
  const amt = withAmount ? money(r.price_amount, r.price_currency || "USD") : "";
  return r.is_paid
    ? `<span class="badge badge-success" title="Paid ${r.paid_at ? fmtDate(r.paid_at) : ""}">${icon("check", "icon-sm")} ${amt || "Paid"}</span>`
    : `<span class="badge badge-warning" title="Awaiting payment">${icon("credit-card", "icon-sm")} ${amt ? amt + " · unpaid" : "Unpaid"}</span>`;
}

export function actionsFor(status) {
  switch (status) {
    case "pending":
      return ["accept", "reject", "complete"];
    case "accepted":
      return ["start", "reject", "complete"];
    case "in_progress":
      return ["review", "complete"];
    case "review":
      return ["approve", "complete"];
    case "completed":
      return ["reopen"];
    case "rejected":
      return ["accept", "complete"];
    default:
      return ["complete"];
  }
}

export function actionButtons(req, { size = "btn-sm", only = null } = {}) {
  let acts = only || actionsFor(req.status);
  if (!only && !req.is_paid && req.status !== "rejected" && req.price_amount) acts = [...acts, "markpaid"];
  return acts
    .map((a) => {
      const d = ACTION_DEFS[a];
      return `<button class="btn ${size} ${d.cls}" data-act="${a}" data-id="${req.id}" title="${esc(d.label)}">${icon(d.icon, "icon-sm")} ${esc(d.label)}</button>`;
    })
    .join("");
}

/** Perform an action; returns the updated RequestOut or null if cancelled. */
export async function performAction(id, act, { title = "" } = {}) {
  const d = ACTION_DEFS[act];
  if (!d) return null;
  let body = undefined;
  if (d.prompt) {
    const reason = await promptDialog({ title: `Reject ${title || "request"}`, label: "Reason (sent to the client)", placeholder: "Out of scope, missing assets…", multiline: true, confirmText: "Reject" });
    if (reason === null) return null;
    body = { reason };
  } else if (act === "complete" || act === "reopen") {
    const ok = await confirmDialog({
      title: act === "complete" ? "Mark as completed?" : "Reopen this request?",
      body: act === "complete" ? "The client will be notified that the work is done." : "The request moves back to In Progress.",
      confirmText: act === "complete" ? "Mark completed" : "Reopen",
    });
    if (!ok) return null;
  } else if (act === "markpaid") {
    const note = await promptDialog({ title: `Record payment for ${title || "request"}`, label: "Reference (bank transfer, cash, invoice no.)", placeholder: "e.g. bank transfer 12 Nov", confirmText: "Mark paid" });
    if (note === null) return null;
    return api.post(`/requests/${id}/mark-paid`, null, { note: note || undefined });
  }
  return api.post(`/requests/${id}/${d.endpoint}`, body);
}

/** Delegate [data-act] clicks inside root. onDone(req, act, updated) is called after success. */
export function bindActions(root, { onDone, onStart } = {}) {
  root.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-act][data-id]");
    if (!btn || !root.contains(btn)) return;
    e.preventDefault();
    e.stopPropagation();
    const act = btn.dataset.act;
    const id = Number(btn.dataset.id);
    const title = btn.closest("[data-title]")?.dataset.title || "";
    setLoading(btn, true);
    let revert = null;
    try {
      if (onStart) revert = onStart(id, act, btn);
      const updated = await performAction(id, act, { title });
      if (updated === null) {
        if (revert) revert();
        setLoading(btn, false);
        return;
      }
      toast({ title: `${ACTION_DEFS[act].label}: done`, body: updated.title, type: "success", timeout: 2500 });
      if (onDone) onDone(updated, act);
    } catch (err) {
      if (revert) revert();
      toast({ title: "Action failed", body: errorMessage(err), type: "error" });
      setLoading(btn, false);
    }
  });
}

/* ---------- request card + board ---------- */
export function requestCard(r, { showService = true, extraClass = "" } = {}) {
  return `<div class="req-card ${extraClass}" data-req="${r.id}" data-status="${esc(r.status)}" data-title="${esc(r.title)}">
    <div class="flex items-center justify-between gap-2"><span class="flex gap-1 wrap">${priorityBadge(r.priority)}${priceBadge(r)}</span><span class="text-xs text-4">${timeAgo(r.submitted_at)}</span></div>
    <div class="req-title"><a href="#/requests/${r.id}" style="color:inherit">${esc(r.title)}</a></div>
    <div class="req-meta"><span>${esc(r.company_name)}</span>${showService ? `<span>·</span><span>${esc(r.service_name)}</span>` : ""}${r.turnaround_days ? `<span>·</span><span>${r.turnaround_days}d</span>` : ""}${r.revision_count ? `<span>·</span><span>${icon("repeat", "icon-sm")} rev ${r.revision_count}</span>` : ""}</div>
    <div class="req-actions"><a class="btn btn-sm btn-live" href="/admin/live/${r.id}" target="_blank" rel="noopener" onclick="event.stopPropagation()" title="See in live: watch the agents work on this request"><span class="live-dot"></span> Live</a>${actionButtons(r)}</div>
  </div>`;
}

export const BOARD_COLS = [
  ["pending", "Pending"],
  ["accepted", "Accepted"],
  ["in_progress", "In Progress"],
  ["review", "In Review"],
  ["completed", "Completed"],
  ["rejected", "Rejected"],
];

export function renderBoard(container, requests, { showService = true, newIds = new Set() } = {}) {
  container.innerHTML = `<div class="board">${BOARD_COLS.map(([key, label]) => {
    const items = requests.filter((r) => r.status === key);
    return `<div class="board-col" data-col="${key}">
      <div class="board-col-header"><span>${statusBadge(key)}</span><span class="count-badge ${items.length ? "" : "is-zero"}" data-col-count>${items.length}</span></div>
      <div class="board-col-body" data-col-body="${key}">${items.map((r) => requestCard(r, { showService, extraClass: newIds.has(r.id) ? "new" : "" })).join("") || `<div class="text-xs text-4 text-center" style="padding:20px 0">Empty</div>`}</div>
    </div>`;
  }).join("")}</div>`;
}

/** Optimistically move a card between columns. Returns a revert function. */
export function moveCard(container, id, toStatus) {
  const cardEl = qs(`[data-req="${id}"]`, container);
  if (!cardEl || !toStatus) return () => {};
  const fromBody = cardEl.parentElement;
  const toBody = qs(`[data-col-body="${toStatus}"]`, container);
  if (!toBody) return () => {};
  const next = cardEl.nextElementSibling;
  toBody.prepend(cardEl);
  cardEl.dataset.status = toStatus;
  updateColCounts(container);
  return () => {
    if (next) fromBody.insertBefore(cardEl, next);
    else fromBody.appendChild(cardEl);
    updateColCounts(container);
  };
}

export function updateColCounts(container) {
  qsa(".board-col", container).forEach((col) => {
    const n = qsa(".req-card", col).length;
    const b = qs("[data-col-count]", col);
    if (b) {
      b.textContent = n;
      b.classList.toggle("is-zero", n === 0);
    }
  });
}

/* ---------- uploads ---------- */
export async function uploadFiles(fileList, { request_id = null, kind = "upload", client_id = null } = {}, onProgress) {
  const out = [];
  const files = Array.from(fileList || []);
  for (let i = 0; i < files.length; i++) {
    const fd = new FormData();
    fd.append("file", files[i]);
    fd.append("kind", kind);
    if (request_id) fd.append("request_id", request_id);
    if (client_id) fd.append("client_id", client_id);
    if (onProgress) onProgress(i + 1, files.length, files[i].name);
    out.push(await api.upload("/files/upload", fd));
  }
  return out;
}

export function fileChip(f) {
  return `<span class="file-chip" data-file="${f.id}">${icon("file", "icon-sm")}<span class="name" title="${esc(f.original_name)}">${esc(f.original_name)}</span><span class="text-4">${fmtBytes(f.size_bytes)}</span></span>`;
}

export function fileRow(f) {
  const isImg = (f.mime_type || "").startsWith("image/");
  return `<div class="list-item" data-file="${f.id}">
    <span class="avatar avatar-sm avatar-neutral">${icon(isImg ? "image" : "file", "icon-sm")}</span>
    <div class="flex-1 min-w-0"><div class="title truncate">${esc(f.original_name)}</div><div class="meta">${esc(f.kind)} · v${f.version} · ${fmtBytes(f.size_bytes)} · ${timeAgo(f.created_at)}</div></div>
    <button class="btn btn-secondary btn-sm" data-download="${f.id}" data-name="${esc(f.original_name)}">${icon("download", "icon-sm")} Download</button>
  </div>`;
}

/* ---------- brief ---------- */
export function formatValue(v) {
  if (v === null || v === undefined || v === "") return '<span class="text-4">—</span>';
  if (Array.isArray(v)) return v.map((x) => `<span class="badge">${esc(x)}</span>`).join(" ");
  if (typeof v === "object") return `<pre class="json-view">${esc(JSON.stringify(v, null, 2))}</pre>`;
  if (typeof v === "boolean") return v ? "Yes" : "No";
  return esc(String(v));
}

export function briefHtml(brief = {}, schema = [], description = "") {
  const known = new Set(schema.map((f) => f.key));
  const rows = schema.map((f) => `<dt>${esc(f.label)}</dt><dd>${formatValue(brief[f.key])}</dd>`);
  Object.keys(brief || {}).filter((k) => !known.has(k)).forEach((k) => rows.push(`<dt>${esc(titleCase(k))}</dt><dd>${formatValue(brief[k])}</dd>`));
  return `${description ? `<p class="text-2 mb-6" style="white-space:pre-wrap">${esc(description)}</p>` : ""}${rows.length ? `<dl class="kv">${rows.join("")}</dl>` : '<p class="text-4">No brief fields.</p>'}`;
}

export function kvHtml(obj) {
  const rows = Object.entries(obj || {}).map(([k, v]) => `<dt>${esc(titleCase(k))}</dt><dd>${formatValue(v)}</dd>`);
  return rows.length ? `<dl class="kv">${rows.join("")}</dl>` : '<p class="text-4">—</p>';
}

/* ---------- logs ---------- */
export function logLine(l, fresh = false) {
  const t = l.created_at ? new Date(l.created_at.endsWith("Z") || /[+-]\d\d:?\d\d$/.test(l.created_at) ? l.created_at : l.created_at + "Z") : new Date();
  const time = t.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit", second: "2-digit" });
  const cls = l.status === "failed" || l.level === "error" ? "failed" : l.level === "warn" ? "warn" : "";
  return `<div class="log-line ${cls} ${fresh ? "fresh" : ""}"><span class="t">${time}</span><span class="k">${esc(titleCase(l.agent_key || ""))}</span><span>${l.request_id ? `<a href="#/requests/${l.request_id}">#${l.request_id}</a> ` : ""}${esc(l.step ? l.step + ": " : "")}${esc(l.message)}${l.duration_ms ? ` <span class="text-4">(${(l.duration_ms / 1000).toFixed(1)}s)</span>` : ""}</span></div>`;
}

/* ---------- chart card with table toggle ---------- */
let _chartSeq = 0;

export function chartCard(container, { title, sub = "", height = 240, legend = "", table = null }) {
  const id = `chart-${++_chartSeq}`;
  const el = h(`<div class="card chart-card">
    <div class="card-header"><div><h3>${esc(title)}</h3>${sub ? `<div class="sub">${esc(sub)}</div>` : ""}</div>
      ${table ? `<div class="segmented"><button class="active" data-view="chart">Chart</button><button data-view="table">Table</button></div>` : ""}</div>
    <div class="chart-view"><div class="chart-box"><canvas id="${id}" style="height:${height}px"></canvas></div><div class="chart-legend">${legend}</div></div>
    ${table ? `<div class="chart-table hidden">${table}</div>` : ""}
  </div>`);
  container.appendChild(el);
  const canvas = qs("canvas", el);
  if (table) {
    qsa("[data-view]", el).forEach((b) =>
      b.addEventListener("click", () => {
        qsa("[data-view]", el).forEach((x) => x.classList.toggle("active", x === b));
        qs(".chart-view", el).classList.toggle("hidden", b.dataset.view === "table");
        qs(".chart-table", el).classList.toggle("hidden", b.dataset.view !== "table");
      })
    );
  }
  return {
    el,
    canvas,
    setLegend(html) {
      qs(".chart-legend", el).innerHTML = html;
    },
  };
}

export function seriesTable(labels, series, { labelHead = "Label", fmt = (v) => v } = {}) {
  return `<div class="table-wrap"><table class="table"><thead><tr><th>${esc(labelHead)}</th>${series.map((s) => `<th>${esc(s.name)}</th>`).join("")}</tr></thead><tbody>${labels
    .map((l, i) => `<tr><td>${esc(l)}</td>${series.map((s) => `<td>${fmt(s.data[i] ?? 0)}</td>`).join("")}</tr>`)
    .join("")}</tbody></table></div>`;
}

export function itemsTable(items, { fmt = (v) => v } = {}) {
  const total = items.reduce((a, i) => a + (i.value || 0), 0);
  return `<div class="table-wrap"><table class="table"><thead><tr><th>Item</th><th>Value</th><th>Share</th></tr></thead><tbody>${items
    .map((i) => `<tr><td>${esc(i.label)}</td><td>${fmt(i.value)}</td><td>${total ? Math.round((i.value / total) * 100) : 0}%</td></tr>`)
    .join("")}</tbody></table></div>`;
}

export { lineChart, barChart, donutChart, legendHtml, destroyChart };

/* ---------- misc ---------- */
export function money(v, currency = "USD") {
  return new Intl.NumberFormat(undefined, { style: "currency", currency, maximumFractionDigits: 0 }).format(Number(v || 0));
}

export function moneyCents(v, currency = "USD") {
  return new Intl.NumberFormat(undefined, { style: "currency", currency }).format(Number(v || 0));
}

export function statusOptions(selected = "") {
  return Object.entries(STATUS_LABELS).map(([k, v]) => `<option value="${k}" ${k === selected ? "selected" : ""}>${v}</option>`).join("");
}

export function loadingBlock(n = 4) {
  return Array.from({ length: n }, () => '<div class="skeleton" style="height:52px;margin-bottom:10px"></div>').join("");
}

export function errorBlock(err) {
  return `<div class="empty">${icon("alert")}<h4>Could not load</h4><p>${esc(errorMessage(err))}</p></div>`;
}

export function dateShort(v) {
  return v ? fmtDate(v) : "—";
}

export function linkTo(path, label) {
  return `<a href="#${path}">${label}</a>`;
}

export function byId(list, id) {
  return list.find((x) => x.id === id);
}

export { modal, confirmDialog, promptDialog, toast, esc, icon, h, qs, qsa, timeAgo, statusBadge, priorityBadge, emptyState, errorMessage, api, titleCase, setLoading };
