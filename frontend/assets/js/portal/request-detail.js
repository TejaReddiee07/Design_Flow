/* Request detail: overview, timeline, designs, deliveries, files, revisions */
import { api, errorMessage, downloadFile, fileUrl } from "../core/api.js";
import { icon, esc, nl2br, qs, qsa, toast, confirmDialog, setLoading, fmtDate, fmtDateTime, timeAgo, fmtBytes, statusBadge, priorityBadge, titleCase, skeletonRows, emptyState } from "../core/ui.js";
import { serviceBySlug, serviceIcon, pageHeader, createDropzone, briefTable, stageTrack, fileIconName, kindBadge, errorBox, reportError, fmtPrice, paidBadge, payRequest } from "./shared.js";

const TABS = [["overview", "Overview"], ["timeline", "Timeline"], ["designs", "Designs"], ["deliveries", "Deliveries"], ["files", "Files"], ["revisions", "Revisions"]];

export async function renderRequestDetail(page, params, query) {
  const id = Number(params.id);
  let tab = query.tab || "overview";
  let detail = null;
  let service = null;
  page.innerHTML = `<div class="skeleton" style="height:90px"></div><div class="mt-6">${skeletonRows(4)}</div>`;

  async function load() {
    detail = await api.get(`/requests/${id}`);
    try {
      service = await serviceBySlug(detail.service_slug);
    } catch {
      service = null;
    }
  }

  try {
    await load();
  } catch (err) {
    page.innerHTML = `<p class="mb-4"><a class="btn btn-ghost btn-sm" href="#/requests">${icon("arrow-left", "icon-sm")} Back to requests</a></p>${err.status === 404 ? emptyState("help", "Request not found", "It may have been withdrawn.") : errorBox(err)}`;
    return;
  }

  if (query.payment === "success") {
    if (query.session_id && !detail.is_paid) {
      // Back from Stripe Checkout: confirm the session with the server (no webhook needed on localhost)
      try {
        const res = await api.post(`/requests/${id}/confirm-payment`, null, { session_id: query.session_id });
        if (res.paid) {
          detail = { ...detail, ...res.request };
          toast({ title: "Payment received", body: "Thank you! Your request is in the queue.", type: "success" });
        } else toast({ title: "Payment not confirmed yet", body: "Stripe hasn't confirmed this payment. Refresh in a moment or pay again.", type: "warning", timeout: 8000 });
      } catch (err) {
        toast({ title: "Could not confirm payment", body: errorMessage(err), type: "error", timeout: 8000 });
      }
    } else toast({ title: "Payment received", body: "Thank you! Your request is in the queue.", type: "success" });
  } else if (query.payment === "cancel") toast({ title: "Payment cancelled", body: "You can pay any time from this page.", type: "warning" });

  function draw() {
    const r = detail;
    const canRevise = ["completed", "review", "in_progress"].includes(r.status);
    const unpaid = r.price_amount && !r.is_paid && r.status !== "rejected";
    const dateRow = [
      `<span>${icon("calendar", "icon-sm")} Submitted ${fmtDateTime(r.submitted_at || r.created_at)}</span>`,
      r.price_amount ? `<span class="req-price">${fmtPrice(r.price_amount, r.price_currency)}</span>` : "",
      r.paid_at ? `<span>${icon("credit-card", "icon-sm")} Paid ${fmtDate(r.paid_at)}</span>` : "",
      r.turnaround_days ? `<span>${icon("zap", "icon-sm")} ${r.turnaround_days}-day delivery</span>` : "",
      r.accepted_at ? `<span>${icon("check", "icon-sm")} Accepted ${fmtDate(r.accepted_at)}</span>` : "",
      r.due_at && !["completed", "rejected"].includes(r.status) ? `<span>${icon("clock", "icon-sm")} Due ${fmtDate(r.due_at)}</span>` : "",
      r.completed_at ? `<span>${icon("check-circle", "icon-sm")} Completed ${fmtDate(r.completed_at)}</span>` : "",
      r.project_name ? `<span>${icon("layers", "icon-sm")} ${esc(r.project_name)}</span>` : "",
    ].filter(Boolean).join("");

    page.innerHTML = `
      <p class="mb-4"><a class="btn btn-ghost btn-sm" href="#/requests">${icon("arrow-left", "icon-sm")} All requests</a></p>
      <div class="detail-head">
        <div class="flex gap-4 items-start min-w-0">
          <span class="service-icon">${serviceIcon(service ? service.icon : "custom")}</span>
          <div class="min-w-0">
            <div class="flex gap-2 items-center wrap"><span class="text-3 text-sm">#${r.id} · ${esc(r.service_name)}</span>${statusBadge(r.status)}${paidBadge(r)}${priorityBadge(r.priority)}</div>
            <h1 class="mt-2">${esc(r.title)}</h1>
            <div class="detail-meta">${dateRow}</div>
            ${stageTrack(r)}
            ${r.pipeline_stage && !["complete", null].includes(r.pipeline_stage) && r.status !== "completed" ? `<p class="text-xs text-3 mt-2">${icon("cpu", "icon-sm")} Pipeline stage: ${esc(titleCase(r.pipeline_stage))}</p>` : ""}
          </div>
        </div>
        <div class="flex gap-2 wrap">
          ${unpaid ? `<button class="btn btn-gradient" id="btn-pay">${icon("credit-card")} Pay now ${fmtPrice(r.price_amount, r.price_currency)}</button>` : ""}
          ${canRevise ? `<button class="btn btn-secondary" id="btn-revise">${icon("repeat")} Request revision</button>` : ""}
          <a class="btn btn-secondary" href="#/chat">${icon("message")} Message</a>
          ${r.status === "pending" ? `<button class="btn btn-danger-soft" id="btn-withdraw">${icon("trash")} Withdraw</button>` : ""}
        </div>
      </div>
      ${unpaid ? `<div class="inline-alert warning mt-4">${icon("credit-card")}<span><b>Payment of ${fmtPrice(r.price_amount, r.price_currency)} is due.</b> Work starts and the ${r.turnaround_days}-day delivery clock begins once it's received.</span></div>` : ""}
      ${r.status === "rejected" ? `<div class="inline-alert danger mt-4">${icon("alert")}<span><b>This request was declined.</b> ${esc(r.rejection_reason || "Contact us if you'd like to discuss it.")}</span></div>` : ""}
      ${r.status === "review" ? `<div class="inline-alert mt-4">${icon("eye")}<span>A draft passed QA and is with your designer for final approval. You'll be notified when it's delivered.</span></div>` : ""}
      <div class="tabs mt-6" id="tabs">${TABS.map(([k, l]) => `<button class="tab ${k === tab ? "active" : ""}" data-tab="${k}">${l}${counter(k)}</button>`).join("")}</div>
      <div class="mt-6" id="tab-body"></div>`;

    qs("#tabs", page).addEventListener("click", (e) => {
      const b = e.target.closest("[data-tab]");
      if (!b) return;
      tab = b.dataset.tab;
      qsa(".tab", page).forEach((t) => t.classList.toggle("active", t === b));
      drawTab();
    });
    const w = qs("#btn-withdraw", page);
    if (w) w.addEventListener("click", withdraw);
    const pay = qs("#btn-pay", page);
    if (pay) pay.addEventListener("click", async () => {
      const res = await payRequest(id, pay);
      if (res) {
        await load();
        draw();
      }
    });
    const rv = qs("#btn-revise", page);
    if (rv) rv.addEventListener("click", () => {
      tab = "revisions";
      qsa(".tab", page).forEach((t) => t.classList.toggle("active", t.dataset.tab === "revisions"));
      drawTab();
      setTimeout(() => qs("#revision-form textarea", page)?.focus(), 50);
    });
    drawTab();
  }

  function counter(k) {
    const n = { designs: detail.designs.length, deliveries: detail.deliveries.length, files: detail.files.length, revisions: detail.revisions.length }[k];
    return n ? ` <span class="count-badge is-zero" style="margin-left:4px">${n}</span>` : "";
  }

  function drawTab() {
    const body = qs("#tab-body", page);
    const r = detail;
    if (tab === "overview") {
      body.innerHTML = `<div class="detail-grid">
        <div class="card"><div class="card-header"><h3>Brief</h3></div><div class="card-body">
          ${r.description ? `<p class="text-2 mb-6" style="white-space:pre-wrap">${esc(r.description)}</p>` : ""}
          ${briefTable(r.brief, service ? service.form_schema : [])}
        </div></div>
        <div class="flex flex-col gap-4">
          ${r.ai_summary ? `<div class="card"><div class="card-header"><h3>${icon("sparkles", "icon-sm")} Project Manager summary</h3></div><div class="card-body text-sm text-2" style="white-space:pre-wrap">${esc(r.ai_summary)}</div></div>` : ""}
          <div class="card"><div class="card-header"><h3>Details</h3></div><div class="card-body"><dl class="kv" style="grid-template-columns:120px 1fr">
            <dt>Status</dt><dd>${statusBadge(r.status)}</dd><dt>Priority</dt><dd>${priorityBadge(r.priority)}</dd>
            <dt>Service</dt><dd>${esc(r.service_name)}</dd><dt>Project</dt><dd>${esc(r.project_name || "—")}</dd>
            <dt>Price</dt><dd>${r.price_amount ? `${fmtPrice(r.price_amount, r.price_currency)} ${paidBadge(r)}` : "—"}</dd>
            <dt>Revisions</dt><dd>${r.revision_count}</dd><dt>Delivery</dt><dd>${r.turnaround_days ? `${r.turnaround_days} day${r.turnaround_days === 1 ? "" : "s"}` : "—"}</dd>
          </dl></div></div>
          ${service ? `<div class="card"><div class="card-header"><h3>Deliverables</h3></div><div class="card-body"><ul class="flex flex-col gap-2 text-sm text-2">${service.deliverables.map((d) => `<li class="flex gap-2">${icon("check-circle", "icon-sm")}<span>${esc(d)}</span></li>`).join("")}</ul></div></div>` : ""}
        </div>
      </div>`;
    } else if (tab === "timeline") {
      const items = r.timeline || [];
      body.innerHTML = `<div class="card"><div class="card-body">${
        items.length
          ? `<div class="timeline">${items.map((e) => `<div class="timeline-item ${esc(e.kind)}"><div class="timeline-title">${esc(e.title)}</div><div class="timeline-meta">${fmtDateTime(e.at)} · ${timeAgo(e.at)}</div>${e.body ? `<div class="timeline-body">${esc(e.body)}</div>` : ""}</div>`).join("")}</div>`
          : emptyState("activity", "No activity yet")
      }</div></div>`;
    } else if (tab === "designs") {
      body.innerHTML = r.designs.length
        ? `<div class="grid grid-2">${r.designs.map((d) => `<div class="design-card">
            ${d.file_id ? `<img src="${fileUrl(d.file_id)}" alt="${esc(d.title || "Design preview")}" loading="lazy">` : d.preview_url ? `<img src="${esc(d.preview_url)}" alt="${esc(d.title || "Design preview")}" loading="lazy">` : ""}
            <div class="body">
              <div class="flex items-center justify-between gap-2 wrap"><b>${esc(d.title || `Design v${d.version}`)}</b><span class="flex gap-2">${d.qa_score != null ? `<span class="badge ${d.qa_score >= 85 ? "badge-success" : "badge-warning"}">QA ${Math.round(d.qa_score)}/100</span>` : ""}<span class="badge ${d.status === "approved" ? "badge-success" : ""}">${esc(titleCase(d.status))}</span></span></div>
              <div class="text-xs text-3 mt-1">v${d.version} · ${d.generated_by === "agent" ? "AI concept" : "Designer"} · ${fmtDate(d.created_at)}</div>
              ${d.concept ? `<div class="concept">${esc(d.concept)}</div>` : ""}
              ${d.qa_notes ? `<div class="text-xs text-3 mt-3">${icon("shield", "icon-sm")} ${esc(d.qa_notes)}</div>` : ""}
              ${d.file_id ? `<button class="btn btn-secondary btn-sm mt-3" data-dl="${d.file_id}" data-name="${esc(d.title || "design")}">${icon("download", "icon-sm")} Download file</button>` : ""}
            </div></div>`).join("")}</div>`
        : emptyState("palette", "No designs yet", "Concepts will appear here once the Design Agent and your designer have drafts.");
    } else if (tab === "deliveries") {
      body.innerHTML = r.deliveries.length
        ? `<div class="inline-alert yd-callout">${icon("image")}<span>All your delivered files are also kept in <b>Your designs</b>, with previews and one-click ZIP downloads.</span><a class="btn btn-secondary btn-sm" href="#/designs">${icon("image", "icon-sm")} View in Your designs</a></div><div class="flex flex-col gap-4">${[...r.deliveries].reverse().map((d) => `<div class="delivery-card">
            <div class="flex items-center justify-between gap-2 wrap"><b>Delivery v${d.version}</b><span class="text-xs text-3">${fmtDateTime(d.delivered_at)} · by ${d.delivered_by === "agent" ? "Delivery Agent" : "your designer"}</span></div>
            ${d.message ? `<p class="text-sm text-2 mt-2" style="white-space:pre-wrap">${esc(d.message)}</p>` : ""}
            ${d.download_links && d.download_links.length ? `<div class="delivery-links">${d.download_links.map((l) => linkButton(l)).join("")}</div>` : `<p class="text-xs text-3 mt-2">No files attached to this delivery.</p>`}
          </div>`).join("")}</div>`
        : emptyState("download", "Nothing delivered yet", "Final files will appear here, and in your Drive folder.");
    } else if (tab === "files") {
      body.innerHTML = `<div class="detail-grid">
        <div class="card"><div class="card-header"><h3>Files on this request</h3></div><div class="card-body" id="file-list">${filesTable(r.files)}</div></div>
        <div class="card"><div class="card-header"><h3>Add files</h3></div><div class="card-body"><div id="req-dz"></div></div></div>
      </div>`;
      createDropzone(qs("#req-dz", body), { request_id: id, kind: "upload", onChange: async () => {
        try {
          await load();
          qs("#file-list", body).innerHTML = filesTable(detail.files);
          qsa(".tab", page).forEach((t) => (t.innerHTML = TABS.find(([k]) => k === t.dataset.tab)[1] + counter(t.dataset.tab)));
        } catch {}
      } });
    } else if (tab === "revisions") {
      const canRevise = ["completed", "review", "in_progress"].includes(r.status);
      body.innerHTML = `<div class="detail-grid">
        <div>${r.revisions.length
          ? [...r.revisions].reverse().map((rv) => `<div class="revision-item">
              <div class="flex items-center justify-between gap-2 wrap"><b>Round ${rv.round}</b><span class="badge ${rv.status === "completed" ? "badge-success" : rv.status === "in_progress" ? "badge-purple" : "badge-warning"}">${esc(titleCase(rv.status))}</span></div>
              <div class="text-xs text-3 mt-1">${fmtDateTime(rv.created_at)}${rv.resolved_at ? ` · resolved ${fmtDate(rv.resolved_at)}` : ""}</div>
              <p class="text-sm text-2 mt-2" style="white-space:pre-wrap">${esc(rv.feedback)}</p>
              ${rv.change_items && rv.change_items.length ? `<ul>${rv.change_items.map((c) => `<li>${esc(typeof c === "string" ? c : c.item || JSON.stringify(c))}</li>`).join("")}</ul>` : ""}
            </div>`).join("")
          : emptyState("repeat", "No revisions requested", canRevise ? "Use the form to ask for changes." : "You can request revisions once a draft has been delivered.")}</div>
        ${canRevise ? `<form class="card" id="revision-form"><div class="card-header"><h3>Request a revision</h3></div><div class="card-body">
          <div class="field"><label class="label">What should change? <span class="req">*</span></label><textarea class="textarea" name="feedback" placeholder="Be specific: 'make the headline bigger', 'use the teal from our logo', 'swap photo for product shot'…"></textarea></div>
          <div class="field mt-4"><label class="label">Attach marked-up files <span class="text-4">(optional)</span></label><div id="rev-dz"></div></div>
          <p class="error-text mt-3 hidden" id="rev-error"></p>
        </div><div class="card-footer flex justify-end"><button class="btn btn-primary" type="submit">${icon("repeat")} Submit revision</button></div></form>` : ""}
      </div>`;
      const form = qs("#revision-form", body);
      if (form) {
        const dz = createDropzone(qs("#rev-dz", form), { request_id: id, kind: "revision" });
        form.addEventListener("submit", async (e) => {
          e.preventDefault();
          const err = qs("#rev-error", form);
          err.classList.add("hidden");
          const feedback = qs("textarea", form).value.trim();
          if (feedback.length < 3) {
            err.textContent = "Please describe the changes you need.";
            err.classList.remove("hidden");
            return;
          }
          const btn = qs("button[type=submit]", form);
          setLoading(btn, true);
          try {
            await api.post(`/requests/${id}/revisions`, { feedback, file_ids: dz.ids() });
            toast({ title: "Revision requested", body: "The Revision Agent is preparing the change list.", type: "success" });
            await load();
            draw();
          } catch (ex) {
            err.textContent = errorMessage(ex);
            err.classList.remove("hidden");
            setLoading(btn, false);
          }
        });
      }
    }
    body.querySelectorAll("[data-dl]").forEach((b) => b.addEventListener("click", () => downloadFile(Number(b.dataset.dl), b.dataset.name || "file").catch((err) => reportError(err, "Download failed"))));
  }

  function linkButton(l) {
    let fileId = l.file_id;
    if (!fileId && l.url && /\/files\/(\d+)\/download/.test(l.url)) fileId = Number(l.url.match(/\/files\/(\d+)\/download/)[1]);
    if (fileId) return `<button type="button" data-dl="${fileId}" data-name="${esc(l.name || "file")}">${icon("download", "icon-sm")}<span class="flex-1 truncate">${esc(l.name || "Download")}</span></button>`;
    if (l.url && /^https?:\/\//.test(l.url)) return `<a href="${esc(l.url)}" target="_blank" rel="noopener">${icon("external", "icon-sm")}<span class="flex-1 truncate">${esc(l.name || l.url)}</span></a>`;
    return `<span class="file-chip">${icon("file", "icon-sm")}${esc(l.name || "File")}</span>`;
  }

  function filesTable(files) {
    if (!files.length) return emptyState("folder", "No files yet", "Reference files you attach and deliverables will be listed here.");
    return `<div class="table-wrap"><table class="table"><thead><tr><th>File</th><th>Type</th><th>Size</th><th>Added</th><th></th></tr></thead><tbody>${files
      .map((f) => `<tr><td><div class="flex items-center gap-3"><span class="file-ico">${icon(fileIconName(f.mime_type, f.original_name), "icon-sm")}</span><span class="truncate" style="max-width:260px" title="${esc(f.original_name)}">${esc(f.original_name)}</span>${f.version > 1 ? `<span class="badge">v${f.version}</span>` : ""}</div></td><td>${kindBadge(f.kind)}</td><td>${fmtBytes(f.size_bytes)}</td><td>${fmtDate(f.created_at)}</td><td class="text-right"><button class="btn btn-ghost btn-sm" data-dl="${f.id}" data-name="${esc(f.original_name)}">${icon("download", "icon-sm")}</button></td></tr>`)
      .join("")}</tbody></table></div>`;
  }

  async function withdraw() {
    const ok = await confirmDialog({ title: "Withdraw this request?", body: "It will be removed from the queue. You can submit a new one at any time.", confirmText: "Withdraw", danger: true });
    if (!ok) return;
    try {
      await api.del(`/requests/${id}`);
      toast({ title: "Request withdrawn", type: "success" });
      location.hash = "/requests";
    } catch (err) {
      reportError(err, "Could not withdraw");
    }
  }

  draw();

  const onUpdate = async (e) => {
    if (!e.detail || Number(e.detail.request_id) !== id) return;
    try {
      await load();
      draw();
      if (e.detail.status) toast({ title: `Request ${titleCase(e.detail.status)}`, body: detail.title, type: "info", timeout: 3000 });
    } catch {}
  };
  document.addEventListener("df:request_update", onUpdate);
  return () => document.removeEventListener("df:request_update", onUpdate);
}
