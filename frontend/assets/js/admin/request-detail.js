/* Request detail: brief, timeline, designs, deliveries, files, revisions, agent logs */
import { api, errorMessage, downloadFile, fileUrl } from "../core/api.js";
import { esc, icon, qs, qsa, h, nl2br, fmtDateTime, fmtDate, timeAgo, statusBadge, priorityBadge, toast, modal, confirmDialog, setLoading, titleCase } from "../core/ui.js";
import {
  pageHeader, actionButtons, bindActions, briefHtml, fileRow, uploadFiles, logLine, loadingBlock, errorBlock, statusOptions, hoursLabel, emptyState, priceBadge, money,
} from "./shared.js";

const TABS = [
  ["brief", "Brief"],
  ["timeline", "Timeline"],
  ["designs", "Designs"],
  ["deliveries", "Deliveries"],
  ["files", "Files"],
  ["revisions", "Revisions"],
  ["logs", "Agent logs"],
];

export async function render(page, params) {
  const id = Number(params.id);
  let req = null;
  let service = null;
  let logs = [];
  let activeTab = "brief";
  page.innerHTML = loadingBlock(4);

  async function load() {
    // One round trip for everything: the request, its service and the agent logs load in parallel.
    const [r, l] = await Promise.all([api.get(`/requests/${id}`), api.get("/agents/logs", { request_id: id, limit: 200 }).catch(() => [])]);
    req = r;
    logs = l;
    try {
      service = await api.get(`/services/${req.service_slug}`);
    } catch {
      service = null;
    }
  }

  function draw() {
    const r = req;
    page.innerHTML = `
      <div class="detail-head" data-title="${esc(r.title)}">
        <div class="min-w-0">
          <div class="breadcrumb mb-2"><a href="#/requests">Requests</a><span>/</span><span>#${r.id}</span></div>
          <h1>${esc(r.title)}</h1>
          <div class="flex gap-2 mt-3 wrap">${statusBadge(r.status)}${priorityBadge(r.priority)}${priceBadge(r)}${r.pipeline_stage ? `<span class="badge badge-cyan">${icon("cpu", "icon-sm")} ${esc(titleCase(r.pipeline_stage))}</span>` : ""}${r.revision_count ? `<span class="badge">${icon("repeat", "icon-sm")} ${r.revision_count} revision${r.revision_count > 1 ? "s" : ""}</span>` : ""}</div>
          <div class="detail-meta">
            <span>${icon("users", "icon-sm")} <a href="#/clients/${r.client_id}">${esc(r.company_name)}</a> (${esc(r.client_name)})</span>
            <span>${icon("layers", "icon-sm")} <a href="#/services/${esc(r.service_slug)}">${esc(r.service_name)}</a></span>
            ${r.project_name ? `<span>${icon("folder", "icon-sm")} ${esc(r.project_name)}</span>` : ""}
            <span>${icon("clock", "icon-sm")} Submitted ${fmtDateTime(r.submitted_at)}</span>
            ${r.due_at ? `<span>${icon("calendar", "icon-sm")} Due ${fmtDate(r.due_at)}</span>` : ""}
            ${r.completed_at ? `<span>${icon("check-circle", "icon-sm")} Completed ${fmtDateTime(r.completed_at)}</span>` : ""}
          </div>
        </div>
        <div class="action-bar" id="actions"><a class="btn btn-live" href="/admin/live/${r.id}" target="_blank" rel="noopener" title="Watch the agents work on this request in real time, in a new tab"><span class="live-dot"></span> See in live</a>${actionButtons(r, { size: "" })}
          <button class="btn" id="btn-pipeline">${icon("cpu")} Run pipeline</button>
          <button class="btn btn-ghost" id="btn-status">${icon("edit")} Set status</button>
        </div>
      </div>
      ${r.rejection_reason ? `<div class="card mb-6" style="border-color:var(--danger)"><div class="card-body text-sm"><b>Rejection reason:</b> ${esc(r.rejection_reason)}</div></div>` : ""}
      ${r.ai_summary ? `<div class="card mb-6"><div class="card-body text-sm"><div class="text-xs text-3 uppercase mb-2">${icon("sparkles", "icon-sm")} Project Manager summary</div>${nl2br(r.ai_summary)}</div></div>` : ""}
      <div class="detail-grid">
        <div class="card">
          <div class="tabs" style="padding:0 var(--s-4)">${TABS.map(([k, l]) => `<button class="tab ${k === activeTab ? "active" : ""}" data-tab="${k}">${l}${k === "designs" && r.designs.length ? ` <span class="count-badge">${r.designs.length}</span>` : ""}${k === "deliveries" && r.deliveries.length ? ` <span class="count-badge">${r.deliveries.length}</span>` : ""}${k === "files" && r.files.length ? ` <span class="count-badge">${r.files.length}</span>` : ""}${k === "revisions" && r.revisions.length ? ` <span class="count-badge">${r.revisions.length}</span>` : ""}</button>`).join("")}</div>
          <div class="card-body" id="tab-body"></div>
        </div>
        <div class="flex flex-col gap-4">
          <div class="card"><div class="card-header"><h3>Status</h3></div><div class="card-body">
            <dl class="kv" style="grid-template-columns:110px 1fr">
              <dt>Price</dt><dd>${r.price_amount !== null && r.price_amount !== undefined ? `<b>${money(r.price_amount, r.price_currency)}</b> ${r.is_paid ? `<span class="badge badge-success">paid${r.paid_at ? " " + fmtDate(r.paid_at) : ""}</span>` : `<span class="badge badge-warning">unpaid</span>`}` : "—"}</dd>
              <dt>Delivery</dt><dd>${r.turnaround_days ? `${r.turnaround_days} day${r.turnaround_days === 1 ? "" : "s"}` : "—"}</dd>
              <dt>Submitted</dt><dd>${fmtDateTime(r.submitted_at)}</dd>
              <dt>Accepted</dt><dd>${r.accepted_at ? fmtDateTime(r.accepted_at) : "—"}</dd>
              <dt>Started</dt><dd>${r.started_at ? fmtDateTime(r.started_at) : "—"}</dd>
              <dt>In review</dt><dd>${r.review_at ? fmtDateTime(r.review_at) : "—"}</dd>
              <dt>Completed</dt><dd>${r.completed_at ? fmtDateTime(r.completed_at) : "—"}</dd>
              <dt>Turnaround</dt><dd>${r.completed_at && r.accepted_at ? hoursLabel((new Date(r.completed_at) - new Date(r.accepted_at)) / 36e5) : "—"}</dd>
            </dl></div></div>
          <div class="card"><div class="card-header"><h3>Client</h3></div><div class="card-body text-sm">
            <div class="flex items-center gap-3"><span class="avatar">${esc((r.company_name || "?").slice(0, 2).toUpperCase())}</span><div><a href="#/clients/${r.client_id}"><b>${esc(r.company_name)}</b></a><div class="text-3 text-xs">${esc(r.client_name)}</div></div></div>
            <div class="flex gap-2 mt-4"><a href="#/chat?client_id=${r.client_id}" class="btn btn-secondary btn-sm">${icon("message", "icon-sm")} Chat</a><a href="#/clients/${r.client_id}" class="btn btn-ghost btn-sm">Profile</a></div>
          </div></div>
          ${service ? `<div class="card"><div class="card-header"><h3>Service</h3></div><div class="card-body text-sm"><div class="flex items-center gap-3"><span class="avatar avatar-neutral">${icon("svc-" + service.icon, "icon-sm")}</span><div><a href="#/services/${esc(service.slug)}"><b>${esc(service.name)}</b></a><div class="text-3 text-xs">${service.turnaround_days}-day delivery · ${money((service.prices || {}).USD || service.starting_price || 0)} ${esc(service.price_unit || "")} · ${service.pending_count} pending</div></div></div></div></div>` : ""}
        </div>
      </div>`;

    qsa("[data-tab]", page).forEach((b) =>
      b.addEventListener("click", () => {
        activeTab = b.dataset.tab;
        qsa("[data-tab]", page).forEach((x) => x.classList.toggle("active", x === b));
        drawTab();
      })
    );
    drawTab();

    bindActions(qs("#actions", page), { onDone: refresh });
    qs("#btn-pipeline", page).onclick = async () => {
      const ok = await confirmDialog({ title: "Run the agent pipeline?", body: req.status === "pending" ? "The request will be accepted and queued for the agents." : "The pipeline will re-run from the Project Manager step.", confirmText: "Run" });
      if (!ok) return;
      try {
        await api.post(`/requests/${id}/run-pipeline`);
        toast({ title: "Pipeline queued", type: "success" });
        refresh();
      } catch (err) {
        toast({ title: "Failed", body: errorMessage(err), type: "error" });
      }
    };
    qs("#btn-status", page).onclick = () => {
      const body = h(`<div><div class="field"><label class="label">Status</label><select class="select" id="st">${statusOptions(req.status)}</select></div><div class="field"><label class="label">Note (optional)</label><textarea class="textarea" id="st-note" placeholder="Visible in the audit log"></textarea></div></div>`);
      const footer = h(`<div class="flex gap-2 justify-end w-full"><button class="btn btn-secondary" data-close>Cancel</button><button class="btn btn-primary" id="st-save">Save</button></div>`);
      const m = modal({ title: "Set status", body, footer });
      qs("#st-save", footer).onclick = async () => {
        setLoading(qs("#st-save", footer), true);
        try {
          await api.post(`/requests/${id}/status`, { status: qs("#st", body).value, note: qs("#st-note", body).value || null });
          m.close();
          toast({ title: "Status updated", type: "success" });
          refresh();
        } catch (err) {
          toast({ title: "Failed", body: errorMessage(err), type: "error" });
          setLoading(qs("#st-save", footer), false);
        }
      };
    };
  }

  function drawTab() {
    const body = qs("#tab-body", page);
    const r = req;
    if (activeTab === "brief") {
      body.innerHTML = briefHtml(r.brief, service ? service.form_schema : [], r.description);
    } else if (activeTab === "timeline") {
      body.innerHTML = r.timeline.length
        ? `<div class="timeline">${r.timeline.map((e) => `<div class="timeline-item ${esc(e.kind)}"><div class="timeline-title">${esc(e.title)}</div><div class="timeline-meta">${fmtDateTime(e.at)}</div>${e.body ? `<div class="timeline-body">${esc(e.body)}</div>` : ""}</div>`).join("")}</div>`
        : emptyState("clock", "No events yet");
    } else if (activeTab === "designs") {
      body.innerHTML = `<div class="flex justify-end mb-4"><button class="btn btn-primary btn-sm" id="add-design">${icon("plus", "icon-sm")} Add design</button></div>` +
        (r.designs.length
          ? r.designs.slice().reverse().map((d) => `<div class="design-card">
              <div class="flex items-center justify-between gap-2 wrap"><div><b>v${d.version} · ${esc(d.title || "Concept")}</b> <span class="badge ${d.status === "approved" ? "badge-success" : d.status === "rejected" ? "badge-danger" : ""}">${esc(titleCase(d.status))}</span> <span class="badge">${d.generated_by === "agent" ? icon("cpu", "icon-sm") + " Agent" : icon("user", "icon-sm") + " Human"}</span></div>
                <div class="flex items-center gap-2">${d.qa_score !== null && d.qa_score !== undefined ? `<span class="badge ${d.qa_score >= 85 ? "badge-success" : d.qa_score >= 70 ? "badge-warning" : "badge-danger"}">QA ${d.qa_score}/100</span>` : ""}${d.status !== "approved" ? `<button class="btn btn-success-soft btn-sm" data-approve-design="${d.id}">${icon("check", "icon-sm")} Approve</button>` : ""}${d.file_id ? `<button class="btn btn-secondary btn-sm" data-download="${d.file_id}" data-name="design-v${d.version}">${icon("download", "icon-sm")}</button>` : ""}</div></div>
              ${d.concept ? `<div class="concept">${nl2br(d.concept)}</div>` : ""}
              ${d.qa_notes ? `<div class="text-xs text-3 mt-2"><b>QA notes:</b> ${esc(d.qa_notes)}</div>` : ""}
              ${d.file_id ? `<img src="${fileUrl(d.file_id)}" alt="Draft v${d.version}">` : d.preview_url ? `<img src="${esc(d.preview_url)}" alt="">` : ""}
              <div class="text-xs text-4 mt-2">${fmtDateTime(d.created_at)}</div>
            </div>`).join("")
          : emptyState("palette", "No designs yet", "Run the pipeline or add a design manually."));
      qs("#add-design", body).onclick = openAddDesign;
      qsa("[data-approve-design]", body).forEach((b) =>
        b.addEventListener("click", async () => {
          setLoading(b, true);
          try {
            await api.post(`/requests/${id}/designs/${b.dataset.approveDesign}/approve`);
            toast({ title: "Design approved", type: "success" });
            refresh();
          } catch (err) {
            toast({ title: "Failed", body: errorMessage(err), type: "error" });
            setLoading(b, false);
          }
        })
      );
    } else if (activeTab === "deliveries") {
      body.innerHTML = `<div class="flex justify-end mb-4"><button class="btn btn-primary btn-sm" id="add-delivery">${icon("send", "icon-sm")} Create delivery</button></div>` +
        (r.deliveries.length
          ? r.deliveries.slice().reverse().map((d) => `<div class="design-card">
              <div class="flex items-center justify-between gap-2 wrap"><b>Delivery v${d.version}</b><span class="text-xs text-3">${fmtDateTime(d.delivered_at)} · by ${esc(d.delivered_by)}</span></div>
              ${d.message ? `<div class="concept">${nl2br(d.message)}</div>` : ""}
              <div class="flex gap-2 wrap mt-3">${(d.download_links || []).map((l) => `<button class="btn btn-secondary btn-sm" data-download="${l.file_id || ""}" data-url="${esc(l.url || "")}" data-name="${esc(l.name || "file")}">${icon("download", "icon-sm")} ${esc(l.name || "Download")}</button>`).join("") || '<span class="text-xs text-4">No files attached</span>'}</div>
            </div>`).join("")
          : emptyState("send", "Nothing delivered yet"));
      qs("#add-delivery", body).onclick = openAddDelivery;
    } else if (activeTab === "files") {
      body.innerHTML = `<div class="flex justify-between items-center mb-4 wrap gap-2"><span class="text-sm text-3">${r.files.length} file${r.files.length === 1 ? "" : "s"}</span><label class="btn btn-secondary btn-sm">${icon("upload", "icon-sm")} Upload <input type="file" multiple class="hidden" id="upload-files"></label></div>` +
        (r.files.length ? `<div class="list">${r.files.map(fileRow).join("")}</div>` : emptyState("folder", "No files", "Client uploads and deliverables appear here."));
      qs("#upload-files", body).addEventListener("change", async (e) => {
        if (!e.target.files.length) return;
        try {
          await uploadFiles(e.target.files, { request_id: id, kind: "upload" });
          toast({ title: "Uploaded", type: "success" });
          refresh();
        } catch (err) {
          toast({ title: "Upload failed", body: errorMessage(err), type: "error" });
        }
      });
    } else if (activeTab === "revisions") {
      body.innerHTML = r.revisions.length
        ? r.revisions.slice().reverse().map((rv) => `<div class="design-card">
            <div class="flex items-center justify-between gap-2 wrap"><b>Round ${rv.round}</b><div class="flex items-center gap-2"><span class="badge ${rv.status === "completed" ? "badge-success" : rv.status === "in_progress" ? "badge-purple" : "badge-warning"}">${esc(titleCase(rv.status))}</span>${rv.status !== "completed" ? `<button class="btn btn-success-soft btn-sm" data-resolve="${rv.id}">${icon("check", "icon-sm")} Mark completed</button>` : ""}</div></div>
            <div class="concept">${nl2br(rv.feedback)}</div>
            ${rv.change_items && rv.change_items.length ? `<ul class="mt-3" style="list-style:disc;padding-left:20px;font-size:var(--fs-sm)">${rv.change_items.map((c) => `<li>${esc(typeof c === "string" ? c : JSON.stringify(c))}</li>`).join("")}</ul>` : ""}
            <div class="text-xs text-4 mt-2">${fmtDateTime(rv.created_at)}${rv.resolved_at ? ` · resolved ${fmtDateTime(rv.resolved_at)}` : ""}</div>
          </div>`).join("")
        : emptyState("repeat", "No revisions requested");
      qsa("[data-resolve]", body).forEach((b) =>
        b.addEventListener("click", async () => {
          setLoading(b, true);
          try {
            await api.patch(`/requests/${id}/revisions/${b.dataset.resolve}`, null, { status: "completed" });
            toast({ title: "Revision resolved", type: "success" });
            refresh();
          } catch (err) {
            toast({ title: "Failed", body: errorMessage(err), type: "error" });
            setLoading(b, false);
          }
        })
      );
    } else if (activeTab === "logs") {
      body.innerHTML = `<div class="log-stream" id="log-stream">${logs.length ? logs.slice().reverse().map((l) => logLine(l)).join("") : emptyState("cpu", "No agent activity yet", "Logs appear live while the pipeline runs.")}</div>`;
    }
  }

  function openAddDesign() {
    const body = h(`<div>
      <div class="field"><label class="label">Title</label><input class="input" id="d-title" placeholder="Concept A"></div>
      <div class="field"><label class="label">Concept / notes</label><textarea class="textarea" id="d-concept" placeholder="Layout, palette, typography, rationale…"></textarea></div>
      <div class="field"><label class="label">Preview / source file (optional)</label><input type="file" class="input" id="d-file"></div>
    </div>`);
    const footer = h(`<div class="flex gap-2 justify-end w-full"><button class="btn btn-secondary" data-close>Cancel</button><button class="btn btn-primary" id="d-save">Add design</button></div>`);
    const m = modal({ title: "Add design", body, footer });
    qs("#d-save", footer).onclick = async () => {
      const btn = qs("#d-save", footer);
      setLoading(btn, true);
      try {
        let file_id = null;
        let preview_url = null;
        const f = qs("#d-file", body).files[0];
        if (f) {
          const [up] = await uploadFiles([f], { request_id: id, kind: "design" });
          file_id = up.id;
          if ((up.mime_type || "").startsWith("image/")) preview_url = up.download_url;
        }
        await api.post(`/requests/${id}/designs`, { title: qs("#d-title", body).value || null, concept: qs("#d-concept", body).value || null, file_id, preview_url, concept_data: {} });
        m.close();
        toast({ title: "Design added", type: "success" });
        activeTab = "designs";
        refresh();
      } catch (err) {
        toast({ title: "Failed", body: errorMessage(err), type: "error" });
        setLoading(btn, false);
      }
    };
  }

  function openAddDelivery() {
    const body = h(`<div>
      <div class="field"><label class="label">Message to client</label><textarea class="textarea" id="dl-msg" placeholder="Final files attached. Let us know if you'd like any changes."></textarea></div>
      <div class="field"><label class="label">Files</label><input type="file" multiple class="input" id="dl-files"><span class="hint">Attach the final deliverables. They are shared with the client as download links.</span></div>
      <label class="checkbox mt-4"><input type="checkbox" id="dl-complete" checked> Mark the request as completed</label>
      <div class="text-xs text-3 mt-3" id="dl-progress"></div>
    </div>`);
    const footer = h(`<div class="flex gap-2 justify-end w-full"><button class="btn btn-secondary" data-close>Cancel</button><button class="btn btn-primary" id="dl-save">${icon("send", "icon-sm")} Deliver</button></div>`);
    const m = modal({ title: "Create delivery", body, footer });
    qs("#dl-save", footer).onclick = async () => {
      const btn = qs("#dl-save", footer);
      setLoading(btn, true);
      try {
        const files = qs("#dl-files", body).files;
        const uploaded = await uploadFiles(files, { request_id: id, kind: "delivery" }, (i, n, name) => (qs("#dl-progress", body).textContent = `Uploading ${i}/${n}: ${name}`));
        await api.post(`/requests/${id}/deliveries`, { message: qs("#dl-msg", body).value || null, file_ids: uploaded.map((f) => f.id), mark_completed: qs("#dl-complete", body).checked });
        m.close();
        toast({ title: "Delivered", body: "The client has been notified.", type: "success" });
        activeTab = "deliveries";
        refresh();
      } catch (err) {
        toast({ title: "Failed", body: errorMessage(err), type: "error" });
        setLoading(btn, false);
      }
    };
  }

  async function refresh() {
    try {
      await load();
      draw();
    } catch (err) {
      page.innerHTML = errorBlock(err);
    }
  }

  page.addEventListener("click", async (e) => {
    const b = e.target.closest("[data-download]");
    if (!b) return;
    const fid = b.dataset.download;
    if (fid) {
      try {
        await downloadFile(fid, b.dataset.name || "file");
      } catch (err) {
        toast({ title: "Download failed", body: errorMessage(err), type: "error" });
      }
    } else if (b.dataset.url) window.open(b.dataset.url, "_blank");
  });

  const onUpdate = (e) => {
    if (e.detail && Number(e.detail.request_id) === id) refresh();
  };
  const onLog = (e) => {
    const l = e.detail;
    if (!l || Number(l.request_id) !== id) return;
    logs.push(l);
    const stream = qs("#log-stream", page);
    if (stream) {
      if (qs(".empty", stream)) stream.innerHTML = "";
      stream.insertAdjacentHTML("afterbegin", logLine(l, true));
    }
  };
  document.addEventListener("df:request_update", onUpdate);
  document.addEventListener("df:agent_log", onLog);

  await refresh();
  return () => {
    document.removeEventListener("df:request_update", onUpdate);
    document.removeEventListener("df:agent_log", onLog);
  };
}
