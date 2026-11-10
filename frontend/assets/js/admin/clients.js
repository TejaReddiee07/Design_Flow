/* Clients list + detail */
import { api, errorMessage } from "../core/api.js";
import { esc, icon, qs, qsa, h, toast, modal, confirmDialog, setLoading, timeAgo, fmtDate, fmtDateTime, statusBadge, priorityBadge, debounce, titleCase, initials, nl2br } from "../core/ui.js";
import { pageHeader, dataTable, sortRows, pager, loadingBlock, errorBlock, statTile, card, money, moneyCents, invalidateClients, emptyState } from "./shared.js";

const CLIENT_STATUSES = ["trial", "active", "paused", "churned"];
const STAGES = ["new", "assets_requested", "assets_received", "active"];

const CURRENCIES = ["USD", "GBP", "INR"];

function unpaidBadge(n) {
  return n ? `<span class="badge badge-warning">${n} unpaid</span>` : '<span class="badge badge-success">all paid</span>';
}

function clientStatusBadge(s) {
  const cls = { active: "badge-success", trial: "badge-info", paused: "badge-warning", churned: "badge-danger" }[s] || "";
  return `<span class="badge ${cls}">${esc(titleCase(s))}</span>`;
}

export async function render(page, params, query) {
  let q = query.q || "";
  let status = "";
  let pg = 1;
  let sort = { key: "created_at", dir: "desc" };
  page.innerHTML = pageHeader("Clients", "Every client account, their currency, requests and payments.", `<button class="btn btn-primary" id="add-client">${icon("plus")} Add client</button>`) +
    `<div class="filters">
      <div class="input-group">${icon("search")}<input class="input" id="f-q" placeholder="Search company, name or email" value="${esc(q)}"></div>
      <select class="select" id="f-status"><option value="">All statuses</option>${CLIENT_STATUSES.map((s) => `<option value="${s}">${titleCase(s)}</option>`).join("")}</select>
      <span class="ml-auto text-sm text-3" id="count"></span>
    </div><div id="content">${loadingBlock(5)}</div>`;
  const content = qs("#content", page);

  async function load() {
    try {
      const data = await api.get("/clients", { q, status, page: pg, page_size: 25 });
      qs("#count", page).textContent = `${data.total} client${data.total === 1 ? "" : "s"}`;
      const rows = sortRows(data.items, sort.key, sort.dir);
      content.innerHTML = dataTable({
        columns: [
          { key: "company_name", label: "Company", sortable: true, render: (c) => `<div class="flex items-center gap-3"><span class="avatar avatar-sm">${initials(c.company_name)}</span><div class="min-w-0"><a href="#/clients/${c.id}"><b>${esc(c.company_name)}</b></a><div class="text-xs text-3"><a class="cf-row-link" href="#/client-files/${c.id}" title="Open ${esc(c.company_name)} folder">${icon("folder", "icon-sm")} Files</a>${c.industry ? ` · ${esc(c.industry)}` : ""}</div></div></div>` },
          { key: "full_name", label: "Contact", sortable: true, render: (c) => `${esc(c.full_name)}<div class="text-xs text-3">${esc(c.email)}</div>` },
          { key: "currency", label: "Currency", sortable: true, render: (c) => `<span class="badge">${esc(c.currency || "USD")}</span>` },
          { key: "status", label: "Status", sortable: true, render: (c) => clientStatusBadge(c.status) },
          { key: "active_requests", label: "Requests", sortable: true, render: (c) => `<b>${c.active_requests}</b> active <span class="text-3">/ ${c.total_requests}</span>` },
          { key: "unpaid_requests", label: "Unpaid", sortable: true, render: (c) => unpaidBadge(c.unpaid_requests) },
          { key: "total_paid", label: "Total paid", sortable: true, render: (c) => money(c.total_paid, c.currency || "USD") },
          { key: "created_at", label: "Joined", sortable: true, render: (c) => fmtDate(c.created_at) },
          { key: "last_login_at", label: "Last login", sortable: true, render: (c) => (c.last_login_at ? timeAgo(c.last_login_at) : "—") },
        ],
        rows,
        sortKey: sort.key,
        sortDir: sort.dir,
        empty: "No clients found",
        emptyIcon: "users",
        rowAttrs: (c) => `class="clickable" data-client="${c.id}"`,
      });
      if (data.total > 25) content.appendChild(pager({ page: pg, total: data.total, pageSize: 25, onPage: (p) => { pg = p; load(); } }));
      qsa("[data-sort]", content).forEach((th) => th.addEventListener("click", () => { sort = { key: th.dataset.sort, dir: sort.key === th.dataset.sort && sort.dir === "desc" ? "asc" : "desc" }; load(); }));
      qsa("[data-client]", content).forEach((tr) => tr.addEventListener("click", (e) => { if (!e.target.closest("a")) location.hash = `/clients/${tr.dataset.client}`; }));
    } catch (err) {
      content.innerHTML = errorBlock(err);
    }
  }

  const apply = debounce(() => { q = qs("#f-q", page).value.trim(); status = qs("#f-status", page).value; pg = 1; load(); }, 250);
  qs("#f-q", page).addEventListener("input", apply);
  qs("#f-status", page).addEventListener("change", apply);
  qs("#add-client", page).onclick = () => openAddClient(load);
  await load();
}

async function openAddClient(onDone) {
  const body = h(`<div class="form-grid">
    <div class="field"><label class="label">Contact name <span class="req">*</span></label><input class="input" id="c-name"></div>
    <div class="field"><label class="label">Company <span class="req">*</span></label><input class="input" id="c-company"></div>
    <div class="field"><label class="label">Email <span class="req">*</span></label><input class="input" type="email" id="c-email"></div>
    <div class="field"><label class="label">Temporary password <span class="req">*</span></label><input class="input" id="c-pass" value="Welcome${Math.floor(1000 + Math.random() * 9000)}!"></div>
    <div class="field"><label class="label">Website</label><input class="input" id="c-site" placeholder="https://"></div>
    <div class="field"><label class="label">Industry</label><input class="input" id="c-industry"></div>
    <div class="field span-2"><label class="label">Billing currency</label><select class="select" id="c-currency">${CURRENCIES.map((c) => `<option value="${c}">${c}</option>`).join("")}</select><span class="hint">Prices for this client's requests are shown and invoiced in this currency.</span></div>
    <div class="field span-2"><label class="label">Brand notes</label><textarea class="textarea" id="c-notes" placeholder="Colours, fonts, tone, do's and don'ts"></textarea></div>
  </div>`);
  const footer = h(`<div class="flex gap-2 justify-end w-full"><button class="btn btn-secondary" data-close>Cancel</button><button class="btn btn-primary" id="c-save">Create client</button></div>`);
  const m = modal({ title: "Add client", body, footer, size: "lg" });
  qs("#c-save", footer).onclick = async () => {
    const btn = qs("#c-save", footer);
    setLoading(btn, true);
    try {
      const payload = {
        full_name: qs("#c-name", body).value, company_name: qs("#c-company", body).value, email: qs("#c-email", body).value, password: qs("#c-pass", body).value,
        website: qs("#c-site", body).value || null, industry: qs("#c-industry", body).value || null, brand_notes: qs("#c-notes", body).value || null, currency: qs("#c-currency", body).value,
      };
      const c = await api.post("/clients", payload);
      invalidateClients();
      m.close();
      toast({ title: "Client created", body: `${c.company_name} · password: ${payload.password}`, type: "success", timeout: 9000 });
      onDone(c);
    } catch (err) {
      toast({ title: "Failed", body: errorMessage(err), type: "error" });
      setLoading(btn, false);
    }
  };
}

export async function renderDetail(page, params) {
  const id = Number(params.id);
  page.innerHTML = loadingBlock(4);
  let ov = null;

  async function load() {
    ov = await api.get(`/clients/${id}/overview`);
  }

  function draw() {
    const c = ov.client;
    const byStatus = ov.requests_by_status || {};
    page.innerHTML = `<div class="detail-head">
        <div><div class="breadcrumb mb-2"><a href="#/clients">Clients</a><span>/</span><span>${esc(c.company_name)}</span></div>
          <div class="flex items-center gap-3"><span class="avatar avatar-lg">${initials(c.company_name)}</span><div><h1>${esc(c.company_name)}</h1><div class="text-3 text-sm">${esc(c.full_name)} · ${esc(c.email)}${c.website ? ` · <a href="${esc(c.website)}" target="_blank">${esc(c.website.replace(/^https?:\/\//, ""))}</a>` : ""}</div></div></div>
          <div class="flex gap-2 mt-3 wrap">${clientStatusBadge(c.status)}<span class="badge">${esc(c.currency || "USD")}</span>${unpaidBadge(c.unpaid_requests)}<span class="badge badge-cyan">Onboarding: ${esc(titleCase(c.onboarding_stage))}</span>${c.industry ? `<span class="badge">${esc(c.industry)}</span>` : ""}</div>
        </div>
        <div class="action-bar"><a href="#/client-files/${c.id}" class="btn btn-secondary">${icon("folder")} Files</a><a href="#/chat?client_id=${c.id}" class="btn btn-secondary">${icon("message")} Open chat</a><a href="#/requests?client_id=${c.id}" class="btn btn-secondary">${icon("inbox")} Requests</a><a href="#/billing?client_id=${c.id}" class="btn btn-secondary">${icon("credit-card")} Invoices</a><button class="btn btn-primary" id="edit">${icon("edit")} Edit</button></div>
      </div>
      <div class="kpi-grid" style="grid-template-columns:repeat(4,minmax(0,1fr))">
        ${statTile({ label: "Active requests", value: c.active_requests, iconName: "activity", delta: `${c.total_requests} total` })}
        ${statTile({ label: "Completed", value: byStatus.completed || 0, iconName: "check-circle", delta: `${byStatus.pending || 0} pending · ${byStatus.in_progress || 0} in progress` })}
        ${statTile({ label: "Total paid", value: money(c.total_paid, c.currency || "USD"), iconName: "dollar", delta: c.unpaid_requests ? `${c.unpaid_requests} request${c.unpaid_requests === 1 ? "" : "s"} unpaid` : "No unpaid requests" })}
        ${statTile({ label: "Member since", value: fmtDate(c.created_at), iconName: "calendar", delta: c.last_login_at ? `Last login ${timeAgo(c.last_login_at)}` : "Never logged in" })}
      </div>
      <div class="dash-grid mt-6">
        <div class="flex flex-col gap-5">
          ${card("Recent requests", `<div class="list">${ov.recent_requests.length ? ov.recent_requests.map((r) => `<div class="list-item"><div class="flex-1 min-w-0"><a class="title" href="#/requests/${r.id}">${esc(r.title)}</a><div class="meta">${esc(r.service)} · ${timeAgo(r.submitted_at)}</div></div>${priorityBadge(r.priority)}${statusBadge(r.status)}</div>`).join("") : emptyState("inbox", "No requests yet")}</div>`, { actions: `<a href="#/requests?client_id=${c.id}" class="btn btn-ghost btn-sm">All ${icon("arrow-right", "icon-sm")}</a>` })}
          ${card("Payments", `<div class="list">${ov.payments.length ? ov.payments.map((p) => `<div class="list-item"><div class="flex-1 min-w-0"><div class="title">${moneyCents(p.amount, p.currency)} <span class="badge ${p.status === "paid" ? "badge-success" : p.status === "failed" ? "badge-danger" : "badge-warning"}">${esc(p.status)}</span></div><div class="meta">${esc(p.description || "")} · ${esc(p.invoice_number || "")}</div></div><span class="text-xs text-4">${p.paid_at ? fmtDate(p.paid_at) : "—"}</span></div>`).join("") : emptyState("credit-card", "No payments")}</div>`, { actions: `<a href="#/billing" class="btn btn-ghost btn-sm">Billing ${icon("arrow-right", "icon-sm")}</a>` })}
        </div>
        <div class="flex flex-col gap-5">
          ${card("Brand notes", `<div class="card-body text-sm" style="white-space:pre-wrap">${c.brand_notes ? nl2br(c.brand_notes) : '<span class="text-4">No brand notes yet.</span>'}</div>`)}
          ${card("Brand assets", `<div class="list">${ov.brand_assets.length ? ov.brand_assets.map((a) => `<div class="list-item"><span class="badge">${esc(a.type)}</span><div class="flex-1 min-w-0"><div class="title truncate">${esc(a.name)}</div>${a.value ? `<div class="meta">${esc(a.value)}</div>` : ""}</div>${a.file_id ? `<a class="btn btn-ghost btn-sm" href="/api/v1/files/${a.file_id}/download" target="_blank">${icon("download", "icon-sm")}</a>` : ""}</div>`).join("") : emptyState("palette", "No assets uploaded")}</div>`)}
          ${card("Projects", `<div class="list">${ov.projects.length ? ov.projects.map((p) => `<div class="list-item"><div class="flex-1"><div class="title">${esc(p.name)}</div></div><span class="badge">${esc(p.status)}</span></div>`).join("") : emptyState("folder", "No projects")}</div>`, { actions: `<a href="#/projects" class="btn btn-ghost btn-sm">Projects</a>` })}
          ${card("Details", `<div class="card-body"><dl class="kv" style="grid-template-columns:120px 1fr"><dt>Status</dt><dd>${esc(titleCase(c.status))}</dd><dt>Onboarding</dt><dd>${esc(titleCase(c.onboarding_stage))}</dd><dt>Drive folder</dt><dd>${c.drive_folder_id ? `<code>${esc(c.drive_folder_id)}</code>` : "—"}</dd><dt>Client ID</dt><dd>#${c.id}</dd><dt>User ID</dt><dd>#${c.user_id}</dd></dl></div>`)}
        </div>
      </div>`;
    qs("#edit", page).onclick = openEdit;
  }

  function openEdit() {
    const c = ov.client;
    const body = h(`<div class="form-grid">
      <div class="field"><label class="label">Company</label><input class="input" id="e-company" value="${esc(c.company_name)}"></div>
      <div class="field"><label class="label">Website</label><input class="input" id="e-site" value="${esc(c.website || "")}"></div>
      <div class="field"><label class="label">Industry</label><input class="input" id="e-industry" value="${esc(c.industry || "")}"></div>
      <div class="field"><label class="label">Status</label><select class="select" id="e-status">${CLIENT_STATUSES.map((s) => `<option value="${s}" ${s === c.status ? "selected" : ""}>${titleCase(s)}</option>`).join("")}</select></div>
      <div class="field"><label class="label">Onboarding stage</label><select class="select" id="e-stage">${STAGES.map((s) => `<option value="${s}" ${s === c.onboarding_stage ? "selected" : ""}>${titleCase(s)}</option>`).join("")}</select></div>
      <div class="field"><label class="label">Billing currency</label><select class="select" id="e-currency">${CURRENCIES.map((x) => `<option value="${x}" ${x === (c.currency || "USD") ? "selected" : ""}>${x}</option>`).join("")}</select></div>
      <div class="field"><label class="label">Drive folder id</label><input class="input" id="e-drive" value="${esc(c.drive_folder_id || "")}"></div>
      <div class="field span-2"><label class="label">Brand notes</label><textarea class="textarea" id="e-notes">${esc(c.brand_notes || "")}</textarea></div>
      <label class="toggle span-2"><input type="checkbox" id="e-active" checked><span class="track"></span>Login enabled</label>
    </div>`);
    const footer = h(`<div class="flex gap-2 justify-between w-full"><button class="btn btn-danger-soft" id="e-delete">${icon("trash", "icon-sm")} Delete client</button><div class="flex gap-2"><button class="btn btn-secondary" data-close>Cancel</button><button class="btn btn-primary" id="e-save">Save</button></div></div>`);
    const m = modal({ title: `Edit ${c.company_name}`, body, footer, size: "lg" });
    qs("#e-save", footer).onclick = async () => {
      setLoading(qs("#e-save", footer), true);
      try {
        await api.patch(`/clients/${id}`, {
          company_name: qs("#e-company", body).value, website: qs("#e-site", body).value || null, industry: qs("#e-industry", body).value || null,
          status: qs("#e-status", body).value, onboarding_stage: qs("#e-stage", body).value, drive_folder_id: qs("#e-drive", body).value || null, currency: qs("#e-currency", body).value,
          brand_notes: qs("#e-notes", body).value, is_active: qs("#e-active", body).checked,
        });
        invalidateClients();
        m.close();
        toast({ title: "Client updated", type: "success" });
        await load();
        draw();
      } catch (err) {
        toast({ title: "Failed", body: errorMessage(err), type: "error" });
        setLoading(qs("#e-save", footer), false);
      }
    };
    qs("#e-delete", footer).onclick = async () => {
      const ok = await confirmDialog({ title: "Delete this client?", body: "This removes the account, requests and files permanently.", confirmText: "Delete", danger: true });
      if (!ok) return;
      try {
        await api.del(`/clients/${id}`);
        invalidateClients();
        m.close();
        toast({ title: "Client deleted", type: "success" });
        location.hash = "/clients";
      } catch (err) {
        toast({ title: "Failed", body: errorMessage(err), type: "error" });
      }
    };
  }

  try {
    await load();
    draw();
  } catch (err) {
    page.innerHTML = errorBlock(err);
  }
}
