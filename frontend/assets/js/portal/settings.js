/* Profile, company, password, theme */
import { api, errorMessage } from "../core/api.js";
import { fetchMe } from "../core/auth.js";
import { icon, esc, qs, qsa, toast, setLoading, applyTheme, getTheme } from "../core/ui.js";
import { state, pageHeader, reportError } from "./shared.js";

const TIMEZONES = ["UTC", "Europe/London", "Europe/Berlin", "Europe/Paris", "Asia/Kolkata", "Asia/Dubai", "Asia/Singapore", "Asia/Tokyo", "Australia/Sydney", "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles", "America/Sao_Paulo"];

export async function renderSettings(page) {
  const u = state.user;
  const c = u.client || {};
  const tzList = TIMEZONES.includes(u.timezone) || !u.timezone ? TIMEZONES : [u.timezone, ...TIMEZONES];
  page.innerHTML = `${pageHeader({ title: "Settings", sub: "Your profile, company details and preferences." })}
    <div class="settings-grid">
      <form class="card" id="profile-form"><div class="card-header"><h3>Profile</h3></div><div class="card-body">
        <div class="field"><label class="label">Full name</label><input class="input" name="full_name" value="${esc(u.full_name)}"></div>
        <div class="field"><label class="label">Email</label><input class="input" value="${esc(u.email)}" disabled><span class="hint">Contact support to change your login email.</span></div>
        <div class="field"><label class="label">Phone</label><input class="input" name="phone" value="${esc(u.phone || "")}" placeholder="+1 555 000 0000"></div>
        <div class="field"><label class="label">Timezone</label><select class="select" name="timezone">${tzList.map((t) => `<option value="${esc(t)}" ${t === (u.timezone || "UTC") ? "selected" : ""}>${esc(t)}</option>`).join("")}</select></div>
      </div><div class="card-footer flex justify-end"><button class="btn btn-primary" type="submit">Save profile</button></div></form>

      <form class="card" id="company-form"><div class="card-header"><h3>Company &amp; brand</h3></div><div class="card-body">
        <div class="field"><label class="label">Company name</label><input class="input" name="company_name" value="${esc(c.company_name || "")}"></div>
        <div class="field"><label class="label">Website</label><input class="input" name="website" value="${esc(c.website || "")}" placeholder="https://"></div>
        <div class="field"><label class="label">Industry</label><input class="input" name="industry" value="${esc(c.industry || "")}"></div>
        <div class="field"><label class="label">Billing currency</label><select class="select" name="currency">${["USD", "GBP", "INR"].map((cur) => `<option value="${cur}" ${cur === (c.currency || "USD") ? "selected" : ""}>${cur === "USD" ? "USD – US Dollar" : cur === "GBP" ? "GBP – British Pound" : "INR – Indian Rupee"}</option>`).join("")}</select><span class="hint">Prices are fixed per request and shown in this currency. Applies to new requests.</span></div>
        <div class="field"><label class="label">Brand notes</label><textarea class="textarea" name="brand_notes" placeholder="Tone of voice, colours, dos and don'ts. Our agents read this on every request.">${esc(c.brand_notes || "")}</textarea><span class="hint">Shown to the Strategy, Content and Design agents and your designer.</span></div>
      </div><div class="card-footer flex justify-end"><button class="btn btn-primary" type="submit">Save company</button></div></form>

      <form class="card" id="password-form"><div class="card-header"><h3>Password</h3></div><div class="card-body">
        <div class="field"><label class="label">Current password</label><input class="input" type="password" name="current_password" autocomplete="current-password"></div>
        <div class="field"><label class="label">New password</label><input class="input" type="password" name="new_password" autocomplete="new-password" placeholder="At least 8 characters, letters and numbers"></div>
        <div class="field"><label class="label">Confirm new password</label><input class="input" type="password" name="confirm" autocomplete="new-password"></div>
        <p class="error-text mt-3 hidden" id="pw-error"></p>
      </div><div class="card-footer flex justify-end"><button class="btn btn-primary" type="submit">Update password</button></div></form>

      <div class="flex flex-col gap-6">
        <div class="card"><div class="card-header"><h3>Appearance</h3></div><div class="card-body">
          <div class="theme-options" id="theme-options">
            <button type="button" data-theme="system">${icon("globe")} System</button>
            <button type="button" data-theme="light">${icon("sun")} Light</button>
            <button type="button" data-theme="dark">${icon("moon")} Dark</button>
          </div></div></div>
        <div class="card"><div class="card-header"><h3>Your data</h3></div><div class="card-body text-sm text-2">
          <p>You own every file we deliver. To export your full history or delete your account and data, email <b>hello@designflow.io</b> from your login address, or open a <a href="#/support">support ticket</a>. We'll confirm within one business day.</p>
        </div></div>
      </div>
    </div>`;

  const themeBox = qs("#theme-options", page);
  const syncTheme = () => qsa("button", themeBox).forEach((b) => b.classList.toggle("active", b.dataset.theme === getTheme()));
  syncTheme();
  themeBox.addEventListener("click", (e) => {
    const b = e.target.closest("[data-theme]");
    if (!b) return;
    try {
      if (b.dataset.theme === "system") localStorage.removeItem("df-theme");
      else localStorage.setItem("df-theme", b.dataset.theme);
    } catch {}
    applyTheme(b.dataset.theme);
    syncTheme();
  });

  async function saveProfile(form, fields, label) {
    const btn = qs("button[type=submit]", form);
    setLoading(btn, true);
    const payload = {};
    fields.forEach((f) => {
      const el = qs(`[name=${f}]`, form);
      if (el) payload[f] = el.value.trim();
    });
    try {
      await api.patch("/auth/me", payload);
      state.user = await fetchMe();
      toast({ title: `${label} saved`, type: "success" });
      if (payload.full_name) {
        const n = qs("#user-name");
        if (n) n.textContent = payload.full_name.split(" ")[0];
      }
    } catch (err) {
      reportError(err, `Could not save ${label.toLowerCase()}`);
    } finally {
      setLoading(btn, false);
    }
  }

  qs("#profile-form", page).addEventListener("submit", (e) => {
    e.preventDefault();
    saveProfile(e.target, ["full_name", "phone", "timezone"], "Profile");
  });
  qs("#company-form", page).addEventListener("submit", (e) => {
    e.preventDefault();
    saveProfile(e.target, ["company_name", "website", "industry", "brand_notes", "currency"], "Company");
  });
  qs("#password-form", page).addEventListener("submit", async (e) => {
    e.preventDefault();
    const form = e.target;
    const err = qs("#pw-error", form);
    err.classList.add("hidden");
    const cur = qs("[name=current_password]", form).value;
    const nw = qs("[name=new_password]", form).value;
    const conf = qs("[name=confirm]", form).value;
    if (!cur || nw.length < 8 || !/\d/.test(nw) || !/[a-zA-Z]/.test(nw)) {
      err.textContent = "New password must be at least 8 characters with letters and numbers.";
      err.classList.remove("hidden");
      return;
    }
    if (nw !== conf) {
      err.textContent = "Passwords do not match.";
      err.classList.remove("hidden");
      return;
    }
    const btn = qs("button[type=submit]", form);
    setLoading(btn, true);
    try {
      await api.post("/auth/change-password", { current_password: cur, new_password: nw });
      toast({ title: "Password updated", type: "success" });
      form.reset();
    } catch (ex) {
      err.textContent = errorMessage(ex);
      err.classList.remove("hidden");
    } finally {
      setLoading(btn, false);
    }
  });
}
