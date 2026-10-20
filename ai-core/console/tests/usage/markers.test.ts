import { describe, expect, it } from "vitest";

import { placeMarkers } from "../../src/features/usage/DailyCostChart";

const GAP = 6;

function spans(
  placed: ReturnType<typeof placeMarkers<{ left: number; text: string }>>,
  widths: Record<string, number>,
) {
  return placed.map((marker) => {
    const size = widths[marker.text] ?? 0;
    const begin = marker.flip ? marker.left - GAP - size : marker.left + GAP;
    return { ...marker, begin, end: begin + size };
  });
}

describe("rótulos dos marcos do gráfico (013 FR-010)", () => {
  it("três marcos próximos na largura do tablet: nenhuma linha atravessa um rótulo", () => {
    const texts = {
      preco: "03/10 · preço novo do gpt-4.1-mini",
      documentos: "07/10 · ana trocou a geração do documentos",
      geral: "14/10 · ana trocou modelos do geral",
    };
    const markers = [
      { left: 443, text: texts.preco },
      { left: 519, text: texts.documentos },
      { left: 650, text: texts.geral },
    ];
    const widths = { [texts.preco]: 199, [texts.documentos]: 261, [texts.geral]: 209 };
    const placed = spans(placeMarkers(markers, 660, widths), widths);
    for (const label of placed) {
      expect(label.begin).toBeGreaterThanOrEqual(0);
      expect(label.end).toBeLessThanOrEqual(660);
      for (const other of placed) {
        if (other === label) {
          continue;
        }
        // a linha de `other` desce da fileira dele até o eixo: não pode passar por um rótulo nessa faixa
        const crosses = label.row >= other.row && other.left > label.begin && other.left < label.end;
        expect(crosses).toBe(false);
        if (label.row === other.row) {
          expect(label.end <= other.begin || label.begin >= other.end).toBe(true);
        }
      }
    }
  });

  it("um marco só fica na primeira fileira, à direita da linha quando cabe", () => {
    const [placed] = placeMarkers([{ left: 100, text: "02/10 · preço novo" }], 800, { "02/10 · preço novo": 120 });
    expect(placed).toMatchObject({ row: 0, flip: false });
  });
});
