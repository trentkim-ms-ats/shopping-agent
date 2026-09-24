import type { NextConfig } from "next";
import path from "node:path";
// A separate build directory lets the Playwright server run while `make dev-web` keeps using .next.
const config: NextConfig = {
  turbopack: { root: path.resolve(__dirname) },
  ...(process.env.NEXT_DIST_DIR ? { distDir: process.env.NEXT_DIST_DIR } : {}),
};
export default config;
