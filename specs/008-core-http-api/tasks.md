---

description: "Task list for 008 — Fase 1 (US1), Fase 2 (US2, US3, US4, US5, US7) e Fase 3 (MCP, desfecho)"
---

# Tasks: API HTTP — chat completions compatível com OpenAI

**Input**: Design documents from `/specs/008-core-http-api/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: incluídos. O seam deste módulo é a própria API HTTP, e a SC-002 exige a suíte ponta a ponta rodando só via
HTTP; as rejeições (princípio IV, FR-012) e o formato de chunk só se demonstram por teste.

**Organization**: só a **User Story 1** (Fase 1 do roadmap), mais FR-010 e as rejeições de campo de ampliação e de data
de referência, que são da rota entregue agora ([research.md](research.md) R8, R9). **Não** entram: listagem de modelos
(US2), requisição nativa (US3), CRUD (US4), introspecção e saúde (US5), fila (US6), conversas (US7) e Open WebUI (US8)
— nem as portas `ConversationStore` e `HealthProvider`. A porta `Clock` **entra**: o campo `created` do formato OpenAI
faz esta fase ler o relógio (R7b).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: user story da tarefa (US1)
- Todo caminho é relativo à raiz do repositório

## Path Conventions

- Código: `ai-core/packages/core/src/ai_core/http/`
- Testes: `ai-core/packages/core/tests/http/{unit,contract,integration}/`
- Configuração: `ai-core/packages/core/pyproject.toml` (dependência) e `ai-core/pyproject.toml` (import-linter, pytest,
  grupo de desenvolvimento)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: o módulo existe no layout do ADR-012 e o framework HTTP entra no workspace

- [X] T001 Criar o esqueleto em `ai-core/packages/core/src/ai_core/http/`: `__init__.py` (docstring: este módulo não
  tem `api.py` — seu seam é a própria superfície HTTP), `domain/__init__.py` e `adapters/__init__.py`
- [X] T002 Acrescentar `fastapi>=0.141,<1` a `dependencies` em `ai-core/packages/core/pyproject.toml` e `httpx` ao
  grupo `dev` de `ai-core/pyproject.toml` (é o que o cliente de teste do framework usa); rodar
  `XDG_DATA_HOME=$HOME/.local/share uv sync` a partir de `ai-core/`
- [X] T003 Em `ai-core/pyproject.toml`, acrescentar `packages/core/tests/http` a `[tool.pytest.ini_options] pythonpath`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: as portas, as regras puras e as fábricas de teste

**⚠️ CRITICAL**: T004 e T005 precedem serviço, rota e testes

- [X] T004 Implementar `ai-core/packages/core/src/ai_core/http/ports.py` conforme
  [contracts/ports.md](contracts/ports.md): `Principal` (`Protocol` com `id`), `Authenticator`
  (`authenticate(surface, credential) -> Principal | None`, nunca levanta), `GrantResolver`
  (`resolve(model, principal) -> ExecutionGrant`, levanta `AssistantNotFound`), `RequestIds` (`next() -> str`),
  `Clock` (`now() -> datetime` com timezone — o campo `created` do formato OpenAI faz esta fase ler o relógio, e o
  princípio XIII manda que tempo passe por porta) e o erro `AssistantNotFound`. Importa só stdlib e
  `ai_core.graph.api` — nenhum framework HTTP
- [X] T005 [P] Implementar `ai-core/packages/core/src/ai_core/http/domain/`, puro e sem I/O:
  `chat_request.py` com `parse(body) -> ChatRequest` (modelo, mensagens, streaming), rejeitando com erro que nomeia o
  campo — `tools`, `functions`, `tool_choice`, `function_call` e qualquer campo de data de referência (FR-012) —, e
  exigindo `model` não vazio, `messages` não vazia e ao menos uma mensagem de papel `user`;
  `openai_chunks.py` com a construção dos chunks e da resposta completa conforme
  [contracts/sse-format.md](contracts/sse-format.md) — papel só no primeiro chunk, `finish_reason` só no último,
  progresso com `delta` vazio e campo extra, `finish_reason="error"` quando o evento final traz erro de execução mas
  **não** quando traz só apontamento de validator
- [X] T006 Criar `ai-core/packages/core/tests/http/conftest.py` e
  `ai-core/packages/core/tests/http/http_testkit.py`: a app montada em processo com o motor real (005), o
  `ScriptedProvider` da 006 e hooks programáveis; `SequentialRequestIds`; um `GrantResolver` de teste que pode levantar
  `AssistantNotFound`; um autenticador que pode recusar; e o cliente de teste do framework

**Checkpoint**: portas, regras puras e fábricas prontas — a US1 pode começar

---

## Phase 3: User Story 1 - Cliente compatível com OpenAI conversa em streaming (Priority: P1) 🎯 MVP

**Goal**: um cliente que fala o formato da OpenAI conversa com a plataforma, com e sem streaming, nas duas
superfícies, e recebe o identificador da requisição para achar o trace.

**Independent Test**: `uv run pytest packages/core/tests/http` passa sem rede; a integração faz a conversa inteira
só via HTTP.

### Tests for User Story 1 ⚠️

> Escrever primeiro e confirmar que falham antes de implementar.

- [X] T007 [P] [US1] `ai-core/packages/core/tests/http/unit/test_chat_request.py`: `parse` devolve modelo, mensagens e
  streaming; rejeita `tools`, `functions`, `tool_choice`, `function_call` e o campo de data de referência, cada um com
  erro que nomeia o campo; rejeita `model` ausente ou vazio, `messages` vazia e requisição sem mensagem de usuário;
  aceita e ignora `temperature`, `top_p` e `max_tokens`
- [X] T008 [P] [US1] `ai-core/packages/core/tests/http/unit/test_openai_chunks.py`: os oito itens de
  [contracts/sse-format.md](contracts/sse-format.md)
- [X] T009 [P] [US1] `ai-core/packages/core/tests/http/contract/test_chat_completions.py`: os treze itens de
  [contracts/chat-completions.md](contracts/chat-completions.md), com os nomes que o [quickstart.md](quickstart.md)
  usa nos filtros (`streaming`, `completo`, `rejeit`) — incluindo falha sem streaming virando **502**, e não 200 com
  marcador de erro
- [X] T010 [P] [US1] `ai-core/packages/core/tests/http/contract/test_http_ports.py`: os quatro itens de
  [contracts/ports.md](contracts/ports.md) — autenticador anônimo nas duas superfícies, recusa virando 401,
  `AssistantNotFound` virando 404 com corpo idêntico, e o identificador aparecendo no cabeçalho, no `id` e no trace
- [X] T011 [P] [US1] `ai-core/packages/core/tests/http/integration/test_http_end_to_end.py`: a conversa ponta a ponta
  só via HTTP (SC-002) com o Pack Runtime real carregando o `ai-generic` — prompt do pack como mensagem de sistema,
  validator do pack rodando, e o trace da requisição (achado pelo `X-Request-Id`) com começo, chamada de modelo,
  validação e fim

### Implementation for User Story 1

- [X] T012 [P] [US1] `ai-core/packages/core/src/ai_core/http/adapters/development.py`: `AnonymousAuthenticator` (mesmo
  Principal em qualquer superfície, nome que denuncia o que é), `DevelopmentPrincipal`, `Uuid4RequestIds`,
  `SequentialRequestIds`, `SystemClock` e `FixedClock`
- [X] T012b [P] [US1] `ai-core/packages/core/tests/http/integration/test_openai_sdk_client.py`: apontar o cliente
  `AsyncOpenAI` real para a app em processo, pelo transporte ASGI do cliente HTTP do SDK, e conversar com e sem
  streaming sem nenhuma adaptação — a prova direta da SC-004. O SDK já está no ambiente por ser o adapter da 006
- [X] T013 [US1] `ai-core/packages/core/src/ai_core/http/service.py`: `ChatService` — recebe corpo já validado e
  Principal, resolve o grant pela porta, gera o identificador da requisição, monta o `ExecutionRequest` (005) **sem**
  data de referência (FR-012), roda o motor e devolve os chunks prontos de `domain/openai_chunks.py`, com e sem
  streaming. Não importa `adapters/` e não conhece HTTP
- [X] T014 [US1] `ai-core/packages/core/src/ai_core/http/adapters/sse.py`: serialização `data: <json>\n\n`, o
  encerramento `data: [DONE]\n\n` e o tipo de conteúdo; nada de regra de formato, que é de `domain/`
- [X] T015 [US1] `ai-core/packages/core/src/ai_core/http/adapters/chat.py`: o roteador com
  `POST /chat/completions` — traduz o corpo por `domain/chat_request.py`, resolve o Principal pela dependência de
  autenticação, chama o `ChatService` e devolve `StreamingResponse` ou objeto único; mapeia
  `AssistantNotFound` → 404, autenticação recusada → 401, erro de requisição e erro do motor antes do primeiro evento
  → 400; põe `X-Request-Id` em toda resposta
- [X] T016 [US1] `ai-core/packages/core/src/ai_core/http/adapters/app.py`: `create_app(engine, authenticator, grants,
  request_ids)` montando o mesmo roteador em `/v1` e `/private/v1`, cada um com sua superfície declarada. É o que a
  011 chama no boot
- [X] T017 [US1] Rodar `uv run pytest packages/core/tests/http` a partir de `ai-core/` até T007–T011 passarem, e
  `uv run mypy` e `uv run ruff check packages` limpos

**Checkpoint**: a US1 está completa — a conversa da Fase 1 acontece por HTTP, e a 011 já pode montar a app

---

## Phase 4: Polish & Cross-Cutting Concerns

- [X] T018 Acrescentar a `ai-core/pyproject.toml` os contratos de import-linter de [research.md](research.md) R11 —
  `ai_core.http.domain` não importa portas, service nem adapters; `ai_core.http.service` não importa adapters;
  `ai_core.http.ports`/`domain`/`service` não importam `fastapi` nem `starlette`; nenhum outro módulo do core importa
  o framework HTTP; e `ai_core.http` só enxerga outros módulos pelo `api.py` — e rodar `uv run lint-imports` até todos
  aparecerem como `KEPT`
- [X] T019 Executar as seções de [quickstart.md](quickstart.md) (pré-requisitos, verificação completa, cenários 1–4) e
  corrigir divergências entre o resultado e o "Esperado"
- [X] T020 [P] Atualizar a seção "Código" de `CLAUDE.md` (o módulo `ai_core/http/` existe, com chat completions
  compatível com OpenAI nas duas superfícies; listagem de modelos, conversas e fila continuam para as Fases 2 e 7) e a
  linha da 008 em `specs/README.md` (status "Fase 1 implementada (US1: chat completions)")

---

## Fase 2 (2026-09-30): US2, US3, US4 (Assistants), US5 (packs, chaves, saúde), US7

Escopo e decisões em [plan.md](plan.md) ("Fase 2") e [research.md](research.md) R12–R24. **Não** entram: endpoints de
MCP (Fase 3), fila e progresso de tool (US6, Fase 7), Open WebUI (US8, Fase 7). Caminhos abaixo relativos a
`ai-core/packages/core/`; `http/` = `src/ai_core/http/`.

## Phase 5: Foundational da Fase 2 — troca atômica para os seams da 003 (R13, R14, R15, R23)

**⚠️ CRITICAL**: bloqueia as stories da Fase 2; ao fim dela, a suíte inteira do workspace precisa passar de novo.

- [X] T021 Reescrever `http/ports.py` (contracts/ports.md, "Fase 2"): remover `Principal`, `Authenticator`,
  `GrantResolver`, `AssistantNotFound`, `PUBLIC_SURFACE`/`PRIVATE_SURFACE` (passam a vir de `ai_core.assistants.api`);
  manter `RequestIds` e `Clock`; acrescentar `Conversation`, `StoredMessage`, `ConversationPage`, `HealthItem`,
  `HealthReport` (data-model.md, "Fase 2") e os `Protocol` `ConversationStore`, `HealthProvider` e `AdminGate`, com as
  assinaturas exatas do contrato
- [X] T022 [P] Criar `tests/http/unit/test_errors.py` (contracts/errors.md): envelope `{"error": {message, type, param,
  code}}` para cada linha da tabela; 404 com o mesmo corpo para inexistente e não autorizado; 424 com
  `x_ai_core.reasons`; 429 com `Retry-After` arredondado para cima
- [X] T023 Implementar `http/domain/errors.py` (a tabela do R14 como função pura: exceção → status, type, code, param,
  extras) e `http/adapters/errors.py` (tratadores de exceção do framework que usam a tabela e escrevem o envelope e
  `Retry-After`); `http/adapters/auth.py` com a extração `Authorization: Bearer <token>` (R15) — ausente, outro
  esquema ou vazio → `credential=None` → 401 no envelope
- [X] T024 Migrar a rota de chat e a app para os seams da 003: `http/adapters/chat.py`, `http/adapters/app.py`
  (`create_app` recebe `authenticator`, `grants`, `directory`, `keys`, `packs`, `admin`, `conversations`, `health`,
  `request_ids`, `conversation_ids`, `clock`), `http/service.py` (`AssistantNotFound`, `RequestRejected`,
  `AssistantUnavailable`, `RateLimited` da 003 atravessam até os tratadores do T023) e
  `http/adapters/development.py` (`AnonymousAuthenticator` devolve `Principal(subject="user:anonymous",
  scheme=SCHEME_OF_SURFACE[surface])` da 003; `DevelopmentPrincipal` sai); atualizar `tests/http/http_testkit.py`,
  `tests/http/contract/test_http_ports.py`, `test_chat_completions.py` e `tests/http/integration/*` para os tipos da
  003 e o envelope de erro
- [X] T025 Acrescentar a `src/ai_core/assistants/service.py` o método público `AccessService.is_admin(principal) ->
  bool` (a regra de `_require_admin`, que passa a usá-lo) e um teste em
  `tests/assistants/contract/test_key_admin.py`; é a implementação da porta `AdminGate` (R20)
- [X] T026 Troca na composition root (exceção declarada do R13): `src/ai_core/bootstrap/wiring.py` constrói, depois do
  motor, `AssistantsService` (003: `YamlAssistantConfigSource` do `assistants_file` ou configuração vazia,
  `InMemoryUserAssistantStore`, catálogos vazios, `InMemoryRateCounterStore`, nomes de flow do motor) e `AccessService`
  (`InMemoryApiKeyStore`, `DisabledOidcVerifier`, `SecretsTokenGenerator`, `admin_group` da configuração), a
  `InMemoryConversationStore`, um `HealthProvider` mínimo a partir do relatório de boot e as duas instâncias de
  `RequestIds`, e os entrega a `create_app`; acrescenta a etapa `assistants` (degradável) que roda `validate()` e põe os
  indisponíveis no relatório; `profiles.py` mantém o `AnonymousAuthenticator` nos dois perfis; remover
  `src/ai_core/bootstrap/grants.py` e `tests/bootstrap/unit/test_grants.py`; migrar os `assistants.yaml` de
  `tests/bootstrap/` (testkit, `test_cli_serve.py`, `test_boot_degradado.py`) para o formato da 003 (`visibility`,
  `auth`, `models.allow`) e trocar a expectativa de "flow inexistente para o boot" por "Assistant indisponível no
  relatório e 424 no chat"
- [X] T027 Atualizar `ai-core/pyproject.toml` (import-linter): `psycopg`/`psycopg_pool` proibidos em
  `ai_core.http.ports`/`domain`/`service`; rodar `uv run lint-imports`, `uv run mypy` e `uv run pytest` inteiros até
  passarem

**Checkpoint**: a plataforma monta com os serviços da 003; chat completions responde como antes, com o envelope novo

## Phase 6: User Story 2 — Assistants aparecem como modelos (Priority: P1)

**Independent Test**: `uv run pytest packages/core/tests/http/contract/test_models_route.py`.

- [X] T028 [P] [US2] Criar `tests/http/contract/test_models_route.py` (contracts/models.md): com os serviços reais da
  003 em memória, dois Principals veem listas que diferem exatamente pela ACL (US2 cen. 1); privado de grupo aparece
  para o membro; indisponível não aparece; o id listado resolve no chat; o id de privado usado por quem não pode dá o
  mesmo 404 de um inexistente (US2 cen. 2); mesmo formato nas duas superfícies; `created` do relógio fixo
- [X] T029 [US2] Implementar `http/adapters/models.py` (`GET /models` nas duas superfícies, sobre
  `AssistantDirectory.discover`) e a construção da entrada em `http/domain/openai_chunks.py` ou num `domain/models.py`
  puro: `{"id", "object": "model", "created", "owned_by", "x_ai_core": {generation, description, origin, allow}}`

## Phase 7: User Story 3 — Requisição nativa que só restringe (Priority: P2)

**Independent Test**: `uv run pytest packages/core/tests/http/contract/test_native_route.py`.

- [X] T030 [P] [US3] Criar `tests/http/unit/test_native_request.py` e `tests/http/contract/test_native_route.py`
  (contracts/native-request.md): cada campo de `WIDENING_FIELDS` recusado nomeando o campo e sem chamar o motor (US3
  cen. 1); campo desconhecido recusado; data de referência recusada; `assistant` + `model` = id completo; mesma resposta
  da compat com e sem streaming; e, na compat, `packs`/`mcp_servers`/`provider` agora também recusados (R18)
- [X] T031 [US3] Implementar `http/domain/native_request.py` (parser estrito) e a rota `POST /chat` nas duas
  superfícies em `http/adapters/chat.py`; trocar `CAPABILITY_FIELDS` de `http/domain/chat_request.py` por
  `WIDENING_FIELDS` da 003 (R18)

## Phase 8: User Story 4 — Usuário gerencia Assistants próprios (Priority: P2)

**Independent Test**: `uv run pytest packages/core/tests/http/contract/test_user_assistants_routes.py`.

- [X] T032 [P] [US4] Criar `tests/http/unit/test_assistant_body.py` e
  `tests/http/contract/test_user_assistants_routes.py` (contracts/user-assistants.md): criar → ler → atualizar →
  listar → remover pela superfície pública; fora da política → 400 `policy_violation` com `param`; sem política → 400
  `no_applicable_policy`; nome repetido → 409; nome alheio → 404; criado aparece em `/v1/models` do dono e resolve no
  chat (US4 cen. 2); as rotas não existem em `/private/v1`
- [X] T033 [US4] Implementar `http/domain/assistant_body.py` (JSON ⇄ `UserAssistantDraft`, modelos em
  `provider/modelo`, campo desconhecido recusado) e `http/adapters/user_assistants.py` (rotas sobre
  `AssistantDirectory`, só em `/v1`)

## Phase 9: User Story 5 — Operação pela superfície privada (Priority: P2)

**Independent Test**: `uv run pytest packages/core/tests/http/contract/test_private_routes.py`.

- [X] T034 [P] [US5] Criar `tests/http/contract/test_private_routes.py` (contracts/private-surface.md): pack em erro com
  status e mensagem para o admin e 404 para chave fora do grupo (US5 cen. 1); emitir → autenticar com a chave → listar
  sem a chave → revogar → recusada (US5 cen. 2), e 404 para quem não é admin; saúde com qualquer chave, 200 quando ok e
  503 quando um item não está (US5 cen. 3); nenhuma dessas rotas em `/v1`
- [X] T035 [US5] Implementar `http/adapters/private.py` (`/packs` com `AdminGate`, `/admin/keys` sobre `ApiKeyAdmin`,
  `/health` sobre `HealthProvider`) e um `StaticHealthProvider` de teste em `http/adapters/development.py`

## Phase 10: User Story 7 — Conversa armazenada e retomada no servidor (Priority: P2)

**Independent Test**: `uv run pytest packages/core/tests/http/contract/test_conversation_routes.py
packages/core/tests/http/integration/test_conversation_restart.py`.

- [X] T036 [P] [US7] Criar `tests/http/contract/test_conversation_store.py` (contracts/ports.md, "Fase 2"), parametrizado
  memória × Postgres (fixture como a da 003, schema `http`): isolamento por dono; ordem das mensagens; `append` em
  conversa apagada → `False`; `delete_inactive(before=…)` apaga só as inativas; paginação estável e mais recente
  primeiro; um armazenamento novo sobre o mesmo banco encontra a conversa
- [X] T037 [P] [US7] Criar `tests/http/unit/test_conversations_domain.py` e `tests/http/unit/test_conversation_expiry.py`:
  com id, só histórico + última mensagem de usuário entram (mensagens de assistente e de tool do cliente descartadas —
  SC-005); sem id, as mensagens do pedido; o que é gravado ao fim (a última de usuário e a resposta, com `request_id`,
  citações e marcações); execução com erro não grava; expiração com relógio fixo apaga no prazo e nem um ciclo depois
  (SC-007)
- [X] T038 [P] [US7] Criar `tests/http/contract/test_conversation_routes.py` e
  `tests/http/integration/test_conversation_restart.py` (contracts/conversations.md): US7 cen. 1, 2 (nas duas
  superfícies, mesmo subject), 3 (serviço novo sobre o mesmo armazenamento, em memória e em Postgres), 4, 5, 6; id no
  cabeçalho e em `x_ai_core.conversation_id` com e sem streaming; conversa de outro Assistant → 400
  `conversation_assistant_mismatch`; conversa apagada durante a execução não recebe a troca
- [X] T039 [US7] Implementar `http/domain/conversations.py` (regras puras do R21), `http/adapters/conversations_memory.py`,
  `http/adapters/sql/001_conversations.sql` (tabelas `http.conversations` e `http.messages`), `http/adapters/postgres_schema.py`
  (`migrate(pool, now=…)`, mesmo desenho da 003) e `http/adapters/conversations_postgres.py`
- [X] T040 [US7] Implementar em `http/service.py` o fluxo de conversa do `ChatService` (resolver → abrir ou carregar →
  executar → gravar no evento final sem erro) e o `ConversationService` (listar, ler, apagar, `expire()` com prazo
  configurável, default 180 dias); `conversation_id` no primeiro chunk e na completion (`http/domain/openai_chunks.py`) e
  no cabeçalho `X-Conversation-Id`; rotas `GET /conversations`, `GET|DELETE /conversations/{id}` nas duas superfícies em
  `http/adapters/conversations.py`

## Phase 11: Polish da Fase 2

- [X] T041 Rodar a seção "Fase 2" do [quickstart.md](quickstart.md) e a verificação completa (`uv run pytest` com e sem
  `AI_CORE_TEST_POSTGRES_DSN`, `uv run mypy`, `uv run ruff check packages`, `uv run lint-imports`), corrigindo
  divergências
- [X] T042 [P] Atualizar `CLAUDE.md` ("Código": a API consome os seams da 003; rotas novas; conversas em Postgres) e a
  linha da 008 em `specs/README.md` ("Fase 1 e Fase 2 implementadas; MCP na Fase 3; fila e Open WebUI na Fase 7")

---

## Ajuste de 2026-10-01 — falha do armazenamento de credenciais (FR-021)

Clarificação de 2026-10-01: a autenticação que não consegue consultar o armazenamento responde 503
`storage_unavailable`, não 500. A 003 garante que `authenticate` só levanta nesse caso (credencial ruim devolve `None`).

- [X] T043 [P] Estender `tests/http/unit/test_errors.py` (503 `storage_unavailable`, `server_error`, mensagem fixa) e
  `tests/http/contract/test_private_routes.py`: autenticador que levanta → 503 nas duas superfícies, sem o texto da
  exceção no corpo; e, na 011, `tests/bootstrap/integration/test_persistent_profile.py` — saúde com o banco fora por
  HTTP é 503
- [X] T044 Implementar `storage_unavailable()` em `src/ai_core/http/domain/errors.py` e, em
  `src/ai_core/http/adapters/auth.py`, a tradução de exceção do autenticador em 503, registrando a causa em log

---

## Fase 3 (2026-10-02): passada de encaixe — MCP e desfecho por gravidade (research R25–R32)

Caminhos relativos a `ai-core/packages/core/`. Testes primeiro; marcas `us4` (MCP do usuário), `us5` (MCP globais) e
`us6` (progresso de tool); o desfecho por gravidade é transversal (sem marca de história).

## Phase 12: Foundational da Fase 3 — desfecho por gravidade (FR-022, ADR-018)

- [X] T045 [P] Estender `tests/http/unit/test_openai_chunks.py`: `finish_reason` é `"stop"` sem registros e com só
  registros `severity="notice"` de qualquer `kind` (`IterationLimit`, `ContextTrimmed`, `ValidatorIssue`), e `"error"`
  com algum `severity="error"`; e `tests/http/contract/test_chat_completions.py` (com o motor real): execução cujo
  `FinalEvent` só tem `notice` → 200 e `finish_reason: "stop"` sem streaming; com `error` → 502, corpo com a resposta e
  os motivos, e cabeçalho `x-should-retry: false`; erro anterior à execução (Assistant indisponível, 424) → **sem** o
  cabeçalho. Para produzir os registros, um `ScriptedHooks` cujo validator aponta (notice) e um provider que falha no meio
  (error)
- [X] T046 Em `src/ai_core/http/domain/openai_chunks.py`, `finish_reason` decide por `issue.severity` e
  `VALIDATOR_ISSUE` sai; em `src/ai_core/http/adapters/chat.py`, a resposta 502 de falha de execução ganha
  `x-should-retry: false` (constante `NO_RETRY_HEADER` no módulo) (depende de T045)

**Checkpoint**: execução truncada é sucesso; falha sem streaming não é repetida pelo SDK

---

## Phase 13: User Story 4 — MCPs próprios (Priority: P2 — Fase 3)

**Goal**: o usuário gerencia os próprios servidores MCP em `/v1/mcp` e os usa num Assistant próprio (US4 cen. 1).

**Independent Test**: `uv run pytest packages/core/tests/http -m us4 -k mcp`.

- [X] T047 [P] [US4] Criar `tests/http/unit/test_mcp_body.py`: `draft_from_json` na forma do `mcp.yaml` (`alias`,
  `transport`, `endpoint`, `description`, `auth: {type, credential}`, `enabled`, `user_access`, `policy: {allowed_tools,
  write_tools, timeout_ms, max_response_bytes}`); chave desconhecida no topo, em `auth` ou em `policy` → `InvalidRequest`
  nomeando o campo; tipo errado (lista onde se espera texto) → idem; `alias` do caminho prevalece e, no escopo `user`,
  ganha `~` se vier sem; `server_json` com todos os campos de contracts/mcp-routes.md e só o **nome** da referência de
  credencial; `summary_json` sem endpoint nem política; `health_json` com `ok`, `detail`, `tools`, `missing`
- [X] T048 [P] [US4] Criar `tests/http/contract/test_mcp_routes.py` (parte do usuário, itens 1–4, 6 e 7 de
  [contracts/mcp-routes.md](contracts/mcp-routes.md)), com o `McpService` da 007 em memória (`InMemoryServerStore`,
  `ScriptedMcpTransport` com um servidor em `https://agenda.example/mcp` anunciando `listar` e `marcar`,
  `InMemorySecretResolver`, `InMemoryDiscoveryCache`, `FixedDnsResolver`) e os serviços da 003: ciclo criar → ler →
  atualizar → listar → saúde → remover (com e sem `~` no caminho); MCP de A → 404 para B com a mesma mensagem;
  `available` com próprios e globais liberados, sem endpoint nem política de global; recusas da 007 com `param` (`http`
  em MCP de usuário, `stdio`, `policy.allowed_tools` vazia) e campo desconhecido → 400; **US4 cen. 1**: MCP `~agenda`
  criado por `POST /v1/mcp` e Assistant de usuário com `mcp: ["~agenda"]` criado por `POST /v1/assistants` → aparece em
  `GET /v1/models` do dono; nenhuma resposta contém valor de credencial
- [X] T049 [US4] Criar `src/ai_core/http/domain/mcp_body.py` (`draft_from_json(body, *, scope, alias=None)`,
  `server_json`, `summary_json`, `health_json`) — faz T047 passar
- [X] T050 [US4] Criar `src/ai_core/http/adapters/mcp_routes.py` com `user_mcp_router()` (rotas de R26; `available`
  declarada antes de `{alias}`) e, em `src/ai_core/http/adapters/app.py`, `create_app(..., mcp: McpRegistry | None =
  None)` guardando `app.state.mcp` e montando o roteador em `/v1` só com registry; em `src/ai_core/http/domain/errors.py`,
  `McpConflict` → 409 com `param: "alias"` (antes do caso genérico de `Conflict`) e `UnknownServer` → 404 (depende de
  T049; faz T048 passar)

---

## Phase 14: User Story 5 — MCPs globais na superfície privada (Priority: P2 — Fase 3)

**Goal**: o operador gerencia os MCPs globais em `/private/v1/mcp`, só com chave do grupo de administração.

**Independent Test**: `uv run pytest packages/core/tests/http -m us5 -k mcp`.

- [X] T051 [P] [US5] Estender `tests/http/contract/test_mcp_routes.py` (item 5): chave fora do grupo de administração →
  404 de recurso inexistente em todas as rotas `/private/v1/mcp*`, sem tocar o registry; administrador cria (com `auth`
  bearer e `user_access`), lê, atualiza, lista e remove; entrada vinda do arquivo do operador (`McpConfig` com uma
  entrada) aparece na listagem com `origin: "file"` e `PUT`/`DELETE` nela → 409 com `param: "alias"`; saúde de um global
  com o servidor programado e com ele fora (`ok: false`, `detail`)
- [X] T052 [US5] Em `src/ai_core/http/adapters/mcp_routes.py`, `global_mcp_router()` (rotas de R27, `_require_admin`
  antes de tudo — o mesmo da superfície privada) montado em `/private/v1` em `create_app` (depende de T050; faz T051
  passar)

---

## Phase 15: User Story 6 — progresso de tool (Priority: P2 — Fase 3, cen. 1)

- [X] T053 [P] [US6] Estender `tests/http/contract/test_chat_completions.py`: com um motor `agentic` montado por
  `graph_testkit.engine(capabilities=FakeCapabilities(), controller=ScriptedController([tool_action("generic.calculate",
  expression="2+2"), ANSWER]))`, a app de `app_with(motor, …)` e um grant `agentic` de `graph_testkit.agentic()`, e
  streaming, o stream contém, antes do primeiro token, um chunk de progresso com `stage: "execute_tool"` e `detail:
  "generic.calculate"`, e o cliente OpenAI padrão ainda lê a resposta (US6 cen. 1) — sem código novo se passar

---

## Phase 16: Polish da Fase 3

- [X] T054 Toque declarado na 011: `src/ai_core/bootstrap/wiring.py` (`_api`) passa `mcp=parts["mcp"]` a `create_app`;
  em `tests/bootstrap/integration/test_platform_agentic_mcp.py`, (a) um teste que cria um MCP global por `POST
  /private/v1/mcp` com `TEST_API_KEY` e o vê em `GET /private/v1/mcp`; e (b) o **Independent Test da US4**, no perfil
  `test` com controller e transporte trocados (`ScriptedMcpTransport` com um servidor em `https://agenda.example/mcp`
  anunciando `listar`): `POST /v1/mcp` cria `~agenda` com `TEST_OIDC_TOKEN`, `POST /v1/assistants` cria `~pesquisa`
  (`flow: agentic`, `mcp: ["~agenda"]`, `models` com `controller`), e uma conversa com `model: "~pesquisa"` faz o
  controller programado pedir `~agenda.listar` — o transporte recebe `call_tool:listar` e a resposta chega com 200. A
  política de usuário do `assistants.yaml` do teste libera o flow `agentic`
- [X] T055 Rodar a seção "Fase 3" de [quickstart.md](quickstart.md) e corrigir divergências
- [X] T056 [P] Atualizar a seção "Código" de `CLAUDE.md` (rotas de MCP; desfecho por gravidade; `x-should-retry`) e a
  linha da 008 em `specs/README.md`; e a linha da 007 ("falta a passada da 008" sai)
- [X] T057 Verificação completa a partir de `ai-core/`: `uv run pytest` (com e sem `AI_CORE_TEST_POSTGRES_DSN`),
  `uv run mypy`, `uv run ruff check packages`, `uv run lint-imports`

---

## Dependencies & Execution Order

**Fase 3**: T045 → T046 (desfecho); US4: T047 ∥ T048, depois T049 → T050; US5: T051 → T052 (depois de T050, mesmo
arquivo); US6: T053 a qualquer momento depois de T046; Polish: T054 depois de T052; T055 e T057 por último; T056 em
paralelo.

### Phase Dependencies

**Fase 2**: T021 → (T022 ∥ T025) → T023 → T024 → T026 → T027 — bloqueia as stories. Depois: US2 (T028 → T029), US3
(T030 → T031), US4 (T032 → T033), US5 (T034 → T035) e US7 (T036–T038 → T039 → T040) são independentes em teste;
`http/adapters/chat.py` é tocado por T024, T031 e T040 nessa ordem, e `http/service.py` por T024 e T040. Polish por
último.


- **Setup (Phase 1)**: T001 e T002 primeiro; T003 em paralelo
- **Foundational (Phase 2)**: T004 antes de T005; T006 depois dos dois e de T012, que por isso pode ser antecipada
- **User Story 1 (Phase 3)**: depende de Setup + Foundational
- **Polish (Phase 4)**: T018 depois de T016; T019 depois de T017; T020 em paralelo

### Within User Story 1

- Testes (T007–T011) antes da implementação e falhando
- T012 é independente; T013 depende de T004 e T005; T014 → T015 → T016
- T017 é o portão da fase

### Parallel Opportunities

- T007, T008, T009, T010 e T011 em paralelo (arquivos distintos)
- T012 em paralelo com qualquer teste já escrito
- T020 em paralelo com qualquer tarefa da Phase 3 concluída

---

## Parallel Example: User Story 1

```bash
# Testes da US1, juntos:
Task: "unit/test_chat_request.py (T007)"
Task: "unit/test_openai_chunks.py (T008)"
Task: "contract/test_chat_completions.py (T009)"
Task: "contract/test_http_ports.py (T010)"
Task: "integration/test_http_end_to_end.py (T011)"
```

---

## Implementation Strategy

### MVP (US1, o escopo desta fase)

1. Phase 1 e 2: esqueleto, dependência, portas e regras puras
2. Phase 3: testes primeiro; depois adapters de desenvolvimento, serviço, SSE, rota e fábrica da app
3. **PARE e VALIDE**: quickstart, cenários 1–4 — streaming, resposta completa, rejeições e conversa só via HTTP
4. Phase 4: fronteiras de import, quickstart completo, documentação

### Depois desta fase

- 011 (mesma fase) monta a app, injeta os adapters do perfil e oferece `ai-core serve`
- Fase 2: a 003 fornece autenticador e resolvedor reais; entram listagem de modelos, conversas, CRUD e saúde
- Fase 7: progresso de tool, fila de admissão e Open WebUI
