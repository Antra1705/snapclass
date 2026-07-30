import type { NextConfig } from "next";
import path from "node:path";

const nextConfig: NextConfig = {
  reactCompiler: true,
  // Pin the workspace root to this project so Next doesn't pick up an
  // unrelated lockfile elsewhere on the machine.
  turbopack: {
    root: path.join(__dirname),
  },
};

export default nextConfig;
