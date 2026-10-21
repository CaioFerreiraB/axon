/** T063 — chaves de API (013 US9, ADR-040): a chave em claro aparece uma vez, num diálogo, e não fica em lugar nenhum
 * depois de fechado; a lista nunca a traz; revogar e rotacionar pedem confirmação na linha. */

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import AccessPage from "../../src/features/access/AccessPage";
import KeysTab from "../../src/features/access/KeysTab";
import * as f from "../msw/fixtures";
import { server } from "../msw/server";
import { renderAt } from "../render";

const routes = [{ path: "/acesso", element: <AccessPage />, children: [{ path: "chaves", element: <KeysTab /> }] }];
const SECRET = "axn_0000000000000009_segredo-mostrado-uma-vez";

function issued(subject: string, label: string | null, extra: object = {}) {
  return {
    key_id: "0000000000000009",
    subject,
    groups: [],
    label,
    created_at: "2026-10-21T10:00:00+00:00",
    revoked_at: null,
    rotated_at: null,
    key: SECRET,
    ...extra,
  };
}

/** Nenhuma query nem mutação do cache guarda a chave em claro (FR-025, SC-009). */
function cacheText(client: ReturnType<typeof renderAt>["client"]): string {
  const queries = client
    .getQueryCache()
    .getAll()
    .map((query) => query.state.data);
  const mutations = client
    .getMutationCache()
    .getAll()
    .map((mutation) => mutation.state.data);
  return JSON.stringify([queries, mutations]);
}

describe("Chaves de API", () => {
  it("lista sistema, rótulo, identificador, grupos, rotação e estado, ativas antes das revogadas", async () => {
    renderAt("/acesso/chaves", routes);
    const table = await screen.findByRole("table", { name: "Chaves de API" });
    const rows = within(table).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(4);
    expect(rows[rows.length - 1]).toHaveTextContent("svc:antigo");
    expect(rows[rows.length - 1]).toHaveTextContent(/Revogada/);
    expect(within(table).getByText("prod")).toBeInTheDocument();
    expect(within(table).getByText("homolog")).toBeInTheDocument();
    expect(within(table).getByText("0000000000000001")).toBeInTheDocument();
    expect(within(table).getByText("admin")).toBeInTheDocument();
    expect(within(table).queryByText(/axn_/)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Revogar a chave 0000000000000003" })).not.toBeInTheDocument();
  });

  it("cria a chave e a mostra uma única vez", async () => {
    let body: unknown = null;
    server.use(
      http.post("*/admin/v1/keys", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(issued("svc:relatorios", "prod"), { status: 201 });
      }),
    );
    const { client } = renderAt("/acesso/chaves?criar=1", routes);
    await userEvent.type(await screen.findByLabelText("Nome do sistema"), "relatorios");
    await userEvent.type(screen.getByLabelText("Rótulo (opcional)"), "prod");
    await userEvent.click(screen.getByRole("button", { name: "Gerar chave" }));

    const dialog = await screen.findByRole("dialog", { name: "Chave criada para svc:relatorios" });
    expect(body).toEqual({ subject: "svc:relatorios", label: "prod" });
    expect(within(dialog).getByDisplayValue(SECRET)).toBeInTheDocument();
    expect(within(dialog).getByText(/não aparece de novo/)).toBeInTheDocument();
    expect(within(dialog).getByRole("button", { name: "Copiar" })).toBeInTheDocument();

    await userEvent.click(within(dialog).getByRole("button", { name: "Concluir" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(document.body.textContent).not.toContain(SECRET);
    expect(screen.queryByDisplayValue(SECRET)).not.toBeInTheDocument();
    expect(cacheText(client)).not.toContain(SECRET);
  });

  it("sem rótulo, não manda o campo; erro de nome aparece no campo", async () => {
    server.use(
      http.post("*/admin/v1/keys", () =>
        HttpResponse.json(
          {
            error: {
              message: "o nome do sistema segue [a-z0-9][a-z0-9._-]{0,63}: 'svc:Relatórios'",
              type: "invalid_request_error",
              code: "invalid_field",
              param: "subject",
            },
          },
          { status: 422 },
        ),
      ),
    );
    renderAt("/acesso/chaves?criar=1", routes);
    await userEvent.type(await screen.findByLabelText("Nome do sistema"), "Relatórios");
    await userEvent.click(screen.getByRole("button", { name: "Gerar chave" }));
    expect(await screen.findByText(/o nome do sistema segue/)).toBeInTheDocument();
    expect(screen.getByLabelText("Nome do sistema")).toHaveAttribute("aria-invalid", "true");
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("revogar pede confirmação na linha", async () => {
    let revoked: string | null = null;
    server.use(
      http.delete("*/admin/v1/keys/:id", ({ params }) => {
        revoked = String(params.id);
        return HttpResponse.json({ ...f.apiKeys[2], revoked_at: "2026-10-21T11:00:00+00:00" });
      }),
    );
    renderAt("/acesso/chaves", routes);
    await userEvent.click(await screen.findByRole("button", { name: "Revogar a chave 0000000000000002" }));
    const confirm = screen.getByRole("group", { name: "Confirmar a revogação de 0000000000000002" });
    expect(within(confirm).getByRole("button", { name: "Cancelar" })).toHaveFocus();
    await userEvent.click(within(confirm).getByRole("button", { name: "Cancelar" }));
    expect(revoked).toBeNull();

    await userEvent.click(screen.getByRole("button", { name: "Revogar a chave 0000000000000002" }));
    await userEvent.click(
      within(screen.getByRole("group", { name: "Confirmar a revogação de 0000000000000002" })).getByRole("button", {
        name: "Revogar",
      }),
    );
    await waitFor(() => expect(revoked).toBe("0000000000000002"));
  });

  it("rotacionar confirma na linha e mostra o segredo novo uma vez", async () => {
    server.use(
      http.post("*/admin/v1/keys/:id/rotate", () =>
        HttpResponse.json(issued("svc:relatorios", "prod", { rotated_at: "2026-10-21T11:00:00+00:00" })),
      ),
    );
    const { client } = renderAt("/acesso/chaves", routes);
    await userEvent.click(await screen.findByRole("button", { name: "Rotacionar a chave 0000000000000001" }));
    const confirm = screen.getByRole("group", { name: "Confirmar a rotação de 0000000000000001" });
    expect(confirm).toHaveTextContent(/deixa de valer/);
    await userEvent.click(within(confirm).getByRole("button", { name: "Rotacionar" }));

    const dialog = await screen.findByRole("dialog", { name: "Segredo novo para svc:relatorios" });
    expect(within(dialog).getByDisplayValue(SECRET)).toBeInTheDocument();
    expect(within(dialog).getByText(/anterior já não vale/)).toBeInTheDocument();
    await userEvent.click(within(dialog).getByRole("button", { name: "Concluir" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(cacheText(client)).not.toContain(SECRET);
  });

  it("chave revogada por outra pessoa: mostra o motivo e relê a lista", async () => {
    let reads = 0;
    server.use(
      http.get("*/admin/v1/keys", () => {
        reads += 1;
        return HttpResponse.json({ data: f.apiKeys });
      }),
      http.post("*/admin/v1/keys/:id/rotate", () =>
        HttpResponse.json(
          {
            error: {
              message: "chave '0000000000000002' revogada não rotaciona",
              type: "conflict_error",
              code: "key_revoked",
              param: "key_id",
            },
          },
          { status: 409 },
        ),
      ),
    );
    renderAt("/acesso/chaves", routes);
    await userEvent.click(await screen.findByRole("button", { name: "Rotacionar a chave 0000000000000002" }));
    await userEvent.click(
      within(screen.getByRole("group", { name: "Confirmar a rotação de 0000000000000002" })).getByRole("button", {
        name: "Rotacionar",
      }),
    );
    expect(await screen.findByRole("alert")).toHaveTextContent(/revogada não rotaciona/);
    await waitFor(() => expect(reads).toBeGreaterThan(1));
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("sem chaves, explica de onde vêm", async () => {
    server.use(http.get("*/admin/v1/keys", () => HttpResponse.json({ data: [] })));
    renderAt("/acesso/chaves", routes);
    expect(await screen.findByText("Nenhuma chave")).toBeInTheDocument();
  });
});
