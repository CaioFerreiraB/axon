/** US10 (013, ADR-040): dar acesso a um sistema pela aba "Permissões" e ver o efetivo; sem `auth` em `overrides`, a
 * aba fica travada. */

import { expect, test } from "@playwright/test";

import { adminGet, login } from "./fixtures/session";

test("liga a chave de API, adiciona um sistema e salva", async ({ page, request }) => {
  await login(page, "/assistentes/relatorios/permissoes");
  await page.getByRole("switch", { name: "Chave de API" }).click();
  await page.getByLabel("Adicionar sistema, grupo ou pessoa").fill("svc:relatorios-e2e");
  await page.getByRole("button", { name: "Adicionar" }).click();
  const list = page.getByRole("list", { name: "Quem pode usar" });
  await expect(list.getByText("svc:relatorios-e2e")).toBeVisible();
  await expect(list.getByRole("listitem").filter({ hasText: "svc:relatorios-e2e" })).toContainText(
    "Sem correspondência",
  );
  await page.getByRole("button", { name: "Salvar sobreposição" }).click();
  await expect(page.getByText(/Sobreposto por/)).toBeVisible();

  const view = (await adminGet(request, "/assistants/relatorios")) as {
    effective: { auth: { schemes: string[]; allow: string[] } };
  };
  expect(view.effective.auth).toEqual({ schemes: ["api_key", "oidc"], allow: ["group:equipe", "svc:relatorios-e2e"] });

  await page.getByRole("button", { name: "Descartar sobreposição" }).click();
  await page.getByRole("group", { name: "Confirmar o descarte" }).getByRole("button", { name: "Descartar" }).click();
  await expect(page.getByText("Sem sobreposição de permissões: vale o YAML")).toBeVisible();
});

test("num privado, qualquer pessoa autenticada não é oferecida; sem auth liberado, a aba é só leitura", async ({
  page,
}) => {
  await login(page, "/assistentes/interno/permissoes");
  await expect(page.getByText(/Assistant privado:/)).toBeVisible();
  await expect(page.getByRole("checkbox", { name: /Qualquer pessoa autenticada/ })).toHaveCount(0);

  await page.goto("/assistentes/rascunho/permissoes");
  await expect(page.getByText("As permissões deste Assistant só mudam por novo deploy")).toBeVisible();
  await expect(page.getByRole("switch", { name: "Login" })).toBeDisabled();
});
