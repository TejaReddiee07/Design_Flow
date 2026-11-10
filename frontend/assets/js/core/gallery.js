/* Design gallery: thumbnail grid + lightbox + downloads. Shared by the admin "Client files" and portal "Your designs" pages.
   A gallery item is a library file item: {file_id, name, format, role, label, width, height, thumb_file_id, size_bytes, is_image}. */
import { api, errorMessage, fileUrl, downloadFile } from "./api.js";
import { esc, icon, qs, h, toast, modal, fmtBytes, setLoading } from "./ui.js";

const IMAGE_FORMATS = new Set(["png", "svg", "jpg", "jpeg", "webp", "gif"]);
const ROLE_ORDER = { board: 0, primary: 1, variant: 2, page: 3, notes: 8, package: 9 };
const FORMAT_LABEL = { pdf: "PDF", zip: "ZIP", md: "Notes", svg: "SVG", png: "PNG", jpg: "JPG" };

export function isImage(item) {
  return Boolean(item && (item.is_image || IMAGE_FORMATS.has(String(item.format || "").toLowerCase())));
}

export function sortItems(items) {
  return [...(items || [])].sort((a, b) => (ROLE_ORDER[a.role] ?? 5) - (ROLE_ORDER[b.role] ?? 5) || (a.page || 0) - (b.page || 0));
}

function dims(item) {
  return item.width && item.height ? `${item.width}×${item.height}` : "";
}

function metaLine(item) {
  const fmt = FORMAT_LABEL[String(item.format || "").toLowerCase()] || String(item.format || "file").toUpperCase();
  return [fmt, dims(item), item.size_bytes ? fmtBytes(item.size_bytes) : ""].filter(Boolean).join(" · ");
}

function fileIcon(fmt) {
  return { pdf: "file", zip: "download", md: "file", svg: "image" }[fmt] || "file";
}

/** One tile. `group` identifies the version the tile belongs to (lightbox navigates within it). */
export function tile(item, group, index) {
  const fmt = String(item.format || "").toLowerCase();
  const img = isImage(item);
  const src = img ? fileUrl(item.thumb_file_id || item.file_id) : "";
  const label = item.label || item.name || "File";
  const thumb = img
    ? `<img src="${esc(src)}" alt="${esc(label)}" loading="lazy" decoding="async">`
    : `<span class="dg-doc dg-doc-${esc(fmt || "file")}">${icon(fileIcon(fmt))}<b>${esc(FORMAT_LABEL[fmt] || fmt.toUpperCase() || "FILE")}</b></span>`;
  return `<figure class="dg-tile" data-dg-group="${esc(group)}" data-dg-index="${index}">
    <button type="button" class="dg-thumb ${img ? "" : "is-doc"}" ${img ? `data-dg-open title="Preview ${esc(label)}"` : `data-dg-dl="${item.file_id}" data-dg-name="${esc(item.name || label)}" title="Download ${esc(item.name || label)}"`}>${thumb}</button>
    <figcaption class="dg-meta">
      <div class="min-w-0">
        <div class="dg-label" title="${esc(label)}">${esc(label)}</div>
        <div class="dg-sub">${esc(metaLine(item))}</div>
      </div>
      <button type="button" class="btn btn-ghost btn-icon btn-sm" data-dg-dl="${item.file_id}" data-dg-name="${esc(item.name || label)}" aria-label="Download ${esc(item.name || label)}">${icon("download", "icon-sm")}</button>
    </figcaption>
  </figure>`;
}

/** A grid of tiles. Packages (ZIP) are offered by the "Download all" button instead of a tile. */
export function grid(items, group) {
  const list = sortItems(items).filter((i) => i.role !== "package" && String(i.format).toLowerCase() !== "zip");
  if (!list.length) return `<p class="dg-empty">${icon("image", "icon-sm")} No files in this version yet.</p>`;
  return `<div class="dg-grid">${list.map((it, i) => tile(it, group, i)).join("")}</div>`;
}

export function gridItems(items) {
  return sortItems(items).filter((i) => i.role !== "package" && String(i.format).toLowerCase() !== "zip");
}

/* ---------- lightbox ---------- */
export function openLightbox(items, start = 0, { title = "" } = {}) {
  const images = items.filter(isImage);
  if (!images.length) return;
  let i = Math.max(0, images.indexOf(items[start]));
  if (i < 0) i = 0;
  const body = h(`<div class="dg-lightbox">
    <div class="dg-stage">
      <button type="button" class="dg-nav prev" aria-label="Previous">${icon("chevron-left")}</button>
      <img alt="">
      <button type="button" class="dg-nav next" aria-label="Next">${icon("chevron-right")}</button>
    </div>
    <div class="dg-caption">
      <div class="min-w-0"><div class="dg-label"></div><div class="dg-sub"></div></div>
      <span class="dg-count"></span>
      <button type="button" class="btn btn-primary btn-sm" data-lb-dl>${icon("download", "icon-sm")} Download</button>
    </div>
  </div>`);
  const m = modal({ title: title || "Preview", body, size: "xl" });
  m.el.classList.add("dg-modal");
  const img = qs("img", body);
  const show = () => {
    const it = images[i];
    img.classList.remove("ready");
    img.onload = () => img.classList.add("ready");
    img.src = fileUrl(it.file_id);
    img.alt = it.label || it.name || "";
    qs(".dg-label", body).textContent = it.label || it.name || "";
    qs(".dg-sub", body).textContent = metaLine(it);
    qs(".dg-count", body).textContent = images.length > 1 ? `${i + 1} / ${images.length}` : "";
    qs(".prev", body).hidden = images.length < 2;
    qs(".next", body).hidden = images.length < 2;
  };
  const go = (d) => {
    i = (i + d + images.length) % images.length;
    show();
  };
  qs(".prev", body).onclick = () => go(-1);
  qs(".next", body).onclick = () => go(1);
  qs("[data-lb-dl]", body).onclick = (e) => saveFile(images[i], e.currentTarget);
  const onKey = (e) => {
    if (!document.body.contains(m.el)) return document.removeEventListener("keydown", onKey);
    if (e.key === "ArrowLeft") go(-1);
    if (e.key === "ArrowRight") go(1);
  };
  document.addEventListener("keydown", onKey);
  show();
}

/* ---------- downloads ---------- */
async function saveFile(item, btn) {
  setLoading(btn, true);
  try {
    await downloadFile(item.file_id, item.name || item.label || "design");
  } catch (err) {
    toast({ title: "Download failed", body: errorMessage(err), type: "error" });
  } finally {
    setLoading(btn, false);
  }
}

function filenameFrom(res, fallback) {
  const cd = res.headers.get("Content-Disposition") || "";
  const star = cd.match(/filename\*=UTF-8''([^;]+)/i);
  if (star) {
    try {
      return decodeURIComponent(star[1]);
    } catch {}
  }
  const plain = cd.match(/filename="?([^";]+)"?/i);
  return plain ? plain[1] : fallback;
}

/** Download a ZIP from an API path such as /library/deliveries/12/download. */
export async function downloadZip(path, fallbackName = "designs.zip", btn = null) {
  if (btn) setLoading(btn, true);
  try {
    const res = await api.raw(path);
    if (!res.ok) throw new Error(res.status === 404 ? "This package is no longer available" : `Download failed (${res.status})`);
    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filenameFrom(res, fallbackName);
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(url), 2000);
  } catch (err) {
    toast({ title: "Download failed", body: errorMessage(err), type: "error" });
  } finally {
    if (btn) setLoading(btn, false);
  }
}

/** Wire tiles inside `root`. `groups` maps a group key to its items (as passed to grid()). */
export function bindGallery(root, groups, { titleFor = () => "" } = {}) {
  root.addEventListener("click", (e) => {
    const dl = e.target.closest("[data-dg-dl]");
    if (dl && root.contains(dl)) {
      e.preventDefault();
      saveFile({ file_id: Number(dl.dataset.dgDl), name: dl.dataset.dgName }, dl);
      return;
    }
    const open = e.target.closest("[data-dg-open]");
    if (open && root.contains(open)) {
      e.preventDefault();
      const fig = open.closest("[data-dg-group]");
      const key = fig.dataset.dgGroup;
      const items = gridItems(groups.get(key) || []);
      openLightbox(items, Number(fig.dataset.dgIndex) || 0, { title: titleFor(key) });
    }
  });
}
