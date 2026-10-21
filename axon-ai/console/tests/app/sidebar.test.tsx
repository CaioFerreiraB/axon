/** 013 US8 (FR-020, ADR-038; research R17, R18): a marca da barra lateral e o título da aba. */

import { screen, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { describe, expect, it } from "vitest";

import { Shell } from "../../src/app/Shell";
import { Page, PageHeader } from "../../src/ui/Page";
import { me } from "../msw/fixtures";
import { server } from "../msw/server";
import { renderAt } from "../render";

function renderShell() {
  renderAt("/uso", [
    {
      path: "/",
      element: <Shell />,
      children: [
        {
          path: "uso",
          element: (
            <Page>
              <PageHeader title="Uso e custo" />
            </Page>
          ),
        },
      ],
    },
  ]);
}

describe("Sidebar", () => {
  it("sem marca da instalação: símbolo, wordmark e Console, sem atribuição", async () => {
    renderShell();
    expect(await screen.findAllByAltText("Axon")).toHaveLength(2);
    expect(screen.getByText("Console")).toBeInTheDocument();
    expect(screen.queryByText("com Axon")).not.toBeInTheDocument();
    await waitFor(() => expect(document.title).toBe("Uso e custo · Axon"));
  });

  it("com marca da instalação: o nome dela e com Axon no rodapé", async () => {
    server.use(
      http.get("*/admin/v1/me", () =>
        HttpResponse.json({ ...me, instance: { name: "Instituto Exemplo", logo_url: null, custom: true } }),
      ),
    );
    renderShell();
    expect(await screen.findByText("Instituto Exemplo")).toBeInTheDocument();
    expect(screen.getByText("I")).toBeInTheDocument();
    expect(screen.getByText("com Axon")).toBeInTheDocument();
    expect(screen.queryAllByAltText("Axon")).toHaveLength(0);
    await waitFor(() => expect(document.title).toBe("Uso e custo · Instituto Exemplo"));
  });
});
