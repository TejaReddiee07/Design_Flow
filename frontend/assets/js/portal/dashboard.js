/* Portal dashboard (pay per request) */
import { api } from "../core/api.js";
import { icon, esc, qs, qsa, fmtNum, skeletonRows, emptyState } from "../core/ui.js";
import { sparkline, destroyChart } from "../core/charts.js";
import { state, getServices, pageHeader, requestRow, errorBox, fmtPrice, payRequest } from "./shared.js";
import { latestCovers } from "./designs.js";

export async function renderDashboard(page) {
  const user = state.user;
  const first = (user.full_name || "").split(" ")[0] || "there";
  page.innerHTML = `
    ${pageHeader({ title: `Welcome back, ${first}`, sub: user.client ? user.client.company_name : "", actions: `<a class="btn btn-primary" href="#/new">${icon("plus")} Order a design</a>` })}
    <div class="stats-grid" id="stats">${skeletonRows(1)}</div>
    <div class="dash-grid">
      <div class="flex flex-col gap-6">
        <div class="card" id="unpaid-card" hidden><div class="card-header"><h3>${icon("credit-card", "icon-sm")} Awaiting payment</h3><a class="btn btn-ghost btn-sm" href="#/invoices">All invoices ${icon("arrow-right", "icon-sm")}</a></div><div class="card-body" id="unpaid-body"></div></div>
        <div class="card" id="designs-card" hidden><div class="card-header"><h3>Latest designs</h3><a class="btn btn-ghost btn-sm" href="#/designs">Your designs ${icon("arrow-right", "icon-sm")}</a></div><div class="card-body" id="designs-body"></div></div>
        <div class="card" id="active-card"><div class="card-header"><h3>In progress</h3><a class="btn btn-ghost btn-sm" href="#/requests">All requests ${icon("arrow-right", "icon-sm")}</a></div><div class="card-body" id="active-body">${skeletonRows(3)}</div></div>
        <div class="card" id="done-card"><div class="card-header"><h3>Recently completed</h3></div><div class="card-body" id="done-body">${skeletonRows(2)}</div></div>
      </div>
      <div class="flex flex-col gap-6">
        <div class="card"><div class="card-header"><h3>How it works</h3></div><div class="card-body">
          <ol class="how-steps">
            <li><i>1</i><div><b>Pick a service</b><span>19 services, each with a fixed price and delivery time.</span></div></li>
            <li><i>2</i><div><b>Send your brief</b><span>The form asks exactly what we need. Attach references.</span></div></li>
            <li><i>3</i><div><b>Pay per request</b><span>No subscription. You only pay for what you order.</span></div></li>
            <li><i>4</i><div><b>Agents + designer deliver</b><span>AI agents research and draft, your designer finishes, you download.</span></div></li>
          </ol>
          <a class="btn btn-gradient btn-block mt-4" href="#/new">${icon("plus")} Order a design</a>
        </div></div>
        <div class="card"><div class="card-header"><h3>Submissions, last 30 days</h3></div><div class="card-body"><canvas class="spark" id="spark"></canvas><p class="text-xs text-3 mt-2" id="spark-label"></p></div></div>
        <div class="card"><div class="card-body">
          <h4>Need something quick?</h4>
          <p class="text-3 text-sm mt-2">Thumbnails, banners and single social posts are delivered in about a day.</p>
          <div class="flex gap-2 wrap mt-4"><a class="btn btn-secondary btn-sm" href="#/new?service=youtube-thumbnail-design">Thumbnail</a><a class="btn btn-secondary btn-sm" href="#/new?service=instagram-post-design">Instagram post</a><a class="btn btn-secondary btn-sm" href="#/new?service=website-banner-design">Banner</a></div>
        </div></div>
      </div>
    </div>`;

  let spark = null;

  try {
    await getServices();
  } catch {}

  const [stats, active, done, all, library] = await Promise.allSettled([
    api.get("/analytics/my-stats"),
    api.get("/requests", { status: "accepted,in_progress,review", page_size: 10 }),
    api.get("/requests", { status: "completed", page_size: 5 }),
    api.get("/requests", { page_size: 50 }),
    api.get("/library/me"),
  ]);

  /* latest designs */
  if (library.status === "fulfilled") {
    const covers = latestCovers(library.value, 4);
    if (covers.length) {
      qs("#designs-card", page).hidden = false;
      qs("#designs-body", page).innerHTML = `<div class="yd-strip">${covers.map((c) => `<a href="#/designs" title="${esc(c.title)}"><span class="thumb"><img src="${esc(c.src)}" alt="${esc(c.title)}" loading="lazy"></span><span class="cap">${esc(c.title)}<small>${esc(c.service)}</small></span></a>`).join("")}</div>`;
    }
  }

  /* stats */
  const statsEl = qs("#stats", page);
  if (stats.status === "fulfilled") {
    const s = stats.value;
    const r = s.requests || {};
    const cur = s.currency || "USD";
    const unpaid = s.unpaid || { count: 0, amount: 0 };
    statsEl.innerHTML = `
      <div class="stat"><span class="stat-label">${icon("inbox", "icon-sm")} Total requests</span><span class="stat-value">${fmtNum(r.total || 0)}</span><span class="stat-delta">${r.pending || 0} pending</span></div>
      <div class="stat"><span class="stat-label">${icon("activity", "icon-sm")} Active now</span><span class="stat-value">${fmtNum(r.active || 0)}</span><span class="stat-delta">${r.review || 0} in review</span></div>
      <div class="stat"><span class="stat-label">${icon("check-circle", "icon-sm")} Completed</span><span class="stat-value">${fmtNum(r.completed || 0)}</span><span class="stat-delta">${s.avg_turnaround_hours != null ? `avg ${Math.round(s.avg_turnaround_hours)}h turnaround` : "accepted → delivered"}</span></div>
      <div class="stat"><span class="stat-label">${icon("alert", "icon-sm")} Unpaid</span><span class="stat-value">${fmtNum(unpaid.count || 0)}</span><span class="stat-delta ${unpaid.count ? "down" : ""}">${unpaid.count ? fmtPrice(unpaid.amount, cur) + " outstanding" : "all settled"}</span></div>
      <div class="stat"><span class="stat-label">${icon("dollar", "icon-sm")} Total spent</span><span class="stat-value">${fmtPrice(s.spent || 0, cur)}</span><span class="stat-delta">paid requests</span></div>`;
    const canvas = qs("#spark", page);
    const data = (s.recent || []).map((d) => d.value);
    if (canvas) spark = sparkline(canvas, data);
    const total30 = data.reduce((a, b) => a + b, 0);
    qs("#spark-label", page).textContent = `${total30} request${total30 === 1 ? "" : "s"} submitted in the last 30 days`;
  } else {
    statsEl.innerHTML = errorBox(stats.reason);
  }

  /* unpaid */
  if (all.status === "fulfilled") {
    const unpaid = all.value.items.filter((r) => r.price_amount && !r.is_paid && r.status !== "rejected");
    const card = qs("#unpaid-card", page);
    if (unpaid.length) {
      card.hidden = false;
      qs("#unpaid-body", page).innerHTML = `<div class="req-list">${unpaid.map((r) => `<div class="req-row unpaid-row">
        <div class="min-w-0 flex-1"><div class="ttl truncate"><a href="#/requests/${r.id}">${esc(r.title)}</a></div><div class="meta"><span>${esc(r.service_name)}</span><span>${r.turnaround_days}-day delivery after payment</span></div></div>
        <b class="req-price">${fmtPrice(r.price_amount, r.price_currency)}</b>
        <button class="btn btn-primary btn-sm" data-pay="${r.id}">${icon("credit-card", "icon-sm")} Pay now</button>
      </div>`).join("")}</div>`;
      qsa("[data-pay]", card).forEach((b) => b.addEventListener("click", async () => {
        const res = await payRequest(Number(b.dataset.pay), b);
        if (res) renderDashboard(page);
      }));
    }
  }

  /* active */
  const activeEl = qs("#active-body", page);
  if (active.status === "fulfilled") {
    const items = active.value.items;
    activeEl.innerHTML = items.length ? `<div class="req-list">${items.map(requestRow).join("")}</div>` : emptyState("inbox", "Nothing in progress", "Order a design and it will show up here once accepted.") + `<p class="text-center"><a class="btn btn-primary btn-sm" href="#/new">Order a design</a></p>`;
  } else activeEl.innerHTML = errorBox(active.reason);

  /* done */
  const doneEl = qs("#done-body", page);
  if (done.status === "fulfilled") {
    const items = done.value.items;
    doneEl.innerHTML = items.length ? `<div class="req-list">${items.map(requestRow).join("")}</div>` : `<p class="text-3 text-sm">No completed requests yet.</p>`;
  } else doneEl.innerHTML = errorBox(done.reason);

  const onUpdate = () => renderDashboard(page);
  document.addEventListener("df:request_update", onUpdate);
  return () => {
    document.removeEventListener("df:request_update", onUpdate);
    const c = qs("#spark", page);
    if (c) destroyChart(c);
  };
}
