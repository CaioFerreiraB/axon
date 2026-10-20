/** Formulário de preço: o provedor numa lista e o modelo sem o prefixo; o OpenRouter avisa que informa o custo de cada
 * chamada (ADR-035). */

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import PricesPage from "../../src/features/usage/PricesPage";
import * as f from "../msw/fixtures";
import { server } from "../msw/server";
import { renderAt } from "../render";

const routes = [{ path: "/uso/precos", element: <PricesPage /> }];

describe("Tabela de preços", () => {
  it("cadastra com o provedor da lista e o modelo sem o prefixo", async () => {
    let body: unknown = null;
    server.use(
      http.get("*/admin/v1/prices/unpriced", () => HttpResponse.json({ data: [] })),
      http.post("*/admin/v1/prices", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(f.prices[0], { status: 201 });
      }),
    );
    renderAt("/uso/precos", routes);
    await userEvent.click(await screen.findByRole("button", { name: "Novo preço" }));
    const provider = screen.getByRole("combobox", { name: "Provedor" });
    await waitFor(() => expect(provider).toHaveValue("openrouter"));
    expect(
      within(provider)
        .getAllByRole("option")
        .map((option) => option.textContent),
    ).toEqual(["openrouter", "ollama · indisponível", "openai · indisponível"]);
    expect(screen.getByText(/O OpenRouter informa o custo de cada chamada/)).toBeInTheDocument();
    await userEvent.type(screen.getByRole("textbox", { name: "Modelo" }), "openai/gpt-4.1");
    await userEvent.type(screen.getByRole("textbox", { name: "Entrada (US$ / 1 M)" }), "2");
    await userEvent.type(screen.getByRole("textbox", { name: "Saída (US$ / 1 M)" }), "8");
    await userEvent.type(screen.getByLabelText("Vigente desde"), "2026-10-01");
    await userEvent.click(screen.getByRole("button", { name: "Salvar preço" }));
    await waitFor(() =>
      expect(body).toEqual({
        provider: "openrouter",
        model: "openai/gpt-4.1",
        input: "2",
        output: "8",
        effective_from: "2026-10-01",
      }),
    );
  });

  it("o modelo usado sem preço chega dividido em provedor e modelo, sem o aviso do OpenRouter", async () => {
    renderAt("/uso/precos?modelo=ollama/qwen3:1.7b", routes);
    const provider = await screen.findByRole("combobox", { name: "Provedor" });
    expect(provider).toHaveValue("ollama");
    expect(screen.getByRole("textbox", { name: "Modelo" })).toHaveValue("qwen3:1.7b");
    expect(screen.queryByText(/O OpenRouter informa o custo/)).not.toBeInTheDocument();
  });

  it("modelo vazio é recusado antes da API", async () => {
    server.use(http.get("*/admin/v1/prices/unpriced", () => HttpResponse.json({ data: [] })));
    renderAt("/uso/precos", routes);
    await userEvent.click(await screen.findByRole("button", { name: "Novo preço" }));
    await userEvent.click(screen.getByRole("button", { name: "Salvar preço" }));
    expect(await screen.findByText("Informe o modelo, como openai/gpt-4.1-mini.")).toBeInTheDocument();
  });
});
