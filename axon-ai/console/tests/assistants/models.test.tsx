/** T019 — aba Modelos: editável, travada e inativa; recusa da API junto ao papel; conflito de versão mantém o rascunho;
 * descarte confirmado na própria tela; a seção inteira vai no PUT (003 FR-018). */

import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import AssistantDetail from "../../src/features/assistants/AssistantDetail";
import ModelsTab from "../../src/features/assistants/ModelsTab";
import * as f from "../msw/fixtures";
import { apiError } from "../msw/handlers";
import { server } from "../msw/server";
import { renderAt } from "../render";

const routes = [
  { path: "/assistentes/:nome", element: <AssistantDetail />, children: [{ path: "modelos", element: <ModelsTab /> }] },
];

describe("aba Modelos", () => {
  it("mostra YAML, sobreposição e efetivo, e salva a seção inteira com a versão lida", async () => {
    let body: unknown = null;
    server.use(
      http.put("*/admin/v1/assistants/geral/models", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(f.geral);
      }),
    );
    renderAt("/assistentes/geral/modelos", routes);
    const generation = await screen.findByRole("combobox", { name: "Modelo de generation" });
    expect(generation).toHaveValue("openai/gpt-4.1-mini");
    expect(screen.getByRole("combobox", { name: "Provedor de generation" })).toHaveValue("openrouter");
    expect(screen.getByText("Sobreposto")).toBeInTheDocument();
    await userEvent.clear(generation);
    await userEvent.type(generation, "openai/gpt-4.1");
    expect(screen.getByText(/1 alteração não salva/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Salvar sobreposição" }));
    await waitFor(() =>
      expect(body).toEqual({
        roles: { generation: "openrouter/openai/gpt-4.1", controller: "openrouter/openai/gpt-4.1-nano" },
        version: 3,
      }),
    );
  });

  it("a recusa da API aparece junto ao papel", async () => {
    server.use(
      http.put("*/admin/v1/assistants/geral/models", () =>
        HttpResponse.json(
          {
            error: {
              message: "roles.generation: fora da allowlist (openrouter/*)",
              type: "x",
              code: "invalid_field",
              param: "roles.generation",
            },
          },
          { status: 422 },
        ),
      ),
    );
    renderAt("/assistentes/geral/modelos", routes);
    const generation = await screen.findByRole("combobox", { name: "Modelo de generation" });
    await userEvent.clear(generation);
    await userEvent.type(generation, "openai/gpt-4.1");
    await userEvent.click(screen.getByRole("button", { name: "Salvar sobreposição" }));
    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("fora da allowlist");
    expect(generation).toHaveAttribute("aria-invalid", "true");
  });

  it("conflito de versão avisa e mantém o rascunho", async () => {
    server.use(
      http.put("*/admin/v1/assistants/geral/models", () =>
        apiError(409, "version_conflict", "mudou", { current_version: 4 }),
      ),
    );
    renderAt("/assistentes/geral/modelos", routes);
    const generation = await screen.findByRole("combobox", { name: "Modelo de generation" });
    await userEvent.clear(generation);
    await userEvent.type(generation, "x/y");
    await userEvent.click(screen.getByRole("button", { name: "Salvar sobreposição" }));
    expect(await screen.findByText("Outra pessoa salvou antes")).toBeInTheDocument();
    expect(generation).toHaveValue("x/y");
  });

  it("descartar pede confirmação na própria tela", async () => {
    let discarded = "";
    server.use(
      http.delete("*/admin/v1/assistants/geral/overrides/models", ({ request }) => {
        discarded = new URL(request.url).search;
        return HttpResponse.json({ ...f.geral, overrides: [], effective: f.geral.yaml });
      }),
    );
    renderAt("/assistentes/geral/modelos", routes);
    await userEvent.click(await screen.findByRole("button", { name: "Descartar sobreposição" }));
    const confirm = screen.getByRole("group", { name: "Confirmar o descarte" });
    await userEvent.click(within(confirm).getByRole("button", { name: "Descartar" }));
    await waitFor(() => expect(discarded).toBe("?version=3"));
  });

  it("seção travada: só muda por novo deploy, sem campos", async () => {
    renderAt("/assistentes/rascunho/modelos", routes);
    expect(await screen.findByText("Os modelos deste Assistant só mudam por novo deploy")).toBeInTheDocument();
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Salvar sobreposição" })).not.toBeInTheDocument();
  });

  it("sobreposição inativa: o motivo da API e o que ficou guardado", async () => {
    renderAt("/assistentes/documentos/modelos", routes);
    expect(await screen.findByText("Sobreposição inativa: o deploy mudou esta seção")).toBeInTheDocument();
    expect(screen.getByText(/O deploy mudou a seção\./)).toBeInTheDocument();
    expect(screen.getByText(/Guardada: generation = ollama\/gemma3:1b/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Apagar sobreposição guardada" })).toBeInTheDocument();
  });

  it("testar modelo mostra disponibilidade e tempo", async () => {
    server.use(
      http.post("*/admin/v1/assistants/geral/models/check", () =>
        HttpResponse.json({ available: true, detail: null, latency_ms: 412 }),
      ),
    );
    renderAt("/assistentes/geral/modelos", routes);
    await userEvent.click(await screen.findByRole("button", { name: "Testar o modelo de generation" }));
    expect(await screen.findByText("Disponível · respondeu em 412 ms")).toBeInTheDocument();
  });

  it("o provedor é uma lista com os prontos, e o papel vazio usa o primeiro pronto", async () => {
    let body: unknown = null;
    server.use(
      http.put("*/admin/v1/assistants/geral/models", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(f.geral);
      }),
    );
    renderAt("/assistentes/geral/modelos", routes);
    const provider = await screen.findByRole("combobox", { name: "Provedor de generation" });
    await waitFor(() =>
      expect(
        within(provider)
          .getAllByRole("option")
          .map((option) => option.textContent),
      ).toEqual(["openrouter"]),
    );
    const rerank = screen.getByRole("combobox", { name: "Provedor de rerank" });
    expect(rerank).toHaveValue("openrouter");
    await userEvent.type(screen.getByRole("combobox", { name: "Modelo de rerank" }), "cohere/rerank-v3.5");
    await userEvent.click(screen.getByRole("button", { name: "Salvar sobreposição" }));
    await waitFor(() =>
      expect(body).toEqual({
        roles: {
          generation: "openrouter/openai/gpt-4.1-mini",
          controller: "openrouter/openai/gpt-4.1-nano",
          rerank: "openrouter/cohere/rerank-v3.5",
        },
        version: 3,
      }),
    );
  });

  it("o provedor em uso que não está pronto continua na lista, marcado como indisponível", async () => {
    const ollama = {
      ...f.geral,
      overrides: [],
      yaml: { ...f.geral.yaml, models: { generation: "ollama/qwen3:1.7b" } },
      effective: { ...f.geral.effective, models: { generation: "ollama/qwen3:1.7b" } },
    };
    server.use(http.get("*/admin/v1/assistants/geral", () => HttpResponse.json(ollama)));
    renderAt("/assistentes/geral/modelos", routes);
    const provider = await screen.findByRole("combobox", { name: "Provedor de generation" });
    expect(provider).toHaveValue("ollama");
    await waitFor(() =>
      expect(
        within(provider)
          .getAllByRole("option")
          .map((option) => option.textContent),
      ).toEqual(["openrouter", "ollama · indisponível"]),
    );
    expect(screen.getByRole("combobox", { name: "Modelo de generation" })).toHaveValue("qwen3:1.7b");
    await userEvent.selectOptions(provider, "openrouter");
    expect(screen.getByText(/1 alteração não salva/)).toBeInTheDocument();
  });

  it("sem provedor pronto, avisa o que configurar", async () => {
    server.use(
      http.get("*/admin/v1/providers", () =>
        HttpResponse.json({ data: f.providers.map((p) => ({ ...p, ready: false, detail: "fora" })) }),
      ),
    );
    renderAt("/assistentes/geral/modelos", routes);
    expect(await screen.findByText("Nenhum provedor pronto")).toBeInTheDocument();
  });
});
