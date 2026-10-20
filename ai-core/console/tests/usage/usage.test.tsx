/** T026 — uso e custo: custo como figura principal, "Incompleto" com atalho, gráfico com descrição e tabela
 * equivalente, estado vazio que explica de onde vêm os dados. ADR-036: custo parcial visível, OpenRouter sem
 * "Cadastrar" e o gráfico em custo, requisições ou tokens. */

import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import UsagePage from "../../src/features/usage/UsagePage";
import * as f from "../msw/fixtures";
import { server } from "../msw/server";
import { renderAt } from "../render";

describe("Uso e custo", () => {
  it("mostra os totais, o fuso da API e o aviso de incompleto", async () => {
    renderAt("/uso", [{ path: "/uso", element: <UsagePage /> }]);
    expect(await screen.findByText(/fuso America\/Sao_Paulo/)).toBeInTheDocument();
    expect(screen.getAllByText(/US\$\s33,52/).length).toBeGreaterThan(0);
    expect(screen.getByRole("link", { name: /Incompleto: 1 modelo sem preço/ })).toHaveAttribute("href", "/uso/precos");
    expect(screen.getByRole("img", { name: /Custo por dia/ })).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Uso por modelo no período" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Cadastrar" })).toHaveAttribute(
      "href",
      "/uso/precos?modelo=ollama%2Fqwen3%3A1.7b",
    );
  });

  it("custo parcial aparece na tabela e no gráfico, sem cadastro de preço para o OpenRouter", async () => {
    renderAt("/uso", [{ path: "/uso", element: <UsagePage /> }]);
    const table = await screen.findByRole("table", { name: "Uso por modelo no período" });
    const glm = within(table).getByRole("row", { name: /glm-5\.3-flash/ });
    expect(within(glm).getByText("Parcial")).toBeInTheDocument();
    expect(within(glm).getByText(/US\$\s0,01/)).toBeInTheDocument();
    expect(within(glm).getByText("informado pelo provedor")).toBeInTheDocument();
    expect(within(glm).queryByRole("link", { name: "Cadastrar" })).not.toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Cadastrar" })).toHaveLength(1);
    expect(screen.getByText(/glm-5\.3-flash/, { selector: "li span" })).toBeInTheDocument();
    const chart = screen.getByRole("table", { name: /Custo por dia em US\$, por modelo/ });
    expect(within(chart).getByRole("columnheader", { name: "openrouter/z-ai/glm-5.3-flash" })).toBeInTheDocument();
  });

  it("só modelos do OpenRouter sem custo: parcial, sem atalho para preços", async () => {
    const glm = f.report.totals[2];
    server.use(
      http.get("*/admin/v1/usage", () =>
        HttpResponse.json({ ...f.report, totals: [f.report.totals[0], { ...glm, cost: null }] }),
      ),
    );
    renderAt("/uso", [{ path: "/uso", element: <UsagePage /> }]);
    expect(await screen.findByText("Parcial: há chamadas sem custo informado")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: /Incompleto/ })).not.toBeInTheDocument();
    expect(screen.getByText("Não informado")).toBeInTheDocument();
    expect(screen.queryByRole("link", { name: "Cadastrar" })).not.toBeInTheDocument();
  });

  it("alterna o gráfico entre custo, requisições e tokens", async () => {
    renderAt("/uso", [{ path: "/uso", element: <UsagePage /> }]);
    await screen.findByRole("img", { name: /Custo por dia/ });
    const metric = screen.getByRole("radiogroup", { name: "Métrica do gráfico" });

    await userEvent.click(within(metric).getByRole("radio", { name: "Requisições" }));
    // Por modelo, uma barra com as requisições distintas: 6 no dia 11, não 5 + 4.
    const requests = await screen.findByRole("table", { name: "Requisições distintas por dia" });
    expect(within(requests).getByRole("columnheader", { name: "Requisições distintas" })).toBeInTheDocument();
    expect(within(requests).getByRole("row", { name: "dom, 11/10 6 6" })).toBeInTheDocument();
    expect(screen.getByText("uma requisição pode usar mais de um modelo")).toBeInTheDocument();

    await userEvent.click(within(metric).getByRole("radio", { name: "Tokens" }));
    await userEvent.click(
      within(screen.getByRole("radiogroup", { name: "Tokens" })).getByRole("radio", { name: "Saída" }),
    );
    const tokens = await screen.findByRole("table", { name: "Tokens de saída por dia, por modelo" });
    expect(within(tokens).getByRole("row", { name: /11\/10 .*1,5 mil$/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Tokens por dia" })).toBeInTheDocument();
  });

  it("sem uso, o estado vazio explica de onde vêm os dados", async () => {
    server.use(http.get("*/admin/v1/usage", () => HttpResponse.json(f.emptyReport)));
    renderAt("/uso", [{ path: "/uso", element: <UsagePage /> }]);
    expect(await screen.findByText("Nenhuma chamada de modelo neste período")).toBeInTheDocument();
    expect(screen.getByText("Sem chamadas no período")).toBeInTheDocument();
    expect(screen.queryByRole("table", { name: "Uso por modelo no período" })).not.toBeInTheDocument();
  });

  it("erro da API com nova tentativa", async () => {
    server.use(
      http.get("*/admin/v1/usage", () =>
        HttpResponse.json(
          { error: { message: "armazenamento indisponível", type: "x", code: "storage_unavailable" } },
          { status: 503 },
        ),
      ),
    );
    renderAt("/uso", [{ path: "/uso", element: <UsagePage /> }]);
    expect(await screen.findByText("Não foi possível carregar o uso", {}, { timeout: 4000 })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Tentar de novo/ })).toBeInTheDocument();
  });
});
