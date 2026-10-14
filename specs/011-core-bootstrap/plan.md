# Implementation Plan: Bootstrap e composition root — boot, perfis e plataforma em memória

**Branch**: `011-core-bootstrap` | **Date**: 2026-09-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/011-core-bootstrap/spec.md`

**Architecture inputs** *(PROJECT OVERRIDE — agentic-app)*: before filling Technical Context, READ
`/specs/011-core-bootstrap/design.md` (including its "Portas e adapters" section) and every ADR listed
in the spec's Module Boundary, plus ADR-012 (architectural style). Decisions recorded there are
**pre-approved**: carry them into this plan and into `research.md` as
"Decision / Rationale (ADR-xxx) / Alternatives", do not re-research them. Any deviation requires a
new ADR in `docs/adr/` and must be listed in Complexity Tracking.

Insumos lidos: [design.md](design.md), ADR-009, ADR-012, ADR-013; e os seis módulos já implementados — contratos
(001), Pack Runtime (002), motor (005), Model Router (006), API HTTP (008) e trace (009). Consumidores: o operador e a
CI. **Sem divergência do `design.md`**: a única diferença é de escopo — `health.py` e os subcomandos contribuídos por
módulo são da Fase 2, e o `assistants.yaml` que o design previa como armazenamento da 003 nasce aqui, lido por este
módulo, até que a 003 exista ([research.md](research.md) R4, R9). Nenhum ADR novo.

## Summary

Entregar a composition root: carregar a configuração do operador, validar o perfil de adapters, conduzir o boot por
**etapas declaradas** — configuração → adapters → packs → motor → API —, cada uma com política de falha própria, e
servir a aplicação com `ai-core serve`. Dois perfis: `memory` (Ollama de verdade, trace em arquivo) e `test`
(plataforma inteira em memória, provider simulado, relógio fixo), este último **parte da distribuição**, para que
qualquer suíte monte a plataforma com uma chamada. É o módulo que amarra os seis já prontos e substitui as montagens
manuais que hoje existem nas suítes de 005 e 008. Escopo da Fase 1: **US1, US2 (perfil em memória) e US3**.

## Technical Context

**Language/Version**: Python 3.14 (módulo da distribuição `ai-core`, `requires-python = ">=3.14"`)

**Primary Dependencies**: os `api.py`, `service.py` e `adapters/` de 002, 005, 006, 008 e 009 — **este é o único
módulo autorizado a importá-los** (princípio XIII); `pyyaml` (já presente, usado pela 002); **nova** —
`uvicorn>=0.53,<1`, para o `serve` (R5)

**Storage**: arquivos de configuração montados na imagem (`packs.yaml`, `assistants.yaml`) e variáveis de ambiente;
nenhum armazenamento persistente nesta fase

**Testing**: pytest + pytest-asyncio; sequência e políticas de falha verificadas com etapas de teste, sem plataforma;
conversa ponta a ponta pela aplicação montada no perfil `test` (R10)

**Target Platform**: processo do core na imagem Linux ARM64

**Performance Goals**: boot sem I/O além de ler dois arquivos e descobrir entry points; nenhum adapter é instanciado
durante a execução de uma requisição (US1 cenário 5)

**Constraints**: nenhum outro módulo importa este (contrato de import-linter); a ordem de boot é dado, não código
(R1); um único relógio atende todos os módulos com porta de tempo (FR-008, ADR-013); o perfil de teste não fala com
rede nem com serviço externo (FR-014, SC-003)

**Scale/Scope**: 1 módulo — `ports.py`, `settings.py`, `profiles.py`, `grants.py`, `wiring.py`, `lifecycle.py` e
`cli.py`; 2 perfis dos 3; 5 etapas de boot das 7

Nenhum `NEEDS CLARIFICATION`: as quatro perguntas abertas foram resolvidas em 2026-09-21 e estão em
[research.md](research.md) R1, R4, R5 e R7.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Resultado | Evidência |
|---|---|---|
| I. Núcleo agnóstico | ✅ | O bootstrap lê nomes de pack e de Assistant como dado; nenhum domínio aparece em código ou configuração de exemplo |
| II. Seams | ✅ | Não expõe seam Python. Consome os `api.py` e, **por exceção declarada**, os `service.py` e `adapters/` de todos os módulos — é o que o ADR-012 reserva à composition root |
| III. O core orquestra | ✅ | O bootstrap não executa nada: monta e entrega. A topologia continua do motor |
| IV. Assistant é a fronteira | ✅ | O grant é montado a partir de `assistants.yaml` (R4): a fronteira é configuração, não código. O modelo pedido no id só vale dentro da allowlist do Assistant |
| V. Determinismo | ✅ | Validação de configuração, de perfil e a sequência de etapas são puras e testáveis sem plataforma |
| VI. Conteúdo externo | ✅ | Configuração do operador é dado validado, com erro que nomeia o campo; segredo nunca aparece em log ou mensagem (FR-009, Fase 3 com os providers remotos) |
| VII. Falha fechada | ✅ | É o ponto da spec: configuração e perfil inválidos impedem o boot; pack em erro degrada e o resto atende (FR-003, SC-004) |
| VIII. Modelos por papel | ✅ | `assistants.yaml` declara modelo por papel e allowlist, que viram a Model Policy da 006 |
| IX. Proveniência | N/A | Sem retrieval nesta fase |
| X. Medir antes de calibrar | ✅ | Nenhum número calibrável: prazo de encerramento é configuração do operador, não valor de qualidade |
| XI. Streaming e independência da interface | ✅ | O `serve` só abre a porta; a API já entrega streaming, e nenhuma lógica de agente vive aqui |
| XII. Simplicidade | ✅ | Sem container de injeção, sem saúde agregada, sem perfil persistente, sem subcomandos de módulo — cada um na fase que o usa (R2, R9) |
| XIII. Portas e adapters | ✅ | Ver gate abaixo |

**Module boundary gate** *(PROJECT OVERRIDE — principle II, mandatory)*:

- [x] Source changes stay inside this module's paths — `ai-core/packages/core/src/ai_core/bootstrap/**` e
  `ai-core/packages/core/tests/bootstrap/**`; fora dele, apenas `ai-core/packages/core/pyproject.toml` (dependência
  `uvicorn` e o ponto de entrada `ai-core`) e `ai-core/pyproject.toml` (import-linter, pytest)
- [x] Every consumed seam is listed with its owner spec; no internals of other modules are used — consome os `api.py`
  de 002, 005, 006, 008 e 009 **e**, por exceção do princípio XIII, o `service.py` e os `adapters/` de cada um. É o
  único módulo autorizado, e o contrato de import-linter garante que continue sendo
- [x] Every seam this module exposes has a conformance test planned — não expõe seam Python; o que expõe é o processo:
  `tests/bootstrap/contract/test_boot_sequence.py` (ordem e políticas de falha) e
  `tests/bootstrap/integration/test_platform_test_profile.py` (plataforma inteira, conversa por HTTP)
- [x] No seam changes — nenhum. Este módulo só consome
- [x] Import boundaries (import-linter) cover the new code — contratos novos do R11: nenhum módulo importa
  `ai_core.bootstrap`, e cada módulo continua proibido de importar `service.py`/`adapters/` dos outros

**Ports & adapters gate** *(PROJECT OVERRIDE — principle XIII, ADR-012, mandatory)*:

- [x] The module follows `api.py` / `domain/` / `ports.py` / `service.py` / `adapters/` — **não**, e é deliberado: o
  `design.md` fixa um layout próprio para a composition root (`settings.py`, `profiles.py`, `wiring.py`,
  `lifecycle.py`, `cli.py`), porque ela não é um módulo de domínio e não expõe seam. As regras puras (validação de
  configuração e de perfil, sequência) ficam separadas das que fazem I/O, e é isso que a suíte exercita
- [x] `api.py`, `domain/`, `ports.py` and `service.py` import no infrastructure framework — aqui a regra se inverte
  por definição: este módulo importa tudo, inclusive `uvicorn`, e é o único que pode
- [x] Other modules are imported only through their `api.py` — exceção declarada do princípio XIII: só a composition
  root importa também `service.py` e `adapters/`
- [x] All I/O, time, randomness, secrets and trace go through a secondary port; `domain/` does no I/O — a leitura de
  configuração passa pela porta `ConfigSource`, com adapter de ambiente e adapter em memória
- [x] Every secondary port exists for I/O, non-determinism or a planned swap — só `ConfigSource`, por I/O
- [x] Every secondary port has an in-memory adapter and a conformance suite that also runs against the real adapter —
  `InMemoryConfigSource` × `EnvConfigSource`
- [x] Services and adapters of other modules are instantiated only in the composition root — é **este** módulo

**Resultado do gate (antes da Phase 0)**: PASS.

## Project Structure

### Documentation (this feature)

```text
specs/011-core-bootstrap/
├── spec.md
├── design.md
├── plan.md              # este arquivo
├── research.md
├── data-model.md
├── quickstart.md
├── checklists/requirements.md   # 16/16, de 2026-09-14
├── contracts/
│   ├── boot-sequence.md      # etapas, políticas de falha, encerramento
│   ├── profiles.md           # portas exigidas, perfis memory e test, validação
│   └── configuration.md      # packs.yaml (002), assistants.yaml (aqui) e ambiente
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
ai-core/
├── pyproject.toml                       # contratos novos de import-linter (R11)
└── packages/core/
    ├── pyproject.toml                   # uvicorn; [project.scripts] ai-core
    ├── src/ai_core/bootstrap/
    │   ├── __init__.py                  # docstring: a única spec que importa service/adapters de outros módulos
    │   ├── ports.py                     # ConfigSource
    │   ├── settings.py                  # Settings do operador: validação pura + adapters de origem
    │   ├── profiles.py                  # portas exigidas, perfis `memory` e `test`, validação do perfil
    │   ├── grants.py                    # assistants.yaml → resolvedor de grant (porta da 008)
    │   ├── wiring.py                    # constrói Platform: packs, trace, router, motor, app
    │   ├── lifecycle.py                 # etapas declaradas, execução com política de falha, encerramento inverso
    │   └── cli.py                       # `ai-core serve`
    └── tests/bootstrap/
        ├── conftest.py
        ├── bootstrap_testkit.py
        ├── unit/                        # settings, perfis, grants, sequência com etapas de teste
        ├── contract/                    # ordem de boot, falha fechada, encerramento
        └── integration/                 # plataforma inteira no perfil `test`, conversa por HTTP
```

**Structure Decision**: layout do `design.md`. `health.py` não nasce nesta fase (US5 é Fase 2). O perfil `test` fica
em `profiles.py`, dentro da distribuição (R7) — é o que permite a um pack externo montar a plataforma.

## Seam Notes for Consumers

| Consumidor | O que precisa saber |
|---|---|
| Operador | `ai-core serve` sobe a plataforma; a configuração vem de `packs.yaml`, `assistants.yaml` e variáveis de ambiente. Erro de configuração ou de perfil impede o boot e nomeia o campo; pack em erro aparece no relatório de boot e o resto atende |
| Suítes de 005 e 008 | Podem trocar a montagem manual por `platform(profile="test")`; o perfil devolve a plataforma inteira com provider simulado e relógio fixo |
| Packs externos | O perfil `test` é parte da distribuição: a suíte de um pack pode subir a plataforma de verdade e conversar com seu pack por HTTP |
| 003 (Fase 2) | Assume `assistants.yaml` e passa a fornecer o resolvedor de grant e o autenticador; o bootstrap troca o adapter e a etapa de validação de Assistants entra na lista |
| 007 (Fase 3) | Acrescenta a etapa de registry MCP à lista, sem tocar na sequência |

## Constitution Check — pós-design (Phase 1)

Reavaliado com [data-model.md](data-model.md), [contracts/](contracts/) e [quickstart.md](quickstart.md): **PASS**.

- VII: `contracts/boot-sequence.md` fixa a política por etapa e o que acontece em cada falha; a tabela de falhas do
  data-model cobre configuração inválida, perfil incompleto, pack em erro e falha de etapa crítica.
- XIII: a exceção deste módulo está declarada e é verificada nos dois sentidos pelo import-linter — ninguém importa o
  bootstrap, e nenhum módulo importa internals de outro.
- IV: o grant sai de `assistants.yaml`; `contracts/configuration.md` fixa que o modelo pedido no id de modelo só vale
  se a allowlist do Assistant permitir — restringir, nunca ampliar.

## Complexity Tracking

> Nenhuma violação. Complexidade adicional justificada (princípio XII):

| Complexidade | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Etapas de boot como valores (R1) | a ordem e a política de falha são requisito (FR-002, FR-003) e precisam ser verificáveis sem plataforma | função linear espalharia a política pelas chamadas e seria reescrita a cada fase |
| Perfil como conjunto de fábricas, com lista de portas exigidas (R6) | FR-004 manda invalidar perfil incompleto **antes** do boot | confiar no erro de construção faria a falha aparecer tarde e sem nomear a porta |
| `assistants.yaml` lido aqui antes de a 003 existir (R4) | a API resolve `<assistant>/<modelo>` desde a Fase 1 | Assistant em código contraria o princípio IV; por ambiente, o formato seria reinventado na Fase 2 |

---

# Fase 2 (2026-09-30): US2 (persistente), US4 (CLI), US5 (saúde) e autenticação real

Insumos: as duas clarificações de 2026-09-30; 002 US4, 003 e 008 Fase 2 implementadas; ADR-015. Decisões em
[research.md](research.md) R11–R20. **Sem divergência do `design.md`**: os três perfis, `health.py`, a raiz com os
subcomandos dos módulos e as tarefas periódicas agendadas no boot são os que ele descreve.

## Summary (Fase 2)

A composition root passa a montar a plataforma de produção: o perfil `persistent` com Postgres (pool aberto no ciclo
de vida da app, migrações de `assistants` e `http` conferidas no boot), autenticação real nos três perfis — o anônimo
sai —, a raiz `ai-core` com `packs`, `assistants validate`, `keys` e `health`, a saúde agregada que só responde 503
quando algo crítico falha, e a expiração periódica das conversas.

## Technical Context (Fase 2)

**Primary Dependencies**: + `psycopg_pool` (o pool, já no workspace), `httpx` (cliente do JWKS, já no workspace), os
`adapters/` da 003 e da 008 que a fase liga; nenhuma dependência nova

**Storage**: Postgres no `persistent` — schemas `assistants` e `http` (ADR-015); memória nos outros

**Testing**: perfis e saúde com checagens falsas; subcomandos por `main(argv)`; o `persistent` contra Postgres real com
`AI_CORE_TEST_POSTGRES_DSN` (R20)

**Constraints**: nenhum segredo em log, relatório ou erro (FR-009); nenhum perfil sem autenticação (FR-015); só item
crítico derruba a saúde (FR-012); trocar de perfil não toca módulo (FR-005)

## Constitution Check (Fase 2)

| Princípio | Resultado | Evidência |
|---|---|---|
| II. Seams | ✅ | Continua consumindo `api.py`, `service.py` e `adapters/` dos módulos (exceção do princípio XIII); os toques na 008 são aditivos e declarados abaixo |
| IV. Assistant é a fronteira | ✅ | Autenticação real nos três perfis: nenhuma requisição chega à resolução sem Principal verificado |
| VI. Conteúdo externo | ✅ | Segredos (`AI_CORE_DATABASE_URL`, `AI_CORE_DEV_API_KEY`) nunca impressos |
| VII. Falha fechada | ✅ | Banco inacessível ou migração quebrada param o boot nomeando porta e adapter; item não crítico degrada sem derrubar |
| XII. Simplicidade | ✅ | argparse; cache de saúde simples; nenhuma dependência nova |
| XIII. Portas e adapters | ✅ | A escolha de adapter por porta continua sendo dado (R12) |

**Module boundary gate (Fase 2)**:

- [x] Source changes stay inside this module's paths — `ai_core/bootstrap/**` e `tests/bootstrap/**`, **mais** dois
  toques aditivos e declarados na 008: `HealthItem.critical` e `HealthReport.status` (`domain/records.py`,
  `domain/private.py`, rota de saúde — 503 só em `down`, clarificação 2) e o parâmetro opcional `lifespan` de
  `create_app` (R14); e as suítes da 008 que conferem a saúde
- [x] Every consumed seam is listed — 002 (`PackRegistry`, CLI), 003 (serviços, adapters, CLI), 005, 006
  (`ModelRouting.check`), 008 (app, portas), 009
- [x] No seam changes — os toques na 008 são em portas e tipos internos dela, de forma aditiva
- [x] Import boundaries — nenhum módulo importa `ai_core.bootstrap` (contrato existente)

**Resultado do gate (Fase 2)**: PASS.

## Project Structure (Fase 2)

```text
ai-core/packages/core/src/ai_core/bootstrap/
├── settings.py     # variáveis novas; segredos fora do repr
├── profiles.py     # três perfis; fábricas com as partes já construídas; credenciais do perfil test
├── wiring.py       # Platform com assistants/access/routing/conversations; ciclo de vida da app (pool, tarefas)
├── health.py       # PlatformHealth: itens críticos e não críticos, cache, timeout
├── lifecycle.py    # sem mudança de contrato
└── cli.py          # raiz ai-core: serve, packs, assistants validate, keys, health
```

## Seam Notes for Consumers (Fase 2)

| Consumidor | O que precisa saber |
|---|---|
| Operador | `AI_CORE_PROFILE=persistent` + `AI_CORE_DATABASE_URL`; a primeira chave sai de `ai-core keys create`; OIDC por `AI_CORE_OIDC_*`. No `memory`, `AI_CORE_DEV_API_KEY` |
| Suítes de packs externos | O perfil `test` exige credencial: `Authorization: Bearer <TEST_OIDC_TOKEN>` (ou `<TEST_API_KEY>` na privada), de `ai_core.bootstrap.profiles` |
| Monitoramento | `GET /private/v1/health` com qualquer chave: 503 só quando algo crítico (banco) falha |

## Complexity Tracking (Fase 2)

| Complexidade | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Pool conferido no boot e aberto no ciclo de vida da app (R13) | o pool do psycopg pertence ao laço em que abre; o boot e o servidor rodam em laços diferentes | abrir no boot quebraria ao servir; só abrir no servidor deixaria a falha de banco aparecer depois de a API existir |
| Cache de 15 s na saúde (R16) | o monitor consulta a saúde com frequência e cada consulta tocaria o provider | sem cache, a saúde vira carga sobre o modelo local |

---

# Fase 3 (2026-10-02): encaixe da 007, da 004 e do `agentic`

Insumos: as três clarificações de 2026-10-02; as notas para a 011 nos planos da 007 e da 004; o `design.md` (tabela de
portas por perfil); ADR-012, ADR-013, ADR-015, ADR-017, ADR-018. Decisões em [research.md](research.md) R21–R33.
**Divergência do `design.md`**: nenhuma — a tabela de portas por perfil (inclusive `stdio` só no `persistent`) é a
dele. **Ajuste em relação à nota da 007**: o `mcp.yaml` é lido na etapa `configuration`, não em `mcp_registry`, porque
o transporte HTTP precisa dos hosts do arquivo já na etapa de adapters e o FR-001 pede a configuração validada antes de
qualquer outra etapa; o erro de arquivo continua parando o boot (R23).

## Summary (Fase 3)

A plataforma em execução passa a oferecer o loop agêntico com MCP: os três perfis montam o registry MCP da 007 e o
gateway de tools da 004 (auditoria em memória ou Postgres), o motor recebe o gateway e oferece `agentic`, a 003 valida
Assistants contra o registry real, a saúde ganha um item por servidor MCP global, `ai-core audit` lista as escritas, e o
SDK de MCP nunca registra conteúdo em `DEBUG`. As suítes trocam portas na montagem para programar controller e
servidores MCP, e uma conversa `agentic` + MCP atravessa a API no perfil `test` sem rede.

## Technical Context (Fase 3)

**Primary Dependencies**: os `service.py` e `adapters/` da 007 e da 004 (a exceção do princípio XIII); nenhuma
dependência nova

**Storage**: Postgres no `persistent` — schemas `mcp` e `capabilities` somam-se a `assistants` e `http` (ADR-015)

**Testing**: unidade (configuração, perfis, trocas, saúde), contrato (etapas, logging), CLI por `main(argv)`,
integração ponta a ponta no `test` e `persistent` contra Postgres real (R32)

**Constraints**: o boot não sai para a rede (clarificação 1); nenhuma credencial de MCP em log, relatório ou erro
(FR-009); trocas de porta só pela chamada Python (clarificação 2); trocar de perfil não toca módulo (FR-005)

**Scale/Scope**: `settings.py` (4 campos), `profiles.py` (6 portas), `wiring.py` (etapa nova, fábricas da 007 e da
004, trocas), `health.py` (itens de MCP), `cli.py` (`audit`); 1 etapa nova; nenhum seam novo

## Constitution Check (Fase 3)

| Princípio | Resultado | Evidência |
|---|---|---|
| II. Seams | ✅ | Consome `api.py`, `service.py` e `adapters/` de 007 e 004 (exceção do princípio XIII); nenhum toque em outro módulo |
| IV. Assistant é a fronteira | ✅ | O catálogo de cada execução continua sendo montado pela 004 com o grant; a 011 só injeta |
| VI. Conteúdo externo | ✅ | Logger do SDK em `INFO` (R30); credenciais de MCP só no `EnvSecretResolver`, nunca em `Settings` (R27) |
| VII. Falha fechada | ✅ | Arquivo malformado para o boot; entrada com problema degrada; MCP remoto fora do ar não derruba nada e aparece na saúde |
| XI. Streaming | ✅ | Sem mudança no caminho da resposta |
| XII. Simplicidade | ✅ | Cache de descoberta só em memória; nenhuma dependência nova; trocas de porta reaproveitam o ponto em que o perfil é aplicado |
| XIII. Portas e adapters | ✅ | Seis portas novas — todas as da 007 e da 004 com adapter declarado nos três perfis, inclusive `DnsResolver` (FR-004); só esta spec instancia os adapters da 007 e da 004 |

**Module boundary gate (Fase 3)**:

- [x] Source changes stay inside this module's paths — `ai_core/bootstrap/**` e `tests/bootstrap/**`; nenhum toque em
  código de outro módulo. Em `ai-core/pyproject.toml`, o contrato da 007 "o SDK de MCP só existe nos adapters" deixa de
  listar `ai_core.bootstrap` (que alcança o SDK pelos transportes da 007, a exceção do princípio XIII) e ganha
  `ai_core.capabilities`; um contrato novo proíbe a composition root de importar o SDK **diretamente**
- [x] Every consumed seam is listed — 007 (`McpService`, `McpConfig`, adapters), 004 (`CapabilityService`,
  `GatewayLimits`, adapters, `audit_command`), 005 (`ExecutionService(capabilities=…)`), 003 (`McpDirectory` pela 007),
  009
- [x] No seam changes — `platform(overrides=…)` é parâmetro do ponto de entrada desta spec, não seam
- [x] Import boundaries — nenhum módulo importa `ai_core.bootstrap` (contrato existente)

**Ports & adapters gate (Fase 3)**: as portas novas são as declaradas por 007 (`McpServerStore`, `DnsResolver`,
`McpTransport`, `SecretResolver`, `DiscoveryCache`) e 004 (`AuditLog`), cada uma com adapter em memória e, onde há banco, Postgres.
**Resultado**: PASS.

## Project Structure (Fase 3)

```text
ai-core/packages/core/src/ai_core/bootstrap/
├── settings.py     # + mcp_file, mcp_discovery_ttl, tool_timeout_ms, tool_max_response_bytes
├── profiles.py     # + mcp_store, mcp_dns, mcp_transports, mcp_secrets, mcp_cache, audit; controller do test
├── wiring.py       # + etapa mcp_registry; mcp_service/capabilities_service; trocas de porta; migrações; Platform.mcp
├── health.py       # + itens mcp:<alias>
└── cli.py          # + audit

ai-core/packages/core/tests/bootstrap/
├── unit/           # + configuração da Fase 3, perfis e trocas, saúde de MCP
├── contract/       # + etapas com mcp_registry, logging do SDK
└── integration/    # + test_platform_agentic_mcp.py; persistent com mcp/capabilities (Postgres)
```

## Seam Notes for Consumers (Fase 3)

| Consumidor | O que precisa saber |
|---|---|
| Operador | `AI_CORE_MCP_FILE` aponta o arquivo de servidores (formato da 007); credenciais por `AI_CORE_MCP_SECRET_<REF>`; limites por `AI_CORE_TOOL_*`; `ai-core audit` lista as escritas |
| 008 (passada de encaixe) | O `McpService` da plataforma está em `Platform.mcp` (e em `parts["mcp"]`) para as rotas de MCP |
| Suítes de packs externos | `platform(profile="test", overrides={...})` programa controller (`providers`) e servidores MCP (`mcp_transports`); sem trocas, o controller simulado responde direto |
| Monitoramento | Itens `mcp:<alias>` não críticos: servidor MCP fora do ar deixa a saúde `degraded`, nunca `down` |

## Complexity Tracking (Fase 3)

| Complexidade | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| `McpService` por sessão de armazenamento no boot e na CLI (R25) | o pool do `persistent` pertence ao laço em que abre (R13) | um serviço só quebraria fora do laço do servidor |
| Trocas de porta em `platform()` (R31) | a suíte ponta a ponta precisa programar controller e servidores MCP sem rede | fakes fixos no perfil `test` limitariam o que uma suíte prova (clarificação 2) |

# Fase 9 (2026-10-14): identidade, administração, sobreposições e destinos do trace (US6)

Insumos: ADR-030 a ADR-034; os planos da Fase 9 da 012, 003, 009 e 008 (o que cada um deixou para a composição).
Decisões em [research.md](research.md) R36–R44. **Sem divergência do `design.md`** (seção da Fase 9 já acrescentada).

## Summary (Fase 9)

A passada de encaixe: variáveis novas validadas cedo; etapa `identity` entre `adapters` e `packs`; o verificador da 003
lendo as chaves da 012 em processo, com audiência por superfície; o `AssistantsService` com as sobreposições; o
`TraceService` com os destinos de uso e Langfuse e a origem do processo; o `create_app` com a superfície de
administração e o router da 012; tarefas periódicas, CLI e saúde novas. O `test` continua compatível com as suítes de
pack e liga a identidade sob pedido.

## Technical Context (Fase 9)

**Dependências**: nenhuma além das das passadas anteriores. **Storage**: migrações de `identity` e `observability` na
etapa `adapters`. **Testing**: configuração (validações), perfis (portas novas), boot (ordem e falhas), CLI, saúde e a
prova ponta a ponta sem rede (R43).

## Constitution Check (Fase 9)

| Princípio | Resultado | Evidência |
|---|---|---|
| II. Seams | ✅ | A 011 só instancia e injeta; a função `jwks()` da 012 chega à 003 como chamável |
| VII. Falha fechada | ✅ | Configuração inconsistente para o boot nomeando a variável; destinos degradam sem derrubar |
| XIII. Portas e adapters | ✅ | Só a composition root importa `service.py`/`adapters/` dos módulos |

**Module boundary gate (Fase 9)**: `ai_core/bootstrap/**` e `tests/bootstrap/**`; `specs/README.md`; `CLAUDE.md`.
**Resultado**: PASS.

## Project Structure (Fase 9)

```text
ai-core/packages/core/src/ai_core/bootstrap/
├── settings.py      # variáveis da Fase 9 e validações (R36)
├── profiles.py      # portas novas nos três perfis; TEST_ADMIN_USERNAME/PASSWORD (R38, R39)
├── wiring.py        # etapa identity; AccessService/AssistantsService/TraceService/create_app novos (R37, R40)
├── health.py        # trace:usage, trace:langfuse, identity; modelos efetivos (R41)
└── cli.py           # users …, identity keys rotate (R42)
```
