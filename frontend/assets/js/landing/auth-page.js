/* Login + register pages */
import { initTheme, qs, setLoading } from "../core/ui.js";
import { errorMessage } from "../core/api.js";
import { login, register, isLoggedIn, cachedUser, homeFor } from "../core/auth.js";

initTheme();

const params = new URLSearchParams(location.search);
const next = params.get("next");
const service = params.get("service");

function destination(user) {
  if (next && next.startsWith("/")) return next;
  if (user.role === "client") {
    if (service) return `/portal#/new?service=${encodeURIComponent(service)}`;
  }
  return homeFor(user);
}

if (isLoggedIn() && cachedUser()) {
  location.replace(destination(cachedUser()));
}

const loginForm = qs("#login-form");
const registerForm = qs("#register-form");
const err = qs("#form-error");

function showError(msg) {
  err.textContent = msg;
  err.classList.remove("hidden");
}

if (loginForm) {
  loginForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    err.classList.add("hidden");
    const email = qs("#email").value.trim();
    const password = qs("#password").value;
    if (!email || !password) return showError("Enter your email and password.");
    const btn = qs("button[type=submit]", loginForm);
    setLoading(btn, true);
    try {
      const user = await login(email, password);
      location.href = destination(user);
    } catch (ex) {
      showError(errorMessage(ex));
      setLoading(btn, false);
    }
  });
}

if (registerForm) {
  registerForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    err.classList.add("hidden");
    const data = Object.fromEntries(new FormData(registerForm).entries());
    if (!data.full_name || !data.email || !data.password) return showError("Please fill in all required fields.");
    if (data.password.length < 8 || !/\d/.test(data.password) || !/[a-zA-Z]/.test(data.password)) return showError("Password must be at least 8 characters and include letters and numbers.");
    if (!data.website) delete data.website;
    if (!data.industry) delete data.industry;
    if (!data.currency) data.currency = "USD";
    const btn = qs("button[type=submit]", registerForm);
    setLoading(btn, true);
    try {
      const user = await register(data);
      location.href = destination(user);
    } catch (ex) {
      showError(errorMessage(ex));
      setLoading(btn, false);
    }
  });
}
