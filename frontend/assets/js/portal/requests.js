/* My requests list */
import { api } from "../core/api.js";
import { icon, esc, qs, qsa, debounce, skeletonRows, emptyState, STATUS_LABELS } from "../core/ui.js";
import { getServices, pageHeader, requestRow, errorBox } from "./shared.js";

const FILTERS = [["", "All"], ["pending", "Pending"], ["accepted", "Accepted"], ["in_progress", "In Progress"], ["review", "In Review"], ["completed", "Completed"], ["rejected", "Rejected"]];

export async function renderRequests(page, params, query) {
  let status = query.status || "";
  let q = query.q || "";
  let pageNo = Number(query.page || 1);
  const projectId = query.project_id ? Number(query.project_id) : undefined;
  const pageSize = 20;

  page.innerHTML = `
    ${pageHeader({ title: "My requests", sub: "Everything you've submitted, newest first.", actions: `<a class="btn btn-primary" href="#/new">${icon("plus")} New request</a>` })}
    <div class="filters-row">
      <div class="pills" id="status-pills">${FILTERS.map(([v, l]) => `<button class="pill ${v === status ? "active" : ""}" data-status="${v}">${l}</button>`).join("")}</div>
      <div class="input-group ml-auto" style="max-width:280px;flex:1">${icon("search")}<input class="input" id="q" placeholder="Search requests…" value="${esc(q)}"></div>
    </div>
    <div id="list">${skeletonRows(5)}</div>
    <div class="pagination" id="pager"></div>`;

  try {
    await getServices();
  } catch {}

  const list = qs("#list", page);
  const pager = qs("#pager", page);

  async function load() {
    list.innerHTML = skeletonRows(5);
    try {
      const data = await api.get("/requests", { status: status || undefined, q: q || undefined, project_id: projectId, page: pageNo, page_size: pageSize });
      if (!data.items.length) {
        list.innerHTML = emptyState("inbox", status ? `No ${STATUS_LABELS[status] ? STATUS_LABELS[status].toLowerCase() : status} requests` : "No requests yet", q ? "Try a different search." : "Your submitted requests will appear here.");
        pager.innerHTML = "";
        return;
      }
      list.innerHTML = `<div class="req-list">${data.items.map(requestRow).join("")}</div>`;
      const pages = Math.max(1, Math.ceil(data.total / pageSize));
      pager.innerHTML = `<span>${data.total} request${data.total === 1 ? "" : "s"}</span>
        <div class="flex gap-2 items-center"><button class="btn btn-secondary btn-sm" id="prev" ${pageNo <= 1 ? "disabled" : ""}>${icon("chevron-left", "icon-sm")} Prev</button><span>Page ${pageNo} of ${pages}</span><button class="btn btn-secondary btn-sm" id="next" ${pageNo >= pages ? "disabled" : ""}>Next ${icon("chevron-right", "icon-sm")}</button></div>`;
      qs("#prev", pager).onclick = () => {
        pageNo -= 1;
        load();
      };
      qs("#next", pager).onclick = () => {
        pageNo += 1;
        load();
      };
    } catch (err) {
      list.innerHTML = errorBox(err);
    }
  }

  qs("#status-pills", page).addEventListener("click", (e) => {
    const b = e.target.closest("[data-status]");
    if (!b) return;
    status = b.dataset.status;
    pageNo = 1;
    qsa(".pill", qs("#status-pills", page)).forEach((p) => p.classList.toggle("active", p === b));
    load();
  });
  qs("#q", page).addEventListener("input", debounce((e) => {
    q = e.target.value.trim();
    pageNo = 1;
    load();
  }, 300));

  await load();
  const onUpdate = () => load();
  document.addEventListener("df:request_update", onUpdate);
  return () => document.removeEventListener("df:request_update", onUpdate);
}
