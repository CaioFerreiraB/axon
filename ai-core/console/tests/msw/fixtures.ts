/** Dados dos testes de componente: os exemplos do contrato da 008 (admin-api.md) e do desenho aprovado. */

import type {
  AccountPage,
  AssistantView,
  Group,
  LoginSettings,
  McpHealth,
  McpServer,
  Me,
  Observability,
  Price,
  Provider,
  UsageReport,
} from "../../src/api/schemas";

export const me: Me = {
  subject: "user:ana",
  username: "ana",
  name: "Ana Souza",
  groups: ["admin", "equipe"],
  scheme: "oidc",
  instance: { name: "Agentic", logo_url: null },
};

export const geral: AssistantView = {
  name: "geral",
  description: "Uso geral, com ferramentas",
  visibility: "public",
  flow: "agentic",
  status: { available: true, reasons: [] },
  overridable: ["mcp", "models"],
  required_roles: ["generation", "controller"],
  allow: ["openrouter/*"],
  yaml: {
    models: { generation: "openrouter/openai/gpt-4.1-nano", controller: "openrouter/openai/gpt-4.1-nano" },
    mcp: { aliases: [], allowed: [], write: [] },
  },
  overrides: [
    {
      section: "models",
      state: "active",
      reason: null,
      version: 3,
      updated_by: "user:ana",
      updated_at: "2026-10-07T17:32:00+00:00",
      payload: { generation: "openrouter/openai/gpt-4.1-mini", controller: "openrouter/openai/gpt-4.1-nano" },
    },
  ],
  effective: {
    models: { generation: "openrouter/openai/gpt-4.1-mini", controller: "openrouter/openai/gpt-4.1-nano" },
    mcp: { aliases: [], allowed: [], write: [] },
  },
};

export const rascunho: AssistantView = {
  name: "rascunho",
  description: "Conversa simples, local",
  visibility: "public",
  flow: "chat",
  status: { available: true, reasons: [] },
  overridable: [],
  required_roles: ["generation"],
  allow: ["ollama/*"],
  yaml: { models: { generation: "ollama/qwen3:1.7b" }, mcp: { aliases: [], allowed: [], write: [] } },
  overrides: [],
  effective: { models: { generation: "ollama/qwen3:1.7b" }, mcp: { aliases: [], allowed: [], write: [] } },
};

export const documentos: AssistantView = {
  ...rascunho,
  name: "documentos",
  description: "Perguntas sobre documentos",
  visibility: "private",
  overridable: ["models"],
  overrides: [
    {
      section: "models",
      state: "inactive",
      reason: "o deploy mudou a seção",
      version: 2,
      updated_by: "user:ana",
      updated_at: "2026-10-07T10:00:00+00:00",
      payload: { generation: "ollama/gemma3:1b" },
    },
  ],
};

export const servers: McpServer[] = [
  {
    alias: "arquivos",
    scope: "global",
    owner: null,
    transport: "http",
    endpoint: "https://mcp.exemplo.org/arquivos",
    command: null,
    description: "Arquivos da equipe",
    auth: { type: "none", credential: null },
    enabled: true,
    user_access: true,
    policy: {
      allowed_tools: ["listar", "ler", "mover"],
      write_tools: ["mover"],
      timeout_ms: 30000,
      max_response_bytes: 16384,
    },
    origin: "registry",
    available: true,
    reason: null,
    created_at: "2026-10-01T10:00:00+00:00",
    updated_at: "2026-10-01T10:00:00+00:00",
  },
  {
    alias: "planilhas",
    scope: "global",
    owner: null,
    transport: "http",
    endpoint: "https://planilhas.interno/mcp",
    command: null,
    description: "Planilhas",
    auth: { type: "bearer", credential: "planilhas" },
    enabled: true,
    user_access: false,
    policy: { allowed_tools: ["ler"], write_tools: [], timeout_ms: 30000, max_response_bytes: 16384 },
    origin: "file",
    available: false,
    reason: "credencial 'planilhas' não configurada",
    created_at: null,
    updated_at: null,
  },
];

export const healths: Record<string, McpHealth> = {
  arquivos: { alias: "arquivos", ok: true, detail: null, tools: ["listar", "ler", "mover"], missing: [] },
  planilhas: { alias: "planilhas", ok: false, detail: "credencial ausente", tools: [], missing: ["ler"] },
};

export const report: UsageReport = {
  query: { from: "2026-10-07", to: "2026-10-13", tz: "America/Sao_Paulo", by: "model", origin: "production" },
  currency: "USD",
  totals: [
    {
      key: "openrouter/openai/gpt-4.1-mini",
      calls: 3118,
      requests: 1802,
      input_tokens: 11400000,
      output_tokens: 1900000,
      cost: "33.520000",
      priced: true,
    },
    {
      key: "ollama/qwen3:1.7b",
      calls: 878,
      requests: 400,
      input_tokens: 1700000,
      output_tokens: 300000,
      cost: null,
      priced: false,
    },
  ],
  total_cost: "33.520000",
  requests: 2202,
  incomplete: true,
  previous_total_cost: "31.000000",
  days: [
    {
      day: "2026-10-10",
      rows: [
        {
          key: "openrouter/openai/gpt-4.1-mini",
          calls: 500,
          requests: 300,
          input_tokens: 1,
          output_tokens: 1,
          cost: "2.080000",
          priced: true,
        },
      ],
    },
  ],
};

export const emptyReport: UsageReport = {
  ...report,
  totals: [],
  total_cost: "0",
  requests: 0,
  incomplete: false,
  previous_total_cost: "0",
  days: [],
};

/** Só o OpenRouter pronto: o Ollama fora do ar e a OpenAI sem chave (ADR-035). */
export const providers: Provider[] = [
  { name: "ollama", ready: false, detail: "provider inalcançável em http://localhost:11434/v1" },
  { name: "openai", ready: false, detail: "sem credencial: defina AI_CORE_OPENAI_API_KEY" },
  { name: "openrouter", ready: true, detail: null },
];

export const prices: Price[] = [
  {
    provider: "openrouter",
    model: "openai/gpt-4.1-mini",
    input: "0.40",
    output: "1.60",
    effective_from: "2026-10-01",
    state: "current",
    created_by: "user:ana",
    created_at: "2026-10-01T12:00:00+00:00",
  },
];

export const observability: Observability = {
  langfuse: {
    enabled: true,
    host: "https://cloud.langfuse.com",
    public_key: "pk-lf-1",
    secret_set: true,
    sources: { enabled: "runtime", host: "runtime", public_key: "runtime", secret_key: "runtime" },
  },
  capture_content: false,
  capture_source: "default",
  version: 4,
  health: [{ name: "langfuse", state: "ok", dropped_24h: 0, last_error: null, last_sent_at: null }],
};

export const accounts: AccountPage = {
  data: [
    {
      id: "id-ana",
      username: "ana",
      email: "ana@exemplo.org",
      name: "Ana Souza",
      groups: ["admin", "equipe"],
      active: true,
      temporary_password: false,
      has_password: true,
      google_linked: true,
      created_at: "2026-10-01T10:00:00+00:00",
      updated_at: "2026-10-01T10:00:00+00:00",
      updated_by: "cli",
      last_login_at: null,
      version: 1,
    },
  ],
  next_cursor: null,
};

export const groups: Group[] = [
  { name: "admin", members: 1, protected: true },
  { name: "equipe", members: 1, protected: false },
];

export const login: LoginSettings = {
  google_enabled: false,
  google_source: "default",
  google_configured: false,
  google_redirect_uri: "https://agentic.exemplo.org/oauth2/google/callback",
  google_client_id: null,
  google_hosted_domain: null,
  version: 0,
};
