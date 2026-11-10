/* Projects */
import { api, errorMessage } from "../core/api.js";
import { esc, icon, qs, qsa, h, toast, modal, setLoading, fmtDate, titleCase } from "../core/ui.js";
import { pageHeader, dataTable, sortRows, getClients, loadingBlock, errorBlock } from "./shared.js";

const STATUSES = ["active", "completed", "archived"];

export async function render(page) {
  let sort = { key: "created_at", dir: "desc" };
  let clientFilter = "";
  page.innerHTML = pageHeader("Projects", "Group requests into campaigns or initiatives per client.", `<button class="btn btn-primary" id="add">${icon("plus")} New project</button>`) +
    `<div class="filters"><select class="select" id="f-client"><option value="">All clients</option></select></div><div id="content">${loadingBlock(4)}</div>`;
  const content = qs("#content", page);
  const clients = await getClients().catch(() => []);
  clients.forEach((c) => qs("#f-client", page).insertAdjacentHTML("beforeend", `<option value="${c.id}">${esc(c.company_name)}</option>`));

  async function load() {
    try {
      const rows = sortRows(await api.get("/projects", { client_id: clientFilter || undefined }), sort.key, sort.dir);
      content.innerHTML = dataTable({
        columns: [
          { key: "name", label: "Project", sortable: true, render: (p) => `<b>${esc(p.name)}</b>${p.description ? `<div class="text-xs text-3">${esc(p.description)}</div>` : ""}` },
          { key: "company_name", label: "Client", sortable: true, render: (p) => `<a href="#/clients/${p.client_id}">${esc(p.company_name)}</a>` },
          { key: "status", label: "Status", sortable: true, render: (p) => `<span class="badge ${p.status === "active" ? "badge-success" : p.status === "completed" ? "badge-info" : ""}">${esc(titleCase(p.status))}</span>` },
          { key: "request_count", label: "Requests", sortable: true, render: (p) => `<a href="#/requests?project_id=${p.id}">${p.request_count}</a>` },
          { key: "created_at", label: "Created", sortable: true, render: (p) => fmtDate(p.created_at) },
          { key: "actions", label: "", render: (p) => `<div class="flex gap-1"><button class="btn btn-ghost btn-sm" data-edit="${p.id}">${icon("edit", "icon-sm")}</button><button class="btn btn-ghost btn-sm" data-del="${p.id}">${icon("trash", "icon-sm")}</button></div>` },
        ],
        rows,
        sortKey: sort.key,
        sortDir: sort.dir,
        empty: "No projects yet",
        emptyIcon: "folder",
      });
      qsa("[data-sort]", content).forEach((th) => th.addEventListener("click", () => { sort = { key: th.dataset.sort, dir: sort.key === th.dataset.sort && sort.dir === "desc" ? "asc" : "desc" }; load(); }));
      qsa("[data-edit]", content).forEach((b) => b.addEventListener("click", () => openEdit(rows.find((p) => p.id === Number(b.dataset.edit)))));
      qsa("[data-del]", content).forEach((b) => b.addEventListener("click", async () => {
        try {
          await api.del(`/projects/${b.dataset.del}`);
          toast({ title: "Project deleted", type: "success" });
          load();
        } catch (err) {
          toast({ title: "Failed", body: errorMessage(err), type: "error" });
        }
      }));
    } catch (err) {
      content.innerHTML = errorBlock(err);
    }
  }

  function openEdit(p) {
    const body = h(`<div>
      ${p ? "" : `<div class="field"><label class="label">Client</label><select class="select" id="p-client">${clients.map((c) => `<option value="${c.id}">${esc(c.company_name)}</option>`).join("")}</select></div>`}
      <div class="field"><label class="label">Name</label><input class="input" id="p-name" value="${esc(p ? p.name : "")}"></div>
      <div class="field"><label class="label">Description</label><textarea class="textarea" id="p-desc">${esc(p ? p.description || "" : "")}</textarea></div>
      ${p ? `<div class="field"><label class="label">Status</label><select class="select" id="p-status">${STATUSES.map((s) => `<option value="${s}" ${s === p.status ? "selected" : ""}>${titleCase(s)}</option>`).join("")}</select></div>` : ""}
    </div>`);
    const footer = h(`<div class="flex gap-2 justify-end w-full"><button class="btn btn-secondary" data-close>Cancel</button><button class="btn btn-primary" id="p-save">${p ? "Save" : "Create"}</button></div>`);
    const m = modal({ title: p ? "Edit project" : "New project", body, footer });
    qs("#p-save", footer).onclick = async () => {
      setLoading(qs("#p-save", footer), true);
      try {
        if (p) await api.patch(`/projects/${p.id}`, { name: qs("#p-name", body).value, description: qs("#p-desc", body).value, status: qs("#p-status", body).value });
        else await api.post("/projects", { name: qs("#p-name", body).value, description: qs("#p-desc", body).value || null, client_id: Number(qs("#p-client", body).value) });
        m.close();
        toast({ title: p ? "Project updated" : "Project created", type: "success" });
        load();
      } catch (err) {
        toast({ title: "Failed", body: errorMessage(err), type: "error" });
        setLoading(qs("#p-save", footer), false);
      }
    };
  }

  qs("#add", page).onclick = () => openEdit(null);
  qs("#f-client", page).addEventListener("change", (e) => { clientFilter = e.target.value; load(); });
  await load();
}
