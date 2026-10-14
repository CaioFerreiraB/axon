# Design — 003 Assistants & Access

> Insumo técnico pré-aprovado para `/speckit-plan`. Origem: arch-v1 §12, §15, §16, §25, §28; ADR-002, ADR-008, ADR-012.

## Localização

```text
ai-core/packages/core/src/ai_core/assistants/
├── api.py        # seams: Authenticator, GrantResolver, AssistantDirectory;
│                 # value objects Principal, ExecutionGrant, ModelPolicy, Limits
├── domain/       # ACL, resolução do grant (interseção com as restrições da requisição), 404-não-403,
│                 # rejeição de campos de ampliação, validação de referências, decisão de rate limit — puro
├── ports.py      # AssistantStore, ApiKeyStore, OidcVerifier, RateCounterStore, Clock
├── service.py
└── adapters/
    ├── assistants_yaml.py       # AssistantStore de sistema (somente leitura)
    ├── assistants_postgres.py   # AssistantStore de usuário — Fase 2
    ├── oidc.py                  # OidcVerifier (JWKS do provedor)
    ├── api_keys.py              # ApiKeyStore
    ├── rate_memory.py           # RateCounterStore (processo único)
    └── cli.py                   # subcomando `assistants validate`
```

A autenticação, antes em `ai_core/auth/`, passa a morar neste pacote (ADR-012). O `api.py` não importa o resto do
módulo, e por isso 004, 005, 006, 007 e 008 podem importar `Principal` e `ExecutionGrant` sem ciclo.

## Assistants (arch-v1 §12)

```yaml
assistants:

  scouting:
    visibility: public
    auth:
      schemes: [oidc, api_key]
      allow: ["*"]                       # qualquer principal autenticado
    flow: rag_first
    packs: [scouting]
    mcp: []                              # nenhum. nem sabe que existem.
    collections: [scouting_docs]
    models:
      generation: { provider: ollama, model: "qwen3:1.7b" }
      controller: { provider: ollama, model: "qwen3:1.7b" }
      allow: ["ollama/*"]
    limits:
      rpm: 20
      max_iterations: 3
      max_context_tokens: 4000

  generic:
    visibility: private                  # não aparece na listagem de terceiros
    auth:
      schemes: [api_key]
      allow: ["user:caio"]
    flow: agentic
    packs: [generic]
    mcp: [finance, drive]
    collections: []
    models:
      generation: { provider: ollama, model: "qwen3:1.7b" }
      controller: { provider: openrouter, model: "qwen/qwen3-8b" }
      allow: ["ollama/*", "openai/*", "openrouter/*"]
    limits:
      max_iterations: 6

  scouting_finance:                      # composição explícita
    visibility: private
    auth:
      schemes: [api_key]
      allow: ["user:caio"]
    flow: agentic
    packs: [scouting, financial]
    mcp: [finance]
    collections: [scouting_docs]
```

A resposta à pergunta *"como uso scouting sem que o sistema conheça os MCPs do generic?"* é estrutural: **são Assistants diferentes**, e `scouting` declara `mcp: []`.

### Sistema vs usuário

| | Sistema | Usuário |
|---|---|---|
| Definidos por | operador, em YAML versionado | usuário, via API |
| Armazenados em | arquivo de configuração | Postgres |
| Podem referenciar | qualquer pack instalado, qualquer MCP global | packs permitidos ao usuário, MCPs próprios |
| Sobrescritos por | novo deploy; pela administração, só as seções em `overrides` (Fase 9, ADR-032) | o próprio usuário |

## Autenticação (arch-v1 §15)

```python
@dataclass(frozen=True)
class Principal:
    subject: str          # "user:caio", "svc:ingestor"
    scheme: str           # "oidc" | "api_key"
    groups: list[str]


class Authenticator(Protocol):     # seam em api.py
    async def authenticate(self, surface: Literal["public", "private"], credential: str) -> Principal:
        """Levanta NotAuthenticated. A superfície pública aceita só OIDC; a privada, só chave de API."""
```

> Forma superada pela [research R1](research.md): argumentos só por nome, `credential: str | None` e `None` para
> credencial recusada — a forma da porta que a 008 já declarou.

A dependência HTTP que extrai a credencial da requisição e chama `authenticate` é da spec 008 (adapter primário).
Superfícies são poucas e estáveis; assistants crescem. Por isso a variável de roteamento é a superfície de auth, não o pack (ADR-002).

### Fase 9: superfície de administração e emissor da plataforma ([ADR-030](../../docs/adr/ADR-030-a-plataforma-e-o-provedor-de-identidade.md), [ADR-031](../../docs/adr/ADR-031-superficie-de-administracao.md))

- `Surface = "public" | "private" | "admin"`; `SCHEME_OF_SURFACE` vira `SCHEMES_OF_SURFACE: Mapping[Surface,
  frozenset[Scheme]]` = `{public: {oidc}, private: {api_key}, admin: {oidc, api_key}}`. Na administração, `parse_key()`
  com o prefixo `aic_` → caminho de chave; senão, OIDC.
- Audiência por superfície: `public` aceita a do chat (`ai-core`), `admin` a da console (`ai-core-admin`); a 011 as
  configura a partir dos clientes da 012.
- `is_admin(principal, admin_group)` = `admin_group in principal.groups`, sem olhar o esquema.
- O `JwksOidcVerifier` mantém a lógica e ganha uma fonte de chaves plugável (`JwksSource`): HTTP (descoberta ou
  `AI_CORE_OIDC_JWKS_URL`, como hoje) ou uma função em processo — o seam `PublicKeySet` da 012, injetado pela 011, sem
  chamada HTTP da plataforma para si mesma. Um único emissor: identidade ligada com `AI_CORE_OIDC_ISSUER` é erro de
  configuração (validado pela 011).
- Com a 012, o subject vem de `preferred_username` (`OidcClaims(subject_claim="preferred_username", groups_claim="groups")`),
  como com o Keycloak na Fase 7.

## Sobreposições de Assistants de sistema (Fase 9, [ADR-032](../../docs/adr/ADR-032-assistants-de-sistema-sobrepostos-em-runtime.md))

```yaml
assistants:
  geral:
    overrides: [models, mcp]     # conjunto fechado; ausente = só por deploy
    models: {generation: openrouter/openai/gpt-4.1-nano, allow: ["openrouter/*"]}
```

- Merge puro em `domain/overrides.py`: `effective(definition, overrides) -> (definition, problems, states)`. Uma
  sobreposição substitui a seção inteira e só vale se a seção está em `overrides`; senão, estado `inactive` com motivo.
- `models`: só papéis; cada `ModelRef` casa `models.allow` (o teto do YAML).
- `mcp`: aliases e as entradas com namespace MCP de `allowed_tools`/`write_tools`; as de pack ficam como no YAML. Se o
  YAML não declara `allowed_tools` (tudo permitido) e a sobreposição restringe tools de MCP, a lista efetiva é: todas as
  tools dos packs (enumeradas como a validação já faz) mais as tools de MCP escolhidas.
- Validação: `static_reasons`, `reference_reasons`, `role_reasons`, `tool_reasons` e `collision_reasons` sobre a
  definição efetiva. Na gravação, 422 nomeando o campo; na resolução, indisponível com o motivo prefixado pela seção.
- `AssistantsService` passa a consultar `SystemOverrideStore` em `_find`, `discover` e `validate`, com cache por processo
  invalidado na gravação (TTL de segurança de 5 s). `declared_models()` passa a ser do serviço, com os modelos efetivos,
  para a saúde (011).
- Impressão digital (clarificação de 2026-10-13): hash da seção do YAML, normalizada, gravado com a sobreposição;
  diferente do YAML atual → `inactive`, motivo "o deploy mudou a seção". O deploy sempre vence.

## Autorização

```yaml
auth:
  schemes: [api_key]           # esquemas aceitos para este assistant
  allow: ["user:caio"]         # subjects ou grupos ("group:chefia")
```

**Principal não autorizado recebe 404, não 403.**

## Execution Grant — seam exposto

```python
@dataclass(frozen=True)
class ExecutionGrant:
    assistant: str
    principal: Principal
    flow: str
    packs: tuple[str, ...]              # ordem declarada
    mcp_aliases: frozenset[str]
    collections: frozenset[str]
    allowed_tools: frozenset[str] | None   # filtro final (spec 004)
    write_tools: frozenset[str]
    models: ModelPolicy                 # por papel + allowlist (spec 006)
    limits: Limits                      # rpm, max_iterations, max_context_tokens
```

> `packs` virou propriedade derivada de `composition` (o `Composition` da 002), que é o que o `Protocol` da 005 lê
> ([research R1](research.md)); `models: ModelPolicy` faz a seta ser 003 → 006 ([ADR-016](../../docs/adr/ADR-016-grant-carrega-politica-de-modelos.md)).

É o único objeto que 004, 005 e 007 recebem para saber o que uma execução pode usar; a 006 recebe dele a política já
pronta. Nenhum deles lê a configuração de Assistants diretamente.

## Cadeia de enforcement (arch-v1 §16) — elos por spec

| # | Camada | O que filtra | Efeito se violado | Spec |
|---|---|---|---|---|
| 1 | Discovery | `/v1/models` lista só o que o Principal pode usar | assistant invisível | **003** (+008) |
| 2 | Resolução | ACL do assistant vs Principal | 404, sem vazar existência | **003** |
| 3 | Capability | catálogo = união só dos packs do assistant | tool inexistente | 004 |
| 4 | MCP | só aliases do assistant; credencial server-side | server desconhecido | 007/004 |
| 5 | Retrieval | allowlist de coleções | query rejeitada | 004 |
| 6 | Provider | allowlist de provider/model | modelo não permitido | 006 (+003 na resolução) |
| 7 | Budget | rate limit por (Principal, Assistant), iterações, tokens | 429 / truncamento | **003** (+005) |

## Requisição: só restringe

Campos aceitos que restringem: `assistant` (ou `model` na compat OpenAI, no formato `<assistant>/<model>`), escolha de modelo de geração dentro da allowlist, parâmetros de amostragem dentro de limites.
Campos rejeitados por ampliar: `packs`, `mcp_servers`, `provider` fora da allowlist, `tools`/`functions` do cliente.

## Persistência (arch-v1 §28)

| Dado | Porta | Adapter | Quando |
|---|---|---|---|
| Assistants de usuário | `AssistantStore` | memória → Postgres | Fase 1 → Fase 2 |
| Contadores de rate limit | `RateCounterStore` | memória (processo único) → avaliar Postgres/Redis se houver réplicas | Fase 2 |
| Sobreposições de Assistants de sistema (+ histórico) | `SystemOverrideStore` | memória → Postgres (`sql/003_system_overrides.sql`) | Fase 9 |

## Portas e adapters **[ADR-012]**

| Porta | Tipo | Adapters por fase | Teste |
|---|---|---|---|
| `Authenticator` | primária (seam) | `service.py` | suíte de conformidade (os dois esquemas, credencial inválida) |
| `GrantResolver` | primária (seam) | `service.py` | suíte adversarial: 404-não-403, ampliação rejeitada |
| `AssistantDirectory` | primária (seam) | `service.py` | listagem filtrada por ACL |
| `SystemAssistantAdmin` | primária (seam, Fase 9) | `service.py` | suíte adversarial: fora da allowlist, escrita em público, seção não permitida, sobreposição inativa, conflito de versão |
| `AssistantStore` | secundária | YAML (sistema); memória → Postgres (usuário, Fase 2) — dividida em `AssistantConfigSource` e `UserAssistantStore` ([research R15](research.md)) | em memória + conformidade contra Postgres |
| `ApiKeyStore` | secundária | ~~configuração do operador (Fase 2); armazenamento a decidir no plano~~ — memória → Postgres, só o hash (clarificação de 2026-09-30, [research R7, R8](research.md), [ADR-015](../../docs/adr/ADR-015-persistencia-postgres-por-modulo.md)) | em memória + conformidade contra Postgres |
| `OidcVerifier` | secundária | JWKS do provedor OIDC; Fase 9: fonte de chaves plugável — HTTP ou em processo (012, pela 011), audiência por superfície | verificador de teste com chaves locais |
| `SystemOverrideStore` | secundária (Fase 9) | memória → Postgres | em memória + conformidade contra Postgres |
| `RateCounterStore` | secundária | memória | em memória |
| `Clock` | secundária | relógio do sistema (adapter único, injetado pela 011) | relógio fixo |

Consome por seam (via `api.py` dos donos): Pack Registry (002), MCP Registry (007), nomes de flow (005), value objects da
política de modelos (006, [ADR-016](../../docs/adr/ADR-016-grant-carrega-politica-de-modelos.md)). Não importa a 012:
as chaves públicas do emissor chegam como uma função injetada pela 011.
