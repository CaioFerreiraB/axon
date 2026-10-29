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

## Fase 7 (2026-10-13): progresso, fila e Open WebUI (research R33–R41)

Caminhos relativos a `ai-core/packages/core/`, salvo os que começam com `specs/`, `docs/` ou `CLAUDE.md`. Testes
primeiro; marcas `us6` e `us8`. A interface de verdade (Open WebUI + Keycloak) é uma passada de encaixe da 002, depois
desta lista (R33).

## Phase 17: User Story 6 — fila e progresso como raciocínio (Priority: P2 — Fase 7, cen. 2–4)

**Goal**: execuções simultâneas limitadas, com fila curta e 503 de sobrecarga antes de qualquer chamada de modelo; o
progresso do motor e a espera na fila aparecem como raciocínio antes do texto.

**Independent Test**: `uv run pytest packages/core/tests/http -m us6`.

- [X] T058 [P] [US6] Criar `tests/http/unit/test_progress_text.py` com a tabela da R34, linha a linha:
  `progress_line("prepare_context", None) == "Preparando o contexto da pergunta…"`, `"load_capabilities"` → `"Carregando
  as ferramentas…"`, `("controller", "iteração 2")` → `"Decidindo o próximo passo (iteração 2)…"`, `("execute_tool",
  "scouting.search_docs")` → `"Usando a ferramenta scouting.search_docs…"`, `"retrieve"` → `"Consultando os
  documentos…"`, `"rerank"` → `"Ordenando os trechos encontrados…"`, `"gate"` → `"Conferindo se os trechos cobrem a
  pergunta…"`, `"generate"` → `"Escrevendo a resposta…"`, `"validate_answer"` → `"Conferindo a resposta…"`, estágio
  desconhecido `("novo", None)` → `"Etapa novo…"`; `controller`/`execute_tool` sem detalhe não quebram; e
  `queue_line(2) == "Aguardando uma vaga (posição 2 na fila)…"`
- [X] T059 [P] [US6] Criar `tests/http/unit/test_admission_decision.py`: `AdmissionLimits` recusa `max_executions` fora de 1–64,
  `queue_size` fora de 0–1000 e `max_wait` fora de 1 ms–600 s com `ValueError` que nomeia o campo; `decide(running,
  queued, limits)` → `"run"` se `running < max_executions`, senão `"queue"` se `queued < queue_size`, senão `"reject"`
  (com `queue_size=0`, cheio → `"reject"`); `retry_after` → `max(1, ceil(max_wait em segundos))` (60 s → 60; 0,2 s → 1;
  1,5 s → 2; 1 ms → 1)
- [X] T060 [P] [US6] Estender `tests/http/unit/test_openai_chunks.py` (contracts/sse-format.md, seção "Fase 7"):
  `progress_chunk(event, …, reasoning=True)` → `delta == {"reasoning_content": progress_line(...) + "\n"}` e o
  `x_ai_core.progress` de antes; `reasoning=False` → `delta == {}` (o chunk de antes); `queue_chunk(position=2, …)` →
  `delta.reasoning_content` com a linha da fila e `x_ai_core.progress == {"stage": "queue", "detail": "2"}`; nenhum
  deles tem `content` nem `finish_reason`; `final_chunk` com o registro `{"stage": "admission", "kind": "QueueTimeout"}`
  tem `finish_reason: "error"`
- [X] T061 [US6] Criar `src/ai_core/http/domain/progress_text.py`: `QUEUE_STAGE: Final = "queue"`, a tabela
  `PROGRESS_LINES` (estágio publicado pela 005 → modelo da linha, com `{detail}` onde a R34 o usa), `progress_line(stage:
  str, detail: str | None) -> str` (estágio desconhecido → `f"Etapa {stage}…"`; `{detail}` ausente → a linha sem os
  parênteses/nome) e `queue_line(position: int) -> str` — faz T058 passar
- [X] T062 [US6] Criar `src/ai_core/http/domain/admission.py`: `AdmissionLimits` (frozen, `max_executions: int`,
  `queue_size: int`, `max_wait: timedelta`, faixas validadas em `__post_init__`), `Decision = Literal["run", "queue",
  "reject"]`, `decide(running: int, queued: int, limits: AdmissionLimits) -> Decision` e `retry_after(limits) -> int` —
  faz T059 passar
- [X] T063 [US6] Em `src/ai_core/http/domain/openai_chunks.py`: `progress_chunk(..., reasoning: bool = True)` com a linha
  de `progress_line` em `delta.reasoning_content` (terminada em `"\n"`) quando `reasoning`, e `queue_chunk(*, position,
  request_id, model, created)`; a docstring do módulo troca "progresso com `delta` vazio" pela regra nova; em
  `src/ai_core/http/domain/errors.py`, `Overloaded(retry_after: int)` → 503, `type` `server_error`, `code` `overloaded`,
  com `Retry-After`, sem `x-should-retry`, e a constante do registro `QUEUE_TIMEOUT_KIND = "QueueTimeout"` (estágio
  `"admission"`) — faz T060 passar
- [X] T064 [P] [US6] Criar `tests/http/contract/test_admission.py` (contracts/admission.md, verificações 1–5) com um
  `HoldingEngine` novo em `tests/http/http_testkit.py` — implementa `ExecutionEngine.run` emitindo
  `ProgressEvent("generate")`, um `TokenEvent` e o `FinalEvent` só depois de um `asyncio.Event` liberado pelo teste, e
  conta execuções simultâneas (`running`, `peak`) e chamadas (`calls`): (1) 10 pedidos sem streaming simultâneos
  (`httpx.AsyncClient` com `ASGITransport` e `asyncio.gather`) com `AdmissionLimits(2, 3, 5 s)` → `peak == 2`, 5
  respostas 503 `overloaded` com `Retry-After: 5` e `calls == 5` ao final (nenhuma execução para os recusados — SC-006);
  (2) com as duas vagas ocupadas, `app.state.chat_service.stream(...)` de um pedido em streaming devolve o chunk de
  abertura e, logo em seguida, o `queue_chunk` com `posição 1` — antes de qualquer liberação do motor — e segue com o
  progresso e o texto ao ganhar a vaga (US6 cen. 2, SC-003); (3) espera esgotada (`max_wait=0,05 s`): sem streaming →
  503 com `Retry-After: 1`; em streaming → chunk final `finish_reason: "error"` com `QueueTimeout` no extra e `[DONE]`,
  e `calls` não muda; (4) iterador de streaming fechado (`aclose`) enquanto na fila → o lugar sai da fila e o próximo
  pedido entra quando a vaga libera; (5) com as vagas e a fila cheias, um pedido a um Assistant inexistente recebe 404,
  e um que estoura a cota do par recebe 429 — nenhum ocupa lugar (ordem do contrato)
- [X] T065 [US6] Em `src/ai_core/http/service.py`, `ExecutionSlots(limits)` — vagas e fila FIFO com `asyncio`, sem
  porta: `acquire()` decide por `domain/admission.decide`; `"run"` ocupa; `"queue"` devolve a posição e espera a vaga
  até `max_wait` (`asyncio.timeout`); `"reject"` levanta `Overloaded(retry_after(limits))`; a vaga é liberada no
  `finally` em volta da execução (evento final ou iterador fechado), e quem sai da fila por cancelamento ou espera
  esgotada é removido dela. No `ChatService`, a admissão entra entre `self._grants.resolve` e `engine.run` (depois das
  recusas de 404/400/424/429): em `complete`, espera esgotada → `Overloaded`; em `stream`, `"reject"` levanta antes do
  primeiro chunk (o adapter já busca o primeiro chunk antes de responder), `"queue"` emite a abertura e o `queue_chunk`
  e espera, espera esgotada → chunk final de erro com `QUEUE_TIMEOUT_KIND`; o progresso sai com `reasoning=True` até o
  primeiro `TokenEvent` e `reasoning=False` depois. Sem `admission`, nenhum limite (faz T064 passar)
- [X] T066 [US6] Em `src/ai_core/http/adapters/app.py`, `create_app(..., admission: AdmissionLimits | None = None)`
  repassado ao `ChatService`; confirmar que o 503 de `Overloaded` sai com `Retry-After` pela tabela de
  `domain/errors.py` nas duas superfícies, na compat e na requisição nativa; e atualizar o teste de US6 cen. 1
  (`test_chat_completions.py`, T053) para conferir também a linha `"Usando a ferramenta generic.calculate…"` em
  `delta.reasoning_content` antes do primeiro token

**Checkpoint**: nunca mais execuções que o limite; quem espera vê a fila; o progresso aparece como raciocínio

---

## Phase 18: User Story 8 — Open WebUI conectado, no lado da API (Priority: P3 — Fase 7)

**Goal**: o pedido do Open WebUI v0.12 funciona sem adaptação, cada token vê só os próprios Assistants, e o cabeçalho
`x-ai-core-store: false` torna efêmero o pedido sem id de conversa.

**Independent Test**: `uv run pytest packages/core/tests/http -m us8`.

- [X] T067 [P] [US8] Estender `tests/http/unit/test_chat_request.py`: `parse_store(None, None)`, `("true", None)`,
  `("TRUE", "conv_1")` → `True`; `("false", None)` e `("False", None)` → `False`; `("false", "conv_1")` →
  `ChatRequestInvalid` com `code="store_conflict"` e `field="x-ai-core-store"`; `("talvez", None)` e `("", None)` →
  `code="invalid_header"`, mesmo `field`; `parse(body, store_header="false")` devolve `ChatRequest.store is False`; e o
  mesmo em `tests/http/unit/test_native_request.py` para `parse_native`
- [X] T068 [P] [US8] Criar `tests/http/contract/test_ephemeral.py` (FR-023; contracts/chat-completions.md, seção "Fase
  7"), com o `Platform` do `http_testkit` e `ANA_TOKEN`: em `/v1` e `/private/v1` (com `ADMIN_KEY`), com e sem streaming,
  e em `POST /chat` nativo, o cabeçalho `x-ai-core-store: false` → 200, nenhum `conversation_id` no primeiro chunk nem no
  corpo, nenhum `X-Conversation-Id`, e `GET /v1/conversations` vazio para o subject; o mesmo pedido sem o cabeçalho cria
  a conversa (regressão do FR-013); com `conversation_id` existente + `false` → 400 `store_conflict` com `param:
  "x-ai-core-store"` e o motor não chamado; valor `talvez` → 400 `invalid_header`
- [X] T069 [P] [US8] Criar `tests/http/open_webui_v0_12.py` — o pedido como o Open WebUI v0.12.0 o monta
  (`routers/openai.py`, `utils/headers.py`, `utils/payload.py`): corpo com `model`, `messages` (sistema opcional, uma
  troca anterior de usuário e assistente, a pergunta), `stream: true`, `temperature`, `top_p`, `max_tokens`, `seed`,
  `stream_options: {"include_usage": true}`; cabeçalhos `Content-Type: application/json`, `Authorization: Bearer
  <token>` (o `system_oauth`) e `x-ai-core-store: false` (o `headers` da conexão) — com um comentário que aponta os
  arquivos e a versão; e criar `tests/http/contract/test_open_webui.py` (contracts/open-webui.md, verificações 1–2):
  o pedido da fixture com `ANA_TOKEN` → 200 SSE com `delta.reasoning_content` antes do primeiro `delta.content`, nenhuma
  linha de raciocínio depois dele, `[DONE]`, nenhum id de conversa; `GET /v1/models` com `ANA_TOKEN` e com `BIA_TOKEN`
  (grupo `chefia`) → listas diferentes, a de `BIA_TOKEN` com `chefia` e a de `ANA_TOKEN` sem (US8 cen. 1–2); a fixture
  com `tools` (modo nativo) → 400 `widening_field`; com conteúdo multimodal (lista de partes) → 400 com `param:
  "messages"`
- [X] T070 [US8] Em `src/ai_core/http/domain/chat_request.py`: `STORE_HEADER: Final = "x-ai-core-store"`,
  `parse_store(value: str | None, conversation_id: str | None) -> bool` (sem diferenciar maiúsculas; `false` com id →
  `store_conflict`; outro valor → `invalid_header`), `ChatRequest.store: bool = True` e `parse(body, *, store_header:
  str | None = None)`; em `src/ai_core/http/domain/native_request.py`, `parse_native(body, *, store_header=None)` com a
  mesma regra — faz T067 passar
- [X] T071 [US8] Em `src/ai_core/http/service.py`, pedido com `store=False`: `_open` não cria conversa (um `_Turn` sem
  conversa) e `_record` não grava; `opening_chunk` e `completion` saem sem `conversation_id`; `CompletionResult.
  conversation_id: str | None`. Em `src/ai_core/http/adapters/chat.py`, as duas rotas leem
  `request.headers.get(STORE_HEADER)` e o passam ao parser; `X-Conversation-Id` só quando há conversa (depende de T070;
  faz T068 passar)
- [X] T072 [US8] Fazer T069 passar: o que divergir do contrato (campo tolerado que hoje recusa, ordem do raciocínio) se
  corrige em `domain/`; sem código novo se já passar

**Checkpoint**: o pedido do Open WebUI v0.12 recebe streaming com o progresso visível; nenhuma conversa duplicada

---

## Phase 19: Polish da Fase 7

- [X] T073 Toque declarado na 011: em `src/ai_core/bootstrap/settings.py`, `max_executions` (`AI_CORE_MAX_EXECUTIONS`,
  1–64), `queue_size` (`AI_CORE_QUEUE_SIZE`, 0–1000) e `queue_wait_ms` (`AI_CORE_QUEUE_WAIT_MS`, 1–600 000), com os
  defaults provisórios 2, 8 e 60 000 e erro que nomeia a variável (`_within`); em `src/ai_core/bootstrap/wiring.py`
  (`_api`), `create_app(..., admission=AdmissionLimits(...))`; em `tests/bootstrap/unit/test_settings.py`, as três
  variáveis (default, valor lido, fora da faixa nomeando a variável); em
  `tests/bootstrap/integration/test_platform_test_profile.py`, com `AI_CORE_MAX_EXECUTIONS=1` e `AI_CORE_QUEUE_SIZE=0`
  e o provider `ollama` trocado por um que segura a geração num `asyncio.Event`, o segundo pedido simultâneo recebe
  503 `overloaded` com `Retry-After`; e a tabela de variáveis em `specs/011-core-bootstrap/contracts/configuration.md`
- [X] T074 Medir no hardware alvo (R36): `ai-core serve` no perfil `memory` com o Ollama local (`qwen3:1.7b`) e o
  Assistant `geral` (ou o `scouting`, se o índice estiver de pé), 1, 2 e 4 conversas simultâneas em streaming, latência
  até o primeiro token e total (p50); preencher a tabela da seção "Fase 7" de
  `specs/008-core-http-api/quickstart.md`, escolher os defaults (manter 2 / 8 / 60 s ou trocar, dizendo por quê na R36
  de `specs/008-core-http-api/research.md`) e alinhar `settings.py` e `contracts/admission.md` — *feita com OpenRouter
  por decisão do mantenedor (2026-10-13); os defaults seguem provisórios até a medição com o Ollama*
- [X] T075 Rodar a seção "Fase 7" de `specs/008-core-http-api/quickstart.md` (raciocínio no stream, fila com três
  pedidos, pedido efêmero) e corrigir divergências
- [X] T076 [P] Documentação: seção "Código" de `CLAUDE.md` (Fase 7 da 008: fila, progresso como raciocínio, pedido
  efêmero; a interface na passada da 002), a linha da 008 em `specs/README.md` e a da 011 (variáveis da fila), e
`docs/roadmap.md` (Fase 7 em andamento: a API pronta; fecha com a passada de encaixe da 002 — Open WebUI e Keycloak)
- [X] T077 Verificação completa a partir de `ai-core/`: `uv run pytest` (com e sem `AI_CORE_TEST_POSTGRES_DSN`), `uv run
  mypy`, `uv run ruff check packages`, `uv run ruff format --check packages`, `uv run lint-imports`
- [X] T078 Com aprovação do mantenedor: commit e push no `agentic-app`; core `0.4.0` (contratos inalterados em `0.1.2`,
  `ai-generic` 0.1.0) e a tag `v0.4.0`, que a passada de encaixe da 002 usa como `CORE_REF`; conferir a CI do core

---

## Fase 9 (2026-10-14): superfície de administração (research R43–R49)

**Escopo**: US9. Caminhos relativos a `ai-core/packages/core/`. Nada em `ai_core/bootstrap/` (passada da 011).

## Phase 20: User Story 9 — Administração pela superfície de administração (Priority: P2)

### Tests for User Story 9

- [X] T084 [P] [US9] `tests/http/unit/test_admin_assistants.py`, `test_admin_usage.py`, `test_admin_accounts.py`,
  `test_admin_observability.py`: corpos válidos e inválidos de [contracts/admin-api.md](contracts/admin-api.md) (campo
  desconhecido → `invalid_field` com `param`; `version` obrigatória onde o contrato pede; dinheiro como string decimal;
  `acknowledged` obrigatório para ligar a captura)
- [X] T085 [P] [US9] `tests/http/contract/test_admin_api.py` (marca `us9`): para cada rota do contrato, admin por token da
  console e por chave → sucesso; não admin → `404` idêntico ao de rota inexistente (corpo e cabeçalhos); token do chat
  → `401`; `409` (`version_conflict` com `current_version`, `installation_defined`, `master_key_missing`,
  `protected_group`, `google_not_configured`) e `422` com `param`; `Cache-Control: no-store`; varredura de segredos em
  todas as respostas (SC-009); a senha temporária só em `POST /users` e `POST /users/{u}/password`

### Implementation for User Story 9

- [X] T086 [US9] `http/ports.py`: `AdminSeams` e `InstanceBranding` (dataclasses de injeção, só com tipos dos `api.py`
  da 003, 006, 007, 009 e 012)
- [X] T087 [P] [US9] `http/domain/admin_assistants.py`, `admin_usage.py`, `admin_accounts.py`,
  `admin_observability.py` para T084
- [X] T088 [US9] `http/domain/errors.py`: os mapeamentos de R46
- [X] T089 [US9] `http/adapters/admin.py`: o router de R43 com todas as rotas do contrato; `GET /me` com `instance`
  (R48); `POST /assistants/{name}/models/check` pelo `ModelRouting.check` (R47); `mcp_routes.global_mcp_router` montado
  também em `/admin/v1`; `authenticated(request, surface="admin")` e `SCHEMES_OF_SURFACE` da 003
- [X] T090 [US9] `http/adapters/app.py`: `create_app(..., admin_seams=None, instance=None)` inclui o router quando há
  seams; `http/adapters/auth.py` usa `SCHEMES_OF_SURFACE`
- [X] T091 [US9] Rodar T084–T085 e a suíte inteira da 008 até verde

## Phase 21: Polish da Fase 9

- [X] T092 [P] Spec 008: Module Boundary com 006 e 012 nos seams consumidos; `specs/README.md` (status da 008 na Fase 9)
- [X] T093 Rodar `uv run pytest`, `mypy`, `ruff check packages`, `lint-imports`

## Dependencies & Execution Order

**Fase 7**: US6 — T058 ∥ T059 ∥ T060 (testes puros), depois T061 → T062 → T063 (T063 usa as linhas de T061); T064 ∥
com eles; T065 depois de T062 e T063 (faz T064 passar); T066 depois de T065. US8 — T067 ∥ T068 ∥ T069, depois T070 →
T071 → T072; `http/service.py` é tocado por T065 e depois por T071, e `http/domain/chat_request.py` só por T070; T069
depende de T063 (raciocínio no stream). Polish: T073 depois de T066; T074 depois de T073; T075 e T077 depois de tudo;
T076 em paralelo; T078 por último.

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

## Passada de 2026-10-13: timeline de status no Open WebUI (FR-005a, US6 cen. 5; research R42; [ADR-028](../../docs/adr/ADR-028-o-motor-publica-o-desfecho-de-cada-etapa.md))

- [X] T079 [US6] `domain/chat_request.py`: `PROGRESS_HEADER`, `parse_progress` e `ChatRequest.progress`; `parse` e
  `parse_native` leem o cabeçalho, e `adapters/chat.py` o repassa nas duas entradas
- [X] T080 [US6] `domain/timeline.py` (puro): `Status`, `Timeline` e a formatação pt-BR; `domain/openai_chunks.py`:
  `status_chunk`, `progress_of` e `queue_progress`
- [X] T081 [US6] `service.py` (`ChatService.stream`): no modo `status`, fila, início e desfecho de etapa e fim pela
  `Timeline`, com o tempo do `Clock`; o modo `reasoning` sem mudança
- [X] T082 [P] [US6] Testes: `tests/http/unit/test_timeline.py`, `test_chat_request.py` (o cabeçalho),
  `test_openai_chunks.py` (`status_chunk`), `tests/http/contract/test_admission.py` (fila no modo `status`),
  `tests/http/contract/test_open_webui.py` (o fixture do v0.12 com o cabeçalho, sem ele, 400 nas duas entradas, a
  requisição nativa) e, na 011, `tests/bootstrap/integration/test_platform_rag_first.py` (a timeline com o motor real)
- [X] T083 Passada de encaixe da 002 (`agentic-deploy`): a conexão manda `x-ai-core-progress: status`, `CORE_REF` na
  tag nova; conferir no navegador (conferido pelo `scripts/check-webui.py`, que lê o `statusHistory` gravado)

---

## Passada de 2026-10-20: identidade Axon — US10 ([ADR-037](../../docs/adr/ADR-037-a-plataforma-se-chama-axon.md), [ADR-038](../../docs/adr/ADR-038-marca-da-plataforma-e-marca-da-instalacao.md); research R50–R55)

**Goal**: cabeçalhos `x-axon-store`/`x-axon-progress`, extensão `x_axon`, OpenAPI "Axon"; os cabeçalhos antigos
recebem 400 que cita o novo; `me.instance.custom`; suítes verdes.

**Independent Test**: [quickstart.md, "Fase 9, incremento 9.5"](quickstart.md) — `-m us10`, a suíte de `http/` e a
integração do `me`; à mão, o título e o 400 do cabeçalho antigo.

### Tests (antes das T098–T101)

- [X] T094 [US10] `axon-ai/pyproject.toml`: a descrição da marca `us10` (já usada pela 003 US10) ganha `; 008 US10 — identidade Axon (cabeçalhos, extensão, OpenAPI e instance.custom)`
- [X] T095 [P] [US10] `axon-ai/packages/core/tests/http/unit/test_chat_request.py` (R55): `reject_legacy_headers` com
  `["x-ai-core-store"]`, `["X-AI-Core-Progress"]` e `["x-axon-store", "x-ai-core-store"]` levanta `ChatRequestInvalid`
  com `field` = o antigo (em minúsculas), `code == "invalid_header"` e o novo na mensagem; com `["x-axon-store",
  "content-type"]` não levanta; `STORE_HEADER == "x-axon-store"` e `PROGRESS_HEADER == "x-axon-progress"`
- [X] T096 [P] [US10] `axon-ai/packages/core/tests/http/contract/test_legacy_headers.py` (R55), marca `us10`, com o
  `http_testkit` da suíte: `/v1/chat/completions` e `/v1/chat` com `x-ai-core-store: false`, com `x-ai-core-progress:
  status` e com o antigo e o novo juntos → 400, `error.code == "invalid_header"`, `error.param` = o antigo, a mensagem
  cita o novo, e nenhuma chamada de modelo (cen. 3); com só `x-axon-store: false` → 200 sem conversa (cen. 1);
  `GET /openapi.json` → `info.title == "Axon"` (cen. 5)
- [X] T097 [P] [US10] `me` (R55, cen. 6): em `axon-ai/packages/core/tests/http/contract/test_admin_api.py`, o
  `InstanceBranding(name="Axon", logo_url="/oauth2/assets/logo", custom=True)` do ambiente e o `me` com `custom: true`, e
  um caso com `InstanceBranding()` → `{"name": "Axon", "logo_url": None, "custom": False}`; em
  `axon-ai/packages/core/tests/bootstrap/integration/test_platform_identity_admin.py`, o `me` sem marca própria com
  `"custom": False`, e um caso com `AXON_DISPLAY_NAME` próprio → `custom: True`. Rodar T095–T097 e ver falhar

### Implementation

- [X] T098 [US10] `axon-ai/packages/core/src/axon_ai/http/domain/chat_request.py` (R50, R51): `STORE_HEADER = "x-axon-store"`,
  `PROGRESS_HEADER = "x-axon-progress"`, as docstrings, `LEGACY_HEADERS` e `reject_legacy_headers(names: Iterable[str])`;
  `domain/errors.py` e `domain/openai_chunks.py`: `EXTRA = "x_axon"` e a docstring
- [X] T099 [US10] `axon-ai/packages/core/src/axon_ai/http/adapters/chat.py` (R51): `reject_legacy_headers(request.headers.keys())`
  nas duas rotas, depois de `authenticated(...)` e antes do parse; `adapters/app.py` (R52): `title="Axon"`
- [X] T100 [US10] `axon-ai/packages/core/src/axon_ai/http/ports.py` (R53): `InstanceBranding(name: str = "Axon", logo_url:
  str | None = None, custom: bool = False)`; `http/adapters/admin.py`: `"instance": {"name", "logo_url", "custom"}`
- [X] T101 [US10] `axon-ai/packages/core/src/axon_ai/bootstrap/wiring.py::_instance` (R53): `custom=settings.display_name
  != DEFAULT_DISPLAY_NAME or logo is not None`, com `DEFAULT_DISPLAY_NAME` de `axon_ai.bootstrap.settings`

### Consumidores (R54)

- [X] T102 [US10] Testes, por troca de texto nos arquivos de `git grep -lE 'x-ai-core|x_ai_core' --
  axon-ai/packages/core/tests` menos os da T095 e T096 (`x-ai-core-store` → `x-axon-store`, `x-ai-core-progress` →
  `x-axon-progress`, `x_ai_core` → `x_axon`), inclusive a fixture `tests/http/open_webui_v0_12.py`
- [X] T103 [P] [US10] `specs/README.md`: a linha da 008 com os nomes novos e a US10

### Integration e verificação

- [X] T104 [US10] Suítes (a partir de `axon-ai/`): `uv run pytest && uv run mypy && uv run ruff check packages && uv run
  ruff format --check packages && uv run lint-imports`, com e sem `AXON_TEST_POSTGRES_DSN`; a console (`npm test` e
  `npm run e2e`, que lê o `me`)
- [X] T105 [US10] Quickstart da US10 à mão (título e 400 do cabeçalho antigo com `serve`) e resíduos (SC-010):
  `git grep -nE "x-ai-core|x_ai_core"` fora do histórico, de `contracts/installation.md` e do `CLAUDE.md` só nos testes e
  textos da recusa; nenhuma palavra `agentic` removida (`--word-diff`)
- [X] T106 [P] [US10] `docs/roadmap.md` (andamento do 9.5: 008 feita)

### Dependencies (US10)

T094 → T095 ∥ T096 ∥ T097 (veem falhar) → T098 → T099 → T100 → T101 → T102 → T104 → T105; T103 e T106 em paralelo com a
T104.

### Notas da execução (US10)

- A marca `us10` já existia (003 US10); a 008 entrou na mesma descrição, como fazem as outras marcas compartilhadas.
- T095–T097 falharam como esperado antes da T098 (erro de coleta no domínio, `custom` inexistente em `InstanceBranding`).
- O cálculo de `custom` ganhou um teste de unidade na 011 (`tests/bootstrap/unit/test_instance_branding.py`): nome
  padrão, `AXON_DISPLAY_NAME=Axon` explícito, nome próprio, logotipo servido e logotipo sem identidade (não servido, não
  conta).
- No exemplo do `me` em `contracts/admin-api.md`, o nome de instalação é neutro ("Instituto Exemplo"), por causa do
  princípio I.
- Suítes: workspace 3150 passed, 168 skipped; com `AXON_TEST_POSTGRES_DSN`, 3307 passed, 11 skipped; mypy sem erro;
  ruff limpo; import-linter 69 kept; console 67 testes e e2e 39 passed, 4 skipped. À mão, com `serve`: `/openapi.json`
  com o título `Axon`; `x-ai-core-store: false` → 400 `invalid_header`, `param: "x-ai-core-store"`, "use 'x-axon-store'".

---

## Passada de 2026-10-21: chaves rotacionáveis e `auth` na administração — US11 ([ADR-040](../../docs/adr/ADR-040-rotacao-de-chaves-e-acesso-sobreponivel.md); research R56–R59)

**Goal**: `POST /admin/v1/keys/{key_id}/rotate` (chave em claro uma vez; 409 `key_revoked`), `rotated_at` nas duas
superfícies, `PUT /admin/v1/assistants/{name}/auth` e o descarte de `auth`, a visão com `yaml.auth`/`effective.auth`;
nada novo para o seletor; mypy volta a fechar.

**Independent Test**: [quickstart.md, "Fase 9 (2026-10-21)"](quickstart.md).

### Tests (antes das T111–T114)

- [X] T107 [US11] `axon-ai/pyproject.toml`: a descrição da marca `us11` passa a citar também "008 US11 — chaves
  rotacionáveis e auth na administração"
- [X] T108 [P] [US11] `axon-ai/packages/core/tests/http/unit/test_admin_assistants.py` (R58): `auth_body` aceita
  `{"schemes", "allow", "version"}` e devolve `AuthOverride` e a versão; campo desconhecido, `schemes`/`allow` que não são
  lista de textos → `AdminInvalid` com o campo; `auth_json` ordena `schemes` e mantém a ordem de `allow`; `view_json` traz
  `yaml.auth` e `effective.auth`; `payload_json(AuthOverride)` = `auth_json`. `tests/http/unit/test_errors.py` (R56):
  `key_revoked("…")` é 409, `code="key_revoked"`, `param="key_id"`; `test_private` (ou onde `key_json` é testado):
  `rotated_at` `null` e ISO
- [X] T109 [P] [US11] `axon-ai/packages/core/tests/http/contract/test_admin_keys_auth.py` (novo, marca `us11`; R56–R59),
  sobre o `_kit` de `test_admin_api.py` (importado ou fatorado em `conftest` da pasta) com o Assistant `geral` ganhando
  `overrides: [models, mcp, auth]` e `auth: {schemes: [oidc], allow: ["group:equipe"]}`: cen. 1 (rotação 200 com `key`
  `axn_<mesmo key_id>_…`, `rotated_at`; `GET /keys` sem a chave; antiga → 401 e nova → 200 em
  `/private/v1/health`); cen. 2 (revogada → 409 `key_revoked` `param` `key_id`; inexistente → 404; corpo
  `{"x": 1}` → 422 `param` `x`); cen. 3 (`svc:Relatorios` → 422 `subject`; grupo `operadores` → 422 `groups`, na
  administração e em `/private/v1/admin/keys`); cen. 4 (`PUT …/auth` com versão `null` → 200 e `effective.auth`;
  versão errada → 409 `version_conflict`; `allow: ["*"]` em privado → 422 `auth.allow`; `schemes: []` → 422
  `auth.schemes`; `fixo` → 422 `auth`); cen. 5 (`DELETE …/overrides/auth?version=1` volta ao YAML; histórico com
  `payload` `{"schemes", "allow"}`); cen. 6 (`fixo` com `yaml.auth == effective.auth`); cen. 7 coberto pela tabela (T110)
- [X] T110 [P] [US11] `axon-ai/packages/core/tests/http/contract/test_admin_api.py`: `("POST",
  "/keys/00000000000000b2/rotate", None)`, `("PUT", "/assistants/geral/auth", {"schemes": ["oidc"], "allow":
  ["group:equipe"], "version": None})` e `("DELETE", "/assistants/geral/overrides/auth?version=1", None)` na tabela de
  rotas (404 para não admin, 401 para o token do chat); `test_chaves_pela_administracao` confere `rotated_at` e a
  rotação na varredura de segredo (a chave em claro nova entra em `SECRETS` do cenário). Rodar T108–T110 e ver falhar

### Implementation

- [X] T111 [US11] `axon-ai/packages/core/src/axon_ai/http/domain/private.py` (R57): `key_json` com `"rotated_at":
  info.rotated_at.isoformat() if info.rotated_at is not None else None`
- [X] T112 [US11] `axon-ai/packages/core/src/axon_ai/http/domain/errors.py` (R56): `key_revoked(message: str) ->
  ErrorResponse` = `_conflict("key_revoked", message, param="key_id")`
- [X] T113 [US11] `axon-ai/packages/core/src/axon_ai/http/domain/admin_assistants.py` (R58): `auth_json`, `auth_body`
  (`only(body, ("schemes", "allow", "version"))`, `texts` para as duas listas, `version_of(body, nullable=True)`),
  `payload_json(payload: OverridePayload | None)` com o ramo de `AuthOverride`, `view_json` com `"auth"` em `yaml` e
  `effective`
- [X] T114 [US11] `axon-ai/packages/core/src/axon_ai/http/adapters/admin.py` (R56, R58): `_SECTIONS` com `"auth"`;
  `@route("PUT", "/assistants/{name}/auth")` → `seams.assistants.override_auth`; `@route("POST",
  "/keys/{key_id}/rotate")`: corpo lido só se houver bytes, `only(body, ())`; `request.app.state.keys.rotate(actor=…,
  key_id=…)`; `Conflict` → `raise ApiError(key_revoked(str(error)))`; resposta `key_json(info) | {"key": plaintext}`.
  Rodar T108–T110: verde

### Integration e verificação

- [X] T115 Suítes (a partir de `axon-ai/`): `uv run pytest && uv run mypy && uv run ruff check packages && uv run ruff
  format --check packages && uv run lint-imports` (o mypy volta a zero); conformidade Postgres com
  `AXON_TEST_POSTGRES_DSN`
- [X] T116 [P] `specs/README.md` (linha da 008 com a US11) e o quickstart da US11 à mão com `axon serve` (rotação e `PUT
  …/auth` por `curl` com chave de admin)

### Dependencies (US11)

T107 → T108 ∥ T109 ∥ T110 (veem falhar) → T111 → T112 → T113 → T114 → T115; T116 depois da T114.

### Notas da execução (US11)

- Os casos da US11 ficaram em `tests/http/contract/test_admin_api.py` (seção própria, marca `us11`), não num arquivo
  novo: o `_kit` mora nesse módulo, e `contract/` não está no `pythonpath`. O `_kit` ganhou `extra_assistants`.
- A T108 previa um teste de unidade de `key_json`; `rotated_at` ficou coberto pelos casos de contrato (listagem e
  rotação), sem arquivo de unidade novo.
- Na superfície privada, a recusa do grupo de administração e do nome de sistema sai pelo envelope dela (400
  `invalid_request` com `param`, conferido), não pelo 422 da administração; o teste fixa o 400 e o `param`.
- T108–T110 falharam na coleta antes da T111 (`auth_body`, `auth_json` e `key_revoked` inexistentes).
- Suítes: workspace 3290 passed, 192 skipped; com `AXON_TEST_POSTGRES_DSN`, 3471 passed, 11 skipped; **mypy sem erro**
  (os dois erros que a passada da 003 deixou em `payload_json` fecharam); ruff limpo; import-linter 69 kept.
- À mão (`persistent`, `axon serve`, chave de admin da CLI): rotação pela administração com o mesmo `key_id`; a antiga
  401 e a nova 200 em `/private/v1/health`; revogada → 409 `key_revoked` `param` `key_id`; `PUT …/auth` com o efetivo e
  o YAML na visão; `Cache-Control: no-store`.


---

## Passada de 2026-10-22: imagens na API ([ADR-044](../../docs/adr/ADR-044-imagens-na-conversa.md); research R60)

**Goal**: imagem na entrada, na resposta, no histórico recebido e na conversa guardada; teto do corpo.

**Independent Test**: `tests/http/contract/test_http_images.py`, `tests/http/unit/test_http_images_domain.py` e a
conformidade do `ConversationStore` com imagens, em memória e no Postgres.

- [X] T117 Verificação do Open WebUI v0.12 (stub, Playwright): renderização, histórico intacto, formato do anexo e as
  telas de 400 e 413 — na clarificação de 2026-10-22
- [X] T118 `domain/images.py`; `parse_messages` com partes; `RequestTooLarge` e o teto no `json_body`; `image_limits` no
  `create_app` (R60)
- [X] T119 `ChatService`: `vision_unsupported`, imagens retidas e emitidas depois do último token, candidatas lidas do
  banco; `x_axon.attachments`; conteúdo da resposta sem streaming
- [X] T120 `StoredAttachment`, `exchange` com bytes, porta `append(files=)`/`attachment`, memória, Postgres e
  `002_attachments.sql`; metadados na leitura e `GET /v1/conversations/{id}/attachments/{attachment_id}`
- [X] T121 `vision` na sobreposição de `models` (administração) e no Assistant de usuário
- [X] T122 [P] Testes: entrega em streaming e sem, conversa guardada (marcas, metadados, bytes, 404 alheio), turno
  seguinte, imagem do usuário, `vision_unsupported`, 413, histórico do Open WebUI; validação da pergunta; conformidade
  do armazenamento com cascata e expiração; corpos de administração e de Assistant de usuário

---

## Passada de 2026-10-28: gráficos na resposta ([ADR-052](../../docs/adr/ADR-052-graficos-na-conversa.md); research R62)

**Goal**: o gráfico do `FinalEvent` chega ao usuário como tabela em todo cliente e, no Open WebUI, como ECharts
interativo pelo evento `embeds`.

**Independent Test**: `tests/http/unit/test_charts_domain.py` e `tests/http/contract/test_http_charts.py`.

- [X] T123 `http/domain/charts.py`: tabela, opção do ECharts por tipo, página sem script inline, evento `embeds`, JSON
  de `x_axon.charts` (R62)
- [X] T124 `http/adapters/static/`: ECharts 6.1.0 e locale pt-BR vendorizados (com `LICENSE` e `NOTICE`) e o
  desenhista `axon-chart.js`; `static.py` com `ChartAssets` e as rotas `/static/echarts/<versão>/<arquivo>` e
  `/static/charts/<impressão>/axon-chart.js`
- [X] T125 `x-axon-charts` (`parse_charts`, nas duas entradas); `answer_tail` com a tabela antes das imagens; o
  `embeds` no streaming; a tabela no `content` sem streaming e na conversa gravada; `charts_base_url` em `create_app`
- [X] T126 [P] Testes: domínio (tabela e escape, rosca com "Outros", união das categorias, zoom, cinco séries ou
  mais, barras, página só com os scripts da plataforma, título hostil, `script_json`, evento único, JSON neutro) e
  contrato (com e sem o cabeçalho, sem endereço, sem gráfico, dois gráficos, sem streaming, 400, rota estática com a
  integridade da página, 404 do que não serve, conversa gravada com a tabela); fixture do Open WebUI com o cabeçalho
- [X] T127 Verificação no navegador (Playwright, iframe com o `sandbox` do Open WebUI): os cinco tipos nos dois temas,
  dica, zoom e altura, sem erro no console
