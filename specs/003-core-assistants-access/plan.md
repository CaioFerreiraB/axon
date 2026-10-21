# Implementation Plan: Assistants, identidade e autorização

**Branch**: `003-core-assistants-access` | **Date**: 2026-09-30 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/003-core-assistants-access/spec.md`

**Architecture inputs** *(PROJECT OVERRIDE — agentic-app)*: before filling Technical Context, READ
`/specs/003-core-assistants-access/design.md` (including its "Portas e adapters" section) and every ADR listed
in the spec's Module Boundary, plus ADR-012 (architectural style). Decisions recorded there are
**pre-approved**: carry them into this plan and into `research.md` as
"Decision / Rationale (ADR-xxx) / Alternatives", do not re-research them. Any deviation requires a
new ADR in `docs/adr/` and must be listed in Complexity Tracking.

Insumos lidos: [design.md](design.md), ADR-002, ADR-008, ADR-012, ADR-013; as cinco clarificações de 2026-09-30; os
seams e portas que os consumidores já publicaram — `ExecutionGrant` (005 R3), `Authenticator` e `GrantResolver` (008
R1, R2) — e o `assistants.yaml` da 011 (R4). **Refinamentos do `design.md`, sem divergência de decisão**: as
assinaturas seguem a forma já acordada com 005 e 008 (R1), `AssistantStore` vira duas portas (R15), o formato YAML do
modelo é o texto herdado da 011 (R3). **Dois ADRs novos, aceitos em 2026-09-30**: [ADR-015](../../docs/adr/ADR-015-persistencia-postgres-por-modulo.md), porque a
persistência em Postgres nasce aqui e fixa a convenção que 008, 004, 005 e 007 vão herdar (R8); e [ADR-016](../../docs/adr/ADR-016-grant-carrega-politica-de-modelos.md), porque o grant
carregar a `ModelPolicy` da 006 torna a seta 003 → 006, o inverso do que o grafo registrava (R1; achado C1 do
`/speckit-analyze`).

## Summary

Entregar a fronteira de isolamento: autenticar o Principal pelas duas superfícies (OIDC na pública, chave de API na
privada), carregar Assistants de sistema do `assistants.yaml` e de usuário do armazenamento, e resolver, para cada
pedido, um **Execution Grant** que contém só o que o Assistant declara — com 404 idêntico para inexistente e não
autorizado, recusa de modelo fora da allowlist antes de qualquer custo e orçamento por (Principal, Assistant). Inclui
as políticas por grupo para Assistants de usuário, o prefixo `~`, a administração de chaves com hash em Postgres e a
validação de referências que o boot e a CLI consomem. Escopo da Fase 2: **US1–US7**, mais a validação (FR-011) de que
a 011 precisa. A troca na plataforma em execução — rotas e boot — é das passadas da 008 e da 011 (R2).

## Technical Context

**Language/Version**: Python 3.14 (módulo da distribuição `ai-core`, `requires-python = ">=3.14"`)

**Primary Dependencies**: `api.py` de 002 (`Composition`, `PackRegistry`), 005 (`FLOW_CHAT`) e 006 (`ModelPolicy`,
`ModelRef`, `ModelRole` — só value objects, ADR-016); `pyyaml` (já presente). **Novas**, confinadas a `adapters/` por import-linter:
`pyjwt[crypto]>=2.10,<3`, `httpx>=0.28,<1` (hoje só transitiva), `psycopg[binary]>=3.2,<4`, `psycopg-pool>=3.2,<4`
(R6, R8, R17)

**Storage**: `assistants.yaml` (sistema, somente leitura); Postgres no schema `assistants` — Assistants de usuário e
chaves de API (ADR-015); memória para rate limit (processo único) e para todos os adapters no perfil de teste

**Testing**: pytest + pytest-asyncio + hypothesis; `unit/` (domínio puro), `contract/` (quatro seams, suíte adversarial
e cada porta contra memória e adapter real), `integration/` (Postgres real e CLI). Postgres por
`AI_CORE_TEST_POSTGRES_DSN`, com serviço na CI; JWKS por `httpx.MockTransport` (R16)

**Target Platform**: processo do core na imagem Linux ARM64 (2 OCPU, 12 GB)

**Project Type**: módulo de biblioteca dentro do monolito modular (`ai_core/assistants/`)

**Performance Goals**: resolução de Assistant de sistema sem I/O além do contador de taxa em memória; de usuário, uma
leitura por (dono, nome); autenticação por chave, uma leitura indexada por `key_id`; OIDC sem rede no caminho, com
JWKS em cache

**Constraints**: 404 idêntico em conteúdo e caminho para inexistente e não autorizado (SC-001); nada da requisição
entra no grant além do modelo de geração dentro da allowlist (SC-002); revogação de chave vale na requisição seguinte;
`api.py`/`domain/`/`ports.py`/`service.py` sem YAML, JWT, HTTP nem driver de banco; tempo e aleatoriedade por porta

**Scale/Scope**: 1 módulo com 4 seams, 9 portas secundárias, 7 regras de domínio; dezenas de Assistants de sistema,
centenas de usuário, dezenas de chaves

Nenhum `NEEDS CLARIFICATION`: as cinco perguntas abertas foram resolvidas em 2026-09-30 e os pontos adiados pelo
`/speckit-clarify` — claims do OIDC (R6), formato do id de modelo (R5), janela do rate limit (R9), encaixe nos
`Protocol` de 005 e 008 (R1) e concorrência na edição (R10) — estão em [research.md](research.md).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Resultado | Evidência |
|---|---|---|
| I. Núcleo agnóstico | ✅ | Nomes de Assistant, pack, grupo e MCP são dados; exemplos de domínio só em configuração ilustrativa |
| II. Seams | ✅ | Consome só `api.py` de 002, 005 e 006; expõe quatro seams com suíte de conformidade; o seam novo **API Key Admin** está registrado em `specs/README.md`; a seta 003 → 006 (value objects da política) está no ADR-016, com 005 e 006 listadas como afetadas |
| III. O core orquestra | ✅ | Resolve o que a execução pode usar; não executa nada. Flow é validado contra os nomes do motor, não escolhido por pack |
| IV. Assistant é a fronteira | ✅ | É o princípio implementado: grant ⊆ declarado (SC-002, hypothesis), 404-não-403 (SC-001), requisição só restringe (R5, R13), capacidade não declarada não entra no grant |
| V. Determinismo | ✅ | ACL, política, janela de taxa, gramática do id e validação são funções puras em `domain/`; nenhum LLM |
| VI. Conteúdo externo | ✅ | Credenciais nunca guardadas em claro (hash, R7); tools de escrita proibidas em público e opt-in por política em Assistant de usuário (FR-012, R10); MCP só por alias validado |
| VII. Falha fechada | ✅ | Erro de arquivo para o boot; Assistant inválido fica indisponível com motivo; OIDC sem emissor recusa tudo; policy malformada para o boot (não pula para uma mais permissiva) |
| VIII. Modelos por papel | ✅ | `models` por papel + `models.allow` obrigatória e não vazia; o pedido troca só `generation`, dentro da allowlist |
| IX. Proveniência | N/A | Sem retrieval nesta spec |
| X. Medir antes de calibrar | ✅ | Nenhum número de RAG ou modelo; `DEFAULT_RPM` é controle de segurança, não calibração de qualidade |
| XI. API independente, streaming | ✅ | O módulo não conhece HTTP; a borda é da 008 |
| XII. Simplicidade | ✅ | Sem ORM, sem ferramenta de migração, sem cache de chaves, sem controle de versão otimista; uma política por Principal (primeira que casa) |
| XIII. Portas e adapters | ✅ | Ver gate abaixo |

**Module boundary gate** *(PROJECT OVERRIDE — principle II, mandatory)*:

- [x] Source changes stay inside this module's paths — `ai-core/packages/core/src/ai_core/assistants/**` e
  `ai-core/packages/core/tests/assistants/**`; fora dele, apenas `ai-core/packages/core/pyproject.toml`
  (dependências), `ai-core/pyproject.toml` (import-linter, pytest) e `.github/workflows/core.yml` (serviço Postgres).
  **Nada** em `http/` nem em `bootstrap/`: a troca na plataforma é das passadas da 008 e da 011 (R2)
- [x] Every consumed seam is listed with its owner spec; no internals of other modules are used — Pack Registry e
  `Composition` (002), `FLOW_CHAT` (005; os nomes de flow chegam como valor, injetados pela 011), `ModelPolicy`/`ModelRef`
  (006, só value objects — ADR-016); MCP Registry (007) e índice de coleções pelas portas `McpDirectory` e `CollectionCatalog`, na forma que esta
  spec exige (R11)
- [x] Every seam this module exposes has a conformance test planned — `test_authenticator.py`,
  `test_grant_resolver.py`, `test_directory.py`, `test_key_admin.py`, mais `test_adversarial.py`
  ([contracts/assistants-api.md](contracts/assistants-api.md))
- [x] No seam changes — os seams desta spec nascem agora, na forma que 005 e 008 já declararam (R1). A direção entre
  003 e 006 muda no grafo (003 → 006) sem mudar nenhum seam, e está no ADR-016 com as specs afetadas (005, 006) e os
  textos da 006 anotados. O seam novo
  (**API Key Admin**, clarificação 2) é acréscimo, não mudança, e está registrado em `specs/README.md`; a 008 ganha o
  endpoint na passada dela
- [x] Import boundaries (import-linter) cover the new code — contratos novos listados em "Fronteiras verificadas"

**Ports & adapters gate** *(PROJECT OVERRIDE — principle XIII, ADR-012, mandatory)*:

- [x] The module follows `api.py` / `domain/` / `ports.py` / `service.py` / `adapters/` — completo, sem partes
  colapsadas
- [x] `api.py`, `domain/`, `ports.py` and `service.py` import no infrastructure framework — `yaml`, `jwt`,
  `cryptography`, `httpx`, `psycopg`, `psycopg_pool`, `fastapi` e `starlette` proibidos fora de `adapters/`; o domínio
  usa só `hashlib`, `hmac`, `fnmatch` e `re` da biblioteca padrão
- [x] Other modules are imported only through their `api.py` — contrato de import-linter; `api.py` da 003 não importa
  o resto do módulo
- [x] All I/O, time, randomness, secrets and trace go through a secondary port — arquivo (`AssistantConfigSource`),
  banco (`UserAssistantStore`, `ApiKeyStore`), rede (`OidcVerifier`), tempo (`Clock`), aleatoriedade
  (`TokenGenerator`). Trace: nenhum evento nesta fase — a resolução não é execução, e o id de requisição nasce na 008
- [x] Every secondary port exists for I/O, non-determinism or a planned swap — `RateCounterStore` (estado entre
  requisições; troca prevista para réplicas no `design.md`), `McpDirectory` e `CollectionCatalog` (troca prevista:
  007 e índice); nenhuma porta para regra pura
- [x] Every secondary port has an in-memory adapter and a conformance suite that also runs against the real adapter —
  tabela em [contracts/ports.md](contracts/ports.md); Postgres na CI
- [x] Services and adapters of other modules are instantiated only in the composition root — este módulo não
  instancia nada de outro; recebe `PackRegistry`, nomes de flow e portas prontos

**Resultado do gate (antes da Phase 0)**: PASS.

## Project Structure

### Documentation (this feature)

```text
specs/003-core-assistants-access/
├── spec.md
├── design.md
├── plan.md              # este arquivo
├── research.md          # R1–R17
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── assistants-api.md    # os quatro seams, erros e suítes de conformidade
│   ├── assistants-yaml.md   # formato do arquivo do operador e política de erros
│   ├── ports.md             # portas secundárias, adapters e conformidade
│   └── cli.md               # assistants validate; keys create|list|revoke
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
ai-core/
├── pyproject.toml                           # import-linter (contratos novos), pytest pythonpath
└── packages/core/
    ├── pyproject.toml                       # pyjwt[crypto], httpx, psycopg[binary], psycopg-pool
    ├── src/ai_core/assistants/
    │   ├── __init__.py
    │   ├── api.py                           # seams, value objects, vocabulário, erros
    │   ├── domain/
    │   │   ├── __init__.py
    │   │   ├── definitions.py               # mapeamento → AssistantDefinition/UserAssistantPolicy, problemas por Assistant
    │   │   ├── access.py                    # ACL, Principal a partir de claims, tempo do token, grupo de admin
    │   │   ├── resolution.py                # gramática do id, restrição de modelo, montagem do grant
    │   │   ├── policies.py                  # primeira política que casa, conformidade do rascunho
    │   │   ├── validation.py                # referências → AssistantStatus
    │   │   ├── keys.py                      # formato aic_<id>_<segredo>, hash, comparação em tempo constante
    │   │   └── rate.py                      # janela deslizante
    │   ├── ports.py                         # as nove portas de contracts/ports.md
    │   ├── service.py                       # AccessService (Authenticator, ApiKeyAdmin) e AssistantsService
    │   │                                    # (GrantResolver, AssistantDirectory, validate)
    │   └── adapters/
    │       ├── __init__.py
    │       ├── assistants_yaml.py           # AssistantConfigSource
    │       ├── assistants_postgres.py       # UserAssistantStore
    │       ├── api_keys_postgres.py         # ApiKeyStore
    │       ├── postgres_schema.py           # migrate(pool): aplica sql/ em ordem, com trava e versão (ADR-015)
    │       ├── sql/001_initial.sql
    │       ├── oidc.py                      # JwksOidcVerifier
    │       ├── rate_memory.py               # RateCounterStore
    │       ├── tokens.py                    # SecretsTokenGenerator
    │       ├── catalogs.py                  # McpDirectory e CollectionCatalog vazios
    │       ├── memory.py                    # adapters em memória e de teste de todas as portas
    │       └── cli.py                       # comandos de contracts/cli.md
    └── tests/assistants/
        ├── conftest.py
        ├── assistants_testkit.py            # construtores de configuração, Principals, registry e catálogos falsos,
        │                                    # chaves RSA/EC e JWT assinados, fixture de Postgres
        ├── unit/                            # domain/: um arquivo por regra
        ├── contract/                        # seams, suíte adversarial, portas (memória × real)
        └── integration/                     # Postgres real, CLI
```

**Structure Decision**: layout hexagonal completo do ADR-012, com os nomes de adapter do `design.md`
(`assistants_yaml.py`, `assistants_postgres.py`, `oidc.py`, `rate_memory.py`, `cli.py`). `api_keys.py` do `design.md`
vira `api_keys_postgres.py` porque o adapter em memória mora em `memory.py` com os demais. A autenticação mora aqui, não
em `ai_core/auth/` (ADR-012). Nenhum `health.py`: a saúde agregada é da 011 (US5) e consulta o que precisar pelos
seams.

## Fronteiras verificadas (import-linter)

Contratos novos em `ai-core/pyproject.toml`, no padrão dos módulos da Fase 1:

1. `api.py` da 003 não importa o resto do módulo;
2. `domain/` da 003 não importa portas, service nem adapters;
3. `service.py` da 003 não importa adapters;
4. o núcleo da 003 (`api`, `domain`, `ports`, `service`) não importa `yaml`, `jwt`, `cryptography`, `httpx`, `psycopg`,
   `psycopg_pool`;
5. a 003 só enxerga outros módulos pelo `api.py` (internals de `packs`, `graph`, `llm`, `observability` proibidos;
   `http` e `bootstrap` inteiros proibidos);
6. nenhum outro módulo importa internals da 003 (`assistants.domain`, `.ports`, `.service`, `.adapters`) — só a
   composition root;
7. o Model Router (`ai_core.llm`) não importa `ai_core.assistants` — torna executável a seta única 003 → 006 do
   ADR-016.

E a 003 entra na lista de origem dos contratos já existentes: "o framework HTTP só existe nos adapters da API", "o
framework de grafo só existe no adapter do motor", "nenhum módulo do core importa a API" e "nenhum módulo importa a
composition root".

## Seam Notes for Consumers

| Consumidor | O que precisa saber |
|---|---|
| 008 (passada da Fase 2) | Importa `Principal`, `Authenticator`, `GrantResolver`, `AssistantDirectory`, `ApiKeyAdmin` e os erros de `ai_core.assistants.api` e aposenta as cópias em `http/ports.py`; passa a ler `principal.subject` (não `id`). Extrai o token do cabeçalho (sem `Bearer`) antes de `authenticate`. Traduz `NotFound`→404, `RequestRejected`→400 (nomeando `field`), `Conflict`→409, `RateLimited`→429 com `Retry-After`, `AssistantUnavailable`→424 (clarificação de 2026-09-30 da 008). Recusa `WIDENING_FIELDS` no corpo. Monta `/v1/models` a partir de `discover`, o CRUD de Assistants de usuário a partir do `AssistantDirectory` e a administração de chaves na superfície privada a partir do `ApiKeyAdmin` (FR a acrescentar na spec dela). Ajusta o cenário US2.1 à regra "a listagem é o que o Principal resolve" |
| 011 (passada da Fase 2) | Constrói `AccessService` e `AssistantsService` depois do motor (precisa dos nomes de flow) e do Pack Runtime. Perfil `test`: `StaticOidcVerifier` e chave semeada, com credenciais conhecidas exportadas para as suítes; perfil persistente: pool Postgres, `migrate` do módulo no boot, `JwksOidcVerifier` (ou `DisabledOidcVerifier` sem emissor); perfil `memory`: decisão dela — uma chave de desenvolvimento lida do ambiente é a saída mais simples. Acrescenta a etapa "validação de Assistants" com `validate()`, registra `assistants validate` e `keys`, e remove `bootstrap/grants.py`. As suítes de bootstrap e de packs passam a enviar credencial e a usar `auth` e `models.allow` no `assistants.yaml` |
| 005 | Nada muda agora: o grant desta spec satisfaz o `Protocol` dela. `limits` já viaja no grant quando a Fase 3 o exigir |
| 006 | Nada muda: a política chega como `ModelPolicy`, com allowlist sempre não vazia; a regra de allowlist é conferida pela suíte de paridade (R5) |
| 004, 007 (Fase 3) | Recebem o grant pronto (`mcp_aliases`, `collections`, `allowed_tools`, `write_tools`). A 007 satisfaz `McpDirectory` estruturalmente, e a composition root troca o adapter vazio |
| Operador | `assistants.yaml` muda: `auth` e `visibility` obrigatórios, allowlist em `models.allow`; o boot diz, por Assistant, o que mudar. Chaves só pela CLI até a 008 expor o endpoint |

## Constitution Check — pós-design (Phase 1)

Reavaliado com [data-model.md](data-model.md), [contracts/](contracts/) e [quickstart.md](quickstart.md): **PASS**.

- IV: [contracts/assistants-api.md](contracts/assistants-api.md) amarra cada regra da fronteira a um teste; a suíte
  adversarial cobre SC-001, SC-002 e SC-005, e a invariante "grant ⊆ declarado" está no data-model.
- VII: [contracts/assistants-yaml.md](contracts/assistants-yaml.md) separa erro de arquivo (para o boot) de erro de
  Assistant (só ele indisponível) e justifica por que política malformada para o boot.
- XIII: [contracts/ports.md](contracts/ports.md) lista nove portas, cada uma com motivo, adapter em memória e suíte
  contra o real; as bibliotecas novas ficam em `adapters/`, verificado por import-linter.
- II: nenhum arquivo fora do módulo além de configuração de build, fronteiras e CI; o encaixe em 008 e 011 está
  descrito como trabalho das passadas delas, não feito daqui.

## Complexity Tracking

> Nenhuma violação. Complexidade adicional justificada (princípio XII):

| Complexidade | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Postgres e ADR-015 já nesta fase (R8) | clarificação 2 põe as chaves em armazenamento persistente, e o roadmap troca `AssistantStore` de usuário para Postgres na Fase 2 | adiar para a 011 deixaria as portas sem adapter real e sem suíte de conformidade contra ele — o que a governança exige em todo PR |
| Nove portas secundárias | cada uma tem I/O, não-determinismo ou troca prevista (tabela em contracts/ports.md) | juntar portas (ex.: uma `AssistantStore` para YAML e Postgres, R15) obrigaria adapters a implementar operações que recusam |
| Verificação de JWT local com JWKS em cache (R6) | a superfície pública precisa de OIDC de verdade, sem rede em toda requisição | introspecção por requisição põe o provedor no caminho de cada chamada |
| Suíte adversarial com hypothesis | SC-002 é "nenhuma capacidade fora do grant é alcançável" — um enunciado sobre todos os casos | casos escritos à mão cobririam só o que já se imaginou |
| Serviço Postgres na CI | princípio XIII e governança: a conformidade contra o adapter real roda em todo PR | Postgres só local transformaria a regra em opcional |

---

# Fase 3 (2026-10-02): passada de encaixe

Insumos: as duas clarificações de 2026-10-02; as pendências para a 003 nos planos da 004, da 005 (R33) e da 007;
[ADR-019](../../docs/adr/ADR-019-papeis-por-flow-no-seam-execution-engine.md). Decisões em [research.md](research.md)
R18–R23. **Sem divergência do `design.md`**: são regras de validação de referência, no lugar onde as outras já vivem.

## Summary (Fase 3)

A validação de referências (FR-011) ganha três regras: os papéis de modelo que o flow exige — publicados pelo motor
como dado (ADR-019) —, as entradas de `allowed_tools`/`write_tools` (com namespace, de um pack ou MCP do próprio
Assistant e, para pack, de tool que ele oferece) e a colisão de alias MCP com pack. Valem para Assistants de sistema e
de usuário, na mesma função que serve à resolução, ao boot e ao `assistants validate`. O contrato do `assistants.yaml`
ganha o exemplo com namespace.

## Technical Context (Fase 3)

**Dependências**: nenhuma nova. Seam novo consumido: `ExecutionEngine.flow_roles()` (005, ADR-019), pela 011.
**Storage**: sem mudança. **Testing**: unidade das três funções; contrato de validação e de criação/atualização de
usuário; nos toques, a conformidade do registro de flows da 005 e o boot real da 011.
**Constraints**: nenhuma rede na validação (tool de MCP conferida só pelo alias); a 003 não conhece a regra de papéis da
005 — só compara com o dado publicado.

## Constitution Check (Fase 3)

| Princípio | Resultado | Evidência |
|---|---|---|
| II. Seams | ✅ | Papéis por flow chegam como dado do seam da 005, sob o ADR-019; a 003 não conhece flow nenhum por dentro |
| IV. Assistant é a fronteira | ✅ | `allowed_tools`/`write_tools` mortos deixam de "parecer" restringir: o Assistant que não faz o que declara não serve |
| VII. Falha fechada | ✅ | Tudo vira indisponível com motivo antes de servir; usuário recebe `400` nomeando o campo |
| XIII. Portas e adapters | ✅ | Regras puras em `domain/validation.py`; nenhuma porta nova |

**Module boundary gate (Fase 3)**: `ai_core/assistants/**` e `tests/assistants/**`; **toques declarados**: 005
(`api.py`: `flow_roles()` no `Protocol`; `service.py`: a implementação; `contracts/execution-engine.md`; a conformidade
do registro de flows) e 011 (`wiring.assistants_service` passa `flow_roles`; um teste de boot), ambos sob o ADR-019;
`ai-core/pyproject.toml` (marca `us8`); `specs/README.md` (linha do seam). **Resultado**: PASS.

## Project Structure (Fase 3)

```text
ai-core/packages/core/src/ai_core/assistants/
├── domain/validation.py   # + role_reasons, tool_reasons, collision_reasons; reference_reasons as chama
└── service.py             # + flow_roles; pack_tools a partir do Pack Registry; _conform aplica as regras
ai-core/packages/core/src/ai_core/graph/{api,service}.py      # toque: flow_roles() (ADR-019)
ai-core/packages/core/src/ai_core/bootstrap/wiring.py         # toque: injeta engine.flow_roles()
```

## Seam Notes for Consumers (Fase 3)

| Consumidor | O que precisa saber |
|---|---|
| Operador | `allowed_tools`/`write_tools` sempre com namespace; Assistant `agentic` declara `models.controller`; alias MCP não pode ter o nome de um pack do mesmo Assistant |
| 008 | Criação/atualização de Assistant de usuário pode recusar com `field` = `models`, `allowed_tools`, `write_tools` ou `mcp` — a tradução para 400 já existe |
| 011 | Passar `flow_roles=engine.flow_roles()` ao `AssistantsService` |

# Fase 9 (2026-10-14): superfície de administração e sobreposições

Insumos: a clarificação de 2026-10-13 (o deploy vence), ADR-030, ADR-031, ADR-032, o plano da 012 (seam `PublicKeySet`,
audiências dos clientes) e o desenho aprovado da console (telas de Assistentes e de detalhe). Decisões em
[research.md](research.md) R25–R32. **Sem divergência do `design.md`** (que já recebeu a seção da Fase 9).

## Summary (Fase 9)

Duas user stories. **US9**: a terceira superfície, `admin`, aceita token da plataforma com a audiência da console ou
chave de API; admin passa a ser só o grupo; o verificador OIDC confere a audiência da superfície e lê as chaves de uma
fonte plugável — HTTP, como hoje, ou a função `jwks()` da 012 injetada pela 011. **US10**: Assistants de sistema ganham a
flag `overrides` no YAML e um armazenamento de sobreposições de `models` e `mcp`, com versão, autor e histórico; a
configuração efetiva (YAML + sobreposições ativas) passa a valer na descoberta, na resolução, na validação e na saúde;
o seam `SystemAssistantAdmin` expõe isso à 008. O deploy sempre vence: sobreposição de seção não liberada ou mudada fica
inativa, com motivo.

## Technical Context (Fase 9)

**Dependências**: nenhuma nova. **Seams consumidos novos**: nenhum por import — a função `jwks()` da 012 chega pela 011
como um chamável. **Storage**: migração `assistants/adapters/sql/003_system_overrides.sql`. **Testing**: unidade de
`domain/overrides.py`; conformidade do `SystemOverrideStore` (memória × Postgres), do `OidcVerifier` com as duas fontes e
do seam `SystemAssistantAdmin` (adversarial); superfícies. **Constraints**: nenhuma sobreposição amplia o YAML; o
`resolve` nunca usa sobreposição inativa ou inválida; cache por processo invalidado na gravação.

## Constitution Check (Fase 9)

| Princípio | Resultado | Evidência |
|---|---|---|
| II. Seams | ✅ | Mudança de seam (`SCHEME_OF_SURFACE`) sob o ADR-031, com o nome antigo mantido e depreciado por uma série; seam novo `SystemAssistantAdmin` com conformidade; a 012 não é importada |
| IV. Assistant é a fronteira | ✅ | A sobreposição fica dentro da allowlist e das regras de escrita; audiência própria impede token do chat na administração; não admin recebe 404 |
| VII. Falha fechada | ✅ | Sobreposição que deixou de valer torna o Assistant indisponível com motivo (`override.<seção>`), nunca resolvido em silêncio |
| VIII. Modelos por papel | ✅ | A sobreposição troca modelos por papel; a allowlist continua do deploy |
| XIII. Portas e adapters | ✅ | Regras puras em `domain/overrides.py`; porta nova `SystemOverrideStore` (armazenamento) com memória e Postgres; `JwksSource` dentro do adapter OIDC |

**Module boundary gate (Fase 9)**: `ai_core/assistants/**` e `tests/assistants/**`; `ai-core/pyproject.toml` (marcas
`us9`, `us10`); `specs/README.md`. **Nada** em `http/` nem `bootstrap/`: a 008 passa a usar `SCHEMES_OF_SURFACE` e o
seam novo na passada dela; a 011 monta o `CallableJwksSource`, as audiências e o `SystemOverrideStore` na dela.
**Resultado**: PASS.

## Project Structure (Fase 9)

```text
ai-core/packages/core/src/ai_core/assistants/
├── api.py                         # + ADMIN_SURFACE, SCHEMES_OF_SURFACE, OverrideSection, ModelsOverride, McpOverride,
│                                  #   OverrideView, SystemAssistantView, OverrideHistoryEntry, SystemAssistantAdmin
├── domain/
│   ├── access.py                  # is_admin só pelo grupo
│   ├── definitions.py             # + overrides no AssistantDefinition e no read_config
│   └── overrides.py               # novo: impressão digital, estados, definição efetiva, mesclagem de allowed_tools
├── ports.py                       # OidcVerifier.verify(token, *, audience); + SystemOverrideStore
├── service.py                     # AccessService (superfícies, audiências); AssistantsService (efetiva, seam novo)
└── adapters/
    ├── oidc.py                    # JwksSource: HttpJwksSource, CallableJwksSource
    ├── memory.py                  # + InMemorySystemOverrideStore; StaticOidcVerifier com audiência
    ├── overrides_postgres.py      # novo: PostgresSystemOverrideStore
    └── sql/003_system_overrides.sql
```

## Seam Notes for Consumers (Fase 9)

| Consumidor | O que precisa saber |
|---|---|
| 008 | Usar `SCHEMES_OF_SURFACE`; a superfície `admin` chama `authenticate(surface="admin", …)`; `SystemAssistantAdmin` para as rotas de Assistants; `RequestRejected` → 422 nomeando o campo, `Conflict` → 409 |
| 011 | `OidcAudiences` a partir dos clientes da 012; `JwksOidcVerifier(source=CallableJwksSource(identity.jwks))` com a identidade ligada; `SystemOverrideStore` no perfil (memória/Postgres) e a migração `003`; saúde por `assistants.declared_models()` |
| Operador | `overrides: [models, mcp]` por Assistant; sem a flag, nada muda pela console |

---

# Passada de 2026-10-20: identidade Axon (US11; [ADR-037](../../docs/adr/ADR-037-a-plataforma-se-chama-axon.md))

> As seções acima são os planos das passadas anteriores e ficam como foram executadas (ADR-037, item 6); os nomes
> antigos nelas se leem pela tabela do ADR-037. Esta seção é o plano da US11.

**Insumos lidos**: [spec.md](spec.md) (US11, FR-024–FR-027, SC-008, clarificações de 2026-10-20), [design.md](design.md),
ADR-031 (a separação das audiências), ADR-037, constituição 1.3.1, a passada da 011 (perfil `test`, chave de
desenvolvimento, clientes de exemplo da identidade). Research: R33–R37. **Sem divergência do `design.md`** além dos
nomes; sem ADR novo.

## Summary (US11)

As audiências passam a `axon` e `axon-admin` (R33), e as chaves de API, ao prefixo `axn_` (R34), em corte seco e sem
migração (R35). A 011 (credencial de teste, mensagens, clientes de exemplo), o e2e da console, os testes e os documentos
vivos acompanham por lista fechada (R36); um teste novo prova os nomes novos e a recusa dos antigos (R37).

## Technical Context (US11)

- **Language/Version, dependências, storage**: sem mudança; sem migração.
- **Testing**: um arquivo de contrato novo (`us11`), um caso novo em `test_keys.py`, literais trocados nas suítes; o e2e
  da console com a chave e as audiências novas.
- **Scale/Scope**: duas constantes de produção na 003 (`OidcAudiences`, `KEY_PREFIX`); na 011, três arquivos; ~25
  arquivos de teste; 2 do e2e; ~12 documentos vivos.
- Nenhum `NEEDS CLARIFICATION`.

## Constitution Check (US11)

| Princípio | Resultado | Evidência |
|---|---|---|
| II. Módulos substituíveis por seams | ✅ | A forma do Principal, do Execution Grant e do `Authenticator` não muda; os nomes mudam por ADR, no módulo dono |
| VII. Falha fechada e explícita | ✅ | Credencial antiga é não autenticada (401), como qualquer inválida; nada é aceito em silêncio (R35) |
| ADR-031 (superfícies separadas) | ✅ | A separação de audiências continua: o token do chat não alcança a administração (cen. 3) |
| XII. Simplicidade deliberada | ✅ | Sem janela de compatibilidade nem migração (R35) |
| XIII. Portas e adapters | ✅ | Só `domain/` muda na 003; nenhuma porta nova |

**Module boundary gate**: `axon_ai/assistants/domain/{access,keys}.py` e `tests/assistants/**`. Fora do módulo, só os
consumidores que o ADR-037 (item 7) atribui a esta passada (R36): a composition root (011) nos três arquivos que
carregam audiência ou formato de chave, duas docstrings (012, 008), testes que usam credenciais, o e2e da console e
documentos vivos. Nenhum comportamento de outro módulo muda. **Ports & adapters gate**: sem mudança. **Resultado**: PASS.

## Project Structure (US11)

```text
axon-ai/
├── pyproject.toml                                   # marca us11
├── console/e2e/{serve_platform.py,fixtures/session.ts}   # audiências e TEST_API_KEY (R36)
└── packages/core/
    ├── src/axon_ai/
    │   ├── assistants/domain/access.py              # OidcAudiences("axon", "axon-admin") (R33)
    │   ├── assistants/domain/keys.py                # KEY_PREFIX = "axn_" (R34)
    │   ├── bootstrap/{identity,settings,profiles}.py   # clientes de exemplo, mensagens, TEST_API_KEY (R33, R34)
    │   ├── identity/domain/tokens.py                # docstring (R36)
    │   └── http/adapters/admin.py                   # docstring (R36)
    └── tests/
        ├── assistants/contract/test_credentials_axon.py   # novo (R37)
        └── …                                        # literais de credencial e audiência (R36)
```

## Seam Notes for Consumers (US11)

| Consumidor | O que muda para ele |
|---|---|
| 008 | Nada no código: a API repassa a credencial; os contratos citam `axn_…` e `axon-admin` |
| 011 | `TEST_API_KEY` com valor novo; mensagens da chave de desenvolvimento pelo `KEY_PREFIX`; clientes de exemplo com as audiências novas |
| 012 | Os clientes do `identity.yaml` declaram `audience: axon` / `axon-admin`; o provedor não muda |
| 013 | O e2e usa a chave e as audiências novas; a console não conhece a audiência (o cliente `console` a recebe da 012) |
| Suíte de pack externo | `TEST_API_KEY` começa com `axn_`; quem a importa não muda de código |
| Instalação | Nada até a passada dela: o `identity.yaml` do deploy e a imagem continuam com a tag antiga |

## Complexity Tracking (US11)

Nenhuma linha nova.

## Constitution Check — pós-design (US11)

Reavaliado com [design.md](design.md), [data-model.md](data-model.md), [contracts/](contracts/) e
[quickstart.md](quickstart.md) ("Fase 9, incremento 9.5"): **PASS**.

---

# Passada de 2026-10-21: rotação de chaves e sobreposição de `auth` (US12, US13; [ADR-040](../../docs/adr/ADR-040-rotacao-de-chaves-e-acesso-sobreponivel.md))

> As seções acima ficam como foram executadas. Esta é o plano da US12 e da US13.

**Insumos lidos**: [spec.md](spec.md) (US12, US13, FR-028–FR-036, SC-009, SC-010, clarificações de 2026-10-21),
[design.md](design.md), ADR-012, ADR-015, ADR-031, ADR-032, ADR-040, constituição 1.3.1. Research: R38–R44. **Sem
divergência** do `design.md` nem dos ADRs; sem ADR novo.

## Summary (US12, US13)

**US12**: o seam API Key Admin ganha `rotate` — mesmo `key_id`, subject, grupos e rótulo, segredo novo mostrado uma vez,
o antigo recusado na requisição seguinte, só para chave ativa (R38, R39); a porta `ApiKeyStore` ganha a troca atômica do
hash; a emissão confere o nome do sistema e, pela administração, recusa o grupo de administração (R40); `axon keys
rotate`. **US13**: `auth` entra nas seções sobreponíveis com o mecanismo do ADR-032 (R41), falha fechada quando um
deploy torna privado um Assistant com `*` sobreposto (R42), e o seam System Assistant Admin ganha `override_auth` e o
`auth` do YAML e efetivo na visão (R43). Duas migrações aditivas (R44).

## Technical Context (US12, US13)

- **Language/Version, dependências**: sem mudança.
- **Storage**: `sql/004_api_key_rotation.sql` e `sql/005_auth_overrides.sql` no schema `assistants` (ADR-015).
- **Testing**: dois arquivos de contrato novos (`us12`, `us13`), acréscimos na conformidade do `ApiKeyStore`, na unidade
  das sobreposições, na CLI e nas migrações.
- **Scale/Scope**: `api.py`, `ports.py`, `service.py`, `domain/overrides.py`, `domain/definitions.py` (leitura de
  `overrides`), três adapters (memória, Postgres das chaves, CLI) e duas migrações; fora do módulo, uma linha de registro
  na 011.
- Nenhum `NEEDS CLARIFICATION`.

## Constitution Check (US12, US13)

| Princípio | Resultado | Evidência |
|---|---|---|
| II. Módulos substituíveis por seams | ✅ | Dois seams mudam de forma aditiva sob o ADR-040; a 008 é a consumidora e se atualiza na passada dela; a 012 continua não importada (R43: sem conferir grupos) |
| IV. O Assistant é a fronteira de isolamento | ✅ | A sobreposição de `auth` passa pela FR-012 na gravação e na efetiva; `visibility` fica no deploy; o 404-não-403 da resolução não muda |
| VII. Falha fechada e explícita | ✅ | Chave revogada não rotaciona; `*` em Assistant que virou privado → indisponível com `override.auth` (R42); conteúdo ilegível → inativa |
| XII. Simplicidade deliberada | ✅ | Sem janela de convivência, sem cadastro de sistemas, sem operação nova para o seletor (ADR-040; clarificação 3) |
| XIII. Portas e adapters | ✅ | Regras puras em `domain/overrides.py`; a troca do hash é operação da porta `ApiKeyStore` (atomicidade no adapter); aleatoriedade pelo `TokenGenerator`, tempo pelo `Clock` |

**Module boundary gate**: `axon_ai/assistants/**`, `tests/assistants/**`, `axon-ai/pyproject.toml` (marcas `us12`,
`us13`), `specs/README.md` (linhas dos dois seams) e `design.md`. Fora do módulo, só `bootstrap/cli.py` (011): uma
entrada `("keys", "rotate")` na lista de subcomandos, atribuída pelo ADR-040. Nada em `http/`: as rotas são da passada
da 008. **Ports & adapters gate**: nenhuma porta nova; uma operação nova na porta `ApiKeyStore`, com conformidade.
**Resultado**: PASS.

## Project Structure (US12, US13)

```text
axon-ai/
├── pyproject.toml                                  # marcas us12, us13
└── packages/core/
    ├── src/axon_ai/
    │   ├── assistants/
    │   │   ├── api.py                              # ApiKeyInfo.rotated_at; ApiKeyAdmin.rotate; OverrideSection + "auth";
    │   │   │                                       #   AuthOverride; SystemAssistantView.yaml_auth/effective_auth;
    │   │   │                                       #   SystemAssistantAdmin.override_auth (R38, R41, R43)
    │   │   ├── ports.py                            # ApiKeyStore.rotate (R38)
    │   │   ├── service.py                          # rotate, rotate_as_operator; nome do sistema e grupo admin (R40);
    │   │   │                                       #   override_auth e a visão (R43)
    │   │   ├── domain/overrides.py                 # yaml_auth, impressão digital, payload, apply_auth (R41, R42)
    │   │   └── adapters/
    │   │       ├── memory.py                       # InMemoryApiKeyStore.rotate
    │   │       ├── api_keys_postgres.py            # rotate; rotated_at nas colunas
    │   │       ├── cli.py                          # keys_rotate_command
    │   │       └── sql/{004_api_key_rotation,005_auth_overrides}.sql
    │   └── bootstrap/cli.py                        # ("keys", "rotate") — registro (011, ADR-040)
    └── tests/assistants/
        ├── contract/{test_key_rotation,test_auth_override}.py   # novos (R44)
        ├── contract/test_api_key_store.py          # conformidade de rotate
        ├── unit/test_overrides.py                  # seção auth
        └── integration/{test_cli,test_postgres_migrations}.py
```

## Seam Notes for Consumers (US12, US13)

| Consumidor | O que precisa saber |
|---|---|
| 008 | `ApiKeyAdmin.rotate(actor=…, key_id=…)` → `IssuedApiKey` (`Conflict` → 409 para chave revogada; `NotFound` → 404); `ApiKeyInfo.rotated_at` na listagem; `issue` recusa o grupo de administração com `RequestRejected(field="groups")` e nome de sistema fora do padrão com `field="subject"`; `SystemAssistantAdmin.override_auth` com `RequestRejected(field="auth.schemes" \| "auth.allow")` e `Conflict`; `discard_override(…, "auth", …)`; `SystemAssistantView.yaml_auth`/`effective_auth` e `overridable` com `auth`. Os sistemas para o seletor saem de `keys()`; os grupos, da 012 |
| 011 | Registrar `("keys", "rotate")`; as migrações 004 e 005 entram pela lista do adapter, sem mudança na etapa |
| Operador | `overrides: [auth]` libera a seção; `axon keys rotate <key_id>`; chave do grupo de administração só pela CLI |

## Complexity Tracking (US12, US13)

Nenhuma linha nova.

## Constitution Check — pós-design (US12, US13)

Reavaliado com [data-model.md](data-model.md), [contracts/](contracts/) e [quickstart.md](quickstart.md) ("Fase 9,
2026-10-21"): **PASS**.
