/**
 * API client. Thin wrapper over `fetch` with:
 *
 * * `credentials: "include"` so the auth cookies travel with every call;
 * * automatic JSON encoding/decoding of bodies;
 * * a typed error class so callers can distinguish HTTP failures from
 *   network failures and read the backend's structured error detail.
 *
 * Endpoint paths are absolute (`/api/v1/auth/login`); the base URL comes
 * from `NEXT_PUBLIC_API_URL`. In dev that's the FastAPI server on a
 * different port; in prod it's the same origin (set to `""`).
 */

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "";

export class ApiError extends Error {
  constructor(
    public readonly status: number,
    message: string,
    public readonly detail?: unknown,
  ) {
    super(message);
    this.name = "ApiError";
  }
}

/**
 * Body is intentionally `unknown`: every endpoint defines its own typed
 * wrapper in `auth-actions.ts`, so the api primitive only needs to know
 * "something JSON-serialisable". Forcing a structural Json type here
 * conflicts with TS interfaces (which lack an index signature).
 */
interface RequestOptions {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  headers?: Record<string, string>;
  signal?: AbortSignal;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method = "GET", body, headers = {}, signal } = options;

  const init: RequestInit = {
    method,
    credentials: "include",
    signal,
    headers: {
      Accept: "application/json",
      ...(body !== undefined ? { "Content-Type": "application/json" } : {}),
      ...headers,
    },
  };
  if (body !== undefined) {
    init.body = JSON.stringify(body);
  }

  const url = `${API_BASE}${path}`;
  let response: Response;
  try {
    response = await fetch(url, init);
  } catch (cause) {
    throw new ApiError(0, "Network error. Check your connection and try again.", { cause });
  }

  // 204 No Content / non-JSON bodies — return undefined as T.
  if (response.status === 204) {
    return undefined as T;
  }

  let payload: unknown = null;
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
  }

  if (!response.ok) {
    const detail = (payload as { detail?: unknown } | null)?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : detail &&
            typeof detail === "object" &&
            "message" in detail &&
            typeof detail.message === "string"
          ? detail.message
          : `Request failed with status ${response.status}.`;
    throw new ApiError(response.status, message, detail);
  }

  return payload as T;
}

/**
 * Multipart POST. Used by file uploads — the browser sets the
 * `multipart/form-data` boundary itself, so we deliberately do *not*
 * pass a Content-Type header. Auth cookies travel via
 * `credentials: "include"` like the JSON helpers above.
 */
async function requestMultipart<T>(path: string, formData: FormData): Promise<T> {
  const url = `${API_BASE}${path}`;
  let response: Response;
  try {
    response = await fetch(url, {
      method: "POST",
      credentials: "include",
      body: formData,
    });
  } catch (cause) {
    throw new ApiError(0, "Network error. Check your connection and try again.", { cause });
  }

  let payload: unknown = null;
  const contentType = response.headers.get("content-type") ?? "";
  if (contentType.includes("application/json")) {
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
  }

  if (!response.ok) {
    const detail = (payload as { detail?: unknown } | null)?.detail;
    const message =
      typeof detail === "string"
        ? detail
        : `Request failed with status ${response.status}.`;
    throw new ApiError(response.status, message, detail);
  }

  return payload as T;
}

export const api = {
  get: <T>(path: string, options?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, { ...options, method: "GET" }),
  post: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, { ...options, method: "POST", body }),
  put: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, { ...options, method: "PUT", body }),
  patch: <T>(path: string, body?: unknown, options?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, { ...options, method: "PATCH", body }),
  delete: <T>(path: string, options?: Omit<RequestOptions, "method" | "body">) =>
    request<T>(path, { ...options, method: "DELETE" }),
  postMultipart: <T>(path: string, formData: FormData) => requestMultipart<T>(path, formData),
};
