/* Client files: one folder per client -> services -> requests -> delivered versions + drafts. */
import { api } from "../core/api.js";
import { fileUrl } from "../core/api.js";
import { esc, icon, qs, qsa, debounce, timeAgo, fmtDate, fmtDateTime, statusBadge, initials } from "../core/ui.js";
import { grid, bindGallery, downloadZip } from "../core/gallery.js";
import { pageHeader, loadingBlock, errorBlock, statTile, emptyState } from "./shared.js";

/** Stable tint per company so each folder is recognisable at a glance. */
function hue(name = "") {
  let h = 0;
  for (const ch of String(name)) h = (h * 31 + ch.charCodeAt(0)) % 360;
  return h;
}

function tintStyle(name) {
  const h0 = hue(name);
  return `--cf-h:${h0}`;
}

function plural(n, word) {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

/* ---------- list ---------- */
function folderCard(c) {
  const cover = c.cover_file_id ? `<img src="${esc(fileUrl(c.cover_file_id))}" alt="" loading="lazy" decoding="async">` : `<span class="cf-cover-empty">${icon("folder")}</span>`;
  return `<a class="card cf-card" href="#/client-files/${c.client_id}" style="${tintStyle(c.company_name)}" title="Open ${esc(c.company_name)}'s folder">
    <div class="cf-cover">${cover}</div>
    <div class="cf-card-body">
      <div class="cf-card-head">
        <span class="cf-folder-ico">${icon("folder")}</span>
        <div class="min-w-0">
          <div class="cf-name" title="${esc(c.company_name)}">${esc(c.company_name)}</div>
          <div class="cf-sub" title="${esc(c.client_name)} · ${esc(c.email)}">${esc(c.client_name || c.email)}</div>
        </div>
      </div>
      <div class="cf-counts">
        <div><b>${c.services}</b><span>${c.services === 1 ? "service" : "services"}</span></div>
        <div><b>${c.designs}</b><span>${c.designs === 1 ? "design" : "designs"}</span></div>
        <div><b>${c.delivered}</b><span>delivered</span></div>
      </div>
      <div class="cf-foot"><span>${icon("clock", "icon-sm")} ${c.last_activity ? `Active ${esc(timeAgo(c.last_activity))}` : "No activity yet"}</span><span>${plural(c.files, "file")}</span></div>
    </div>
  </a>`;
}

export async function render(page, params, query) {
  let q = (query && query.q) || "";
  page.innerHTML = pageHeader("Client files", "Every client has their own folder. Open one to see all their services and designs.") +
    `<div class="filters">
      <div class="input-group cf-search">${icon("search")}<input class="input" id="cf-q" placeholder="Search company, name or email" value="${esc(q)}" aria-label="Search client folders"></div>
      <span class="ml-auto text-sm text-3" id="cf-count"></span>
    </div>
    <div id="cf-list">${loadingBlock(3)}</div>`;
  const list = qs("#cf-list", page);

  async function load() {
    try {
      const cards = await api.get("/library/clients", { q: q || undefined });
      qs("#cf-count", page).textContent = plural(cards.length, "folder");
      list.innerHTML = cards.length
        ? `<div class="cf-grid">${cards.map(folderCard).join("")}</div>`
        : emptyState("folder", q ? "No folders match your search" : "No client folders yet", q ? "Try a company name, a person or an email address." : "A folder is created for every client when they create an account.");
    } catch (err) {
      list.innerHTML = errorBlock(err);
    }
  }

  qs("#cf-q", page).addEventListener("input", debounce((e) => {
    q = e.target.value.trim();
    load();
  }, 250));
  await load();
}

/* ---------- one client's folder ---------- */
function versionHead({ badge, when, by, actions, note }) {
  return `<div class="cf-version-head">
    <div class="cf-version-title">${badge}<span class="text-xs text-3">${when}${by ? ` · ${by}` : ""}</span></div>
    <div class="cf-version-actions">${actions}</div>
    ${note ? `<p class="cf-version-note" title="${esc(note)}">${esc(note)}</p>` : ""}
  </div>`;
}

function deliveryBlock(d, groups) {
  const key = `delivery-${d.id}`;
  groups.set(key, d.files);
  return `<section class="cf-version is-delivered">
    ${versionHead({
      badge: `<span class="badge badge-success">${icon("check-circle", "icon-sm")} Delivered v${d.version}</span>`,
      when: d.delivered_at ? esc(fmtDateTime(d.delivered_at)) : "",
      by: d.delivered_by === "agent" ? "Delivery Agent" : d.delivered_by === "admin" ? "You" : "",
      actions: `<button type="button" class="btn btn-secondary btn-sm" data-zip="/library/deliveries/${d.id}/download">${icon("download", "icon-sm")} Download all (ZIP)</button>`,
      note: d.message || "",
    })}
    ${grid(d.files, key)}
  </section>`;
}

function draftBlock(d, groups) {
  const key = `design-${d.id}`;
  groups.set(key, d.files);
  const qa = d.qa_score !== null && d.qa_score !== undefined ? ` · QA ${Math.round(d.qa_score)}` : "";
  const cls = d.status === "approved" ? "badge-info" : d.status === "rejected" ? "badge-danger" : "";
  return `<section class="cf-version">
    ${versionHead({
      badge: `<span class="badge ${cls}">${d.status === "approved" ? "Approved" : "Draft"} v${d.version}${qa}</span>${d.title ? `<span class="cf-version-name" title="${esc(d.title)}">${esc(d.title)}</span>` : ""}`,
      when: d.created_at ? esc(fmtDateTime(d.created_at)) : "",
      by: d.generated_by === "agent" ? "Design Agent" : d.generated_by === "human" ? "Designer" : "",
      actions: `<button type="button" class="btn btn-ghost btn-sm" data-zip="/library/designs/${d.id}/download">${icon("download", "icon-sm")} Download all (ZIP)</button>`,
    })}
    ${grid(d.files, key)}
  </section>`;
}

function requestCard(r, groups) {
  const delivered = r.deliveries || [];
  const drafts = r.designs || [];
  const body = !delivered.length && !drafts.length
    ? `<p class="dg-empty">${icon("sparkles", "icon-sm")} No files yet. Drafts appear here as soon as the Design Agent or your designer adds them.</p>`
    : `${delivered.map((d) => deliveryBlock(d, groups)).join("")}
       ${drafts.length ? `<details class="cf-drafts" ${delivered.length ? "" : "open"}><summary>${icon("chevron-right", "icon-sm")} ${plural(drafts.length, "draft version")}</summary><div class="cf-drafts-body">${drafts.map((d) => draftBlock(d, groups)).join("")}</div></details>` : ""}`;
  return `<article class="card cf-request">
    <header class="cf-request-head">
      <div class="min-w-0">
        <a class="cf-request-title" href="#/requests/${r.id}" title="${esc(r.title)}">${esc(r.title)}</a>
        <div class="cf-request-meta"><span>#${r.id}</span><span>Submitted ${esc(fmtDate(r.submitted_at))}</span>${r.completed_at ? `<span>Completed ${esc(fmtDate(r.completed_at))}</span>` : ""}${r.revision_count ? `<span>${plural(r.revision_count, "revision")}</span>` : ""}</div>
      </div>
      <div class="cf-request-actions">${statusBadge(r.status)}<a class="btn btn-ghost btn-sm" href="#/requests/${r.id}">${icon("eye", "icon-sm")} Open request</a><a class="btn btn-sm btn-live" href="/admin/live/${r.id}" target="_blank" rel="noopener"><span class="live-dot"></span> See in live</a></div>
    </header>
    <div class="cf-request-body">${body}</div>
  </article>`;
}

function serviceSection(s, groups) {
  return `<section class="cf-service" id="svc-${esc(s.slug)}">
    <header class="cf-service-head">
      <span class="cf-service-ico">${icon("svc-" + (s.icon || "custom"))}</span>
      <div class="min-w-0"><h2>${esc(s.name)}</h2><div class="text-xs text-3">${esc(s.category || "")}${s.category ? " · " : ""}${plural(s.request_count, "request")}</div></div>
    </header>
    <div class="cf-service-body">${s.requests.map((r) => requestCard(r, groups)).join("")}</div>
  </section>`;
}

export async function renderDetail(page, params) {
  const id = Number(params.id);
  page.innerHTML = loadingBlock(4);
  let data;
  try {
    data = await api.get(`/library/clients/${id}`);
  } catch (err) {
    page.innerHTML = errorBlock(err);
    return;
  }
  const c = data.client;
  const t = data.totals;
  const groups = new Map();
  const titles = new Map();
  data.services.forEach((s) => s.requests.forEach((r) => {
    (r.deliveries || []).forEach((d) => titles.set(`delivery-${d.id}`, `${r.title} · delivered v${d.version}`));
    (r.designs || []).forEach((d) => titles.set(`design-${d.id}`, `${r.title} · draft v${d.version}`));
  }));

  page.innerHTML = `<div class="detail-head cf-detail-head">
      <div class="min-w-0">
        <nav class="cf-crumbs" aria-label="Breadcrumb"><a href="#/client-files">Client files</a><span>/</span><span aria-current="page">${esc(c.company_name)}</span></nav>
        <div class="cf-title" style="${tintStyle(c.company_name)}">
          <span class="cf-title-ico">${esc(initials(c.company_name))}</span>
          <div class="min-w-0"><h1 title="${esc(c.company_name)}">${esc(c.company_name)}</h1><div class="text-sm text-3 truncate">${esc(c.client_name)}${c.email ? ` · ${esc(c.email)}` : ""}</div></div>
        </div>
        <div class="cf-path" title="Storage folder">${icon("folder", "icon-sm")}<code>${esc(c.folder)}</code></div>
      </div>
      <div class="action-bar"><a class="btn btn-secondary" href="#/clients/${c.id}">${icon("users")} Open client</a><a class="btn btn-secondary" href="#/chat?client_id=${c.id}">${icon("message")} Chat</a></div>
    </div>
    <div class="kpi-grid cf-kpis">
      ${statTile({ label: "Services", value: t.services, iconName: "layers" })}
      ${statTile({ label: "Requests", value: t.requests, iconName: "inbox" })}
      ${statTile({ label: "Design versions", value: t.designs, iconName: "palette" })}
      ${statTile({ label: "Delivered", value: t.delivered, iconName: "check-circle" })}
    </div>
    ${data.services.length > 1 ? `<nav class="cf-jump" aria-label="Services">${data.services.map((s) => `<a href="#svc-${esc(s.slug)}" data-jump="svc-${esc(s.slug)}">${icon("svc-" + (s.icon || "custom"), "icon-sm")} ${esc(s.name)} <span class="count-badge">${s.request_count}</span></a>`).join("")}</nav>` : ""}
    <div id="cf-services">${data.services.length ? data.services.map((s) => serviceSection(s, groups)).join("") : `<div class="card">${emptyState("folder", "No designs yet for this client", "When this client orders a service, its drafts and deliveries are filed here automatically.")}</div>`}</div>`;

  const root = qs("#cf-services", page);
  bindGallery(root, groups, { titleFor: (k) => titles.get(k) || c.company_name });
  page.addEventListener("click", (e) => {
    const z = e.target.closest("[data-zip]");
    if (z) {
      e.preventDefault();
      downloadZip(z.dataset.zip, `${c.company_name}.zip`, z);
      return;
    }
    const j = e.target.closest("[data-jump]");
    if (j) {
      e.preventDefault();
      const target = document.getElementById(j.dataset.jump);
      if (target) target.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });
  qsa(".cf-drafts", page).forEach((d) => d.addEventListener("toggle", () => d.classList.toggle("open", d.open)));
}
