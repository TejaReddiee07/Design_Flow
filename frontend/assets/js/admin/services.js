/* Service management: grid + per-service detail (board, analytics, notifications, form) */
import { api, errorMessage } from "../core/api.js";
import { esc, icon, qs, qsa, h, toast, modal, setLoading, timeAgo, titleCase, STATUS_LABELS, NOTIF_ICONS, debounce } from "../core/ui.js";
import {
  pageHeader, getServices, invalidateServices, serviceIcon, renderBoard, moveCard, bindActions, ACTION_DEFS, requestCard, updateColCounts,
  statTile, chartCard, donutChart, barChart, legendHtml, itemsTable, seriesTable, loadingBlock, errorBlock, emptyState, pct, hoursLabel, card, money,
} from "./shared.js";

function priceLine(s) {
  const p = s.prices || {};
  if (!p.USD && !s.starting_price) return '<span class="text-4">No price set</span>';
  return `<b>${money(p.USD ?? s.starting_price, "USD")}</b> <span class="text-3">· ${money(p.GBP || 0, "GBP")} · ${money(p.INR || 0, "INR")}</span> <span class="text-xs text-4">${esc(s.price_unit || "per request")}</span>`;
}

export async function render(page) {
  page.innerHTML = pageHeader("Service management", "Each service has a fixed price (USD, with GBP and INR derived) and a delivery time. Pending counts update live; toggle a service to hide it from the site and portal.") + `<div id="grid">${loadingBlock(6)}</div>`;
  const grid = qs("#grid", page);

  async function draw() {
    try {
      const services = await getServices(true);
      grid.innerHTML = `<div class="svc-admin-grid">${services.map((s) => `<div class="svc-admin-card ${s.is_active ? "" : "inactive"}" data-svc="${s.id}">
          <div class="flex items-center justify-between gap-2"><span class="svc-icon">${serviceIcon(s)}</span><span class="count-badge ${s.pending_count ? "" : "is-zero"}" data-service-badge="${s.id}">${s.pending_count}</span></div>
          <h3><a href="#/services/${esc(s.slug)}">${esc(s.name)}</a></h3>
          <div class="text-xs text-3">${esc(s.category)} · ${esc(s.tagline || "")}</div>
          <div class="svc-stats"><span><b>${s.total_requests}</b>requests</span><span><b>${s.pending_count}</b>pending</span><span><b>${s.turnaround_days}d</b>delivery</span></div>
          <div class="svc-price">${priceLine(s)}</div>
          <div class="flex items-center justify-between mt-2"><label class="toggle"><input type="checkbox" data-active="${s.id}" ${s.is_active ? "checked" : ""}><span class="track"></span><span class="text-xs">${s.is_active ? "Active" : "Hidden"}</span></label><a href="#/services/${esc(s.slug)}" class="btn btn-ghost btn-sm">Open ${icon("arrow-right", "icon-sm")}</a></div>
        </div>`).join("")}</div>`;
      qsa("[data-active]", grid).forEach((t) =>
        t.addEventListener("change", async () => {
          try {
            await api.patch(`/services/${t.dataset.active}`, { is_active: t.checked });
            invalidateServices();
            toast({ title: t.checked ? "Service activated" : "Service hidden", type: "success", timeout: 2000 });
            draw();
          } catch (err) {
            t.checked = !t.checked;
            toast({ title: "Failed", body: errorMessage(err), type: "error" });
          }
        })
      );
    } catch (err) {
      grid.innerHTML = errorBlock(err);
    }
  }

  const onBadges = debounce(() => draw(), 500);
  document.addEventListener("df:request_update", onBadges);
  await draw();
  return () => document.removeEventListener("df:request_update", onBadges);
}

const TABS = [["requests", "Requests"], ["analytics", "Analytics"], ["notifications", "Notifications"], ["form", "Form fields"]];

export async function renderDetail(page, params) {
  let svc = null;
  let tab = "requests";
  const cleanups = [];
  page.innerHTML = loadingBlock(4);

  async function load() {
    svc = await api.get(`/services/${params.slug}`);
  }

  function draw() {
    page.innerHTML = `<div class="detail-head">
        <div><div class="breadcrumb mb-2"><a href="#/services">Services</a><span>/</span><span>${esc(svc.name)}</span></div>
          <div class="flex items-center gap-3"><span class="service-icon" style="width:48px;height:48px;border-radius:14px;display:inline-flex;align-items:center;justify-content:center;background:var(--brand-50);color:var(--brand-600)">${serviceIcon(svc)}</span><div><h1>${esc(svc.name)}</h1><div class="text-3 text-sm">${esc(svc.tagline || "")}</div></div></div>
          <div class="flex gap-2 mt-3 wrap"><span class="badge badge-purple">${esc(svc.category)}</span><span class="badge badge-success">${priceLine(svc)}</span><span class="badge">${svc.turnaround_days}-day delivery</span><span class="badge ${svc.is_active ? "badge-success" : "badge-danger"}">${svc.is_active ? "Active" : "Hidden"}</span><span class="badge badge-warning" data-service-pending>${svc.pending_count} pending</span><span class="badge">${svc.total_requests} total</span></div>
        </div>
        <div class="action-bar"><a href="/services/${esc(svc.slug)}" target="_blank" class="btn btn-secondary">${icon("external")} Public page</a><button class="btn btn-primary" id="edit-svc">${icon("edit")} Edit</button></div>
      </div>
      <div class="tabs mb-6">${TABS.map(([k, l]) => `<button class="tab ${k === tab ? "active" : ""}" data-tab="${k}">${l}</button>`).join("")}</div>
      <div id="tab-body"></div>`;
    qsa("[data-tab]", page).forEach((b) =>
      b.addEventListener("click", () => {
        tab = b.dataset.tab;
        qsa("[data-tab]", page).forEach((x) => x.classList.toggle("active", x === b));
        drawTab();
      })
    );
    qs("#edit-svc", page).onclick = openEdit;
    drawTab();
  }

  async function drawTab() {
    const body = qs("#tab-body", page);
    body.innerHTML = loadingBlock(3);
    try {
      if (tab === "requests") {
        const reqs = await api.get(`/services/${svc.id}/requests`, { limit: 300 });
        body.innerHTML = `<div class="flex items-center justify-between mb-4 wrap gap-2"><span class="text-sm text-3">${reqs.length} request${reqs.length === 1 ? "" : "s"} for this service</span><a href="#/requests?service_id=${svc.id}" class="btn btn-ghost btn-sm">Open in requests ${icon("arrow-right", "icon-sm")}</a></div><div id="svc-board"></div>`;
        const boardEl = qs("#svc-board", body);
        renderBoard(boardEl, reqs, { showService: false });
        bindActions(boardEl, {
          onStart: (id, act) => moveCard(boardEl, id, ACTION_DEFS[act].next),
          onDone: (updated) => {
            const c = qs(`[data-req="${updated.id}"]`, boardEl);
            if (c) {
              c.outerHTML = requestCard(updated, { showService: false });
              const fresh = qs(`[data-req="${updated.id}"]`, boardEl);
              const col = qs(`[data-col-body="${updated.status}"]`, boardEl);
              if (fresh && col && fresh.parentElement !== col) col.prepend(fresh);
              updateColCounts(boardEl);
            }
          },
        });
      } else if (tab === "analytics") {
        const a = await api.get(`/services/${svc.id}/analytics`);
        body.innerHTML = `<div class="kpi-grid" style="grid-template-columns:repeat(4,minmax(0,1fr))">
            ${statTile({ label: "Total requests", value: a.total, iconName: "inbox" })}
            ${statTile({ label: "Last 30 days", value: a.last_30_days, iconName: "calendar" })}
            ${statTile({ label: "Avg turnaround", value: hoursLabel(a.avg_turnaround_hours), iconName: "clock" })}
            ${statTile({ label: "Revision rate", value: pct(a.revision_rate), iconName: "repeat" })}
          </div><div class="dash-grid-2 mt-6" id="svc-charts"></div>`;
        api.get("/analytics/sales").then((sales) => {
          const row = (sales.by_service || []).find((s) => s.service_id === svc.id);
          if (!row) return;
          qs(".kpi-grid", body).insertAdjacentHTML("beforeend", statTile({ label: `Revenue (${sales.currency || "INR"})`, value: money(row.revenue ?? row.revenue_usd, sales.currency || "INR"), iconName: "dollar", delta: `${row.paid} paid of ${row.orders} orders` }));
        }).catch(() => {});
        const charts = qs("#svc-charts", body);
        const items = Object.entries(a.by_status).map(([k, v]) => ({ label: STATUS_LABELS[k] || titleCase(k), value: v }));
        const c1 = chartCard(charts, { title: "Requests by status", height: 220, legend: legendHtml(items.map((i) => ({ label: i.label, value: i.value }))), table: itemsTable(items) });
        donutChart(c1.canvas, { items, centerLabel: "requests" });
        const labels = a.trend.map((t) => t.week.slice(5));
        const series = [{ name: "Requests", data: a.trend.map((t) => t.requests) }];
        const c2 = chartCard(charts, { title: "12-week trend", sub: "Requests submitted per week", height: 220, table: seriesTable(labels, series, { labelHead: "Week of" }) });
        barChart(c2.canvas, { labels, series, xTicks: 12 });
      } else if (tab === "notifications") {
        const notes = await api.get("/notifications", { service_id: svc.id, limit: 50 });
        body.innerHTML = notes.length
          ? `<div class="card"><div class="list">${notes.map((n) => `<div class="list-item ${n.is_read ? "" : "font-semibold"}"><span class="notif-icon avatar avatar-sm avatar-neutral">${icon(NOTIF_ICONS[n.type] || "info", "icon-sm")}</span><div class="flex-1 min-w-0"><div class="title">${esc(n.title)}</div><div class="meta">${esc(n.body || "")}</div></div>${n.request_id ? `<a href="#/requests/${n.request_id}" class="btn btn-ghost btn-sm">Open</a>` : ""}<span class="text-xs text-4">${timeAgo(n.created_at)}</span></div>`).join("")}</div></div>`
          : emptyState("bell", "No notifications for this service yet");
      } else if (tab === "form") {
        body.innerHTML = card("Request form fields", `<div class="card-body"><p class="text-sm text-3 mb-4">These fields are shown to clients when they request ${esc(svc.name)}. Edit them in <code>backend/app/db/seed_data.py</code> or via PATCH /services/${svc.id} (form_schema).</p><div class="table-wrap"><table class="table"><thead><tr><th>Key</th><th>Label</th><th>Type</th><th>Required</th><th>Options</th></tr></thead><tbody>${(svc.form_schema || []).map((f) => `<tr><td class="mono">${esc(f.key)}</td><td>${esc(f.label)}</td><td>${esc(f.type || "text")}</td><td>${f.required ? '<span class="badge badge-danger">required</span>' : '<span class="text-4">optional</span>'}</td><td class="wrap">${(f.options || []).map((o) => `<span class="badge">${esc(o)}</span>`).join(" ")}</td></tr>`).join("")}</tbody></table></div>
          <h4 class="mt-6 mb-2">Deliverables</h4><ul style="list-style:disc;padding-left:20px;font-size:var(--fs-sm)">${(svc.deliverables || []).map((d) => `<li>${esc(d)}</li>`).join("")}</ul></div>`);
      }
    } catch (err) {
      body.innerHTML = errorBlock(err);
    }
  }

  function openEdit() {
    const body = h(`<div class="form-grid">
      <div class="field span-2"><label class="label">Name</label><input class="input" id="e-name" value="${esc(svc.name)}"></div>
      <div class="field span-2"><label class="label">Tagline</label><input class="input" id="e-tagline" value="${esc(svc.tagline || "")}"></div>
      <div class="field span-2"><label class="label">Description</label><textarea class="textarea" id="e-desc">${esc(svc.description || "")}</textarea></div>
      <div class="field"><label class="label">Price (USD)</label><input class="input" type="number" min="0" step="1" id="e-price" value="${Number((svc.prices || {}).USD ?? svc.starting_price ?? 0)}"><span class="hint">GBP and INR are derived automatically (FX rates in .env).</span></div>
      <div class="field"><label class="label">Delivery time (days)</label><input class="input" type="number" min="0" max="60" id="e-days" value="${svc.turnaround_days}"></div>
      <div class="field span-2"><label class="label">Category</label><input class="input" id="e-cat" value="${esc(svc.category)}"></div>
      <label class="toggle span-2"><input type="checkbox" id="e-active" ${svc.is_active ? "checked" : ""}><span class="track"></span>Visible on site and portal</label>
    </div>`);
    const footer = h(`<div class="flex gap-2 justify-end w-full"><button class="btn btn-secondary" data-close>Cancel</button><button class="btn btn-primary" id="e-save">Save</button></div>`);
    const m = modal({ title: `Edit ${svc.name}`, body, footer });
    qs("#e-save", footer).onclick = async () => {
      setLoading(qs("#e-save", footer), true);
      try {
        await api.patch(`/services/${svc.id}`, {
          name: qs("#e-name", body).value, tagline: qs("#e-tagline", body).value, description: qs("#e-desc", body).value,
          turnaround_days: Number(qs("#e-days", body).value), starting_price: Number(qs("#e-price", body).value), category: qs("#e-cat", body).value, is_active: qs("#e-active", body).checked,
        });
        invalidateServices();
        m.close();
        toast({ title: "Service updated", type: "success" });
        await load();
        draw();
      } catch (err) {
        toast({ title: "Failed", body: errorMessage(err), type: "error" });
        setLoading(qs("#e-save", footer), false);
      }
    };
  }

  const onUpdate = debounce(async (e) => {
    if (e.detail && svc && Number(e.detail.service_id) === svc.id) {
      await load();
      const b = qs("[data-service-pending]", page);
      if (b) b.textContent = `${svc.pending_count} pending`;
      if (tab === "requests") drawTab();
    }
  }, 400);
  document.addEventListener("df:request_update", onUpdate);
  cleanups.push(() => document.removeEventListener("df:request_update", onUpdate));

  try {
    await load();
    draw();
  } catch (err) {
    page.innerHTML = errorBlock(err);
  }
  return () => cleanups.forEach((fn) => fn());
}
