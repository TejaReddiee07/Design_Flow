/* API client with JWT access/refresh handling. */

export const API_BASE = "/api/v1";
const ACCESS_KEY = "df-access";
const REFRESH_KEY = "df-refresh";
const USER_KEY = "df-user";

export class ApiError extends Error {
  constructor(status, detail, data) {
    super(typeof detail === "string" ? detail : JSON.stringify(detail));
    this.status = status;
    this.detail = detail;
    this.data = data;
  }
}

export const tokens = {
  access: () => localStorage.getItem(ACCESS_KEY),
  refresh: () => localStorage.getItem(REFRESH_KEY),
  set({ access_token, refresh_token, user }) {
    if (access_token) localStorage.setItem(ACCESS_KEY, access_token);
    if (refresh_token) localStorage.setItem(REFRESH_KEY, refresh_token);
    if (user) localStorage.setItem(USER_KEY, JSON.stringify(user));
    document.dispatchEvent(new CustomEvent("tokens", { detail: { access: access_token } }));
  },
  user() {
    try {
      return JSON.parse(localStorage.getItem(USER_KEY) || "null");
    } catch {
      return null;
    }
  },
  clear() {
    [ACCESS_KEY, REFRESH_KEY, USER_KEY].forEach((k) => localStorage.removeItem(k));
  },
};

let refreshing = null;

async function refreshTokens() {
  if (refreshing) return refreshing;
  const rt = tokens.refresh();
  if (!rt) return false;
  refreshing = fetch(`${API_BASE}/auth/refresh`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ refresh_token: rt }),
  })
    .then(async (r) => {
      if (!r.ok) {
        tokens.clear();
        return false;
      }
      tokens.set(await r.json());
      return true;
    })
    .catch(() => false)
    .finally(() => (refreshing = null));
  return refreshing;
}

function buildQuery(params) {
  if (!params) return "";
  const q = new URLSearchParams();
  Object.entries(params).forEach(([k, v]) => {
    if (v === undefined || v === null || v === "") return;
    q.append(k, v);
  });
  const s = q.toString();
  return s ? `?${s}` : "";
}

async function request(method, path, { params, body, form, raw = false, retry = true } = {}) {
  const headers = {};
  const access = tokens.access();
  if (access) headers.Authorization = `Bearer ${access}`;
  let payload;
  if (form) payload = form;
  else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const res = await fetch(`${API_BASE}${path}${buildQuery(params)}`, { method, headers, body: payload });
  if (res.status === 401 && retry && tokens.refresh()) {
    const ok = await refreshTokens();
    if (ok) return request(method, path, { params, body, form, raw, retry: false });
  }
  if (raw) return res;
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    const detail = (data && data.detail) || res.statusText || "Request failed";
    throw new ApiError(res.status, detail, data);
  }
  return data;
}

export const api = {
  get: (path, params) => request("GET", path, { params }),
  post: (path, body, params) => request("POST", path, { body, params }),
  patch: (path, body, params) => request("PATCH", path, { body, params }),
  put: (path, body, params) => request("PUT", path, { body, params }),
  del: (path, params) => request("DELETE", path, { params }),
  upload: (path, form, params) => request("POST", path, { form, params }),
  raw: (path, params) => request("GET", path, { params, raw: true }),
  refresh: refreshTokens,
};

export function errorMessage(err) {
  if (!err) return "Something went wrong";
  if (err instanceof ApiError) {
    if (Array.isArray(err.detail)) {
      return err.detail.map((d) => `${(d.loc || []).slice(-1)[0] || ""}: ${d.msg}`).join("; ");
    }
    return String(err.detail);
  }
  return err.message || String(err);
}

/** Download an authenticated file in the browser. */
export async function downloadFile(fileId, name = "download") {
  const res = await api.raw(`/files/${fileId}/download`);
  if (!res.ok) throw new ApiError(res.status, "Download failed");
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export function fileUrl(fileId) {
  return `${API_BASE}/files/${fileId}/download?token=${encodeURIComponent(tokens.access() || "")}`;
}
