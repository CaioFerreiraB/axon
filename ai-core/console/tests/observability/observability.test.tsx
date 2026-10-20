/** T030 — Langfuse: o segredo nunca volta; o que a instalação define é somente leitura; captura só depois de marcar
 * "Li e quero capturar o texto". */

import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import ObservabilityPage from "../../src/features/observability/ObservabilityPage";
import * as f from "../msw/fixtures";
import { server } from "../msw/server";
import { renderAt } from "../render";

const routes = [{ path: "/observabilidade", element: <ObservabilityPage /> }];

describe("Observabilidade", () => {
  it("o segredo salvo aparece só como definido", async () => {
    renderAt("/observabilidade", routes);
    const secret = await screen.findByLabelText("Chave secreta");
    expect(secret).toHaveValue("");
    expect(secret).toHaveAttribute("placeholder", "Definida · digite para trocar");
  });

  it("campos da instalação ficam somente leitura com o selo", async () => {
    server.use(
      http.get("*/admin/v1/observability", () =>
        HttpResponse.json({
          ...f.observability,
          langfuse: {
            ...f.observability.langfuse,
            sources: {
              enabled: "installation",
              host: "installation",
              public_key: "installation",
              secret_key: "installation",
            },
          },
        }),
      ),
    );
    renderAt("/observabilidade", routes);
    expect(await screen.findByLabelText("Endereço")).toHaveAttribute("readonly");
    expect(screen.getAllByText("Definido na instalação").length).toBeGreaterThanOrEqual(3);
    expect(screen.queryByRole("button", { name: "Salvar" })).not.toBeInTheDocument();
  });

  it("ligar a captura exige confirmar o aviso de privacidade", async () => {
    let body: unknown = null;
    server.use(
      http.put("*/admin/v1/observability/capture", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ ...f.observability, capture_content: true, version: 5 });
      }),
    );
    renderAt("/observabilidade", routes);
    await userEvent.click(await screen.findByRole("switch", { name: "Capturar prompt e resposta" }));
    const confirm = screen.getByRole("button", { name: "Ligar captura" });
    expect(confirm).toBeDisabled();
    await userEvent.click(screen.getByRole("checkbox", { name: "Li e quero capturar o texto" }));
    await userEvent.click(confirm);
    await waitFor(() => expect(body).toEqual({ enabled: true, acknowledged: true, version: 4 }));
  });

  it("chave mestra ausente é explicada junto à chave secreta", async () => {
    server.use(
      http.put("*/admin/v1/observability/langfuse", () =>
        HttpResponse.json(
          {
            error: {
              message: "defina AI_CORE_MASTER_KEY na instalação para gravar o segredo do Langfuse",
              type: "conflict_error",
              code: "master_key_missing",
              param: "secret_key",
            },
          },
          { status: 409 },
        ),
      ),
    );
    renderAt("/observabilidade", routes);
    await userEvent.type(await screen.findByLabelText("Chave secreta"), "sk-lf-novo");
    await userEvent.click(screen.getByRole("button", { name: "Salvar" }));
    expect(await screen.findByText(/AI_CORE_MASTER_KEY/)).toBeInTheDocument();
  });
});
