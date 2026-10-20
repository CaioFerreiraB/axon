/** T007 — componentes de UI: rótulos, erro ligado ao campo e nenhuma violação do axe (o contraste é medido no e2e, com
 * as cores de verdade). */

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import axe from "axe-core";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { Badge, InstallationBadge } from "../../src/ui/Badge";
import { Button } from "../../src/ui/Button";
import { Checkbox } from "../../src/ui/Checkbox";
import { Field, TextInput } from "../../src/ui/Field";
import { Notice } from "../../src/ui/Notice";
import { Segmented } from "../../src/ui/Segmented";
import { Toggle } from "../../src/ui/Toggle";

async function violations(container: HTMLElement) {
  const result = await axe.run(container, {
    rules: { "color-contrast": { enabled: false }, region: { enabled: false } },
  });
  return result.violations.map((v) => `${v.id}: ${v.nodes.map((n) => n.html).join(" | ")}`);
}

function Period() {
  const [value, setValue] = useState("30");
  return (
    <Segmented
      label="Período"
      value={value}
      onChange={setValue}
      options={[
        { value: "7", label: "7 dias" },
        { value: "30", label: "30 dias" },
        { value: "90", label: "90 dias" },
      ]}
    />
  );
}

describe("componentes", () => {
  it("campo com erro: aria-invalid e mensagem ligada", () => {
    render(
      <Field label="Host" error="host: precisa ser https">
        <TextInput />
      </Field>,
    );
    const input = screen.getByLabelText("Host");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input).toHaveAccessibleDescription("host: precisa ser https");
  });

  it("segmentado responde às setas", async () => {
    render(<Period />);
    await userEvent.click(screen.getByRole("radio", { name: "30 dias" }));
    await userEvent.keyboard("{ArrowRight}{Enter}");
    expect(screen.getByRole("radio", { name: "90 dias" })).toHaveFocus();
  });

  it("nenhuma violação do axe num formulário composto", async () => {
    const { container } = render(
      <main>
        <h1>Formulário</h1>
        <Notice tone="warn" title="Sobreposição inativa">
          O deploy mudou a seção.
        </Notice>
        <Field label="Chave pública" installation>
          <TextInput readOnly value="pk-lf-1" />
        </Field>
        <Field label="Modelo" help="provider/modelo">
          <TextInput />
        </Field>
        <Checkbox label="Permitida" defaultChecked />
        <Toggle label="Enviar traces" checked onChange={() => {}} />
        <Period />
        <Badge tone="ok" dot>
          Disponível
        </Badge>
        <InstallationBadge />
        <Button variant="primary" icon="mais">
          Novo preço
        </Button>
        <Button icon="atualizar" aria-label="Testar modelo" />
      </main>,
    );
    expect(await violations(container)).toEqual([]);
  });
});
