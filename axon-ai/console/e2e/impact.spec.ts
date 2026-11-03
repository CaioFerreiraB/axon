/** US11 (013; ADR-056): a página Meio ambiente sobre a plataforma de verdade, com o uso semeado estimado pelo
 * EcoLogits; agregação e período na URL; o casamento aproximado do GLM; a célula Emissões em Uso e custo. */

import { expect, test } from "@playwright/test";

import { expectAccessible, login } from "./fixtures/session";

test("faixas, cinco gráficos, tabela com o modelo do EcoLogits e o método", async ({ page }) => {
  await login(page, "/meio-ambiente");
  await expect(page.getByRole("heading", { name: "Meio ambiente" })).toBeVisible();
  await expect(page.getByRole("region", { name: "Impacto do período" }).getByText(/CO₂e/).first()).toBeVisible();
  for (const name of ["Emissões", "Energia", "Água", "Energia primária (PE)", "Recursos abióticos (ADPe)"]) {
    await expect(
      page.getByRole("img", { name: new RegExp(`^${name.replace(/[()]/g, "\\$&")} por dia`) }),
    ).toBeVisible();
  }
  const table = page.getByRole("table", { name: "Impacto por modelo no período" });
  await expect(table.getByRole("row", { name: /openai\/gpt-4\.1-mini/ }).first()).toBeVisible();
  await expect(page.getByText(/Estimativas do EcoLogits \d+\.\d+\.\d+/)).toBeVisible();
  await expectAccessible(page, "meio ambiente");
});

test("agregação e período ficam na URL", async ({ page }) => {
  await login(page, "/meio-ambiente");
  await page.getByRole("radio", { name: "Semana" }).click();
  await expect(page).toHaveURL(/agregacao=semana/);
  await expect(page.getByRole("img", { name: /Emissões por semana/ })).toBeVisible();
  await page.getByRole("radio", { name: "90 dias" }).click();
  await expect(page).toHaveURL(/periodo=90/);
  await page.getByRole("radio", { name: "Personalizado" }).click();
  const form = page.getByRole("form", { name: "Período personalizado" });
  await expect(form.getByLabel("De")).toBeVisible();
  await form.getByRole("button", { name: "Cancelar" }).click();
  await expect(form).toHaveCount(0);
});

test("Uso e custo leva a Meio ambiente pela célula Emissões", async ({ page }) => {
  await login(page, "/uso");
  const strip = page.getByRole("region", { name: "Totais do período" });
  await expect(strip.getByText("Emissões")).toBeVisible();
  await strip.getByRole("link", { name: /Meio ambiente/ }).click();
  await expect(page).toHaveURL(/\/meio-ambiente\?periodo=personalizado&de=\d{4}-\d{2}-\d{2}&ate=/);
  await expect(page.getByRole("heading", { name: "Meio ambiente" })).toBeVisible();
});
