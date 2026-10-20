/** US1 (013): entrar pelo login da plataforma, voltar à página pedida, Google simulado, acesso negado sem dado
 * administrativo (SC-007), sair encerra a sessão no provedor, nada de token no navegador (SC-006). */

import { expect, test } from "@playwright/test";

import { ADMIN, login, OUTSIDER } from "./fixtures/session";

test("sem sessão: login da plataforma e volta à página pedida", async ({ page }) => {
  await login(page, "/assistentes/geral/mcp");
  await expect(page).toHaveURL(/\/assistentes\/geral\/mcp$/);
  await expect(page.getByRole("heading", { name: "geral", level: 1 })).toBeVisible();
});

test("fora do grupo de administração: acesso negado e só o /me é pedido", async ({ page }) => {
  const calls = new Set<string>();
  page.on("request", (request) => {
    const url = new URL(request.url());
    if (url.pathname.startsWith("/admin/v1")) {
      calls.add(url.pathname);
    }
  });
  await login(page, "/uso", OUTSIDER);
  await expect(page.getByRole("heading", { name: "Sua conta não tem acesso à console" })).toBeVisible();
  await expect(page.getByText(`(${OUTSIDER.email})`)).toBeVisible();
  await expect(page.getByRole("navigation", { name: "Seções" })).toHaveCount(0);
  expect([...calls]).toEqual(["/admin/v1/me"]);
});

test("Google simulado: entra como a conta cadastrada com o mesmo e-mail", async ({ page }) => {
  await page.goto("/uso");
  await page.waitForURL((url) => url.pathname.startsWith("/oauth2/"));
  await page.getByRole("link", { name: "Entrar com Google" }).click();
  await page.waitForURL((url) => url.port === "4173" && url.pathname === "/uso");
  await expect(page.getByRole("complementary", { name: "Navegação da console" }).getByText("Ana Souza")).toBeVisible();
});

test("sair encerra a sessão no provedor: voltar exige login", async ({ page }) => {
  await login(page);
  await page.getByRole("button", { name: "Sair" }).click();
  await page.waitForURL((url) => url.pathname.startsWith("/oauth2/"));
  await expect(page.getByLabel("Usuário ou e-mail")).toBeVisible();
  await page.goto("/uso");
  await page.waitForURL((url) => url.pathname.startsWith("/oauth2/"));
  await expect(page.getByLabel("Usuário ou e-mail")).toBeVisible();
});

test("nada de token nem dado administrativo no armazenamento do navegador", async ({ page }) => {
  await login(page);
  await expect(page.getByRole("heading", { name: "Uso e custo" })).toBeVisible();
  await page.getByRole("radio", { name: "Tema escuro" }).click();
  const storage = await page.evaluate(() => ({
    local: Object.fromEntries(Object.entries(localStorage)),
    session: Object.keys(sessionStorage),
  }));
  expect(storage.local).toEqual({ "console.theme": "dark" });
  expect(storage.session).toEqual([]);
  expect(JSON.stringify(storage)).not.toContain(ADMIN.password);
});
