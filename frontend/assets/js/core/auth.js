/* Authentication helpers shared by landing, portal and admin. */
import { api, tokens } from "./api.js";

export async function login(email, password) {
  const data = await api.post("/auth/login", { email, password });
  tokens.set(data);
  return data.user;
}

export async function register(payload) {
  const data = await api.post("/auth/register", payload);
  tokens.set(data);
  return data.user;
}

export async function logout(redirect = "/login") {
  const rt = tokens.refresh();
  try {
    if (rt) await api.post("/auth/logout", { refresh_token: rt });
  } catch {}
  tokens.clear();
  if (redirect) location.href = redirect;
}

export function cachedUser() {
  return tokens.user();
}

export async function fetchMe() {
  const user = await api.get("/auth/me");
  tokens.set({ user });
  return user;
}

export function homeFor(user) {
  if (!user) return "/login";
  return user.role === "client" ? "/portal" : "/admin";
}

/**
 * Ensure the visitor is logged in with one of the given roles.
 * Redirects otherwise. Returns the user.
 */
export async function requireAuth(roles = ["admin", "client", "staff"]) {
  if (!tokens.access() && !tokens.refresh()) {
    location.href = `/login?next=${encodeURIComponent(location.pathname + location.hash)}`;
    return null;
  }
  let user = cachedUser();
  try {
    user = await fetchMe();
  } catch (err) {
    if (err.status === 401) {
      tokens.clear();
      location.href = `/login?next=${encodeURIComponent(location.pathname + location.hash)}`;
      return null;
    }
  }
  if (user && !roles.includes(user.role)) {
    location.href = homeFor(user);
    return null;
  }
  return user;
}

export function isLoggedIn() {
  return Boolean(tokens.access() || tokens.refresh());
}
