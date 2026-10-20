/** T032 — acesso: senha temporária mostrada uma vez no cadastro; Google desabilitado sem cliente na instalação;
 * grupo de administração protegido. */

import { screen, waitFor } from "@testing-library/react";
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
