/**
 * Single place the backend base URL is defined. To point the app at a
 * deployed backend (e.g. Render) later, change NEXT_PUBLIC_API_BASE_URL in
 * the environment (or the fallback below) — a one-line change, no grep.
 */
export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL?.replace(/\/$/, "") ?? "http://localhost:8000";
