/** SC-005 (013): nenhuma violação automática de WCAG 2.2 AA nas telas — com dados, vazio e erro —, nos dois temas e na
 * largura de tablet (os projetos do playwright.config.ts). */

import { test } from "@playwright/test";

import { expectAccessible, login, OUTSIDER } from "./fixtures/session";

const SCREENS = [
  "/uso",
  "/uso/precos",
  "/assistentes",
  "/assistentes/geral/modelos",
  "/assistentes/geral/mcp",
  "/assistentes/geral/historico",
  "/assistentes/rascunho/modelos",
  "/assistentes/documentos/modelos",
  "/servidores-mcp",
  "/observabilidade",
  "/acesso/usuarios",
  "/acesso/grupos",
  "/acesso/login",
];

test("todas as telas com dados", async ({ page }) => {
  await login(page, "/uso");
  for (const path of SCREENS) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    await expectAccessible(page, path);
  }
});

test("estados vazio e de erro", async ({ page }) => {
  await login(page, "/uso?origem=evaluation");
  await page.getByText("Nenhuma chamada de modelo neste período").waitFor();
  await expectAccessible(page, "uso vazio");
  await page.route("**/admin/v1/usage**", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({
        error: { message: "armazenamento indisponível", type: "server_error", code: "storage_unavailable" },
      }),
    }),
  );
  await page.goto("/uso?dias=7");
  await page.getByText("Não foi possível carregar o uso").waitFor({ timeout: 15_000 });
  await expectAccessible(page, "uso com erro");
});

test("acesso negado", async ({ page }) => {
  await login(page, "/uso", OUTSIDER);
  await page.getByText("Sua conta não tem acesso à console").waitFor();
  await expectAccessible(page, "acesso negado");
});
