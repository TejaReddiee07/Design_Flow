/* Leads list + detail */
import { api, errorMessage } from "../core/api.js";
import { esc, icon, qs, qsa, h, toast, modal, confirmDialog, setLoading, fmtDate, fmtDateTime, timeAgo, titleCase, debounce, nl2br } from "../core/ui.js";
import { pageHeader, statTile, dataTable, sortRows, pager, loadingBlock, errorBlock, pct, kvHtml, card, emptyState, getServices, money } from "./shared.js";

const CURRENCIES = ["USD", "GBP", "INR"];

function serviceOptions(services, selected = "") {
  return `<option value="">Any service (rotate)</option>` + services.map((s) => `<option value="${esc(s.slug)}" ${s.slug === selected ? "selected" : ""}>${esc(s.name)}</option>`).join("");
}

const LEAD_STATUSES = ["new", "contacted", "replied", "qualified", "converted", "rejected"];
const LEAD_CLS = { new: "badge-info", contacted: "badge-purple", replied: "badge-cyan", qualified: "badge-warning", converted: "badge-success", rejected: "badge-danger" };
const OUT_CLS = { draft: "", approved: "badge-info", sent: "badge-purple", replied: "badge-success", bounced: "badge-danger" };

export function leadStatusBadge(s) {
  return `<span class="badge ${LEAD_CLS[s] || ""}">${esc(titleCase(s))}</span>`;
}

export function outreachStatusBadge(s) {
  return `<span class="badge ${OUT_CLS[s] || ""}">${esc(titleCase(s))}</span>`;
}

export function scoreBar(score) {
  const color = score >= 80 ? "var(--success)" : score >= 60 ? "var(--warning)" : "var(--danger)";
  return `<div class="score-bar"><div class="progress"><span style="width:${Math.min(100, score)}%;background:${color}"></span></div><b>${score}</b></div>`;
}

export async function render(page, params, query) {
  let q = query.q || "";
  let status = query.status || "";
  let pg = 1;
  let sort = { key: "score", dir: "desc" };
  page.innerHTML = pageHeader("Leads", "Real businesses found on the web by the Lead Agent, plus website enquiries and manual entries. Convert any lead into a client with one click.", `<button class="btn btn-secondary" id="add-lead">${icon("plus")} Add lead</button><button class="btn btn-primary" id="gen-leads">${icon("search")} Find leads</button>`) +
    `<div class="kpi-grid" id="kpis">${loadingBlock(5)}</div>
     <div class="filters mt-6">
      <div class="input-group">${icon("search")}<input class="input" id="f-q" placeholder="Search company, email, industry" value="${esc(q)}"></div>
      <select class="select" id="f-status"><option value="">All statuses</option>${LEAD_STATUSES.map((s) => `<option value="${s}" ${s === status ? "selected" : ""}>${titleCase(s)}</option>`).join("")}</select>
      <span class="ml-auto text-sm text-3" id="count"></span>
     </div><div id="content">${loadingBlock(5)}</div>`;
  const content = qs("#content", page);

  async function loadStats() {
    try {
      const s = await api.get("/leads/stats");
      qs("#kpis", page).innerHTML = [
        statTile({ label: "Total leads", value: s.total, iconName: "target", delta: `${s.by_status.new || 0} new` }),
        statTile({ label: "Converted", value: s.converted, iconName: "award", delta: `${pct(s.conversion_rate)} conversion` }),
        statTile({ label: "Avg score", value: s.avg_score, iconName: "star", small: "/100" }),
        statTile({ label: "Outreach sent", value: s.outreach_sent, iconName: "send" }),
        statTile({ label: "Reply rate", value: pct(s.reply_rate), iconName: "message", delta: `${s.replies} replies` }),
      ].join("");
    } catch (err) {
      qs("#kpis", page).innerHTML = errorBlock(err);
    }
  }

  async function load() {
    try {
      const data = await api.get("/leads", { q: q || undefined, status: status || undefined, page: pg, page_size: 25 });
      qs("#count", page).textContent = `${data.total} lead${data.total === 1 ? "" : "s"}`;
      const rows = sortRows(data.items, sort.key, sort.dir);
      content.innerHTML = dataTable({
        columns: [
          { key: "company_name", label: "Company", sortable: true, render: (l) => `<a href="#/leads/${l.id}"><b>${esc(l.company_name)}</b></a>${l.website ? `<div class="text-xs text-3">${esc(l.website.replace(/^https?:\/\//, ""))}</div>` : ""}` },
          { key: "contact_email", label: "Contact", sortable: true, render: (l) => `${esc(l.contact_name || "—")}<div class="text-xs">${l.contact_email ? `<span class="badge badge-success">${icon("mail", "icon-sm")} ${esc(l.contact_email)}</span>` : '<span class="badge badge-warning">no email found</span>'}</div>` },
          { key: "industry", label: "Industry", sortable: true, render: (l) => `${esc(l.industry || "—")}${l.analysis && l.analysis.interested_in ? `<div class="text-xs text-3">wants: ${esc(String(l.analysis.interested_in).replace(/-/g, " "))}</div>` : ""}` },
          { key: "score", label: "Score", sortable: true, render: (l) => scoreBar(l.score) },
          { key: "status", label: "Status", sortable: true, render: (l) => (l.status === "converted" && l.client_id ? `<a href="#/clients/${l.client_id}" class="badge badge-success">Converted → client</a>` : leadStatusBadge(l.status)) },
          { key: "source", label: "Source", sortable: true, render: (l) => `<span class="badge">${esc(l.source)}</span>` },
          { key: "outreach_count", label: "Outreach", sortable: true },
          { key: "created_at", label: "Added", sortable: true, render: (l) => timeAgo(l.created_at) },
        ],
        rows,
        sortKey: sort.key,
        sortDir: sort.dir,
        empty: "No leads yet",
        emptyIcon: "target",
        rowAttrs: (l) => `class="clickable" data-lead="${l.id}"`,
      });
      if (data.total > 25) content.appendChild(pager({ page: pg, total: data.total, pageSize: 25, onPage: (p) => { pg = p; load(); } }));
      qsa("[data-sort]", content).forEach((th) => th.addEventListener("click", () => { sort = { key: th.dataset.sort, dir: sort.key === th.dataset.sort && sort.dir === "desc" ? "asc" : "desc" }; load(); }));
      qsa("[data-lead]", content).forEach((tr) => tr.addEventListener("click", (e) => { if (!e.target.closest("a")) location.hash = `/leads/${tr.dataset.lead}`; }));
    } catch (err) {
      content.innerHTML = errorBlock(err);
    }
  }

  const apply = debounce(() => { q = qs("#f-q", page).value.trim(); status = qs("#f-status", page).value; pg = 1; load(); }, 250);
  qs("#f-q", page).addEventListener("input", apply);
  qs("#f-status", page).addEventListener("change", apply);

  qs("#gen-leads", page).onclick = async () => {
    const services = await getServices().catch(() => []);
    const body = h(`<div class="form-grid">
      <div class="field span-2"><label class="label">Service to sell</label><select class="select" id="g-service">${serviceOptions(services)}</select><span class="hint">The agent searches the web for the kinds of businesses that buy this service (e.g. new restaurants for logos, creators for thumbnails).</span></div>
      <div class="field"><label class="label">Industry (optional)</label><input class="input" id="g-industry" placeholder="e.g. fitness studios"></div>
      <div class="field"><label class="label">Location (optional)</label><input class="input" id="g-location" placeholder="e.g. London"></div>
      <div class="field span-2"><label class="label">How many businesses</label><input class="input" type="number" min="1" max="25" value="5" id="g-count"></div>
      <p class="hint span-2">${icon("search", "icon-sm")} The Lead Agent runs real web searches, opens each website, extracts a contact email, scores the fit and stores the lead. Leads with an email automatically get an outreach draft for you to approve. This takes a minute or two.</p></div>`);
    const footer = h(`<div class="flex gap-2 justify-end w-full"><button class="btn btn-secondary" data-close>Cancel</button><button class="btn btn-primary" id="g-run">${icon("search", "icon-sm")} Find leads</button></div>`);
    const m = modal({ title: "Find leads on the web", body, footer });
    qs("#g-run", footer).onclick = async () => {
      setLoading(qs("#g-run", footer), true);
      try {
        const r = await api.post("/leads/generate", { industry: qs("#g-industry", body).value || null, location: qs("#g-location", body).value || null, count: Number(qs("#g-count", body).value) || 5, service_slug: qs("#g-service", body).value || null });
        m.close();
        toast({ title: "Lead Agent searching", body: `${r.message}. You'll get a notification when leads are ready.`, type: "success", timeout: 6000 });
      } catch (err) {
        toast({ title: "Failed", body: errorMessage(err), type: "error" });
        setLoading(qs("#g-run", footer), false);
      }
    };
  };

  qs("#add-lead", page).onclick = () => {
    const body = h(`<div class="form-grid">
      <div class="field span-2"><label class="label">Company <span class="req">*</span></label><input class="input" id="l-company"></div>
      <div class="field"><label class="label">Website</label><input class="input" id="l-site" placeholder="https://"></div>
      <div class="field"><label class="label">Industry</label><input class="input" id="l-industry"></div>
      <div class="field"><label class="label">Contact name</label><input class="input" id="l-name"></div>
      <div class="field"><label class="label">Contact email</label><input class="input" type="email" id="l-email"></div>
      <div class="field"><label class="label">Phone</label><input class="input" id="l-phone"></div>
      <div class="field"><label class="label">Location</label><input class="input" id="l-location"></div>
      <div class="field"><label class="label">Score (0-100)</label><input class="input" type="number" min="0" max="100" value="50" id="l-score"></div>
      <div class="field span-2"><label class="label">Notes</label><textarea class="textarea" id="l-notes"></textarea></div>
    </div>`);
    const footer = h(`<div class="flex gap-2 justify-end w-full"><button class="btn btn-secondary" data-close>Cancel</button><button class="btn btn-primary" id="l-save">Add lead</button></div>`);
    const m = modal({ title: "Add lead", body, footer, size: "lg" });
    qs("#l-save", footer).onclick = async () => {
      setLoading(qs("#l-save", footer), true);
      try {
        await api.post("/leads", {
          company_name: qs("#l-company", body).value, website: qs("#l-site", body).value || null, industry: qs("#l-industry", body).value || null,
          contact_name: qs("#l-name", body).value || null, contact_email: qs("#l-email", body).value || null, contact_phone: qs("#l-phone", body).value || null,
          location: qs("#l-location", body).value || null, notes: qs("#l-notes", body).value || null, score: Number(qs("#l-score", body).value) || 0,
        });
        m.close();
        toast({ title: "Lead added", type: "success" });
        loadStats();
        load();
      } catch (err) {
        toast({ title: "Failed", body: errorMessage(err), type: "error" });
        setLoading(qs("#l-save", footer), false);
      }
    };
  };

  loadStats();
  await load();
}

function analysisHtml(a) {
  if (!a || !Object.keys(a).length) return '<p class="text-4 text-sm">No analysis yet. The Lead Agent fills this in when it researches the website.</p>';
  const list = (v) => (Array.isArray(v) && v.length ? `<ul style="margin:0;padding-left:18px">${v.map((x) => `<li>${esc(String(x))}</li>`).join("")}</ul>` : v ? esc(String(v)) : '<span class="text-4">—</span>');
  const rest = Object.fromEntries(Object.entries(a).filter(([k]) => !["interested_in", "recommended_services", "pain_points", "opportunity", "score"].includes(k)));
  return `<dl class="kv">
    ${a.interested_in ? `<dt>Asked for</dt><dd><span class="badge badge-purple">${esc(String(a.interested_in).replace(/-/g, " "))}</span></dd>` : ""}
    <dt>Opportunity</dt><dd>${esc(a.opportunity || "—")}</dd>
    <dt>Recommended services</dt><dd>${Array.isArray(a.recommended_services) && a.recommended_services.length ? a.recommended_services.map((s) => `<span class="badge badge-cyan">${esc(String(s))}</span>`).join(" ") : "—"}</dd>
    <dt>Pain points</dt><dd>${list(a.pain_points)}</dd>
  </dl>${Object.keys(rest).length ? `<details class="mt-3"><summary class="text-xs" style="cursor:pointer;color:var(--brand-600)">More details</summary><div class="mt-2">${kvHtml(rest)}</div></details>` : ""}`;
}

async function openConvert(lead, onDone) {
  const services = await getServices().catch(() => []);
  const interested = (lead.analysis || {}).interested_in || "";
  const body = h(`<div class="form-grid">
    <div class="field span-2"><p class="text-sm text-2">Creates a client account for <b>${esc(lead.contact_email || "")}</b>${lead.contact_email ? "" : ' <span class="badge badge-danger">no email - add one first</span>'} and, if you pick a service, opens a request for it so the normal pipeline starts.</p></div>
    <div class="field span-2"><label class="label">Service they want</label><select class="select" id="cv-service"><option value="">No request yet - account only</option>${services.map((s) => `<option value="${esc(s.slug)}" ${s.slug === interested ? "selected" : ""}>${esc(s.name)} — ${money((s.prices || {}).USD || 0)} · ${s.turnaround_days}d</option>`).join("")}</select></div>
    <div class="field span-2"><label class="label">Request title (optional)</label><input class="input" id="cv-title" placeholder="e.g. Logo for ${esc(lead.company_name)}"></div>
    <div class="field"><label class="label">Billing currency</label><select class="select" id="cv-currency">${CURRENCIES.map((c) => `<option value="${c}">${c}</option>`).join("")}</select></div>
    <div class="field"><label class="label">Password (optional)</label><input class="input" id="cv-password" placeholder="Leave empty to generate"></div>
    <label class="checkbox span-2"><input type="checkbox" id="cv-email" checked> Email the login details to the client (uses your SMTP settings)</label>
  </div>`);
  const footer = h(`<div class="flex gap-2 justify-end w-full"><button class="btn btn-secondary" data-close>Cancel</button><button class="btn btn-primary" id="cv-go" ${lead.contact_email ? "" : "disabled"}>${icon("users", "icon-sm")} Convert</button></div>`);
  const m = modal({ title: `Convert ${lead.company_name} to a client`, body, footer });
  qs("#cv-go", footer).onclick = async () => {
    setLoading(qs("#cv-go", footer), true);
    try {
      const pw = qs("#cv-password", body).value.trim();
      const res = await api.post(`/leads/${lead.id}/convert`, {
        service_slug: qs("#cv-service", body).value || null, title: qs("#cv-title", body).value || null, currency: qs("#cv-currency", body).value,
        password: pw || null, send_email: qs("#cv-email", body).checked,
      });
      m.close();
      const rbody = h(`<div class="text-sm">
        <p>${res.created_account ? "Client account created." : "This email already had an account; the lead is now linked to it."}</p>
        <dl class="kv mt-3"><dt>Login</dt><dd><code>${esc(res.email)}</code></dd>${res.temporary_password ? `<dt>Password</dt><dd><code id="cv-pw">${esc(res.temporary_password)}</code> <button class="btn btn-ghost btn-sm" id="cv-copy">${icon("link", "icon-sm")} Copy</button></dd>` : ""}
        ${res.request ? `<dt>Request</dt><dd><a href="#/requests/${res.request.id}">${esc(res.request.title)}</a> — ${money(res.request.price_amount, res.request.price_currency)}</dd>` : ""}</dl>
        <p class="hint mt-3">${qs("#cv-email", body).checked ? "The login details were sent by email (check Settings → Email provider if it should be live)." : "Share the login details with the client yourself."}</p></div>`);
      const rfooter = h(`<div class="flex gap-2 justify-end w-full"><a class="btn btn-secondary" href="#/clients/${res.client_id}" data-close>Open client</a>${res.request ? `<a class="btn btn-primary" href="#/requests/${res.request.id}" data-close>Open request</a>` : '<button class="btn btn-primary" data-close>Done</button>'}</div>`);
      modal({ title: "Lead converted", body: rbody, footer: rfooter });
      const copy = qs("#cv-copy", rbody);
      if (copy) copy.onclick = () => navigator.clipboard?.writeText(res.temporary_password).then(() => toast({ title: "Copied", type: "success", timeout: 1500 }));
      onDone(res);
    } catch (err) {
      toast({ title: "Conversion failed", body: errorMessage(err), type: "error" });
      setLoading(qs("#cv-go", footer), false);
    }
  };
}

export async function renderDetail(page, params) {
  const id = Number(params.id);
  page.innerHTML = loadingBlock(4);
  let lead = null;
  let outreach = [];

  async function load() {
    [lead, outreach] = await Promise.all([api.get(`/leads/${id}`), api.get(`/leads/${id}/outreach`).catch(() => [])]);
  }

  function draw() {
    const l = lead;
    page.innerHTML = `<div class="detail-head">
        <div><div class="breadcrumb mb-2"><a href="#/leads">Leads</a><span>/</span><span>${esc(l.company_name)}</span></div>
          <h1>${esc(l.company_name)}</h1>
          <div class="detail-meta">${l.website ? `<span>${icon("globe", "icon-sm")} <a href="${esc(l.website)}" target="_blank">${esc(l.website.replace(/^https?:\/\//, ""))}</a></span>` : ""}${l.industry ? `<span>${icon("tag", "icon-sm")} ${esc(l.industry)}</span>` : ""}${l.location ? `<span>${icon("globe", "icon-sm")} ${esc(l.location)}</span>` : ""}<span>${icon("clock", "icon-sm")} Added ${fmtDate(l.created_at)} via ${esc(l.source)}</span></div>
          <div class="flex gap-2 mt-3 wrap items-center">${leadStatusBadge(l.status)}<span style="width:160px">${scoreBar(l.score)}</span>${l.client_id ? `<a href="#/clients/${l.client_id}" class="badge badge-success">Converted → client</a>` : ""}</div>
        </div>
        <div class="action-bar">
          <select class="select" id="status-select" style="width:auto">${LEAD_STATUSES.map((s) => `<option value="${s}" ${s === l.status ? "selected" : ""}>${titleCase(s)}</option>`).join("")}</select>
          <button class="btn btn-secondary" id="draft">${icon("mail")} Draft outreach</button>
          ${l.status !== "converted" ? `<button class="btn btn-primary" id="convert">${icon("users")} Convert to client</button>` : `<a href="#/clients/${l.client_id}" class="btn btn-success-soft">${icon("users")} View client</a>`}
          <button class="btn btn-ghost" id="delete">${icon("trash")}</button>
        </div>
      </div>
      <div class="dash-grid">
        <div class="flex flex-col gap-5">
          ${card("Contact", `<div class="card-body"><dl class="kv"><dt>Name</dt><dd>${esc(l.contact_name || "—")}</dd><dt>Email</dt><dd>${l.contact_email ? `<a href="mailto:${esc(l.contact_email)}">${esc(l.contact_email)}</a>` : '<span class="badge badge-warning">not found — add one to convert or email</span>'}</dd><dt>Phone</dt><dd>${esc(l.contact_phone || "—")}</dd></dl></div>`, { actions: `<button class="btn btn-ghost btn-sm" id="edit-contact">${icon("edit", "icon-sm")} Edit</button>` })}
          ${card("Analysis", `<div class="card-body">${analysisHtml(l.analysis)}</div>`)}
          ${card("Outreach history", `<div class="list">${outreach.length ? outreach.map((o) => `<div class="list-item" style="align-items:flex-start"><div class="flex-1 min-w-0"><div class="title">${esc(o.subject || "(no subject)")} ${outreachStatusBadge(o.status)}</div><div class="meta">${esc(o.channel)} · ${o.sent_at ? "sent " + fmtDateTime(o.sent_at) : "not sent"} · ${o.follow_up_count} follow-up${o.follow_up_count === 1 ? "" : "s"}</div><details class="mt-2"><summary class="text-xs" style="cursor:pointer;color:var(--brand-600)">Show email</summary><div class="text-sm mt-2" style="white-space:pre-wrap">${esc(o.body)}</div>${o.reply_text ? `<div class="text-sm mt-2" style="padding:8px 10px;background:var(--success-bg);border-radius:8px"><b>Reply:</b> ${esc(o.reply_text)}</div>` : ""}</details></div><a href="#/outreach" class="btn btn-ghost btn-sm">Manage</a></div>`).join("") : emptyState("mail", "No outreach yet", "Draft a personalised email with the Outreach Agent.")}</div>`)}
        </div>
        <div class="flex flex-col gap-5">
          ${card("Notes", `<div class="card-body"><textarea class="textarea" id="notes" placeholder="Call notes, context, next steps…">${esc(l.notes || "")}</textarea><button class="btn btn-secondary btn-sm mt-3" id="save-notes">Save notes</button></div>`)}
          ${card("Score", `<div class="card-body"><input type="range" min="0" max="100" value="${l.score}" id="score" style="width:100%"><div class="flex justify-between text-xs text-3 mt-1"><span>0</span><b id="score-val">${l.score}</b><span>100</span></div><button class="btn btn-secondary btn-sm mt-3" id="save-score">Save score</button></div>`)}
        </div>
      </div>`;

    qs("#status-select", page).addEventListener("change", async (e) => {
      try {
        lead = await api.patch(`/leads/${id}`, { status: e.target.value });
        toast({ title: "Status updated", type: "success", timeout: 2000 });
        draw();
      } catch (err) {
        toast({ title: "Failed", body: errorMessage(err), type: "error" });
      }
    });
    qs("#save-notes", page).onclick = async () => {
      try {
        lead = await api.patch(`/leads/${id}`, { notes: qs("#notes", page).value });
        toast({ title: "Notes saved", type: "success", timeout: 2000 });
      } catch (err) {
        toast({ title: "Failed", body: errorMessage(err), type: "error" });
      }
    };
    qs("#score", page).addEventListener("input", (e) => (qs("#score-val", page).textContent = e.target.value));
    qs("#save-score", page).onclick = async () => {
      try {
        lead = await api.patch(`/leads/${id}`, { score: Number(qs("#score", page).value) });
        toast({ title: "Score saved", type: "success", timeout: 2000 });
        draw();
      } catch (err) {
        toast({ title: "Failed", body: errorMessage(err), type: "error" });
      }
    };
    qs("#draft", page).onclick = async () => {
      const btn = qs("#draft", page);
      setLoading(btn, true);
      try {
        const r = await api.post("/outreach/draft", { lead_ids: [id], tone: "friendly" });
        toast({ title: "Outreach Agent drafting", body: r.message, type: "success" });
      } catch (err) {
        toast({ title: "Failed", body: errorMessage(err), type: "error" });
      } finally {
        setLoading(btn, false);
      }
    };
    const cv = qs("#convert", page);
    if (cv) cv.onclick = () => openConvert(lead, async () => { await load(); draw(); });
    qs("#delete", page).onclick = async () => {
      const ok = await confirmDialog({ title: "Delete lead?", body: "Outreach history is removed too.", confirmText: "Delete", danger: true });
      if (!ok) return;
      try {
        await api.del(`/leads/${id}`);
        toast({ title: "Lead deleted", type: "success" });
        location.hash = "/leads";
      } catch (err) {
        toast({ title: "Failed", body: errorMessage(err), type: "error" });
      }
    };
    qs("#edit-contact", page).onclick = () => {
      const body = h(`<div class="form-grid"><div class="field"><label class="label">Contact name</label><input class="input" id="c-name" value="${esc(l.contact_name || "")}"></div><div class="field"><label class="label">Email</label><input class="input" id="c-email" value="${esc(l.contact_email || "")}"></div><div class="field span-2"><label class="label">Industry</label><input class="input" id="c-industry" value="${esc(l.industry || "")}"></div></div>`);
      const footer = h(`<div class="flex gap-2 justify-end w-full"><button class="btn btn-secondary" data-close>Cancel</button><button class="btn btn-primary" id="c-save">Save</button></div>`);
      const m = modal({ title: "Edit contact", body, footer });
      qs("#c-save", footer).onclick = async () => {
        try {
          lead = await api.patch(`/leads/${id}`, { contact_name: qs("#c-name", body).value || null, contact_email: qs("#c-email", body).value || null, industry: qs("#c-industry", body).value || null });
          m.close();
          draw();
        } catch (err) {
          toast({ title: "Failed", body: errorMessage(err), type: "error" });
        }
      };
    };
  }

  try {
    await load();
    draw();
  } catch (err) {
    page.innerHTML = errorBlock(err);
  }
}
