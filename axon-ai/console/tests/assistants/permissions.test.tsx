/** T067 — aba "Permissões" (013 US10, FR-028 a FR-031; ADR-040): esquemas e entradas de `allow` com o mecanismo das
 * sobreposições; sugestões só do que a API lista; `*` à parte e só em Assistant público; marcas sem bloquear. */

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import AssistantDetail from "../../src/features/assistants/AssistantDetail";
import AssistantsPage from "../../src/features/assistants/AssistantsPage";
import HistoryTab from "../../src/features/assistants/HistoryTab";
import PermissionsTab from "../../src/features/assistants/PermissionsTab";
import * as f from "../msw/fixtures";
import { server } from "../msw/server";
import { renderAt } from "../render";

const routes = [
  {
    path: "/assistentes/:nome",
    element: <AssistantDetail />,
    children: [
      { path: "permissoes", element: <PermissionsTab /> },
      { path: "historico", element: <HistoryTab /> },
    ],
  },
];

async function entries() {
  return within(await screen.findByRole("list", { name: "Quem pode usar" }));
}

describe("aba Permissões", () => {
  it("sem auth em overrides, mostra o YAML só para leitura", async () => {
    renderAt("/assistentes/geral/permissoes", routes);
    expect(await screen.findByText("As permissões deste Assistant só mudam por novo deploy")).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "Login" })).toBeDisabled();
    expect(screen.getByRole("checkbox", { name: /Qualquer pessoa autenticada/ })).toBeDisabled();
    expect(screen.queryByRole("button", { name: "Salvar sobreposição" })).not.toBeInTheDocument();
  });

  it("mostra esquemas, entradas com rótulo e as marcas de pendência", async () => {
    renderAt("/assistentes/aberto/permissoes", routes);
    expect(await screen.findByRole("switch", { name: "Login" })).toBeChecked();
    expect(screen.getByRole("switch", { name: "Chave de API" })).toBeChecked();
    const list = await entries();
    expect(list.getByText("svc:relatorios")).toBeInTheDocument();
    expect(list.getByText("group:equipe")).toBeInTheDocument();
    const sumiu = list.getByText("group:sumiu").closest("li");
    expect(sumiu).toHaveTextContent("Sem correspondência");
    expect(list.getByText("svc:relatorios").closest("li")).not.toHaveTextContent("Sem correspondência");
  });

  it("sistema com Chave de API desligada fica marcado", async () => {
    renderAt("/assistentes/aberto/permissoes", routes);
    await userEvent.click(await screen.findByRole("switch", { name: "Chave de API" }));
    const list = await entries();
    expect(list.getByText("svc:relatorios").closest("li")).toHaveTextContent("Não entra com os esquemas ligados");
  });

  it("sugere sistemas com chave ativa e grupos; aceita user: digitado; recusa forma errada", async () => {
    renderAt("/assistentes/aberto/permissoes", routes);
    const input = await screen.findByLabelText("Adicionar sistema, grupo ou pessoa");
    const listId = input.getAttribute("list") ?? "";
    const suggested = () =>
      [...document.querySelectorAll(`datalist#${CSS.escape(listId)} option`)].map(
        (option) => (option as HTMLOptionElement).value,
      );
    await waitFor(() => expect(suggested()).toContain("svc:relatorios"));
    const options = suggested();
    expect(options.filter((value) => value === "svc:relatorios")).toHaveLength(1);
    expect(options).not.toContain("svc:antigo");
    expect(options).not.toContain("user:caio");
    expect(options).toEqual(expect.arrayContaining(f.groups.map((group) => `group:${group.name}`)));

    await userEvent.type(input, "caio");
    await userEvent.click(screen.getByRole("button", { name: "Adicionar" }));
    expect(await screen.findByText(/Use svc:<nome>, group:<nome> ou user:<nome>/)).toBeInTheDocument();
    expect((await entries()).queryByText("caio")).not.toBeInTheDocument();

    await userEvent.clear(input);
    await userEvent.type(input, "user:ana");
    await userEvent.click(screen.getByRole("button", { name: "Adicionar" }));
    expect((await entries()).getByText("user:ana")).toBeInTheDocument();
    expect(screen.getByText("1 alteração não salva", { exact: false })).toBeInTheDocument();
  });

  it("qualquer pessoa autenticada é opção à parte só em Assistant público", async () => {
    renderAt("/assistentes/aberto/permissoes", routes);
    expect(await screen.findByRole("checkbox", { name: /Qualquer pessoa autenticada/ })).toBeEnabled();
  });

  it("em Assistant privado, qualquer pessoa autenticada não é oferecida, com o motivo", async () => {
    renderAt("/assistentes/restrito/permissoes", routes);
    expect(await screen.findByText(/Assistant privado:/)).toBeInTheDocument();
    expect(screen.queryByRole("checkbox", { name: /Qualquer pessoa autenticada/ })).not.toBeInTheDocument();
  });

  it("não salva sem esquema nem sem entrada, explicando", async () => {
    renderAt("/assistentes/restrito/permissoes", routes);
    await userEvent.click(await screen.findByRole("switch", { name: "Login" }));
    expect(screen.getByText("Ligue ao menos uma forma de entrada.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Salvar sobreposição" })).toBeDisabled();
    await userEvent.click(screen.getByRole("switch", { name: "Login" }));
    await userEvent.click((await entries()).getByRole("button", { name: "Remover group:equipe" }));
    expect(screen.getByText("Inclua ao menos uma entrada.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Salvar sobreposição" })).toBeDisabled();
  });

  it("salva esquemas ordenados, entradas e a versão lida", async () => {
    let body: unknown = null;
    server.use(
      http.put("*/admin/v1/assistants/restrito/auth", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(f.restrito);
      }),
    );
    renderAt("/assistentes/restrito/permissoes", routes);
    await userEvent.click(await screen.findByRole("switch", { name: "Chave de API" }));
    await userEvent.type(screen.getByLabelText("Adicionar sistema, grupo ou pessoa"), "svc:relatorios");
    await userEvent.click(screen.getByRole("button", { name: "Adicionar" }));
    await userEvent.click(screen.getByRole("button", { name: "Salvar sobreposição" }));
    await waitFor(() =>
      expect(body).toEqual({
        schemes: ["api_key", "oidc"],
        allow: ["group:equipe", "svc:relatorios"],
        version: null,
      }),
    );
  });

  it("conflito de versão preserva o rascunho", async () => {
    server.use(
      http.put("*/admin/v1/assistants/aberto/auth", () =>
        HttpResponse.json(
          {
            error: {
              message: "versão desatualizada",
              type: "conflict_error",
              code: "version_conflict",
              param: "version",
              current_version: 3,
            },
          },
          { status: 409 },
        ),
      ),
    );
    renderAt("/assistentes/aberto/permissoes", routes);
    await userEvent.click((await entries()).getByRole("button", { name: "Remover group:sumiu" }));
    await userEvent.click(screen.getByRole("button", { name: "Salvar sobreposição" }));
    expect(await screen.findByText("Outra pessoa salvou antes")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Recarregar e manter meu rascunho" })).toBeInTheDocument();
    expect((await entries()).queryByText("group:sumiu")).not.toBeInTheDocument();
  });

  it("descarte pede confirmação na tela", async () => {
    let discarded = false;
    server.use(
      http.delete("*/admin/v1/assistants/aberto/overrides/auth", ({ request }) => {
        discarded = new URL(request.url).searchParams.get("version") === "2";
        return HttpResponse.json({
          ...f.aberto,
          overrides: [],
          effective: { ...f.aberto.effective, auth: f.aberto.yaml.auth },
        });
      }),
    );
    renderAt("/assistentes/aberto/permissoes", routes);
    await userEvent.click(await screen.findByRole("button", { name: "Descartar sobreposição" }));
    const confirm = screen.getByRole("group", { name: "Confirmar o descarte" });
    await userEvent.click(within(confirm).getByRole("button", { name: "Descartar" }));
    await waitFor(() => expect(discarded).toBe(true));
  });

  it("o histórico nomeia a seção e resume as permissões", async () => {
    server.use(
      http.get("*/admin/v1/assistants/aberto/history", () =>
        HttpResponse.json({
          data: [
            {
              section: "auth",
              action: "saved",
              payload: { schemes: ["api_key", "oidc"], allow: ["group:equipe", "svc:relatorios"] },
              version: 2,
              actor: "user:ana",
              at: "2026-10-20T14:00:00+00:00",
            },
          ],
        }),
      ),
    );
    renderAt("/assistentes/aberto/historico", routes);
    const table = await screen.findByRole("table", { name: "Histórico de sobreposições de aberto" });
    const row = within(table).getByText("Permissões").closest("tr");
    expect(row).toHaveTextContent("Login, Chave de API · group:equipe, svc:relatorios");
  });

  it("a lista de Assistants mostra o selo de permissões", async () => {
    renderAt("/assistentes", [{ path: "/assistentes", element: <AssistantsPage /> }]);
    const row = (await screen.findByText("aberto")).closest("tr");
    expect(row).toHaveTextContent("Permissões");
  });
});
