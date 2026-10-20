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


---

# Fase 7 (2026-10-13): progresso, fila e Open WebUI (US6, US8)

Insumos: as quatro clarificações de 2026-10-13; o `design.md` ("Admissão e fila" e "Compatibilidade OpenAI e Open
WebUI", pré-aprovados); os estágios de progresso publicados nos contratos da 005; o código do Open WebUI v0.12.0.
Decisões em [research.md](research.md) R33–R41. **Sem divergência do `design.md`**: a decisão de admissão é pura em
`domain/`, as vagas e a fila ficam em memória no `service.py`, sem porta.

## Summary (Fase 7)

A API passa a limitar as execuções simultâneas, com uma fila curta: quem espera em streaming recebe na hora uma linha
"aguardando uma vaga"; fila cheia ou espera esgotada é 503 com `Retry-After`, antes de qualquer chamada de modelo. O
progresso do motor sai também como raciocínio (`delta.reasoning_content`, uma linha em português por etapa, até o
primeiro token), que o Open WebUI mostra num bloco recolhível. O cabeçalho `x-ai-core-store: false` torna efêmero um
pedido sem id de conversa. Nenhuma mudança na autenticação: o Open WebUI repassa o access token de cada usuário
(`system_oauth`) e a 003 o verifica. Toque declarado na 011: três variáveis e `create_app(admission=…)`. A interface de
verdade (Open WebUI + Keycloak) é provada numa passada de encaixe da 002, depois desta.

## Technical Context (Fase 7)

**Dependências**: nenhuma nova. **Storage**: sem mudança (o pedido efêmero não grava). **Testing**: motor programado que
segura a execução (porta de execução trocada na montagem) para a fila; a 003 real com dois tokens de teste de grupos
diferentes para a lista por usuário; o pedido do Open WebUI v0.12 como fixture.
**Performance Goals**: linha de fila e primeira linha de progresso no mesmo instante do pedido (bem antes dos 2 s da
SC-003); 0 execuções além do limite (SC-006).
**Constraints**: a vaga só é ocupada depois das recusas de 404/400/424/429; nenhum 503 de sobrecarga depois de uma
chamada de modelo; raciocínio nunca em `delta.content` e nunca depois do primeiro token; o 008 não lê nomes de nó — só
os estágios que a 005 publica, com linha genérica para o resto.
**Scale/Scope**: processo único (limite e fila por processo); valores provisórios 2 / 8 / 60 s, medidos no hardware
alvo na implementação (R36).

## Constitution Check (Fase 7)

| Princípio | Resultado | Evidência |
|---|---|---|
| II. Seams | ✅ | Só os estágios de progresso publicados pela 005; a autenticação continua sendo a da 003 |
| III. Streaming nativo | ✅ | Progresso e fila no stream, no instante do evento; raciocínio só antes do texto |
| IV. Assistant é a fronteira | ✅ | Lista de modelos por token (cada usuário do Open WebUI vê o que a 003 resolve para ele); `tools` continua recusado |
| VII. Falha fechada | ✅ | Sobrecarga é 503 explícito com `Retry-After`; espera esgotada com o stream aberto encerra com `finish_reason: "error"`; cabeçalho inválido é 400 que o nomeia |
| XI. Interface substituível | ✅ | Nada específico do Open WebUI na API além de campos que qualquer cliente pode usar (`reasoning_content`, um cabeçalho) |
| XII. Simplicidade | ✅ | Sem porta para a fila (regra pura + estado em memória); sem mudança de seam |
| XIII. Portas e adapters | ✅ | `domain/admission.py` e `domain/progress_text.py` puros; o cabeçalho é lido no adapter e validado no domínio |

**Module boundary gate (Fase 7)**: `ai_core/http/**` e `tests/http/**`; toques declarados na 011 (`settings.py`: três
variáveis; `wiring._api`: `admission=…`; `tests/bootstrap/`); nenhum import novo de outro módulo. A instalação
(`agentic-deploy`) é da 002. **Resultado**: PASS.

## Project Structure (Fase 7)

```text
ai-core/packages/core/src/ai_core/http/
├── domain/admission.py         # NOVO: AdmissionLimits, decide, retry_after — puro
├── domain/progress_text.py     # NOVO: estágio publicado (005) → linha em português; linha da fila
├── domain/openai_chunks.py     # progress_chunk com reasoning_content; opening/completion sem conversa no efêmero
├── domain/chat_request.py      # parse_store (x-ai-core-store); ChatRequest.store
├── domain/native_request.py    # idem, na requisição nativa
├── domain/errors.py            # Overloaded → 503 overloaded + Retry-After; store_conflict / invalid_header → 400
├── service.py                  # ExecutionSlots (vagas + fila FIFO); admissão entre o grant e o motor; efêmero
├── adapters/chat.py            # lê o cabeçalho; 503 com Retry-After; sem X-Conversation-Id no efêmero
└── adapters/app.py             # create_app(admission: AdmissionLimits | None = None)

ai-core/packages/core/src/ai_core/bootstrap/
├── settings.py                 # AI_CORE_MAX_EXECUTIONS, AI_CORE_QUEUE_SIZE, AI_CORE_QUEUE_WAIT_MS
└── wiring.py                   # _api passa admission

ai-core/packages/core/tests/http/
├── unit/test_progress_text.py, unit/test_admission_decision.py
├── contract/test_admission.py, contract/test_ephemeral.py, contract/test_open_webui.py
└── open_webui_v0_12.py         # o pedido do Open WebUI v0.12 (corpo e cabeçalhos), como fixture
```

## Seam Notes for Consumers (Fase 7)

| Consumidor | O que precisa saber |
|---|---|
| Clientes OpenAI | Progresso também em `delta.reasoning_content` antes do texto (clientes padrão ignoram); 503 `overloaded` com `Retry-After` quando a plataforma está cheia |
| Open WebUI (instalação, 002) | Conexão `system_oauth` para `/v1`, cabeçalho `x-ai-core-store: false`, tarefas auxiliares desligadas, `BYPASS_MODEL_ACCESS_CONTROL=true` (R40); provedor OIDC com access token JWT, audiência e grupos (R39) |
| 011 | Lê as três variáveis e passa `create_app(..., admission=AdmissionLimits(...))` |
| 005 | Os estágios de progresso publicados viram texto para pessoas; estágio novo aparece com a linha genérica até entrar na tabela |

# Fase 9 (2026-10-14): superfície de administração (US9)

Insumos: ADR-029, ADR-031, ADR-032, ADR-033, ADR-034; os planos da Fase 9 da 012, 003 e 009 (seams consumidos); o
desenho aprovado da console. Decisões em [research.md](research.md) R43–R49; contrato em
[contracts/admin-api.md](contracts/admin-api.md). **Refinamento do `design.md`**: versão no corpo em vez de
`If-Match` (R45), sem mudar a regra da FR-026.

## Summary (Fase 9)

Uma terceira superfície, `/admin/v1`, só para o grupo de administração, com token da console ou chave de API. Ela
traduz HTTP para os seams dos módulos donos — Assistants de sistema e sobreposições (003), "testar modelo" (006),
servidores MCP globais (007), uso, preços e destinos do trace (009), contas, grupos e login (012), chaves (003) e saúde
(011) — sem regra própria (ADR-029). Não admin vê 404 em tudo; nenhuma resposta traz segredo.

## Technical Context (Fase 9)

**Dependências**: nenhuma nova. **Seams consumidos novos**: `SystemAssistantAdmin` (003), `ModelRouting.check` (006),
`UsageReportSeam`/`PriceBook`/`TraceDestinations` (009), `AccountAdmin`/`LoginSettings` (012). **Storage**: nenhum.
**Testing**: formatos puros e o contrato rota a rota. **Constraints**: sem CORS; `no-store`; 404 indistinguível.

## Constitution Check (Fase 9)

| Princípio | Resultado | Evidência |
|---|---|---|
| II. Seams | ✅ | Só `api.py` dos donos; `SCHEMES_OF_SURFACE` da 003 (ADR-031) |
| IV. Assistant é a fronteira | ✅ | 404 para não admin; audiência própria da console (na 003) |
| VI. Conteúdo externo | ✅ | Nenhum segredo nas respostas (varredura no contrato); senha temporária só na resposta que a define |
| XI. API independente da interface | ✅ | Toda tela da console tem rota aqui; nenhuma regra na rota |
| XIII. Portas e adapters | ✅ | Formatos puros em `domain/admin_*.py`; FastAPI só em `adapters/admin.py` |

**Module boundary gate (Fase 9)**: `ai_core/http/**` e `tests/http/**`; o Module Boundary da spec passa a listar a 006
(`ModelRouting.check`) e a 012 entre os seams consumidos. Nada em `bootstrap/`: a 011 passa os seams na passada dela.
**Resultado**: PASS.

## Project Structure (Fase 9)

```text
ai-core/packages/core/src/ai_core/http/
├── adapters/admin.py              # router /admin/v1
├── adapters/app.py                # create_app(..., admin_seams: AdminSeams | None, instance: InstanceBranding | None)
├── adapters/mcp_routes.py         # global_mcp_router montável em /private/v1 e /admin/v1
├── domain/admin_assistants.py, admin_usage.py, admin_accounts.py, admin_observability.py
├── domain/errors.py               # + mapeamentos da Fase 9
└── ports.py                       # + AdminSeams, InstanceBranding (dataclasses de injeção)
```

## Seam Notes for Consumers (Fase 9)

| Consumidor | O que precisa saber |
|---|---|
| 011 | Passar `admin_seams` e `instance` ao `create_app` quando a identidade (ou só as chaves) estiver montada; sem eles, `/admin/v1` não existe |
| 013 (console) | [contracts/admin-api.md](contracts/admin-api.md) é a fonte dos esquemas; `GET /me` 404 = acesso negado |

---

# Passada de 2026-10-20: identidade Axon (US10; [ADR-037](../../docs/adr/ADR-037-a-plataforma-se-chama-axon.md), [ADR-038](../../docs/adr/ADR-038-marca-da-plataforma-e-marca-da-instalacao.md))

> As seções acima são os planos das passadas anteriores e ficam como foram executadas (ADR-037, item 6); os nomes
> antigos nelas se leem pela tabela do ADR-037. Esta seção é o plano da US10.

**Insumos lidos**: [spec.md](spec.md) (US10, FR-029–FR-033, SC-010, clarificações de 2026-10-20, inclusive a decisão do
mantenedor de recusar o cabeçalho antigo), [design.md](design.md), ADR-037, ADR-038, constituição 1.3.1, a passada da
011 (`DEFAULT_DISPLAY_NAME = "Axon"`, `AXON_LOGO_FILE`). Research: R50–R55. **Sem divergência do `design.md`**; sem ADR
novo: a recusa do cabeçalho antigo explica o nome novo sem aceitar o antigo, dentro do corte seco do ADR-037.

## Summary (US10)

Os cabeçalhos passam a `x-axon-store`/`x-axon-progress` e a extensão a `x_axon` (R50); o antigo recebe 400 que cita o
novo, antes de executar (R51); o OpenAPI se chama "Axon" (R52); o `me` ganha `instance.custom`, calculado pela composição
(R53). Fixture do Open WebUI, testes e documentos vivos acompanham (R54); testes novos para a recusa e o `custom` (R55).

## Technical Context (US10)

- **Language/Version, dependências, storage**: sem mudança.
- **Testing**: um arquivo de contrato novo (`us10`), casos novos no domínio e na superfície de administração; literais
  trocados nas suítes.
- **Scale/Scope**: três constantes, uma função pura e duas chamadas no adapter de chat, um campo em `InstanceBranding`,
  uma linha na composição (011); ~18 arquivos de teste; ~10 documentos.
- Nenhum `NEEDS CLARIFICATION`.

## Constitution Check (US10)

| Princípio | Resultado | Evidência |
|---|---|---|
| II. Módulos substituíveis por seams | ✅ | O seam de chat não muda de forma; `instance.custom` é aditivo (ADR-038) |
| VII. Falha fechada e explícita | ✅ | Cabeçalho antigo → 400 que nomeia o novo, antes de executar; nenhum "não gravar" é ignorado (R51) |
| XI. API independente da interface | ✅ | A API publica `custom`; a decisão de mostrar o lockup ou a atribuição é da console (013) |
| XII. Simplicidade deliberada | ✅ | A recusa é um mapa de dois nomes e uma função pura; sem alias (R51) |
| XIII. Portas e adapters | ✅ | A regra fica em `domain/`; o adapter só a chama com os nomes dos cabeçalhos |

**Module boundary gate**: `axon_ai/http/**` e `tests/http/**`. Fora do módulo, só `bootstrap/wiring.py::_instance` (a
011 calcula `custom` a partir da configuração que ela lê, R53), a integração da 011 que lê o `me`, e documentos vivos.
**Ports & adapters gate**: `InstanceBranding` ganha um campo; nenhuma porta nova. **Resultado**: PASS.

## Project Structure (US10)

```text
axon-ai/packages/core/
├── src/axon_ai/
│   ├── http/domain/chat_request.py     # STORE_HEADER, PROGRESS_HEADER novos; LEGACY_HEADERS; reject_legacy_headers (R50, R51)
│   ├── http/domain/{errors,openai_chunks}.py   # EXTRA = "x_axon" (R50)
│   ├── http/adapters/chat.py           # reject_legacy_headers nas duas entradas (R51)
│   ├── http/adapters/app.py            # title="Axon" (R52)
│   ├── http/adapters/admin.py          # me: instance.custom (R53)
│   ├── http/ports.py                   # InstanceBranding(name="Axon", logo_url, custom) (R53)
│   └── bootstrap/wiring.py             # _instance calcula custom (R53)
└── tests/
    ├── http/contract/test_legacy_headers.py   # novo (R55)
    ├── http/unit/test_chat_request.py         # reject_legacy_headers (R55)
    └── …                                      # literais e o me (R54)
```

## Seam Notes for Consumers (US10)

| Consumidor | O que muda para ele |
|---|---|
| Open WebUI (instalação) | A conexão passa a mandar `x-axon-store`/`x-axon-progress` na passada da instalação; antes disso, ela usa uma tag antiga do core |
| 011 | `_instance` calcula `custom` |
| 013 | `me.instance.custom` disponível; a console passa a usá-lo na passada dela |
| Cliente da API | Troca os cabeçalhos; o antigo recebe 400 que diz o novo; a extensão é `x_axon` |

## Complexity Tracking (US10)

| Complexidade | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Mapa de cabeçalhos antigos e a recusa (R51) | um cliente antigo que pede para não gravar teria a conversa gravada sem saber | ignorar como desconhecido: rejeitado pelo mantenedor (princípio VII) |

## Constitution Check — pós-design (US10)

Reavaliado com [contracts/](contracts/), [data-model.md](data-model.md) e [quickstart.md](quickstart.md) ("Fase 9,
incremento 9.5"): **PASS**.
