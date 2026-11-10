/* Admin app entry: auth, shell, navigation, real-time wiring, router. */
import { requireAuth, logout } from "../core/auth.js";
import { api, errorMessage } from "../core/api.js";
import { ws } from "../core/ws.js";
import { createRouter } from "../core/router.js";
import { initTheme, icon, qs, qsa, esc, toast, timeAgo, initials, NOTIF_ICONS, onClickOutside } from "../core/ui.js";
import { setTitle } from "./shared.js";

import * as overview from "./overview.js";
import * as requests from "./requests.js";
import * as requestDetail from "./request-detail.js";
import * as services from "./services.js";
import * as clients from "./clients.js";
import * as clientFiles from "./client-files.js";
import * as projects from "./projects.js";
import * as billing from "./billing.js";
import * as leads from "./leads.js";
import * as outreach from "./outreach.js";
import * as chat from "./chat.js";
import * as support from "./support.js";
import * as agents from "./agents.js";
import * as analytics from "./analytics.js";
import * as notifications from "./notifications.js";
import * as users from "./users.js";
import * as audit from "./audit.js";
import * as settings from "./settings.js";

initTheme();

const user = await requireAuth(["admin", "staff"]);
if (!user) throw new Error("redirecting");

/* ---------- user menu ---------- */
qs("#user-avatar").textContent = initials(user.full_name);
qs("#user-name").textContent = user.full_name;
const userBtn = qs("#user-btn");
const userPanel = qs("#user-menu-panel");
userBtn.addEventListener("click", (e) => {
  e.stopPropagation();
  userPanel.classList.toggle("open");
  if (userPanel.classList.contains("open")) onClickOutside(userPanel, () => userPanel.classList.remove("open"));
});
qs("#logout-btn").addEventListener("click", () => logout("/login"));

/* ---------- sidebar ---------- */
const NAV = [
  { section: "" },
  { path: "/", label: "Overview", icon: "home", exact: true },
  { path: "/requests", label: "Requests", icon: "inbox", badge: "pending" },
  { path: "/services", label: "Service management", icon: "layers" },
  { section: "Services", id: "services-section" },
  { section: "Business" },
  { path: "/clients", label: "Clients", icon: "users" },
  { path: "/client-files", label: "Client files", icon: "folder" },
  { path: "/projects", label: "Projects", icon: "folder" },
  { path: "/billing", label: "Billing", icon: "credit-card" },
  { path: "/leads", label: "Leads", icon: "target" },
  { path: "/outreach", label: "Outreach", icon: "mail" },
  { section: "Communication" },
  { path: "/chat", label: "Chat", icon: "message", badge: "chat" },
  { path: "/support", label: "Support", icon: "life-buoy" },
  { path: "/notifications", label: "Notifications", icon: "bell", badge: "unread" },
  { section: "Automation" },
  { path: "/agents", label: "AI Agents", icon: "cpu" },
  { path: "/analytics", label: "Analytics", icon: "bar-chart" },
  { section: "System" },
  { path: "/users", label: "Users & roles", icon: "shield" },
  { path: "/audit", label: "Audit log", icon: "list" },
  { path: "/settings", label: "Settings", icon: "settings" },
];

const sidenav = qs("#sidenav");

function navItem(n) {
  return `<a class="nav-item" href="#${n.path}" data-nav="${n.path}" data-exact="${n.exact ? 1 : 0}">${icon(n.icon)}<span class="flex-1 truncate">${esc(n.label)}</span>${n.badge ? `<span class="count-badge is-zero" data-badge="${n.badge}">0</span>` : ""}</a>`;
}

sidenav.innerHTML = NAV.map((n) => {
  if (n.section !== undefined) return `<div class="nav-section" ${n.id ? `id="${n.id}"` : ""}>${esc(n.section)}</div>${n.id ? `<div id="services-nav"></div>` : ""}`;
  return navItem(n);
}).join("");

qs("#sidebar-footer").innerHTML = `<div class="flex items-center gap-3"><span class="avatar avatar-sm">${initials(user.full_name)}</span><div class="min-w-0"><div class="text-sm font-semibold truncate">${esc(user.full_name)}</div><div class="text-xs text-3 truncate">${esc(user.email)}</div></div></div>`;

function highlightNav(path) {
  qsa("[data-nav]", sidenav).forEach((a) => {
    const p = a.dataset.nav;
    const exact = a.dataset.exact === "1";
    a.classList.toggle("active", exact ? path === p : path === p || path.startsWith(p + "/"));
  });
}

/* services sub-menu with live counts */
const serviceNav = qs("#services-nav");
let serviceCounts = [];

function renderServiceNav() {
  serviceNav.innerHTML = serviceCounts
    .map((s) => `<a class="nav-item" href="#/services/${esc(s.slug)}" data-nav="/services/${esc(s.slug)}" data-exact="1" data-service-id="${s.id}">${icon("chevron-right", "icon-sm")}<span class="flex-1 truncate">${esc(s.name)}</span><span class="count-badge ${s.pending ? "" : "is-zero"}" data-service-badge="${s.id}">${s.pending}</span></a>`)
    .join("");
  const total = serviceCounts.reduce((a, s) => a + (s.pending || 0), 0);
  setBadge("pending", total);
  highlightNav(router.current ? router.current.path : "/");
}

function setBadge(name, value) {
  qsa(`[data-badge="${name}"]`).forEach((b) => {
    b.textContent = value;
    b.classList.toggle("is-zero", !value);
  });
}

async function loadServiceCounts() {
  try {
    const data = await api.get("/services/counts");
    serviceCounts = data.services;
    renderServiceNav();
  } catch (err) {
    console.warn("service counts", err);
  }
}

function applyBadgeCounts(payload) {
  serviceCounts = payload.services || serviceCounts;
  renderServiceNav();
  if (payload.highlight_service_id) {
    const item = qs(`[data-service-id="${payload.highlight_service_id}"]`, serviceNav);
    if (item) {
      item.classList.add("highlight");
      const badge = qs(".count-badge", item);
      if (badge) badge.classList.add("pulse");
      setTimeout(() => {
        item.classList.remove("highlight");
        if (badge) badge.classList.remove("pulse");
      }, 2400);
    }
  }
}

async function loadChatUnread() {
  try {
    const convs = await api.get("/chat/conversations");
    setBadge("chat", convs.reduce((a, c) => a + (c.unread || 0), 0));
  } catch {}
}

/* mobile sidebar */
const sidebar = qs("#sidebar");
const scrim = qs("#sidebar-scrim");
function closeSidebar() {
  sidebar.classList.remove("open");
  scrim.classList.add("hidden");
}
qs("#sidebar-toggle").addEventListener("click", () => {
  sidebar.classList.toggle("open");
  scrim.classList.toggle("hidden", !sidebar.classList.contains("open"));
});
scrim.addEventListener("click", closeSidebar);
sidenav.addEventListener("click", (e) => {
  if (e.target.closest("a")) closeSidebar();
});

/* ---------- global search ---------- */
qs("#global-search").addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    const q = e.target.value.trim();
    router.navigate(q ? `/requests?q=${encodeURIComponent(q)}` : "/requests");
  }
});

/* ---------- notifications bell ---------- */
const bell = qs("#bell");
const bellCount = qs("#bell-count");
const panel = qs("#notif-panel");
const notifList = qs("#notif-list");
let unread = 0;

function setUnread(n) {
  unread = Math.max(0, Number(n) || 0);
  bellCount.textContent = unread > 99 ? "99+" : unread;
  bellCount.classList.toggle("hidden", unread === 0);
  setBadge("unread", unread);
}

function ringBell() {
  bell.classList.remove("ring");
  void bell.offsetWidth;
  bell.classList.add("ring");
  setTimeout(() => bell.classList.remove("ring"), 900);
}

function notifItem(n) {
  return `<div class="notif-item ${n.is_read ? "" : "unread"}" data-notif="${n.id}" data-link="${esc(n.link || "")}">
    <span class="notif-icon">${icon(NOTIF_ICONS[n.type] || "info", "icon-sm")}</span>
    <div class="min-w-0 flex-1"><div class="notif-title truncate">${esc(n.title)}</div>${n.body ? `<div class="notif-body">${esc(n.body)}</div>` : ""}<div class="notif-time">${timeAgo(n.created_at)}</div></div>
  </div>`;
}

async function loadPanel() {
  notifList.innerHTML = '<div style="padding:16px"><div class="skeleton" style="height:40px;margin-bottom:8px"></div><div class="skeleton" style="height:40px"></div></div>';
  try {
    const items = await api.get("/notifications", { limit: 20 });
    notifList.innerHTML = items.length ? items.map(notifItem).join("") : '<div class="empty" style="padding:28px"><h4>All caught up</h4></div>';
  } catch (err) {
    notifList.innerHTML = `<div class="empty"><p>${esc(errorMessage(err))}</p></div>`;
  }
}

export function openLink(link) {
  if (!link) return;
  if (link.startsWith("/admin#")) router.navigate(link.slice("/admin#".length));
  else if (link.startsWith("#")) router.navigate(link.slice(1));
  else if (link.startsWith("/admin")) router.navigate("/");
  else location.href = link;
}

qs("#bell-btn").addEventListener("click", (e) => {
  e.stopPropagation();
  const open = panel.classList.toggle("hidden");
  if (!open) {
    loadPanel();
    onClickOutside(panel, () => panel.classList.add("hidden"));
  }
});

notifList.addEventListener("click", async (e) => {
  const item = e.target.closest("[data-notif]");
  if (!item) return;
  const id = Number(item.dataset.notif);
  const link = item.dataset.link;
  if (item.classList.contains("unread")) {
    item.classList.remove("unread");
    try {
      const r = await api.post(`/notifications/${id}/read`);
      setUnread(r.unread_count);
    } catch {}
  }
  panel.classList.add("hidden");
  openLink(link);
});

qs("#notif-mark-all").addEventListener("click", async () => {
  try {
    const r = await api.post("/notifications/mark-all-read");
    setUnread(r.unread_count);
    qsa(".notif-item", notifList).forEach((i) => i.classList.remove("unread"));
    document.dispatchEvent(new CustomEvent("df:notifications_changed"));
  } catch (err) {
    toast({ title: "Failed", body: errorMessage(err), type: "error" });
  }
});

/* ---------- real-time ---------- */
const wsIndicator = qs("#ws-indicator");
ws.on("status", ({ status }) => {
  wsIndicator.classList.toggle("offline", status === "closed");
  wsIndicator.classList.toggle("connecting", status === "connecting");
  wsIndicator.dataset.tip = status === "open" ? "Live updates connected" : status === "connecting" ? "Connecting…" : "Reconnecting…";
});
ws.on("hello", (p) => setUnread(p.unread_count));
ws.on("unread_count", (p) => setUnread(p.unread_count));
ws.on("badge_counts", applyBadgeCounts);
ws.on("notification", (p) => {
  const n = p.notification || {};
  setUnread(p.unread_count);
  ringBell();
  toast({ title: n.title || "Notification", body: n.body || "", type: n.type === "payment" ? "success" : "info", timeout: 6000, onClick: () => openLink(n.link) });
  if (!panel.classList.contains("hidden")) loadPanel();
  if (n.type === "chat") loadChatUnread();
  document.dispatchEvent(new CustomEvent("df:notification", { detail: n }));
});
ws.on("request_update", (p) => document.dispatchEvent(new CustomEvent("df:request_update", { detail: p })));
ws.on("agent_status", (p) => document.dispatchEvent(new CustomEvent("df:agent_status", { detail: p })));
ws.on("agent_log", (p) => document.dispatchEvent(new CustomEvent("df:agent_log", { detail: p })));
ws.on("chat_message", (p) => {
  document.dispatchEvent(new CustomEvent("df:chat_message", { detail: p }));
  loadChatUnread();
});
ws.on("chat_read", () => loadChatUnread());
ws.connect();

/* ---------- router ---------- */
const outlet = qs("#outlet");

const ROUTES = [
  { path: "/", title: "Overview", render: overview.render },
  { path: "/requests", title: "Requests", render: requests.render },
  { path: "/requests/:id", title: "Request", render: requestDetail.render },
  { path: "/services", title: "Service management", render: services.render },
  { path: "/services/:slug", title: "Service", render: services.renderDetail },
  { path: "/clients", title: "Clients", render: clients.render },
  { path: "/clients/:id", title: "Client", render: clients.renderDetail },
  { path: "/client-files", title: "Client files", render: clientFiles.render },
  { path: "/client-files/:id", title: "Client files", render: clientFiles.renderDetail },
  { path: "/projects", title: "Projects", render: projects.render },
  { path: "/billing", title: "Billing", render: billing.render },
  { path: "/leads", title: "Leads", render: leads.render },
  { path: "/leads/:id", title: "Lead", render: leads.renderDetail },
  { path: "/outreach", title: "Outreach", render: outreach.render },
  { path: "/chat", title: "Chat", render: chat.render },
  { path: "/chat/:id", title: "Chat", render: chat.render },
  { path: "/support", title: "Support", render: support.render },
  { path: "/support/:id", title: "Ticket", render: support.renderDetail },
  { path: "/agents", title: "AI Agent Control Center", render: agents.render },
  { path: "/analytics", title: "Analytics", render: analytics.render },
  { path: "/notifications", title: "Notifications", render: notifications.render },
  { path: "/users", title: "Users & roles", render: users.render },
  { path: "/audit", title: "Audit log", render: audit.render },
  { path: "/settings", title: "Settings", render: settings.render },
];

export const router = createRouter({
  routes: ROUTES.map((r) => ({ ...r, render: (page, params, query, current) => r.render(page, params, query, { ...current, user }) })),
  outlet,
  notFound: (o) => {
    o.innerHTML = `<div class="page"><div class="empty">${icon("help")}<h4>Page not found</h4><p><a href="#/">Back to overview</a></p></div></div>`;
  },
  onNavigate: (cur) => {
    const route = ROUTES.find((r) => r.path === (cur.route && cur.route.path));
    setTitle(route ? route.title : "Admin");
    highlightNav(cur.path);
    closeSidebar();
  },
});

window.dfAdmin = { router, user, openLink, refreshBadges: loadServiceCounts };

// Render the requested page straight away; the sidebar badges, chat and bell counts fill in as they arrive
// (renderServiceNav re-highlights the active item once the service counts are in).
router.start();
loadServiceCounts();
loadChatUnread();
api.get("/notifications/unread-count").then((c) => setUnread(c.unread_count)).catch(() => {});
