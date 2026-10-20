/** T009 — os esquemas aceitam os exemplos do contrato da 008 e recusam variações (013 R6). */

import { describe, expect, it } from "vitest";

import * as s from "../../src/api/schemas";
import * as f from "../msw/fixtures";

describe("esquemas do contrato", () => {
  it.each([
    ["me", s.meSchema, f.me],
    ["AssistantView ativo", s.assistantViewSchema, f.geral],
    ["AssistantView inativo", s.assistantViewSchema, f.documentos],
    ["servidor MCP", s.mcpServerSchema, f.servers[0]],
    ["saúde do MCP", s.mcpHealthSchema, f.healths.arquivos],
    ["relatório de uso", s.usageReportSchema, f.report],
    ["preço", s.priceSchema, f.prices[0]],
    ["observabilidade", s.observabilitySchema, f.observability],
    ["página de contas", s.accountPageSchema, f.accounts],
    ["grupo", s.groupSchema, f.groups[0]],
    ["login", s.loginSettingsSchema, f.login],
  ])("aceita %s", (_name, schema, example) => {
    expect(schema.safeParse(example).success).toBe(true);
  });

  it("recusa campo faltando e tipo errado", () => {
    const { name: _name, ...semNome } = f.geral;
    expect(s.assistantViewSchema.safeParse(semNome).success).toBe(false);
    expect(s.usageReportSchema.safeParse({ ...f.report, total_cost: 41.87 }).success).toBe(false);
    expect(s.priceSchema.safeParse({ ...f.prices[0], state: "vigente" }).success).toBe(false);
    expect(s.meSchema.safeParse({ ...f.me, scheme: "senha" }).success).toBe(false);
  });

  it("a senha temporária é opcional na resposta de cadastro (só Google)", () => {
    expect(s.issuedSchema.safeParse({ account: f.accounts.data[0] }).success).toBe(true);
    expect(s.issuedSchema.safeParse({ account: f.accounts.data[0], temporary_password: "k7m2-qx9p" }).success).toBe(
      true,
    );
  });

  it("o conteúdo de uma sobreposição de MCP é distinguível do de modelos", () => {
    expect(s.isMcpPayload({ aliases: ["a"], allowed: [], write: [] })).toBe(true);
    expect(s.isMcpPayload({ generation: "x/y" })).toBe(false);
    expect(s.isMcpPayload(null)).toBe(false);
  });
});
