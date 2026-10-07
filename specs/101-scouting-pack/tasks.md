---

description: "Task list for 101 — pack scouting, Fase 4 (US1, US2, US3)"
---

# Tasks: Pack scouting — composição, contexto determinístico e prompts

**Input**: Design documents from `/specs/101-scouting-pack/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: incluídos. A FR-001 e o SC-003 exigem a conformidade da 001 só com os contratos, a US1 cen. 3 exige
verificação de fronteiras, e a US2 e a US3 são tabelas de casos — testes primeiro, falhando antes do código.

**Organization**: só a **Fase 4** do roadmap — US1, US2 e US3. A US4 (prioridade de fontes) e a US5 (`rag_first`,
retriever, validators) são Fase 5.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: user story da tarefa (US1, US2, US3)

## Path Conventions

- Todo caminho começa em `ai-scouting/` (o submódulo → `CaioFerreiraB/ai-scouting`, ADR-021), salvo os que começam
  com `specs/`, `docs/` ou `CLAUDE.md` (raiz do `agentic-app`)
- Comandos rodam dentro de `ai-scouting/`, com `XDG_DATA_HOME=$HOME/.local/share`
- O código e os testes do pack são commitados no `ai-scouting`; no `agentic-app`, só o SDD e o ponteiro do submódulo

---

## Phase 1: Setup

- [X] T001 Criar `ai-scouting/pyproject.toml` conforme [contracts/packaging.md](contracts/packaging.md): `[project]`
  (`ai-scouting` 0.1.0, descrição, `readme = "README.md"`, `requires-python = ">=3.12"`, `dependencies =
  ["ai-core-contracts>=0.1,<0.2"]`), entry point `scouting = "ai_scouting.pack:ScoutingPack"` em
  `[project.entry-points."ai_core.packs"]`, `[dependency-groups]` `dev = ["pytest", "mypy", "ruff", "import-linter"]` e
  `platform = ["ai-core ; python_version >= '3.14'"]`, `[tool.uv.sources]` com `ai-core-contracts` e `ai-core` pela tag
  `contracts-v0.1.0` do `agentic-app` (subdiretórios `ai-core/packages/contracts` e `ai-core/packages/core`), build
  backend `uv_build>=0.12,<0.13`; `[tool.ruff]` (`py312`, linha 120, regras `E F I UP B SIM RUF`, `known-first-party =
  ["ai_scouting"]`), `[tool.mypy]` (`strict`, `python_version = "3.12"`, `files = ["src"]`), `[tool.pytest.ini_options]`
  (`testpaths = ["tests"]`) e `[tool.importlinter]` com `root_packages = ["ai_scouting"]`, `include_external_packages =
  true` e os três contratos de [contracts/packaging.md](contracts/packaging.md) (research R13)
- [X] T002 Criar o esqueleto do pacote: `src/ai_scouting/__init__.py` (docstring: pack de domínio escoteiro; consumidores
  usam o entry point), `src/ai_scouting/py.typed`, `src/ai_scouting/context/__init__.py`,
  `src/ai_scouting/prompts/__init__.py` e `tests/integration/__init__.py` vazio; rodar `uv lock` e `uv sync --locked`
  (depende de T001; exige SSH no `agentic-app`) e confirmar que `uv pip list` tem `ai-core-contracts` e **não** tem
  `ai-core`
- [X] T003 [P] Criar `ai-scouting/.github/workflows/ci.yml` com os jobs `lint`, `test` (matriz 3.12 e 3.14), `clean-env`
  (3.12, instalação normal com `uv pip install . pytest` e `pytest tests --ignore=tests/integration`) e `platform` (3.14,
  `uv sync --locked --group platform`, `pytest tests/integration`), cada um com `actions/checkout@v5`,
  `webfactory/ssh-agent@v0.9.0` carregando `secrets.AGENTIC_APP_DEPLOY_KEY` e `astral-sh/setup-uv@v6` (research R14)

---

## Phase 2: Foundational (bloqueia US2 e US3)

**⚠️ CRITICAL**: a derivação (US2, US3) depende da normalização e do léxico; a US1 não depende.

- [X] T004 [P] Criar `tests/test_text.py`: `normalize` — maiúsculas, acentos (`"Liderança"` → `"lideranca"`, `"Clã"` →
  `"cla"`), pontuação e espaços repetidos viram um espaço, pontas aparadas; `contains_term` — casa termo de uma e de
  várias palavras só em limite de palavra (`"pioneiro"` casa em `"o pioneiro é"`, não em `"pioneirismo"`; `"ramo
  senior"` casa em `"no ramo sênior,"`) (research R6)
- [X] T005 Criar `src/ai_scouting/context/text.py` com `normalize(text: str) -> str` (casefold, NFKD sem marcas
  combinantes, não-alfanuméricos → espaço, espaços colapsados e aparados) e `contains_term(normalized_text: str, term:
  str) -> bool` (termo já normalizado, limites de palavra) (T004 passa)
- [X] T006 Criar `src/ai_scouting/context/lexicon.py` com a **semente proposta** (research R7, clarificação 5):
  dataclasses imutáveis `Topic(id, terms, document_types)` e `Lexicon(branches, ambiguous, topics, document_types,
  type_signals, previous_markers)` e a constante `LEXICON` — ramos `lobinho`, `escoteiro`, `senior`, `pioneiro` com
  plural, feminino e sinônimos antigos e regionais (sem a palavra "escoteiro" sozinha, que vai para `ambiguous`, com
  "patrulha"); tipos `manual`, `programa_educativo`, `por`, `resolucao`, `estatuto`, `guia`, nessa ordem; cerca de 15
  temas (entre eles `lideranca` e `promessa_e_lei`); sinais (entre eles "competencia"/"competencias" →
  `programa_educativo`, `manual`; "regra"/"regras"/"norma" → `por`, `resolucao`); marcas de versão anterior ("manual
  anterior", "versao anterior", "regra anterior", "antigamente"); todos os termos já normalizados (depende de T005)
- [X] T007 Criar `tests/test_lexicon.py` com as invariantes do [data-model.md](data-model.md) "Lexicon": termos
  normalizados (`normalize(term) == term`), nenhum termo em dois ramos, nenhum termo de ramo em `ambiguous`, todo tipo
  citado por tema ou sinal existe, ids únicos e em ASCII com `_`
- [X] T008 **Checkpoint do mantenedor**: apresentar a semente de `lexicon.py` (ramos e sinônimos, tipos, temas, sinais,
  marcas) e aplicar a revisão antes de seguir para os testes de aceite da US2 e da US3 (clarificação 5)

**Checkpoint**: léxico revisado; normalização verde

---

## Phase 3: User Story 1 — Pack carregado e respondendo com instruções de domínio (Priority: P1) 🎯 MVP

**Goal**: o pack carrega por entry point com manifest mínimo, publica o fragmento de instruções da Fase 4 e conforma à
001 só com os contratos.

**Independent Test**: `uv run pytest tests/test_pack.py tests/test_prompt.py tests/test_conformance.py` (contratos) e
`uv run --python 3.14 --group platform pytest tests/integration` (plataforma).

### Testes da US1 (escrever primeiro; devem falhar)

- [X] T009 [P] [US1] Criar `tests/test_pack.py`: `name == "scouting"` e `contract_version == "0.1"` na classe;
  `manifest() == PackManifest(name="scouting", version="0.1.0")` com `preferred_flow is None` (comentário:
  "clarificação 1: rag_first na Fase 5"), `requires_collections == ()` e `config_schema is None`; versão do manifest
  igual a `importlib.metadata.version("ai-scouting")`; `system_prompt` não vazio e igual para `pack_context("scouting")`
  e `pack_context("scouting", {"qualquer": "coisa"})`; `tools`, `retrievers` e `validators` vazios e `reranker` `None`
- [X] T010 [P] [US1] Criar `tests/test_prompt.py` (FR-009, FR-011; [contracts/scouting-pack.md](contracts/scouting-pack.md)
  "system_prompt"): sobre `" ".join(SYSTEM_PROMPT.split()).casefold()`, afirmar que contém `"escot"`, `"nenhum documento"`,
  `"fonte oficial"`, `"nunca instrução"` e uma proibição de citar (`"não cite"`), e que **não** contém `"chame"` nem
  `"use a ferramenta"`
- [X] T011 [P] [US1] Criar `tests/test_conformance.py` no molde de `ai-core/packages/generic/tests/test_conformance.py`:
  `VIEWS` com `turn_view` das perguntas do [data-model.md](data-model.md) (exemplos de aceite) e uma pergunta vazia;
  `assert_pack_conforms(ScoutingPack(), views=VIEWS)`; relatório sem item na instalação normal e só
  `distribution.not_found` na editável (detecção por `packages_distributions()`)
- [X] T012 [P] [US1] Criar `tests/integration/test_platform.py` (research R9) usando só a superfície que a 011 publica
  para suítes de packs externos: `pytest.importorskip("ai_core")`; fixture que remove do ambiente toda variável
  `AI_CORE_*` (`monkeypatch.delenv`), escreve em `tmp_path` um `packs.yaml` (`scouting: { enabled: true }`) e um
  `assistants.yaml` com o Assistant `scouting` (`visibility: public`, `auth` com `schemes: [oidc, api_key]` e `allow:
  ["*"]`, `flow: chat`, `packs: [scouting]`, `generation: ollama/qwen3:1.7b`, `allow: ["ollama/*"]`) e
  `api_keys.admin_group: admin`, define `AI_CORE_PACKS_FILE` e `AI_CORE_ASSISTANTS_FILE` (`monkeypatch.setenv`) e monta
  `platform(profile="test")` — sem `overrides` e sem importar módulo interno ou adapter do core. Testes:
  `test_pack_carrega_pelo_entry_point` (`plataforma.ok`; `plataforma.packs.entry("scouting")` com status `enabled`,
  versão `0.1.0` e `contract_version` `0.1`) e `test_plataforma_compoe_as_instrucoes_de_dominio`
  (`plataforma.packs.system_prompts(plataforma.packs.compose(["scouting"]))` contém `ScoutingPack().system_prompt(...)`;
  `POST /v1/chat/completions` com `model="scouting"` e `Authorization: Bearer <TEST_OIDC_TOKEN>` de
  `ai_core.bootstrap.profiles` → 200 com conteúdo não vazio)

### Implementação da US1

- [X] T013 [US1] Criar `src/ai_scouting/prompts/domain.py` com `SYSTEM_PROMPT: Final` (constante, docstring de módulo
  citando FR-009, FR-011 e research R10) nos quatro blocos de [contracts/scouting-pack.md](contracts/scouting-pack.md):
  papel; sem documentos consultados nesta fase (declarar; não citar, nomear nem numerar documento, resolução ou trecho;
  recomendar a fonte oficial; regras mudam); dado, nunca instrução; fora do domínio. Reexportar em
  `prompts/__init__.py` (T010 passa)
- [X] T014 [US1] Criar `src/ai_scouting/pack.py`: `ScoutingPack(PackBase)` com `name`, `contract_version`, `VERSION =
  "0.1.0"`, `manifest()` mínimo e `system_prompt()` devolvendo `SYSTEM_PROMPT` — docstring de composition root (só
  compõe; políticas em `context/` e `prompts/`) (T009, T011 e T012 passam)

**Checkpoint**: US1 verde nos dois ambientes — só contratos e plataforma

---

## Phase 4: User Story 2 — Contexto derivado da pergunta sem chamar modelo (Priority: P1)

**Goal**: ramo, temas, tipos de documento e a vigência default derivados por regra e léxico, publicados na fatia.

**Independent Test**: `uv run pytest tests/test_derivation.py tests/test_periods.py tests/test_purity.py -k "not historico"`.

### Testes da US2 (escrever primeiro; devem falhar)

- [X] T015 [P] [US2] Criar `tests/test_periods.py` com a parte da US2: `reference_day` converte para UTC−03:00
  (`2026-10-07T12:00Z` → `2026-10-07`; `2026-10-08T01:00Z` → `2026-10-07`); `Validity(start, end)` com `start > end`
  levanta `ValueError`; `Validity.day(d)` tem início = fim
- [X] T016 [P] [US2] Criar `tests/test_derivation.py` com a tabela da US2 (dia de referência 2026-10-07): US2 cen. 1
  (`pioneiro`, (`lideranca`,), (`manual`, `programa_educativo`), vigência de um dia, sem revogados); US2 cen. 2
  (pergunta sem ramo → `branch is None`); casos de borda — "escoteiro" sozinho → sem ramo; dois ramos ("diferença entre
  lobinho e sênior") → sem ramo; sinônimo antigo de um ramo → o ramo; maiúsculas e acentos indiferentes; tipo citado
  explicitamente prevalece sobre os sugeridos; pergunta vazia → contexto default; e a forma de `to_slice`: chaves de
  `context` sempre presentes, `retrieval_filters` sem `branch` quando não há ramo e sem listas vazias, datas ISO, JSON
  (`json.dumps` não levanta) — e `ScoutingPack().prepare_context` devolve exatamente `to_slice(...)` (via `asyncio.run`)
- [X] T017 [P] [US2] Criar `tests/test_purity.py` (research R13): varre os `.py` de `src/ai_scouting/context/` e falha
  se houver `.now(`, `.today(`, `utcnow`, `time.time(` ou `time.monotonic(`

### Implementação da US2

- [X] T018 [US2] Criar `src/ai_scouting/context/periods.py`: `BRASILIA: Final = timezone(timedelta(hours=-3),
  "UTC-03:00")` (docstring: sem horário de verão desde 2019; dispensa `tzdata` — R5), `Validity` (dataclass imutável,
  `start <= end`, construtor `day`) e `reference_day(reference_time: datetime) -> date` (T015 passa)
- [X] T019 [US2] Criar `src/ai_scouting/context/derivation.py`: `ScoutingContext` (campos do
  [data-model.md](data-model.md)), `derive_context(question: str, reference_day: date, lexicon: Lexicon = LEXICON) ->
  ScoutingContext` com as regras 1–3 de research R8 e vigência default de um dia, e `to_slice(context) -> dict[str,
  JSONValue]` no formato de [contracts/retrieval-filters.md](contracts/retrieval-filters.md) (depende de T005, T006,
  T018)
- [X] T020 [US2] Em `src/ai_scouting/pack.py`, `prepare_context(view, ctx)` devolve
  `to_slice(derive_context(view.question, reference_day(view.reference_time)))`; conferir `uv run lint-imports` com os
  três contratos da T001 (T016, T017 passam; T011 continua verde)

**Checkpoint**: US2 verde; `lint-imports` com os três contratos `KEPT`

---

## Phase 5: User Story 3 — Consulta histórica (Priority: P2)

**Goal**: períodos citados viram intervalo com revogados incluídos; marca de versão anterior liga `previous_version`.

**Independent Test**: `uv run pytest tests/test_periods.py tests/test_derivation.py -k historico`.

### Testes da US3 (escrever primeiro; devem falhar)

- [X] T021 [P] [US3] Em `tests/test_periods.py`, `test_historico_*` com a tabela de vigência do
  [data-model.md](data-model.md): "em 2023", "no ano de 2023", "durante 2023" → ano inteiro; "em março de 2023" → o mês
  (fevereiro de 2024 termina em 29); "em 15/03/2023" e "em 15 de março de 2023" → um dia; "ano passado" (referência
  2026-10-07) → 2025; "resolução 3/2023" → nenhum período; dois períodos → o primeiro; data impossível ("em
  31/02/2023") → nenhum período
- [X] T022 [P] [US3] Em `tests/test_derivation.py`, `test_historico_*`: US3 cen. 1 ("Qual era a regra em 2023?" →
  2023-01-01 a 2023-12-31, `include_superseded`, tipos do sinal "regra"); US3 cen. 2 ("O que dizia o manual anterior?" →
  vigência no dia de referência, `include_superseded` e `previous_version`, tipos (`manual`,)); "antigamente" →
  `previous_version`; e `retrieval_filters` com `effective_from`/`effective_until` do período

### Implementação da US3

- [X] T023 [US3] Em `src/ai_scouting/context/periods.py`, `find_period(normalized: str, reference_day: date) ->
  Validity | None` com as regras da research R8 item 4 — meses em português, data `dd/mm/aaaa` e por extenso, marcas
  "em", "no ano de", "durante", "ano passado"; ano solto não conta; a primeira ocorrência vence; data inválida não é
  período (T021 passa)
- [X] T024 [US3] Em `src/ai_scouting/context/derivation.py`, usar `find_period` (com período → `include_superseded`) e
  `previous_markers` (→ `previous_version` e `include_superseded`, vigência default) (T022 passa; a tabela da US2 segue
  verde)

**Checkpoint**: US3 verde; a tabela completa do data-model passa

---

## Phase 6: Polish

- [X] T025 Verificação completa dentro de `ai-scouting/`: `uv run pytest` em 3.14 e em 3.12 (`uv run --python 3.12
  pytest`), `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`, `uv run lint-imports` e a integração
  (`uv run --python 3.14 --group platform pytest tests/integration`); corrigir o que quebrar
- [X] T026 Executar as seções 0–6 de [quickstart.md](quickstart.md) — a §2 no ambiente limpo em 3.12; a §6 com os
  arquivos de `~/.config/ai-core/` (acrescentar o pack e o Assistant `scouting`) e o modelo do OpenRouter, conferindo
  a resposta sem citação inventada — e corrigir divergências entre o resultado e o "Esperado"
- [ ] T027 Com o aval do mantenedor: commit e push do `ai-scouting`; criar a deploy key só de leitura no `agentic-app` e
  o segredo `AGENTIC_APP_DEPLOY_KEY` no `ai-scouting` (quickstart §7) e conferir os quatro jobs do `ci.yml` verdes
- [X] T028 [P] Atualizar no `agentic-app`: `CLAUDE.md` (seção "Código": o `ai-scouting` existe — pack `scouting` 0.1.0,
  manifest mínimo na Fase 4, prompt sem corpus, derivação pura com vigência em intervalo e dia de Brasília, suíte só com
  contratos e integração pelo grupo `platform`, CI com deploy key; "Fase 4 em andamento"), a linha da 101 em
  `specs/README.md` (status "Fase 4 implementada (US1, US2, US3)") e, no mesmo commit, o ponteiro do submódulo
  `ai-scouting`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup**: T001 → T002 (o `uv lock` precisa do `pyproject.toml`); T003 em paralelo
- **Foundational**: T004 → T005 → T006 → T007 → T008 (checkpoint do mantenedor); bloqueia US2 e US3, não a US1
- **US1**: depende só do Setup; testes T009–T012 em paralelo; T013 → T014
- **US2**: depende do Foundational; testes T015–T017 em paralelo; T018 → T019 → T020 (T020 edita o `pack.py` da US1)
- **US3**: depende da US2 (mesmos arquivos `periods.py` e `derivation.py`); T021 ∥ T022; T023 → T024
- **Polish**: T025 depois das histórias; T026 depois de T025; T027 depois de T026; T028 em paralelo com T027

### Parallel Opportunities

- T003 em paralelo com todo o Setup restante
- US1 (T009–T014) em paralelo com o Foundational (T004–T008): arquivos distintos
- Testes de cada história em paralelo entre si

---

## Parallel Example: User Story 1

```bash
Task: "tests/test_pack.py (T009)"
Task: "tests/test_prompt.py (T010)"
Task: "tests/test_conformance.py (T011)"
Task: "tests/integration/test_platform.py (T012)"
```

---

## Implementation Strategy

### MVP (US1)

1. Setup: distribuição, esqueleto, lock (contratos pela tag), CI
2. US1: testes, prompt, `pack.py` — **PARE e VALIDE**: conformidade só com contratos e integração na plataforma
3. Foundational + checkpoint do léxico com o mantenedor
4. US2, depois US3 — **PARE e VALIDE** cada tabela
5. Polish: verificação, quickstart (inclusive a conversa manual), CI com deploy key, documentação e ponteiro do submódulo

### Depois desta fase

- 104 (esqueleto, Fase 4): validators `citation_integrity` e `validity_notice` ligados no `pack.py`
- 002 US5 (Fase 4): build da instalação com o pack (precisa de leitura no `ai-scouting` e no `agentic-app`)
- Fase 5: US5 (manifest com `rag_first`, coleção e esquema de configuração; retriever e reranker da 103; prompt com
  prioridades de fonte e citação), US4

---

## Notes

- O pack só importa stdlib e `ai_core_contracts` — qualquer outro import quebra a etapa de imports da conformidade e o
  import-linter
- Nenhuma tarefa cria porta secundária: a 101 não faz I/O (plano, gate de portas)
- Hooks assíncronos são testados com `asyncio.run`, sem `pytest-asyncio`
