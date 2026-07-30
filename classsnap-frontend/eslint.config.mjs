import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    rules: {
      // Performance heuristic (react-hooks v6). We intentionally setState in
      // effects for external-sync patterns: reading localStorage / the URL on
      // mount, kicking off async data loaders, and resetting form state when a
      // dialog opens. These are correct and avoid hydration mismatches, so we
      // opt out of the heuristic rather than contort the code.
      "react-hooks/set-state-in-effect": "off",
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
