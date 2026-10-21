/** SC-005 (013): nenhuma violação automática de WCAG 2.2 AA nas telas — com dados, vazio e erro —, nos dois temas e na
 * largura de tablet (os projetos do playwright.config.ts). */

import { expect, test } from "@playwright/test";

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

test("a aba: favicon do símbolo Axon e o título com o nome da instalação", async ({ page }) => {
  await login(page, "/uso");
  await page.getByRole("heading", { name: "Uso e custo" }).waitFor();
  await expect(page).toHaveTitle("Uso e custo · Axon");
  const icon = page.locator('link[rel="icon"]');
  await expect(icon).toHaveAttribute("type", "image/svg+xml");
  const href = await icon.getAttribute("href");
  expect(href).toBeTruthy();
  const favicon = await page.request.get(new URL(href ?? "", page.url()).toString());
  expect(favicon.status()).toBe(200);
  expect(await favicon.text()).toContain('fill="#0B0F19"');
});
