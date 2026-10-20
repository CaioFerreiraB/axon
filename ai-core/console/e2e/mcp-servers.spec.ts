/** US7 (013): servidores MCP globais; os do arquivo do operador são somente leitura; cadastrar e remover pela API. */

import { expect, test } from "@playwright/test";

import { login } from "./fixtures/session";

test("o servidor do arquivo do operador é somente leitura e mostra o motivo, sem credencial", async ({ page }) => {
  await login(page, "/servidores-mcp");
  const row = page.getByRole("row", { name: /planilhas/ });
  await expect(row.getByText("mcp.yaml · somente leitura")).toBeVisible();
  await expect(row.getByRole("button", { name: /Ações/ })).toHaveCount(0);
  await expect(row.getByText("Credencial ausente na instalação")).toBeVisible();
  // O detalhe mostra o que o mcp.yaml define, com a credencial só pelo nome da referência.
  await row.getByRole("button", { name: "Ver planilhas, somente leitura" }).click();
  const details = page.getByRole("region", { name: "planilhas · mcp.yaml" });
  await expect(details.getByText("https://planilhas.interno.exemplo.org/mcp")).toBeVisible();
  await expect(details.getByText("ler, escrever")).toBeVisible();
  await expect(details.getByRole("textbox")).toHaveCount(0);
  await details.getByRole("button", { name: "Fechar" }).click();
  await expect(details).toHaveCount(0);
});

test("cadastra e remove um servidor pela console", async ({ page }) => {
  const alias = `teste${Date.now().toString(36)}`;
  await login(page, "/servidores-mcp");
  await page.getByRole("button", { name: "Novo servidor" }).click();
  await page.getByLabel("Alias").fill(alias);
  await page.getByLabel("Endereço").fill(`https://mcp.exemplo.org/${alias}`);
  await page.getByLabel("Tools permitidas").fill("listar");
  await page.getByRole("button", { name: "Cadastrar servidor" }).click();
  const row = page.getByRole("row", { name: new RegExp(alias) });
  await expect(row.getByText("API", { exact: true })).toBeVisible();
  await row.getByRole("button", { name: `Ações de ${alias}` }).click();
  await page.getByRole("button", { name: "Remover" }).click();
  await page.getByRole("alert").getByRole("button", { name: "Remover" }).click();
  await expect(row).toHaveCount(0);
});
