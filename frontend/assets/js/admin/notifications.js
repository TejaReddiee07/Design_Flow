/* Notification center page */
import { api, errorMessage } from "../core/api.js";
import { esc, icon, qs, qsa, toast, timeAgo, NOTIF_ICONS, titleCase, confirmDialog } from "../core/ui.js";
import { pageHeader, loadingBlock, errorBlock, emptyState } from "./shared.js";

const TYPES = ["new_request", "request_status", "revision", "file_upload", "payment", "lead", "agent", "approval_needed", "delivery", "chat", "support", "system"];

export async function render(page, params, query) {
  let type = query.type || "";
  let unreadOnly = query.unread === "1";
  let offset = 0;
  const LIMIT = 50;
  let items = [];

  page.innerHTML = pageHeader("Notifications", "Everything that happened, in order.", `<button class="btn btn-secondary" id="mark-all">${icon("check")} Mark all read</button>`) +
    `<div class="filters"><select class="select" id="f-type"><option value="">All types</option>${TYPES.map((t) => `<option value="${t}" ${t === type ? "selected" : ""}>${titleCase(t)}</option>`).join("")}</select><label class="toggle"><input type="checkbox" id="f-unread" ${unreadOnly ? "checked" : ""}><span class="track"></span>Unread only</label><span class="ml-auto text-sm text-3" id="count"></span></div>
     <div class="card"><div id="list">${loadingBlock(5)}</div><div class="card-footer flex justify-center" id="more-wrap"><button class="btn btn-secondary btn-sm" id="more">Load more</button></div></div>`;
  const list = qs("#list", page);

  function item(n) {
    return `<div class="notif-page-item ${n.is_read ? "" : "unread"}" data-id="${n.id}">
      <span class="notif-icon avatar avatar-sm avatar-neutral">${icon(NOTIF_ICONS[n.type] || "info", "icon-sm")}</span>
      <div class="flex-1 min-w-0"><div class="flex items-center gap-2 wrap"><b>${esc(n.title)}</b><span class="badge">${esc(titleCase(n.type))}</span>${n.is_read ? "" : '<span class="badge badge-brand">new</span>'}</div>${n.body ? `<div class="text-sm text-3 mt-1">${esc(n.body)}</div>` : ""}<div class="text-xs text-4 mt-1">${timeAgo(n.created_at)}</div></div>
      <div class="flex gap-1">${n.link ? `<button class="btn btn-secondary btn-sm" data-open="${n.id}" data-link="${esc(n.link)}">Open</button>` : ""}${n.is_read ? "" : `<button class="btn btn-ghost btn-sm" data-read="${n.id}" title="Mark read">${icon("check", "icon-sm")}</button>`}<button class="btn btn-ghost btn-sm" data-del="${n.id}" title="Delete">${icon("trash", "icon-sm")}</button></div>
    </div>`;
  }

  async function load(append = false) {
    if (!append) {
      offset = 0;
      list.innerHTML = loadingBlock(5);
    }
    try {
      const rows = await api.get("/notifications", { type: type || undefined, unread_only: unreadOnly || undefined, limit: LIMIT, offset });
      items = append ? items.concat(rows) : rows;
      list.innerHTML = items.length ? items.map(item).join("") : emptyState("bell", unreadOnly ? "No unread notifications" : "No notifications yet");
      qs("#count", page).textContent = `${items.length}${rows.length === LIMIT ? "+" : ""} shown`;
      qs("#more-wrap", page).classList.toggle("hidden", rows.length < LIMIT);
    } catch (err) {
      list.innerHTML = errorBlock(err);
    }
  }

  list.addEventListener("click", async (e) => {
    const open = e.target.closest("[data-open]");
    const read = e.target.closest("[data-read]");
    const del = e.target.closest("[data-del]");
    try {
      if (open) {
        await api.post(`/notifications/${open.dataset.open}/read`).catch(() => {});
        window.dfAdmin.openLink(open.dataset.link);
      } else if (read) {
        await api.post(`/notifications/${read.dataset.read}/read`);
        const n = items.find((x) => x.id === Number(read.dataset.read));
        if (n) n.is_read = true;
        list.innerHTML = items.map(item).join("");
      } else if (del) {
        await api.del(`/notifications/${del.dataset.del}`);
        items = items.filter((x) => x.id !== Number(del.dataset.del));
        list.innerHTML = items.length ? items.map(item).join("") : emptyState("bell", "No notifications");
      }
    } catch (err) {
      toast({ title: "Failed", body: errorMessage(err), type: "error" });
    }
  });

  qs("#mark-all", page).onclick = async () => {
    try {
      await api.post("/notifications/mark-all-read");
      items.forEach((n) => (n.is_read = true));
      list.innerHTML = items.length ? items.map(item).join("") : emptyState("bell", "No notifications");
      toast({ title: "All read", type: "success", timeout: 1500 });
      document.dispatchEvent(new CustomEvent("df:notifications_changed"));
    } catch (err) {
      toast({ title: "Failed", body: errorMessage(err), type: "error" });
    }
  };
  qs("#f-type", page).addEventListener("change", (e) => { type = e.target.value; load(); });
  qs("#f-unread", page).addEventListener("change", (e) => { unreadOnly = e.target.checked; load(); });
  qs("#more", page).onclick = () => { offset += LIMIT; load(true); };

  const onNotif = () => load();
  document.addEventListener("df:notification", onNotif);
  await load();
  return () => document.removeEventListener("df:notification", onNotif);
}
