/* Billing: pay-per-request invoices and payments */
import { api, errorMessage } from "../core/api.js";
import { esc, icon, qs, qsa, h, toast, modal, drawer, setLoading, fmtDate, fmtDateTime, titleCase } from "../core/ui.js";
import { pageHeader, statTile, dataTable, pager, getClients, loadingBlock, errorBlock, money, moneyCents, invalidateClients } from "./shared.js";

const PAY_STATUS_CLS = { paid: "badge-success", pending: "badge-warning", failed: "badge-danger", refunded: "" };
const CURRENCIES = ["USD", "GBP", "INR"];

const PROVIDER_LABEL = { stripe: "Stripe", manual: "Recorded manually", mock: "Test (mock provider)", free: "Free", pending: "Not paid yet" };
const METHOD_ICON = { card: "credit-card", manual: "edit", none: "clock", test: "zap", free: "check-circle" };
const pretty = (v) => titleCase(String(v || "").replace(/_/g, " "));

function kvRow(label, value, { copy = false, html = false } = {}) {
  if (value === null || value === undefined || value === "") return "";
  const shown = html ? value : esc(String(value));
  const btn = copy ? ` <button type="button" class="btn btn-ghost btn-sm pd-copy" data-copy="${esc(String(value))}" aria-label="Copy ${esc(label)}">Copy</button>` : "";
  return `<dt>${esc(label)}</dt><dd>${shown}${btn}</dd>`;
}

function section(title, rows) {
  const body = rows.join("");
  return body ? `<section class="pd-section"><h4>${esc(title)}</h4><dl class="kv pd-kv">${body}</dl></section>` : "";
}

function paymentDetailHtml(p) {
  const d = p.details || {};
  const card = d.card || {};
  const m = p.method || {};
  const statusCls = PAY_STATUS_CLS[p.status] || "";
  const extra = Object.entries(d.method_details || {}).map(([k, v]) =>
    kvRow(k === "transaction_id" ? `${pretty(d.method_type)} transaction ID` : pretty(k), v, { copy: /id$/i.test(k) })
  );
  const settleCur = d.settlement_currency || p.settled_currency || p.currency;
  const testBadge = d.livemode === false ? `<span class="badge badge-warning">Test mode</span>` : "";
  const methodSub = `${esc(PROVIDER_LABEL[m.provider] || pretty(m.provider))}${d.method_type && d.method_type !== "card" ? ` · ${esc(pretty(d.method_type))}` : ""}`;
  return `<div class="pay-detail">
    <div class="pd-hero">
      <div class="pd-amount">${moneyCents(p.amount, p.currency)}</div>
      <div class="pd-hero-sub"><span class="badge ${statusCls}">${esc(titleCase(p.status))}</span><span>${esc(p.invoice_number || "Invoice")}</span>${testBadge}</div>
      <div class="pd-method">
        <span class="pd-method-icon">${icon(METHOD_ICON[m.kind] || "credit-card")}</span>
        <div><b>${esc(m.summary || "—")}</b><small>${methodSub}</small></div>
      </div>
    </div>
    ${p.details_error ? `<div class="inline-alert warning mt-4">${icon("alert")}<span>${esc(p.details_error)}</span></div>` : ""}
    ${section("Payment method", [
      kvRow("Provider", PROVIDER_LABEL[m.provider] || pretty(m.provider)),
      kvRow("Method", d.method_type ? pretty(d.method_type) : m.provider === "manual" ? "Offline (bank transfer, cash, ...)" : ""),
      card.brand ? kvRow("Card", `${pretty(card.brand)} •••• ${card.last4 || "????"}`) : "",
      card.exp_month ? kvRow("Expires", `${String(card.exp_month).padStart(2, "0")}/${String(card.exp_year || "").slice(-2)}`) : "",
      kvRow("Funding", card.funding ? pretty(card.funding) : ""),
      kvRow("Card country", card.country || ""),
      kvRow("Wallet", card.wallet ? pretty(card.wallet) : ""),
      kvRow("3-D Secure", card.three_d_secure ? pretty(card.three_d_secure) : ""),
      ...extra,
      kvRow("Reference", m.reference || ""),
    ])}
    ${section("Transaction", [
      kvRow("Payment ID", p.provider_payment_id || "", { copy: true }),
      kvRow("Charge ID", d.charge_id || "", { copy: true }),
      kvRow("Stripe status", d.status ? pretty(d.status) : ""),
      kvRow("Network", d.network_status ? pretty(d.network_status) : ""),
      kvRow("Risk level", d.risk_level ? pretty(d.risk_level) : ""),
      kvRow("Result", d.seller_message || ""),
      kvRow("Invoice created", p.created_at ? fmtDateTime(p.created_at) : ""),
      kvRow("Paid", p.paid_at ? fmtDateTime(p.paid_at) : ""),
    ])}
    ${section("Settlement", [
      kvRow("Charged", moneyCents(p.amount, p.currency)),
      d.fee != null ? kvRow("Stripe fee", moneyCents(d.fee, settleCur)) : "",
      d.net != null
        ? kvRow("Net received", `<b>${moneyCents(d.net, settleCur)}</b>`, { html: true })
        : p.settled_amount != null ? kvRow(`In ${p.settled_currency}`, moneyCents(p.settled_amount, p.settled_currency)) : "",
      kvRow("Payout available", d.available_on ? fmtDate(d.available_on) : ""),
    ])}
    ${section("Customer", [
      kvRow("Company", p.company_name || ""),
      kvRow("Contact", p.client_name || ""),
      kvRow("Email", p.client_email || ""),
      kvRow("Paid by", d.billing_name || ""),
      kvRow("Receipt sent to", d.billing_email && d.billing_email !== p.client_email ? d.billing_email : ""),
      kvRow("Billing country", d.billing_country || ""),
    ])}
    ${section("Request", [
      p.request_id
        ? kvRow("Request", `<a href="#/requests/${p.request_id}">${esc(p.request_title || `#${p.request_id}`)}</a>`, { html: true })
        : kvRow("Description", p.description || ""),
      kvRow("Service", p.service_name || ""),
      kvRow("Request status", p.request_status ? pretty(p.request_status) : ""),
    ])}
    ${(p.history || []).length
      ? `<section class="pd-section"><h4>History</h4><ol class="pd-history">${p.history
          .map((e) => `<li><b>${esc(e.title)}</b><span>${e.at ? fmtDateTime(e.at) : ""}${e.body ? ` · ${esc(e.body)}` : ""}</span></li>`)
          .join("")}</ol></section>`
      : ""}
    <div class="pd-actions">
      ${d.receipt_url ? `<a class="btn btn-primary btn-sm" href="${esc(d.receipt_url)}" target="_blank" rel="noopener">${icon("file", "icon-sm")} View receipt</a>` : ""}
      ${d.dashboard_url ? `<a class="btn btn-secondary btn-sm" href="${esc(d.dashboard_url)}" target="_blank" rel="noopener">${icon("external", "icon-sm")} Open in Stripe</a>` : ""}
      ${p.invoice_url ? `<a class="btn btn-secondary btn-sm" href="${esc(p.invoice_url)}" target="_blank" rel="noopener">${icon("external", "icon-sm")} Invoice</a>` : ""}
      ${m.provider === "stripe" ? `<button type="button" class="btn btn-ghost btn-sm" data-refresh>${icon("refresh", "icon-sm")} Refresh from Stripe</button>` : ""}
    </div>
  </div>`;
}

async function openPaymentDetail(id) {
  const d = drawer({ title: "Payment details", body: loadingBlock(5) });
  d.el.classList.add("drawer-wide");
  const load = async (refresh = false) => {
    try {
      const p = await api.get(`/billing/payments/${id}`, refresh ? { refresh: true } : undefined);
      d.body.innerHTML = paymentDetailHtml(p);
      qsa("[data-copy]", d.body).forEach((b) =>
        b.addEventListener("click", async () => {
          try {
            await navigator.clipboard.writeText(b.dataset.copy);
            toast({ title: "Copied", type: "success", timeout: 1500 });
          } catch {
            toast({ title: "Could not copy", type: "error" });
          }
        })
      );
      const r = qs("[data-refresh]", d.body);
      if (r) r.addEventListener("click", () => {
        d.body.innerHTML = loadingBlock(5);
        load(true);
      });
    } catch (err) {
      d.body.innerHTML = errorBlock(err);
    }
  };
  load();
}

export async function render(page, params, query) {
  let payPage = 1;
  let payClient = query.client_id || "";
  let payStatus = query.status || "";

  page.innerHTML = pageHeader("Billing", "Every request is paid individually. Invoices are created when a request is submitted and settled by the client, by Stripe or by you.", `<button class="btn btn-primary" id="manual-pay">${icon("plus")} Record payment</button>`) +
    `<div class="kpi-grid" id="kpis">${loadingBlock(5)}</div>
     <div id="content" class="mt-6"></div>`;
  const content = qs("#content", page);

  async function loadKpis() {
    try {
      const [s, sales] = await Promise.all([api.get("/billing/summary"), api.get("/analytics/sales")]);
      const cur = Object.entries(s.by_currency || {});
      const paidLine = cur.filter(([, b]) => b.paid).map(([c, b]) => money(b.paid, c)).join(" · ") || money(0);
      const pendLine = cur.filter(([, b]) => b.pending).map(([c, b]) => money(b.pending, c)).join(" · ") || money(0);
      qs("#kpis", page).innerHTML = [
        statTile({ label: "Paid revenue", value: `<span style="font-size:var(--fs-xl)">${paidLine}</span>`, iconName: "dollar", delta: "all time, per currency" }),
        statTile({ label: "Awaiting payment", value: `<span style="font-size:var(--fs-xl)">${pendLine}</span>`, iconName: "clock", delta: `${s.unpaid_requests} unpaid request${s.unpaid_requests === 1 ? "" : "s"}`, dir: s.unpaid_requests ? "down" : "" }),
        statTile({ label: "Paid orders", value: sales.paid_orders, iconName: "check-circle" }),
        statTile({ label: "Unpaid orders", value: sales.unpaid_orders, iconName: "alert", dir: sales.unpaid_orders ? "down" : "" }),
        statTile({ label: `Avg order (${sales.currency || "INR"})`, value: money(sales.avg_order ?? sales.avg_order_usd, sales.currency || "INR"), iconName: "trending-up", delta: `${sales.orders} orders total` }),
        statTile({ label: `Received (${(s.settled || {}).currency || "GBP"})`, value: money((s.settled || {}).paid || 0, (s.settled || {}).currency || "GBP"), iconName: "dollar", delta: `${money((s.settled || {}).pending || 0, (s.settled || {}).currency || "GBP")} still unpaid · all currencies converted` }),
      ].join("");
    } catch (err) {
      qs("#kpis", page).innerHTML = errorBlock(err);
    }
  }

  async function loadPayments() {
    content.innerHTML = loadingBlock(4);
    try {
      const clients = await getClients().catch(() => []);
      const data = await api.get("/billing/payments", { client_id: payClient || undefined, status: payStatus || undefined, page: payPage, page_size: 25 });
      content.innerHTML = `<div class="filters"><select class="select" id="f-pay-client"><option value="">All clients</option>${clients.map((c) => `<option value="${c.id}" ${String(c.id) === String(payClient) ? "selected" : ""}>${esc(c.company_name)}</option>`).join("")}</select><select class="select" id="f-pay-status"><option value="">All statuses</option>${["paid", "pending", "failed", "refunded"].map((s) => `<option value="${s}" ${s === payStatus ? "selected" : ""}>${titleCase(s)}</option>`).join("")}</select><span class="ml-auto text-sm text-3">${data.total} invoice${data.total === 1 ? "" : "s"}</span></div>` +
        dataTable({
          columns: [
            { key: "invoice_number", label: "Invoice", render: (p) => `<b>${esc(p.invoice_number || "—")}</b>${p.invoice_url ? ` <a href="${esc(p.invoice_url)}" target="_blank">${icon("external", "icon-sm")}</a>` : ""}<div class="text-xs text-3">${fmtDate(p.created_at)}</div>` },
            { key: "company_name", label: "Client", render: (p) => `<a href="#/clients/${p.client_id}">${esc(p.company_name)}</a>` },
            { key: "request_title", label: "Request", cls: "wrap", render: (p) => (p.request_id ? `<a href="#/requests/${p.request_id}">${esc(p.request_title || `#${p.request_id}`)}</a>` : `<span class="text-3">${esc(p.description || "—")}</span>`) },
            { key: "amount", label: "Amount", render: (p) => `${moneyCents(p.amount, p.currency)} <span class="badge">${esc(p.currency)}</span>` },
            { key: "status", label: "Status", render: (p) => `<span class="badge ${PAY_STATUS_CLS[p.status] || ""}">${esc(titleCase(p.status))}</span>` },
            { key: "provider", label: "Via", render: (p) => `<span class="badge">${esc(p.provider)}</span>` },
            { key: "paid_at", label: "Paid", render: (p) => (p.paid_at ? fmtDateTime(p.paid_at) : "—") },
            { key: "actions", label: "", render: (p) => (p.status === "pending" ? `<button class="btn btn-warning-soft btn-sm" data-mark="${p.id}">${icon("check", "icon-sm")} Mark paid</button>` : "") },
          ],
          rows: data.items,
          rowAttrs: (p) => `class="row-click" data-pay="${p.id}" tabindex="0" title="View payment details"`,
          empty: "No invoices yet. They appear as soon as a client submits a request.",
          emptyIcon: "credit-card",
        });
      if (data.total > 25) content.appendChild(pager({ page: payPage, total: data.total, pageSize: 25, onPage: (p) => { payPage = p; loadPayments(); } }));
      qs("#f-pay-client", content).addEventListener("change", (e) => { payClient = e.target.value; payPage = 1; loadPayments(); });
      qs("#f-pay-status", content).addEventListener("change", (e) => { payStatus = e.target.value; payPage = 1; loadPayments(); });
      const openFromRow = (e) => {
        const row = e.target.closest("tr[data-pay]");
        if (!row || e.target.closest("a, button, select, input")) return;
        if (e.type === "keydown" && e.key !== "Enter" && e.key !== " ") return;
        e.preventDefault();
        openPaymentDetail(Number(row.dataset.pay));
      };
      content.addEventListener("click", openFromRow);
      content.addEventListener("keydown", openFromRow);
      qsa("[data-mark]", content).forEach((b) =>
        b.addEventListener("click", async () => {
          setLoading(b, true);
          try {
            await api.post(`/billing/payments/${b.dataset.mark}/mark-paid`);
            toast({ title: "Marked as paid", type: "success" });
            invalidateClients();
            loadKpis();
            loadPayments();
          } catch (err) {
            toast({ title: "Failed", body: errorMessage(err), type: "error" });
            setLoading(b, false);
          }
        })
      );
    } catch (err) {
      content.innerHTML = errorBlock(err);
    }
  }

  async function openManualPayment() {
    const clients = await getClients().catch(() => []);
    const body = h(`<div class="form-grid">
      <div class="field span-2"><label class="label">Client</label><select class="select" id="m-client">${clients.map((c) => `<option value="${c.id}" data-cur="${esc(c.currency || "USD")}">${esc(c.company_name)}</option>`).join("")}</select></div>
      <div class="field span-2"><label class="label">Request (optional)</label><select class="select" id="m-request"><option value="">Not linked to a request</option></select><span class="hint">Pick an unpaid request to settle its invoice.</span></div>
      <div class="field"><label class="label">Amount</label><input class="input" type="number" min="1" step="0.01" id="m-amount" placeholder="149"></div>
      <div class="field"><label class="label">Currency</label><select class="select" id="m-currency">${CURRENCIES.map((c) => `<option value="${c}">${c}</option>`).join("")}</select></div>
      <div class="field"><label class="label">Status</label><select class="select" id="m-status"><option value="paid">Paid</option><option value="pending">Pending</option><option value="failed">Failed</option><option value="refunded">Refunded</option></select></div>
      <div class="field"><label class="label">Reference / description</label><input class="input" id="m-desc" placeholder="Bank transfer 12 Nov"></div>
    </div>`);
    const footer = h(`<div class="flex gap-2 justify-end w-full"><button class="btn btn-secondary" data-close>Cancel</button><button class="btn btn-primary" id="m-save">Record</button></div>`);
    const m = modal({ title: "Record payment", body, footer });
    const reqSel = qs("#m-request", body);
    async function loadRequests() {
      const cid = qs("#m-client", body).value;
      const opt = qs("#m-client", body).selectedOptions[0];
      if (opt) qs("#m-currency", body).value = opt.dataset.cur || "USD";
      reqSel.innerHTML = `<option value="">Not linked to a request</option>`;
      if (!cid) return;
      try {
        const data = await api.get("/requests", { client_id: cid, page_size: 100 });
        data.items.forEach((r) => {
          const o = document.createElement("option");
          o.value = r.id;
          o.textContent = `#${r.id} ${r.title} — ${money(r.price_amount, r.price_currency)} ${r.is_paid ? "(paid)" : "(unpaid)"}`;
          o.dataset.amount = r.price_amount ?? "";
          o.dataset.cur = r.price_currency || "USD";
          reqSel.appendChild(o);
        });
      } catch {}
    }
    qs("#m-client", body).addEventListener("change", loadRequests);
    reqSel.addEventListener("change", () => {
      const o = reqSel.selectedOptions[0];
      if (o && o.dataset.amount) {
        qs("#m-amount", body).value = o.dataset.amount;
        qs("#m-currency", body).value = o.dataset.cur;
      }
    });
    loadRequests();
    qs("#m-save", footer).onclick = async () => {
      setLoading(qs("#m-save", footer), true);
      try {
        await api.post("/billing/payments", {
          client_id: Number(qs("#m-client", body).value), amount: Number(qs("#m-amount", body).value), currency: qs("#m-currency", body).value,
          description: qs("#m-desc", body).value || null, status: qs("#m-status", body).value, request_id: reqSel.value ? Number(reqSel.value) : null,
        });
        m.close();
        toast({ title: "Payment recorded", type: "success" });
        invalidateClients();
        loadKpis();
        loadPayments();
      } catch (err) {
        toast({ title: "Failed", body: errorMessage(err), type: "error" });
        setLoading(qs("#m-save", footer), false);
      }
    };
  }

  qs("#manual-pay", page).onclick = openManualPayment;
  const onUpdate = () => { loadKpis(); };
  document.addEventListener("df:request_update", onUpdate);
  loadKpis();
  await loadPayments();
  return () => document.removeEventListener("df:request_update", onUpdate);
}
