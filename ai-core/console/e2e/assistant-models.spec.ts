/** US2 (013): trocar o modelo de geração, testar, salvar — a conversa seguinte usa o novo (SC-001); recusa da API
 * junto ao papel; travado; inativa; descarte confirmado. */

import { expect, test } from "@playwright/test";

import { adminGet, login, TEST_API_KEY } from "./fixtures/session";

test.describe.configure({ mode: "serial" });

type Usage = { totals: { key: string | null; calls: number }[] };

test("troca o modelo de geração e a conversa seguinte já usa o novo (SC-001)", async ({ page, request }) => {
  await login(page, "/assistentes/geral/modelos");
  await page.getByRole("combobox", { name: "Provedor de generation" }).selectOption("ollama");
  const generation = page.getByRole("combobox", { name: "Modelo de generation" });
  await generation.fill("gemma3:1b");
  await page.getByRole("button", { name: "Testar o modelo de generation" }).click();
  await expect(page.getByText(/Disponível · respondeu em \d+ ms/)).toBeVisible();
  await page.getByRole("button", { name: "Salvar sobreposição" }).click();
  await expect(page.getByText(/Sobreposto por ana em/)).toBeVisible();
  await expect(page.getByTitle("ollama/gemma3:1b")).toBeVisible();

  const chat = await request.post("http://127.0.0.1:8765/private/v1/chat/completions", {
    headers: { Authorization: `Bearer ${TEST_API_KEY}` },
    data: { model: "geral", messages: [{ role: "user", content: "qual é a capital?" }] },
  });
  expect(chat.status()).toBe(200);
  await expect
    .poll(
      async () =>
        ((await adminGet(request, "/usage")) as Usage).totals.find((row) => row.key === "ollama/gemma3:1b")?.calls ?? 0,
      {
        timeout: 10_000,
      },
    )
    .toBeGreaterThan(0);
});

test("modelo fora da allowlist: a recusa da API aparece junto ao papel", async ({ page }) => {
  await login(page, "/assistentes/geral/modelos");
  await page.getByRole("combobox", { name: "Provedor de generation" }).selectOption("openai");
  const generation = page.getByRole("combobox", { name: "Modelo de generation" });
  await generation.fill("gpt-4.1");
  await page.getByRole("button", { name: "Salvar sobreposição" }).click();
  await expect(page.getByRole("alert").filter({ hasText: "allowlist" })).toBeVisible();
  await expect(generation).toHaveAttribute("aria-invalid", "true");
});

test("sem models em overrides: a seção fica travada", async ({ page }) => {
  await login(page, "/assistentes/rascunho/modelos");
  await expect(page.getByText("Os modelos deste Assistant só mudam por novo deploy")).toBeVisible();
  await expect(page.getByRole("combobox")).toHaveCount(0);
  await expect(page.getByText("O flow chat não usa controller")).toBeVisible();
});

test("sobreposição que o deploy desativou: inativa, com o motivo, e o YAML vale", async ({ page }) => {
  await login(page, "/assistentes/documentos/modelos");
  await expect(page.getByText("Sobreposição inativa: o deploy mudou esta seção")).toBeVisible();
  await expect(page.getByText(/Guardada: generation = ollama\/gemma3:1b/)).toBeVisible();
  await expect(page.getByText("Do YAML")).toBeVisible();
});

test("descartar pede confirmação na própria tela e volta ao YAML", async ({ page }) => {
  await login(page, "/assistentes/geral/modelos");
  await page.getByRole("button", { name: "Descartar sobreposição" }).click();
  const confirm = page.getByRole("group", { name: "Confirmar o descarte" });
  await confirm.getByRole("button", { name: "Descartar" }).click();
  await expect(page.getByText("Sem sobreposição de modelos: vale o YAML")).toBeVisible();
  await page.getByRole("link", { name: "Histórico" }).click();
  await expect(page.getByText("Descartada").first()).toBeVisible();
});
