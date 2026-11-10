/* Invoices & payments (one invoice per request) */
import { api } from "../core/api.js";
import { icon, esc, qs, qsa, fmtDate, titleCase, skeletonRows, emptyState } from "../core/ui.js";
import { pageHeader, errorBox, fmtPrice, payRequest, clientCurrency } from "./shared.js";

const BADGE = { paid: "badge-success", pending: "badge-warning", failed: "badge-danger", refunded: "" };

export async function renderInvoices(page) {
  page.innerHTML = `${pageHeader({ title: "Invoices & payments", sub: "One invoice per request. Pay by card (secure checkout) or ask us for bank details.", actions: `<a class="btn btn-primary" href="#/new">${icon("plus")} Order a design</a>` })}<div id="summary"></div><div id="list">${skeletonRows(4)}</div>`;
  const el = qs("#list", page);
  const sum = qs("#summary", page);
  try {
    const [rows, summary] = await Promise.all([api.get("/billing/invoices"), api.get("/billing/summary").catch(() => null)]);
    if (summary) {
      const cur = clientCurrency();
      const c = (summary.by_currency || {})[cur] || Object.values(summary.by_currency || {})[0] || { paid: 0, pending: 0, count_paid: 0, count_pending: 0 };
      const curKey = (summary.by_currency || {})[cur] ? cur : Object.keys(summary.by_currency || {})[0] || cur;
      sum.innerHTML = `<div class="stats-grid mb-6" style="grid-template-columns:repeat(3,minmax(0,1fr))">
        <div class="stat"><span class="stat-label">${icon("dollar", "icon-sm")} Total paid</span><span class="stat-value">${fmtPrice(c.paid, curKey)}</span><span class="stat-delta">${c.count_paid} invoice${c.count_paid === 1 ? "" : "s"}</span></div>
        <div class="stat"><span class="stat-label">${icon("alert", "icon-sm")} Outstanding</span><span class="stat-value">${fmtPrice(c.pending, curKey)}</span><span class="stat-delta ${c.count_pending ? "down" : ""}">${c.count_pending ? `${c.count_pending} awaiting payment` : "nothing due"}</span></div>
        <div class="stat"><span class="stat-label">${icon("credit-card", "icon-sm")} Currency</span><span class="stat-value">${esc(curKey)}</span><span class="stat-delta">change in <a href="#/settings">Settings</a></span></div>
      </div>`;
    }
    if (!rows.length) {
      el.innerHTML = emptyState("credit-card", "No invoices yet", "An invoice is created for every request you order.");
      return;
    }
    el.innerHTML = `<div class="table-wrap"><table class="table"><thead><tr><th>Invoice</th><th>Request</th><th>Amount</th><th>Status</th><th>Date</th><th></th></tr></thead><tbody>${rows
      .map((p) => `<tr>
        <td><b>${esc(p.invoice_number || `#${p.id}`)}</b><div class="text-xs text-3">${esc(p.provider === "pending" ? "awaiting payment" : titleCase(p.provider))}</div></td>
        <td class="wrap">${p.request_id ? `<a href="#/requests/${p.request_id}">${esc(p.request_title || p.description || `Request #${p.request_id}`)}</a>` : esc(p.description || "")}</td>
        <td><b>${fmtPrice(p.amount, p.currency)}</b></td>
        <td><span class="badge ${BADGE[p.status] || ""}">${esc(titleCase(p.status))}</span></td>
        <td>${p.paid_at ? fmtDate(p.paid_at) : fmtDate(p.created_at)}</td>
        <td class="text-right"><div class="flex gap-2 justify-end">${p.status === "pending" && p.request_id ? `<button class="btn btn-primary btn-sm" data-pay="${p.request_id}">${icon("credit-card", "icon-sm")} Pay</button>` : ""}${p.invoice_url ? `<a class="btn btn-ghost btn-sm" href="${esc(p.invoice_url)}" target="_blank" rel="noopener">${icon("external", "icon-sm")} Receipt</a>` : ""}</div></td>
      </tr>`)
      .join("")}</tbody></table></div>`;
    qsa("[data-pay]", el).forEach((b) => b.addEventListener("click", async () => {
      const res = await payRequest(Number(b.dataset.pay), b);
      if (res) renderInvoices(page);
    }));
  } catch (err) {
    el.innerHTML = errorBox(err);
  }
}
