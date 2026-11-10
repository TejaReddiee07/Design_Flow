/* Files & brand assets */
import { api, errorMessage, downloadFile } from "../core/api.js";
import { icon, esc, qs, qsa, h, modal, confirmDialog, toast, setLoading, fmtBytes, fmtDate, titleCase, skeletonRows, emptyState } from "../core/ui.js";
import { pageHeader, fileIconName, kindBadge, createDropzone, errorBox, reportError } from "./shared.js";

const ASSET_TYPES = ["logo", "font", "color", "guideline", "image", "other"];
const ASSET_BADGE = { logo: "badge-purple", font: "badge-info", color: "badge-pink", guideline: "badge-cyan", image: "badge-success", other: "" };

export async function renderFiles(page) {
  page.innerHTML = `
    ${pageHeader({ title: "Files & brand assets", sub: "Everything you've uploaded and everything we've delivered.", actions: `<button class="btn btn-secondary" id="btn-upload">${icon("upload")} Upload files</button><button class="btn btn-primary" id="btn-asset">${icon("plus")} Add brand asset</button>` })}
    <div class="card mb-6"><div class="card-header"><h3>Brand assets</h3><span class="text-xs text-3">Logos, colours, fonts and guidelines our agents use on every request</span></div><div class="card-body" id="assets">${skeletonRows(2)}</div></div>
    <div class="card"><div class="card-header"><h3>All files</h3><div class="segmented" id="kind-filter"><button class="active" data-kind="">All</button><button data-kind="upload">Uploads</button><button data-kind="delivery">Deliveries</button><button data-kind="design">Designs</button></div></div><div class="card-body" id="files">${skeletonRows(4)}</div></div>`;

  let kind = "";

  async function loadAssets() {
    const el = qs("#assets", page);
    try {
      const rows = await api.get("/brand-assets");
      el.innerHTML = rows.length
        ? `<div class="grid grid-3">${rows.map((a) => `<div class="card card-compact"><div class="card-body flex items-center gap-3">
            ${a.type === "color" && a.value ? `<span class="swatch" style="width:36px;height:36px;border-radius:10px;background:${esc(a.value)}"></span>` : `<span class="file-ico">${icon(a.type === "font" ? "type" : a.type === "logo" ? "svc-logo" : a.type === "guideline" ? "file" : "image", "icon-sm")}</span>`}
            <div class="min-w-0 flex-1"><div class="font-semibold text-sm truncate">${esc(a.name)}</div><div class="text-xs text-3 flex gap-2 items-center"><span class="badge ${ASSET_BADGE[a.type] || ""}">${esc(titleCase(a.type))}</span>${a.value ? `<span class="truncate">${esc(a.value)}</span>` : ""}${a.version > 1 ? `<span>v${a.version}</span>` : ""}</div></div>
            <div class="flex gap-1">${a.file_id ? `<button class="btn btn-ghost btn-icon btn-sm" data-dl="${a.file_id}" data-name="${esc(a.name)}" aria-label="Download">${icon("download", "icon-sm")}</button>` : ""}<button class="btn btn-ghost btn-icon btn-sm" data-del-asset="${a.id}" aria-label="Delete">${icon("trash", "icon-sm")}</button></div>
          </div></div>`).join("")}</div>`
        : emptyState("palette", "No brand assets yet", "Add your logo, colours and fonts so every design stays on-brand.");
    } catch (err) {
      el.innerHTML = errorBox(err);
    }
  }

  async function loadFiles() {
    const el = qs("#files", page);
    el.innerHTML = skeletonRows(4);
    try {
      const rows = await api.get("/files", { kind: kind || undefined, limit: 300 });
      el.innerHTML = rows.length
        ? `<div class="table-wrap"><table class="table"><thead><tr><th>File</th><th>Type</th><th>Size</th><th>Request</th><th>Added</th><th></th></tr></thead><tbody>${rows
            .map((f) => `<tr><td><div class="flex items-center gap-3"><span class="file-ico">${icon(fileIconName(f.mime_type, f.original_name), "icon-sm")}</span><span class="truncate" style="max-width:280px" title="${esc(f.original_name)}">${esc(f.original_name)}</span>${f.version > 1 ? `<span class="badge">v${f.version}</span>` : ""}</div></td><td>${kindBadge(f.kind)}</td><td>${fmtBytes(f.size_bytes)}</td><td>${f.request_id ? `<a href="#/requests/${f.request_id}">#${f.request_id}</a>` : "—"}</td><td>${fmtDate(f.created_at)}</td><td class="text-right"><div class="flex gap-1 justify-end"><button class="btn btn-ghost btn-sm" data-dl="${f.id}" data-name="${esc(f.original_name)}" aria-label="Download">${icon("download", "icon-sm")}</button>${["upload", "brand_asset", "chat", "revision"].includes(f.kind) ? `<button class="btn btn-ghost btn-sm" data-del-file="${f.id}" aria-label="Delete">${icon("trash", "icon-sm")}</button>` : ""}</div></td></tr>`)
            .join("")}</tbody></table></div>`
        : emptyState("folder", "No files here yet", "Upload reference files or wait for your first delivery.");
    } catch (err) {
      el.innerHTML = errorBox(err);
    }
  }

  page.addEventListener("click", async (e) => {
    const dl = e.target.closest("[data-dl]");
    if (dl) return downloadFile(Number(dl.dataset.dl), dl.dataset.name || "file").catch((err) => reportError(err, "Download failed"));
    const delA = e.target.closest("[data-del-asset]");
    if (delA) {
      if (!(await confirmDialog({ title: "Delete brand asset?", confirmText: "Delete", danger: true }))) return;
      try {
        await api.del(`/brand-assets/${delA.dataset.delAsset}`);
        toast({ title: "Asset deleted", type: "success" });
        loadAssets();
      } catch (err) {
        reportError(err);
      }
    }
    const delF = e.target.closest("[data-del-file]");
    if (delF) {
      if (!(await confirmDialog({ title: "Delete this file?", body: "This cannot be undone.", confirmText: "Delete", danger: true }))) return;
      try {
        await api.del(`/files/${delF.dataset.delFile}`);
        toast({ title: "File deleted", type: "success" });
        loadFiles();
      } catch (err) {
        reportError(err);
      }
    }
  });

  qs("#kind-filter", page).addEventListener("click", (e) => {
    const b = e.target.closest("[data-kind]");
    if (!b) return;
    kind = b.dataset.kind;
    qsa("button", qs("#kind-filter", page)).forEach((x) => x.classList.toggle("active", x === b));
    loadFiles();
  });

  qs("#btn-upload", page).addEventListener("click", () => {
    const body = h('<div><div id="up-dz"></div></div>');
    const m = modal({ title: "Upload files", body, footer: `<button class="btn btn-primary" data-close>Done</button>` });
    createDropzone(qs("#up-dz", body), { kind: "upload", onChange: () => loadFiles() });
    m.el.addEventListener("click", (e) => e.target.closest("[data-close]") && loadFiles());
  });

  qs("#btn-asset", page).addEventListener("click", () => {
    const body = h(`<form id="asset-form" class="form-grid">
      <div class="field"><label class="label">Type</label><select class="select" name="type">${ASSET_TYPES.map((t) => `<option value="${t}">${titleCase(t)}</option>`).join("")}</select></div>
      <div class="field"><label class="label">Name <span class="req">*</span></label><input class="input" name="name" placeholder="Primary logo, Brand teal, Heading font…"></div>
      <div class="field span-2" id="value-field"><label class="label">Value</label><div class="color-field"><input type="color" name="color" value="#6366f1"><input class="input" name="value" placeholder="#RRGGBB or font name"></div></div>
      <div class="field span-2"><label class="label">File <span class="text-4">(optional for colours and fonts)</span></label><div id="asset-dz"></div></div>
      <p class="error-text span-2 hidden" id="asset-error"></p>
    </form>`);
    const footer = h(`<div class="flex gap-2 justify-end w-full"><button class="btn btn-secondary" type="button" data-cancel>Cancel</button><button class="btn btn-primary" type="button" data-save>Save asset</button></div>`);
    const m = modal({ title: "Add brand asset", body, footer });
    const dz = createDropzone(qs("#asset-dz", body), { kind: "brand_asset", hint: "Logo files, font files, PDF guidelines…" });
    const typeSel = qs("[name=type]", body);
    const colorIn = qs("[name=color]", body);
    const valIn = qs("[name=value]", body);
    const syncValue = () => {
      colorIn.style.display = typeSel.value === "color" ? "" : "none";
      valIn.placeholder = typeSel.value === "color" ? "#RRGGBB" : typeSel.value === "font" ? "Font family name" : "Optional note";
    };
    typeSel.addEventListener("change", syncValue);
    colorIn.addEventListener("input", () => (valIn.value = colorIn.value));
    syncValue();
    qs("[data-cancel]", footer).onclick = () => m.close();
    qs("[data-save]", footer).onclick = async () => {
      const err = qs("#asset-error", body);
      err.classList.add("hidden");
      const name = qs("[name=name]", body).value.trim();
      if (!name) {
        err.textContent = "Please give the asset a name.";
        err.classList.remove("hidden");
        return;
      }
      if (dz.busy()) {
        err.textContent = "Please wait for the upload to finish.";
        err.classList.remove("hidden");
        return;
      }
      const btn = qs("[data-save]", footer);
      setLoading(btn, true);
      try {
        const ids = dz.ids();
        await api.post("/brand-assets", { type: typeSel.value, name, value: valIn.value.trim() || null, file_id: ids.length ? ids[ids.length - 1] : null });
        toast({ title: "Brand asset added", type: "success" });
        m.close();
        loadAssets();
        loadFiles();
      } catch (ex) {
        err.textContent = errorMessage(ex);
        err.classList.remove("hidden");
        setLoading(btn, false);
      }
    };
  });

  await Promise.all([loadAssets(), loadFiles()]);
}
