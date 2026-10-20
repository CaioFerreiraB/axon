/** T012/SC-007 — quem não administra vê só o acesso negado, sem nenhuma outra chamada administrativa. */

import { screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { RequireAdmin } from "../../src/app/RequireAdmin";
import { server } from "../msw/server";
import { renderAt } from "../render";

describe("RequireAdmin", () => {
  it("404 no /me é a página de acesso negado, e nada mais é pedido", async () => {
    const paths: string[] = [];
    server.events.on("request:start", ({ request }) => {
      paths.push(new URL(request.url).pathname);
    });
    server.use(
      http.get("*/admin/v1/me", () =>
        HttpResponse.json(
          { error: { message: "recurso não encontrado", type: "not_found_error", code: "not_found" } },
          { status: 404 },
        ),
      ),
    );
    renderAt("/uso", [
      {
        path: "/uso",
        element: (
          <RequireAdmin>
            <p>painel administrativo</p>
          </RequireAdmin>
        ),
      },
    ]);
    expect(await screen.findByText("Sua conta não tem acesso à console")).toBeInTheDocument();
    expect(screen.queryByText("painel administrativo")).not.toBeInTheDocument();
    expect(paths.every((path) => path === "/admin/v1/me")).toBe(true);
    server.events.removeAllListeners();
  });
});
