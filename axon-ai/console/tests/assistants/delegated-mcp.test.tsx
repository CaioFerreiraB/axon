import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import type { McpServer } from "../../src/api/schemas";
import AssistantDetail from "../../src/features/assistants/AssistantDetail";
import McpTab from "../../src/features/assistants/McpTab";
import McpServersPage from "../../src/features/mcp/McpServersPage";
import * as f from "../msw/fixtures";
import { server } from "../msw/server";
import { renderAt } from "../render";

const baseServer = f.servers[0];
if (!baseServer) throw new Error("Fixture MCP ausente");
const delegated: McpServer = {
  ...baseServer,
  alias: "delegado",
  origin: "file",
  user_access: false,
  auth: { type: "delegated", credential: null },
};
const routes = [{ path: "/servidores-mcp", element: <McpServersPage /> }];
function respond(entry = delegated) {
  const probe = vi.fn(() =>
    HttpResponse.json({ alias: "delegado", ok: false, detail: "autorização delegada ausente", tools: [], missing: [] }),
  );
  server.use(
    http.get("*/admin/v1/mcp", () => HttpResponse.json({ data: [...f.servers, entry] })),
    http.get("*/admin/v1/mcp/delegado/health", probe),
  );
  return probe;
}

describe("MCP delegado na console", () => {
  it("carrega lista mista e explica a autorização nos detalhes sem sondagem sem credencial", async () => {
    const probe = respond();
    renderAt("/servidores-mcp", routes);
    const row = await screen.findByRole("row", { name: /delegado/ });
    expect(within(row).getByText("Por execução")).toBeInTheDocument();
    await userEvent.click(within(row).getByRole("button", { name: "Ver delegado, somente leitura" }));
    expect(screen.getByText("Delegada por execução; sem credencial estática")).toBeInTheDocument();
    expect(probe).not.toHaveBeenCalled();
  });

  it("preserva delegação ao editar descrição de um registro da API", async () => {
    respond({ ...delegated, origin: "registry" });
    let body: unknown;
    server.use(
      http.put("*/admin/v1/mcp/delegado", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ ...delegated, origin: "registry" });
      }),
    );
    renderAt("/servidores-mcp", routes);
    await userEvent.click(await screen.findByRole("button", { name: "Ações de delegado" }));
    await userEvent.click(screen.getByRole("button", { name: "Editar" }));
    expect(screen.queryByLabelText("Credencial (referência)")).not.toBeInTheDocument();
    await userEvent.type(screen.getByLabelText("Descrição"), " atualizada");
    await userEvent.click(screen.getByRole("button", { name: "Salvar servidor" }));
    await waitFor(() => expect(body).toMatchObject({ auth: { type: "delegated" } }));
    expect(JSON.stringify(body)).not.toContain("credential");
  });

  it("mostra erro de configuração mesmo no modo delegado", async () => {
    respond({ ...delegated, available: false, reason: "configuração inválida" });
    renderAt("/servidores-mcp", routes);
    const row = await screen.findByRole("row", { name: /delegado/ });
    expect(within(row).getByText("Indisponível")).toBeInTheDocument();
  });

  it("a aba do Assistant usa a política configurada sem anunciar descoberta autenticada", async () => {
    const probe = respond();
    renderAt("/assistentes/geral/mcp", [
      { path: "/assistentes/:nome", element: <AssistantDetail />, children: [{ path: "mcp", element: <McpTab /> }] },
    ]);
    await userEvent.click(await screen.findByRole("switch", { name: "Usar o servidor delegado" }));
    expect(screen.getByRole("checkbox", { name: "Permitir delegado.listar" })).toBeInTheDocument();
    expect(
      screen.getByText(/Tools configuradas; descoberta e conexão verificadas durante cada execução/),
    ).toBeInTheDocument();
    expect(probe).not.toHaveBeenCalled();
  });
});
