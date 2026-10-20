/** Formulário de preço: o provedor numa lista e o modelo sem o prefixo; o OpenRouter, que informa o custo de cada
 * chamada, fica fora (ADR-036). */

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
  it("cadastra com o provedor da lista e o modelo sem o prefixo, sem o OpenRouter", async () => {
    let body: unknown = null;
    const ready = f.providers.map((p) => (p.name === "openai" ? { ...p, ready: true, detail: null } : p));
    server.use(
      http.get("*/admin/v1/providers", () => HttpResponse.json({ data: ready })),
      http.get("*/admin/v1/prices/unpriced", () => HttpResponse.json({ data: [] })),
      http.post("*/admin/v1/prices", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(f.prices[0], { status: 201 });
      }),
    );
    renderAt("/uso/precos", routes);
    await userEvent.click(await screen.findByRole("button", { name: "Novo preço" }));
    const provider = screen.getByRole("combobox", { name: "Provedor" });
    await waitFor(() => expect(provider).toHaveValue("openai"));
    expect(
      within(provider)
        .getAllByRole("option")
        .map((option) => option.textContent),
    ).toEqual(["openai", "ollama · indisponível"]);
    await userEvent.type(screen.getByRole("textbox", { name: "Modelo" }), "openai/gpt-4.1");
    await userEvent.type(screen.getByRole("textbox", { name: "Entrada (US$ / 1 M)" }), "2");
    await userEvent.type(screen.getByRole("textbox", { name: "Saída (US$ / 1 M)" }), "8");
    await userEvent.type(screen.getByLabelText("Vigente desde"), "2026-10-01");
    await userEvent.click(screen.getByRole("button", { name: "Salvar preço" }));
    await waitFor(() =>
      expect(body).toEqual({
        provider: "openai",
        model: "openai/gpt-4.1",
        input: "2",
        output: "8",
        effective_from: "2026-10-01",
      }),
    );
  });

  it("o modelo usado sem preço chega dividido em provedor e modelo", async () => {
    renderAt("/uso/precos?modelo=ollama/qwen3:1.7b", routes);
    const provider = await screen.findByRole("combobox", { name: "Provedor" });
    expect(provider).toHaveValue("ollama");
    expect(screen.getByRole("textbox", { name: "Modelo" })).toHaveValue("qwen3:1.7b");
  });

  it("modelo do OpenRouter não tem preço a cadastrar", async () => {
    server.use(
      http.get("*/admin/v1/prices/unpriced", () =>
        HttpResponse.json({ data: ["ollama/qwen3:1.7b", "openrouter/z-ai/glm-5.3-flash"] }),
      ),
    );
    renderAt("/uso/precos?modelo=openrouter/z-ai/glm-5.3-flash", routes);
    expect(await screen.findByText("openrouter informa o custo de cada chamada")).toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: "Provedor" })).not.toBeInTheDocument();
    expect(screen.queryByRole("rowheader", { name: "openrouter/z-ai/glm-5.3-flash" })).not.toBeInTheDocument();
    expect(await screen.findByRole("rowheader", { name: "ollama/qwen3:1.7b" })).toBeInTheDocument();
  });

  it("modelo vazio é recusado antes da API", async () => {
    server.use(http.get("*/admin/v1/prices/unpriced", () => HttpResponse.json({ data: [] })));
    renderAt("/uso/precos", routes);
    await userEvent.click(await screen.findByRole("button", { name: "Novo preço" }));
    await userEvent.click(screen.getByRole("button", { name: "Salvar preço" }));
    expect(await screen.findByText("Informe o modelo, como openai/gpt-4.1-mini.")).toBeInTheDocument();
  });
});
