/* New request wizard */
import { api, errorMessage } from "../core/api.js";
import { icon, esc, qs, qsa, toast, setLoading, promptDialog } from "../core/ui.js";
import { getServices, serviceIcon, pageHeader, createDropzone, renderFields, readFields, validateFields, wireColorFields, reportError, priceFor, fmtPrice, clientCurrency, payRequest } from "./shared.js";

export async function renderNewRequest(page, params, query) {
  page.innerHTML = pageHeader({ title: "Order a design", sub: `Fixed price per request in ${clientCurrency()}, delivery time shown on every service. No subscription.` }) + `<div id="wizard"><div class="skeleton" style="height:200px"></div></div>`;
  const wizard = qs("#wizard", page);
  let services = [];
  try {
    services = await getServices();
  } catch (err) {
    wizard.innerHTML = `<div class="empty"><h4>Could not load services</h4><p>${esc(errorMessage(err))}</p></div>`;
    return;
  }
  const preset = query.service ? services.find((s) => s.slug === query.service) : null;
  if (preset) showForm(preset);
  else showPicker();

  function steps(active) {
    return `<div class="wizard-steps">
      <span class="ws ${active === 1 ? "active" : ""}"><i>1</i> Choose a service</span><span class="sep"></span>
      <span class="ws ${active === 2 ? "active" : ""}"><i>2</i> Brief &amp; files</span><span class="sep"></span>
      <span class="ws ${active === 3 ? "active" : ""}"><i>3</i> Submitted</span>
    </div>`;
  }

  function showPicker() {
    const cats = [];
    services.forEach((s) => !cats.includes(s.category) && cats.push(s.category));
    wizard.innerHTML = `${steps(1)}
      <div class="filters-row">
        <div class="input-group" style="max-width:320px;flex:1">${icon("search")}<input class="input" id="svc-search" placeholder="Search services…"></div>
        <div class="pills" id="svc-cats"><button class="pill active" data-cat="All">All</button>${cats.map((c) => `<button class="pill" data-cat="${esc(c)}">${esc(c)}</button>`).join("")}</div>
      </div>
      <div class="svc-pick" id="svc-grid"></div>`;
    const grid = qs("#svc-grid", wizard);
    const search = qs("#svc-search", wizard);
    let cat = "All";
    const draw = () => {
      const q = search.value.trim().toLowerCase();
      const list = services.filter((s) => (cat === "All" || s.category === cat) && (!q || s.name.toLowerCase().includes(q) || s.tagline.toLowerCase().includes(q) || s.category.toLowerCase().includes(q)));
      grid.innerHTML = list.length
        ? list.map((s) => {
            const p = priceFor(s);
            return `<div class="service-card" data-slug="${esc(s.slug)}" role="button" tabindex="0">
            <span class="service-icon">${serviceIcon(s.icon)}</span><h3>${esc(s.name)}</h3><p>${esc(s.tagline)}</p>
            <div class="meta"><span class="svc-price">${fmtPrice(p.amount, p.currency)}</span><span class="delivery">${icon("clock", "icon-sm")}${s.turnaround_days}-day delivery</span></div></div>`;
          }).join("")
        : `<div class="empty" style="grid-column:1/-1"><h4>No services match</h4></div>`;
    };
    draw();
    search.addEventListener("input", draw);
    qs("#svc-cats", wizard).addEventListener("click", (e) => {
      const b = e.target.closest("[data-cat]");
      if (!b) return;
      cat = b.dataset.cat;
      qsa(".pill", qs("#svc-cats", wizard)).forEach((p) => p.classList.toggle("active", p === b));
      draw();
    });
    grid.addEventListener("click", (e) => {
      const c = e.target.closest("[data-slug]");
      if (c) {
        location.hash = `/new?service=${c.dataset.slug}`;
      }
    });
    grid.addEventListener("keydown", (e) => {
      const c = e.target.closest("[data-slug]");
      if (c && (e.key === "Enter" || e.key === " ")) {
        e.preventDefault();
        location.hash = `/new?service=${c.dataset.slug}`;
      }
    });
  }

  async function showForm(service) {
    const schema = service.form_schema || [];
    let projects = [];
    try {
      projects = await api.get("/projects");
    } catch {}
    const price = priceFor(service);
    wizard.innerHTML = `${steps(2)}
      <div class="form-layout">
        <form class="card" id="req-form" novalidate>
          <div class="card-header">
            <div class="flex items-center gap-3"><span class="service-icon">${serviceIcon(service.icon)}</span><div><h3>${esc(service.name)}</h3><span class="text-3 text-sm">${esc(service.tagline)}</span></div></div>
            <a class="btn btn-ghost btn-sm" href="#/new">${icon("arrow-left", "icon-sm")} Change</a>
          </div>
          <div class="card-body">
            <div class="form-grid">
              <div class="field span-2"><label class="label" for="title">Request title <span class="req">*</span></label><input class="input" id="title" name="title" placeholder="e.g. Holiday campaign thumbnail set" maxlength="200"></div>
              <div class="field span-2"><label class="label" for="description">Describe what you need</label><textarea class="textarea" id="description" name="description" placeholder="Goal, context, anything we should know…"></textarea></div>
              ${renderFields(schema)}
              <div class="field"><label class="label">Priority</label><div class="segmented" id="priority">${["low", "normal", "high", "urgent"].map((p) => `<button type="button" data-p="${p}" class="${p === "normal" ? "active" : ""}">${p[0].toUpperCase() + p.slice(1)}</button>`).join("")}</div></div>
              <div class="field"><label class="label" for="project">Project <span class="text-4">(optional)</span></label><div class="flex gap-2"><select class="select" id="project"><option value="">No project</option>${projects.filter((p) => p.status !== "archived").map((p) => `<option value="${p.id}">${esc(p.name)}</option>`).join("")}</select><button type="button" class="btn btn-secondary btn-icon" id="new-project" data-tip="Create project">${icon("plus")}</button></div></div>
              <div class="field span-2"><label class="label">Reference files &amp; assets</label><div id="dropzone"></div></div>
            </div>
            <p class="error-text mt-4 hidden" id="form-error"></p>
          </div>
          <div class="card-footer flex items-center justify-between gap-3 wrap">
            <span class="text-xs text-3">Fields marked <span class="req">*</span> are required. You pay after submitting.</span>
            <button class="btn btn-primary btn-lg" type="submit">Submit request ${icon("send")}</button>
          </div>
        </form>
        <aside class="form-side">
          <div class="price-box">
            <div class="price-amount">${fmtPrice(price.amount, price.currency)}</div>
            <div class="price-meta">${esc(price.unit)} · delivered in ${service.turnaround_days} day${service.turnaround_days === 1 ? "" : "s"}</div>
            <div class="text-xs text-3 mt-2">Price: ${esc(price.currency)} ${Math.round(price.amount)} · ${esc(price.unit)} · Delivered in ${service.turnaround_days} day${service.turnaround_days === 1 ? "" : "s"}</div>
          </div>
          <div class="card"><div class="card-body">
            <h4>What's included</h4>
            <ul class="mt-3 flex flex-col gap-2 text-sm text-2">${(service.deliverables || []).map((d) => `<li class="flex gap-2">${icon("check-circle", "icon-sm")}<span>${esc(d)}</span></li>`).join("")}</ul>
            <hr>
            <div class="text-sm"><b>Delivery time</b><div class="text-3">${service.turnaround_days} day${service.turnaround_days === 1 ? "" : "s"} after payment and acceptance. Unlimited revisions included.</div></div>
            <div class="text-sm mt-3"><b>What happens next</b><div class="text-3">Submit, pay (card or bank), we accept it, then agents and your designer get to work. You're notified at every step.</div></div>
          </div></div>
        </aside>
      </div>`;

    const form = qs("#req-form", wizard);
    wireColorFields(form);
    const dz = createDropzone(qs("#dropzone", wizard), { kind: "upload" });
    let priority = "normal";
    qs("#priority", wizard).addEventListener("click", (e) => {
      const b = e.target.closest("[data-p]");
      if (!b) return;
      priority = b.dataset.p;
      qsa("button", qs("#priority", wizard)).forEach((x) => x.classList.toggle("active", x === b));
    });
    qs("#new-project", wizard).addEventListener("click", async () => {
      const name = await promptDialog({ title: "New project", label: "Project name", placeholder: "e.g. Q4 Launch", confirmText: "Create" });
      if (!name || !name.trim()) return;
      try {
        const p = await api.post("/projects", { name: name.trim() });
        const sel = qs("#project", wizard);
        const o = document.createElement("option");
        o.value = p.id;
        o.textContent = p.name;
        o.selected = true;
        sel.appendChild(o);
        toast({ title: "Project created", type: "success" });
      } catch (err) {
        reportError(err, "Could not create project");
      }
    });

    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      const err = qs("#form-error", wizard);
      err.classList.add("hidden");
      const title = qs("#title", form).value.trim();
      const problems = [];
      qs("#title", form).classList.toggle("invalid", title.length < 3);
      if (title.length < 3) problems.push("Request title");
      problems.push(...validateFields(form, schema));
      if (problems.length) {
        err.textContent = `Please fill in: ${problems.join(", ")}`;
        err.classList.remove("hidden");
        err.scrollIntoView({ behavior: "smooth", block: "center" });
        return;
      }
      if (dz.busy()) {
        err.textContent = "Please wait for uploads to finish.";
        err.classList.remove("hidden");
        return;
      }
      const btn = qs("button[type=submit]", form);
      setLoading(btn, true);
      try {
        const created = await api.post("/requests", {
          service_id: service.id,
          title,
          description: qs("#description", form).value.trim() || null,
          brief: readFields(form, schema),
          priority,
          project_id: qs("#project", form).value ? Number(qs("#project", form).value) : null,
          file_ids: dz.ids(),
        });
        toast({ title: "Request submitted", body: "Pay now to start the clock, or pay later from the request.", type: "success" });
        const amount = created.price_amount ? fmtPrice(created.price_amount, created.price_currency) : null;
        wizard.innerHTML = `${steps(3)}<div class="card"><div class="card-body text-center" style="padding:48px 24px">
          <span class="service-icon mx-auto" style="width:64px;height:64px;border-radius:18px">${icon("check-circle", "icon-lg")}</span>
          <h2 class="mt-4">Request #${created.id} is submitted</h2>
          <p class="text-3 mt-2">${esc(created.title)} · ${esc(created.service_name)} · ${created.turnaround_days}-day delivery</p>
          ${amount ? `<div class="price-box mx-auto mt-6" style="max-width:360px"><div class="price-amount">${amount}</div><div class="price-meta">Due for this request. Work starts once payment is received.</div></div>` : ""}
          <div class="flex gap-3 justify-center wrap mt-6">
            ${amount && !created.is_paid ? `<button class="btn btn-gradient btn-lg" id="pay-now">${icon("credit-card")} Pay now ${amount}</button>` : ""}
            <a class="btn btn-secondary btn-lg" href="#/requests/${created.id}">${amount && !created.is_paid ? "Pay later" : "Track this request"}</a>
          </div>
          <p class="text-xs text-3 mt-4"><a href="#/new">Order another design</a></p>
        </div></div>`;
        const payBtn = qs("#pay-now", wizard);
        if (payBtn) payBtn.addEventListener("click", async () => {
          const res = await payRequest(created.id, payBtn);
          if (res) location.hash = `/requests/${created.id}`;
        });
      } catch (ex) {
        err.textContent = errorMessage(ex);
        err.classList.remove("hidden");
        setLoading(btn, false);
      }
    });
  }
}
