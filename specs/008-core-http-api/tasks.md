---

description: "Task list for 008 — chat completions compatível com OpenAI, Fase 1"
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

## Dependencies & Execution Order

### Phase Dependencies

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
