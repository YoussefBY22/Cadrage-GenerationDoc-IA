import { defineConfig } from "@playwright/test";

const API_PORT = process.env.E2E_API_PORT ?? "8001";
const API = `http://localhost:${API_PORT}`;
const FRONT = "http://localhost:3001";

// Parcours complet contre l'API de démonstration (modèle « demo », sans réseau) et le front de production.
// Python du backend : variable CADRAGE_PYTHON (voir e2e/start-api.mjs).
export default defineConfig({
  testDir: "./e2e",
  timeout: 240_000,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: FRONT,
    viewport: { width: 1440, height: 900 },
    deviceScaleFactor: 1,
    locale: "fr-FR",
    acceptDownloads: true,
    trace: "retain-on-failure",
  },
  webServer: [
    {
      command: "node e2e/start-api.mjs",
      env: { E2E_API_PORT: API_PORT },
      url: `${API}/health`,
      reuseExistingServer: false,
      timeout: 120_000,
      stdout: "pipe",
    },
    {
      command: "npx next build && npx next start -p 3001",
      url: `${FRONT}/login`,
      reuseExistingServer: false,
      timeout: 300_000,
      env: { NEXT_PUBLIC_API_URL: API },
    },
  ],
});
