/* Your designs: everything delivered to this client, grouped by service, ready to download. */
import { api, fileUrl } from "../core/api.js";
import { icon, esc, qs, qsa, fmtDate, fmtDateTime, skeletonRows, emptyState } from "../core/ui.js";
import { grid, bindGallery, downloadZip } from "../core/gallery.js";
import { pageHeader, errorBox, serviceIcon } from "./shared.js";

function plural(n, word) {
  return `${n} ${word}${n === 1 ? "" : "s"}`;
}

function deliveryBlock(r, d, groups, { latest }) {
  const key = `delivery-${d.id}`;
  groups.set(key, d.files);
  return `<section class="yd-delivery ${latest ? "is-latest" : ""}">
    <div class="yd-delivery-head">
      <div class="yd-delivery-title"><span class="badge ${latest ? "badge-success" : ""}">${icon("check-circle", "icon-sm")} Delivery ${d.version}</span><span class="text-xs text-3">${esc(fmtDateTime(d.delivered_at))}</span></div>
      <button type="button" class="btn ${latest ? "btn-primary" : "btn-secondary"} btn-sm" data-zip="/library/deliveries/${d.id}/download" data-zip-name="${esc(r.title)}.zip">${icon("download", "icon-sm")} Download all (ZIP)</button>
    </div>
    ${d.message ? `<div class="yd-message"><p class="clamp">${esc(d.message)}</p><button type="button" class="yd-more" data-more hidden>Show more</button></div>` : ""}
    ${grid(d.files, key)}
  </section>`;
}

function requestCard(r, groups) {
  const dels = r.deliveries || [];
  const [latest, ...earlier] = dels;
  return `<article class="card yd-request">
    <header class="yd-request-head">
      <div class="min-w-0">
        <a class="yd-request-title" href="#/requests/${r.id}" title="${esc(r.title)}">${esc(r.title)}</a>
        <div class="yd-request-meta"><span>Delivered ${esc(fmtDate(latest.delivered_at))}</span><span>${plural(dels.length, "delivery")}</span>${r.revision_count ? `<span>${plural(r.revision_count, "revision")}</span>` : ""}</div>
      </div>
      <a class="btn btn-secondary btn-sm" href="#/requests/${r.id}">${icon("eye", "icon-sm")} View request</a>
    </header>
    <div class="yd-request-body">
      ${deliveryBlock(r, latest, groups, { latest: true })}
      ${earlier.length ? `<details class="yd-earlier"><summary>${icon("chevron-right", "icon-sm")} ${plural(earlier.length, "earlier delivery")}</summary><div class="yd-earlier-body">${earlier.map((d) => deliveryBlock(r, d, groups, { latest: false })).join("")}</div></details>` : ""}
    </div>
  </article>`;
}

export async function renderDesigns(page) {
  page.innerHTML = `${pageHeader({ title: "Your designs", sub: "Everything we have delivered to you, ready to download.", actions: `<a class="btn btn-primary" href="#/new">${icon("plus")} Order a design</a>` })}
    <div id="yd-body">${skeletonRows(3)}</div>`;
  const body = qs("#yd-body", page);
  let data;
  try {
    data = await api.get("/library/me");
  } catch (err) {
    body.innerHTML = errorBox(err);
    return;
  }
  if (!data.services.length) {
    body.innerHTML = `<div class="card">${emptyState("image", "No designs delivered yet", "When your designer approves and sends your work, it appears here with every file ready to download.")}<p class="text-center" style="margin:-24px 0 32px"><a class="btn btn-primary" href="#/new">${icon("plus")} Order a design</a></p></div>`;
    return;
  }
  const groups = new Map();
  const titles = new Map();
  data.services.forEach((s) => s.requests.forEach((r) => (r.deliveries || []).forEach((d) => titles.set(`delivery-${d.id}`, `${r.title} · delivery ${d.version}`))));
  const t = data.totals;
  body.innerHTML = `<div class="yd-summary">
      <div><b>${t.delivered}</b><span>${t.delivered === 1 ? "delivery" : "deliveries"}</span></div>
      <div><b>${t.requests}</b><span>${t.requests === 1 ? "request" : "requests"}</span></div>
      <div><b>${t.services}</b><span>${t.services === 1 ? "service" : "services"}</span></div>
    </div>
    ${data.services.map((s) => `<section class="yd-service">
      <header class="yd-service-head"><span class="yd-service-ico">${serviceIcon(s.icon)}</span><div class="min-w-0"><h2>${esc(s.name)}</h2><div class="text-xs text-3">${plural(s.requests.length, "request")}</div></div></header>
      <div class="yd-service-body">${s.requests.map((r) => requestCard(r, groups)).join("")}</div>
    </section>`).join("")}`;

  bindGallery(body, groups, { titleFor: (k) => titles.get(k) || "Your designs" });
  body.addEventListener("click", (e) => {
    const z = e.target.closest("[data-zip]");
    if (z) {
      e.preventDefault();
      downloadZip(z.dataset.zip, z.dataset.zipName || "designs.zip", z);
      return;
    }
    const more = e.target.closest("[data-more]");
    if (more) {
      const p = more.previousElementSibling;
      const open = p.classList.toggle("clamp");
      more.textContent = open ? "Show more" : "Show less";
    }
  });
  // Only offer "Show more" when the message is actually longer than three lines.
  requestAnimationFrame(() => qsa(".yd-message", body).forEach((m) => {
    const p = qs("p", m);
    qs("[data-more]", m).hidden = p.scrollHeight <= p.clientHeight + 2;
  }));
}

/** Small "Latest designs" strip for the dashboard: up to 4 covers, newest first. */
export function latestCovers(data, n = 4) {
  const out = [];
  (data.services || []).forEach((s) => s.requests.forEach((r) => (r.deliveries || []).forEach((d) => {
    if (d.cover_file_id) out.push({ file_id: d.cover_file_id, title: r.title, service: s.name, at: d.delivered_at });
  })));
  out.sort((a, b) => String(b.at || "").localeCompare(String(a.at || "")));
  return out.slice(0, n).map((c) => ({ ...c, src: fileUrl(c.file_id) }));
}
