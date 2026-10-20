/** US6 (013): cadastrar uma pessoa e ver a senha temporária uma única vez; desativar; Google liga e desliga; o grupo de
 * administração é protegido. */

import { expect, test } from "@playwright/test";

import { login } from "./fixtures/session";

const stamp = Date.now().toString(36);

test("cadastra uma pessoa, a senha temporária aparece uma vez, e desativa a conta", async ({ page }) => {
  await login(page, "/acesso/usuarios");
  await page.getByRole("button", { name: "Cadastrar pessoa" }).first().click();
  const dialog = page.getByRole("dialog", { name: "Cadastrar pessoa" });
  await dialog.getByLabel("Nome").fill("Eva Torres");
  await dialog.getByLabel("Usuário").fill(`eva${stamp}`);
  await dialog.getByLabel("E-mail").fill(`eva${stamp}@exemplo.org`);
  await dialog.getByRole("checkbox", { name: "equipe" }).check();
  await dialog.getByRole("button", { name: "Cadastrar" }).click();
  const created = page.getByRole("dialog", { name: "Eva Torres foi cadastrado" });
  const password = await created.getByLabel("Senha temporária").inputValue();
  expect(password.length).toBeGreaterThan(8);
  await created.getByRole("button", { name: "Concluir" }).click();
  await expect(page.getByText(password)).toHaveCount(0);
  const row = page.getByRole("row", { name: new RegExp(`eva${stamp}`) });
  await expect(row.getByText("Senha temporária")).toBeVisible();

  await row.getByRole("button", { name: "Ações de Eva Torres" }).click();
  await page.getByRole("button", { name: "Desativar conta" }).click();
  await page.getByRole("button", { name: "Confirmar" }).click();
  await page.getByRole("radio", { name: "Todas" }).click();
  await expect(page.getByRole("row", { name: new RegExp(`eva${stamp}`) }).getByText("Desativada")).toBeVisible();
  expect(await page.content()).not.toContain(password);
});

test("Google liga e desliga, com o endereço de retorno para registrar", async ({ page }) => {
  await login(page, "/acesso/login");
  await expect(page.getByLabel("Endereço de retorno para cadastrar no Google")).toHaveValue(
    /\/oauth2\/google\/callback$/,
  );
  const google = page.getByRole("switch", { name: "Entrar com Google" });
  await google.click();
  await expect(google).toHaveAttribute("aria-checked", "false");
  await google.click();
  await expect(google).toHaveAttribute("aria-checked", "true");
});

test("o grupo de administração é protegido; um grupo comum é criado e apagado", async ({ page }) => {
  await login(page, "/acesso/grupos");
  await expect(page.getByRole("row", { name: /admin.*Protegido/ }).getByRole("button", { name: "Apagar" })).toHaveCount(
    0,
  );
  await page.getByLabel("Novo grupo").fill(`temp${stamp}`);
  await page.getByRole("button", { name: "Criar grupo" }).click();
  const row = page.getByRole("row", { name: new RegExp(`temp${stamp}`) });
  await row.getByRole("button", { name: "Apagar" }).click();
  await page.getByRole("alert").getByRole("button", { name: "Apagar" }).click();
  await expect(row).toHaveCount(0);
});
