/**
 * Typed fetch wrapper. Attaches `Authorization: Bearer <token>` automatically
 * (from the token store), parses FastAPI's `{ detail }` error envelope, and
 * surfaces every failure as an ApiError so callers never fail silently.
 */
import { API_BASE_URL } from "./config";
import { getToken, notifyUnauthorized } from "./authToken";
import type { MarkInvalidDetail } from "./types";

export class ApiError extends Error {
  status: number;
  /** Raw `detail` from FastAPI: a string for most errors, an object for the
   *  /api/attendance/mark enrollment failure. */
  detail: unknown;
  retryAfter: number | null;

  constructor(status: number, message: string, detail: unknown, retryAfter: number | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
    this.retryAfter = retryAfter;
  }

  get isUnauthorized() {
    return this.status === 401;
  }
  get isForbidden() {
    return this.status === 403;
  }
  get isRateLimited() {
    return this.status === 429;
  }

  /** True when this is the mark endpoint's structured "unenrolled students" 400. */
  get markInvalidDetail(): MarkInvalidDetail | null {
    if (
      this.status === 400 &&
      this.detail &&
      typeof this.detail === "object" &&
      "invalid_entries" in (this.detail as Record<string, unknown>)
    ) {
      return this.detail as MarkInvalidDetail;
    }
    return null;
  }
}

/** A human-readable string for any error `detail` (string, object, or unknown). */
export function detailToMessage(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (detail && typeof detail === "object") {
    const obj = detail as Record<string, unknown>;
    if (typeof obj.message === "string") return obj.message;
  }
  return fallback;
}

interface RequestOptions {
  method?: string;
  /** JSON body — serialized and given an application/json content-type. */
  json?: unknown;
  /** FormData body — sent as multipart/form-data (no explicit content-type). */
  form?: FormData;
  /** Attach the bearer token (default true). */
  auth?: boolean;
  query?: Record<string, string | number | undefined>;
  signal?: AbortSignal;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = new URL(`${API_BASE_URL}${path}`);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined) url.searchParams.set(k, String(v));
    }
  }
  return url.toString();
}

function authHeader(auth: boolean): Record<string, string> {
  if (!auth) return {};
  const token = getToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function toApiError(res: Response, authed: boolean): Promise<ApiError> {
  let detail: unknown = null;
  try {
    const body = await res.json();
    detail = (body as { detail?: unknown })?.detail ?? body;
  } catch {
    detail = res.statusText;
  }
  const retryAfterRaw = res.headers.get("Retry-After");
  const retryAfter = retryAfterRaw ? Number.parseInt(retryAfterRaw, 10) : null;
  const message = detailToMessage(detail, `Request failed (${res.status})`);
  const err = new ApiError(res.status, message, detail, Number.isNaN(retryAfter) ? null : retryAfter);
  // Only treat a 401 as "session expired" when the request was authenticated.
  // Public endpoints (e.g. FaceID login) legitimately return 401 for an
  // unrecognized face — that must NOT trigger the global logout/redirect.
  if (res.status === 401 && authed) notifyUnauthorized();
  return err;
}

async function parse<T>(res: Response, authed: boolean): Promise<T> {
  if (!res.ok) throw await toApiError(res, authed);
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

export async function apiFetch<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const { method, json, form, auth = true, query, signal } = options;
  const headers: Record<string, string> = { ...authHeader(auth) };
  let body: BodyInit | undefined;

  if (json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(json);
  } else if (form !== undefined) {
    body = form; // browser sets multipart boundary automatically
  }

  let res: Response;
  try {
    res = await fetch(buildUrl(path, query), {
      method: method ?? (body ? "POST" : "GET"),
      headers,
      body,
      signal,
    });
  } catch (e) {
    if (e instanceof DOMException && e.name === "AbortError") throw e;
    throw new ApiError(
      0,
      `Cannot reach the server at ${API_BASE_URL}. Is the backend running?`,
      null,
      null
    );
  }
  return parse<T>(res, auth);
}

/** Fetch a binary resource (e.g. the QR PNG) with auth, as a Blob. */
export async function apiBlob(path: string, options: RequestOptions = {}): Promise<Blob> {
  const { auth = true, query } = options;
  let res: Response;
  try {
    res = await fetch(buildUrl(path, query), { headers: authHeader(auth) });
  } catch {
    throw new ApiError(0, `Cannot reach the server at ${API_BASE_URL}.`, null, null);
  }
  if (!res.ok) throw await toApiError(res, auth);
  return res.blob();
}
