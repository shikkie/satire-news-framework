/**
 * Admin session storage (session_id for X-Session-Id header).
 */

const KEY = "agentnews_session_id";
const META_KEY = "agentnews_session_meta";

export function getSessionId() {
  try {
    return sessionStorage.getItem(KEY) || "";
  } catch {
    return "";
  }
}

export function setSession(sessionId, meta = {}) {
  try {
    if (sessionId) sessionStorage.setItem(KEY, sessionId);
    else sessionStorage.removeItem(KEY);
    sessionStorage.setItem(META_KEY, JSON.stringify(meta || {}));
  } catch {
    /* private mode */
  }
}

export function clearSession() {
  setSession("", {});
}

export function getSessionMeta() {
  try {
    return JSON.parse(sessionStorage.getItem(META_KEY) || "{}");
  } catch {
    return {};
  }
}

export function authHeaders(extra = {}) {
  const sid = getSessionId();
  const headers = { ...extra };
  if (sid) headers["X-Session-Id"] = sid;
  return headers;
}

export async function apiJson(path, options = {}) {
  const headers = authHeaders({
    "Content-Type": "application/json",
    ...(options.headers || {}),
  });
  const res = await fetch(path, { ...options, headers, cache: "no-store" });
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = { raw: text };
  }
  if (!res.ok) {
    const err = new Error(data?.message || data?.error || res.statusText);
    err.status = res.status;
    err.data = data;
    throw err;
  }
  return data;
}

export async function login(username, password) {
  const data = await apiJson("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  setSession(data.session_id, {
    username: data.username,
    role: data.role,
  });
  return data;
}

export async function logout() {
  try {
    await apiJson("/api/auth/logout", { method: "POST" });
  } catch {
    /* ignore */
  }
  clearSession();
}

export async function fetchMe() {
  return apiJson("/api/auth/me");
}
