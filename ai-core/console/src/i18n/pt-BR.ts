/** Textos compartilhados entre telas (013 FR-016). O texto próprio de cada tela fica junto dela. */

export const NAV = [
  { to: "/uso", label: "Uso e custo", icon: "uso" },
  { to: "/assistentes", label: "Assistentes", icon: "assistente" },
  { to: "/servidores-mcp", label: "Servidores MCP", icon: "mcp" },
  { to: "/observabilidade", label: "Observabilidade", icon: "observabilidade" },
  { to: "/acesso", label: "Acesso", icon: "acesso" },
] as const;

export const ROLE_TEXT: Record<string, string> = {
  generation: "Escreve a resposta",
  controller: "Decide a próxima ação",
  rerank: "Opcional",
};

export const ORIGIN_TEXT = { production: "produção", evaluation: "avaliação", all: "produção e avaliação" } as const;

export const VISIBILITY_TEXT = { public: "público", private: "privado" } as const;

export const DEPLOY_ONLY = "Só muda por novo deploy";
export const INSTALLATION = "Definido na instalação";

export const STATE_TEXT = {
  available: "Disponível",
  unavailable: "Indisponível",
  overridden: "Sobreposto",
  inactive: "Sobreposição inativa",
  locked: "Travado",
  unpriced: "Sem preço",
} as const;

const MISSING_CREDENTIAL = /^credencial '([a-z0-9_]+)' (?:não configurada|ausente)/i;

/** O motivo de um servidor MCP indisponível, em frase. A falta de credencial (007) vira o que o operador faz:
 * curta na lista, com o nome da variável no detalhe. */
export function mcpReason(reason: string, form: "curta" | "completa"): string {
  const missing = MISSING_CREDENTIAL.exec(reason.trim());
  if (missing) {
    return form === "curta"
      ? "Credencial ausente na instalação"
      : `Credencial ausente: defina AI_CORE_MCP_SECRET_${(missing[1] ?? "").toUpperCase()} na instalação.`;
  }
  const text = reason.trim();
  const capital = text.charAt(0).toUpperCase() + text.slice(1);
  return form === "curta" || /[.!?]$/.test(capital) ? capital : `${capital}.`;
}
