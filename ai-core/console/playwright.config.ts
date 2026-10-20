/**
 * E2e da console contra a plataforma real em memória (013 R11): o `serve_platform.py` sobe `platform(profile="test")`
 * com a identidade ligada, e o `vite preview` repassa os prefixos do core como o nginx da instalação. Um worker só: as
 * specs mudam o estado da mesma plataforma.
 */

import { defineConfig, devices } from "@playwright/test";

const CORE = 8765;
const ci = Boolean(process.env.CI);
// Contra o nginx da instalação (`e2e/serve_nginx.sh`), quem sobe a plataforma e o nginx é quem roda o teste.
const nginx = Boolean(process.env.CONSOLE_NGINX_URL);

export default defineConfig({
  testDir: "e2e",
  fullyParallel: false,
  workers: 1,
  retries: ci ? 1 : 0,
  timeout: 45_000,
  expect: { timeout: 8_000 },
  reporter: ci ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: "http://127.0.0.1:4173",
    locale: "pt-BR",
    timezoneId: "America/Sao_Paulo",
    trace: "retain-on-failure",
  },
  projects: [
    {
      name: "claro",
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 960 }, colorScheme: "light" },
    },
    {
      name: "escuro",
      testMatch: /a11y\.spec\.ts/,
      use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 960 }, colorScheme: "dark" },
    },
    {
      name: "tablet",
      testMatch: /(a11y|keyboard)\.spec\.ts/,
      use: { ...devices["Desktop Chrome"], viewport: { width: 768, height: 1024 }, colorScheme: "light" },
    },
  ],
  webServer: nginx
    ? []
    : [
        {
          command: "uv run python console/e2e/serve_platform.py",
          cwd: "..",
          url: `http://127.0.0.1:${CORE}/.well-known/openid-configuration`,
          reuseExistingServer: !ci,
          timeout: 180_000,
          env: {
            CONSOLE_E2E_PORT: String(CORE),
            XDG_DATA_HOME: process.env.XDG_DATA_HOME ?? `${process.env.HOME}/.local/share`,
          },
        },
        {
          command: "npm run build && npm run preview",
          url: "http://127.0.0.1:4173",
          reuseExistingServer: !ci,
          timeout: 120_000,
          env: { AI_CORE_UPSTREAM: `http://127.0.0.1:${CORE}` },
        },
      ],
});
