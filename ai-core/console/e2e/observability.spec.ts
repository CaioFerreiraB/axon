/** US5 (013): Langfuse salvo e testado; a chave secreta nunca volta à tela; captura só com o aviso confirmado. */

import { expect, test } from "@playwright/test";

import { login } from "./fixtures/session";

const SECRET = "sk-lf-segredo-do-e2e";

test.describe.configure({ mode: "serial" });

test("salva endereço e chaves, testa a conexão; o segredo só aparece como definido", async ({ page }) => {
  await login(page, "/observabilidade");
  await page.getByLabel("Endereço").fill("https://lf.exemplo.org");
  await page.getByLabel("Chave pública").fill("pk-lf-e2e");
  await page.getByLabel("Chave secreta").fill(SECRET);
  await page.getByRole("button", { name: "Salvar" }).click();
  await expect(page.getByLabel("Chave secreta")).toHaveAttribute("placeholder", "Definida · digite para trocar");
  await expect(page.getByLabel("Chave secreta")).toHaveValue("");
  await page.getByRole("button", { name: "Testar conexão" }).click();
  await expect(page.getByText(/As credenciais foram aceitas/)).toBeVisible();
  await page.reload();
  await expect(page.getByLabel("Chave pública")).toHaveValue("pk-lf-e2e");
  expect(await page.content()).not.toContain(SECRET);
});

test("ligar a captura exige confirmar o aviso de privacidade", async ({ page }) => {
  await login(page, "/observabilidade");
  const capture = page.getByRole("switch", { name: "Capturar prompt e resposta" });
  await capture.click();
  const confirm = page.getByRole("button", { name: "Ligar captura" });
  await expect(confirm).toBeDisabled();
  await page.getByRole("checkbox", { name: "Li e quero capturar o texto" }).check();
  await confirm.click();
  await expect(capture).toHaveAttribute("aria-checked", "true");
  await capture.click();
  await expect(capture).toHaveAttribute("aria-checked", "false");
});
