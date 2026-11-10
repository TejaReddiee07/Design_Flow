/* Client portal entry: auth, shell, real-time glue, router. */
import { requireAuth, logout } from "../core/auth.js";
import { api, errorMessage } from "../core/api.js";
import { ws } from "../core/ws.js";
import { createRouter } from "../core/router.js";
import { initTheme, icon, qs, qsa, esc, toast, timeAgo, initials, NOTIF_ICONS, emptyState } from "../core/ui.js";
import { state, navigateLink, setPageTitle } from "./shared.js";

import { renderDashboard } from "./dashboard.js";
import { renderNewRequest } from "./new-request.js";
import { renderRequests } from "./requests.js";
import { renderRequestDetail } from "./request-detail.js";
import { renderFiles } from "./files.js";
import { renderDesigns } from "./designs.js";
import { renderProjects } from "./projects.js";
import { renderChat } from "./chat.js";
import { renderSupport, renderTicket } from "./support.js";
import { renderInvoices } from "./invoices.js";
import { renderSettings } from "./settings.js";

const routes = [
  { path: "/", title: "Dashboard", render: renderDashboard },
  { path: "/new", title: "New request", render: renderNewRequest },
  { path: "/requests", title: "My requests", render: renderRequests },
  { path: "/requests/:id", title: "Request", render: renderRequestDetail, nav: "/requests" },
  { path: "/designs", title: "Your designs", render: renderDesigns },
  { path: "/files", title: "Files & brand assets", render: renderFiles },
  { path: "/projects", title: "Projects", render: renderProjects },
  { path: "/chat", title: "Chat", render: renderChat },
  { path: "/support", title: "Support", render: renderSupport },
  { path: "/support/:id", title: "Support ticket", render: renderTicket, nav: "/support" },
  { path: "/invoices", title: "Invoices", render: renderInvoices },
  { path: "/subscription", title: "Invoices", render: renderInvoices, nav: "/invoices" },
  { path: "/settings", title: "Settings", render: renderSettings },
];

/* ---------- shell ---------- */
function renderUser(user) {
  const name = user.full_name || user.email;
  const company = user.client ? user.client.company_name : "";
  qs("#user-avatar").textContent = initials(name);
  qs("#user-name").textContent = name.split(" ")[0];
  qs("#side-user").innerHTML = `<span class="avatar">${esc(initials(name))}</span><div class="meta"><b>${esc(name)}</b><span>${esc(company)}</span></div>`;
}

function setupSidebar() {
  const sidebar = qs("#sidebar");
  const toggle = qs("#sidebar-toggle");
  let scrim = null;
  const close = () => {
    sidebar.classList.remove("open");
    if (scrim) {
      scrim.remove();
      scrim = null;
    }
  };
  toggle.addEventListener("click", () => {
    const open = sidebar.classList.toggle("open");
    if (open) {
      scrim = document.createElement("div");
      scrim.className = "sidebar-scrim";
      scrim.addEventListener("click", close);
      document.body.appendChild(scrim);
    } else close();
  });
  qsa(".nav-item", sidebar).forEach((a) => a.addEventListener("click", close));
}

function setActiveNav(path) {
  qsa("#side-nav .nav-item").forEach((a) => a.classList.toggle("active", a.dataset.route === path));
}

/* ---------- notifications ---------- */
const bell = {
  count: 0,
  open: false,
  loaded: false,
  set(n) {
    this.count = Math.max(0, Number(n) || 0);
    state.unread = this.count;
    const el = qs("#bell-count");
    el.textContent = this.count > 99 ? "99+" : String(this.count);
    el.hidden = this.count === 0;
    el.classList.toggle("is-zero", this.count === 0);
  },
  ring() {
    const b = qs("#bell");
    b.classList.remove("ring");
    void b.offsetWidth;
    b.classList.add("ring");
    const c = qs("#bell-count");
    c.classList.remove("pulse");
    void c.offsetWidth;
    c.classList.add("pulse");
  },
  item(n) {
    return `<div class="notif-item ${n.is_read ? "" : "unread"}" data-id="${n.id}" data-link="${esc(n.link || "")}">
      <span class="notif-icon">${icon(NOTIF_ICONS[n.type] || "info", "icon-sm")}</span>
      <div class="min-w-0 flex-1">
        <div class="notif-title">${esc(n.title)}</div>
        ${n.body ? `<div class="notif-body">${esc(n.body)}</div>` : ""}
        <div class="notif-time">${timeAgo(n.created_at)}</div>
      </div>
    </div>`;
  },
  async load() {
    const list = qs("#notif-list");
    list.innerHTML = '<div class="skeleton" style="height:60px;margin:10px"></div><div class="skeleton" style="height:60px;margin:10px"></div>';
    try {
      const rows = await api.get("/notifications", { limit: 30 });
      list.innerHTML = rows.length ? rows.map((n) => this.item(n)).join("") : emptyState("bell", "No notifications yet", "Updates about your requests will appear here.");
      this.loaded = true;
    } catch (err) {
      list.innerHTML = `<div class="empty"><p>${esc(errorMessage(err))}</p></div>`;
    }
  },
  prepend(n) {
    if (!this.open) return;
    const list = qs("#notif-list");
    const empty = qs(".empty", list);
    if (empty) empty.remove();
    list.insertAdjacentHTML("afterbegin", this.item(n));
  },
  toggle(force) {
    const panel = qs("#notif-panel");
    this.open = force !== undefined ? force : !this.open;
    panel.hidden = !this.open;
    if (this.open) this.load();
  },
};

function setupBell() {
  qs("#bell-btn").addEventListener("click", (e) => {
    e.stopPropagation();
    bell.toggle();
    qs("#user-menu-panel").classList.remove("open");
  });
  qs("#mark-all-read").addEventListener("click", async () => {
    try {
      const res = await api.post("/notifications/mark-all-read");
      bell.set(res.unread_count);
      qsa("#notif-list .notif-item").forEach((i) => i.classList.remove("unread"));
    } catch (err) {
      toast({ title: "Could not mark read", body: errorMessage(err), type: "error" });
    }
  });
  qs("#notif-list").addEventListener("click", async (e) => {
    const item = e.target.closest(".notif-item");
    if (!item) return;
    const id = Number(item.dataset.id);
    const link = item.dataset.link;
    item.classList.remove("unread");
    try {
      const res = await api.post(`/notifications/${id}/read`);
      bell.set(res.unread_count);
    } catch {}
    bell.toggle(false);
    if (link && (link.startsWith("/portal") || link.startsWith("#"))) navigateLink(link);
  });
  document.addEventListener("click", (e) => {
    if (bell.open && !e.target.closest("#bell")) bell.toggle(false);
  });
  api.get("/notifications/unread-count").then((r) => bell.set(r.unread_count)).catch(() => {});
}

function setupUserMenu() {
  const btn = qs("#user-btn");
  const panel = qs("#user-menu-panel");
  btn.addEventListener("click", (e) => {
    e.stopPropagation();
    panel.classList.toggle("open");
    bell.toggle(false);
  });
  document.addEventListener("click", (e) => {
    if (!e.target.closest("#user-menu")) panel.classList.remove("open");
  });
  qsa(".menu-item", panel).forEach((a) => a.addEventListener("click", () => panel.classList.remove("open")));
  qs("#logout-btn").addEventListener("click", () => logout("/login"));
}

/* ---------- real-time ---------- */
function setupRealtime() {
  const live = qs("#live-indicator");
  ws.on("status", ({ status }) => {
    live.className = `live-indicator ${status}`;
    const label = status === "open" ? "Live" : status === "connecting" ? "Connecting" : "Offline";
    live.dataset.tip = status === "open" ? "Real-time updates connected" : "Reconnecting…";
    const span = qs("span", live);
    if (span) span.textContent = label;
  });
  ws.on("hello", (p) => bell.set(p.unread_count));
  ws.on("unread_count", (p) => bell.set(p.unread_count));
  ws.on("notification", (p) => {
    bell.set(p.unread_count);
    bell.ring();
    bell.prepend(p.notification);
    const n = p.notification;
    toast({
      title: n.title,
      body: n.body || "",
      type: n.type === "delivery" || n.type === "payment" ? "success" : "info",
      timeout: 6000,
      onClick: () => {
        api.post(`/notifications/${n.id}/read`).then((r) => bell.set(r.unread_count)).catch(() => {});
        if (n.link) navigateLink(n.link);
      },
    });
    if (n.type === "chat") refreshChatBadge();
  });
  ws.on("request_update", (p) => {
    document.dispatchEvent(new CustomEvent("df:request_update", { detail: p }));
    refreshActiveCount();
  });
  ws.on("chat_message", (p) => {
    document.dispatchEvent(new CustomEvent("df:chat_message", { detail: p }));
    if (!location.hash.startsWith("#/chat")) refreshChatBadge();
  });
  ws.on("chat_read", () => refreshChatBadge());
  ws.connect();
}

export async function refreshActiveCount() {
  try {
    const page = await api.get("/requests", { status: "accepted,in_progress,review", page_size: 1 });
    state.activeCount = page.total;
    const el = qs("#nav-active-count");
    el.textContent = String(page.total);
    el.hidden = page.total === 0;
    el.classList.toggle("is-zero", page.total === 0);
  } catch {}
  try {
    const s = await api.get("/billing/summary");
    const n = s.unpaid_requests || 0;
    const el = qs("#nav-unpaid-count");
    if (el) {
      el.textContent = String(n);
      el.hidden = n === 0;
    }
  } catch {}
}

export async function refreshChatBadge() {
  try {
    const convs = await api.get("/chat/conversations");
    const unread = convs.reduce((a, c) => a + (c.unread || 0), 0);
    const el = qs("#nav-chat-count");
    el.textContent = String(unread);
    el.hidden = unread === 0 || location.hash.startsWith("#/chat");
  } catch {}
}

/* ---------- boot ---------- */
async function boot() {
  const user = await requireAuth(["client"]);
  if (!user) return;
  state.user = user;
  initTheme();
  renderUser(user);
  setupSidebar();
  setupBell();
  setupUserMenu();
  setupRealtime();
  refreshActiveCount();
  refreshChatBadge();

  const outlet = qs("#outlet");
  const router = createRouter({
    routes,
    outlet,
    onNavigate(cur) {
      const route = cur.route;
      setActiveNav(route ? route.nav || route.path : "");
      setPageTitle(route ? route.title : "Not found");
      if (cur.path.startsWith("/chat")) {
        const el = qs("#nav-chat-count");
        if (el) el.hidden = true;
      }
    },
    notFound(el) {
      el.innerHTML = `<div class="page">${emptyState("help", "Page not found", "The link you followed does not exist.")}<p class="text-center"><a class="btn btn-primary" href="#/">Back to dashboard</a></p></div>`;
    },
  });
  qs("#app").hidden = false;
  qs("#boot").remove();
  router.start();
}

boot().catch((err) => {
  console.error(err);
  const b = qs("#boot");
  if (b) b.innerHTML = `<p class="text-3">Could not load the portal: ${esc(errorMessage(err))}</p><a class="btn btn-primary" href="/login">Log in again</a>`;
});
