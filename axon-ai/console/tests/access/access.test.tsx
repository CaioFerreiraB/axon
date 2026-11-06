/** T032 — acesso: senha temporária mostrada uma vez no cadastro; Google desabilitado sem cliente na instalação;
 * grupo de administração protegido. */

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import AccessPage from "../../src/features/access/AccessPage";
import GroupsTab from "../../src/features/access/GroupsTab";
import LoginTab from "../../src/features/access/LoginTab";
import UsersTab from "../../src/features/access/UsersTab";
import * as f from "../msw/fixtures";
import { server } from "../msw/server";
import { renderAt } from "../render";

const routes = [
  {
    path: "/acesso",
    element: <AccessPage />,
    children: [
      { path: "usuarios", element: <UsersTab /> },
      { path: "grupos", element: <GroupsTab /> },
      { path: "login", element: <LoginTab /> },
    ],
  },
];

describe("Acesso", () => {
  it("cadastro mostra a senha temporária uma vez", async () => {
    server.use(
      http.post("*/admin/v1/users", () =>
        HttpResponse.json(
          {
            account: { ...f.accounts.data[0], username: "davi", name: "Davi Reis", temporary_password: true },
            temporary_password: "tropa-quiabo-marfim-71",
          },
          { status: 201 },
        ),
      ),
    );
    renderAt("/acesso/usuarios?cadastrar=1", routes);
    const dialog = await screen.findByRole("dialog", { name: "Cadastrar pessoa" });
    await userEvent.type(screen.getByLabelText("Nome"), "Davi Reis");
    await userEvent.type(screen.getByLabelText("Usuário"), "davi");
    await userEvent.type(screen.getByLabelText("E-mail"), "davi@exemplo.org");
    await userEvent.click(screen.getByRole("button", { name: "Cadastrar" }));
    expect(await screen.findByRole("dialog", { name: "Davi Reis foi cadastrado" })).toBeInTheDocument();
    expect(screen.getByDisplayValue("tropa-quiabo-marfim-71")).toBeInTheDocument();
    expect(dialog).toBeTruthy();
    await userEvent.click(screen.getByRole("button", { name: "Concluir" }));
    await waitFor(() => expect(screen.queryByDisplayValue("tropa-quiabo-marfim-71")).not.toBeInTheDocument());
  });

  it("sem cliente Google na instalação, a chave fica desabilitada com a explicação", async () => {
    renderAt("/acesso/login", routes);
    expect(await screen.findByText("Falta o cliente Google na instalação")).toBeInTheDocument();
    expect(screen.getByRole("switch", { name: "Entrar com Google" })).toBeDisabled();
    expect(screen.getByDisplayValue(f.login.google_redirect_uri)).toBeInTheDocument();
  });

  it("o grupo de administração é protegido, sem apagar", async () => {
    renderAt("/acesso/grupos", routes);
    expect(await screen.findByText("Protegido")).toBeInTheDocument();
    expect(screen.getAllByRole("button", { name: "Apagar" })).toHaveLength(1);
  });
});

describe("Apagar conta e um grupo de cada vez (incremento 9.7, US12; 013 R32–R35)", () => {
  async function openMenu(name: string) {
    renderAt("/acesso/usuarios", routes);
    await userEvent.click(await screen.findByRole("button", { name: `Ações de ${name}` }));
  }

  it("a própria conta não oferece apagar; a de outra pessoa, sim", async () => {
    await openMenu("Ana Souza");
    expect(screen.queryByRole("button", { name: "Apagar conta" })).not.toBeInTheDocument();
    await userEvent.keyboard("{Escape}");
    await userEvent.click(screen.getByRole("button", { name: "Ações de Bia Lima" }));
    expect(screen.getByRole("button", { name: "Apagar conta" })).toBeInTheDocument();
  });

  it("apagar só habilita com o nome exato e mostra o relatório, sem pseudônimo", async () => {
    await openMenu("Bia Lima");
    await userEvent.click(screen.getByRole("button", { name: "Apagar conta" }));
    const dialog = await screen.findByRole("dialog", { name: "Apagar a conta de Bia Lima?" });
    const apagar = within(dialog).getByRole("button", { name: "Apagar" });
    expect(apagar).toBeDisabled();
    await userEvent.type(within(dialog).getByLabelText(/Digite o nome de usuário/), "bi");
    expect(apagar).toBeDisabled();
    await userEvent.type(within(dialog).getByLabelText(/Digite o nome de usuário/), "a");
    expect(apagar).toBeEnabled();
    await userEvent.click(apagar);

    const report = await screen.findByRole("dialog", { name: "A conta bia foi apagada" });
    expect(within(report).getByText("Servidores MCP")).toBeInTheDocument();
    expect(within(report).getByText("3 conversas")).toBeInTheDocument();
    expect(within(report).getByText(/Aviso: referências na configuração/)).toBeInTheDocument();
    expect(report.textContent).not.toMatch(/deleted:/);
  });

  it("incompleto: o relatório parcial, a parte que falhou e tentar de novo conclui", async () => {
    let calls = 0;
    server.use(
      http.delete("*/admin/v1/users/:username", () => {
        calls += 1;
        if (calls === 1) {
          return HttpResponse.json(
            {
              error: {
                message: "apagamento incompleto",
                type: "server_error",
                code: "deletion_incomplete",
                param: null,
              },
              report: {
                ...f.deletionReport,
                complete: false,
                identity: {},
                modules: f.deletionReport.modules.map((m) =>
                  m.name === "conversations" ? { ...m, counts: {}, failed: true } : m,
                ),
              },
            },
            { status: 503, headers: { "Retry-After": "5" } },
          );
        }
        return HttpResponse.json(f.deletionReport);
      }),
    );
    await openMenu("Bia Lima");
    await userEvent.click(screen.getByRole("button", { name: "Apagar conta" }));
    const dialog = await screen.findByRole("dialog", { name: "Apagar a conta de Bia Lima?" });
    await userEvent.type(within(dialog).getByLabelText(/Digite o nome de usuário/), "bia");
    await userEvent.click(within(dialog).getByRole("button", { name: "Apagar" }));

    const partial = await screen.findByRole("dialog", { name: "O apagamento de bia não terminou" });
    expect(within(partial).getByText("Falhou")).toBeInTheDocument();
    await userEvent.click(within(partial).getByRole("button", { name: "Tentar de novo" }));
    expect(await screen.findByRole("dialog", { name: "A conta bia foi apagada" })).toBeInTheDocument();
    expect(calls).toBe(2);
  });

  it("a conta em apagamento tem o selo e só concluir, sem pedir o nome", async () => {
    const bia = { ...f.accounts.data[1], active: false, groups: [], deleting: true };
    server.use(
      http.get("*/admin/v1/users", () => HttpResponse.json({ data: [f.accounts.data[0], bia], next_cursor: null })),
    );
    renderAt("/acesso/usuarios", routes);
    expect(await screen.findByText("Em apagamento")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Ações de Bia Lima" }));
    expect(screen.queryByRole("button", { name: "Editar" })).not.toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Concluir apagamento" }));
    const dialog = await screen.findByRole("dialog", { name: "Concluir o apagamento de bia" });
    expect(within(dialog).queryByLabelText(/Digite o nome de usuário/)).not.toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "Concluir" }));
    expect(await screen.findByRole("dialog", { name: "A conta bia foi apagada" })).toBeInTheDocument();
  });

  it("o último admin: a recusa aparece com o motivo", async () => {
    server.use(
      http.delete("*/admin/v1/users/:username", () =>
        HttpResponse.json(
          {
            error: {
              message: "o grupo de administração ficaria sem admin ativo",
              type: "conflict",
              code: "protected_group",
              param: null,
            },
          },
          { status: 409 },
        ),
      ),
    );
    await openMenu("Bia Lima");
    await userEvent.click(screen.getByRole("button", { name: "Apagar conta" }));
    const dialog = await screen.findByRole("dialog", { name: "Apagar a conta de Bia Lima?" });
    await userEvent.type(within(dialog).getByLabelText(/Digite o nome de usuário/), "bia");
    await userEvent.click(within(dialog).getByRole("button", { name: "Apagar" }));
    expect(await within(dialog).findByText("o grupo de administração ficaria sem admin ativo")).toBeInTheDocument();
  });

  it("os grupos da ficha valem na hora, um de cada vez, sem PATCH com a lista", async () => {
    const requests: string[] = [];
    server.use(
      http.put("*/admin/v1/users/:username/groups/:group", ({ request, params }) => {
        requests.push(`PUT ${new URL(request.url).pathname}`);
        return HttpResponse.json({ ...f.accounts.data[1], groups: ["equipe", String(params.group)] });
      }),
      http.patch("*/admin/v1/users/:username", ({ request }) => {
        requests.push(`PATCH ${new URL(request.url).pathname}`);
        return HttpResponse.json(f.accounts.data[1]);
      }),
    );
    await openMenu("Bia Lima");
    await userEvent.click(screen.getByRole("button", { name: "Editar" }));
    const dialog = await screen.findByRole("dialog", { name: "Editar Bia Lima" });
    await userEvent.click(within(dialog).getByRole("checkbox", { name: "admin" }));

    await waitFor(() => expect(within(dialog).getByRole("checkbox", { name: "admin" })).toBeChecked());
    expect(requests).toEqual(["PUT /admin/v1/users/bia/groups/admin"]);
    expect(within(dialog).getByRole("checkbox", { name: "equipe" })).toBeChecked();
  });

  it("a recusa de um grupo volta a caixa e aparece ao lado dela", async () => {
    server.use(
      http.delete("*/admin/v1/users/:username/groups/:group", () =>
        HttpResponse.json(
          { error: { message: "último admin ativo", type: "conflict", code: "protected_group", param: null } },
          { status: 409 },
        ),
      ),
    );
    await openMenu("Bia Lima");
    await userEvent.click(screen.getByRole("button", { name: "Editar" }));
    const dialog = await screen.findByRole("dialog", { name: "Editar Bia Lima" });
    const equipe = within(dialog).getByRole("checkbox", { name: "equipe" });
    await userEvent.click(equipe);
    expect(await within(dialog).findByText("último admin ativo")).toBeInTheDocument();
    expect(equipe).toBeChecked();
  });

  it("o Salvar da ficha leva só nome e e-mail", async () => {
    let body: unknown;
    server.use(
      http.patch("*/admin/v1/users/:username", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(f.accounts.data[1]);
      }),
    );
    await openMenu("Bia Lima");
    await userEvent.click(screen.getByRole("button", { name: "Editar" }));
    const dialog = await screen.findByRole("dialog", { name: "Editar Bia Lima" });
    await userEvent.clear(within(dialog).getByLabelText("Nome"));
    await userEvent.type(within(dialog).getByLabelText("Nome"), "Bia L.");
    await userEvent.click(within(dialog).getByRole("button", { name: "Salvar" }));
    await waitFor(() => expect(body).toEqual({ version: 3, name: "Bia L." }));
  });
});
