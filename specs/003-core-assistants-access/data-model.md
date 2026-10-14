# Data model — 003 Assistants & Access (Fase 2)

Os tipos publicados vivem em `ai_core/assistants/api.py` e são imutáveis
(`@dataclass(frozen=True, slots=True, kw_only=True)`). `api.py` importa só a stdlib e os `api.py` de 002
(`Composition`), 005 (`FLOW_CHAT`) e 006 (`ModelPolicy`, `ModelRef`, `ModelRole` — só value objects, [ADR-016](../../docs/adr/ADR-016-grant-carrega-politica-de-modelos.md)). Os tipos internos vivem em `domain/`
e não saem do módulo.

## Vocabulário fechado

```python
type Surface = Literal["public", "private"]
type Scheme = Literal["oidc", "api_key"]
SCHEME_OF_SURFACE: Final[Mapping[Surface, Scheme]]   # public → oidc, private → api_key
USER_PREFIX: Final = "~"                              # nome de Assistant de usuário (FR-017)
DEFAULT_RPM: Final = 60                                # rpm quando o Assistant de sistema não declara (research R9)
WIDENING_FIELDS: Final[frozenset[str]]                 # campos de requisição que ampliariam capacidade (R13)
```

**Nome de Assistant**: `[a-z0-9][a-z0-9._-]{0,63}`. Nunca contém `/` (é o separador do id de modelo). De sistema: o
nome puro. De usuário: `~` + nome, único por dono.

**Seletor de acesso** (`auth.allow` e `match` de política): `*`, `user:<id>`, `svc:<id>` ou `group:<nome>`.

## Value objects publicados

### `Principal` — quem pede (FR-002)

| Campo | Tipo | Regra |
|---|---|---|
| `subject` | `str` | `user:<id>` ou `svc:<id>`; OIDC produz `user:<claim de subject>`; a chave de API, o subject de quem a recebeu |
| `scheme` | `Scheme` | esquema que autenticou |
| `groups` | `frozenset[str]` | nomes sem prefixo; `group:chefia` em `allow` casa com `"chefia"` aqui |

Avaliado a cada requisição; nada é guardado entre requisições (edge case "grupos mudam").

### `Limits`

| Campo | Tipo | Regra |
|---|---|---|
| `rpm` | `int` | ≥ 1; default `DEFAULT_RPM` em Assistant de sistema, o teto da política em Assistant de usuário |
| `max_iterations` | `int \| None` | ≥ 1; `None` = o default do motor (005, Fase 3) |
| `max_context_tokens` | `int \| None` | ≥ 1; `None` = o default do motor (Fase 5) |

### `ExecutionGrant` — a configuração efetiva de uma execução (FR-005)

| Campo | Tipo | Origem |
|---|---|---|
| `assistant` | `str` | nome resolvido (`~nome` para Assistant de usuário) |
| `principal` | `Principal` | quem pediu |
| `flow` | `str` | declarado; sem declaração e com um pack, o `preferred_flow` dele ou `chat` (US1 cen. 3) |
| `composition` | `Composition` (002) | `PackRegistry.compose(packs)`, na ordem declarada (US1 cen. 2) |
| `mcp_aliases` | `frozenset[str]` | exatamente os declarados; `mcp: []` → vazio (US1 cen. 1) |
| `collections` | `frozenset[str]` | exatamente as declaradas |
| `allowed_tools` | `frozenset[str] \| None` | filtro final do catálogo (004); `None` = sem filtro adicional |
| `write_tools` | `frozenset[str]` | vazio em Assistant público, sempre (FR-012) |
| `models` | `ModelPolicy` (006) | papéis declarados + allowlist; o modelo pedido substitui só `generation` (R5) |
| `limits` | `Limits` | do Assistant |

Propriedade derivada: `packs -> tuple[str, ...]` (= `composition.packs`). Satisfaz estruturalmente o `ExecutionGrant`
da 005 (`assistant`, `flow`, `composition`, `models`). **Invariante (SC-002)**: todo conjunto do grant está contido no
declarado pelo Assistant; nada da requisição entra no grant além do modelo de geração, e só dentro da allowlist.

### `AssistantSummary` — item da descoberta (FR-008)

| Campo | Tipo | Significado |
|---|---|---|
| `name` | `str` | como se endereça (`geral`, `~meu-rag`) |
| `origin` | `Literal["system", "user"]` | origem |
| `description` | `str \| None` | texto do operador ou do dono |
| `generation` | `ModelRef` | modelo de geração declarado |
| `allow` | `tuple[str, ...]` | allowlist de modelos, para a 008 montar os ids `<assistant>/<modelo>` |

### `UserAssistantDraft` — o que o usuário envia (FR-009)

| Campo | Tipo | Regra |
|---|---|---|
| `name` | `str` | sem o `~`; gramática de nome |
| `description` | `str \| None` | até 500 caracteres |
| `flow` | `str \| None` | ∈ `policy.flows`; ausente segue a regra do US1 cen. 3–4 |
| `packs` | `tuple[str, ...]` | ⊆ `policy.packs`, em ordem |
| `mcp` | `tuple[str, ...]` | ⊆ `McpDirectory.aliases(owner=dono)` |
| `collections` | `tuple[str, ...]` | ⊆ `policy.collections` ∩ `CollectionCatalog.names()` |
| `models` | `Mapping[ModelRole, ModelRef]` | ao menos `generation`; cada um casa com `policy.models_allow` |
| `limits` | `DraftLimits` (`rpm`, `max_iterations`, `max_context_tokens`, todos opcionais) | ≤ teto da política; ausente = teto |
| `allowed_tools` | `tuple[str, ...] \| None` | livre (o catálogo só existe na Fase 3) |
| `write_tools` | `tuple[str, ...]` | vazio, a menos que `policy.write_tools` seja verdadeiro |

Visibilidade (privada), esquemas (os dois) e `allow` (só o dono) **não** são campos: são fixos (clarificação 4).

### `UserAssistant` — visão do dono (gestão)

| Campo | Tipo | Significado |
|---|---|---|
| `name` | `str` | `~<nome>` |
| `owner` | `str` | subject do dono |
| `draft` | `UserAssistantDraft` | o que está salvo |
| `created_at`, `updated_at` | `datetime` | da porta `Clock` |
| `status` | `AssistantStatus` | calculado na leitura, contra a política aplicável ao Principal que lê (o próprio dono) |

### `AssistantStatus` e `ValidationReport` (FR-011)

| `AssistantStatus` | Tipo | |
|---|---|---|
| `name` | `str` | |
| `origin` | `Literal["system", "user"]` | |
| `available` | `bool` | |
| `reasons` | `tuple[str, ...]` | vazio se disponível; cada motivo nomeia o campo e a referência |
| `owner` | `str \| None` | dono, para Assistants de usuário (aparece no `assistants validate`) |

`ValidationReport.statuses: tuple[AssistantStatus, ...]` (ordenado por origem e nome); `ok` = todos disponíveis.

### `ApiKeyInfo` e `IssuedApiKey` (FR-015)

| `ApiKeyInfo` | Tipo | |
|---|---|---|
| `key_id` | `str` | 16 caracteres hexadecimais, público |
| `subject` | `str` | `user:…` ou `svc:…` |
| `groups` | `frozenset[str]` | |
| `label` | `str \| None` | nota do operador |
| `created_at` | `datetime` | |
| `revoked_at` | `datetime \| None` | `None` = ativa |

`IssuedApiKey(info: ApiKeyInfo, plaintext: str)` — o único objeto que carrega a chave em claro; existe só na resposta
da emissão.

## Erros publicados

| Erro | Quando | Tradução sugerida à 008 |
|---|---|---|
| `NotFound` (base, `LookupError`) | recurso inexistente **ou** não visível ao Principal | 404 |
| `AssistantNotFound(NotFound)` | Assistant inexistente ou ACL recusada — mesma mensagem nos dois casos | 404 |
| `AssistantUnavailable` | autorizado, mas indisponível; carrega `reasons` | 424 (008, clarificação de 2026-09-30) |
| `RequestRejected` (`ValueError`) | pedido fora do permitido; carrega `field` (ex.: `model`) | 400 |
| `PolicyViolation(RequestRejected)` | rascunho de Assistant de usuário fora da política; `field` nomeia o campo | 400 |
| `NoApplicablePolicy(RequestRejected)` | Principal sem política aplicável tenta criar Assistant (US6 cen. 6) | 400 |
| `Conflict` | criação com nome que o dono já usa | 409 |
| `RateLimited` | orçamento excedido; carrega `retry_after: float` (segundos) | 429 + `Retry-After` |
| `AssistantsConfigError` (`ValueError`) | erro de arquivo no `assistants.yaml`; nomeia o campo | boot interrompido |

A tradução em status é da 008; a tabela registra a intenção que os erros carregam.

## Tipos internos (`domain/`)

| Tipo | Campos | Uso |
|---|---|---|
| `AccessRule` | `schemes: frozenset[Scheme]`, `allow: tuple[str, ...]` | ACL; `permits(principal) -> bool` puro |
| `AssistantDefinition` | nome, origem, dono, descrição, `visibility`, `AccessRule`, flow, packs, mcp, collections, allowed/write tools, papéis, allowlist, `Limits`, `problems` | forma normalizada de sistema e de usuário; `problems` guarda erros de carga daquele Assistant |
| `UserAssistantPolicy` | `match`, `packs`, `flows`, `collections`, `models_allow`, tetos de limite, `write_tools: bool` | clarificação 1, FR-014 |
| `AssistantsConfig` | `assistants: Mapping[str, AssistantDefinition]`, `policies: tuple[UserAssistantPolicy, ...]`, `admin_group: str \| None` | resultado de `AssistantConfigSource.load()` |
| `ApiKeyRecord` | `ApiKeyInfo` + `key_hash: bytes` | o que a porta guarda |
| `ModelSelection` | `assistant: str`, `requested: str \| None` | id de modelo decomposto no primeiro `/` (R5); `select_models` interpreta a parte pedida |
| `RateDecision` | `allowed: bool`, `retry_after: timedelta \| None` | resultado da janela deslizante (R9) |
| `OidcClaims` | `subject_claim`, `groups_claim`, `leeway: timedelta` | configuração do mapeamento de claims (R6) |

## Ciclos de vida

**Chave de API** — `ativa → revogada` (terminal). Revogar de novo é idempotente e devolve o mesmo `revoked_at`. Não há
reativação: emite-se outra chave.

**Assistant de usuário** — `inexistente → criado → (atualizado)* → removido`. Atualização substitui o rascunho inteiro
(a última escrita vence, R10). Remoção é definitiva.

**Disponibilidade** — não é guardada: é calculada na validação (boot, CLI) e em cada resolução. Um Assistant
indisponível volta a ficar disponível sozinho quando a causa some (pack corrigido, política afrouxada).

## Armazenamento Postgres (schema `assistants`, ADR-015)

```sql
CREATE TABLE assistants.schema_version (version integer PRIMARY KEY, applied_at timestamptz NOT NULL);

CREATE TABLE assistants.user_assistants (
    owner       text        NOT NULL,
    name        text        NOT NULL,           -- sem o "~"
    definition  jsonb       NOT NULL,           -- UserAssistantDraft serializado, com "format": 1
    created_at  timestamptz NOT NULL,
    updated_at  timestamptz NOT NULL,
    PRIMARY KEY (owner, name)
);

CREATE TABLE assistants.api_keys (
    key_id      text        PRIMARY KEY,
    key_hash    bytea       NOT NULL,           -- SHA-256 da chave inteira
    subject     text        NOT NULL,
    groups      text[]      NOT NULL DEFAULT '{}',
    label       text,
    created_at  timestamptz NOT NULL,
    revoked_at  timestamptz
);
```

A forma exata do DDL é do adapter; este esboço registra as chaves de unicidade (dono + nome; `key_id`) que a suíte de
conformidade verifica nos dois adapters.

## Volume esperado

Dezenas de Assistants de sistema, centenas de Assistants de usuário, dezenas de chaves por instalação (um operador,
vários usuários — Assumptions da spec). Nenhuma consulta precisa de paginação nesta fase.

---

## Fase 3 (2026-10-02): regras de referência novas (research R18–R23)

### `AssistantsService` — parâmetro novo

| Parâmetro | Tipo | Origem |
|---|---|---|
| `flow_roles` | `Mapping[str, tuple[ModelRole, ...]] \| None` (default `None` = nenhuma exigência) | `ExecutionEngine.flow_roles()` da 005 (ADR-019), injetado pela 011 |

### Funções puras novas (`domain/validation.py`)

| Função | Entrada | Saída |
|---|---|---|
| `role_reasons(definition, flow, flow_roles)` | o flow efetivo e o mapeamento | um motivo por papel exigido e não declarado |
| `tool_reasons(definition, pack_tools)` | `pack_tools`: pack → nomes de tools nativas e retrievers | um motivo por entrada morta de `allowed_tools` e `write_tools` |
| `collision_reasons(definition)` | — | um motivo por alias MCP igual a pack |

As três entram em `reference_reasons` (resolução, boot, `assistants validate`) e em `_conform` (criação e atualização
de Assistant de usuário: o primeiro motivo vira `RequestRejected` com `field` = `models`, `allowed_tools`, `write_tools`
ou `mcp`). Formatos das mensagens em [contracts/assistants-yaml.md](contracts/assistants-yaml.md), "Fase 3".

### Toque declarado na 005 (ADR-019)

`ExecutionEngine.flow_roles() -> Mapping[str, tuple[ModelRole, ...]]`: um item por flow de `flows()`, com os papéis que
`run` confere para ele (`chat`: `generation`; `agentic`: `controller`, `generation`).

## Fase 9 (2026-10-14): superfície de administração e sobreposições (research R25–R31)

### Vocabulário

`Surface = Literal["public", "private", "admin"]`; `ADMIN_SURFACE = "admin"`;
`SCHEMES_OF_SURFACE = {public: {oidc}, private: {api_key}, admin: {oidc, api_key}}`;
`OverrideSection = Literal["models", "mcp"]`; `OverrideState = Literal["active", "inactive"]`.

### `AssistantDefinition` — campo novo

`overrides: frozenset[OverrideSection]` (do YAML; padrão vazio).

### `ModelsOverride` e `McpOverride` (publicados)

- `ModelsOverride(roles: Mapping[ModelRole, ModelRef])`
- `McpOverride(aliases: tuple[str, ...], allowed: frozenset[str], write: frozenset[str])` — entradas sempre
  `<alias>.<tool>` de um alias da própria sobreposição

### `OverrideView` (publicado)

`section`, `payload` (`ModelsOverride | McpOverride`), `state`, `reason` (para `inactive`), `version`, `updated_by`,
`updated_at`.

### `SystemAssistantView` (publicado)

`name`, `description`, `visibility`, `flow`, `status` (`AssistantStatus`), `overridable: frozenset[OverrideSection]`,
`yaml_models: Mapping[ModelRole, ModelRef]`, `allow: tuple[str, ...]`, `yaml_mcp: McpOverride` (a seção do YAML),
`overrides: tuple[OverrideView, ...]`, `effective_models: Mapping[ModelRole, ModelRef]`, `effective_mcp: McpOverride`,
`required_roles: tuple[ModelRole, ...]` (do flow).

### `OverrideHistoryEntry` (publicado)

`section`, `action` (`saved`, `discarded`), `payload`, `version`, `actor`, `at`.

### `OidcAudiences` (configuração do `AccessService`)

`public: str` (padrão `ai-core`), `admin: str` (padrão `ai-core-admin`).

### Armazenamento (schema `assistants`, migração `003_system_overrides.sql`)

| Tabela | Chave | Colunas |
|---|---|---|
| `system_overrides` | (`assistant`, `section`) | `payload jsonb`, `fingerprint text`, `version int`, `updated_by text`, `updated_at timestamptz` |
| `system_override_history` | `id bigserial` | `assistant`, `section`, `action`, `payload jsonb`, `fingerprint`, `version`, `actor`, `at` |
