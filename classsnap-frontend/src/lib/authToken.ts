/**
 * Framework-agnostic token store (localStorage) shared by the API client and
 * the React AuthProvider. Kept separate from auth.tsx to avoid a circular
 * import between the fetch wrapper and the React context.
 *
 * NOTE: httpOnly cookies would be preferable, but the backend returns the JWT
 * in the JSON login/register body (it does not Set-Cookie), so the only place
 * the client can hold it without backend changes is localStorage. Flagged in
 * the handoff notes.
 */
import type { Role } from "./types";

export interface StoredAuth {
  token: string;
  role: Role;
  id: number;
  name: string;
  username?: string;
}

const STORAGE_KEY = "classsnap.auth";

let unauthorizedHandler: (() => void) | null = null;

/** Registered by AuthProvider; called when any request gets a 401. */
export function setUnauthorizedHandler(handler: (() => void) | null) {
  unauthorizedHandler = handler;
}

export function notifyUnauthorized() {
  if (unauthorizedHandler) unauthorizedHandler();
}

export function readAuth(): StoredAuth | null {
  if (typeof window === "undefined") return null;
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as StoredAuth;
  } catch {
    return null;
  }
}

export function writeAuth(auth: StoredAuth) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(auth));
}

export function clearAuth() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(STORAGE_KEY);
}

export function getToken(): string | null {
  return readAuth()?.token ?? null;
}
