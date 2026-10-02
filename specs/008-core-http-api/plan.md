# Implementation Plan: API HTTP — chat completions compatível com OpenAI

**Branch**: `008-core-http-api` | **Date**: 2026-09-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/008-core-http-api/spec.md`

**Architecture inputs** *(PROJECT OVERRIDE — agentic-app)*: before filling Technical Context, READ
`/specs/008-core-http-api/design.md` (including its "Portas e adapters" section) and every ADR listed
in the spec's Module Boundary, plus ADR-012 (architectural style). Decisions recorded there are
**pre-approved**: carry them into this plan and into `research.md` as
"Decision / Rationale (ADR-xxx) / Alternatives", do not re-research them. Any deviation requires a
new ADR in `docs/adr/` and must be listed in Complexity Tracking.

Insumos lidos: [design.md](design.md), ADR-002, ADR-012, ADR-013; Execution Engine da 005, Model Router da 006, Pack
Hooks da 002 e Trace Sink da 009, todos implementados. Consumidores conferidos: clientes externos (Open WebUI, SDKs) e
011 (monta a app e injeta os seams). **Sem divergência do `design.md`**: a única diferença é interna e preserva o
arquivo que ele nomeia — a construção do chunk é pura, em `domain/openai_chunks.py`, e `adapters/sse.py` fica com a
serialização e a conexão ([research.md](research.md) R4). Nenhum ADR novo.

## Summary

Entregar a rota de **chat completions compatível com OpenAI**, com e sem streaming, nas superfícies `/v1` e
`/private/v1`: a requisição vira um `ExecutionRequest` do motor (005), os eventos voltam traduzidos em chunks SSE, e o
identificador de requisição do trace acompanha a resposta. O Principal e o resolvedor de grant entram por portas que
este módulo publica, para que a autenticação e a resolução de Assistant da 003 cheguem na Fase 2 como troca de adapter.
Escopo da Fase 1: **US1**, mais FR-010 e as rejeições de campo de ampliação e de data de referência
([research.md](research.md) R8, R9). Listagem de modelos, conversas, CRUD, saúde e fila ficam para as fases deles.

## Technical Context

**Language/Version**: Python 3.14 (módulo da distribuição `ai-core`, `requires-python = ">=3.14"`)

**Primary Dependencies**: `ai_core.graph.api` (005), `ai_core_contracts` (mensagens); **nova** — `fastapi>=0.141,<1`,
confinada a `ai_core/http/adapters/` por contrato de import (R4, R11); `httpx` como dependência de desenvolvimento, que
é o que o cliente de teste do framework usa

**Storage**: N/A nesta fase — conversas são Fase 2 (R9)

**Testing**: pytest + pytest-asyncio; `domain/` puro (mapeamento da requisição e construção de chunk); suíte ponta a
ponta pelo cliente de teste do framework, com motor real, Pack Runtime real, `ai-generic` e provider simulado (R10)

**Target Platform**: processo do core na imagem Linux ARM64

**Project Type**: adapter primário da plataforma, dentro do monolito modular (`ai-core`)

**Performance Goals**: SC-003 — primeiro sinal em até 2 s. A API não acumula: cada evento do motor vira um chunk
escrito na conexão no mesmo instante, e o progresso de `generate` (005) chega antes da primeira chamada de modelo

**Constraints**: nenhum tipo do framework HTTP fora de `adapters/` (princípio XIII); a API não aceita data de
referência em nenhuma superfície (FR-012, ADR-013); erro de autorização é 404, nunca 403 (FR-009); a API não conhece
flows, packs, providers nem políticas de tool; nenhuma lógica de agente vive aqui (princípio XI)

**Scale/Scope**: 1 módulo — `ports.py` (4 Protocols), `domain/` com 2 arquivos, `service.py`, e `adapters/` com a
fábrica da app, as duas superfícies, a rota de chat completions, a serialização SSE e os adapters de desenvolvimento;
1 rota das ~15 do `design.md`

Nenhum `NEEDS CLARIFICATION`: as quatro perguntas abertas foram resolvidas em 2026-09-21 e estão em
[research.md](research.md) R1, R2, R5 e R6.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Resultado | Evidência |
|---|---|---|
| I. Núcleo agnóstico | ✅ | A API transporta mensagens e eventos; nenhum termo de domínio, nenhum prompt |
| II. Seams | ✅ | Consome o `api.py` da 005 e declara como `Protocol` o que exige da 003. Não expõe seam Python: o seam é a própria API HTTP, com suíte ponta a ponta |
| III. O core orquestra | ✅ | A API não decide topologia nem chama packs: entrega a requisição ao motor e traduz o que volta |
| IV. Assistant é a fronteira | ✅ | O grant vem resolvido de fora (R2); campos de ampliação (`tools`, `functions`) são rejeitados antes de qualquer execução (R8); Assistant não autorizado responde 404 |
| V. Determinismo | ✅ | Mapeamento da requisição e construção de chunk são funções puras; nenhuma decisão por modelo |
| VI. Conteúdo externo | ✅ | O corpo da requisição é dado: só campos conhecidos entram no `ExecutionRequest`, e o resto é rejeitado em vez de repassado |
| VII. Falha fechada | ✅ | Campo proibido, Assistant inexistente e requisição inválida falham com 4xx **antes** de qualquer chamada de modelo; falha depois do stream aberto encerra o stream com motivo (R6) |
| VIII. Modelos por papel | ✅ | O modelo vem do id `<assistant>/<modelo>` e é conferido pela allowlist do grant, na 006 — a API não escolhe modelo |
| IX. Proveniência | ✅ | Citações e marcações do evento final chegam ao cliente no chunk final, sem edição |
| X. Medir antes de calibrar | ✅ | Nenhum número calibrável nesta fase: limite de concorrência e fila são Fase 7, com medição no hardware alvo |
| XI. Streaming e independência da interface | ✅ | É o ponto da fase; nenhuma lógica de agente na API, e nenhuma dependência de interface gráfica |
| XII. Simplicidade | ✅ | Sem conversas, sem fila, sem saúde agregada, sem CRUD — cada um adiado para a fase que o usa (R9) |
| XIII. Portas e adapters | ✅ | Ver gate abaixo |

**Module boundary gate** *(PROJECT OVERRIDE — principle II, mandatory)*:

- [x] Source changes stay inside this module's paths — `ai-core/packages/core/src/ai_core/http/**` e
  `ai-core/packages/core/tests/http/**`; fora dele, apenas `ai-core/packages/core/pyproject.toml` (dependência
  `fastapi`) e `ai-core/pyproject.toml` (import-linter, pytest, `httpx` no grupo de desenvolvimento)
- [x] Every consumed seam is listed with its owner spec; no internals of other modules are used —
  `ExecutionEngine`, `ExecutionRequest`, `ExecutionGrant` e os eventos de `ai_core.graph.api` (005); `Message` de
  `ai_core_contracts` (001). Em `src/`, nada de 002, 006 ou 009: o motor é a única porta de entrada. A suíte de
  integração monta o caminho real (Pack Runtime, Model Router, trace) de propósito — é o que a SC-002 pede
- [x] Every seam this module exposes has a conformance test planned — o seam é a API HTTP:
  `tests/http/contract/test_chat_completions.py` (formato OpenAI, streaming, erros) e
  `tests/http/integration/test_http_end_to_end.py` (SC-002, conversa completa via HTTP)
- [x] No seam changes — a API nasce aqui. As formas exigidas da 003 entram como `Protocol` deste módulo, o que **não**
  move a posse dos seams Authenticator/GrantResolver, que continuam da 003 (R1, R2)
- [x] Import boundaries (import-linter) cover the new code — contratos novos do R11

**Ports & adapters gate** *(PROJECT OVERRIDE — principle XIII, ADR-012, mandatory)*:

- [x] The module follows `api.py` / `domain/` / `ports.py` / `service.py` / `adapters/` — sem `api.py`, por decisão do
  `design.md`: este módulo não expõe seam Python, e sim a própria superfície HTTP
- [x] `api.py`, `domain/`, `ports.py` and `service.py` import no infrastructure framework — nenhum deles importa
  `fastapi` ou `starlette`; o contrato de import-linter do R11 barra
- [x] Other modules are imported only through their `api.py` — só `ai_core.graph.api` e `ai_core_contracts`
- [x] All I/O, time, randomness, secrets and trace go through a secondary port; `domain/` does no I/O —
  aleatoriedade pela porta `RequestIds` (R7); autenticação e resolução de grant por porta; `domain/` é puro
- [x] Every secondary port exists for I/O, non-determinism or a planned swap — `Authenticator` e `GrantResolver` por
  troca prevista (anônimo → 003 na Fase 2); `RequestIds` e `Clock` por não-determinismo (o campo `created` do formato
  OpenAI faz esta fase ler o relógio). `ConversationStore` e `HealthProvider` são da Fase 2 (R9)
- [x] Every secondary port has an in-memory adapter and a conformance suite that also runs against the real adapter —
  os adapters desta fase **são** os de memória; a conformidade roda contra eles e volta a rodar contra os da 003
- [x] Services and adapters of other modules are instantiated only in the composition root — a 008 não instancia nada
  de outro módulo: recebe o motor pronto. Quem monta a app é a 011 (e os testes)

**Resultado do gate (antes da Phase 0)**: PASS.

## Project Structure

### Documentation (this feature)

```text
specs/008-core-http-api/
├── spec.md
├── design.md
├── plan.md              # este arquivo
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── chat-completions.md   # a rota: corpo aceito, rejeições, resposta com e sem streaming
│   ├── sse-format.md         # ExecutionEvent → chunk OpenAI, e o encerramento
│   └── ports.md              # Authenticator, Principal, GrantResolver, RequestIds
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
ai-core/
├── pyproject.toml                       # contratos novos de import-linter (R11); httpx no grupo dev
└── packages/core/
    ├── pyproject.toml                   # dependência fastapi>=0.141,<1 (R4)
    ├── src/ai_core/http/
    │   ├── __init__.py                  # docstring: o seam deste módulo é a própria API HTTP
    │   ├── ports.py                     # Principal, Authenticator, GrantResolver, RequestIds + erros
    │   ├── domain/
    │   │   ├── __init__.py
    │   │   ├── chat_request.py          # corpo OpenAI → (modelo, mensagens, streaming); rejeições (R8)
    │   │   └── openai_chunks.py         # ExecutionEvent → chunk/resposta OpenAI — puro (R4)
    │   ├── service.py                   # ChatService: resolve grant, chama o motor, devolve chunks
    │   └── adapters/
    │       ├── __init__.py
    │       ├── app.py                   # fábrica da app, chamada pela composition root (011)
    │       ├── chat.py                  # rota de chat completions, nas duas superfícies
    │       ├── sse.py                   # serialização `data: …` e a conexão
    │       └── development.py           # Authenticator anônimo e RequestIds — perfil de desenvolvimento
    └── tests/http/
        ├── conftest.py                  # app montada em processo, motor real, provider simulado
        ├── http_testkit.py              # fábricas compartilhadas
        ├── unit/                        # domain/ puro: mapeamento da requisição e construção de chunk
        ├── contract/                    # a rota: formato OpenAI, streaming, rejeições, 404
        └── integration/                 # SC-002: conversa ponta a ponta só via HTTP
```

**Structure Decision**: layout do `design.md` (`ai_core/http/`), sem `api.py` — o seam é a superfície HTTP. Dos
arquivos que o `design.md` lista, nascem `app.py`, `sse.py` e a rota de chat; `auth.py`, `public.py`, `private.py`,
`openai_compat.py` (listagem de modelos) e os adapters de conversa chegam com as fases deles. As duas superfícies são
o mesmo roteador montado em dois prefixos, com a dependência de autenticação parametrizada — é o que o `design.md`
descreve e evita duplicar rota.

## Seam Notes for Consumers

| Consumidor | O que precisa saber |
|---|---|
| 011 (Fase 1) | Montar a app com `create_app(engine=…, authenticator=…, grants=…, request_ids=…)` e servi-la. Na Fase 1, injetar `AnonymousAuthenticator` e um `GrantResolver` montado da configuração; o nome do adapter anônimo aparece no boot, para não ser confundido com produção |
| 003 (Fase 2) | Fornecer o verificador real e o resolvedor de grant: basta satisfazer `Authenticator` e `GrantResolver`; nenhuma rota muda. A regra 404-não-403 já está no caminho da requisição |
| Clientes externos | `POST /v1/chat/completions` e `POST /private/v1/chat/completions`, formato OpenAI. `stream: true` devolve `chat.completion.chunk` e `[DONE]`; o identificador de requisição vem em `X-Request-Id` e no `id` da resposta |
| 005 | Recebe `ExecutionRequest` com o identificador de requisição que a API gerou; a API nunca preenche a data de referência (FR-012) |

## Constitution Check — pós-design (Phase 1)

Reavaliado com [data-model.md](data-model.md), [contracts/](contracts/) e [quickstart.md](quickstart.md): **PASS**.

- IV: `contracts/chat-completions.md` lista os campos aceitos e fixa que qualquer outro campo de capacidade é rejeitado
  com 400 nomeando-o — a ampliação é barrada na borda, antes do motor.
- VII: a tabela de falhas do [data-model.md](data-model.md) separa o que acontece antes do stream (status HTTP) do que
  acontece depois (chunk final com motivo), sem nenhum caso de conexão pendurada.
- XI: `contracts/sse-format.md` fixa que cada evento do motor vira um chunk escrito na hora, sem acumular.
- XIII: três portas, todas por troca prevista ou não-determinismo; `fastapi` só em `adapters/`, verificado por
  import-linter.

## Complexity Tracking

> Nenhuma violação. Complexidade adicional justificada (princípio XII):

| Complexidade | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Porta `RequestIds` para gerar identificador (R7) | o identificador aparece na resposta e é a chave do trace; aleatoriedade é porta por princípio XIII | gerar no adapter deixaria a suíte casando por expressão regular e o elo resposta↔trace sem verificação exata |
| `Principal` e `GrantResolver` como `Protocol` daqui (R1, R2) | os donos são da 003, que é Fase 2 | montar o grant na API poria a fronteira de isolamento no adapter primário; antecipar a 003 criaria código sem spec |
| Construção de chunk separada da escrita (R4) | as regras de formato que quebram cliente são puras e merecem teste sem servidor | tudo no adapter exigiria subir servidor para verificar cada regra de formato |

---

# Fase 2 (2026-09-30): US2, US3, US4 (Assistants), US5 (packs, chaves, saúde), US7

Insumos: as cinco clarificações de 2026-09-30 da spec; a 003 implementada (`ai_core.assistants.api`); a US4 da 002;
ADR-015 (Postgres por módulo) e ADR-016. Decisões em [research.md](research.md) R12–R24. **Sem divergência do
`design.md`** além do que as clarificações fixaram: endpoints de MCP na Fase 3, id curto em `/v1/models`, 424 para
Assistant indisponível e a checagem de administrador por porta (R20).

## Summary (Fase 2)

A API passa a consumir os seams da 003 diretamente — autenticação real, grant, diretório e administração de chaves —
e ganha a listagem de modelos (id curto por Assistant), a requisição nativa estrita, o CRUD de Assistants de usuário,
a superfície privada (packs e chaves para administradores, saúde para qualquer chave) e as conversas no servidor, com
dono = subject, continuação pelo id, exclusão e expiração, em memória e em Postgres (schema `http`). Todo erro sai no
envelope da OpenAI. A troca de tipos na API e a troca de adapter na composition root acontecem juntas (R13).

## Technical Context (Fase 2)

**Primary Dependencies**: + `ai_core.assistants.api` (003) e `ai_core.packs.api` (002, já consumido pelo motor);
`psycopg`/`psycopg-pool` (já no workspace pela 003), confinados a `http/adapters/`

**Storage**: conversas — memória (perfis `memory` e `test`) e Postgres no schema `http` (ADR-015; o perfil
persistente é da 011)

**Testing**: rotas com os serviços reais da 003 sobre adapters em memória; `ConversationStore` em memória × Postgres
(`AI_CORE_TEST_POSTGRES_DSN`); reinício simulado por serviço novo sobre o mesmo armazenamento (R24)

**Constraints**: toda regra de acesso é da 003 (a API não repete nenhuma); 404 idêntico para inexistente e não
autorizado em Assistants, conversas e rotas administrativas; nenhuma mensagem de assistente do cliente entra numa
execução com id de conversa (SC-005); tempo e ids por porta

**Scale/Scope**: ~14 rotas novas; portas `ConversationStore`, `HealthProvider`, `AdminGate`; `domain/` com os corpos
nativo e de rascunho, o envelope de erro e as regras de conversa

## Constitution Check (Fase 2)

| Princípio | Resultado | Evidência |
|---|---|---|
| II. Seams | ✅ | Consome `api.py` de 003, 002 e 005; a seta 008 → 003 é a do grafo. A troca na composition root é exceção declarada abaixo (R13) |
| IV. Assistant é a fronteira | ✅ | Listagem = o que o Principal resolve; campos de ampliação recusados nas duas rotas de chat; 404 em Assistants, conversas e rotas de administração |
| VI. Conteúdo externo | ✅ | O histórico armazenado é a fonte de verdade; o que o cliente manda como resposta anterior é descartado (R21) |
| VII. Falha fechada | ✅ | Toda recusa (401, 404, 400, 409, 424, 429) acontece antes de qualquer chamada de modelo; conversa apagada não recebe troca |
| XI. Independência da interface | ✅ | Envelope e formatos da OpenAI; nenhuma lógica de agente na API |
| XII. Simplicidade | ✅ | Uma resposta só para compat e nativa (R17); sem MCP, fila nem progresso de tool nesta fase |
| XIII. Portas e adapters | ✅ | Ver gate abaixo |

**Module boundary gate (Fase 2)**:

- [x] Source changes stay inside this module's paths — `ai_core/http/**` e `tests/http/**`, **mais a exceção declarada
  do R13**: na composition root, `bootstrap/wiring.py` e `bootstrap/profiles.py` (construir os serviços da 003, a
  `ConversationStore` em memória e o provedor mínimo de saúde; nova etapa de validação de Assistants), a remoção de
  `bootstrap/grants.py`, e os testes e o `assistants.yaml` das suítes de `tests/bootstrap/` no formato da 003; na 003,
  um método público `AccessService.is_admin` (a regra já existe como `_require_admin`, R20); e `pyproject.toml`
  (import-linter)
- [x] Every consumed seam is listed with its owner spec — 003 (`Authenticator`, `GrantResolver`, `AssistantDirectory`,
  `ApiKeyAdmin`, `Principal`, erros, `WIDENING_FIELDS`), 002 (`PackRegistry`), 005 (`ExecutionEngine`)
- [x] Every seam this module exposes has a conformance test planned — a API HTTP: uma suíte por grupo de rotas
  (contracts/*.md)
- [x] No seam changes — nenhum seam muda; a API passa a consumir os seams da 003 como a Fase 1 previa (R1, R2)
- [x] Import boundaries cover the new code — `psycopg` só em `http/adapters/`; a API só vê `assistants.api`

**Ports & adapters gate (Fase 2)**:

- [x] `ConversationStore` (I/O, troca memória → Postgres), `HealthProvider` (montada fora do módulo), `AdminGate` (regra
  de outro módulo, R20) — cada uma com adapter em memória ou de teste e conformidade; Postgres contra o real na CI
- [x] `domain/` puro: corpos, envelope de erro, regras de conversa (qual mensagem entra, quando gravar)
- [x] nenhum framework HTTP nem driver fora de `adapters/`

**Resultado do gate (Fase 2)**: PASS.

## Project Structure (Fase 2)

```text
ai-core/packages/core/src/ai_core/http/
├── ports.py                     # − Principal/Authenticator/GrantResolver/AssistantNotFound; + ConversationStore,
│                                #   HealthProvider, AdminGate, Conversation, StoredMessage, ConversationPage, HealthReport
├── service.py                   # ChatService com conversas; ConversationService (listar, ler, apagar, expirar)
├── domain/
│   ├── chat_request.py          # compat: recusa WIDENING_FIELDS (R18); conversation_id
│   ├── native_request.py        # requisição nativa estrita (R17)
│   ├── assistant_body.py        # JSON ⇄ UserAssistantDraft (R19)
│   ├── conversations.py         # mensagens da execução a partir do histórico (R21)
│   ├── errors.py                # envelope da OpenAI e tabela de status (R14)
│   └── openai_chunks.py         # + conversation_id no primeiro chunk e na completion
└── adapters/
    ├── app.py                   # create_app com os seams da 003, 002 e as portas novas
    ├── auth.py                  # Bearer → authenticate (R15)
    ├── chat.py                  # compat e nativa
    ├── models.py                # /models
    ├── user_assistants.py       # CRUD /v1/assistants
    ├── private.py               # packs, admin/keys, health
    ├── conversations.py         # /conversations
    ├── errors.py                # exceções → envelope + status
    ├── development.py           # AnonymousAuthenticator com o Principal da 003
    ├── conversations_memory.py
    ├── conversations_postgres.py
    ├── postgres_schema.py       # migrate(pool, now=…) do schema http
    └── sql/001_conversations.sql
```

## Seam Notes for Consumers (Fase 2)

| Consumidor | O que precisa saber |
|---|---|
| 011 (passada da Fase 2) | A app agora recebe `Authenticator`, `GrantResolver`, `AssistantDirectory`, `ApiKeyAdmin` (003), `PackRegistry` (002), `AdminGate`, `ConversationStore`, `HealthProvider` e duas instâncias de `RequestIds`. Esta passada já monta a plataforma com os serviços da 003 em memória e o autenticador anônimo (R13); à 011 cabem o perfil persistente (pool, `migrate` de `assistants` e `http`), a autenticação real nos perfis, o agregador de saúde, o agendamento de `ConversationService.expire()` e o registro dos subcomandos |
| Clientes | Erros no envelope da OpenAI; `x_ai_core.conversation_id` e `X-Conversation-Id` em toda resposta de chat; `/v1/models` com id curto |
| 007 (Fase 3) | Os endpoints de MCP entram nesta spec na Fase 3, sobre o seam MCP Registry |

## Complexity Tracking (Fase 2)

| Complexidade | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Troca atômica na composition root dentro desta passada (R13) | a composition root importa as portas provisórias da 008; trocar só a API deixaria a plataforma sem montar | passar a 011 antes inverteria a dependência entre as passadas; tradutores de tipo no boot seriam código de transição sem dono |
| Conversa criada antes de executar (R21) | o id precisa sair no primeiro chunk (FR-014) | criar só depois do sucesso esconderia o id do cliente em streaming |
| Porta `AdminGate` (R20) | a regra de administrador é da 003, e a introspecção de packs precisa dela | repetir a regra aqui duplicaria uma regra de acesso; mudar o seam `ApiKeyAdmin` pediria ADR |

---

# Fase 3 (2026-10-02): passada de encaixe — MCP e desfecho por gravidade

Insumos: a clarificação de 2026-10-02 (FR-022); a nota para a 008 no plano da 007; ADR-018. Decisões em
[research.md](research.md) R25–R32. **Sem divergência do `design.md`**: rotas de MCP nas duas superfícies, como ele
prevê, sobre o seam da 007.

## Summary (Fase 3)

A API ganha o CRUD de servidores MCP — do usuário em `/v1/mcp` (com `available` e saúde do próprio servidor) e globais
em `/private/v1/mcp`, só para o grupo de administração —, no formato do `mcp.yaml` da 007. O desfecho de uma execução
passa a ser decidido pela gravidade dos registros (ADR-018): só `notice` é sucesso; algum `error` é falha, e a falha
sem streaming (502) leva `x-should-retry: false` para que o SDK oficial não reexecute o loop. Toque declarado na 011:
`create_app(mcp=…)`.

## Technical Context (Fase 3)

**Dependências**: nenhuma nova. Seam novo consumido: `McpRegistry` (007, `ai_core.mcp.api`).
**Storage**: sem mudança (o registry persiste pela 007). **Testing**: rotas com o `McpService` da 007 em memória e a
003 real; desfecho com o motor real e o provider simulado.
**Constraints**: nenhum valor de credencial em resposta; 404 idêntico para MCP alheio e inexistente; a API não conhece
`kind` da 005.

## Constitution Check (Fase 3)

| Princípio | Resultado | Evidência |
|---|---|---|
| II. Seams | ✅ | Só `ai_core.mcp.api`; as regras de escopo e de rede ficam na 007; a 008 só traduz JSON e erros |
| IV. Assistant é a fronteira | ✅ | MCP de usuário só no escopo do dono; globais só para o grupo de administração (AdminGate da 003) |
| VI. Conteúdo externo | ✅ | Resposta nunca traz valor de credencial; `stdio` recusado pela API (só arquivo do operador) |
| VII. Falha fechada | ✅ | Falha de execução continua explícita (502 / `finish_reason: "error"`), agora sem reexecução automática; registro `notice` não vira falha |
| XIII. Portas e adapters | ✅ | Registry injetado como seam opcional; nenhuma porta nova |

**Module boundary gate (Fase 3)**: `ai_core/http/**` e `tests/http/**`; toque declarado na 011
(`wiring._api` passa `mcp=parts["mcp"]`); import-linter: `ai_core.http` já só enxerga a 007 pelo `api.py` (contrato
existente). **Resultado**: PASS.

## Project Structure (Fase 3)

```text
ai-core/packages/core/src/ai_core/http/
├── adapters/mcp_routes.py      # NOVO: /v1/mcp e /private/v1/mcp sobre o McpRegistry
├── adapters/app.py             # + mcp opcional; monta as rotas
├── adapters/chat.py            # + x-should-retry: false no 502
├── domain/mcp_body.py          # NOVO: corpo ⇄ McpServerDraft; servidor, resumo e saúde em JSON
├── domain/errors.py            # McpConflict → 409 com param "alias"
└── domain/openai_chunks.py     # finish_reason por severity
```

## Seam Notes for Consumers (Fase 3)

| Consumidor | O que precisa saber |
|---|---|
| Clientes OpenAI | Execução truncada pelo limite ou com corte de contexto agora é `stop` (200); falha (`error`) sem streaming é 502 com `x-should-retry: false` |
| Operador | Servidores MCP globais pela API em `/private/v1/mcp` (chave do grupo de administração); os do `mcp.yaml` aparecem na listagem, somente leitura |
| 011 | `create_app(..., mcp=parts["mcp"])` |

