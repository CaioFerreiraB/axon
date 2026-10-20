/** T024 — aba MCP: ligar servidor e marcar tool; escrita bloqueada em Assistant público; servidor indisponível com o
 * motivo. */

import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import AssistantDetail from "../../src/features/assistants/AssistantDetail";
import McpTab from "../../src/features/assistants/McpTab";
import * as f from "../msw/fixtures";
import { server } from "../msw/server";
import { renderAt } from "../render";

const routes = [
  { path: "/assistentes/:nome", element: <AssistantDetail />, children: [{ path: "mcp", element: <McpTab /> }] },
];

describe("aba MCP", () => {
  it("liga um servidor, marca uma tool e salva com o namespace", async () => {
    let body: unknown = null;
    server.use(
      http.put("*/admin/v1/assistants/geral/mcp", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(f.geral);
      }),
    );
    renderAt("/assistentes/geral/mcp", routes);
    await userEvent.click(await screen.findByRole("switch", { name: "Usar o servidor arquivos" }));
    await userEvent.click(await screen.findByRole("checkbox", { name: "Permitir arquivos.listar" }));
    await userEvent.click(screen.getByRole("button", { name: "Salvar sobreposição" }));
    await waitFor(() =>
      expect(body).toEqual({ aliases: ["arquivos"], allowed: ["arquivos.listar"], write: [], version: null }),
    );
  });

  it("em Assistant público a escrita fica bloqueada, com a explicação", async () => {
    renderAt("/assistentes/geral/mcp", routes);
    expect(await screen.findByText("Assistant público: tools de escrita não podem ser marcadas")).toBeInTheDocument();
    await userEvent.click(await screen.findByRole("switch", { name: "Usar o servidor arquivos" }));
    expect(
      await screen.findByRole("checkbox", { name: "Escrita de arquivos.mover bloqueada em Assistant público" }),
    ).toBeDisabled();
  });

  it("servidor indisponível por falta de credencial diz o que a instalação define", async () => {
    renderAt("/assistentes/geral/mcp", routes);
    expect(
      await screen.findByText(/Credencial ausente: defina AI_CORE_MCP_SECRET_PLANILHAS na instalação\./),
    ).toBeInTheDocument();
  });
});
