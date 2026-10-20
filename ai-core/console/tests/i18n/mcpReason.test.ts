import { describe, expect, it } from "vitest";

import { mcpReason } from "../../src/i18n/pt-BR";

describe("motivo de servidor MCP indisponível (013 FR-014)", () => {
  it("falta de credencial vira a ação do operador", () => {
    expect(mcpReason("credencial 'planilhas' não configurada", "curta")).toBe("Credencial ausente na instalação");
    expect(mcpReason("credencial 'fin_token' não configurada", "completa")).toBe(
      "Credencial ausente: defina AI_CORE_MCP_SECRET_FIN_TOKEN na instalação.",
    );
  });

  it("outro motivo segue como veio, em frase", () => {
    expect(mcpReason("o servidor não respondeu", "curta")).toBe("O servidor não respondeu");
    expect(mcpReason("o servidor não respondeu", "completa")).toBe("O servidor não respondeu.");
  });
});
