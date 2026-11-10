/* Support tickets */
import { api, errorMessage } from "../core/api.js";
import { esc, icon, qs, qsa, h, toast, setLoading, timeAgo, fmtDateTime, titleCase, priorityBadge, nl2br } from "../core/ui.js";
import { pageHeader, dataTable, loadingBlock, errorBlock, card, emptyState } from "./shared.js";

const T_CLS = { open: "badge-danger", pending: "badge-warning", resolved: "badge-success", closed: "" };

export function ticketBadge(s) {
  return `<span class="badge ${T_CLS[s] || ""}">${esc(titleCase(s))}</span>`;
}

export async function render(page, params, query) {
  let status = query.status || "";
  page.innerHTML = pageHeader("Support", "Tickets raised by clients from their portal.") +
    `<div class="filters"><div class="segmented" id="status-seg">${["", "open", "pending", "resolved", "closed"].map((s) => `<button data-status="${s}" class="${s === status ? "active" : ""}">${s ? titleCase(s) : "All"}</button>`).join("")}</div><span class="ml-auto text-sm text-3" id="count"></span></div>
     <div id="content">${loadingBlock(4)}</div>`;
  const content = qs("#content", page);

  async function load() {
    try {
      const rows = await api.get("/support/tickets", { status: status || undefined });
      qs("#count", page).textContent = `${rows.length} ticket${rows.length === 1 ? "" : "s"}`;
      content.innerHTML = dataTable({
        columns: [
          { key: "subject", label: "Subject", cls: "wrap", render: (t) => `<a href="#/support/${t.id}"><b>${esc(t.subject)}</b></a><div class="text-xs text-3">${esc((t.messages && t.messages[t.messages.length - 1] && t.messages[t.messages.length - 1].body) || "").slice(0, 90)}</div>` },
          { key: "company_name", label: "Client", render: (t) => `<a href="#/clients/${t.client_id}">${esc(t.company_name)}</a>` },
          { key: "status", label: "Status", render: (t) => ticketBadge(t.status) },
          { key: "priority", label: "Priority", render: (t) => priorityBadge(t.priority) },
          { key: "category", label: "Category", render: (t) => (t.category ? `<span class="badge">${esc(t.category)}</span>` : "—") },
          { key: "messages", label: "Messages", render: (t) => (t.messages || []).length },
          { key: "updated_at", label: "Updated", render: (t) => timeAgo(t.updated_at) },
        ],
        rows,
        empty: "No tickets",
        emptyIcon: "life-buoy",
        rowAttrs: (t) => `class="clickable" data-ticket="${t.id}"`,
      });
      qsa("[data-ticket]", content).forEach((tr) => tr.addEventListener("click", (e) => { if (!e.target.closest("a")) location.hash = `/support/${tr.dataset.ticket}`; }));
    } catch (err) {
      content.innerHTML = errorBlock(err);
    }
  }

  qs("#status-seg", page).addEventListener("click", (e) => {
    const b = e.target.closest("[data-status]");
    if (!b) return;
    status = b.dataset.status;
    qsa("[data-status]", page).forEach((x) => x.classList.toggle("active", x === b));
    load();
  });
  const onNotif = (e) => e.detail && e.detail.type === "support" && load();
  document.addEventListener("df:notification", onNotif);
  await load();
  return () => document.removeEventListener("df:notification", onNotif);
}

export async function renderDetail(page, params) {
  const id = Number(params.id);
  page.innerHTML = loadingBlock(4);
  let t = null;

  async function load() {
    t = await api.get(`/support/tickets/${id}`);
  }

  function draw() {
    page.innerHTML = `<div class="detail-head">
        <div><div class="breadcrumb mb-2"><a href="#/support">Support</a><span>/</span><span>#${t.id}</span></div><h1>${esc(t.subject)}</h1>
          <div class="flex gap-2 mt-3 wrap">${ticketBadge(t.status)}${priorityBadge(t.priority)}${t.category ? `<span class="badge">${esc(t.category)}</span>` : ""}<span class="badge">${icon("users", "icon-sm")} <a href="#/clients/${t.client_id}">${esc(t.company_name)}</a></span><span class="text-xs text-3">opened ${fmtDateTime(t.created_at)}${t.resolved_at ? ` · resolved ${fmtDateTime(t.resolved_at)}` : ""}</span></div></div>
        <div class="action-bar"><a href="#/chat?client_id=${t.client_id}" class="btn btn-secondary">${icon("message")} Chat</a><select class="select" id="status-select" style="width:auto">${["open", "pending", "resolved", "closed"].map((s) => `<option value="${s}" ${s === t.status ? "selected" : ""}>${titleCase(s)}</option>`).join("")}</select></div>
      </div>
      <div class="dash-grid">
        <div>
          ${card("Conversation", `<div class="card-body">${(t.messages || []).map((m) => `<div class="ticket-msg ${m.sender === "admin" ? "admin" : ""}"><div class="who"><b>${esc(m.name || titleCase(m.sender))}</b><span>${fmtDateTime(m.at)}</span></div>${nl2br(m.body)}</div>`).join("") || emptyState("message", "No messages")}</div>`)}
          <div class="card mt-5"><div class="card-header"><h3>Reply</h3></div><div class="card-body">
            <textarea class="textarea" id="reply" placeholder="Write your reply to the client…"></textarea>
            <div class="flex items-center gap-3 mt-3 wrap"><select class="select" id="reply-status" style="width:auto"><option value="">Keep status</option><option value="pending">Mark pending</option><option value="resolved">Mark resolved</option><option value="closed">Close</option></select><button class="btn btn-primary ml-auto" id="send">${icon("send", "icon-sm")} Send reply</button></div>
          </div></div>
        </div>
        <div>${card("Details", `<div class="card-body"><dl class="kv" style="grid-template-columns:110px 1fr"><dt>Client</dt><dd><a href="#/clients/${t.client_id}">${esc(t.company_name)}</a></dd><dt>Status</dt><dd>${esc(titleCase(t.status))}</dd><dt>Priority</dt><dd>${esc(titleCase(t.priority))}</dd><dt>Category</dt><dd>${esc(t.category || "—")}</dd><dt>Opened</dt><dd>${fmtDateTime(t.created_at)}</dd><dt>Updated</dt><dd>${fmtDateTime(t.updated_at)}</dd></dl></div>`)}</div>
      </div>`;
    qs("#status-select", page).addEventListener("change", async (e) => {
      try {
        t = await api.patch(`/support/tickets/${id}`, null, { status: e.target.value });
        toast({ title: "Status updated", type: "success", timeout: 2000 });
        draw();
      } catch (err) {
        toast({ title: "Failed", body: errorMessage(err), type: "error" });
      }
    });
    qs("#send", page).onclick = async () => {
      const msg = qs("#reply", page).value.trim();
      if (!msg) return;
      const btn = qs("#send", page);
      setLoading(btn, true);
      try {
        t = await api.post(`/support/tickets/${id}/reply`, { message: msg, status: qs("#reply-status", page).value || null });
        toast({ title: "Reply sent", type: "success" });
        draw();
      } catch (err) {
        toast({ title: "Failed", body: errorMessage(err), type: "error" });
        setLoading(btn, false);
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
