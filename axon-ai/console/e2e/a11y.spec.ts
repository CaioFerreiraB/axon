/** SC-005 (013): nenhuma violação automática de WCAG 2.2 AA nas telas — com dados, vazio e erro —, nos dois temas e na
 * largura de tablet (os projetos do playwright.config.ts). */

import { expect, test } from "@playwright/test";

import { expectAccessible, login, OUTSIDER } from "./fixtures/session";

const SCREENS = [
  "/uso",
  "/uso/precos",
  "/meio-ambiente",
  "/meio-ambiente?agregacao=semana&periodo=90",
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
  "/acesso/chaves",
  "/assistentes/relatorios/permissoes",
  "/assistentes/interno/permissoes",
  "/assistentes/rascunho/permissoes",
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

test("o diálogo da chave criada", async ({ page }) => {
  await login(page, "/acesso/chaves?criar=1");
  await page.getByLabel("Nome do sistema").fill(`a11y${Date.now().toString(36)}`);
  await page.getByRole("button", { name: "Gerar chave" }).click();
  await page.getByRole("dialog").waitFor();
  await expectAccessible(page, "diálogo da chave");
  await page.getByRole("button", { name: "Concluir" }).click();
});

// --- incremento 9.7 (SC-012) ------------------------------------------------------------------------------------------

test("a nova chave com os escopos", async ({ page }) => {
  await login(page, "/acesso/chaves?criar=1");
  await page.getByRole("checkbox", { name: "Uso de inferência" }).waitFor();
  await expectAccessible(page, "nova chave com os escopos");
});

test("apagar uma conta: confirmação e relatório, só pelo teclado", async ({ page }) => {
  const username = `ada${Date.now().toString(36)}`;
  await login(page, "/acesso/usuarios?cadastrar=1");
  const create = page.getByRole("dialog", { name: "Cadastrar pessoa" });
  await create.getByLabel("Nome").fill("Ada Reis");
  await create.getByLabel("Usuário").fill(username);
  await create.getByLabel("E-mail").fill(`${username}@exemplo.org`);
  await create.getByRole("button", { name: "Cadastrar" }).click();
  await page.getByRole("dialog", { name: "Ada Reis foi cadastrado" }).getByRole("button", { name: "Concluir" }).click();

  await page.getByRole("button", { name: "Ações de Ada Reis" }).focus();
  await page.keyboard.press("Enter");
  await page.getByRole("button", { name: "Apagar conta" }).focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", { name: "Apagar a conta de Ada Reis?" });
  await dialog.waitFor();
  await expectAccessible(page, "confirmação do apagamento");
  await dialog.getByLabel(/Digite o nome de usuário/).focus();
  await page.keyboard.type(username);
  await page.keyboard.press("Enter");
  await page.getByRole("dialog", { name: `A conta ${username} foi apagada` }).waitFor();
  await expectAccessible(page, "relatório do apagamento");
});

test("a ficha com os grupos na hora", async ({ page }) => {
  await login(page, "/acesso/usuarios");
  await page
    .getByRole("button", { name: /^Ações de / })
    .first()
    .click();
  await page.getByRole("button", { name: "Editar" }).click();
  await page.getByRole("dialog").getByText("Cada grupo vale na hora, sem precisar salvar.").waitFor();
  await expectAccessible(page, "ficha com os grupos");
});
