/** 013 US11 — Meio ambiente: faixas de resumo e de intensidade, os cinco gráficos com o formato do grão, a tabela com
 * o selo "Aproximado", a nota de método, o período personalizado e os estados; em Uso e custo, a célula Emissões. */

import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import ImpactPage from "../../src/features/impact/ImpactPage";
import UsagePage from "../../src/features/usage/UsagePage";
import * as f from "../msw/fixtures";
import { server } from "../msw/server";
import { renderAt } from "../render";

const page = [{ path: "/meio-ambiente", element: <ImpactPage /> }];

describe("Meio ambiente", () => {
  it("mostra as faixas, os gráficos, a tabela e o método", async () => {
    renderAt("/meio-ambiente?agregacao=semana", page);
    expect(await screen.findByText(/14\/09 a 13\/10 · fuso America\/Sao_Paulo/)).toBeInTheDocument();
    const summary = screen.getByRole("region", { name: "Impacto do período" });
    expect(within(summary).getByText("Emissões (GWP)")).toBeInTheDocument();
    expect(within(summary).getByText("337")).toBeInTheDocument();
    expect(within(summary).getByText("g CO₂e")).toBeInTheDocument();
    expect(within(summary).getByText(/Parcial: 14,9% das chamadas sem estimativa/)).toBeInTheDocument();
    expect(within(summary).getByText("menos de 0,01")).toBeInTheDocument();
    expect(within(summary).getByText("Mata Atlântica, 20 anos")).toBeInTheDocument();
    const intensity = screen.getByRole("region", { name: "Intensidade" });
    expect(within(intensity).getByText("85,1%")).toBeInTheDocument();
    for (const name of [
      /Emissões por semana/,
      /Energia por semana/,
      /Água por semana/,
      /Energia primária \(PE\) por semana/,
      /Recursos abióticos \(ADPe\) por semana/,
    ]) {
      expect(screen.getByRole("img", { name })).toBeInTheDocument();
    }
    const equivalent = screen.getByRole("table", { name: /Emissões por semana, em CO₂e, por fase/ });
    expect(within(equivalent).getByRole("rowheader", { name: /S38 · 14–20 set/ })).toBeInTheDocument();
    const table = screen.getByRole("table", { name: "Impacto por modelo no período" });
    const glm = within(table).getByRole("row", { name: /glm-5\.3-flash/ });
    expect(within(glm).getAllByText("Aproximado").length).toBeGreaterThan(0);
    expect(within(glm).getAllByText("mistralai/zai-glm-5-3").length).toBeGreaterThan(0);
    expect(within(within(table).getByRole("row", { name: /qwen3/ })).getAllByText("sem estimativa").length).toBe(2);
    expect(screen.getByText(/Estimativas do EcoLogits 0\.11\.3/)).toBeInTheDocument();
  });

  it("troca a agregação e o rótulo dos baldes acompanha", async () => {
    let grain: string | null = null;
    server.use(
      http.get("*/admin/v1/impact", ({ request }) => {
        grain = new URL(request.url).searchParams.get("grain");
        const month = grain === "month";
        return HttpResponse.json({
          ...f.impactReport,
          query: { ...f.impactReport.query, grain: grain ?? "day" },
          buckets: month
            ? [
                { ...f.impactReport.buckets[0], start: "2026-09-14", end: "2026-09-30" },
                { ...f.impactReport.buckets[1], start: "2026-10-01", end: "2026-10-13" },
              ]
            : f.impactReport.buckets,
        });
      }),
    );
    renderAt("/meio-ambiente", page);
    await screen.findByRole("img", { name: /Emissões por dia/ });
    await userEvent.click(screen.getByRole("radio", { name: "Mês" }));
    expect(await screen.findByRole("img", { name: /Emissões por mês/ })).toBeInTheDocument();
    expect(grain).toBe("month");
    const equivalent = screen.getByRole("table", { name: /Emissões por mês/ });
    expect(within(equivalent).getByRole("rowheader", { name: /out\/26 · 1–13 out/ })).toBeInTheDocument();
  });

  it("período personalizado: De e Até vão para a API, e a recusa aparece no campo", async () => {
    const asked: string[] = [];
    server.use(
      http.get("*/admin/v1/impact", ({ request }) => {
        const params = new URL(request.url).searchParams;
        asked.push(`${params.get("from")}..${params.get("to")}`);
        if (params.get("from") === "2025-01-01") {
          return HttpResponse.json(
            {
              error: {
                message: "grain: por dia, o período vai até 366 dias",
                type: "invalid_request_error",
                code: "invalid_field",
                param: "grain",
              },
            },
            { status: 422 },
          );
        }
        return HttpResponse.json(f.impactReport);
      }),
    );
    renderAt("/meio-ambiente", page);
    await screen.findByRole("img", { name: /Emissões por dia/ });
    await userEvent.click(screen.getByRole("radio", { name: "Personalizado" }));
    const form = screen.getByRole("form", { name: "Período personalizado" });
    const from = within(form).getByLabelText("De");
    await userEvent.clear(from);
    await userEvent.type(from, "2025-01-01");
    await userEvent.click(within(form).getByRole("button", { name: "Aplicar" }));
    expect(asked).toContain("2025-01-01..2026-10-13");
    await userEvent.click(screen.getByRole("radio", { name: "Personalizado" }));
    expect(await screen.findByText(/por dia, o período vai até 366 dias/)).toBeInTheDocument();
  });

  it("estimativa desligada, vazio e erro", async () => {
    server.use(
      http.get("*/admin/v1/impact", () =>
        HttpResponse.json({
          ...f.impactReport,
          enabled: false,
          totals: null,
          previous_totals: null,
          buckets: [],
          rows: [],
        }),
      ),
    );
    const { unmount } = renderAt("/meio-ambiente", page);
    expect(await screen.findByText(/está desligada nesta instalação/)).toBeInTheDocument();
    unmount();

    server.use(
      http.get("*/admin/v1/impact", () =>
        HttpResponse.json({
          ...f.impactReport,
          totals: {
            metrics: f.impactMetrics(0),
            coverage: { calls: 0, eligible: 0, estimated: 0, approximate: 0, unestimated: 0 },
            responses: 0,
            estimated_responses: 0,
            estimated_output_tokens: 0,
            trees: "0",
          },
          rows: [],
        }),
      ),
    );
    const empty = renderAt("/meio-ambiente", page);
    expect((await screen.findAllByText("Nenhuma chamada estimada no período")).length).toBeGreaterThan(0);
    empty.unmount();

    server.use(
      http.get("*/admin/v1/impact", () =>
        HttpResponse.json(
          { error: { message: "banco fora do ar", type: "api_error", code: "storage_unavailable" } },
          { status: 503 },
        ),
      ),
    );
    renderAt("/meio-ambiente", page);
    expect(await screen.findByText("Não foi possível carregar o impacto ambiental")).toBeInTheDocument();
  });
});

describe("Uso e custo com emissões", () => {
  it("a quinta célula mostra o CO₂e e leva a Meio ambiente com o mesmo período", async () => {
    renderAt("/uso", [{ path: "/uso", element: <UsagePage /> }]);
    const strip = await screen.findByRole("region", { name: "Totais do período" });
    expect(await within(strip).findByText("337 g CO₂e")).toBeInTheDocument();
    expect(within(strip).getByRole("link", { name: /Meio ambiente/ })).toHaveAttribute(
      "href",
      "/meio-ambiente?periodo=personalizado&de=2026-09-14&ate=2026-10-13",
    );
  });
});
