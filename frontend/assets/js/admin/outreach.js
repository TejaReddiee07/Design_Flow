/* Outreach: review, edit, approve and send agent-drafted emails */
import { api, errorMessage } from "../core/api.js";
import { esc, icon, qs, qsa, h, toast, drawer, confirmDialog, setLoading, fmtDateTime, timeAgo, titleCase } from "../core/ui.js";
import { pageHeader, dataTable, pager, loadingBlock, errorBlock } from "./shared.js";
import { outreachStatusBadge } from "./leads.js";

const STATUSES = ["draft", "approved", "sent", "replied", "bounced"];

export async function render(page, params, query) {
  let status = query.status || "";
  let pg = 1;
  let rows = [];
  const selected = new Set();
  let settings = { auto_send: false, email_provider: "mock" };

  page.innerHTML = pageHeader("Outreach", "Emails drafted by the Outreach Agent. Review, edit, approve and send.", `<button class="btn btn-primary" id="send-selected" disabled>${icon("send")} Send selected</button>`) +
    `<div class="card mb-5"><div class="card-body flex items-center gap-4 wrap text-sm" id="settings-line">${loadingBlock(1)}</div></div>
     <div class="filters"><select class="select" id="f-status"><option value="">All statuses</option>${STATUSES.map((s) => `<option value="${s}" ${s === status ? "selected" : ""}>${titleCase(s)}</option>`).join("")}</select><span class="ml-auto text-sm text-3" id="count"></span></div>
     <div id="content">${loadingBlock(5)}</div>`;
  const content = qs("#content", page);

  api.get("/outreach/settings").then((s) => {
    settings = s;
    qs("#settings-line", page).innerHTML = `<span>${icon("mail")} Email provider: <b>${esc(s.email_provider)}</b>${s.email_provider === "mock" ? ' <span class="badge badge-warning">mock — nothing is actually sent</span>' : ""}</span><span>${icon("zap")} Auto-send: <b>${s.auto_send ? "on" : "off"}</b>${s.auto_send ? "" : ' <span class="text-3">(drafts wait for your approval)</span>'}</span><span class="ml-auto text-3">Configure EMAIL_PROVIDER and OUTREACH_AUTO_SEND in .env</span>`;
  }).catch(() => (qs("#settings-line", page).innerHTML = '<span class="text-3">Settings unavailable</span>'));

  function updateSendBtn() {
    const b = qs("#send-selected", page);
    b.disabled = selected.size === 0;
    b.innerHTML = `${icon("send")} Send selected${selected.size ? ` (${selected.size})` : ""}`;
  }

  async function load() {
    try {
      const data = await api.get("/outreach", { status: status || undefined, page: pg, page_size: 25 });
      rows = data.items;
      qs("#count", page).textContent = `${data.total} email${data.total === 1 ? "" : "s"}`;
      content.innerHTML = dataTable({
        columns: [
          { key: "sel", label: "", width: "32px", render: (o) => (o.status === "sent" || o.status === "replied" ? "" : `<input type="checkbox" data-sel="${o.id}" ${selected.has(o.id) ? "checked" : ""}>`) },
          { key: "company_name", label: "Lead", render: (o) => `<a href="#/leads/${o.lead_id}"><b>${esc(o.company_name)}</b></a><div class="text-xs text-3">${esc(o.contact_email || "no email")}</div>` },
          { key: "subject", label: "Subject", cls: "wrap", render: (o) => `<span class="clickable" data-open="${o.id}">${esc(o.subject || "(no subject)")}</span>` },
          { key: "status", label: "Status", render: (o) => outreachStatusBadge(o.status) },
          { key: "channel", label: "Channel", render: (o) => `<span class="badge">${esc(o.channel)}</span>` },
          { key: "sent_at", label: "Sent", render: (o) => (o.sent_at ? fmtDateTime(o.sent_at) : "—") },
          { key: "follow_up_count", label: "Follow-ups", render: (o) => `${o.follow_up_count}${o.follow_up_at ? `<div class="text-xs text-3">next ${timeAgo(o.follow_up_at)}</div>` : ""}` },
          { key: "actions", label: "", render: (o) => `<div class="flex gap-1"><button class="btn btn-secondary btn-sm" data-open="${o.id}">${icon("eye", "icon-sm")} Review</button>${o.status === "draft" ? `<button class="btn btn-success-soft btn-sm" data-approve="${o.id}">${icon("check", "icon-sm")}</button>` : ""}${o.status !== "sent" && o.status !== "replied" ? `<button class="btn btn-primary btn-sm" data-send="${o.id}">${icon("send", "icon-sm")}</button>` : ""}</div>` },
        ],
        rows,
        empty: "No outreach emails",
        emptyIcon: "mail",
      });
      if (data.total > 25) content.appendChild(pager({ page: pg, total: data.total, pageSize: 25, onPage: (p) => { pg = p; load(); } }));
      qsa("[data-sel]", content).forEach((c) => c.addEventListener("change", () => { c.checked ? selected.add(Number(c.dataset.sel)) : selected.delete(Number(c.dataset.sel)); updateSendBtn(); }));
      qsa("[data-open]", content).forEach((b) => b.addEventListener("click", () => openDrawer(rows.find((o) => o.id === Number(b.dataset.open)))));
      qsa("[data-approve]", content).forEach((b) => b.addEventListener("click", () => setStatus(Number(b.dataset.approve), "approved")));
      qsa("[data-send]", content).forEach((b) => b.addEventListener("click", () => send([Number(b.dataset.send)])));
    } catch (err) {
      content.innerHTML = errorBlock(err);
    }
  }

  async function setStatus(id, st) {
    try {
      await api.patch(`/outreach/${id}`, null, { status: st });
      toast({ title: `Marked ${st}`, type: "success", timeout: 2000 });
      load();
    } catch (err) {
      toast({ title: "Failed", body: errorMessage(err), type: "error" });
    }
  }

  async function send(ids) {
    const ok = await confirmDialog({ title: `Send ${ids.length} email${ids.length === 1 ? "" : "s"}?`, body: settings.email_provider === "mock" ? "Email provider is mock: emails are logged, not delivered." : `Emails go out via ${settings.email_provider} immediately.`, confirmText: "Send" });
    if (!ok) return;
    try {
      const r = await api.post("/outreach/send", { outreach_ids: ids });
      toast({ title: `Sent ${r.sent} email${r.sent === 1 ? "" : "s"}`, body: `Provider: ${r.provider}`, type: "success" });
      ids.forEach((i) => selected.delete(i));
      updateSendBtn();
      load();
    } catch (err) {
      toast({ title: "Send failed", body: errorMessage(err), type: "error" });
    }
  }

  function openDrawer(o) {
    if (!o) return;
    const editable = o.status !== "sent" && o.status !== "replied";
    const body = h(`<div style="padding:var(--s-5)">
      <div class="flex items-center gap-2 mb-4">${outreachStatusBadge(o.status)}<span class="text-xs text-3">to ${esc(o.contact_email || "no email")} · ${esc(o.generated_by)}</span></div>
      <div class="field"><label class="label">Subject</label><input class="input" id="o-subject" value="${esc(o.subject || "")}" ${editable ? "" : "disabled"}></div>
      <div class="field"><label class="label">Body</label><textarea class="textarea" id="o-body" style="min-height:260px" ${editable ? "" : "disabled"}>${esc(o.body)}</textarea></div>
      ${o.reply_text ? `<div class="mt-4" style="padding:10px 12px;background:var(--success-bg);border-radius:10px;font-size:var(--fs-sm)"><b>Reply received:</b><br>${esc(o.reply_text)}</div>` : `<div class="field mt-4"><label class="label">Log a reply (marks lead as replied)</label><textarea class="textarea" id="o-reply" style="min-height:70px" placeholder="Paste what they replied"></textarea></div>`}
      <div class="flex gap-2 mt-5 wrap">
        ${editable ? `<button class="btn btn-secondary" id="o-save">${icon("check", "icon-sm")} Save edits</button>` : ""}
        ${o.status === "draft" ? `<button class="btn btn-success-soft" id="o-approve">${icon("check-circle", "icon-sm")} Approve</button>` : ""}
        ${editable ? `<button class="btn btn-primary" id="o-send">${icon("send", "icon-sm")} Send now</button>` : ""}
        ${!o.reply_text ? `<button class="btn btn-ghost" id="o-reply-save">Save reply</button>` : ""}
      </div></div>`);
    const d = drawer({ title: o.company_name, body });
    const saveEdits = async () => {
      await api.patch(`/outreach/${o.id}`, null, { subject: qs("#o-subject", body).value, body: qs("#o-body", body).value });
    };
    const btnSave = qs("#o-save", body);
    if (btnSave) btnSave.onclick = async () => {
      setLoading(btnSave, true);
      try {
        await saveEdits();
        toast({ title: "Saved", type: "success", timeout: 1500 });
        load();
      } catch (err) {
        toast({ title: "Failed", body: errorMessage(err), type: "error" });
      } finally {
        setLoading(btnSave, false);
      }
    };
    const btnApprove = qs("#o-approve", body);
    if (btnApprove) btnApprove.onclick = async () => {
      try {
        await saveEdits();
        await setStatus(o.id, "approved");
        d.close();
      } catch (err) {
        toast({ title: "Failed", body: errorMessage(err), type: "error" });
      }
    };
    const btnSend = qs("#o-send", body);
    if (btnSend) btnSend.onclick = async () => {
      try {
        await saveEdits();
        d.close();
        send([o.id]);
      } catch (err) {
        toast({ title: "Failed", body: errorMessage(err), type: "error" });
      }
    };
    const btnReply = qs("#o-reply-save", body);
    if (btnReply) btnReply.onclick = async () => {
      const txt = qs("#o-reply", body).value.trim();
      if (!txt) return;
      try {
        await api.patch(`/outreach/${o.id}`, null, { reply_text: txt });
        toast({ title: "Reply logged", type: "success" });
        d.close();
        load();
      } catch (err) {
        toast({ title: "Failed", body: errorMessage(err), type: "error" });
      }
    };
  }

  qs("#f-status", page).addEventListener("change", (e) => { status = e.target.value; pg = 1; load(); });
  qs("#send-selected", page).onclick = () => send([...selected]);
  await load();
}
