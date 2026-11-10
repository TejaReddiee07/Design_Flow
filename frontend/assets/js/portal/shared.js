/* Shared helpers for the client portal (no core files are modified). */
import { api, errorMessage } from "../core/api.js";
import { icon, esc, h, qs, qsa, toast, fmtBytes, fmtDate, timeAgo, statusBadge, priorityBadge, titleCase, emptyState } from "../core/ui.js";

export const state = { user: null, services: null, unread: 0, activeCount: 0 };

export const STATUS_ORDER = ["pending", "accepted", "in_progress", "review", "completed"];

/* ---------- services (cached) ---------- */
export async function getServices(force = false) {
  if (!state.services || force) state.services = await api.get("/services");
  return state.services;
}

export async function serviceBySlug(slug) {
  const list = await getServices();
  return list.find((s) => s.slug === slug) || (await api.get(`/services/${slug}`));
}

export function serviceIcon(name, cls = "") {
  return icon(`svc-${name || "custom"}`, cls);
}

/* ---------- navigation ---------- */
export function navigateLink(link) {
  if (!link) return;
  if (link.startsWith("/portal")) {
    const hash = link.includes("#") ? link.slice(link.indexOf("#") + 1) : "/";
    location.hash = hash;
    return;
  }
  if (link.startsWith("#")) {
    location.hash = link.slice(1);
    return;
  }
  if (link.startsWith("/")) location.href = link;
}

export function setPageTitle(title) {
  const el = qs("#page-title");
  if (el) el.textContent = title;
  document.title = `${title} — Designflow`;
}

/* ---------- page scaffolding ---------- */
export function pageHeader({ title, sub = "", actions = "" }) {
  return `<div class="page-header">
    <div><h1>${esc(title)}</h1>${sub ? `<p class="sub">${esc(sub)}</p>` : ""}</div>
    ${actions ? `<div class="flex gap-2 wrap">${actions}</div>` : ""}
  </div>`;
}

export function card(title, body, { actions = "", id = "", cls = "" } = {}) {
  return `<div class="card ${cls}" ${id ? `id="${id}"` : ""}>
    ${title ? `<div class="card-header"><h3>${esc(title)}</h3>${actions ? `<div class="flex gap-2">${actions}</div>` : ""}</div>` : ""}
    <div class="card-body">${body}</div>
  </div>`;
}

export function errorBox(err) {
  return `<div class="inline-alert danger">${icon("alert")}<span>${esc(errorMessage(err))}</span></div>`;
}

export function reportError(err, title = "Something went wrong") {
  console.error(err);
  toast({ title, body: errorMessage(err), type: "error" });
}

/* ---------- pricing (pay per request) ---------- */
export function clientCurrency() {
  const c = state.user && state.user.client && state.user.client.currency;
  return ["USD", "GBP", "INR"].includes(c) ? c : "USD";
}

export function fmtPrice(amount, currency) {
  const cur = currency || clientCurrency();
  const n = Number(amount || 0);
  try {
    const locale = cur === "INR" ? "en-IN" : cur === "GBP" ? "en-GB" : "en-US";
    return new Intl.NumberFormat(locale, { style: "currency", currency: cur, maximumFractionDigits: 0 }).format(n);
  } catch {
    return `${cur} ${Math.round(n)}`;
  }
}

/** Price of a service in the client's currency (falls back to USD). */
export function priceFor(service, currency = clientCurrency()) {
  const p = (service && service.prices) || {};
  const amount = p[currency] != null ? p[currency] : p.USD != null ? p.USD : service.starting_price || 0;
  return { amount: Number(amount), currency: p[currency] != null ? currency : "USD", unit: service.price_unit || "per request" };
}

export function deliveryText(days) {
  return `${days}-day delivery`;
}

export function paidBadge(r) {
  if (!r.price_amount) return "";
  return r.is_paid ? `<span class="badge badge-success">${icon("check", "icon-sm")} Paid</span>` : `<span class="badge badge-warning">Unpaid</span>`;
}

/**
 * Pay for a request. Mock provider settles instantly; Stripe redirects to checkout.
 * Returns the updated request (or null when redirected).
 */
export async function payRequest(id, btn = null) {
  if (btn) btn.classList.add("loading"), (btn.disabled = true);
  try {
    const res = await api.post(`/requests/${id}/pay`);
    if (res.checkout_url) {
      toast({ title: "Redirecting to secure checkout…", type: "info", timeout: 2500 });
      location.href = res.checkout_url;
      return null;
    }
    if (res.paid) toast({ title: "Payment received", body: "Thank you. Your request is in the queue.", type: "success" });
    return res.request;
  } catch (err) {
    reportError(err, "Payment failed");
    return null;
  } finally {
    if (btn) btn.classList.remove("loading"), (btn.disabled = false);
  }
}

/* ---------- requests ---------- */
export function requestRow(r) {
  const due = r.due_at && !["completed", "rejected"].includes(r.status) ? `<span>${icon("clock", "icon-sm")} due ${fmtDate(r.due_at)}</span>` : "";
  const price = r.price_amount ? `<span class="req-price">${fmtPrice(r.price_amount, r.price_currency)}</span>` : "";
  return `<a class="req-row" href="#/requests/${r.id}">
    <span class="svc-ico">${serviceIcon(iconForSlug(r.service_slug))}</span>
    <div class="min-w-0">
      <div class="ttl truncate">${esc(r.title)}</div>
      <div class="meta">
        <span>${esc(r.service_name)}</span>
        <span>${icon("calendar", "icon-sm")} ${fmtDate(r.submitted_at || r.created_at)}</span>
        ${due}
        ${r.revision_count ? `<span>${icon("repeat", "icon-sm")} ${r.revision_count} revision${r.revision_count > 1 ? "s" : ""}</span>` : ""}
        ${r.project_name ? `<span>${icon("layers", "icon-sm")} ${esc(r.project_name)}</span>` : ""}
      </div>
    </div>
    <div class="badges">${price}${paidBadge(r)}${statusBadge(r.status)}${priorityBadge(r.priority)}</div>
  </a>`;
}

const SLUG_ICON = {};
export function iconForSlug(slug) {
  if (SLUG_ICON[slug]) return SLUG_ICON[slug];
  const s = (state.services || []).find((x) => x.slug === slug);
  if (s) SLUG_ICON[slug] = s.icon;
  return s ? s.icon : "custom";
}

export function stageTrack(r) {
  if (r.status === "rejected") return `<div class="stage-track rejected"><i class="st"></i><i class="st"></i><i class="st"></i><i class="st"></i><i class="st"></i></div>`;
  const idx = STATUS_ORDER.indexOf(r.status);
  return `<div class="stage-track">${STATUS_ORDER.map((s, i) => `<i class="st ${i < idx ? "done" : i === idx ? "cur" : ""}" title="${esc(titleCase(s))}"></i>`).join("")}</div>`;
}

/* ---------- files ---------- */
export function fileIconName(mime = "", name = "") {
  if (mime.startsWith("image/")) return "image";
  if (mime === "application/pdf") return "file";
  if (/zip|rar|7z/.test(mime) || /\.(zip|rar|7z)$/i.test(name)) return "folder";
  if (mime.startsWith("video/")) return "play";
  return "file";
}

export function kindBadge(kind) {
  const map = { upload: "", design: "badge-purple", delivery: "badge-success", brand_asset: "badge-cyan", chat: "badge-info", revision: "badge-warning" };
  return `<span class="badge ${map[kind] || ""}">${esc(titleCase(kind))}</span>`;
}

export function fileChip(f, { removable = false } = {}) {
  return `<span class="file-chip" data-file-id="${f.id}">${icon(fileIconName(f.mime_type, f.original_name), "icon-sm")}<span class="name" title="${esc(f.original_name)}">${esc(f.original_name)}</span><span class="text-4 text-xs">${fmtBytes(f.size_bytes)}</span>${
    removable ? `<button type="button" class="btn btn-ghost btn-icon btn-sm" data-remove-file="${f.id}" aria-label="Remove">${icon("x", "icon-sm")}</button>` : ""
  }</span>`;
}

/**
 * Drag & drop uploader. Uploads immediately and keeps the returned file records.
 */
export function createDropzone(container, { request_id = null, kind = "upload", onChange = null, hint = "PNG, JPG, SVG, PDF, AI, PSD, PPTX, ZIP… up to 50 MB each" } = {}) {
  const files = [];
  let uploading = 0;
  container.innerHTML = `
    <div class="dropzone" tabindex="0" role="button">
      ${icon("upload", "icon-lg")}
      <div class="mt-2"><b>Drop files here</b> or click to browse</div>
      <div class="hint mt-1">${esc(hint)}</div>
      <input type="file" multiple hidden>
    </div>
    <div class="chips mt-3 dz-files"></div>`;
  const zone = qs(".dropzone", container);
  const input = qs("input[type=file]", container);
  const list = qs(".dz-files", container);

  function render() {
    list.innerHTML = files.map((f) => fileChip(f, { removable: true })).join("") + (uploading ? `<span class="file-chip">${icon("refresh", "icon-sm")} Uploading ${uploading} file${uploading > 1 ? "s" : ""}…</span>` : "");
  }

  async function upload(fileList) {
    const arr = Array.from(fileList || []);
    if (!arr.length) return;
    uploading += arr.length;
    render();
    for (const file of arr) {
      const fd = new FormData();
      fd.append("file", file);
      fd.append("kind", kind);
      if (request_id) fd.append("request_id", String(request_id));
      try {
        const res = await api.upload("/files/upload", fd);
        files.push(res);
      } catch (err) {
        toast({ title: `Could not upload ${file.name}`, body: errorMessage(err), type: "error" });
      } finally {
        uploading -= 1;
        render();
        if (onChange) onChange(files.map((f) => f.id), files);
      }
    }
  }

  zone.addEventListener("click", () => input.click());
  zone.addEventListener("keydown", (e) => (e.key === "Enter" || e.key === " ") && (e.preventDefault(), input.click()));
  input.addEventListener("change", () => {
    upload(input.files);
    input.value = "";
  });
  ["dragenter", "dragover"].forEach((ev) => zone.addEventListener(ev, (e) => {
    e.preventDefault();
    zone.classList.add("drag");
  }));
  ["dragleave", "drop"].forEach((ev) => zone.addEventListener(ev, (e) => {
    e.preventDefault();
    zone.classList.remove("drag");
  }));
  zone.addEventListener("drop", (e) => upload(e.dataTransfer.files));
  list.addEventListener("click", async (e) => {
    const btn = e.target.closest("[data-remove-file]");
    if (!btn) return;
    const id = Number(btn.dataset.removeFile);
    const idx = files.findIndex((f) => f.id === id);
    if (idx < 0) return;
    try {
      await api.del(`/files/${id}`);
    } catch {}
    files.splice(idx, 1);
    render();
    if (onChange) onChange(files.map((f) => f.id), files);
  });

  return {
    ids: () => files.map((f) => f.id),
    files,
    busy: () => uploading > 0,
    reset() {
      files.length = 0;
      render();
    },
  };
}

/* ---------- dynamic brief forms ---------- */
export function renderFields(schema = [], values = {}) {
  return schema
    .map((f) => {
      const key = esc(f.key);
      const name = `f_${key}`;
      const val = values[f.key];
      const req = f.required ? '<span class="req">*</span>' : "";
      const label = `<label class="label" for="${name}">${esc(f.label)} ${req}</label>`;
      const hint = f.help ? `<span class="hint">${esc(f.help)}</span>` : "";
      let control = "";
      switch (f.type) {
        case "textarea":
          control = `<textarea class="textarea" id="${name}" name="${name}" data-key="${key}" placeholder="${esc(f.placeholder || "")}">${esc(val || "")}</textarea>`;
          break;
        case "select":
          control = `<select class="select" id="${name}" name="${name}" data-key="${key}"><option value="">Select…</option>${(f.options || [])
            .map((o) => `<option value="${esc(o)}" ${val === o ? "selected" : ""}>${esc(o)}</option>`)
            .join("")}</select>`;
          break;
        case "multiselect": {
          const chosen = Array.isArray(val) ? val : val ? [val] : [];
          control = `<div class="chips" data-key="${key}" data-multi="1">${(f.options || [])
            .map((o) => `<label class="chip"><input type="checkbox" name="${name}" value="${esc(o)}" ${chosen.includes(o) ? "checked" : ""}>${esc(o)}</label>`)
            .join("")}</div>`;
          break;
        }
        case "number":
          control = `<input class="input" type="number" id="${name}" name="${name}" data-key="${key}" min="0" step="1" value="${esc(val ?? "")}" placeholder="${esc(f.placeholder || "")}">`;
          break;
        case "url":
          control = `<input class="input" type="url" id="${name}" name="${name}" data-key="${key}" value="${esc(val || "")}" placeholder="${esc(f.placeholder || "https://")}">`;
          break;
        case "color":
          control = `<div class="color-field"><input type="color" id="${name}" name="${name}" data-key="${key}" value="${esc(val || "#6366f1")}"><input class="input" type="text" data-color-text="${key}" value="${esc(val || "#6366f1")}" placeholder="#RRGGBB"></div>`;
          break;
        default:
          control = `<input class="input" type="text" id="${name}" name="${name}" data-key="${key}" value="${esc(val || "")}" placeholder="${esc(f.placeholder || "")}">`;
      }
      const wide = f.type === "textarea" || f.type === "multiselect";
      return `<div class="field ${wide ? "span-2" : ""}">${label}${control}${hint}</div>`;
    })
    .join("");
}

export function readFields(root, schema = []) {
  const brief = {};
  schema.forEach((f) => {
    if (f.type === "multiselect") {
      brief[f.key] = qsa(`[data-key="${f.key}"] input:checked`, root).map((i) => i.value);
      return;
    }
    const el = qs(`[data-key="${f.key}"]`, root);
    if (!el) return;
    let v = el.value;
    if (f.type === "number") v = v === "" ? "" : Number(v);
    brief[f.key] = typeof v === "string" ? v.trim() : v;
  });
  return brief;
}

export function validateFields(root, schema = []) {
  const missing = [];
  schema.forEach((f) => {
    if (!f.required) return;
    if (f.type === "multiselect") {
      if (!qsa(`[data-key="${f.key}"] input:checked`, root).length) missing.push(f.label);
      return;
    }
    const el = qs(`[data-key="${f.key}"]`, root);
    const v = el ? String(el.value || "").trim() : "";
    el && el.classList.toggle("invalid", !v);
    if (!v) missing.push(f.label);
  });
  return missing;
}

export function wireColorFields(root) {
  qsa("input[type=color][data-key]", root).forEach((c) => {
    const text = qs(`[data-color-text="${c.dataset.key}"]`, root);
    if (!text) return;
    c.addEventListener("input", () => (text.value = c.value));
    text.addEventListener("input", () => {
      if (/^#[0-9a-fA-F]{6}$/.test(text.value)) c.value = text.value;
    });
  });
}

/* Brief as key/value HTML using the schema labels */
export function briefTable(brief = {}, schema = []) {
  const labels = {};
  schema.forEach((f) => (labels[f.key] = f.label));
  const rows = Object.entries(brief)
    .filter(([, v]) => v !== "" && v !== null && v !== undefined && !(Array.isArray(v) && !v.length))
    .map(([k, v]) => {
      const val = Array.isArray(v) ? v.join(", ") : String(v);
      const isColor = /^#[0-9a-fA-F]{6}$/.test(val);
      return `<dt>${esc(labels[k] || titleCase(k))}</dt><dd>${isColor ? `<span class="swatch" style="background:${esc(val)}"></span> ` : ""}${esc(val)}</dd>`;
    });
  return rows.length ? `<dl class="kv">${rows.join("")}</dl>` : `<p class="text-3 text-sm">No brief details were provided.</p>`;
}

export { emptyState, timeAgo };
