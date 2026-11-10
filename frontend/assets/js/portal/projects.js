/* Projects */
import { api, errorMessage } from "../core/api.js";
import { icon, esc, qs, h, modal, confirmDialog, toast, setLoading, fmtDate, titleCase, skeletonRows, emptyState } from "../core/ui.js";
import { pageHeader, errorBox, reportError } from "./shared.js";

export async function renderProjects(page) {
  page.innerHTML = `${pageHeader({ title: "Projects", sub: "Group related requests so everything for a campaign lives together.", actions: `<button class="btn btn-primary" id="btn-new">${icon("plus")} New project</button>` })}<div id="list">${skeletonRows(3)}</div>`;

  async function load() {
    const el = qs("#list", page);
    try {
      const rows = await api.get("/projects");
      const active = rows.filter((p) => p.status !== "archived");
      const archived = rows.filter((p) => p.status === "archived");
      const card = (p) => `<div class="card project-card card-hover"><div class="card-body">
        <div class="flex items-start justify-between gap-2"><div class="min-w-0"><h3 class="truncate">${esc(p.name)}</h3><p class="text-3 text-sm mt-1">${esc(p.description || "No description")}</p></div><span class="badge ${p.status === "active" ? "badge-success" : p.status === "completed" ? "badge-info" : ""}">${esc(titleCase(p.status))}</span></div>
        <div class="flex items-center justify-between mt-4 text-xs text-3"><span>${p.request_count} request${p.request_count === 1 ? "" : "s"} · created ${fmtDate(p.created_at)}</span>
          <div class="flex gap-1"><a class="btn btn-ghost btn-sm" href="#/requests?project_id=${p.id}">View</a><a class="btn btn-ghost btn-sm" href="#/new">Add request</a>${p.status !== "archived" ? `<button class="btn btn-ghost btn-sm" data-archive="${p.id}">Archive</button>` : `<button class="btn btn-ghost btn-sm" data-restore="${p.id}">Restore</button>`}<button class="btn btn-ghost btn-sm" data-delete="${p.id}" aria-label="Delete">${icon("trash", "icon-sm")}</button></div></div>
      </div></div>`;
      el.innerHTML = rows.length
        ? `<div class="grid grid-3">${active.map(card).join("")}</div>${archived.length ? `<h4 class="mt-8 mb-4 text-3">Archived</h4><div class="grid grid-3">${archived.map(card).join("")}</div>` : ""}`
        : emptyState("layers", "No projects yet", "Create one to organise requests by campaign, product or quarter.");
    } catch (err) {
      el.innerHTML = errorBox(err);
    }
  }

  page.addEventListener("click", async (e) => {
    const a = e.target.closest("[data-archive]");
    const r = e.target.closest("[data-restore]");
    const d = e.target.closest("[data-delete]");
    try {
      if (a) {
        await api.patch(`/projects/${a.dataset.archive}`, { status: "archived" });
        toast({ title: "Project archived", type: "success" });
        load();
      } else if (r) {
        await api.patch(`/projects/${r.dataset.restore}`, { status: "active" });
        load();
      } else if (d) {
        if (!(await confirmDialog({ title: "Delete project?", body: "Requests in it are kept; they just lose the project label.", confirmText: "Delete", danger: true }))) return;
        await api.del(`/projects/${d.dataset.delete}`);
        toast({ title: "Project deleted", type: "success" });
        load();
      }
    } catch (err) {
      reportError(err);
    }
  });

  qs("#btn-new", page).addEventListener("click", () => {
    const body = h(`<form id="pform"><div class="field"><label class="label">Name <span class="req">*</span></label><input class="input" name="name" placeholder="Q4 Launch"></div><div class="field"><label class="label">Description</label><textarea class="textarea" name="description" placeholder="What is this project about?"></textarea></div><p class="error-text mt-2 hidden" id="perr"></p></form>`);
    const footer = h(`<div class="flex gap-2 justify-end w-full"><button class="btn btn-secondary" data-cancel>Cancel</button><button class="btn btn-primary" data-save>Create</button></div>`);
    const m = modal({ title: "New project", body, footer });
    qs("[data-cancel]", footer).onclick = () => m.close();
    const save = async () => {
      const err = qs("#perr", body);
      err.classList.add("hidden");
      const name = qs("[name=name]", body).value.trim();
      if (name.length < 2) {
        err.textContent = "Please enter a project name.";
        err.classList.remove("hidden");
        return;
      }
      setLoading(qs("[data-save]", footer), true);
      try {
        await api.post("/projects", { name, description: qs("[name=description]", body).value.trim() || null });
        toast({ title: "Project created", type: "success" });
        m.close();
        load();
      } catch (ex) {
        err.textContent = errorMessage(ex);
        err.classList.remove("hidden");
        setLoading(qs("[data-save]", footer), false);
      }
    };
    qs("[data-save]", footer).onclick = save;
    body.addEventListener("submit", (e) => (e.preventDefault(), save()));
  });

  await load();
}
