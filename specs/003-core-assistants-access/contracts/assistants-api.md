# Contrato — seams da 003 (Assistants & Access)

Dono: spec 003. Consumidores: 008 (autenticação, resolução, descoberta, CRUD, administração de chaves), 005 (lê o grant
pelo `Protocol` dela), 004, 006 e 007 (recebem o grant a partir da Fase 3), 011 (constrói, valida no boot, registra a
CLI). Publicado em `ai_core/assistants/api.py`. **Mudar qualquer assinatura abaixo exige ADR** (princípio II).

## Superfície

```python
from ai_core.assistants.api import (
    # seams
    Authenticator, GrantResolver, AssistantDirectory, ApiKeyAdmin,
    # value objects
    Principal, ExecutionGrant, Limits, AssistantSummary, UserAssistantDraft, DraftLimits, UserAssistant,
    AssistantStatus, ValidationReport, ApiKeyInfo, IssuedApiKey,
    # vocabulário
    Surface, Scheme, Origin, PUBLIC_SURFACE, PRIVATE_SURFACE, SCHEMES, SCHEME_OF_SURFACE, USER_PREFIX,
    DEFAULT_RPM, WIDENING_FIELDS, NAME_PATTERN, SUBJECT_PATTERN, KEY_ID_PATTERN, DESCRIPTION_MAX,
    # erros
    NotFound, AssistantNotFound, AssistantUnavailable, RequestRejected, PolicyViolation,
    NoApplicablePolicy, Conflict, RateLimited, AssistantsConfigError,
)
```

Nada além disso é público. `domain/`, `ports.py`, `service.py` e `adapters/` são internos; só a composition root
importa `service.py` e `adapters/`. Campos e regras dos value objects: [data-model.md](../data-model.md).

## `Authenticator` — elo 0: quem está pedindo

```python
class Authenticator(Protocol):
    async def authenticate(self, *, surface: str, credential: str | None) -> Principal | None: ...
```

| Regra | Origem | Verificada por |
|---|---|---|
| `surface="public"` aceita só token OIDC; `"private"`, só chave de API | FR-001, US2 | conformidade do seam |
| Token OIDC válido → `Principal(subject="user:<sub>", scheme="oidc", groups=<claim>)` | US2 cen. 1 | conformidade |
| Chave válida → `Principal(subject=<dono>, scheme="api_key", groups=<da chave>)` | US2 cen. 2 | conformidade |
| Credencial ausente, malformada, expirada, com assinatura inválida ou revogada → `None`; **nunca levanta** | US2 cen. 3–4 | conformidade |
| Superfície desconhecida → `None` | falha fechada | conformidade |
| `credential` é o token puro, sem esquema HTTP (`Bearer`): extraí-lo do cabeçalho é da 008 | Module Boundary | revisão da 008 |

A forma é a da porta que a 008 já declarou ([research.md](../research.md) R1).

## `GrantResolver` — elos 2, 6 e 7: o que a execução pode usar

```python
class GrantResolver(Protocol):
    async def resolve(self, *, model: str, principal: Principal) -> ExecutionGrant: ...
```

`model` é `<assistant>`, `<assistant>/<modelo>` ou `<assistant>/<provider>/<modelo>` (R5). Ordem da resolução e
motivo de cada passo: [research.md](../research.md) R4.

| Regra | Origem | Verificada por |
|---|---|---|
| Inexistente e não autorizado levantam `AssistantNotFound` com **a mesma mensagem**, pelo mesmo caminho | FR-006, SC-001 | suíte adversarial |
| Assistant de usuário só resolve para o dono; `~x` de outro usuário é indistinguível de inexistente | FR-017 | suíte adversarial |
| Autorizado mas indisponível levanta `AssistantUnavailable(reasons)` — nunca resolve com a referência ignorada | FR-011, FR-016 | conformidade |
| Modelo pedido fora da allowlist levanta `RequestRejected(field="model")` antes de qualquer custo | US4 cen. 1, SC-005 | suíte adversarial |
| Modelo pedido dentro da allowlist substitui só o papel `generation` | US4 cen. 3 | conformidade |
| Grant contém apenas o declarado; `mcp: []` → `mcp_aliases` vazio | US1 cen. 1, SC-002 | suíte adversarial (hypothesis) |
| Packs na ordem declarada; flow ausente com um pack → `preferred_flow` ou `chat` | US1 cen. 2–3 | conformidade |
| Assistant de usuário fora da política aplicável **agora** → `AssistantUnavailable` nomeando o campo | FR-014, edge case | conformidade |
| Excedeu `rpm` no par (subject, Assistant) → `RateLimited(retry_after)`; outro Principal não é afetado | US7, FR-010 | conformidade com relógio fixo |
| Público nunca carrega `write_tools` | FR-012 | suíte adversarial |

## `AssistantDirectory` — elo 1 e gestão de Assistants de usuário

```python
class AssistantDirectory(Protocol):
    async def discover(self, principal: Principal) -> Sequence[AssistantSummary]: ...
    async def mine(self, principal: Principal) -> Sequence[UserAssistant]: ...
    async def get(self, principal: Principal, name: str) -> UserAssistant: ...
    async def create(self, principal: Principal, draft: UserAssistantDraft) -> UserAssistant: ...
    async def update(self, principal: Principal, name: str, draft: UserAssistantDraft) -> UserAssistant: ...
    async def delete(self, principal: Principal, name: str) -> None: ...
```

| Regra | Origem | Verificada por |
|---|---|---|
| `discover` devolve exatamente o que `resolve` aceitaria sem `NotFound` nem `Unavailable` | FR-008, US5, R12 | conformidade: para cada Principal da suíte, `discover` = {nomes que resolvem} |
| `visibility` não filtra a descoberta; privado aparece para quem o `allow` nomeia | clarificação 4 | conformidade |
| `mine` lista só Assistants do próprio Principal, incluindo os indisponíveis, com motivo | R12 | conformidade |
| `get`/`update`/`delete` de nome alheio ou inexistente → `AssistantNotFound` | FR-013, FR-017 | suíte adversarial |
| `create` fora da política → `PolicyViolation(field)`; sem política aplicável → `NoApplicablePolicy` | US6 cen. 5–6 | conformidade |
| `create` referenciando MCP de outro usuário → `PolicyViolation(field="mcp")` com a mensagem de "não existe" | US6 cen. 2 | suíte adversarial |
| `create` com nome já usado pelo mesmo dono → `Conflict` | R10 | conformidade |
| `name` recebido com ou sem `~` é aceito; o devolvido sempre tem `~` | FR-017 | conformidade |
| Criado fica resolvível na requisição seguinte, sem restart | SC-003, US6 cen. 1 | conformidade |

## `ApiKeyAdmin` — administração de chaves pela superfície privada

```python
class ApiKeyAdmin(Protocol):
    async def issue(self, *, actor: Principal, subject: str, groups: Collection[str] = (),
                    label: str | None = None) -> IssuedApiKey: ...
    async def keys(self, *, actor: Principal) -> Sequence[ApiKeyInfo]: ...
    async def revoke(self, *, actor: Principal, key_id: str) -> ApiKeyInfo: ...
```

| Regra | Origem | Verificada por |
|---|---|---|
| Ator fora de `api_keys.admin_group`, autenticado fora da superfície privada (esquema diferente de `api_key`) ou com o grupo não configurado → `NotFound` em todas as operações | US2 cen. 5, FR-015 | suíte adversarial |
| A chave em claro só existe em `IssuedApiKey.plaintext`; `keys()` nunca a devolve | FR-015 | conformidade |
| Revogada, a chave é recusada por `authenticate` na chamada seguinte | US2 cen. 4 | conformidade |
| `revoke` de `key_id` inexistente → `NotFound`; revogar de novo devolve o mesmo `revoked_at` | ciclo de vida | conformidade |
| `subject` fora de `user:…`/`svc:…` → `RequestRejected(field="subject")` | data-model | conformidade |

## Validação e campos de ampliação

- `await service.validate() -> ValidationReport` não é seam entre módulos: a composition root o chama na etapa de validação
  de Assistants, e a CLI da própria 003 o expõe ([cli.md](cli.md)).
- `WIDENING_FIELDS` é a lista canônica que a 008 recusa no corpo da requisição, nomeando o campo (FR-007, R13).

## Suítes de conformidade

- `tests/assistants/contract/test_authenticator.py` — tabela do `Authenticator`, com os dois verificadores OIDC (estático
  e JWKS) e os dois armazenamentos de chave;
- `tests/assistants/contract/test_grant_resolver.py` — tabela do `GrantResolver`;
- `tests/assistants/contract/test_adversarial.py` — SC-001 (mesmo erro, mesma mensagem, mesmo caminho; tempo na mesma
  ordem de grandeza), SC-002 (hypothesis: grant ⊆ declarado para Assistants e pedidos gerados), SC-005 (nenhum pedido
  com modelo fora da allowlist produz grant);
- `tests/assistants/contract/test_directory.py` — descoberta igual ao conjunto resolvível, CRUD e isolamento entre donos;
- `tests/assistants/contract/test_key_admin.py` — emissão, listagem, revogação e 404 para não administradores;
- `tests/assistants/contract/test_validation.py` — um estado por Assistant, motivos que nomeiam campo e referência;
- `tests/assistants/contract/test_allowlist_parity.py` — a regra de allowlist da resolução e a da 006 concordam sobre
  o mesmo conjunto de casos (R5).

## Fase 9 (2026-10-14): superfície de administração e `SystemAssistantAdmin`

### Superfícies (ADR-031)

`SCHEMES_OF_SURFACE` substitui `SCHEME_OF_SURFACE` (mantido, derivado e depreciado, até a série seguinte). Na superfície
`admin`, credencial com o prefixo de chave da 003 segue o caminho de chave; qualquer outra, OIDC com a audiência
`ai-core-admin`. Na `public`, OIDC com a audiência `ai-core`. Audiência errada → `None` (não autenticado).
`is_admin(principal)` = membro do grupo de administração, em qualquer esquema.

### `SystemAssistantAdmin` — consumido pela 008 (superfície de administração)

```python
class SystemAssistantAdmin(Protocol):
    async def system_assistants(self, *, actor: Principal) -> tuple[SystemAssistantView, ...]: ...
    async def system_assistant(self, name: str, *, actor: Principal) -> SystemAssistantView: ...
    async def override_models(self, name: str, override: ModelsOverride, *, actor: Principal,
                              version: int | None) -> SystemAssistantView: ...
    async def override_mcp(self, name: str, override: McpOverride, *, actor: Principal,
                           version: int | None) -> SystemAssistantView: ...
    async def discard_override(self, name: str, section: OverrideSection, *, actor: Principal,
                               version: int) -> SystemAssistantView: ...
    async def history(self, name: str, *, actor: Principal) -> tuple[OverrideHistoryEntry, ...]: ...
    async def declared_models(self) -> tuple[ModelRef, ...]: ...  # efetivos, para a saúde (011); lê o armazenamento
```

| Situação | Resultado |
|---|---|
| ator fora do grupo de administração | `NotFound` (404) |
| Assistant inexistente ou de usuário | `NotFound` |
| seção fora de `overrides` | `RequestRejected(field="models" \| "mcp")` com "só muda por novo deploy" |
| modelo fora de `models.allow`; papel exigido ausente; entrada sem namespace ou de alias alheio; alias inexistente; escrita em Assistant público | `RequestRejected(field=…)` nomeando o campo |
| `version` diferente da guardada (`None` só quando não há sobreposição) | `Conflict` |
| sucesso | a visão atualizada; vale na resolução seguinte, sem restart |

### Conformidade — acréscimos

`tests/assistants/contract/test_system_assistant_admin.py` (adversarial, marca `us10`),
`tests/assistants/contract/test_override_store.py` (memória × Postgres), `tests/assistants/contract/test_surfaces.py`
(três superfícies, audiências, admin por grupo, marca `us9`).
