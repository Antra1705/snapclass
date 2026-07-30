"use client";

/** Shared loading / error / empty presentational helpers. */
import { ApiError } from "@/lib/api";
import { cn } from "@/lib/cn";

export function Spinner({ label }: { label?: string }) {
  return (
    <div className="flex items-center gap-3 text-slate-500">
      <span className="h-5 w-5 animate-spin rounded-full border-2 border-slate-300 border-t-indigo-600" />
      {label ? <span className="text-sm">{label}</span> : null}
    </div>
  );
}

export function Alert({
  variant = "error",
  title,
  children,
  className,
}: {
  variant?: "error" | "warning" | "success" | "info";
  title?: string;
  children?: React.ReactNode;
  className?: string;
}) {
  const styles = {
    error: "border-red-200 bg-red-50 text-red-800",
    warning: "border-amber-200 bg-amber-50 text-amber-800",
    success: "border-emerald-200 bg-emerald-50 text-emerald-800",
    info: "border-sky-200 bg-sky-50 text-sky-800",
  }[variant];
  return (
    <div className={cn("rounded-lg border p-3 text-sm", styles, className)} role="alert">
      {title ? <p className="font-semibold">{title}</p> : null}
      {children ? <div className={title ? "mt-0.5" : ""}>{children}</div> : null}
    </div>
  );
}

/**
 * Renders an unknown error consistently. Special-cases 403 (permission), 429
 * (rate limit w/ retry), and the /api/attendance/mark 400 (invalid entries).
 */
export function ErrorNotice({ error }: { error: unknown }) {
  if (error instanceof ApiError) {
    const invalid = error.markInvalidDetail;
    if (invalid) {
      return (
        <Alert variant="warning" title="Some entries were rejected — nothing was saved">
          <p>{invalid.message}</p>
          <ul className="mt-1 list-disc pl-5">
            {invalid.invalid_entries.map((e, i) => (
              <li key={i}>
                student #{e.student_id} is not enrolled in subject #{e.subject_id}
              </li>
            ))}
          </ul>
        </Alert>
      );
    }
    if (error.isForbidden) {
      return (
        <Alert variant="warning" title="You don't have permission to do that">
          {error.message}
        </Alert>
      );
    }
    if (error.isRateLimited) {
      return (
        <Alert variant="warning" title="Too many attempts">
          {error.message}
          {error.retryAfter ? ` Try again in about ${error.retryAfter}s.` : ""}
        </Alert>
      );
    }
    if (error.isUnauthorized) {
      return <Alert variant="warning">{error.message || "Please sign in again."}</Alert>;
    }
    return <Alert variant="error">{error.message}</Alert>;
  }
  return <Alert variant="error">{error instanceof Error ? error.message : "Something went wrong."}</Alert>;
}
