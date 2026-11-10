/* UI helpers: icons, DOM, formatting, toasts, modals, theme. ES module. */

export const ICONS = "/assets/img/icons.svg";

export function icon(name, cls = "") {
  return `<svg class="icon ${cls}" aria-hidden="true"><use href="${ICONS}#${name}"></use></svg>`;
}

export const qs = (sel, root = document) => root.querySelector(sel);
export const qsa = (sel, root = document) => Array.from(root.querySelectorAll(sel));

export function h(html) {
  const t = document.createElement("template");
  t.innerHTML = html.trim();
  return t.content.firstElementChild;
}

export function esc(value) {
  if (value === null || value === undefined) return "";
  return String(value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

export function nl2br(value) {
  return esc(value).replace(/\n/g, "<br>");
}

/* ---------- formatting ---------- */
const dateFmt = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", year: "numeric" });
const dateTimeFmt = new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });

export function parseDate(v) {
  if (!v) return null;
  if (v instanceof Date) return v;
  let s = String(v);
  if (!/[zZ]|[+-]\d\d:?\d\d$/.test(s)) s += "Z";
  const d = new Date(s);
  return isNaN(d) ? null : d;
}

export function fmtDate(v) {
  const d = parseDate(v);
  return d ? dateFmt.format(d) : "";
}

export function fmtDateTime(v) {
  const d = parseDate(v);
  return d ? dateTimeFmt.format(d) : "";
}

export function timeAgo(v) {
  const d = parseDate(v);
  if (!d) return "";
  const s = Math.floor((Date.now() - d.getTime()) / 1000);
  if (s < 45) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  if (s < 86400 * 7) return `${Math.floor(s / 86400)}d ago`;
  return fmtDate(d);
}

export function fmtMoney(amount, currency = "USD", opts = {}) {
  const n = Number(amount || 0);
  try {
    return new Intl.NumberFormat(undefined, { style: "currency", currency, maximumFractionDigits: opts.cents === false ? 0 : 2, ...opts }).format(n);
  } catch {
    return `${currency} ${n.toFixed(2)}`;
  }
}

export function fmtNum(n) {
  return new Intl.NumberFormat().format(Number(n || 0));
}

export function fmtBytes(b) {
  const n = Number(b || 0);
  if (n < 1024) return `${n} B`;
  if (n < 1024 * 1024) return `${(n / 1024).toFixed(1)} KB`;
  return `${(n / 1024 / 1024).toFixed(1)} MB`;
}

export function initials(name = "") {
  // Skip words that start with punctuation ("Brew & Bean" -> "BB", not "B&").
  return String(name || "")
    .split(/\s+/)
    .filter((w) => /^[\p{L}\p{N}]/u.test(w))
    .slice(0, 2)
    .map((p) => p[0].toUpperCase())
    .join("") || "?";
}

export function titleCase(s = "") {
  return String(s).replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/* ---------- status helpers ---------- */
export const STATUS_LABELS = {
  pending: "Pending",
  accepted: "Accepted",
  rejected: "Rejected",
  in_progress: "In Progress",
  review: "In Review",
  completed: "Completed",
};

export function statusBadge(status) {
  return `<span class="badge status-${esc(status)}">${esc(STATUS_LABELS[status] || titleCase(status))}</span>`;
}

export function priorityBadge(p) {
  return `<span class="badge priority-${esc(p)}">${esc(titleCase(p))}</span>`;
}

export function agentBadge(status) {
  return `<span class="badge agent-${esc(status)}">${status === "running" ? '<span class="live-dot"></span>' : ""}${esc(titleCase(status))}</span>`;
}

export const NOTIF_ICONS = {
  new_request: "inbox",
  request_status: "activity",
  revision: "repeat",
  file_upload: "upload",
  payment: "credit-card",
  lead: "target",
  agent: "cpu",
  approval_needed: "check-circle",
  delivery: "download",
  chat: "message",
  support: "life-buoy",
  system: "info",
};

/* ---------- theme ---------- */
const THEME_KEY = "df-theme";

export function getTheme() {
  try {
    return localStorage.getItem(THEME_KEY) || "system";
  } catch {
    return "system";
  }
}

export function applyTheme(theme) {
  const root = document.documentElement;
  // pages built on the Prism look are dark only
  if (root.hasAttribute("data-theme-lock")) theme = "dark";
  if (theme === "dark" || theme === "light") root.setAttribute("data-theme", theme);
  else root.removeAttribute("data-theme");
  qsa("[data-theme-toggle]").forEach((b) => {
    b.innerHTML = icon(isDark() ? "sun" : "moon");
    b.setAttribute("aria-label", isDark() ? "Switch to light mode" : "Switch to dark mode");
  });
  document.dispatchEvent(new CustomEvent("themechange", { detail: { theme, dark: isDark() } }));
}

export function isDark() {
  const t = document.documentElement.getAttribute("data-theme");
  if (t) return t === "dark";
  return window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches;
}

export function toggleTheme() {
  const next = isDark() ? "light" : "dark";
  try {
    localStorage.setItem(THEME_KEY, next);
  } catch {}
  applyTheme(next);
}

export function initTheme() {
  applyTheme(getTheme());
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-theme-toggle]");
    if (b) toggleTheme();
  });
  if (window.matchMedia) {
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
      if (getTheme() === "system") applyTheme("system");
    });
  }
}

/* ---------- toasts ---------- */
let toastStack;

export function toast({ title, body = "", type = "info", timeout = 4500, onClick } = {}) {
  if (!toastStack) {
    toastStack = h('<div class="toast-stack" role="status" aria-live="polite"></div>');
    document.body.appendChild(toastStack);
  }
  const icons = { success: "check-circle", error: "alert", info: "info", warning: "alert" };
  const el = h(`
    <div class="toast toast-${esc(type)}">
      ${icon(icons[type] || "info")}
      <div class="min-w-0 flex-1">
        <div class="toast-title">${esc(title)}</div>
        ${body ? `<div class="toast-body">${esc(body)}</div>` : ""}
      </div>
    </div>`);
  const remove = () => {
    el.classList.add("leaving");
    setTimeout(() => el.remove(), 220);
  };
  el.addEventListener("click", () => {
    if (onClick) onClick();
    remove();
  });
  toastStack.appendChild(el);
  if (timeout) setTimeout(remove, timeout);
  return el;
}

/* ---------- modal ---------- */
export function modal({ title = "", body = "", footer = "", size = "", onClose, closable = true } = {}) {
  const backdrop = h(`
    <div class="modal-backdrop" role="dialog" aria-modal="true">
      <div class="modal ${size ? "modal-" + size : ""}">
        <div class="modal-header">
          <h3>${esc(title)}</h3>
          ${closable ? `<button class="btn btn-ghost btn-icon" data-close aria-label="Close">${icon("x")}</button>` : ""}
        </div>
        <div class="modal-body"></div>
        ${footer ? '<div class="modal-footer"></div>' : ""}
      </div>
    </div>`);
  const bodyEl = qs(".modal-body", backdrop);
  if (typeof body === "string") bodyEl.innerHTML = body;
  else bodyEl.appendChild(body);
  if (footer) {
    const f = qs(".modal-footer", backdrop);
    if (typeof footer === "string") f.innerHTML = footer;
    else f.appendChild(footer);
  }
  const close = () => {
    backdrop.remove();
    document.removeEventListener("keydown", onKey);
    if (onClose) onClose();
  };
  const onKey = (e) => {
    if (e.key === "Escape" && closable) close();
  };
  document.addEventListener("keydown", onKey);
  backdrop.addEventListener("click", (e) => {
    if (e.target === backdrop && closable) close();
    if (e.target.closest("[data-close]")) close();
  });
  document.body.appendChild(backdrop);
  const first = qs("input, textarea, select, button.btn-primary", bodyEl);
  if (first) setTimeout(() => first.focus(), 50);
  return { el: backdrop, body: bodyEl, close };
}

export function confirmDialog({ title = "Are you sure?", body = "", confirmText = "Confirm", cancelText = "Cancel", danger = false } = {}) {
  return new Promise((resolve) => {
    const footer = h(`<div class="flex gap-3 justify-end w-full">
      <button class="btn btn-secondary" data-cancel>${esc(cancelText)}</button>
      <button class="btn ${danger ? "btn-danger" : "btn-primary"}" data-ok>${esc(confirmText)}</button>
    </div>`);
    const m = modal({ title, body: `<p class="text-2">${esc(body)}</p>`, footer, onClose: () => resolve(false) });
    qs("[data-cancel]", footer).onclick = () => m.close();
    qs("[data-ok]", footer).onclick = () => {
      resolve(true);
      m.el.remove();
    };
  });
}

export function promptDialog({ title, label = "", placeholder = "", multiline = false, confirmText = "Save", value = "" } = {}) {
  return new Promise((resolve) => {
    const body = h(`<div class="field"><label class="label">${esc(label)}</label>${
      multiline
        ? `<textarea class="textarea" placeholder="${esc(placeholder)}">${esc(value)}</textarea>`
        : `<input class="input" placeholder="${esc(placeholder)}" value="${esc(value)}">`
    }</div>`);
    const footer = h(`<div class="flex gap-3 justify-end w-full">
      <button class="btn btn-secondary" data-cancel>Cancel</button>
      <button class="btn btn-primary" data-ok>${esc(confirmText)}</button></div>`);
    const m = modal({ title, body, footer, onClose: () => resolve(null) });
    const input = qs("textarea, input", body);
    qs("[data-cancel]", footer).onclick = () => m.close();
    qs("[data-ok]", footer).onclick = () => {
      resolve(input.value);
      m.el.remove();
    };
    if (!multiline) input.addEventListener("keydown", (e) => e.key === "Enter" && qs("[data-ok]", footer).click());
  });
}

export function drawer({ title = "", body = "" } = {}) {
  const scrim = h('<div class="drawer-backdrop"></div>');
  const el = h(`<aside class="drawer">
    <div class="drawer-header"><h3 class="text-md">${esc(title)}</h3><button class="btn btn-ghost btn-icon" data-close>${icon("x")}</button></div>
    <div class="drawer-body"></div></aside>`);
  const bodyEl = qs(".drawer-body", el);
  if (typeof body === "string") bodyEl.innerHTML = body;
  else bodyEl.appendChild(body);
  const close = () => {
    scrim.remove();
    el.remove();
  };
  scrim.onclick = close;
  qs("[data-close]", el).onclick = close;
  document.body.append(scrim, el);
  return { el, body: bodyEl, close };
}

/* ---------- misc ---------- */
export function debounce(fn, ms = 250) {
  let t;
  return (...a) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...a), ms);
  };
}

export function onClickOutside(el, fn) {
  const handler = (e) => {
    if (!el.contains(e.target)) fn(e);
  };
  setTimeout(() => document.addEventListener("click", handler), 0);
  return () => document.removeEventListener("click", handler);
}

export function emptyState(iconName, title, body = "") {
  return `<div class="empty">${icon(iconName)}<h4>${esc(title)}</h4><p>${esc(body)}</p></div>`;
}

export function skeletonRows(n = 4) {
  return Array.from({ length: n }, () => '<div class="skeleton" style="height:56px;margin-bottom:10px"></div>').join("");
}

export function setLoading(btn, loading) {
  if (!btn) return;
  btn.classList.toggle("loading", loading);
  btn.disabled = loading;
}

export function serializeForm(form) {
  const data = {};
  new FormData(form).forEach((v, k) => {
    if (data[k] !== undefined) {
      data[k] = Array.isArray(data[k]) ? [...data[k], v] : [data[k], v];
    } else data[k] = v;
  });
  qsa("input[type=checkbox]", form).forEach((c) => {
    if (c.name && !c.closest(".chip")) data[c.name] = c.checked;
  });
  return data;
}

export function revealOnScroll(selector = ".reveal") {
  const els = qsa(selector);
  if (!("IntersectionObserver" in window)) {
    els.forEach((e) => e.classList.add("in"));
    return;
  }
  const io = new IntersectionObserver(
    (entries) => entries.forEach((en) => en.isIntersecting && (en.target.classList.add("in"), io.unobserve(en.target))),
    { threshold: 0.12 }
  );
  els.forEach((e) => io.observe(e));
}

export function animateCount(el, to, { duration = 1200, prefix = "", suffix = "", decimals = 0 } = {}) {
  const start = performance.now();
  const from = 0;
  const step = (now) => {
    const p = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - p, 3);
    el.textContent = prefix + (from + (to - from) * eased).toFixed(decimals) + suffix;
    if (p < 1) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

export function queryParams() {
  const out = {};
  const hash = location.hash.includes("?") ? location.hash.split("?")[1] : "";
  new URLSearchParams(hash || location.search).forEach((v, k) => (out[k] = v));
  return out;
}

export function copyText(text) {
  return navigator.clipboard?.writeText(text).then(() => toast({ title: "Copied", type: "success", timeout: 1500 }));
}
