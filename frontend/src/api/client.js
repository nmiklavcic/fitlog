// Thin wrapper around fetch for the Django API.
// - Sends the session cookie (same origin, so `credentials: "same-origin"` is enough).
// - Adds Django's CSRF token header to every non-GET request.
// - Turns error responses into ApiError with the HTTP status and DRF's error body.

export class ApiError extends Error {
  constructor(status, data) {
    super(typeof data === "object" && data?.detail ? data.detail : `Request failed (${status})`);
    this.status = status;
    this.data = data;
    this.code = typeof data === "object" ? data?.code : undefined;
  }
}

function getCookie(name) {
  const match = document.cookie.split("; ").find((row) => row.startsWith(`${name}=`));
  return match ? decodeURIComponent(match.split("=")[1]) : null;
}

async function ensureCsrfCookie() {
  if (!getCookie("csrftoken")) {
    await fetch("/api/auth/csrf/", { credentials: "same-origin" });
  }
}

export async function api(path, { method = "GET", body, form, signal } = {}) {
  const headers = { Accept: "application/json" };
  const options = { method, credentials: "same-origin", headers, signal };

  if (method !== "GET") {
    await ensureCsrfCookie();
    headers["X-CSRFToken"] = getCookie("csrftoken");
  }
  if (form) {
    options.body = form; // multipart: the browser sets the Content-Type boundary itself
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }

  const response = await fetch(path.startsWith("/api") ? path : `/api${path}`, options);
  if (response.status === 204) return null;
  const isJson = response.headers.get("content-type")?.includes("application/json");
  const data = isJson ? await response.json() : await response.text();
  if (!response.ok) throw new ApiError(response.status, data);
  return data;
}

// DRF pagination returns absolute "next" URLs; keep only the path + query.
export function nextPath(url) {
  if (!url) return undefined;
  const parsed = new URL(url, window.location.origin);
  return parsed.pathname + parsed.search;
}

// One readable sentence from any DRF error shape.
export function errorMessage(error) {
  if (!error) return "";
  if (!(error instanceof ApiError)) return error.message || "Something went wrong.";
  const data = error.data;
  if (error.status >= 500) return "The server had a problem. Try again in a moment.";
  if (typeof data === "string") return data.slice(0, 200) || error.message;
  if (data?.detail) return data.detail;
  if (data && typeof data === "object") {
    const [field, messages] = Object.entries(data)[0] ?? [];
    const message = Array.isArray(messages) ? messages[0] : typeof messages === "string" ? messages : JSON.stringify(messages);
    return field === "non_field_errors" ? message : `${field.replaceAll("_", " ")}: ${message}`;
  }
  return error.message;
}

// Per-field errors for forms: { password: "This password is too short..." }
export function fieldErrors(error) {
  if (!(error instanceof ApiError) || typeof error.data !== "object" || !error.data) return {};
  return Object.fromEntries(
    Object.entries(error.data)
      .filter(([, v]) => Array.isArray(v) && typeof v[0] === "string")
      .map(([k, v]) => [k, v.join(" ")])
  );
}
