# Implementation Plan: Registry e cliente MCP

**Branch**: `007-core-mcp-integration` | **Date**: 2026-10-01 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/007-core-mcp-integration/spec.md`

**Architecture inputs** *(PROJECT OVERRIDE — agentic-app)*: before filling Technical Context, READ
`/specs/007-core-mcp-integration/design.md` (including its "Portas e adapters" section) and every ADR listed
in the spec's Module Boundary, plus ADR-012 (architectural style). Decisions recorded there are
**pre-approved**: carry them into this plan and into `research.md` as
"Decision / Rationale (ADR-xxx) / Alternatives", do not re-research them. Any deviation requires a
new ADR in `docs/adr/` and must be listed in Complexity Tracking.

Insumos lidos: [design.md](design.md), ADR-003, ADR-012, ADR-013, ADR-015; as cinco clarificações de 2026-10-01; os
seams ao redor — `MCPClient`, `ToolSpec` e `ToolResult` (001), `Principal`, `ExecutionGrant` e a porta `McpDirectory`
(003), o que a 004 espera do cliente (design dela) e a sessão de armazenamento da 011 (R13 dela). **Refinamentos do
`design.md`, sem divergência de decisão**: duas portas a mais — `McpConfigSource` (o arquivo do operador, que nasce das
clarificações 1 e 2) e `Clock` (cache e datas, ADR-013) —, e o seam `discover`, que acrescenta ao contrato 001 a lista
de servidores com falha (R2). **Nenhum ADR novo.**

## Summary

Entregar o registro de servidores MCP por alias e o cliente restrito ao grant. O registry guarda globais e de usuário,
com política por servidor (prazo, tamanho, allowlist de tools obrigatória, tools de escrita) e só a **referência** da
credencial; globais `stdio` vêm apenas do arquivo do operador, e os `http`/`sse` também da API, ao vivo. O cliente
entregue a uma execução conhece só os aliases do grant, descobre tools com cache por TTL filtrando pela allowlist,
executa com prazo e teto de bytes, e conecta só a destinos que passam pela política de rede — conferida no IP resolvido,
a cada conexão, com a conexão fixada no IP validado, e pela allowlist de hosts de destino do operador quando ele a define.
MCP de usuário é sempre `https`, sem autenticação nesta fase, e nunca alcança hosts internos. Escopo da Fase 3: **US1–US6**. O encaixe na 003, na 008 e na 011 é das passadas delas
(R1).

## Technical Context

**Language/Version**: Python 3.14 (módulo da distribuição `ai-core`, `requires-python = ">=3.14"`)

**Primary Dependencies**: `api.py` da 003 (`Principal`, `ExecutionGrant`, `NotFound`, `RequestRejected`, `Conflict`)
e o contrato 001 (`MCPClient`, `ToolSpec`, `ToolResult`, `JSONValue`); `pyyaml` e `psycopg`/`psycopg-pool` (já
presentes). **Nova**, confinada a `adapters/` por import-linter: `mcp>=2.2,<3` — o SDK oficial, que traz `httpx2` e
`httpcore2` (R6)

**Storage**: Postgres no schema `mcp` — servidores globais criados pela API e todos os de usuário (ADR-015); arquivo
`mcp.yaml` do operador, somente leitura; cache de descoberta em memória

**Testing**: pytest + pytest-asyncio + hypothesis; `unit/` (domínio puro e vetores de SSRF), `contract/` (três seams e
cada porta contra memória e adapter real — Postgres, ambiente, DNS do sistema, servidor MCP do SDK em `127.0.0.1` e
servidor `stdio` em script), `integration/` (SSRF de ponta a ponta e varredura de segredos) (R16)

**Target Platform**: processo do core na imagem Linux ARM64 (2 OCPU, 12 GB)

**Project Type**: módulo de biblioteca dentro do monolito modular (`ai_core/mcp/`)

**Performance Goals**: descoberta servida do cache dentro do TTL sem I/O; servidor fora do ar custa no máximo o prazo
dele uma vez a cada 30 s (cache negativo, R8); validação de alias e de rede sem I/O além da resolução de nome

**Constraints**: nenhum segredo em armazenamento, log, trace, exceção ou valor devolvido (SC-001); 100% dos vetores de
SSRF bloqueados (SC-002); MCP novo disponível sem restart (SC-003); nenhum MCP de usuário visível a outro (SC-004);
`stdio` nunca pela API; `api.py`/`domain/`/`ports.py`/`service.py` sem `mcp`, `httpx2`, `httpcore2`, `anyio`, `yaml`
nem driver de banco

**Scale/Scope**: 1 módulo com 3 seams, 7 portas secundárias e 5 regras de domínio; dezenas de servidores globais,
centenas de usuário, até dezenas de tools por servidor

Nenhum `NEEDS CLARIFICATION`: as cinco perguntas abertas foram resolvidas em 2026-10-01, e os pontos adiados pelo
`/speckit-clarify` — semântica de `http`/`sse` (R6), formato do arquivo do operador (R10), prefixo das referências de
credencial (R7), saúde por servidor e TTL do cache (R8, R14) — estão em [research.md](research.md).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Resultado | Evidência |
|---|---|---|
| I. Núcleo agnóstico | ✅ | Aliases, tools e endpoints são dados; exemplos de servidor só em configuração ilustrativa |
| II. Seams | ✅ | Consome só o `api.py` da 003 e o contrato 001; expõe três seams com suíte de conformidade; `McpCatalog` tem a forma exata da porta que a 003 declarou |
| III. O core orquestra | ✅ | Descobre e executa tools quando a 004 pede; não decide o que entra no catálogo além da allowlist do servidor |
| IV. Assistant é a fronteira | ✅ | O cliente só conhece os aliases do grant; alias fora dele é "servidor desconhecido" (US3); allowlist de tools obrigatória — capacidade não declarada não existe (R11); MCP alheio responde como inexistente (SC-004) |
| V. Determinismo | ✅ | Política de rede, visibilidade, validação e corte de resultado são funções puras; nenhum LLM |
| VI. Conteúdo externo | ✅ | É o princípio implementado: credencial por referência, resolvida no servidor e nunca devolvida (R7); SSRF no IP resolvido com conexão fixada e allowlist de hosts de destino opcional do operador — a "allowlist de hosts" do princípio (R5; achado C1 do `/speckit-analyze`); prazo e teto de bytes; resultado sempre `untrusted`, com marca de corte (R9); usuário nunca registra comando (`stdio` só no arquivo, R3) |
| VII. Falha fechada | ✅ | Erro de arquivo para o boot; servidor inválido ou sombreado fica indisponível com motivo; servidor desabilitado some do catálogo e o Assistant fica indisponível na 003; servidor fora do ar vira `unavailable`, nunca silêncio |
| VIII. Modelos por papel | N/A | Sem modelo |
| IX. Proveniência | N/A | Sem retrieval |
| X. Medir antes de calibrar | ✅ | Prazos e tetos são controles de segurança, não calibração de qualidade; TTL é configuração do operador |
| XI. API independente, streaming | ✅ | O módulo não conhece HTTP de entrada; as rotas são da 008 |
| XII. Simplicidade | ✅ | Sessão por operação, sem pool de sessões; sem deduplicação de descoberta; um arquivo do operador para `stdio` e hosts internos |
| XIII. Portas e adapters | ✅ | Ver gate abaixo |

**Module boundary gate** *(PROJECT OVERRIDE — principle II, mandatory)*:

- [x] Source changes stay inside this module's paths — `ai-core/packages/core/src/ai_core/mcp/**` e
  `ai-core/packages/core/tests/mcp/**`; fora dele, apenas `ai-core/packages/core/pyproject.toml` (dependência `mcp`),
  `ai-core/pyproject.toml` (import-linter, pytest) e `specs/README.md` (os seams). **Nada** em `assistants/`, `http/`
  nem `bootstrap/`: o encaixe é das passadas de 003, 008 e 011 (R1)
- [x] Every consumed seam is listed with its owner spec; no internals of other modules are used — `Principal`,
  `ExecutionGrant` e os erros base (003, `ai_core.assistants.api`); `MCPClient`, `ToolSpec`, `ToolResult` (001)
- [x] Every seam this module exposes has a conformance test planned — `test_registry.py`, `test_catalog.py`,
  `test_restricted_client.py` e `test_isolation.py` ([contracts/mcp-api.md](contracts/mcp-api.md))
- [x] No seam changes — os três seams nascem agora; `McpCatalog` tem a forma que a 003 declarou, e `RestrictedMcpClient`
  cumpre o `MCPClient` da 001 e só acrescenta `discover`
- [x] Import boundaries (import-linter) cover the new code — contratos novos em "Fronteiras verificadas"

**Ports & adapters gate** *(PROJECT OVERRIDE — principle XIII, ADR-012, mandatory)*:

- [x] The module follows `api.py` / `domain/` / `ports.py` / `service.py` / `adapters/` — completo
- [x] `api.py`, `domain/`, `ports.py` and `service.py` import no infrastructure framework — `mcp`, `mcp_types`,
  `httpx2`, `httpcore2`, `anyio`, `yaml`, `psycopg` e `psycopg_pool` proibidos fora de `adapters/`; o domínio usa
  `ipaddress`, `re` e `urllib.parse` da biblioteca padrão
- [x] Other modules are imported only through their `api.py` — contrato de import-linter; `api.py` da 007 não importa o
  resto do módulo
- [x] All I/O, time, randomness, secrets and trace go through a secondary port — banco (`McpServerStore`), arquivo
  (`McpConfigSource`), rede e processo (`McpTransport`), DNS (`DnsResolver`), segredos (`SecretResolver`), cache
  (`DiscoveryCache`), tempo (`Clock`). Trace: nenhum evento nesta fase (R15)
- [x] Every secondary port exists for I/O, non-determinism or a planned swap — tabela em
  [contracts/ports.md](contracts/ports.md); nenhuma porta para regra pura (a política de rede é função, não porta)
- [x] Every secondary port has an in-memory adapter and a conformance suite that also runs against the real adapter —
  [contracts/ports.md](contracts/ports.md)
- [x] Services and adapters of other modules are instantiated only in the composition root — este módulo não instancia
  nada de outro

**Resultado do gate (antes da Phase 0)**: PASS.

## Project Structure

### Documentation (this feature)

```text
specs/007-core-mcp-integration/
├── spec.md
├── design.md
├── plan.md              # este arquivo
├── research.md          # R1–R16
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── mcp-api.md          # os três seams, erros e suítes de conformidade
│   ├── mcp-yaml.md         # arquivo do operador: servidores e hosts internos
│   ├── network-policy.md   # a decisão de rede e a tabela de vetores de SSRF
│   └── ports.md            # portas secundárias, adapters e conformidade
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
ai-core/
├── pyproject.toml                           # import-linter (contratos novos), pytest pythonpath
└── packages/core/
    ├── pyproject.toml                       # mcp>=2.2,<3
    ├── src/ai_core/mcp/
    │   ├── __init__.py
    │   ├── api.py                           # seams, value objects, vocabulário, erros
    │   ├── domain/
    │   │   ├── __init__.py
    │   │   ├── servers.py                   # validação de rascunho e de entrada do arquivo, gramática do alias
    │   │   ├── visibility.py                # o que cada dono e cada grant enxerga; sombreamento pelo arquivo
    │   │   ├── network.py                   # política de rede: destino permitido?
    │   │   ├── tools.py                     # allowlist, marca de escrita, ToolSpec a partir da tool remota
    │   │   └── results.py                   # ToolResult a partir do resultado remoto; corte com marca
    │   ├── ports.py                         # as sete portas de contracts/ports.md
    │   ├── service.py                       # McpService: McpRegistry, McpCatalog, McpClients
    │   └── adapters/
    │       ├── __init__.py
    │       ├── memory.py                    # adapters em memória e de teste de todas as portas
    │       ├── registry_postgres.py         # McpServerStore
    │       ├── postgres_schema.py           # migrate(pool) do schema mcp (ADR-015)
    │       ├── sql/001_servers.sql
    │       ├── config_yaml.py               # McpConfigSource
    │       ├── transport_http.py            # McpTransport http/sse: SDK + backend de rede guardado
    │       ├── transport_stdio.py           # McpTransport stdio: SDK, comando do arquivo
    │       ├── dns_system.py                # DnsResolver
    │       └── secrets_env.py               # SecretResolver: AI_CORE_MCP_SECRET_<REF>
    └── tests/mcp/
        ├── conftest.py
        ├── mcp_testkit.py                   # rascunhos, grants, Principals, servidores programados, servidor MCP do
        │                                    # SDK em 127.0.0.1, servidor stdio em script, fixture de Postgres
        ├── unit/                            # domain/: um arquivo por regra, vetores de SSRF
        ├── contract/                        # seams e portas (memória × real)
        └── integration/                     # SSRF ponta a ponta, varredura de segredos
```

**Structure Decision**: layout hexagonal completo do ADR-012, com os nomes do `design.md`. `registry_memory.py` e
`cache_memory.py` do `design.md` viram parte de `memory.py`, junto com os demais adapters em memória (como na 003);
`secrets_env.py` e `config_yaml.py` são os adapters das portas `SecretResolver` e `McpConfigSource`.

## Fronteiras verificadas (import-linter)

Contratos novos em `ai-core/pyproject.toml`, no padrão dos módulos já implementados:

1. `api.py` da 007 não importa o resto do módulo;
2. `domain/` da 007 não importa portas, service nem adapters;
3. `service.py` da 007 não importa adapters;
4. o núcleo da 007 (`api`, `domain`, `ports`, `service`) não importa `mcp`, `mcp_types`, `httpx2`, `httpcore2`, `anyio`,
   `yaml`, `psycopg`, `psycopg_pool`;
5. a 007 só enxerga outros módulos pelo `api.py` (só `ai_core.assistants.api`; `http` e `bootstrap` inteiros
   proibidos);
6. nenhum outro módulo importa internals da 007 (`mcp.domain`, `.ports`, `.service`, `.adapters`) — só a composition
   root;
7. o SDK de MCP (`mcp`, `mcp_types`) não aparece fora de `ai_core.mcp.adapters` — `httpx2`/`httpcore2` também são a
   pilha HTTP do SDK do provider (006), então só o contrato 4 os proíbe no núcleo da 007.

E a 007 entra na lista de origem dos contratos já existentes: "nenhum módulo do core importa a API" e "nenhum módulo
importa a composition root".

## Seam Notes for Consumers

| Consumidor | O que precisa saber |
|---|---|
| 004 (Fase 3) | Pede `client_for(grant)` uma vez por execução. `discover(aliases)` devolve `Discovery(tools, unavailable)`: tools com o nome **local**, `kind="mcp"` e `mutates` pela política; servidores com falha e o motivo, para o trace e os metadados da resposta. `execute` devolve `ToolResult(untrusted=True)` e nunca levanta por falha de servidor; levanta `UnknownServer` só para alias fora do grant. O cache de descoberta é daqui (004 FR-004) |
| 003 (passada da Fase 3) | Nada muda no código dela: a composition root troca `EmptyMcpDirectory` por este serviço, que tem a forma de `McpDirectory`. Servidor desabilitado some do catálogo e o Assistant fica indisponível pelo caminho que já existe |
| 008 (passada da Fase 3) | CRUD de usuário em `/v1` com `mine`/`get_mine`/`create_mine`/`update_mine`/`delete_mine` e `available`; CRUD de globais em `/private/v1` com `globals`/`*_global`, depois de conferir o grupo de administração (`AdminGate`); saúde por servidor com `check`. Erros: `McpNotFound`→404 (mensagem fixa), `McpRejected`→400 (nomeando `field`), `McpConflict`→409 — os três herdam dos erros da 003 que a tabela dela já traduz |
| 011 (passada da Fase 3) | Constrói `McpService` com: armazenamento (memória ou Postgres, `migrate` do schema `mcp` na etapa `adapters`), arquivo do operador (`AI_CORE_MCP_FILE`), transportes (`http`/`sse` com o `DnsResolver` do sistema, os hosts internos e a allowlist de hosts do arquivo; `stdio`), `SecretResolver` de ambiente, cache com TTL (`AI_CORE_MCP_DISCOVERY_TTL`, padrão 300 s) e o relógio único. Etapa `mcp_registry` (erro de arquivo é crítico) antes de `assistants`, e o serviço no lugar do `McpDirectory` vazio. Perfil `test`: transporte em memória com servidores programados — nada de rede |
| Operador | `mcp.yaml` para `stdio` e hosts internos; segredos em `AI_CORE_MCP_SECRET_<REF>`; a saúde de cada servidor lista as tools que ele anuncia, para escrever a allowlist |

## Constitution Check — pós-design (Phase 1)

Reavaliado com [data-model.md](data-model.md), [contracts/](contracts/) e [quickstart.md](quickstart.md): **PASS**.

- IV: [contracts/mcp-api.md](contracts/mcp-api.md) amarra cada regra de fronteira a um teste — alias fora do grant,
  visibilidade revalidada na execução, allowlist obrigatória e isolamento entre usuários.
- VI: [contracts/network-policy.md](contracts/network-policy.md) fixa a decisão de rede como função pura com tabela de
  vetores, e onde ela é aplicada (cada conexão, IP fixado); [contracts/ports.md](contracts/ports.md) fixa o prefixo das
  referências de credencial e a varredura de segredos.
- VII: [contracts/mcp-yaml.md](contracts/mcp-yaml.md) separa erro de arquivo (para o boot) de erro de servidor (só ele
  indisponível) e define a precedência do arquivo sobre o armazenamento.
- XIII: sete portas, cada uma com motivo, adapter em memória e suíte contra o real; o SDK fica em `adapters/`.

## Complexity Tracking

> Nenhuma violação. Complexidade adicional justificada (princípio XII):

| Complexidade | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Dependência do SDK de MCP (R6) | o protocolo tem negociação de versão, sessão e dois formatos de resposta; o SDK é a implementação de referência. A pilha HTTP dele (`httpx2`) já vinha com o SDK do provider (006); o que entra de novo é `mcp`, `mcp-types`, `sse-starlette` e `opentelemetry-api` | implementar o protocolo à mão seria código de protocolo para manter; o SDK fica confinado a `adapters/` |
| Backend de rede próprio que fixa a conexão no IP validado (R5) | SC-002 inclui DNS que resolve para privada e redirecionamento; conferir e deixar a biblioteca resolver de novo abre a janela de rebinding | checar só no registro ou só o nome não pega DNS que muda nem resposta mista |
| Duas origens de MCP global — arquivo e armazenamento — com precedência do arquivo (R3) | clarificação 1: `stdio` só por configuração do operador, `http`/`sse` ao vivo pela API | uma origem só obrigaria a escolher entre execução de comando pela API e restart para todo MCP global |
| Cache negativo de 30 s (R8) | sem ele, cada execução espera o prazo inteiro de um servidor fora do ar | só o cache positivo deixaria a latência de toda execução refém do pior servidor |
| Allowlist de tools obrigatória (R11) | princípio IV: capacidade não declarada não existe | allowlist opcional exporia tools novas do servidor sem decisão de ninguém |


## Incremento: delegação MCP por execução (2026-10-29)

Regido por [ADR-055](../../docs/adr/ADR-055-autenticacao-mcp-delegada.md). Protocolo 1: um MCP delegado por grant, identidade confidencial por execução, sem cache compartilhado e sem alteração da ACL. Contrato: [delegação](../007-core-mcp-integration/contracts/delegation.md). Casos D01 isolamento concorrente; D02 falha fechada; D03 metadados e superfície privada; D04 segredo ausente de persistência/trace; D05 regressão estática.
