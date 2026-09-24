import { defineConfig } from "@playwright/test";
export default defineConfig({
  testDir: "./tests",
  use: { baseURL: "http://localhost:3001", viewport: { width: 1280, height: 800 }, screenshot: "only-on-failure" },
  // Ports are offset from the 8000/3000 dev servers so `make dev-api` / `make dev-web` survive a test run.
  webServer: [
    {
      command: "cd ../backend && DEMO_MODE=fixture uv run --frozen python -m app.cli seed && DEMO_MODE=fixture uv run --frozen python -m app.cli enrich && DEMO_MODE=fixture ALLOWED_ORIGIN=http://localhost:3001 uv run --frozen uvicorn app.main:app --host 127.0.0.1 --port 8001",
      url: "http://127.0.0.1:8001/api/health", reuseExistingServer: false, timeout: 60000,
    },
    {
      command: "npm run dev -- --hostname 127.0.0.1 --port 3001",
      url: "http://localhost:3001", reuseExistingServer: false, timeout: 60000,
      env: { NEXT_PUBLIC_API_BASE_URL: "http://localhost:8001/api", NEXT_DIST_DIR: ".next-test" },
    },
  ],
});
