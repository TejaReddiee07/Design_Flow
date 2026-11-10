/* WebSocket client: reconnects, re-authenticates on token refresh, simple event bus. */
import { tokens } from "./api.js";

const listeners = new Map();
let socket = null;
let attempts = 0;
let pingTimer = null;
let wanted = false;
let status = "closed";

function emit(type, payload, raw) {
  (listeners.get(type) || []).forEach((fn) => {
    try {
      fn(payload, raw);
    } catch (e) {
      console.error("ws handler", e);
    }
  });
  (listeners.get("*") || []).forEach((fn) => fn(raw));
}

function setStatus(s) {
  status = s;
  emit("status", { status: s }, { type: "status", payload: { status: s } });
}

export function wsStatus() {
  return status;
}

export function on(type, fn) {
  if (!listeners.has(type)) listeners.set(type, []);
  listeners.get(type).push(fn);
  return () => off(type, fn);
}

export function off(type, fn) {
  const arr = listeners.get(type) || [];
  const i = arr.indexOf(fn);
  if (i >= 0) arr.splice(i, 1);
}

export function connect() {
  wanted = true;
  const token = tokens.access();
  if (!token) return;
  if (socket && (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING)) return;
  const proto = location.protocol === "https:" ? "wss" : "ws";
  setStatus("connecting");
  socket = new WebSocket(`${proto}://${location.host}/ws?token=${encodeURIComponent(token)}`);
  socket.onopen = () => {
    attempts = 0;
    setStatus("open");
    clearInterval(pingTimer);
    pingTimer = setInterval(() => socket && socket.readyState === WebSocket.OPEN && socket.send(JSON.stringify({ type: "ping" })), 30000);
  };
  socket.onmessage = (ev) => {
    let msg;
    try {
      msg = JSON.parse(ev.data);
    } catch {
      return;
    }
    if (msg.type === "ping") {
      socket.send(JSON.stringify({ type: "pong" }));
      return;
    }
    if (msg.type === "pong") return;
    emit(msg.type, msg.payload || {}, msg);
  };
  socket.onclose = (ev) => {
    clearInterval(pingTimer);
    setStatus("closed");
    socket = null;
    if (!wanted) return;
    if (ev.code === 4401) {
      // token rejected: wait for a refresh (api.js dispatches "tokens") then reconnect
      return;
    }
    const delay = Math.min(30000, 1000 * Math.pow(2, attempts++));
    setTimeout(connect, delay);
  };
  socket.onerror = () => {};
}

export function disconnect() {
  wanted = false;
  clearInterval(pingTimer);
  if (socket) socket.close();
  socket = null;
}

document.addEventListener("tokens", () => {
  if (!wanted) return;
  if (socket) {
    wanted = false;
    socket.close();
    wanted = true;
  }
  attempts = 0;
  setTimeout(connect, 100);
});

document.addEventListener("visibilitychange", () => {
  if (document.visibilityState === "visible" && wanted && !socket) connect();
});

export const ws = { connect, disconnect, on, off, status: wsStatus };
