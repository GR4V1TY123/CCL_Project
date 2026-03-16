import { v4 as uuidv4 } from "uuid";

const BASE_URL = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";
const TOKEN_KEY = "ccl_token";

function getSessionId() {
  const key = "ccl_session_id";
  let sessionId = localStorage.getItem(key);
  if (!sessionId) {
    sessionId = uuidv4();
    localStorage.setItem(key, sessionId);
  }
  return sessionId;
}

export function getToken() {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token) {
  localStorage.setItem(TOKEN_KEY, token);
}

export function clearToken() {
  localStorage.removeItem(TOKEN_KEY);
}

async function request(path, options = {}) {
  const token = getToken();
  const headers = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  const res = await fetch(`${BASE_URL}${path}`, {
    headers,
    ...options,
  });

  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${text}`);
  }

  return res.json();
}

export async function getChatHistory() {
  const session_id = getSessionId();
  return request(`/chat/history/${encodeURIComponent(session_id)}`);
}

export async function sendChatMessage(message) {
  const session_id = getSessionId();
  return request("/chat/message", {
    method: "POST",
    body: JSON.stringify({ session_id, message }),
  });
}

export async function markMessageInvalid(messageIndex) {
  const session_id = getSessionId();
  return request("/chat/feedback", {
    method: "POST",
    body: JSON.stringify({ session_id, message_index: messageIndex }),
  });
}

export async function getKnowledge() {
  return request("/admin/knowledge");
}

export async function addKnowledge(topic, info) {
  return request("/admin/knowledge", {
    method: "POST",
    body: JSON.stringify({ topic, info }),
  });
}

export async function getStudents() {
  return request("/admin/students");
}

export async function addStudent(student) {
  return request("/admin/students", {
    method: "POST",
    body: JSON.stringify(student),
  });
}

export async function getPlaybook() {
  const session_id = getSessionId();
  return request(`/admin/playbook/${encodeURIComponent(session_id)}`);
}

export async function getLogs() {
  return request("/admin/logs");
}

export async function approveLog(logId, rule) {
  const session_id = getSessionId();
  return request(`/admin/logs/${encodeURIComponent(logId)}/approve`, {
    method: "POST",
    body: JSON.stringify({ rule, session_id }),
  });
}

export async function deleteLog(logId) {
  const session_id = getSessionId();
  return request(`/admin/logs/${encodeURIComponent(logId)}`, {
    method: "DELETE",
    body: JSON.stringify({ session_id }),
  });
}

export async function register(username, password) {
  const res = await request("/auth/register", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  if (res?.access_token) {
    setToken(res.access_token);
  }
  return res;
}

export async function login(username, password) {
  const res = await request("/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
  if (res?.access_token) {
    setToken(res.access_token);
  }
  return res;
}

export async function getMe() {
  return request("/auth/me");
}

export function getApiBaseUrl() {
  return BASE_URL;
}
