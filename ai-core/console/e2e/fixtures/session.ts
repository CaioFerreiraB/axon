/** Entrar pelo formulário da 012 (o mesmo que o Open WebUI usa) e as credenciais semeadas pelo `serve_platform.py`. */

import AxeBuilder from "@axe-core/playwright";
import { expect, type APIRequestContext, type Page } from "@playwright/test";

export const ADMIN = { username: "ana", password: "senha-da-ana-no-e2e", email: "ana@exemplo.org" };
export const OUTSIDER = { username: "bia", password: "senha-da-bia-no-e2e", email: "bia@exemplo.org" };
/** A chave de teste do perfil `test` (`ai_core.bootstrap.profiles.TEST_API_KEY`), do grupo de administração. */
export const TEST_API_KEY = "aic_7e57c0de00000001_chave-de-teste";

export async function login(page: Page, path = "/uso", who: { username: string; password: string } = ADMIN) {
  await page.goto(path);
  await page.waitForURL((url) => url.pathname.startsWith("/oauth2/"));
  await page.getByLabel("Usuário ou e-mail").fill(who.username);
  await page.getByLabel("Senha").fill(who.password);
  await page.getByRole("button", { name: "Entrar", exact: true }).click();
  await page.waitForURL((url) => !url.pathname.startsWith("/oauth2/") && url.pathname !== "/callback");
}

/** WCAG 2.2 AA pelo axe (013 SC-005). */
export async function expectAccessible(page: Page, label: string) {
  // O @axe-core/playwright tipa o Page da versão dele do playwright-core; o objeto é o mesmo.
  const result = await new AxeBuilder({ page: page as unknown as ConstructorParameters<typeof AxeBuilder>[0]["page"] })
    .withTags(["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"])
    .analyze();
  const problems = result.violations.map(
    (v) => `${v.id} (${v.impact}): ${v.nodes.map((n) => n.target.join(" ")).join(" | ")}`,
  );
  expect(problems, `${label}: violações do axe`).toEqual([]);
}

/** A API de administração com a chave de teste — para conferir que a ação da tela chegou à plataforma (SC-002). */
export async function adminGet(request: APIRequestContext, path: string): Promise<unknown> {
  const response = await request.get(`http://127.0.0.1:8765/admin/v1${path}`, {
    headers: { Authorization: `Bearer ${TEST_API_KEY}` },
  });
  expect(response.ok(), `${path}: ${response.status()}`).toBe(true);
  return response.json();
}
