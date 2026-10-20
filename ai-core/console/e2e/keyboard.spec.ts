/** FR-017 (013): a console inteira pelo teclado — atalho para o conteúdo, navegação, segmentados por setas, dica do
 * gráfico, diálogo que prende e devolve o foco. */

import { expect, test } from "@playwright/test";

import { login } from "./fixtures/session";

test("atalho para o conteúdo e navegação pelo teclado", async ({ page }) => {
  await login(page, "/uso");
  await expect(page.getByRole("heading", { name: "Uso e custo" })).toBeVisible();
  await page.keyboard.press("Tab");
  const skip = page.getByRole("link", { name: "Ir para o conteúdo" });
  await expect(skip).toBeFocused();
  await page.keyboard.press("Enter");
  await expect(page.locator("main#conteudo")).toBeFocused();
  await page.getByRole("link", { name: "Assistentes" }).focus();
  await page.keyboard.press("Enter");
  await expect(page).toHaveURL(/\/assistentes$/);
});

test("segmentado pelas setas e dica do gráfico pelo teclado", async ({ page }) => {
  await login(page, "/uso");
  await page.getByRole("radio", { name: "30 dias" }).focus();
  await page.keyboard.press("ArrowRight");
  await expect(page.getByRole("radio", { name: "90 dias" })).toBeFocused();
  await page.keyboard.press("Space");
  await expect(page).toHaveURL(/dias=90/);
  await page.getByRole("img", { name: /Custo por dia/ }).focus();
  await page.keyboard.press("End");
  await expect(page.getByRole("status").filter({ hasText: "Total" })).toBeVisible();
  await page.keyboard.press("Escape");
  await expect(page.getByRole("status").filter({ hasText: "Total" })).toHaveCount(0);
});

test("o diálogo prende o foco e o devolve a quem abriu", async ({ page }) => {
  await login(page, "/acesso/usuarios");
  const open = page.getByRole("button", { name: "Cadastrar pessoa" }).first();
  await open.focus();
  await page.keyboard.press("Enter");
  const dialog = page.getByRole("dialog", { name: "Cadastrar pessoa" });
  await expect(dialog).toBeVisible();
  for (let index = 0; index < 12; index += 1) {
    await page.keyboard.press("Tab");
    await expect(dialog.locator(":focus")).toHaveCount(1);
  }
  await page.keyboard.press("Escape");
  await expect(dialog).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Cadastrar pessoa" }).first()).toBeFocused();
});
