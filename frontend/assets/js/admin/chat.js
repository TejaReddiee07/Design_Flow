/* Chat: conversations list + thread, real-time */
import { api, errorMessage, downloadFile } from "../core/api.js";
import { esc, icon, qs, qsa, h, toast, timeAgo, fmtDateTime, initials, nl2br, setLoading } from "../core/ui.js";
import { pageHeader, loadingBlock, errorBlock, uploadFiles, emptyState } from "./shared.js";

export async function render(page, params, query, ctx) {
  const me = ctx.user;
  let convs = [];
  let active = params.id ? Number(params.id) : null;
  let messages = [];
  let sending = false;

  page.innerHTML = pageHeader("Chat", "Direct messages with every client. Messages arrive in real time.") +
    `<div class="chat-layout">
      <div class="conv-list" id="conv-list">${loadingBlock(4)}</div>
      <div class="chat-thread" id="thread"><div class="empty">${icon("message")}<h4>Select a conversation</h4></div></div>
    </div>`;
  const list = qs("#conv-list", page);
  const thread = qs("#thread", page);

  async function loadConvs() {
    try {
      convs = await api.get("/chat/conversations");
      if (query.client_id && !active) {
        const c = convs.find((x) => String(x.client_id) === String(query.client_id));
        if (c) active = c.id;
        else {
          // conversation may not exist yet: ask the API to create it by fetching messages by client
          try {
            await api.get("/chat/messages", { client_id: query.client_id });
            convs = await api.get("/chat/conversations");
            const c2 = convs.find((x) => String(x.client_id) === String(query.client_id));
            if (c2) active = c2.id;
          } catch {}
        }
      }
      if (!active && convs.length) active = convs[0].id;
      drawList();
      if (active) await loadThread();
    } catch (err) {
      list.innerHTML = errorBlock(err);
    }
  }

  function drawList() {
    list.innerHTML = convs.length
      ? convs.map((c) => `<div class="conv-item ${c.id === active ? "active" : ""}" data-conv="${c.id}">
          <span class="avatar avatar-sm">${initials(c.company_name)}</span>
          <div class="conv-main"><div class="conv-name"><span class="truncate">${esc(c.company_name)}</span><small>${c.last_message_at ? timeAgo(c.last_message_at) : ""}</small></div><div class="conv-preview">${esc(c.last_message_preview || c.client_name)}</div></div>
          ${c.unread ? `<span class="count-badge">${c.unread}</span>` : ""}
        </div>`).join("")
      : emptyState("message", "No conversations yet", "Conversations are created when a client signs up.");
    qsa("[data-conv]", list).forEach((el) => el.addEventListener("click", () => { active = Number(el.dataset.conv); location.hash = `/chat/${active}`; }));
  }

  async function loadThread() {
    const conv = convs.find((c) => c.id === active);
    if (!conv) return;
    thread.innerHTML = `<div class="chat-thread-head"><span class="avatar avatar-sm">${initials(conv.company_name)}</span><div class="flex-1 min-w-0"><b>${esc(conv.company_name)}</b><div class="text-xs text-3">${esc(conv.client_name)}</div></div><a href="#/clients/${conv.client_id}" class="btn btn-ghost btn-sm">Profile</a><a href="#/requests?client_id=${conv.client_id}" class="btn btn-ghost btn-sm">Requests</a></div>
      <div class="chat-messages" id="messages">${loadingBlock(3)}</div>
      <form class="chat-input" id="chat-form"><label class="btn btn-ghost btn-icon" title="Attach file">${icon("paperclip")}<input type="file" class="hidden" id="chat-file"></label><textarea class="textarea" id="chat-text" placeholder="Write a message… (Enter to send, Shift+Enter for newline)" rows="1"></textarea><button class="btn btn-primary" type="submit">${icon("send")}</button></form>`;
    try {
      messages = await api.get("/chat/messages", { conversation_id: active, limit: 100 });
      conv.unread = 0;
      drawList();
      drawMessages();
    } catch (err) {
      qs("#messages", thread).innerHTML = errorBlock(err);
    }
    const form = qs("#chat-form", thread);
    const ta = qs("#chat-text", thread);
    ta.addEventListener("keydown", (e) => {
      if (e.key === "Enter" && !e.shiftKey) {
        e.preventDefault();
        form.requestSubmit();
      }
    });
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const body = ta.value.trim();
      const file = qs("#chat-file", thread).files[0];
      if (!body && !file) return;
      if (sending) return;
      sending = true;
      const btn = qs("button[type=submit]", form);
      setLoading(btn, true);
      try {
        let file_id = null;
        if (file) {
          const [up] = await uploadFiles([file], { kind: "chat", client_id: conv.client_id });
          file_id = up.id;
        }
        const msg = await api.post("/chat/messages", { body: body || null, file_id }, { conversation_id: active });
        if (!messages.find((m) => m.id === msg.id)) messages.push(msg);
        ta.value = "";
        qs("#chat-file", thread).value = "";
        drawMessages();
      } catch (err) {
        toast({ title: "Not sent", body: errorMessage(err), type: "error" });
      } finally {
        sending = false;
        setLoading(btn, false);
      }
    });
  }

  function bubble(m) {
    const mine = m.sender_id === me.id;
    return `<div class="bubble ${mine ? "me" : ""}" data-msg="${m.id}">${m.body ? nl2br(m.body) : ""}${m.file_id ? `<div class="mt-1"><button class="btn btn-sm ${mine ? "" : "btn-secondary"}" data-dl="${m.file_id}" data-name="${esc(m.file_name || "file")}" style="${mine ? "background:rgba(255,255,255,.18);color:#fff;border-color:transparent" : ""}">${icon("paperclip", "icon-sm")} ${esc(m.file_name || "Attachment")}</button></div>` : ""}<span class="meta">${mine ? "You" : esc(m.sender_name)} · ${fmtDateTime(m.created_at)}</span></div>`;
  }

  function drawMessages() {
    const box = qs("#messages", thread);
    if (!box) return;
    box.innerHTML = messages.length ? messages.map(bubble).join("") : `<div class="empty" style="padding:30px">${icon("message")}<h4>No messages yet</h4><p>Say hello.</p></div>`;
    box.scrollTop = box.scrollHeight;
    qsa("[data-dl]", box).forEach((b) => b.addEventListener("click", () => downloadFile(b.dataset.dl, b.dataset.name).catch((err) => toast({ title: "Download failed", body: errorMessage(err), type: "error" }))));
  }

  const onMsg = async (e) => {
    const p = e.detail || {};
    const msg = p.message;
    if (!msg) return;
    if (p.conversation_id === active) {
      if (!messages.find((m) => m.id === msg.id)) {
        messages.push(msg);
        drawMessages();
      }
      const conv = convs.find((c) => c.id === active);
      if (conv) {
        conv.last_message_at = msg.created_at;
        conv.last_message_preview = msg.body || "📎 File";
      }
      drawList();
    } else {
      try {
        convs = await api.get("/chat/conversations");
        drawList();
      } catch {}
    }
  };
  document.addEventListener("df:chat_message", onMsg);
  await loadConvs();
  return () => document.removeEventListener("df:chat_message", onMsg);
}
