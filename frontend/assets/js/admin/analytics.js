/* Analytics dashboard */
import { api } from "../core/api.js";
import { esc, icon, qs, qsa, timeAgo, titleCase, STATUS_LABELS, fmtNum } from "../core/ui.js";
import {
  pageHeader, statTile, chartCard, lineChart, barChart, donutChart, legendHtml, seriesTable, itemsTable, dataTable, loadingBlock, errorBlock, money, pct, hoursLabel, card,
} from "./shared.js";

export async function render(page, params, query) {
  let days = Number(query.days) || 30;
  page.innerHTML = pageHeader("Analytics", "Revenue, orders, requests, agents and leads.", `<div class="segmented" id="range">${[7, 30, 90].map((d) => `<button data-days="${d}" class="${d === days ? "active" : ""}">${d}d</button>`).join("")}</div>`) +
    `<div id="body">${loadingBlock(6)}</div>`;
  const body = qs("#body", page);

  async function load() {
    body.innerHTML = loadingBlock(6);
    try {
      const [ov, rev, req, ag, leads, sales] = await Promise.all([
        api.get("/analytics/overview"), api.get("/analytics/revenue", { months: 12 }), api.get("/analytics/requests", { days }),
        api.get("/analytics/agents", { days }), api.get("/analytics/leads", { days }), api.get("/analytics/sales"),
      ]);
      body.innerHTML = `
        <div class="kpi-grid">
          ${statTile({ label: `Total revenue (${ov.revenue.currency || "INR"})`, value: money(ov.revenue.total, ov.revenue.currency || "INR"), iconName: "dollar", delta: `${money(ov.revenue.this_month, ov.revenue.currency || "INR")} this month` })}
          ${statTile({ label: "Paid orders", value: fmtNum(sales.paid_orders), iconName: "check-circle", delta: `${sales.unpaid_orders} unpaid · avg ${money(sales.avg_order ?? sales.avg_order_usd, sales.currency || "INR")}` })}
          ${statTile({ label: "Awaiting payment", value: money(ov.revenue.unpaid || 0), iconName: "credit-card", delta: `${ov.revenue.unpaid_count || 0} invoice${(ov.revenue.unpaid_count || 0) === 1 ? "" : "s"}`, dir: ov.revenue.unpaid_count ? "down" : "" })}
          ${statTile({ label: "Requests", value: fmtNum(ov.requests.total), iconName: "inbox", delta: `${pct(ov.requests.completion_rate)} completed · avg ${hoursLabel(ov.requests.avg_turnaround_hours)}` })}
          ${statTile({ label: "Lead conversion", value: pct(ov.conversion.rate), iconName: "target", delta: `${leads.outreach_sent} outreach · ${pct(leads.reply_rate)} reply rate` })}
        </div>
        <h3 class="mt-8 mb-4">Revenue & requests</h3>
        <div class="dash-grid-2" id="row1"></div>
        <h3 class="mt-8 mb-4">Sales by service & currency</h3>
        <div class="dash-grid-2" id="row-sales"></div>
        <h3 class="mt-8 mb-4">Requests by service & priority</h3>
        <div class="dash-grid" id="row2"></div>
        <h3 class="mt-8 mb-4">Agents</h3>
        <div class="dash-grid" id="row3"></div>
        <h3 class="mt-8 mb-4">Leads</h3>
        <div class="dash-grid-2" id="row4"></div>`;

      /* sales */
      const rs = qs("#row-sales", body);
      const svcs = (sales.by_service || []).slice(0, 10);
      const rc = sales.currency || rev.currency || "GBP"; // reporting currency (your Stripe payout currency)
      const svcRev = [{ name: `Revenue (${rc})`, data: svcs.map((s) => Math.round(s.revenue ?? s.revenue_usd)) }];
      const cs1 = chartCard(rs, { title: "Revenue by service", sub: `Paid orders converted to ${rc}`, height: Math.max(220, svcs.length * 28), table: `<div class="table-wrap"><table class="table"><thead><tr><th>Service</th><th>Orders</th><th>Paid</th><th>Revenue (${rc})</th></tr></thead><tbody>${(sales.by_service || []).map((s) => `<tr><td><a href="#/services/${esc(s.slug)}">${esc(s.name)}</a></td><td>${s.orders}</td><td>${s.paid}</td><td>${money(s.revenue ?? s.revenue_usd, rc)}</td></tr>`).join("") || '<tr><td colspan="4" class="text-3">No paid orders yet</td></tr>'}</tbody></table></div>` });
      barChart(cs1.canvas, { labels: svcs.map((s) => s.name), series: svcRev, horizontal: true, yFormat: (v) => money(v, rc) });
      const curItems = (sales.by_currency || []).map((c) => ({ label: c.currency, value: c.orders }));
      const cs2 = chartCard(rs, { title: "Orders by currency", sub: (sales.by_currency || []).map((c) => `${c.currency}: ${money(c.paid, c.currency)} paid`).join(" · ") || "No orders yet", legend: legendHtml(curItems), table: `<div class="table-wrap"><table class="table"><thead><tr><th>Currency</th><th>Orders</th><th>Paid</th><th>Pending</th></tr></thead><tbody>${(sales.by_currency || []).map((c) => `<tr><td>${esc(c.currency)}</td><td>${c.orders}</td><td>${money(c.paid, c.currency)}</td><td>${money(c.pending, c.currency)}</td></tr>`).join("")}</tbody></table></div>` });
      donutChart(cs2.canvas, { items: curItems, centerLabel: "orders" });

      /* row 1 */
      const r1 = qs("#row1", body);
      const revLabels = rev.series.map((s) => s.label);
      const revSeries = [{ name: "Revenue", data: rev.series.map((s) => s.revenue) }];
      const c1 = chartCard(r1, { title: "Revenue by month", sub: `Paid invoices, last 12 months (${rc})`, table: seriesTable(revLabels, revSeries, { labelHead: "Month", fmt: (v) => money(v, rc) }) });
      barChart(c1.canvas, { labels: revLabels, series: revSeries, yFormat: (v) => (v >= 1000 ? `${money(v / 1000, rc)}k` : money(v, rc)), xTicks: 12 });

      const rLabels = req.submitted.map((d) => d.date.slice(5));
      const rSeries = [{ name: "Submitted", data: req.submitted.map((d) => d.value) }, { name: "Completed", data: req.completed.map((d) => d.value) }];
      const c2 = chartCard(r1, { title: "Submitted vs completed", sub: `Per day, last ${days} days`, legend: legendHtml(rSeries), table: seriesTable(rLabels, rSeries, { labelHead: "Day" }) });
      lineChart(c2.canvas, { labels: rLabels, series: rSeries, area: false });

      /* row 2 */
      const r2 = qs("#row2", body);
      const top = req.by_service.slice(0, 10);
      const svcSeries = [{ name: "Total", data: top.map((s) => s.total) }];
      const c3 = chartCard(r2, { title: "Requests by service", sub: "Top 10 all time", height: Math.max(220, top.length * 28), table: `<div class="table-wrap"><table class="table"><thead><tr><th>Service</th><th>Total</th><th>Pending</th><th>Completed</th></tr></thead><tbody>${req.by_service.map((s) => `<tr><td><a href="#/services/${esc(s.slug)}">${esc(s.name)}</a></td><td>${s.total}</td><td>${s.pending}</td><td>${s.completed}</td></tr>`).join("")}</tbody></table></div>` });
      barChart(c3.canvas, { labels: top.map((s) => s.name), series: svcSeries, horizontal: true });
      const prItems = Object.entries(req.by_priority).map(([k, v]) => ({ label: titleCase(k), value: v }));
      const c4 = chartCard(r2, { title: "By priority", sub: "All requests", legend: legendHtml(prItems), table: itemsTable(prItems) });
      donutChart(c4.canvas, { items: prItems, centerLabel: "requests" });

      /* row 3 */
      const r3 = qs("#row3", body);
      const agentTable = `<div class="card">${dataTable({
        columns: [
          { key: "name", label: "Agent", render: (a) => `<b>${esc(a.name)}</b>` },
          { key: "status", label: "Status", render: (a) => `<span class="badge agent-${esc(a.status)}">${esc(titleCase(a.status))}</span>` },
          { key: "runs", label: `Runs (${days}d)` },
          { key: "failed_runs", label: "Failed" },
          { key: "avg_duration_ms", label: "Avg duration", render: (a) => (a.avg_duration_ms ? `${(a.avg_duration_ms / 1000).toFixed(1)}s` : "—") },
          { key: "tokens", label: "Tokens", render: (a) => fmtNum(a.tokens) },
          { key: "success_rate", label: "Success", render: (a) => `<div class="score-bar"><div class="progress"><span style="width:${Math.min(100, a.success_rate)}%"></span></div><b>${pct(a.success_rate)}</b></div>` },
          { key: "last_run_at", label: "Last run", render: (a) => (a.last_run_at ? timeAgo(a.last_run_at) : "—") },
        ],
        rows: ag.agents,
        empty: "No agents",
      })}</div>`;
      r3.insertAdjacentHTML("beforeend", agentTable);
      const actLabels = ag.activity.map((d) => d.date.slice(5));
      const actSeries = [{ name: "Completed steps", data: ag.activity.map((d) => d.value) }];
      const c5 = chartCard(r3, { title: "Agent activity", sub: "Completed steps per day", table: seriesTable(actLabels, actSeries, { labelHead: "Day" }) });
      lineChart(c5.canvas, { labels: actLabels, series: actSeries });

      /* row 4 */
      const r4 = qs("#row4", body);
      const leadItems = Object.entries(leads.by_status).map(([k, v]) => ({ label: titleCase(k), value: v }));
      const c6 = chartCard(r4, { title: "Leads by status", sub: `${leads.total} total · avg score ${leads.avg_score}`, legend: legendHtml(leadItems), table: itemsTable(leadItems) });
      donutChart(c6.canvas, { items: leadItems, centerLabel: "leads" });
      const genLabels = leads.generated.map((d) => d.date.slice(5));
      const genSeries = [{ name: "Leads", data: leads.generated.map((d) => d.value) }];
      const c7 = chartCard(r4, { title: "Leads generated", sub: `Per day · reply rate ${pct(leads.reply_rate)} (${leads.replies}/${leads.outreach_sent})`, table: seriesTable(genLabels, genSeries, { labelHead: "Day" }) });
      lineChart(c7.canvas, { labels: genLabels, series: genSeries });
    } catch (err) {
      body.innerHTML = errorBlock(err);
    }
  }

  qs("#range", page).addEventListener("click", (e) => {
    const b = e.target.closest("[data-days]");
    if (!b) return;
    days = Number(b.dataset.days);
    qsa("[data-days]", page).forEach((x) => x.classList.toggle("active", x === b));
    load();
  });
  await load();
}
