/* Overview dashboard */
import { api, errorMessage } from "../core/api.js";
import { esc, icon, qs, timeAgo, statusBadge, priorityBadge, agentBadge, fmtNum, titleCase } from "../core/ui.js";
import {
  pageHeader, statTile, card, money, pct, hoursLabel, loadingBlock, errorBlock, bindActions, actionButtons,
  chartCard, lineChart, barChart, legendHtml, seriesTable, emptyState, priceBadge,
} from "./shared.js";

export async function render(page) {
  page.innerHTML = pageHeader("Overview", "Live snapshot of the studio.", `<a href="#/requests" class="btn btn-secondary">${icon("inbox")} Requests</a><a href="#/agents" class="btn btn-primary">${icon("cpu")} Agents</a>`) +
    `<div class="kpi-grid" id="kpis">${loadingBlock(5)}</div>
     <div class="dash-grid mt-6" id="charts"></div>
     <div class="dash-grid-2 mt-6" id="lists"></div>`;

  const kpis = qs("#kpis", page);
  const charts = qs("#charts", page);
  const lists = qs("#lists", page);
  const cleanups = [];

  try {
    const [ov, rev, reqs, pending, agents, leads, notes, sales] = await Promise.all([
      api.get("/analytics/overview"),
      api.get("/analytics/revenue", { months: 12 }),
      api.get("/analytics/requests", { days: 30 }),
      api.get("/requests", { status: "pending", page_size: 8 }),
      api.get("/agents/summary"),
      api.get("/leads", { page_size: 5 }),
      api.get("/notifications", { limit: 6 }),
      api.get("/analytics/sales").catch(() => ({ by_service: [], orders: 0 })),
    ]);

    const growth = ov.revenue.growth_pct;
    const unpaid = ov.revenue.unpaid || 0;
    const unpaidCount = ov.revenue.unpaid_count || 0;
    const rc = ov.revenue.currency || rev.currency || "GBP"; // reporting currency (your Stripe payout currency)
    kpis.innerHTML = [
      statTile({ label: "Total clients", value: fmtNum(ov.clients.total), iconName: "users", delta: `+${ov.clients.new_this_month} this month` }),
      statTile({ label: "Active clients", value: fmtNum(ov.clients.active), iconName: "heart", delta: "with an open order right now" }),
      statTile({ label: `Revenue this month (${rc})`, value: money(ov.revenue.this_month, rc), iconName: "trending-up", delta: growth === null ? `Last month ${money(ov.revenue.last_month, rc)}` : `${growth >= 0 ? "▲" : "▼"} ${Math.abs(growth)}% vs last month`, dir: growth === null ? "" : growth >= 0 ? "up" : "down" }),
      statTile({ label: "Unpaid invoices", value: fmtNum(unpaidCount), iconName: "credit-card", delta: unpaidCount ? `${money(unpaid, rc)} awaiting payment` : "Everything is paid", dir: unpaidCount ? "down" : "" }),
      statTile({ label: `Total revenue (${rc})`, value: money(ov.revenue.total, rc), iconName: "dollar", delta: Object.entries(ov.revenue.by_currency || {}).map(([c, v]) => money(v, c)).join(" · ") || "no payments yet" }),
      statTile({ label: "Pending requests", value: fmtNum(ov.requests.pending), iconName: "inbox", delta: `${ov.requests.accepted} accepted · ${ov.requests.rejected} rejected` }),
      statTile({ label: "In progress", value: fmtNum(ov.requests.in_progress + ov.requests.review), iconName: "activity", delta: `${ov.requests.review} awaiting your review` }),
      statTile({ label: "Completed", value: fmtNum(ov.requests.completed), iconName: "check-circle", delta: `Avg turnaround ${hoursLabel(ov.requests.avg_turnaround_hours)}` }),
      statTile({ label: "Completion rate", value: pct(ov.requests.completion_rate), iconName: "award" }),
      statTile({ label: "Lead conversion", value: pct(ov.conversion.rate), iconName: "target", delta: `${ov.conversion.converted} of ${ov.conversion.leads} leads · ${ov.conversion.leads_this_month} new` }),
      statTile({ label: "Agent success", value: pct(ov.agents.success_rate), iconName: "cpu", delta: `${fmtNum(ov.agents.tasks_completed)} tasks · ${ov.agents.running} running` }),
    ].join("");

    /* charts */
    const revLabels = rev.series.map((s) => s.label);
    const revSeries = [{ name: "Revenue", data: rev.series.map((s) => s.revenue) }];
    const c1 = chartCard(charts, { title: "Revenue", sub: `Paid invoices by month, last 12 months (${rc})`, height: 240, legend: legendHtml([{ name: "Revenue" }]), table: seriesTable(revLabels, revSeries, { labelHead: "Month", fmt: (v) => money(v, rc) }) });
    lineChart(c1.canvas, { labels: revLabels, series: revSeries, yFormat: (v) => (v >= 1000 ? `${money(v / 1000, rc)}k` : money(v, rc)) });

    const rLabels = reqs.submitted.map((d) => d.date.slice(5));
    const rSeries = [
      { name: "Submitted", data: reqs.submitted.map((d) => d.value) },
      { name: "Completed", data: reqs.completed.map((d) => d.value) },
    ];
    const c2 = chartCard(charts, { title: "Requests", sub: "Submitted vs completed, last 30 days", height: 240, legend: legendHtml(rSeries), table: seriesTable(rLabels, rSeries, { labelHead: "Day" }) });
    lineChart(c2.canvas, { labels: rLabels, series: rSeries, area: false });

    const topSvc = (sales.by_service || []).slice(0, 8);
    if (topSvc.length) {
      const sc = sales.currency || rc;
      const svcSeries = [{ name: `Revenue (${sc})`, data: topSvc.map((s) => Math.round(s.revenue ?? s.revenue_usd)) }];
      const c3 = chartCard(charts, { title: "Revenue by service", sub: `Paid orders, all time (${sc})`, height: Math.max(200, topSvc.length * 30), table: seriesTable(topSvc.map((s) => s.name), [{ name: `Revenue (${sc})`, data: topSvc.map((s) => s.revenue ?? s.revenue_usd) }, { name: "Orders", data: topSvc.map((s) => s.orders) }], { labelHead: "Service", fmt: (v) => (Number.isInteger(v) && v < 1000 ? v : money(v, sc)) }) });
      barChart(c3.canvas, { labels: topSvc.map((s) => s.name), series: svcSeries, horizontal: true, yFormat: (v) => money(v, sc) });
    }

    /* lists */
    const queue = pending.items;
    lists.innerHTML =
      card(`Pending queue <span class="count-badge ${queue.length ? "" : "is-zero"}">${pending.total}</span>`, `<div class="list" id="queue">${
        queue.length
          ? queue.map((r) => `<div class="list-item" data-title="${esc(r.title)}">
              <div class="flex-1 min-w-0"><a class="title" href="#/requests/${r.id}">${esc(r.title)}</a><div class="meta">${esc(r.company_name)} · ${esc(r.service_name)} · ${timeAgo(r.submitted_at)} ${priorityBadge(r.priority)} ${priceBadge(r)}</div></div>
              <div class="flex gap-1">${actionButtons(r, { only: ["accept", "reject"] })}</div></div>`).join("")
          : emptyState("inbox", "Queue is empty", "New client requests will appear here instantly.")
      }</div>`, { actions: `<a href="#/requests" class="btn btn-ghost btn-sm">All requests ${icon("arrow-right", "icon-sm")}</a>` }) +
      `<div class="flex flex-col gap-6">` +
      card("AI agents", `<div class="card-body">
          <div class="flex gap-6 wrap">
            <div><div class="text-xs text-3 uppercase">Running</div><div class="text-xl font-bold">${agents.running.length}</div></div>
            <div><div class="text-xs text-3 uppercase">Paused</div><div class="text-xl font-bold">${agents.paused.length}</div></div>
            <div><div class="text-xs text-3 uppercase">Stopped</div><div class="text-xl font-bold">${agents.stopped.length}</div></div>
            <div><div class="text-xs text-3 uppercase">Errors</div><div class="text-xl font-bold ${agents.errors.length ? "text-danger" : ""}">${agents.errors.length}</div></div>
            <div><div class="text-xs text-3 uppercase">Tasks done</div><div class="text-xl font-bold">${fmtNum(agents.tasks_completed)}</div></div>
            <div><div class="text-xs text-3 uppercase">Success</div><div class="text-xl font-bold">${pct(agents.success_rate)}</div></div>
          </div>
          <div class="mt-4 flex gap-2 wrap">${agents.running.map((k) => `<span class="badge agent-running"><span class="live-dot"></span>${esc(titleCase(k))}</span>`).join("")}${agents.errors.map((k) => `<span class="badge agent-error">${esc(titleCase(k))}</span>`).join("")}${!agents.running.length && !agents.errors.length ? '<span class="text-sm text-3">All agents idle.</span>' : ""}</div>
        </div>`, { actions: `<a href="#/agents" class="btn btn-ghost btn-sm">Control center ${icon("arrow-right", "icon-sm")}</a>` }) +
      card("Latest leads", `<div class="list">${
        leads.items.length
          ? leads.items.map((l) => `<div class="list-item"><div class="flex-1 min-w-0"><a class="title" href="#/leads/${l.id}">${esc(l.company_name)}</a><div class="meta">${esc(l.industry || "—")} · ${esc(l.contact_email || "no email")}</div></div><span class="badge">${l.score}/100</span><span class="badge">${esc(titleCase(l.status))}</span></div>`).join("")
          : emptyState("target", "No leads yet", "Run the Lead Agent to find prospects.")
      }</div>`, { actions: `<a href="#/leads" class="btn btn-ghost btn-sm">All leads ${icon("arrow-right", "icon-sm")}</a>` }) +
      card("Recent notifications", `<div class="list">${
        notes.length
          ? notes.map((n) => `<div class="list-item ${n.is_read ? "" : "font-semibold"}"><div class="flex-1 min-w-0"><div class="title truncate">${esc(n.title)}</div><div class="meta">${esc(n.body || "")}</div></div><span class="text-xs text-4">${timeAgo(n.created_at)}</span></div>`).join("")
          : emptyState("bell", "No notifications")
      }</div>`, { actions: `<a href="#/notifications" class="btn btn-ghost btn-sm">All ${icon("arrow-right", "icon-sm")}</a>` }) +
      `</div>`;

    bindActions(qs("#queue", page), {
      onDone: (updated) => {
        const row = qs(`[data-title="${CSS.escape(updated.title)}"]`, page);
        if (row) row.remove();
        if (!qs("#queue .list-item", page)) qs("#queue", page).innerHTML = emptyState("inbox", "Queue is empty", "New client requests will appear here instantly.");
      },
    });

    const refresh = () => {
      api.get("/requests", { status: "pending", page_size: 8 }).then((p) => {
        const q = qs("#queue", page);
        if (!q) return;
        q.innerHTML = p.items.length
          ? p.items.map((r) => `<div class="list-item" data-title="${esc(r.title)}"><div class="flex-1 min-w-0"><a class="title" href="#/requests/${r.id}">${esc(r.title)}</a><div class="meta">${esc(r.company_name)} · ${esc(r.service_name)} · ${timeAgo(r.submitted_at)} ${priorityBadge(r.priority)} ${priceBadge(r)}</div></div><div class="flex gap-1">${actionButtons(r, { only: ["accept", "reject"] })}</div></div>`).join("")
          : emptyState("inbox", "Queue is empty", "New client requests will appear here instantly.");
      }).catch(() => {});
    };
    document.addEventListener("df:request_update", refresh);
    cleanups.push(() => document.removeEventListener("df:request_update", refresh));
  } catch (err) {
    kpis.innerHTML = errorBlock(err);
  }

  return () => cleanups.forEach((fn) => fn());
}
