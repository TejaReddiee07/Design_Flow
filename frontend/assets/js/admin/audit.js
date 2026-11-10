/* Audit log */
import { api } from "../core/api.js";
import { esc, icon, qs, qsa, fmtDateTime, debounce } from "../core/ui.js";
import { pageHeader, dataTable, pager, loadingBlock, errorBlock } from "./shared.js";

const ENTITIES = ["user", "client", "service_request", "service", "design", "delivery", "revision", "file", "brand_asset", "project", "payment", "billing", "lead", "outreach", "agent", "support_ticket"];

export async function render(page, params, query) {
  let action = query.action || "";
  let entity = query.entity || "";
  let pg = 1;
  page.innerHTML = pageHeader("Audit log", "Every login, status change and admin action, with before/after values.") +
    `<div class="filters"><div class="input-group">${icon("search")}<input class="input" id="f-action" placeholder="Filter by action, e.g. request.accept" value="${esc(action)}"></div><select class="select" id="f-entity"><option value="">All entities</option>${ENTITIES.map((e) => `<option value="${e}" ${e === entity ? "selected" : ""}>${e}</option>`).join("")}</select><span class="ml-auto text-sm text-3" id="count"></span></div><div id="content">${loadingBlock(6)}</div>`;
  const content = qs("#content", page);

  function json(v) {
    if (v === null || v === undefined) return '<span class="text-4">—</span>';
    return `<pre class="json-view" style="max-height:200px">${esc(JSON.stringify(v, null, 2))}</pre>`;
  }

  async function load() {
    try {
      const data = await api.get("/admin/audit", { action: action || undefined, entity: entity || undefined, page: pg, page_size: 50 });
      qs("#count", page).textContent = `${data.total} entr${data.total === 1 ? "y" : "ies"}`;
      content.innerHTML = dataTable({
        columns: [
          { key: "created_at", label: "When", render: (a) => fmtDateTime(a.created_at) },
          { key: "actor", label: "Actor", render: (a) => `<b>${esc(a.actor)}</b>${a.user_id ? `<div class="text-xs text-3">user #${a.user_id}</div>` : ""}` },
          { key: "action", label: "Action", render: (a) => `<code>${esc(a.action)}</code>` },
          { key: "entity", label: "Entity", render: (a) => `<span class="badge">${esc(a.entity)}</span>${a.entity_id ? ` <span class="text-3">#${a.entity_id}</span>` : ""}${a.entity === "service_request" && a.entity_id ? ` <a href="#/requests/${a.entity_id}">${icon("external", "icon-sm")}</a>` : ""}` },
          { key: "ip", label: "IP", render: (a) => esc(a.ip || "—") },
          { key: "diff", label: "Changes", cls: "wrap audit-row", render: (a) => (a.before || a.after ? `<details><summary>before / after</summary><div class="flex gap-3 mt-2 wrap"><div class="flex-1 min-w-0"><div class="text-xs text-3 mb-1">Before</div>${json(a.before)}</div><div class="flex-1 min-w-0"><div class="text-xs text-3 mb-1">After</div>${json(a.after)}</div></div></details>` : '<span class="text-4">—</span>') },
        ],
        rows: data.items,
        empty: "No audit entries",
        emptyIcon: "list",
      });
      if (data.total > 50) content.appendChild(pager({ page: pg, total: data.total, pageSize: 50, onPage: (p) => { pg = p; load(); } }));
    } catch (err) {
      content.innerHTML = errorBlock(err);
    }
  }

  const apply = debounce(() => { action = qs("#f-action", page).value.trim(); entity = qs("#f-entity", page).value; pg = 1; load(); }, 250);
  qs("#f-action", page).addEventListener("input", apply);
  qs("#f-entity", page).addEventListener("change", apply);
  await load();
}
