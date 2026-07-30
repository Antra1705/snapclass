"use client";

import { useEffect, useState } from "react";

/**
 * Reads a URL query param on the client after mount. Avoids Next's
 * useSearchParams Suspense-boundary requirement for these simple lookups.
 */
export function useQueryParam(name: string): string | null {
  const [value, setValue] = useState<string | null>(null);
  useEffect(() => {
    setValue(new URLSearchParams(window.location.search).get(name));
  }, [name]);
  return value;
}
