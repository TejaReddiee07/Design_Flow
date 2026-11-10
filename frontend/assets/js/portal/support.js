/* Support tickets */
import { api, errorMessage } from "../core/api.js";
import { icon, esc, qs, h, modal, confirmDialog, toast, setLoading, fmtDateTime, timeAgo, titleCase, priorityBadge, skeletonRows, emptyState } from "../core/ui.js";
import { pageHeader, errorBox, reportError } from "./shared.js";

const STATUS_BADGE = { open: "badge-info", pending: "badge-warning", resolved: "badge-success", closed: "" };

export async function renderSupport(page) {
  page.innerHTML = `${pageHeader({ title: "Support", sub: "Billing, account or anything that isn't a design request.", actions: `<button class="btn btn-primary" id="btn-new">${icon("plus")} New ticket</button>` })}
    <div class="inline-alert mb-6">${icon("info")}<span>For questions about a specific design request, use <a href="#/chat">Chat</a> or the request page. Tickets are for account and billing help.</span></div>
    <div id="list">${skeletonRows(3)}</div>`;

  async function load() {
    const el = qs("#list", page);
    try {
      const rows = await api.get("/support/tickets");
      el.innerHTML = rows.length
        ? `<div class="table-wrap"><table class="table"><thead><tr><th>Subject</th><th>Status</th><th>Priority</th><th>Category</th><th>Updated</th></tr></thead><tbody>${rows
            .map((t) => `<tr class="clickable" data-id="${t.id}"><td class="wrap"><b>${esc(t.subject)}</b><div class="text-xs text-3">${(t.messages || []).length} message${(t.messages || []).length === 1 ? "" : "s"}</div></td><td><span class="badge ${STATUS_BADGE[t.status] || ""}">${esc(titleCase(t.status))}</span></td><td>${priorityBadge(t.priority)}</td><td>${esc(titleCase(t.category || "general"))}</td><td>${timeAgo(t.updated_at || t.created_at)}</td></tr>`)
            .join("")}</tbody></table></div>`
        : emptyState("life-buoy", "No tickets", "Open one if you need help with your account or billing.");
      el.querySelectorAll("tr[data-id]").forEach((tr) => tr.addEventListener("click", () => (location.hash = `/support/${tr.dataset.id}`)));
    } catch (err) {
      el.innerHTML = errorBox(err);
    }
  }

  qs("#btn-new", page).addEventListener("click", () => {
    const body = h(`<form id="tform" class="form-grid">
      <div class="field span-2"><label class="label">Subject <span class="req">*</span></label><input class="input" name="subject" placeholder="Short summary"></div>
      <div class="field"><label class="label">Priority</label><select class="select" name="priority"><option value="low">Low</option><option value="normal" selected>Normal</option><option value="high">High</option><option value="urgent">Urgent</option></select></div>
      <div class="field"><label class="label">Category</label><select class="select" name="category"><option value="general">General</option><option value="billing">Billing</option><option value="account">Account</option><option value="technical">Technical</option><option value="feedback">Feedback</option></select></div>
      <div class="field span-2"><label class="label">Message <span class="req">*</span></label><textarea class="textarea" name="message" placeholder="Tell us what's going on…"></textarea></div>
      <p class="error-text span-2 hidden" id="terr"></p></form>`);
    const footer = h(`<div class="flex gap-2 justify-end w-full"><button class="btn btn-secondary" data-cancel>Cancel</button><button class="btn btn-primary" data-save>Open ticket</button></div>`);
    const m = modal({ title: "New support ticket", body, footer });
    qs("[data-cancel]", footer).onclick = () => m.close();
    qs("[data-save]", footer).onclick = async () => {
      const err = qs("#terr", body);
      err.classList.add("hidden");
      const subject = qs("[name=subject]", body).value.trim();
      const message = qs("[name=message]", body).value.trim();
      if (subject.length < 3 || !message) {
        err.textContent = "Please add a subject and a message.";
        err.classList.remove("hidden");
        return;
      }
      setLoading(qs("[data-save]", footer), true);
      try {
        const t = await api.post("/support/tickets", { subject, message, priority: qs("[name=priority]", body).value, category: qs("[name=category]", body).value });
        toast({ title: "Ticket opened", body: "We'll get back to you shortly.", type: "success" });
        m.close();
        location.hash = `/support/${t.id}`;
      } catch (ex) {
        err.textContent = errorMessage(ex);
        err.classList.remove("hidden");
        setLoading(qs("[data-save]", footer), false);
      }
    };
  });

  await load();
}

export async function renderTicket(page, params) {
  const id = Number(params.id);
  page.innerHTML = `<p class="mb-4"><a class="btn btn-ghost btn-sm" href="#/support">${icon("arrow-left", "icon-sm")} All tickets</a></p><div id="ticket">${skeletonRows(3)}</div>`;

  async function load() {
    const el = qs("#ticket", page);
    try {
      const t = await api.get(`/support/tickets/${id}`);
      const closed = ["resolved", "closed"].includes(t.status);
      el.innerHTML = `
        <div class="detail-head"><div><div class="flex gap-2 items-center wrap"><span class="text-3 text-sm">Ticket #${t.id}</span><span class="badge ${STATUS_BADGE[t.status] || ""}">${esc(titleCase(t.status))}</span>${priorityBadge(t.priority)}<span class="badge">${esc(titleCase(t.category || "general"))}</span></div><h1 class="mt-2">${esc(t.subject)}</h1><div class="detail-meta"><span>Opened ${fmtDateTime(t.created_at)}</span>${t.resolved_at ? `<span>Resolved ${fmtDateTime(t.resolved_at)}</span>` : ""}</div></div>
          ${!closed ? `<button class="btn btn-secondary" id="btn-close">${icon("check")} Close ticket</button>` : ""}</div>
        <div class="detail-grid"><div>
          <div id="thread">${(t.messages || []).map((m) => `<div class="ticket-msg ${m.sender === "admin" ? "admin" : ""}"><div class="who"><b>${esc(m.name || (m.sender === "admin" ? "Designflow" : "You"))}</b> · ${fmtDateTime(m.at)}</div><div style="white-space:pre-wrap">${esc(m.body)}</div></div>`).join("")}</div>
          ${closed ? `<div class="inline-alert mt-4">${icon("info")}<span>This ticket is ${t.status}. Reply to reopen it.</span></div>` : ""}
          <form class="card mt-6" id="reply"><div class="card-body"><div class="field"><label class="label">Reply</label><textarea class="textarea" name="message" placeholder="Add more details or reply to our answer…"></textarea></div></div><div class="card-footer flex justify-end"><button class="btn btn-primary" type="submit">${icon("send")} Send reply</button></div></form>
        </div>
        <div class="card"><div class="card-body text-sm"><b>Need something faster?</b><p class="text-3 mt-2">Design-related questions are quickest in <a href="#/chat">Chat</a>. Billing emergencies: mention "urgent" in your reply.</p></div></div></div>`;
      const close = qs("#btn-close", el);
      if (close) close.addEventListener("click", async () => {
        if (!(await confirmDialog({ title: "Close this ticket?", confirmText: "Close ticket" }))) return;
        try {
          await api.patch(`/support/tickets/${id}`, null, { status: "closed" });
          toast({ title: "Ticket closed", type: "success" });
          load();
        } catch (err) {
          reportError(err);
        }
      });
      qs("#reply", el).addEventListener("submit", async (e) => {
        e.preventDefault();
        const ta = qs("textarea", e.target);
        const message = ta.value.trim();
        if (!message) return;
        const btn = qs("button[type=submit]", e.target);
        setLoading(btn, true);
        try {
          await api.post(`/support/tickets/${id}/reply`, { message });
          toast({ title: "Reply sent", type: "success" });
          load();
        } catch (err) {
          reportError(err, "Reply failed");
          setLoading(btn, false);
        }
      });
    } catch (err) {
      el.innerHTML = err.status === 404 ? emptyState("help", "Ticket not found") : errorBox(err);
    }
  }
  await load();
}
