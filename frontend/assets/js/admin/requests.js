/* Requests: board + table with real-time action buttons */
import { api } from "../core/api.js";
import { esc, icon, qs, qsa, timeAgo, fmtDate, statusBadge, priorityBadge, debounce, STATUS_LABELS } from "../core/ui.js";
import {
  pageHeader, getServices, getClients, renderBoard, moveCard, bindActions, ACTION_DEFS, actionButtons, dataTable, sortRows,
  pager, loadingBlock, errorBlock, updateColCounts, requestCard, priceBadge,
} from "./shared.js";

const PRIORITIES = ["low", "normal", "high", "urgent"];

export async function render(page, params, query) {
  let view = localStorage.getItem("df-admin-req-view") || "board";
  let filters = { q: query.q || "", service_id: query.service_id || "", priority: query.priority || "", client_id: query.client_id || "", status: query.status || "" };
  let sort = { key: "submitted_at", dir: "desc" };
  let tablePage = 1;
  let requests = [];
  let total = 0;
  const seen = new Set();
  const newIds = new Set();

  page.innerHTML = pageHeader("Requests", "Accept, reject and complete work in real time.", `
      <div class="segmented" id="view-toggle"><button data-view="board" class="${view === "board" ? "active" : ""}">${icon("kanban", "icon-sm")} Board</button><button data-view="table" class="${view === "table" ? "active" : ""}">${icon("list", "icon-sm")} Table</button></div>`) +
    `<div class="filters" id="filters">
      <div class="input-group">${icon("search")}<input class="input" id="f-q" placeholder="Search title or description" value="${esc(filters.q)}"></div>
      <select class="select" id="f-service"><option value="">All services</option></select>
      <select class="select" id="f-priority"><option value="">All priorities</option>${PRIORITIES.map((p) => `<option value="${p}" ${filters.priority === p ? "selected" : ""}>${p[0].toUpperCase() + p.slice(1)}</option>`).join("")}</select>
      <select class="select" id="f-client"><option value="">All clients</option></select>
      <select class="select" id="f-status"><option value="">All statuses</option>${Object.entries(STATUS_LABELS).map(([k, v]) => `<option value="${k}" ${filters.status === k ? "selected" : ""}>${v}</option>`).join("")}</select>
      <button class="btn btn-ghost btn-sm" id="f-clear">Clear</button>
      <span class="ml-auto text-sm text-3" id="count"></span>
    </div>
    <div id="content">${loadingBlock(5)}</div>`;

  const content = qs("#content", page);

  getServices().then((svcs) => {
    const sel = qs("#f-service", page);
    svcs.forEach((s) => {
      const o = document.createElement("option");
      o.value = s.id;
      o.textContent = s.name;
      if (String(s.id) === String(filters.service_id)) o.selected = true;
      sel.appendChild(o);
    });
  });
  getClients().then((cl) => {
    const sel = qs("#f-client", page);
    cl.forEach((c) => {
      const o = document.createElement("option");
      o.value = c.id;
      o.textContent = c.company_name;
      if (String(c.id) === String(filters.client_id)) o.selected = true;
      sel.appendChild(o);
    });
  });

  async function load() {
    try {
      const params = { ...filters, page_size: view === "board" ? 200 : 25, page: view === "board" ? 1 : tablePage };
      const data = await api.get("/requests", params);
      requests = data.items;
      total = data.total;
      newIds.clear();
      if (seen.size) requests.forEach((r) => !seen.has(r.id) && newIds.add(r.id));
      requests.forEach((r) => seen.add(r.id));
      qs("#count", page).textContent = `${total} request${total === 1 ? "" : "s"}`;
      draw();
    } catch (err) {
      content.innerHTML = errorBlock(err);
    }
  }

  function draw() {
    if (view === "board") {
      renderBoard(content, requests, { newIds });
    } else {
      const rows = sortRows(requests, sort.key, sort.dir);
      content.innerHTML = dataTable({
        columns: [
          { key: "title", label: "Request", sortable: true, render: (r) => `<a href="#/requests/${r.id}"><b>${esc(r.title)}</b></a><div class="text-xs text-3">${esc(r.service_name)}</div>` },
          {
            key: "client_name", label: "Client", sortable: true,
            render: (r) => `<b>${esc(r.client_name || r.company_name)}</b>${r.company_name && r.company_name !== r.client_name ? `<div class="text-xs text-3">${esc(r.company_name)}</div>` : ""}`,
          },
          { key: "status", label: "Status", sortable: true, render: (r) => statusBadge(r.status) },
          { key: "priority", label: "Priority", sortable: true, render: (r) => priorityBadge(r.priority) },
          { key: "price_amount", label: "Price", sortable: true, render: (r) => priceBadge(r) || "—" },
          { key: "submitted_at", label: "Submitted", sortable: true, render: (r) => `<span title="${esc(r.submitted_at || "")}">${timeAgo(r.submitted_at)}</span>` },
          { key: "due_at", label: "Due", sortable: true, render: (r) => (r.due_at ? fmtDate(r.due_at) : "—") },
          { key: "revision_count", label: "Rev.", sortable: true },
          { key: "actions", label: "Actions", render: (r) => `<div class="flex gap-1 wrap" data-title="${esc(r.title)}">${actionButtons(r)}</div>` },
        ],
        rows,
        sortKey: sort.key,
        sortDir: sort.dir,
        empty: "No requests match these filters",
        rowAttrs: (r) => `data-req="${r.id}" class="${newIds.has(r.id) ? "new" : ""}"`,
      });
      if (total > 25) content.appendChild(pager({ page: tablePage, total, pageSize: 25, onPage: (p) => { tablePage = p; load(); } }));
      qsa("[data-sort]", content).forEach((th) =>
        th.addEventListener("click", () => {
          const k = th.dataset.sort;
          sort = { key: k, dir: sort.key === k && sort.dir === "desc" ? "asc" : "desc" };
          draw();
        })
      );
    }
  }

  bindActions(content, {
    onStart: (id, act) => (view === "board" ? moveCard(content, id, ACTION_DEFS[act].next) : null),
    onDone: (updated) => {
      const idx = requests.findIndex((r) => r.id === updated.id);
      if (idx >= 0) requests[idx] = updated;
      if (view === "board") {
        const cardEl = qs(`[data-req="${updated.id}"]`, content);
        if (cardEl) {
          cardEl.outerHTML = requestCard(updated);
          const fresh = qs(`[data-req="${updated.id}"]`, content);
          const body = qs(`[data-col-body="${updated.status}"]`, content);
          if (fresh && body && fresh.parentElement !== body) body.prepend(fresh);
          updateColCounts(content);
        }
      } else draw();
    },
  });

  qs("#view-toggle", page).addEventListener("click", (e) => {
    const b = e.target.closest("[data-view]");
    if (!b) return;
    view = b.dataset.view;
    localStorage.setItem("df-admin-req-view", view);
    qsa("[data-view]", page).forEach((x) => x.classList.toggle("active", x === b));
    load();
  });

  const applyFilters = debounce(() => {
    filters = {
      q: qs("#f-q", page).value.trim(),
      service_id: qs("#f-service", page).value,
      priority: qs("#f-priority", page).value,
      client_id: qs("#f-client", page).value,
      status: qs("#f-status", page).value,
    };
    tablePage = 1;
    load();
  }, 250);
  ["#f-q", "#f-service", "#f-priority", "#f-client", "#f-status"].forEach((sel) => qs(sel, page).addEventListener("input", applyFilters));
  qs("#f-clear", page).addEventListener("click", () => {
    ["#f-q", "#f-service", "#f-priority", "#f-client", "#f-status"].forEach((sel) => (qs(sel, page).value = ""));
    applyFilters();
  });

  const onUpdate = debounce(() => load(), 400);
  document.addEventListener("df:request_update", onUpdate);

  await load();
  return () => document.removeEventListener("df:request_update", onUpdate);
}
