/** 013 US13 (FR-046 a FR-050, SC-013): a console no celular — barra inferior e "Mais", nenhuma tela rolando de lado,
 * tabelas em lista, diálogo como folha e alvos de toque. Roda nos projetos `celular` (Pixel 7). */

import { expect, test, type Page } from "@playwright/test";

import { login } from "./fixtures/session";

const SCREENS = [
  "/uso",
  "/uso/precos",
  "/meio-ambiente",
  "/meio-ambiente?agregacao=semana&periodo=90",
  "/assistentes",
  "/assistentes/geral/modelos",
  "/assistentes/geral/mcp",
  "/assistentes/geral/permissoes",
  "/assistentes/geral/historico",
  "/servidores-mcp",
  "/observabilidade",
  "/acesso/usuarios",
  "/acesso/grupos",
  "/acesso/login",
  "/acesso/chaves",
];

/** O que passa da borda direita da tela, fora do que é fixo ou está dentro de um contêiner que rola de lado. */
async function overflow(page: Page) {
  return page.evaluate(() => {
    const width = document.documentElement.clientWidth;
    return {
      page: document.documentElement.scrollWidth - width,
      offenders: Array.from(document.querySelectorAll<HTMLElement>("body *"))
        .filter((element) => {
          const box = element.getBoundingClientRect();
          if (box.width === 0 || box.right <= width + 1 || element.closest(".visually-hidden")) {
            return false;
          }
          for (let parent = element.parentElement; parent; parent = parent.parentElement) {
            const style = getComputedStyle(parent);
            if (style.overflowX === "auto" || style.overflowX === "hidden" || style.overflowX === "scroll") {
              return false;
            }
          }
          return getComputedStyle(element).position !== "fixed";
        })
        .slice(0, 3)
        .map((element) => `${element.tagName.toLowerCase()}.${String(element.className).slice(0, 40)}`),
    };
  });
}

test("nenhuma tela rola de lado", async ({ page }) => {
  await login(page, "/uso");
  for (const path of SCREENS) {
    await page.goto(path);
    await page.waitForLoadState("networkidle");
    const found = await overflow(page);
    expect(found.page, `${path}: a página rola de lado (${found.offenders.join(", ")})`).toBeLessThanOrEqual(0);
  }
});

test("barra inferior, Mais e cabeçalho de app no lugar da barra lateral", async ({ page }) => {
  await login(page, "/uso");
  await expect(page.getByRole("complementary", { name: "Navegação da console" })).toBeHidden();
  const nav = page.getByRole("navigation", { name: "Seções" });
  await expect(nav).toBeVisible();
  await expect(nav.getByRole("link", { name: "Uso" })).toHaveAttribute("aria-current", "page");
  const box = await nav.boundingBox();
  const viewport = page.viewportSize();
  expect(box && viewport && Math.round(box.y + box.height)).toBe(viewport?.height);

  for (const target of await nav.getByRole("link").all()) {
    expect((await target.boundingBox())?.height ?? 0).toBeGreaterThanOrEqual(44);
  }

  await nav.getByRole("button", { name: "Mais" }).click();
  const sheet = page.getByRole("dialog", { name: "Mais" });
  await expect(sheet).toBeVisible();
  await sheet.getByRole("link", { name: "Meio ambiente" }).click();
  await expect(page).toHaveURL(/\/meio-ambiente$/);
  await expect(sheet).toHaveCount(0);
  await expect(nav.getByRole("button", { name: "Mais" })).toHaveAttribute("data-active", "true");

  await nav.getByRole("link", { name: "Assistentes" }).click();
  await page.getByRole("link", { name: "geral", exact: true }).click();
  const back = page.getByRole("link", { name: "Voltar para Assistentes" });
  await expect(back).toBeVisible();
  await back.click();
  await expect(page).toHaveURL(/\/assistentes$/);
});

test("a tabela vira lista de linhas, com o rótulo de cada valor", async ({ page }) => {
  await login(page, "/acesso/usuarios");
  const row = page.getByRole("row").filter({ hasText: "Ana Souza" });
  await expect(row).toBeVisible();
  // O cabeçalho fica só para o leitor de tela: recortado a 1px.
  const head = page.locator("thead").first();
  expect((await head.evaluate((element) => element.getBoundingClientRect().height)) <= 1).toBe(true);
  await expect(page.getByRole("columnheader", { name: "Grupos" })).toHaveCount(1);
  const groups = row.locator('[data-label="Grupos"]');
  await expect(groups).toBeVisible();
  const label = await groups.evaluate((cell) => getComputedStyle(cell, "::before").content);
  expect(label).toBe('"Grupos"');
});

test("o diálogo abre como folha ancorada embaixo, com o primário por cima", async ({ page }) => {
  await login(page, "/acesso/usuarios");
  await page.getByRole("button", { name: "Cadastrar pessoa" }).click();
  const dialog = page.getByRole("dialog", { name: "Cadastrar pessoa" });
  await expect(dialog).toBeVisible();
  const viewport = page.viewportSize();
  // Depois da animação de subida, a folha encosta embaixo e ocupa a largura.
  await expect
    .poll(async () => {
      const box = await dialog.boundingBox();
      return box ? [Math.round(box.y + box.height), Math.round(box.width)] : null;
    })
    .toEqual([viewport?.height, viewport?.width]);
  const primary = await dialog.getByRole("button", { name: "Cadastrar", exact: true }).boundingBox();
  const cancel = await dialog.getByRole("button", { name: "Cancelar" }).boundingBox();
  expect(primary && cancel && primary.y < cancel.y).toBe(true);
  expect(primary?.height ?? 0).toBeGreaterThanOrEqual(44);
  expect(await dialog.getByLabel("Nome").evaluate((input) => getComputedStyle(input).fontSize)).toBe("16px");
});
