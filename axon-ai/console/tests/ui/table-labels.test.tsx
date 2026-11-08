/** 013 FR-048 (R39): no celular a tabela vira lista, e cada célula leva o rótulo da coluna, inclusive as linhas que
 * chegam depois e as colunas com `colSpan`. */

import { render, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Table } from "../../src/ui/Table";

function Prices({ rows }: { rows: string[] }) {
  return (
    <Table caption="Preços">
      <thead>
        <tr>
          <th scope="col">Modelo</th>
          <th scope="col" colSpan={2}>
            Entrada e saída
          </th>
          <th scope="col">
            <span className="visually-hidden">Ações</span>
          </th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr key={row}>
            <th scope="row">{row}</th>
            <td>0,10</td>
            <td>0,40</td>
            <td>…</td>
          </tr>
        ))}
      </tbody>
      <tfoot>
        <tr>
          <td>Total</td>
          <td colSpan={3}>US$ 1</td>
        </tr>
      </tfoot>
    </Table>
  );
}

const labels = (row: Element | undefined) =>
  Array.from(row?.children ?? []).map((cell) => (cell as HTMLElement).dataset.label);

describe("Table no celular", () => {
  it("põe o rótulo da coluna em cada célula", () => {
    const { container } = render(<Prices rows={["gpt-4.1-mini"]} />);
    const [body, foot] = container.querySelectorAll("tbody tr, tfoot tr");
    expect(labels(body)).toEqual(["Modelo", "Entrada e saída", "Entrada e saída", "Ações"]);
    expect(labels(foot)).toEqual(["Modelo", "Entrada e saída"]);
    expect(container.firstElementChild?.className).toContain("stack");
  });

  it("rotula as linhas que chegam depois", async () => {
    const { container, rerender } = render(<Prices rows={["a"]} />);
    rerender(<Prices rows={["a", "b"]} />);
    await waitFor(() =>
      expect(labels(container.querySelectorAll("tbody tr")[1])).toEqual([
        "Modelo",
        "Entrada e saída",
        "Entrada e saída",
        "Ações",
      ]),
    );
  });
});
