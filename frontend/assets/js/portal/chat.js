/* Client <-> studio chat */
import { api, errorMessage, downloadFile } from "../core/api.js";
import { icon, esc, qs, toast, fmtDateTime, fmtDate, parseDate, setLoading } from "../core/ui.js";
import { state, errorBox, reportError } from "./shared.js";

export async function renderChat(page) {
  const me = state.user.id;
  page.classList.add("chat-page");
  page.innerHTML = `<div class="card">
    <div class="chat-head"><span class="avatar">DF</span><div><b style="display:block">Designflow Studio</b><span class="text-xs text-3">Your designer and project manager. Replies usually within a few hours.</span></div></div>
    <div class="chat"><div class="chat-messages" id="msgs"><div class="skeleton" style="height:48px;width:60%"></div><div class="skeleton" style="height:48px;width:50%;align-self:flex-end"></div></div>
    <form class="chat-input" id="chat-form">
      <button type="button" class="btn btn-ghost btn-icon" id="attach" aria-label="Attach file">${icon("paperclip")}</button>
      <input type="file" id="attach-input" hidden>
      <textarea class="textarea flex-1" id="msg" rows="1" placeholder="Write a message… (Enter to send, Shift+Enter for a new line)"></textarea>
      <button class="btn btn-primary btn-icon" type="submit" aria-label="Send">${icon("send")}</button>
    </form></div>
  </div>`;

  const list = qs("#msgs", page);
  const form = qs("#chat-form", page);
  const input = qs("#msg", page);
  const seen = new Set();
  let lastDay = "";

  function bubble(m) {
    const mine = m.sender_id === me;
    const day = fmtDate(m.created_at);
    let dayHtml = "";
    if (day !== lastDay) {
      lastDay = day;
      dayHtml = `<div class="chat-day">${esc(day)}</div>`;
    }
    const att = m.file_id ? `<span class="att" data-dl="${m.file_id}" data-name="${esc(m.file_name || "attachment")}">${icon("paperclip", "icon-sm")} ${esc(m.file_name || "Attachment")}</span>` : "";
    return `${dayHtml}<div class="bubble ${mine ? "me" : ""}" data-id="${m.id}">${esc(m.body || "")}${att}<span class="meta">${mine ? "You" : esc(m.sender_name || "Studio")} · ${fmtDateTime(m.created_at)}</span></div>`;
  }

  function append(m) {
    if (seen.has(m.id)) return;
    seen.add(m.id);
    list.insertAdjacentHTML("beforeend", bubble(m));
    list.scrollTop = list.scrollHeight;
  }

  try {
    const rows = await api.get("/chat/messages", { limit: 200 });
    list.innerHTML = rows.length ? "" : `<div class="empty" style="margin:auto">${icon("message")}<h4>Say hello</h4><p>Questions about a request, pricing or anything else: write here and we'll answer.</p></div>`;
    rows.forEach(append);
    list.scrollTop = list.scrollHeight;
  } catch (err) {
    list.innerHTML = errorBox(err);
  }

  async function send(body, fileId = null) {
    if (!body && !fileId) return;
    const btn = qs("button[type=submit]", form);
    setLoading(btn, true);
    try {
      const m = await api.post("/chat/messages", { body: body || null, file_id: fileId });
      const empty = qs(".empty", list);
      if (empty) empty.remove();
      append(m);
      input.value = "";
      input.style.height = "";
    } catch (err) {
      reportError(err, "Message not sent");
    } finally {
      setLoading(btn, false);
      input.focus();
    }
  }

  form.addEventListener("submit", (e) => {
    e.preventDefault();
    send(input.value.trim());
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      send(input.value.trim());
    }
  });
  input.addEventListener("input", () => {
    input.style.height = "auto";
    input.style.height = `${Math.min(160, input.scrollHeight)}px`;
  });
  qs("#attach", page).addEventListener("click", () => qs("#attach-input", page).click());
  qs("#attach-input", page).addEventListener("change", async (e) => {
    const file = e.target.files[0];
    e.target.value = "";
    if (!file) return;
    const fd = new FormData();
    fd.append("file", file);
    fd.append("kind", "chat");
    try {
      const up = await api.upload("/files/upload", fd);
      await send(input.value.trim(), up.id);
    } catch (err) {
      reportError(err, "Upload failed");
    }
  });
  list.addEventListener("click", (e) => {
    const a = e.target.closest("[data-dl]");
    if (a) downloadFile(Number(a.dataset.dl), a.dataset.name).catch((err) => reportError(err, "Download failed"));
  });

  const onMsg = (e) => {
    const m = e.detail && e.detail.message;
    if (m) {
      const empty = qs(".empty", list);
      if (empty) empty.remove();
      append(m);
    }
  };
  document.addEventListener("df:chat_message", onMsg);
  setTimeout(() => input.focus(), 50);
  return () => {
    document.removeEventListener("df:chat_message", onMsg);
    page.classList.remove("chat-page");
  };
}
