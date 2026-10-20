/** T026 — uso e custo: custo como figura principal, "Incompleto" com atalho, gráfico com descrição e tabela
 * equivalente, estado vazio que explica de onde vêm os dados. */

import { screen } from "@testing-library/react";
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
