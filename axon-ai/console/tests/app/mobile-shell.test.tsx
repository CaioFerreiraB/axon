/** 013 US13 (FR-046, FR-047; R38): a barra inferior, a folha "Mais" e o cabeçalho de app do celular. O CSS esconde
 * uma ou outra navegação pela largura; aqui as duas existem, e cada teste olha a do celular. */

import { screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { Shell } from "../../src/app/Shell";
import { Page, PageHeader } from "../../src/ui/Page";
import { renderAt } from "../render";

function renderShellAt(path: string) {
  const page = (title: string, back?: { to: string; label: string }) => (
    <Page>
      <PageHeader title={title} back={back} />
    </Page>
  );
  renderAt(path, [
    {
      path: "/",
      element: <Shell />,
      children: [
        { path: "uso", element: page("Uso e custo") },
        { path: "meio-ambiente", element: page("Meio ambiente") },
        { path: "assistentes/geral", element: page("geral", { to: "/assistentes", label: "Assistentes" }) },
      ],
    },
  ]);
}

async function bottomNav() {
  const nav = (await screen.findAllByRole("navigation", { name: "Seções" })).find((element) =>
    within(element).queryByText("Mais"),
  );
  if (!nav) {
    throw new Error("sem a barra inferior");
  }
  return within(nav);
}

describe("Barra inferior e Mais (celular)", () => {
  it("marca a seção primária atual", async () => {
    renderShellAt("/uso");
    expect(await screen.findAllByText("Uso e custo")).not.toHaveLength(0);
    expect((await bottomNav()).getByRole("link", { name: "Uso" })).toHaveAttribute("aria-current", "page");
    expect((await bottomNav()).getByRole("button", { name: "Mais" })).not.toHaveAttribute("data-active");
  });

  it("numa seção secundária, marca Mais, e a folha leva às outras seções e à sessão", async () => {
    const user = userEvent.setup();
    renderShellAt("/meio-ambiente");
    const more = (await bottomNav()).getByRole("button", { name: "Mais" });
    expect(more).toHaveAttribute("data-active", "true");
    await user.click(more);
    const sheet = within(await screen.findByRole("dialog", { name: "Mais" }));
    expect(sheet.getByRole("link", { name: "Meio ambiente" })).toHaveAttribute("aria-current", "page");
    expect(sheet.getByRole("link", { name: "Observabilidade" })).toBeInTheDocument();
    expect(sheet.getByRole("radiogroup", { name: "Tema" })).toBeInTheDocument();
    expect(await sheet.findByRole("button", { name: "Sair" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: "Mais" })).not.toBeInTheDocument();
    expect(more).toHaveFocus();
  });

  it("o foco volta ao Mais também depois do véu e de um link da folha", async () => {
    const user = userEvent.setup();
    renderShellAt("/meio-ambiente");
    const more = (await bottomNav()).getByRole("button", { name: "Mais" });

    await user.click(more);
    await screen.findByRole("dialog", { name: "Mais" });
    const overlay = document.querySelector<HTMLElement>("[data-state='open'][class*='overlay']");
    expect(overlay).not.toBeNull();
    if (overlay) {
      await user.click(overlay);
    }
    expect(screen.queryByRole("dialog", { name: "Mais" })).not.toBeInTheDocument();
    expect(more).toHaveFocus();

    await user.click(more);
    const sheet = within(await screen.findByRole("dialog", { name: "Mais" }));
    await user.click(sheet.getByRole("link", { name: "Meio ambiente" }));
    expect(screen.queryByRole("dialog", { name: "Mais" })).not.toBeInTheDocument();
    expect(more).toHaveFocus();
  });

  it("o cabeçalho de app mostra o título e, no detalhe, o voltar", async () => {
    renderShellAt("/assistentes/geral");
    expect(await screen.findByRole("link", { name: "Voltar para Assistentes" })).toHaveAttribute(
      "href",
      "/assistentes",
    );
    expect(screen.getByRole("heading", { level: 1, name: "geral" })).toBeInTheDocument();
  });
});
