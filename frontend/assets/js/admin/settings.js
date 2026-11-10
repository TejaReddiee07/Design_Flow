/* Settings: system status, profile, password, theme */
import { api, errorMessage } from "../core/api.js";
import { esc, icon, qs, qsa, toast, setLoading, getTheme, applyTheme } from "../core/ui.js";
import { fetchMe } from "../core/auth.js";
import { pageHeader, loadingBlock, errorBlock, card } from "./shared.js";

export async function render(page, params, query, ctx) {
  const me = ctx.user;
  page.innerHTML = pageHeader("Settings", "System status, your profile and preferences.") +
    `<div class="dash-grid">
      <div class="sys-status" id="sys">${loadingBlock(4)}</div>
      <div class="flex flex-col gap-5">
        ${card("Profile", `<div class="card-body">
          <div class="field"><label class="label">Full name</label><input class="input" id="p-name" value="${esc(me.full_name)}"></div>
          <div class="field"><label class="label">Email</label><input class="input" value="${esc(me.email)}" disabled></div>
          <div class="field"><label class="label">Phone</label><input class="input" id="p-phone" value="${esc(me.phone || "")}"></div>
          <div class="field"><label class="label">Timezone</label><input class="input" id="p-tz" value="${esc(me.timezone || Intl.DateTimeFormat().resolvedOptions().timeZone)}"></div>
          <button class="btn btn-primary mt-4" id="p-save">Save profile</button></div>`)}
        ${card("Password", `<div class="card-body" id="pw-card">
          <div class="field"><label class="label">Current password</label><input class="input" type="password" id="pw-cur" autocomplete="current-password"></div>
          <div class="field"><label class="label">New password</label><input class="input" type="password" id="pw-new" autocomplete="new-password" placeholder="At least 8 characters"></div>
          <button class="btn btn-secondary mt-4" id="pw-save">Change password</button></div>`)}
        ${card("Appearance", `<div class="card-body"><div class="segmented" id="theme-seg">${["system", "light", "dark"].map((t) => `<button data-theme-opt="${t}" class="${getTheme() === t ? "active" : ""}">${t[0].toUpperCase() + t.slice(1)}</button>`).join("")}</div><p class="hint mt-3">Stored on this device.</p></div>`)}
      </div>
    </div>`;

  try {
    const s = await api.get("/admin/settings");
    const yes = (v) => (v ? '<span class="badge badge-success">on</span>' : '<span class="badge">off</span>');
    const live = (name, isLive) => `<span class="badge ${isLive ? "badge-success" : "badge-warning"}">${esc(name)}</span>${isLive ? "" : ' <span class="text-xs text-3">mock mode</span>'}`;
    const llm = s.llm || {};
    const llmProvider = llm.provider || "mock";
    const llmModel = llm.model || "";
    const configured = llm.configured_provider || llmProvider;
    const llmHint = llmProvider === "mock"
      ? `<div class="text-xs text-3 mt-1">${configured === "ollama" ? `Ollama is not reachable${llm.ollama_base_url ? ` at <code>${esc(llm.ollama_base_url)}</code>` : ""} or the model is missing. Install Ollama from ollama.com, then run <code>ollama pull ${esc(llmModel || "llama3.1")}</code> and restart the server.` : "No AI provider is configured - agents return placeholder output. Set LLM_PROVIDER=ollama (free, local) in .env."}</div>`
      : llmProvider === "ollama" ? '<div class="text-xs text-3 mt-1">Running locally with Ollama (free).</div>' : "";
    if (me.email && s.admin_email && me.email.toLowerCase() === String(s.admin_email).toLowerCase()) lockPasswordCard();
    qs("#sys", page).innerHTML = card("System status", `<div class="card-body"><dl class="kv">
        <dt>Application</dt><dd>${esc(s.app_name)} · <span class="badge ${s.app_env === "production" ? "badge-success" : "badge-warning"}">${esc(s.app_env)}</span></dd>
        <dt>Public URL</dt><dd><a href="${esc(s.app_url)}" target="_blank">${esc(s.app_url)}</a></dd>
        <dt>AI model</dt><dd>${live(llmProvider, llmProvider !== "mock")} <code>${esc(llmModel)}</code>${llmHint}</dd>
        <dt>Admin account</dt><dd>${s.admin_email ? `<code>${esc(s.admin_email)}</code> · ` : ""}<span class="text-xs text-3">credentials are managed in <code>.env</code> (ADMIN_EMAIL / ADMIN_PASSWORD) and cannot be changed here</span></dd>
        <dt>Storage</dt><dd>${live(s.storage, s.storage === "gdrive")}${s.storage !== "gdrive" ? ' <span class="text-xs text-3">(local disk)</span>' : ""}</dd>
        <dt>Billing</dt><dd>${live(s.billing, s.billing === "stripe")}</dd>
        <dt>Email</dt><dd>${live(s.email, s.email === "smtp")}</dd>
        <dt>Redis / worker</dt><dd>${s.redis ? '<span class="badge badge-success">connected</span> separate worker process' : '<span class="badge badge-warning">not set</span> <span class="text-xs text-3">agents run inside the API process</span>'}</dd>
        <dt>Agents enabled</dt><dd>${yes(s.agents_enabled)}</dd>
        <dt>Auto-run on accept</dt><dd>${yes(s.auto_run_on_accept)}</dd>
        <dt>Outreach auto-send</dt><dd>${yes(s.outreach_auto_send)}</dd>
        <dt>Lead provider</dt><dd><code>${esc(s.lead_provider)}</code></dd>
        <dt>Image provider</dt><dd><code>${esc(s.image_provider)}</code></dd>
        <dt>Max upload</dt><dd>${s.max_upload_mb} MB</dd>
        <dt>Currencies</dt><dd>USD · GBP · INR <span class="text-xs text-3">(prices set per service in USD; rates in .env)</span></dd>
      </dl><p class="hint mt-4">Change these in <code>.env</code> and restart. See <code>.env.example</code> for every option.</p></div>`) +
      card("Quick links", `<div class="card-body flex gap-2 wrap"><a class="btn btn-secondary btn-sm" href="/docs" target="_blank">${icon("file", "icon-sm")} API docs</a><a class="btn btn-secondary btn-sm" href="/" target="_blank">${icon("globe", "icon-sm")} Public site</a><a class="btn btn-secondary btn-sm" href="/portal" target="_blank">${icon("users", "icon-sm")} Client portal</a><a class="btn btn-secondary btn-sm" href="#/audit">${icon("list", "icon-sm")} Audit log</a></div>`, { cls: "mt-5" });
  } catch (err) {
    qs("#sys", page).innerHTML = errorBlock(err);
  }

  qs("#p-save", page).onclick = async () => {
    const btn = qs("#p-save", page);
    setLoading(btn, true);
    try {
      await api.patch("/auth/me", { full_name: qs("#p-name", page).value, phone: qs("#p-phone", page).value || null, timezone: qs("#p-tz", page).value || null });
      await fetchMe();
      toast({ title: "Profile saved", type: "success" });
      qs("#user-name").textContent = qs("#p-name", page).value;
    } catch (err) {
      toast({ title: "Failed", body: errorMessage(err), type: "error" });
    } finally {
      setLoading(btn, false);
    }
  };
  function lockPasswordCard() {
    const cardBody = qs("#pw-card", page);
    if (cardBody) cardBody.innerHTML = `<p class="text-sm text-2">${icon("lock", "icon-sm")} The primary admin password is managed in the <code>.env</code> file (<code>ADMIN_PASSWORD</code>). Edit it there and restart the server to change it. It cannot be changed from the app.</p>`;
  }
  const pwSaveBtn = qs("#pw-save", page);
  if (pwSaveBtn) pwSaveBtn.onclick = async () => {
    const btn = pwSaveBtn;
    const cur = qs("#pw-cur", page).value;
    const nw = qs("#pw-new", page).value;
    if (!cur || nw.length < 8) return toast({ title: "Check the fields", body: "New password must be at least 8 characters.", type: "warning" });
    setLoading(btn, true);
    try {
      await api.post("/auth/change-password", { current_password: cur, new_password: nw });
      toast({ title: "Password changed", body: "Other sessions were signed out.", type: "success" });
      qs("#pw-cur", page).value = "";
      qs("#pw-new", page).value = "";
    } catch (err) {
      toast({ title: err.status === 403 ? "Managed in .env" : "Failed", body: errorMessage(err), type: err.status === 403 ? "info" : "error", timeout: 7000 });
      if (err.status === 403) lockPasswordCard();
    } finally {
      setLoading(btn, false);
    }
  };
  qs("#theme-seg", page).addEventListener("click", (e) => {
    const b = e.target.closest("[data-theme-opt]");
    if (!b) return;
    const t = b.dataset.themeOpt;
    try {
      if (t === "system") localStorage.removeItem("df-theme");
      else localStorage.setItem("df-theme", t);
    } catch {}
    applyTheme(t);
    qsa("[data-theme-opt]", page).forEach((x) => x.classList.toggle("active", x === b));
  });
}
