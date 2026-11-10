/* Users & roles */
import { api, errorMessage } from "../core/api.js";
import { esc, icon, qs, qsa, h, toast, modal, setLoading, fmtDate, timeAgo, titleCase, initials } from "../core/ui.js";
import { pageHeader, dataTable, loadingBlock, errorBlock, card } from "./shared.js";

export async function render(page, params, query, ctx) {
  const me = ctx.user;
  let roleFilter = "";
  page.innerHTML = pageHeader("Users & roles", "Admins run the studio; staff get the same dashboard. Clients are managed under Clients.", `<button class="btn btn-primary" id="add">${icon("plus")} Add user</button>`) +
    `<div class="dash-grid"><div><div class="filters"><select class="select" id="f-role"><option value="">All roles</option><option value="admin">Admin</option><option value="staff">Staff</option><option value="client">Client</option></select></div><div id="content">${loadingBlock(4)}</div></div><div id="roles">${loadingBlock(3)}</div></div>`;
  const content = qs("#content", page);

  async function loadRoles() {
    try {
      const roles = await api.get("/admin/roles");
      qs("#roles", page).innerHTML = card("Roles", `<div class="list">${roles.map((r) => `<div class="list-item"><div class="flex-1"><div class="title">${esc(titleCase(r.name))}</div><div class="meta">${esc(r.description || "")}</div></div><span class="count-badge ${r.users ? "" : "is-zero"}">${r.users}</span></div>`).join("")}</div>`) +
        card("Permissions", `<div class="card-body text-sm"><dl class="kv" style="grid-template-columns:70px 1fr"><dt>admin</dt><dd>Everything: requests, clients, billing, agents, users, audit.</dd><dt>staff</dt><dd>Same dashboard as admin; reserved for team members.</dd><dt>client</dt><dd>Portal only: their own requests, files, invoices and chat.</dd></dl></div>`, { cls: "mt-5" });
    } catch (err) {
      qs("#roles", page).innerHTML = errorBlock(err);
    }
  }

  async function load() {
    try {
      const rows = await api.get("/admin/users", { role: roleFilter || undefined });
      content.innerHTML = dataTable({
        columns: [
          { key: "full_name", label: "User", render: (u) => `<div class="flex items-center gap-3"><span class="avatar avatar-sm ${u.role === "client" ? "avatar-neutral" : ""}">${initials(u.full_name)}</span><div><b>${esc(u.full_name)}</b>${u.id === me.id ? ' <span class="badge">you</span>' : ""}<div class="text-xs text-3">${esc(u.email)}</div></div></div>` },
          { key: "role", label: "Role", render: (u) => `<span class="badge ${u.role === "admin" ? "badge-brand" : u.role === "staff" ? "badge-purple" : ""}">${esc(titleCase(u.role))}</span>` },
          { key: "is_active", label: "Status", render: (u) => (u.is_active ? '<span class="badge badge-success">Active</span>' : '<span class="badge badge-danger">Disabled</span>') },
          { key: "last_login_at", label: "Last login", render: (u) => (u.last_login_at ? timeAgo(u.last_login_at) : "never") },
          { key: "created_at", label: "Created", render: (u) => fmtDate(u.created_at) },
          { key: "actions", label: "", render: (u) => `<button class="btn btn-ghost btn-sm" data-edit="${u.id}">${icon("edit", "icon-sm")} Edit</button>` },
        ],
        rows,
        empty: "No users",
        emptyIcon: "users",
      });
      qsa("[data-edit]", content).forEach((b) => b.addEventListener("click", () => openEdit(rows.find((u) => u.id === Number(b.dataset.edit)))));
    } catch (err) {
      content.innerHTML = errorBlock(err);
    }
  }

  function openEdit(u) {
    const isClient = u && u.role === "client";
    const body = h(`<div class="form-grid">
      ${u ? "" : `<div class="field span-2"><label class="label">Email</label><input class="input" type="email" id="u-email"></div>`}
      <div class="field span-2"><label class="label">Full name</label><input class="input" id="u-name" value="${esc(u ? u.full_name : "")}"></div>
      ${isClient ? "" : `<div class="field"><label class="label">Role</label><select class="select" id="u-role"><option value="admin" ${u && u.role === "admin" ? "selected" : ""}>Admin</option><option value="staff" ${!u || u.role === "staff" ? "selected" : ""}>Staff</option></select></div>`}
      <div class="field"><label class="label">${u ? "New password (optional)" : "Password"}</label><input class="input" id="u-pass" placeholder="${u ? "Leave blank to keep" : "At least 8 characters"}"></div>
      ${u ? `<label class="toggle span-2"><input type="checkbox" id="u-active" ${u.is_active ? "checked" : ""} ${u.id === me.id ? "disabled" : ""}><span class="track"></span>Account enabled</label>` : ""}
    </div>`);
    const footer = h(`<div class="flex gap-2 justify-end w-full"><button class="btn btn-secondary" data-close>Cancel</button><button class="btn btn-primary" id="u-save">${u ? "Save" : "Create"}</button></div>`);
    const m = modal({ title: u ? `Edit ${u.full_name}` : "Add admin or staff user", body, footer });
    qs("#u-save", footer).onclick = async () => {
      setLoading(qs("#u-save", footer), true);
      try {
        if (u) {
          const payload = { full_name: qs("#u-name", body).value, is_active: qs("#u-active", body).checked };
          if (!isClient) payload.role = qs("#u-role", body).value;
          const pw = qs("#u-pass", body).value;
          if (pw) payload.password = pw;
          await api.patch(`/admin/users/${u.id}`, payload);
        } else {
          await api.post("/admin/users", { email: qs("#u-email", body).value, full_name: qs("#u-name", body).value, password: qs("#u-pass", body).value, role: qs("#u-role", body).value });
        }
        m.close();
        toast({ title: u ? "User updated" : "User created", type: "success" });
        load();
        loadRoles();
      } catch (err) {
        toast({ title: "Failed", body: errorMessage(err), type: "error" });
        setLoading(qs("#u-save", footer), false);
      }
    };
  }

  qs("#add", page).onclick = () => openEdit(null);
  qs("#f-role", page).addEventListener("change", (e) => { roleFilter = e.target.value; load(); });
  loadRoles();
  await load();
}
