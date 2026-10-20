/** US3 (013): ligar um servidor MCP ao Assistant e permitir uma tool; escrita bloqueada em público; servidor fora do
 * ar com o motivo. */

import { expect, test } from "@playwright/test";

import { adminGet, login } from "./fixtures/session";

type View = { effective: { mcp: { aliases: string[]; allowed: string[] } } };

test("liga o servidor, permite uma tool e a configuração efetiva traz só ela", async ({ page, request }) => {
  await login(page, "/assistentes/geral/mcp");
  await page.getByRole("switch", { name: "Usar o servidor arquivos" }).click();
  await page.getByRole("checkbox", { name: "Permitir arquivos.listar" }).check();
  await expect(
    page.getByRole("checkbox", { name: "Escrita de arquivos.mover bloqueada em Assistant público" }),
  ).toBeDisabled();
  await expect(page.getByText("1 de 4 tools permitidas")).toBeVisible();
  await page.getByRole("button", { name: "Salvar sobreposição" }).click();
  await expect(page.getByText(/Sobreposto por ana em/)).toBeVisible();
  const view = (await adminGet(request, "/assistants/geral")) as View;
  expect(view.effective.mcp.aliases).toEqual(["arquivos"]);
  expect(view.effective.mcp.allowed).toContain("arquivos.listar");
  expect(view.effective.mcp.allowed.filter((tool) => tool.startsWith("arquivos."))).toEqual(["arquivos.listar"]);
});

test("servidor indisponível mostra o motivo", async ({ page }) => {
  await login(page, "/assistentes/geral/mcp");
  await expect(page.getByText(/Credencial ausente: defina AI_CORE_MCP_SECRET_PLANILHAS na instalação\./)).toBeVisible();
});
