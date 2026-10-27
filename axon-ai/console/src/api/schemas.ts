/**
 * Os formatos da API de administração (specs/008-core-http-api/contracts/admin-api.md) como esquemas `zod`.
 * Resposta que não casa com o esquema é erro explícito: pega divergência de contrato (013 R6). Nenhuma regra de
 * negócio aqui — só forma.
 */

import { z } from "zod";

const instant = z.string().min(1);
const decimal = z.string().regex(/^-?\d+(\.\d+)?$/, "valor decimal");
const settingSource = z.enum(["installation", "runtime", "default"]);

export const meSchema = z.object({
  subject: z.string(),
  username: z.string(),
  name: z.string(),
  groups: z.array(z.string()),
  scheme: z.enum(["oidc", "api_key"]),
  instance: z.object({ name: z.string(), logo_url: z.string().nullable(), custom: z.boolean() }),
});
export type Me = z.infer<typeof meSchema>;

// --- Assistants de sistema (003) ------------------------------------------------------------------------------------

export const ROLES = ["generation", "controller", "rerank"] as const;
export type Role = (typeof ROLES)[number];
export const SECTIONS = ["models", "mcp", "auth"] as const;
export type Section = (typeof SECTIONS)[number];

/** Um papel: `provider/modelo`, ou `{model, vision: true}` quando o modelo enxerga imagem — a forma do YAML (ADR-044). */
const roleValue = z.union([z.string(), z.object({ model: z.string(), vision: z.boolean().optional() })]);
export type RoleValue = z.infer<typeof roleValue>;
const modelsMap = z.record(z.string(), roleValue);
export type ModelsMap = z.infer<typeof modelsMap>;

/** O `provider/modelo` de um papel, nas duas formas. */
export function refOfRole(value: RoleValue | undefined): string | undefined {
  return value === undefined || typeof value === "string" ? value : value.model;
}

/** O papel declara `vision` (ADR-044, item 10). */
export function sees(value: RoleValue | undefined): boolean {
  return typeof value === "object" && value.vision === true;
}
export const mcpSelectionSchema = z.object({
  aliases: z.array(z.string()),
  allowed: z.array(z.string()),
  write: z.array(z.string()),
});
export type McpSelection = z.infer<typeof mcpSelectionSchema>;

/** Quem pode usar um Assistant (ADR-040): os esquemas aceitos e as entradas de `allow`. */
export const SCHEMES = ["oidc", "api_key"] as const;
export type Scheme = (typeof SCHEMES)[number];
export const authSelectionSchema = z.object({ schemes: z.array(z.enum(SCHEMES)), allow: z.array(z.string()) });
export type AuthSelection = z.infer<typeof authSelectionSchema>;

const payloadSchema = z.union([authSelectionSchema, mcpSelectionSchema, modelsMap]);

export const overrideViewSchema = z.object({
  section: z.enum(SECTIONS),
  state: z.enum(["active", "inactive"]),
  reason: z.string().nullable(),
  version: z.number().int(),
  updated_by: z.string(),
  updated_at: instant,
  payload: payloadSchema.nullable(),
});
export type OverrideView = z.infer<typeof overrideViewSchema>;

/** O conteúdo de uma sobreposição de MCP. */
export function isMcpPayload(payload: OverrideView["payload"]): payload is McpSelection {
  return payload !== null && Array.isArray((payload as McpSelection).aliases);
}

/** O conteúdo de uma sobreposição de permissões. */
export function isAuthPayload(payload: OverrideView["payload"]): payload is AuthSelection {
  return payload !== null && Array.isArray((payload as AuthSelection).schemes);
}

/** O conteúdo de uma sobreposição de modelos: papel → modelo (com `vision`, na forma de objeto). */
export function isModelsPayload(payload: OverrideView["payload"]): payload is ModelsMap {
  return payload !== null && !isMcpPayload(payload) && !isAuthPayload(payload);
}

export const assistantViewSchema = z.object({
  name: z.string(),
  description: z.string().nullable(),
  visibility: z.enum(["public", "private"]),
  flow: z.string().nullable(),
  status: z.object({ available: z.boolean(), reasons: z.array(z.string()) }),
  overridable: z.array(z.enum(SECTIONS)),
  required_roles: z.array(z.string()),
  allow: z.array(z.string()),
  yaml: z.object({ models: modelsMap, mcp: mcpSelectionSchema, auth: authSelectionSchema }),
  overrides: z.array(overrideViewSchema),
  effective: z.object({ models: modelsMap, mcp: mcpSelectionSchema, auth: authSelectionSchema }),
});
export type AssistantView = z.infer<typeof assistantViewSchema>;
export const assistantListSchema = z.object({ data: z.array(assistantViewSchema) });

export const historyEntrySchema = z.object({
  section: z.enum(SECTIONS),
  action: z.enum(["saved", "discarded"]),
  payload: payloadSchema.nullable(),
  version: z.number().int(),
  actor: z.string(),
  at: instant,
});
export type HistoryEntry = z.infer<typeof historyEntrySchema>;
export const historySchema = z.object({ data: z.array(historyEntrySchema) });

export const modelCheckSchema = z.object({
  available: z.boolean(),
  detail: z.string().nullable(),
  latency_ms: z.number(),
});
export type ModelCheck = z.infer<typeof modelCheckSchema>;

/** Um provider registrado e se está pronto (ADR-035): o remoto pela credencial, o local se responde. `reports_cost`: ele
 * informa o custo de cada chamada, e não há preço de tabela a cadastrar (ADR-036). */
export const providerSchema = z.object({
  name: z.string(),
  ready: z.boolean(),
  detail: z.string().nullable(),
  reports_cost: z.boolean(),
});
export type Provider = z.infer<typeof providerSchema>;
export const providerListSchema = z.object({ data: z.array(providerSchema) });

// --- servidores MCP (007) -------------------------------------------------------------------------------------------

export const mcpServerSchema = z.object({
  alias: z.string(),
  scope: z.enum(["global", "user"]),
  owner: z.string().nullable(),
  transport: z.enum(["http", "sse", "stdio"]).nullable(),
  endpoint: z.string().nullable(),
  command: z.string().nullable(),
  description: z.string().nullable(),
  auth: z.object({ type: z.enum(["none", "bearer"]), credential: z.string().nullable() }),
  enabled: z.boolean(),
  user_access: z.boolean(),
  policy: z
    .object({
      allowed_tools: z.array(z.string()),
      write_tools: z.array(z.string()),
      timeout_ms: z.number().int(),
      max_response_bytes: z.number().int(),
    })
    .nullable(),
  origin: z.enum(["file", "registry"]),
  available: z.boolean(),
  reason: z.string().nullable(),
  created_at: instant.nullable(),
  updated_at: instant.nullable(),
});
export type McpServer = z.infer<typeof mcpServerSchema>;
export const mcpListSchema = z.object({ data: z.array(mcpServerSchema) });

export const mcpHealthSchema = z.object({
  alias: z.string(),
  ok: z.boolean(),
  detail: z.string().nullable(),
  tools: z.array(z.string()),
  missing: z.array(z.string()),
});
export type McpHealth = z.infer<typeof mcpHealthSchema>;

// --- uso e preços (009) ---------------------------------------------------------------------------------------------

export const usageRowSchema = z.object({
  key: z.string().nullable(),
  calls: z.number().int(),
  requests: z.number().int(),
  input_tokens: z.number().int(),
  output_tokens: z.number().int(),
  cost: decimal.nullable(),
  priced: z.boolean(),
});
export type UsageRow = z.infer<typeof usageRowSchema>;

export const usageReportSchema = z.object({
  query: z.object({
    from: z.string(),
    to: z.string(),
    tz: z.string(),
    by: z.enum(["model", "assistant"]),
    origin: z.enum(["production", "evaluation", "all"]),
  }),
  currency: z.literal("USD"),
  totals: z.array(usageRowSchema),
  total_cost: decimal.nullable(),
  requests: z.number().int(),
  incomplete: z.boolean(),
  previous_total_cost: decimal.nullable(),
  /** `requests` do dia são as distintas (ADR-036): somar as linhas por modelo contaria duas vezes. */
  days: z.array(z.object({ day: z.string(), requests: z.number().int(), rows: z.array(usageRowSchema) })),
});
export type UsageReport = z.infer<typeof usageReportSchema>;
export type UsageGrouping = UsageReport["query"]["by"];
export type UsageOrigin = UsageReport["query"]["origin"];

export const priceSchema = z.object({
  provider: z.string(),
  model: z.string(),
  input: decimal,
  output: decimal,
  effective_from: z.string(),
  state: z.enum(["current", "superseded", "scheduled"]),
  created_by: z.string(),
  created_at: instant,
});
export type Price = z.infer<typeof priceSchema>;
export const priceListSchema = z.object({ data: z.array(priceSchema) });
export const unpricedSchema = z.object({ data: z.array(z.string()) });

// --- observabilidade (009) ------------------------------------------------------------------------------------------

export const destinationHealthSchema = z.object({
  name: z.string(),
  state: z.enum(["ok", "degraded", "off"]),
  dropped_24h: z.number().int(),
  last_error: z.string().nullable(),
  last_sent_at: instant.nullable(),
});
export type DestinationHealth = z.infer<typeof destinationHealthSchema>;

export const observabilitySchema = z.object({
  langfuse: z.object({
    enabled: z.boolean(),
    host: z.string().nullable(),
    public_key: z.string().nullable(),
    secret_set: z.boolean(),
    sources: z.object({
      enabled: settingSource,
      host: settingSource,
      public_key: settingSource,
      secret_key: settingSource,
    }),
  }),
  capture_content: z.boolean(),
  capture_source: settingSource,
  version: z.number().int(),
  health: z.array(destinationHealthSchema),
});
export type Observability = z.infer<typeof observabilitySchema>;
export type SettingSource = z.infer<typeof settingSource>;

export const connectionCheckSchema = z.object({ ok: z.boolean(), detail: z.string() });
export type ConnectionCheck = z.infer<typeof connectionCheckSchema>;

// --- contas, grupos e login (012) -----------------------------------------------------------------------------------

export const accountSchema = z.object({
  id: z.string(),
  username: z.string(),
  email: z.string(),
  name: z.string(),
  groups: z.array(z.string()),
  active: z.boolean(),
  temporary_password: z.boolean(),
  has_password: z.boolean(),
  google_linked: z.boolean(),
  created_at: instant,
  updated_at: instant,
  updated_by: z.string().nullable(),
  last_login_at: instant.nullable(),
  version: z.number().int(),
});
export type Account = z.infer<typeof accountSchema>;
export const accountPageSchema = z.object({ data: z.array(accountSchema), next_cursor: z.string().nullable() });
export type AccountPage = z.infer<typeof accountPageSchema>;

/** Só a resposta que define a senha a traz (`POST /users`, `POST /users/{u}/password`); nunca vai para o cache. */
export const issuedSchema = z.object({ account: accountSchema, temporary_password: z.string().optional() });
export type Issued = z.infer<typeof issuedSchema>;

export const groupSchema = z.object({ name: z.string(), members: z.number().int(), protected: z.boolean() });
export type Group = z.infer<typeof groupSchema>;
export const groupListSchema = z.object({ data: z.array(groupSchema) });

export const loginSettingsSchema = z.object({
  google_enabled: z.boolean(),
  google_source: settingSource,
  google_configured: z.boolean(),
  google_redirect_uri: z.string(),
  google_client_id: z.string().nullable(),
  google_hosted_domain: z.string().nullable(),
  version: z.number().int(),
});
export type LoginSettings = z.infer<typeof loginSettingsSchema>;

// --- chaves e saúde -------------------------------------------------------------------------------------------------

export const apiKeySchema = z.object({
  key_id: z.string(),
  subject: z.string(),
  groups: z.array(z.string()),
  label: z.string().nullable(),
  created_at: instant,
  revoked_at: instant.nullable(),
  rotated_at: instant.nullable(),
});
export type ApiKey = z.infer<typeof apiKeySchema>;
export const apiKeyListSchema = z.object({ data: z.array(apiKeySchema) });
/** A resposta da emissão e da rotação: a única que traz a chave em claro (ADR-040). Nunca vai para o cache (013 R23). */
export const issuedKeySchema = apiKeySchema.extend({ key: z.string() });
export type IssuedKey = z.infer<typeof issuedKeySchema>;

export const healthSchema = z.object({
  status: z.enum(["ok", "degraded", "down"]),
  items: z.array(z.object({ name: z.string(), ok: z.boolean(), critical: z.boolean(), detail: z.string().nullable() })),
});
export type Health = z.infer<typeof healthSchema>;

// --- envelope de erro -----------------------------------------------------------------------------------------------

export const errorEnvelopeSchema = z.object({
  error: z.object({
    message: z.string(),
    type: z.string().optional(),
    code: z.string().nullable().optional(),
    param: z.string().nullable().optional(),
    current_version: z.number().int().nullable().optional(),
  }),
});
