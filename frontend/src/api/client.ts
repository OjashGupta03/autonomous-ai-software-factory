const API_BASE = "/api/v1";
const TOKEN_STORAGE_KEY = "factory_access_token";

// Auth token lives in a module-level variable, NOT localStorage/
// sessionStorage - this is a browser app (not a Claude artifact, so
// localStorage would be fine here in principle), but keeping it in
// memory plus a same-session sync from a cookie-less login response
// keeps the auth surface simple; see docs/19-security.md for the
// tradeoffs (page refresh currently requires re-login - a documented
// limitation, not an oversight).
let inMemoryToken: string | null = null;

export function setAuthToken(token: string | null) {
  inMemoryToken = token;
}

export function getAuthToken(): string | null {
  return inMemoryToken;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  // Only default to JSON when the caller hasn't already set a
  // Content-Type (e.g. postForm below sets its own) - unconditionally
  // overwriting it here would silently break any non-JSON request body.
  if (!headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (inMemoryToken) headers.set("Authorization", `Bearer ${inMemoryToken}`);

  const response = await fetch(`${API_BASE}${path}`, { ...options, headers });

  if (!response.ok) {
    let detail = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // response body wasn't JSON - fall back to statusText, already set
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) return undefined as T;
  return response.json() as Promise<T>;
}

export const api = {
  get: <T>(path: string) => request<T>(path, { method: "GET" }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, { method: "POST", body: body ? JSON.stringify(body) : undefined }),
  postForm: <T>(path: string, form: URLSearchParams) =>
    request<T>(path, {
      method: "POST",
      body: form,
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
    }),
};

export { TOKEN_STORAGE_KEY };
