---

description: "Task list for 011 — bootstrap e composition root, Fases 1 e 2"
---

# Tasks: Bootstrap e composition root — boot, perfis e plataforma em memória

**Input**: Design documents from `/specs/011-core-bootstrap/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: incluídos. A ordem de boot e as políticas de falha são requisito observável (FR-002, FR-003) e só se
demonstram por teste; SC-002, SC-003 e SC-004 são critérios desta fase.

**Organization**: **US1**, **US2 no perfil em memória** e **US3** (Fase 1 do roadmap), mais o `ai-core serve` que a
US1 exige para existir ([research.md](research.md) R5, R9). **Não** entram: subcomandos contribuídos por módulo (US4,
Fase 2), saúde agregada (US5, Fase 2) e perfil persistente — nem `health.py`.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: user story da tarefa (US1, US2, US3)
- Todo caminho é relativo à raiz do repositório

## Path Conventions

- Código: `ai-core/packages/core/src/ai_core/bootstrap/`
- Testes: `ai-core/packages/core/tests/bootstrap/{unit,contract,integration}/`
- Configuração: `ai-core/packages/core/pyproject.toml` (dependência e ponto de entrada) e `ai-core/pyproject.toml`

---

## Phase 1: Setup (Shared Infrastructure)

- [X] T001 Criar `ai-core/packages/core/src/ai_core/bootstrap/__init__.py` com a docstring que declara a exceção do
  princípio XIII: esta é a única spec autorizada a importar `service.py` e `adapters/` de outros módulos
- [X] T002 Acrescentar `uvicorn>=0.53,<1` a `dependencies` e `[project.scripts] ai-core =
  "ai_core.bootstrap.cli:main"` em `ai-core/packages/core/pyproject.toml`; rodar
  `XDG_DATA_HOME=$HOME/.local/share uv sync` e conferir que o comando `ai-core` existe no ambiente
- [X] T003 Em `ai-core/pyproject.toml`, acrescentar `packages/core/tests/bootstrap` a
  `[tool.pytest.ini_options] pythonpath`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: as regras puras que o resto usa — configuração, perfis e a sequência

**⚠️ CRITICAL**: T004–T006 precedem a montagem da plataforma

- [X] T004 [US2] Implementar `ai-core/packages/core/src/ai_core/bootstrap/ports.py` e `settings.py` conforme
  [contracts/configuration.md](contracts/configuration.md): porta `ConfigSource` (`load() -> Settings`); `Settings`
  congelada com `profile`, `packs_file`, `assistants_file`, `ollama_base_url`, `trace_dir`, `host`, `port`,
  `shutdown_grace_seconds`, validando perfil desconhecido, porta fora de 1–65535 e prazo negativo com erro que nomeia
  o campo; adapters `EnvConfigSource` (variáveis `AI_CORE_*`, com os defaults da tabela) e `InMemoryConfigSource`
- [X] T005 [US2] Implementar `ai-core/packages/core/src/ai_core/bootstrap/profiles.py` conforme
  [contracts/profiles.md](contracts/profiles.md): a lista de portas exigidas como **dado** (`clock`, `trace`,
  `providers`, `pack_source`, `authenticator`, `request_ids`); `Profile` com uma fábrica por porta; `validate` que
  recusa perfil incompleto nomeando a porta; e os perfis `memory` (relógio do sistema, JSONL ou memória conforme
  `trace_dir`, provider do Ollama, entry points, autenticador anônimo, identificadores aleatórios) e `test` (relógio
  fixo, trace em memória, provider simulado, entry points, anônimo, identificadores sequenciais). Um **único** objeto
  de relógio atende as três portas de tempo (FR-008)
- [X] T006 [US1] Implementar `ai-core/packages/core/src/ai_core/bootstrap/lifecycle.py` conforme
  [contracts/boot-sequence.md](contracts/boot-sequence.md): `Stage` (nome, ação, `critical`), `StageOutcome`
  (`ok`/`degraded`/`failed` + motivo), `BootReport` (etapas na ordem, `ok`, `degraded`), o executor que roda a lista
  respeitando a política de cada etapa, o registro de recursos a liberar e o encerramento em **ordem inversa** —
  inclusive quando uma etapa crítica falha no meio. O executor **não** menciona nenhum módulo

---

## Phase 3: User Story 1 - Ordem de boot com falha fechada (Priority: P1) 🎯 MVP

**Goal**: o boot segue a ordem declarada, cada etapa falha conforme sua política, e o operador lê no relatório o que
falhou e por quê.

**Independent Test**: `uv run pytest packages/core/tests/bootstrap/contract` passa com etapas de teste, sem plataforma.

### Tests for User Story 1 ⚠️

- [X] T007 [P] [US1] `ai-core/packages/core/tests/bootstrap/contract/test_boot_sequence.py`: os sete itens de
  [contracts/boot-sequence.md](contracts/boot-sequence.md), com etapas de teste — ordem, interrupção em etapa
  crítica, continuidade em etapa degradável, relatório nomeando etapa e motivo, encerramento inverso, desfazimento
  inverso quando etapa crítica falha, e uma etapa nova rodando sem mudança no executor
- [X] T008 [P] [US1] `ai-core/packages/core/tests/bootstrap/unit/test_settings.py`: os itens 1 e 2 de
  [contracts/configuration.md](contracts/configuration.md) — defaults, e recusa de perfil desconhecido, porta fora da
  faixa e prazo negativo, cada um nomeando a variável

### Implementation for User Story 1

- [X] T009 [US1] `ai-core/packages/core/src/ai_core/bootstrap/grants.py`: leitura do `assistants.yaml` conforme
  [contracts/configuration.md](contracts/configuration.md) e `ConfiguredGrants`, que cumpre a porta `GrantResolver`
  da 008 — resolve `<assistant>[/<modelo>]`, compõe os packs pelo Pack Registry, monta a `ModelPolicy` da 006 e
  levanta `AssistantNotFound` para Assistant desconhecido ou cujo pack está indisponível
- [X] T010 [US1] `ai-core/packages/core/src/ai_core/bootstrap/wiring.py`: `platform(profile=…, config=…)` montando,
  nas cinco etapas da fase, `PackRuntime` (002), `TraceService` (009), `ModelRoutingService` (006), `ExecutionService`
  (005) e a aplicação HTTP (008), e devolvendo a `Platform` congelada com `settings`, `profile`, `packs`, `trace`,
  `engine`, `app`, `report` e `aclose()`. É o único lugar do projeto que importa `service.py` e `adapters/` de outros
  módulos
- [X] T011 [US1] `ai-core/packages/core/src/ai_core/bootstrap/cli.py`: raiz `ai-core` com o subcomando `serve` —
  monta a plataforma, imprime o relatório de boot, serve a app com o servidor ASGI e encerra no sinal de parada,
  respeitando o prazo configurado. Sai com código não zero quando o boot falha. O servidor entra por parâmetro
  (default: o real), para que a suíte exercite o comando sem abrir porta. **O relatório DEVE avisar, em destaque,
  quando a autenticação em uso é anônima** — o perfil `memory` é o que mais parece produção, e subir sem autenticação
  achando que está protegido é o erro caro que este aviso evita
- [X] T011b [P] [US1] `ai-core/packages/core/tests/bootstrap/contract/test_cli_serve.py`: o comando monta a
  plataforma e chama o servidor injetado com a app e o endereço configurados; imprime o relatório com as cinco
  etapas; **imprime o aviso de autenticação anônima**; sai com código não zero — e **sem** chamar o servidor — quando
  a configuração é inválida; e `--help` lista o subcomando

---

## Phase 4: User Story 2 - Perfil de adapters por fase (Priority: P1)

**Goal**: o operador escolhe o perfil por configuração; perfil incompleto é recusado antes do boot; trocar de perfil
não muda módulo nenhum.

**Independent Test**: `uv run pytest packages/core/tests/bootstrap/unit/test_profiles.py`.

- [X] T012 [P] [US2] `ai-core/packages/core/tests/bootstrap/unit/test_profiles.py`: os seis itens de
  [contracts/profiles.md](contracts/profiles.md) — cobertura das portas nos dois perfis, recusa de perfil incompleto
  nomeando a porta, recusa de perfil desconhecido, o **mesmo** objeto de relógio em motor, API e trace, provider
  simulado e trace de memória no `test`, e a escolha entre JSONL e memória no `memory` conforme `trace_dir`
- [X] T013 [P] [US2] `ai-core/packages/core/tests/bootstrap/unit/test_grants.py`: os itens 3 a 9 de
  [contracts/configuration.md](contracts/configuration.md) — YAML válido, recusas nomeando o campo, `flow` inexistente,
  id com e sem a parte do modelo, Assistant desconhecido e Assistant com pack indisponível

---

## Phase 5: User Story 3 - Plataforma inteira em memória (Priority: P1)

**Goal**: uma chamada monta a plataforma completa, sem rede e sem serviço externo, e uma conversa acontece por HTTP.

**Independent Test**: `uv run pytest packages/core/tests/bootstrap/integration`.

- [X] T014 [P] [US3] `ai-core/packages/core/tests/bootstrap/integration/test_platform_test_profile.py`:
  `platform(profile="test")` devolve a plataforma montada com o `ai-generic` carregado; uma conversa completa
  acontece por HTTP, com e sem streaming; o trace da requisição tem começo, chamada de modelo, validação e fim; o
  relógio fixo torna `created` e a data de referência verificáveis; e nenhum adapter que fale com rede é instanciado
- [X] T015 [P] [US3] `ai-core/packages/core/tests/bootstrap/integration/test_boot_degradado.py` (nome com
  `degradado`, que o [quickstart.md](quickstart.md) usa no filtro): com um pack em erro na configuração, o boot
  conclui, a etapa `packs` aparece degradada com o pack nomeado, e um Assistant que não depende dele atende
  normalmente (SC-004)
- [X] T016 [US3] Rodar `uv run pytest packages/core/tests/bootstrap` até T007, T008 e T012–T015 passarem, e
  `uv run mypy` e `uv run ruff check packages` limpos

**Checkpoint**: a Fase 1 do roadmap está completa — a conversa ponta a ponta existe, montada por configuração

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T017 Acrescentar a `ai-core/pyproject.toml` os contratos de import-linter de [research.md](research.md) R11 —
  nenhum módulo do core importa `ai_core.bootstrap`, e cada módulo continua proibido de importar `service.py` e
  `adapters/` dos outros — e rodar `uv run lint-imports` até todos aparecerem como `KEPT`
- [X] T018 [P] Registrar em [research.md](research.md) R7 por que as suítes de 005 e 008 **não** passam a usar o
  perfil `test`: fariam os testes desses módulos dependerem da composition root, inversão que o próprio design evita
  ("a 008 não importa a 011") e que enfraqueceria o isolamento protegido pelo SC-001 da 005. A montagem manual lá é
  deliberada; o perfil serve a esta spec e às suítes de packs externos
- [X] T019 Executar as seções de [quickstart.md](quickstart.md) (verificação completa e cenários 1–4) e corrigir
  divergências entre o resultado e o "Esperado"
- [X] T020 [P] Atualizar a seção "Código" de `CLAUDE.md` (o módulo `ai_core/bootstrap/` existe, com boot por etapas
  declaradas, perfis `memory` e `test`, resolvedor de grant a partir de `assistants.yaml` e o comando `ai-core
  serve`; saúde agregada e subcomandos de módulo continuam para a Fase 2), a linha da 011 em `specs/README.md`
  (status "Fase 1 implementada (US1, US2 memória, US3)") e a linha da Fase 1 em `docs/roadmap.md`, que passa a estar
  concluída

---

## Fase 2 (2026-09-30): US2 (persistente), US4 (CLI), US5 (saúde) e autenticação real (FR-015)

Decisões em [plan.md](plan.md) ("Fase 2") e [research.md](research.md) R11–R20. Caminhos relativos a
`ai-core/packages/core/`; `bootstrap/` = `src/ai_core/bootstrap/`.

## Phase 7: Foundational da Fase 2 — configuração e perfis

- [X] T021 [P] Estender `tests/bootstrap/unit/test_settings.py` (contracts/configuration.md, "Fase 2"): cada variável
  nova com default; `persistent` sem `AI_CORE_DATABASE_URL`, `AI_CORE_OIDC_ISSUER` sem `AI_CORE_OIDC_AUDIENCE`,
  `AI_CORE_DEV_API_KEY` fora do formato `aic_<16 hex>_<segredo>` e `AI_CORE_DEV_API_KEY` no `persistent` recusados
  nomeando a variável — e nenhuma mensagem nem `repr(Settings)` contém o valor de um segredo
- [X] T022 Implementar em `bootstrap/settings.py` as variáveis de R18, o perfil `persistent`, as validações do T021 e
  `repr` sem segredos
- [X] T023 [P] Estender `tests/bootstrap/unit/test_profiles.py` (contracts/profiles.md, "Fase 2"): os três perfis
  atendem as portas exigidas; as fábricas do `persistent` constroem o pool **fechado** e os adapters Postgres sem
  conectar; o `test` não instancia nada que fale com rede; as credenciais exportadas (`TEST_SUBJECT`,
  `TEST_OIDC_TOKEN`, `TEST_API_KEY`, `TEST_ADMIN_GROUP`) autenticam pelos adapters do perfil
- [X] T024 Implementar em `bootstrap/profiles.py` a lista nova de portas exigidas, fábricas que recebem a configuração e
  as partes já construídas, os três perfis da tabela de contracts/profiles.md, as credenciais do perfil `test` (claims
  válidas no instante do relógio fixo) e a fábrica `conversation_ids` (R19); remover `ANONYMOUS_WARNING` e
  `anonymous_auth`

## Phase 8: User Story 2 — perfil persistente e autenticação real (Priority: P1)

**Independent Test**: `AI_CORE_TEST_POSTGRES_DSN=… uv run pytest packages/core/tests/bootstrap -k persistent`.

- [X] T025 [P] [US2] Criar `tests/bootstrap/integration/test_persistent_profile.py` (pulado sem
  `AI_CORE_TEST_POSTGRES_DSN`): o boot migra `assistants` e `http` e conclui; uma chave emitida por `AccessService`
  sobre o Postgres autentica numa plataforma **nova** sobre o mesmo banco; uma conversa aberta numa plataforma continua
  noutra; um Assistant de usuário criado sobrevive; com a URL apontando para uma porta fechada, o boot falha na etapa
  `adapters` nomeando `database` e o adapter, e nem o relatório nem a mensagem contêm a URL (US2 cen. 2) — usando
  `httpx.AsyncClient` com o ciclo de vida da app no laço do teste
- [X] T026 [P] [US2] Atualizar as suítes de `tests/bootstrap/` para a autenticação real: `test_platform_test_profile.py`
  e `test_boot_degradado.py` mandam `Authorization` com as credenciais exportadas; sem credencial é 401 (US2 cen. 5);
  `test_cli_serve.py` troca o aviso de anônimo pelo aviso de "sem chave de desenvolvimento nem OIDC" no `memory`
- [X] T027 [US2] Implementar em `bootstrap/wiring.py`: os armazenamentos e o verificador OIDC vindos do perfil;
  `AccessService` com eles e o `admin_group` do `assistants.yaml`; a chave de desenvolvimento semeada no `memory`;
  na etapa `adapters` do `persistent`, conferência de conexão e `migrate` de `assistants` e `http` num pool temporário
  (falha nomeia porta e adapter, sem a URL); o ciclo de vida da app — abrir o pool de serviço, agendar
  `ConversationService.expire` a cada `AI_CORE_CONVERSATION_EXPIRY_INTERVAL` segundos, cancelar e fechar no fim — e
  `conversation_retention` dos dias configurados; `Platform` com `assistants`, `access`, `routing` e `conversations`;
  e em `src/ai_core/http/adapters/app.py` o parâmetro opcional `lifespan` de `create_app` (toque declarado na 008, R14)
- [X] T028 [US2] Atualizar `bootstrap/cli.py` (`serve`): avisar em destaque quando o `memory` sobe sem chave de
  desenvolvimento nem OIDC; nenhum segredo em saída

## Phase 9: User Story 5 — saúde agregada (Priority: P2)

**Independent Test**: `uv run pytest packages/core/tests/bootstrap/unit/test_health.py`.

- [X] T029 [P] [US5] Criar `tests/bootstrap/unit/test_health.py` (contracts/health.md) com checagens falsas: provider
  fora do ar → `degraded` nomeando o modelo e os demais saudáveis (US5 cen. 1); tudo bem → `ok` (cen. 2); banco fora →
  `down` (cen. 3); checagem que passa de 3 s vira item não saudável; segunda consulta em 15 s não repete checagens; e
  atualizar `tests/http/contract/test_private_routes.py` — 503 só em `down`, 200 em `degraded`
- [X] T030 [US5] Implementar `bootstrap/health.py` (`PlatformHealth`: itens `database`, `boot:*`, `pack:*`,
  `assistant:*`, `model:*`, timeout de 3 s por item, cache de 15 s) e, na 008 (toque declarado),
  `HealthItem.critical`, `HealthReport.status` (`ok`/`degraded`/`down`) em `src/ai_core/http/domain/records.py`, o JSON
  com `critical` em `domain/private.py` e a rota de saúde em `adapters/private.py` respondendo 503 só em `down`

## Phase 10: User Story 4 — linha de comando única (Priority: P2)

**Independent Test**: `uv run pytest packages/core/tests/bootstrap/contract/test_cli_commands.py`.

- [X] T031 [P] [US4] Criar `tests/bootstrap/contract/test_cli_commands.py` (contracts/cli.md): `--help` lista todos os
  subcomandos (US4 cen. 1); `packs check` com pack incompatível sai com 1 e com `packs.yaml` malformado com 2;
  `assistants validate` com Assistant inválido sai com 1 e com `assistants.yaml` malformado com 2 (US4 cen. 2 e
  Independent Test); `keys create` imprime a chave e avisa que o perfil não é persistente; `health` sai com 0/1/2;
  nenhum subcomando além de `serve` chama o servidor injetado
- [X] T032 [US4] Implementar em `bootstrap/cli.py` a raiz com a lista de registro dos subcomandos (R17), chamando as
  funções de `ai_core.packs.adapters.cli`, `ai_core.assistants.adapters.cli` e `bootstrap/health.py`; `packs` monta só
  configuração, adapters e packs; `keys` abre e fecha o armazenamento no próprio laço

## Phase 11: Polish da Fase 2

- [X] T033 Rodar a seção "Fase 2" do [quickstart.md](quickstart.md) e a verificação completa (`uv run pytest` com e sem
  `AI_CORE_TEST_POSTGRES_DSN`, `uv run mypy`, `uv run ruff check packages`, `uv run lint-imports`), incluindo o roteiro
  manual com `ai-core keys create` e `ai-core serve` no `persistent`
- [X] T034 [P] Atualizar `CLAUDE.md` ("Código"), a linha da 011 em `specs/README.md` e `docs/roadmap.md` (a Fase 2 fica
  concluída: 003 US1–US7, 002 US4, 008 US2–US5 e US7, 011 US2, US4, US5)

---

## Dependencies & Execution Order

### Phase Dependencies

**Fase 2**: T021 → T022; T023 → T024 (depois de T022) — bloqueiam as stories. US2: T025 ∥ T026, depois T027 → T028;
US5: T029 → T030 (depois de T027, que monta a plataforma com `routing` e `access`); US4: T031 → T032 (depois de T028 e
T030, mesmo `cli.py`). Polish por último.


- **Setup (Phase 1)**: T001 e T002 primeiro; T003 em paralelo
- **Foundational (Phase 2)**: T004 → T005; T006 em paralelo com os dois
- **US1 (Phase 3)**: depende de Setup + Foundational; T009 → T010 → T011
- **US2 (Phase 4)** e **US3 (Phase 5)**: dependem de T010
- **Polish (Phase 6)**: T017 depois de T010; T019 depois de T016; T018 e T020 em paralelo

### Parallel Opportunities

- T007 e T008 em paralelo; T012 e T013 em paralelo; T014 e T015 em paralelo
- T018 e T020 em paralelo com qualquer tarefa concluída

---

## Implementation Strategy

### MVP (US1, US2 e US3 — o escopo desta fase)

1. Phase 1 e 2: esqueleto, dependência, configuração, perfis e sequência
2. Phase 3: grant, montagem e comando
3. Phases 4 e 5: perfis e plataforma completa
4. **PARE e VALIDE**: quickstart — inclusive subir `ai-core serve` com Ollama de verdade e conversar por `curl`
5. Phase 6: fronteiras de import, limpeza das suítes, documentação

### Depois desta fase

- Fase 2: a 003 assume `assistants.yaml` e fornece autenticador e resolvedor reais; entram os subcomandos de módulo
  (US4), a saúde agregada (US5) e o perfil persistente
- Fase 3: etapa de registry MCP (007) e porta de checkpoint (005) entram na lista, sem mudar a sequência
