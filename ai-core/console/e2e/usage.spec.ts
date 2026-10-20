/** US4 (013): 7/30/90 dias, por modelo e por Assistant, no fuso da API; "sem preço" e total incompleto; preço novo no
 * passado recalcula o custo; 90 dias pronto em menos de 2 s (SC-004). ADR-036: custo parcial do OpenRouter sem
 * cadastro de preço, e o gráfico em custo, requisições ou tokens. */

import { expect, test } from "@playwright/test";

import { login } from "./fixtures/session";

test("período e agrupamento ficam na URL; 90 dias abre em menos de 2 s", async ({ page }) => {
  await login(page, "/uso");
  await expect(page.getByText(/fuso America\/Sao_Paulo/)).toBeVisible();
  await page.getByRole("radio", { name: "7 dias" }).click();
  await expect(page).toHaveURL(/dias=7/);
  const started = Date.now();
  await page.getByRole("radio", { name: "90 dias" }).click();
  await expect(page.getByRole("table", { name: "Uso por modelo no período" })).toBeVisible();
  await expect(page.getByText(/^\d{2}\/\d{2} a \d{2}\/\d{2} · fuso/)).toBeVisible();
  expect(Date.now() - started).toBeLessThan(2_000);
  await page.getByRole("radio", { name: "Por Assistant" }).click();
  await expect(page.getByRole("table", { name: "Uso por Assistant no período" })).toBeVisible();
});

test("modelo sem preço marca o total como incompleto; preço no passado recalcula", async ({ page }) => {
  await login(page, "/uso");
  await expect(page.getByRole("link", { name: /Incompleto: \d+ modelos? sem preço/ })).toBeVisible();
  const qwen = page.getByRole("row", { name: /ollama\/qwen3:1\.7b/ });
  await expect(qwen.getByText("Sem preço")).toBeVisible();
  await qwen.getByRole("link", { name: "Cadastrar" }).click();
  await expect(page).toHaveURL(/\/uso\/precos\?modelo=/);
  await page.getByLabel("Entrada (US$ / 1 M)").fill("0");
  await page.getByLabel("Saída (US$ / 1 M)").fill("0");
  await page.getByLabel("Vigente desde").fill("2025-01-01");
  await page.getByRole("button", { name: "Salvar preço" }).click();
  await expect(page.getByRole("row", { name: /ollama\/qwen3:1\.7b.*Vigente/ })).toBeVisible();
  await page.getByRole("link", { name: "Uso e custo" }).first().click();
  await expect(page.getByRole("heading", { name: "Uso e custo" })).toBeVisible();
  await expect(page.getByRole("row", { name: /ollama\/qwen3:1\.7b/ }).getByText("Sem preço")).toHaveCount(0);
});

test("sem uso no período: o estado vazio explica de onde vêm os dados", async ({ page }) => {
  await login(page, "/uso?origem=evaluation");
  await expect(page.getByText("Nenhuma chamada de modelo neste período")).toBeVisible();
  await expect(page.getByText("O uso aparece aqui assim que a primeira conversa acontecer.")).toBeVisible();
});

test("custo parcial do OpenRouter sem cadastro de preço", async ({ page }) => {
  await login(page, "/uso");
  const glm = page.getByRole("row", { name: /openrouter\/z-ai\/glm-5\.3-flash/ });
  await expect(glm.getByText("Parcial")).toBeVisible();
  await expect(glm.getByText("informado pelo provedor")).toBeVisible();
  await expect(glm.getByRole("link", { name: "Cadastrar" })).toHaveCount(0);
  // A sessão do provedor ainda vale: a nova carga volta do login sem formulário.
  await page.goto("/uso/precos?modelo=openrouter/z-ai/glm-5.3-flash");
  await expect(page.getByText("openrouter informa o custo de cada chamada")).toBeVisible();
  await expect(page.getByRole("combobox", { name: "Provedor" })).toHaveCount(0);
});

test("o gráfico alterna entre custo, requisições e tokens, e a métrica fica na URL", async ({ page }) => {
  await login(page, "/uso");
  await expect(page.getByRole("img", { name: /Custo por dia/ })).toBeVisible();
  await page.getByRole("radio", { name: "Requisições" }).click();
  await expect(page).toHaveURL(/metrica=requisicoes/);
  await expect(page.getByRole("heading", { name: "Requisições por dia" })).toBeVisible();
  await expect(page.getByText("uma requisição pode usar mais de um modelo")).toBeVisible();
  await page.getByRole("radio", { name: "Por Assistant" }).click();
  await expect(page.getByRole("img", { name: "Requisições distintas por dia, por Assistant" })).toBeVisible();
  await page.getByRole("radio", { name: "Tokens" }).click();
  await page.getByRole("radio", { name: "Entrada" }).click();
  await expect(page).toHaveURL(/metrica=tokens.*tokens=entrada|tokens=entrada.*metrica=tokens/);
  await expect(page.getByRole("img", { name: "Tokens de entrada por dia, por Assistant" })).toBeVisible();
  await page.getByRole("radio", { name: "Custo" }).click();
  await expect(page).not.toHaveURL(/tokens=/);
});
