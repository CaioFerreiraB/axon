/** US9 (013, ADR-040): criar a chave de um sistema, vê-la uma vez, rotacionar e revogar com confirmação na linha — e
 * conferir pela própria plataforma que a chave antiga deixa de valer. */

import { expect, test, type APIRequestContext } from "@playwright/test";

import { login } from "./fixtures/session";

const stamp = Date.now().toString(36);

async function privateHealth(request: APIRequestContext, key: string): Promise<number> {
  const response = await request.get("http://127.0.0.1:8765/private/v1/health", {
    headers: { Authorization: `Bearer ${key}` },
  });
  return response.status();
}

test("cria, rotaciona e revoga a chave de um sistema", async ({ page, request }) => {
  const system = `rel${stamp}`;
  await login(page, "/acesso/chaves");
  await page.getByRole("button", { name: "Criar chave" }).click();
  await page.getByLabel("Nome do sistema").fill(system);
  await page.getByLabel("Rótulo (opcional)").fill("prod");
  await page.getByRole("button", { name: "Gerar chave" }).click();

  const created = page.getByRole("dialog", { name: `Chave criada para svc:${system}` });
  const first = await created.getByLabel("Chave de API").inputValue();
  expect(first).toMatch(/^axn_[0-9a-f]{16}_/);
  await expect(created.getByText(/não aparece de novo/)).toBeVisible();
  await created.getByRole("button", { name: "Concluir" }).click();
  await expect(created).toHaveCount(0);
  expect(await page.content()).not.toContain(first);
  expect(await privateHealth(request, first)).toBe(200);

  const keyId = first.split("_")[1] ?? "";
  const row = page.getByRole("row", { name: new RegExp(keyId) });
  await expect(row.getByText("Ativa")).toBeVisible();
  await row.getByRole("button", { name: `Rotacionar a chave ${keyId}` }).click();
  await page
    .getByRole("group", { name: `Confirmar a rotação de ${keyId}` })
    .getByRole("button", { name: "Rotacionar" })
    .click();
  const rotated = page.getByRole("dialog", { name: `Segredo novo para svc:${system}` });
  const second = await rotated.getByLabel("Chave de API").inputValue();
  expect(second).not.toBe(first);
  expect(second.split("_")[1]).toBe(keyId);
  await rotated.getByRole("button", { name: "Concluir" }).click();
  expect(await privateHealth(request, first)).toBe(401);
  expect(await privateHealth(request, second)).toBe(200);

  await row.getByRole("button", { name: `Revogar a chave ${keyId}` }).click();
  await page
    .getByRole("group", { name: `Confirmar a revogação de ${keyId}` })
    .getByRole("button", { name: "Revogar" })
    .click();
  await expect(page.getByRole("row", { name: new RegExp(keyId) }).getByText(/Revogada em/)).toBeVisible();
  expect(await privateHealth(request, second)).toBe(401);
  expect(await page.content()).not.toContain(second);
});

test("cria uma chave só para gerenciar usuários: a lista mostra o escopo e a chave não alcança o resto", async ({
  page,
  request,
}) => {
  const system = `prov${stamp}`;
  await login(page, "/acesso/chaves");
  await page.getByRole("button", { name: "Criar chave" }).click();
  await page.getByLabel("Nome do sistema").fill(system);
  await page.getByRole("checkbox", { name: "Gerenciar usuários e grupos" }).check();
  await page.getByRole("checkbox", { name: "Uso de inferência" }).uncheck();
  await page.getByRole("button", { name: "Gerar chave" }).click();

  const created = page.getByRole("dialog", { name: `Chave criada para svc:${system}` });
  await expect(created.getByText("Gerenciar usuários e grupos")).toBeVisible();
  const key = await created.getByLabel("Chave de API").inputValue();
  await created.getByRole("button", { name: "Concluir" }).click();
  const keyId = key.split("_")[1] ?? "";
  await expect(
    page.getByRole("row", { name: new RegExp(keyId) }).getByText("Gerenciar usuários e grupos"),
  ).toBeVisible();

  const as = { headers: { Authorization: `Bearer ${key}` } };
  expect((await request.get("http://127.0.0.1:8765/admin/v1/users", as)).status()).toBe(200);
  expect((await request.get("http://127.0.0.1:8765/admin/v1/keys", as)).status()).toBe(404);
});
