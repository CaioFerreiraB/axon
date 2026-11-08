/** Textos compartilhados entre telas (013 FR-016). O texto próprio de cada tela fica junto dela. */

export const NAV = [
  { to: "/uso", label: "Uso e custo", icon: "uso" },
  { to: "/meio-ambiente", label: "Meio ambiente", icon: "folha" },
  { to: "/assistentes", label: "Assistentes", icon: "assistente" },
  { to: "/servidores-mcp", label: "Servidores MCP", icon: "mcp" },
  { to: "/observabilidade", label: "Observabilidade", icon: "observabilidade" },
  { to: "/acesso", label: "Acesso", icon: "acesso" },
] as const;

/** A barra inferior do celular (013 FR-047, R38): as quatro seções primárias; as outras ficam na folha "Mais". */
export const NAV_PRIMARY = [
  { to: "/uso", label: "Uso", icon: "uso" },
  { to: "/assistentes", label: "Assistentes", icon: "assistente" },
  { to: "/servidores-mcp", label: "MCP", icon: "mcp" },
  { to: "/acesso", label: "Acesso", icon: "acesso" },
] as const;

export const NAV_SECONDARY = NAV.filter((item) => !NAV_PRIMARY.some((primary) => primary.to === item.to));

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
      : `Credencial ausente: defina AXON_MCP_SECRET_${(missing[1] ?? "").toUpperCase()} na instalação.`;
  }
  const text = reason.trim();
  const capital = text.charAt(0).toUpperCase() + text.slice(1);
  return form === "curta" || /[.!?]$/.test(capital) ? capital : `${capital}.`;
}

/** O nome de cada seção sobreponível nas telas (013 FR-004, FR-005; US10). */
export const SECTION_TEXT: Record<"models" | "mcp" | "auth", string> = {
  models: "Modelos",
  mcp: "MCP",
  auth: "Permissões",
};

// --- incremento 9.7: escopos de chave e o relatório do apagamento (013 R31, R33) -----------------------------------

/** Os escopos de chave em português (ADR-057). A administração só a linha de comando concede. */
export const SCOPE_TEXT: Record<"inference" | "users" | "admin", string> = {
  inference: "Uso de inferência",
  users: "Gerenciar usuários e grupos",
  admin: "Administração",
};

/** Os escopos que a console concede, na ordem do diálogo (sem a administração; ADR-057 item 3). */
export const GRANTABLE_SCOPES = ["inference", "users"] as const;

/** As partes da plataforma no relatório do apagamento; uma parte nova aparece pelo nome cru. */
const MODULE_TEXT: Record<string, string> = {
  assistants: "Assistants e chaves",
  mcp: "Servidores MCP",
  conversations: "Conversas",
  audit: "Auditoria de tools",
  observability: "Preços e ajustes",
  identity: "Conta e sessões",
};

const COUNT_TEXT: Record<string, string> = {
  user_assistants: "Assistants pessoais",
  api_keys: "chaves de API",
  override_entries: "permissões em Assistants",
  authored: "registros com o autor trocado",
  servers: "servidores pessoais",
  conversations: "conversas",
  attachments: "imagens",
  audit_records: "registros de auditoria com o autor trocado",
  prices: "preços com o autor trocado",
  destination_settings: "ajustes com o autor trocado",
  account: "conta",
  sessions: "sessões",
  refresh_tokens: "tokens de renovação",
  codes: "códigos de login",
  pending: "logins em andamento",
};

export function moduleText(name: string): string {
  return MODULE_TEXT[name] ?? name;
}

export function countText(name: string): string {
  return COUNT_TEXT[name] ?? name;
}
