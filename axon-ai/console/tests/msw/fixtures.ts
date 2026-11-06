/** Dados dos testes de componente: os exemplos do contrato da 008 (admin-api.md) e do desenho aprovado. */

import type {
  AccountPage,
  ApiKey,
  AssistantView,
  DeletionReport,
  Group,
  ImpactReport,
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
  instance: { name: "Axon", logo_url: null, custom: false },
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
    auth: { schemes: ["oidc"], allow: ["*"] },
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
    auth: { schemes: ["oidc"], allow: ["*"] },
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
  yaml: {
    models: { generation: "ollama/qwen3:1.7b" },
    mcp: { aliases: [], allowed: [], write: [] },
    auth: { schemes: ["oidc"], allow: ["*"] },
  },
  overrides: [],
  effective: {
    models: { generation: "ollama/qwen3:1.7b" },
    mcp: { aliases: [], allowed: [], write: [] },
    auth: { schemes: ["oidc"], allow: ["*"] },
  },
};

export const documentos: AssistantView = {
  ...rascunho,
  name: "documentos",
  description: "Perguntas sobre documentos",
  visibility: "private",
  overridable: ["models"],
  yaml: { ...rascunho.yaml, auth: { schemes: ["api_key"], allow: ["group:equipe"] } },
  effective: { ...rascunho.effective, auth: { schemes: ["api_key"], allow: ["group:equipe"] } },
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
    // Parcial: só parte das chamadas do OpenRouter informou o custo (as outras são anteriores ao ADR-035).
    {
      key: "openrouter/z-ai/glm-5.3-flash",
      calls: 22,
      requests: 10,
      input_tokens: 22902,
      output_tokens: 8454,
      cost: "0.007060",
      priced: false,
    },
  ],
  total_cost: "33.527060",
  requests: 2202,
  incomplete: true,
  previous_total_cost: "31.000000",
  days: [
    {
      day: "2026-10-10",
      requests: 300,
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
    // Uma requisição do agentic usa os dois modelos: 5 + 4 linhas, 6 requisições distintas.
    {
      day: "2026-10-11",
      requests: 6,
      rows: [
        {
          key: "openrouter/openai/gpt-4.1-mini",
          calls: 9,
          requests: 5,
          input_tokens: 4000,
          output_tokens: 1000,
          cost: "0.500000",
          priced: true,
        },
        {
          key: "openrouter/z-ai/glm-5.3-flash",
          calls: 8,
          requests: 4,
          input_tokens: 3000,
          output_tokens: 500,
          cost: "0.007060",
          priced: false,
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
  { name: "ollama", ready: false, detail: "provider inalcançável em http://localhost:11434/v1", reports_cost: false },
  { name: "openai", ready: false, detail: "sem credencial: defina AXON_OPENAI_API_KEY", reports_cost: false },
  { name: "openrouter", ready: true, detail: null, reports_cost: true },
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
      deleting: false,
    },
    {
      id: "id-bia",
      username: "bia",
      email: "bia@exemplo.org",
      name: "Bia Lima",
      groups: ["equipe"],
      active: true,
      temporary_password: false,
      has_password: true,
      google_linked: false,
      created_at: "2026-10-02T10:00:00+00:00",
      updated_at: "2026-10-02T10:00:00+00:00",
      updated_by: "user:ana",
      last_login_at: null,
      version: 3,
      deleting: false,
    },
  ],
  next_cursor: null,
};

/** O relatório de um apagamento completo de `bia` (008 FR-049): sem pseudônimo. */
export const deletionReport: DeletionReport = {
  username: "bia",
  complete: true,
  identity: { account: 1, authored: 0, codes: 0, pending: 0, refresh_tokens: 1, sessions: 2 },
  modules: [
    {
      name: "assistants",
      counts: { api_keys: 1, authored: 0, override_entries: 0, user_assistants: 2 },
      warnings: ["referências na configuração (assistants.yaml): escritor"],
      failed: false,
    },
    { name: "mcp", counts: { servers: 1 }, warnings: [], failed: false },
    { name: "conversations", counts: { attachments: 0, conversations: 3 }, warnings: [], failed: false },
    { name: "audit", counts: { audit_records: 0 }, warnings: [], failed: false },
    { name: "observability", counts: { destination_settings: 0, prices: 0 }, warnings: [], failed: false },
  ],
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

// --- US9 e US10 (ADR-040) -------------------------------------------------------------------------------------------

/** Público, com `auth` liberado e uma sobreposição ativa de permissões. */
export const aberto: AssistantView = {
  ...rascunho,
  name: "aberto",
  description: "Relatórios para sistemas",
  overridable: ["auth"],
  yaml: { ...rascunho.yaml, auth: { schemes: ["oidc"], allow: ["group:equipe"] } },
  overrides: [
    {
      section: "auth",
      state: "active",
      reason: null,
      version: 2,
      updated_by: "user:ana",
      updated_at: "2026-10-20T14:00:00+00:00",
      payload: { schemes: ["api_key", "oidc"], allow: ["group:equipe", "svc:relatorios", "group:sumiu"] },
    },
  ],
  effective: {
    ...rascunho.effective,
    auth: { schemes: ["api_key", "oidc"], allow: ["group:equipe", "svc:relatorios", "group:sumiu"] },
  },
};

/** Privado, com `auth` liberado e sem sobreposição. */
export const restrito: AssistantView = {
  ...rascunho,
  name: "restrito",
  description: "Só a equipe",
  visibility: "private",
  overridable: ["auth"],
  yaml: { ...rascunho.yaml, auth: { schemes: ["oidc"], allow: ["group:equipe"] } },
  effective: { ...rascunho.effective, auth: { schemes: ["oidc"], allow: ["group:equipe"] } },
};

export const apiKeys: ApiKey[] = [
  {
    key_id: "0000000000000003",
    subject: "svc:antigo",
    groups: [],
    scopes: ["inference"],
    label: null,
    created_at: "2026-09-01T10:00:00+00:00",
    revoked_at: "2026-10-01T10:00:00+00:00",
    rotated_at: null,
  },
  {
    key_id: "0000000000000001",
    subject: "svc:relatorios",
    groups: [],
    scopes: ["inference"],
    label: "prod",
    created_at: "2026-10-10T10:00:00+00:00",
    revoked_at: null,
    rotated_at: "2026-10-18T09:30:00+00:00",
  },
  {
    key_id: "0000000000000002",
    subject: "svc:relatorios",
    groups: [],
    scopes: ["users"],
    label: "homolog",
    created_at: "2026-10-11T10:00:00+00:00",
    revoked_at: null,
    rotated_at: null,
  },
  {
    key_id: "0000000000000004",
    subject: "user:caio",
    groups: ["admin"],
    scopes: ["admin", "inference"],
    label: "notebook",
    created_at: "2026-10-12T10:00:00+00:00",
    revoked_at: null,
    rotated_at: null,
  },
];

// --- impacto ambiental (013 US11; 008 US12) — ordens de grandeza do EcoLogits 0.11.3 ---------------------------------

const IMPACT_NAMES = [
  "energy_kwh",
  "gwp_kgco2eq",
  "adpe_kgsbeq",
  "pe_mj",
  "wcf_l",
  "gwp_usage",
  "gwp_embodied",
  "adpe_usage",
  "adpe_embodied",
  "pe_usage",
  "pe_embodied",
] as const;

/** Por chamada de um gpt-4.1-mini com 500 tokens de saída: GWP 0,03–0,10 g, energia 0,08–0,26 Wh. */
const PER_CALL: Record<(typeof IMPACT_NAMES)[number], number> = {
  energy_kwh: 0.00017,
  gwp_kgco2eq: 0.000067,
  adpe_kgsbeq: 3.1e-10,
  pe_mj: 0.0019,
  wcf_l: 0.00061,
  gwp_usage: 0.000065,
  gwp_embodied: 0.0000015,
  adpe_usage: 1.2e-11,
  adpe_embodied: 3e-10,
  pe_usage: 0.00188,
  pe_embodied: 0.00002,
};

export function impactMetrics(calls: number): ImpactReport["rows"][number]["metrics"] {
  // Texto decimal sem expoente, como a API manda (008 R65).
  const text = (value: number) => (value === 0 ? "0" : value.toFixed(15).replace(/0+$/, "").replace(/\.$/, ""));
  return Object.fromEntries(
    IMPACT_NAMES.map((name) => {
      const mean = PER_CALL[name] * calls;
      return [name, { min: text(mean * 0.5), max: text(mean * 1.5), mean: text(mean) }];
    }),
  ) as ImpactReport["rows"][number]["metrics"];
}

const coverage = (calls: number, unestimated = 0, approximate = 0) => ({
  calls,
  eligible: calls,
  estimated: calls - unestimated,
  approximate,
  unestimated,
});

export const impactReport: ImpactReport = {
  enabled: true,
  query: {
    from: "2026-09-14",
    to: "2026-10-13",
    tz: "America/Sao_Paulo",
    grain: "week",
    by: "model",
    origin: "production",
  },
  method: { ecologits_version: "0.11.3", tree_kg_co2e: "140", tree_years: 20 },
  clipped_from: null,
  totals: {
    metrics: impactMetrics(5_024),
    coverage: coverage(5_902, 878, 1_906),
    responses: 3_214,
    estimated_responses: 2_890,
    estimated_output_tokens: 2_512_000,
    trees: "0.0024",
  },
  previous_totals: {
    metrics: impactMetrics(4_600),
    coverage: coverage(5_300, 700, 1_700),
    responses: 2_900,
    estimated_responses: 2_600,
    estimated_output_tokens: 2_300_000,
    trees: "0.0022",
  },
  buckets: [
    ["2026-09-14", "2026-09-20", 1_102],
    ["2026-09-21", "2026-09-27", 1_215],
    ["2026-09-28", "2026-10-04", 1_330],
    ["2026-10-05", "2026-10-11", 1_120],
    ["2026-10-12", "2026-10-13", 257],
  ].map(([start, end, calls]) => ({
    start: String(start),
    end: String(end),
    calls: Number(calls),
    responses: Math.round(Number(calls) * 0.55),
    estimated_responses: Math.round(Number(calls) * 0.5),
    metrics: impactMetrics(Number(calls)),
    rows: [],
  })),
  rows: [
    {
      key: "openrouter/openai/gpt-4.1-mini",
      impact_model: "openai/gpt-4.1-mini",
      match: "exact",
      calls: 3_118,
      responses: 1_802,
      estimated_responses: 1_802,
      estimated_output_tokens: 1_559_000,
      coverage: coverage(3_118),
      metrics: impactMetrics(3_118),
    },
    {
      key: "openrouter/z-ai/glm-5.3-flash",
      impact_model: "mistralai/zai-glm-5-3",
      match: "approximate",
      calls: 1_906,
      responses: 1_088,
      estimated_responses: 1_088,
      estimated_output_tokens: 953_000,
      coverage: coverage(1_906, 0, 1_906),
      metrics: impactMetrics(1_906),
    },
    {
      key: "ollama/qwen3:1.7b",
      impact_model: null,
      match: null,
      calls: 878,
      responses: 324,
      estimated_responses: 0,
      estimated_output_tokens: 0,
      coverage: coverage(878, 878),
      metrics: impactMetrics(0),
    },
  ],
};
