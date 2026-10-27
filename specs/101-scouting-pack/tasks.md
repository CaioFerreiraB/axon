---

description: "Task list for 101 — pack scouting, Fase 4 (US1, US2, US3) e Fase 5 (US4, US5)"
---

# Tasks: Pack scouting — composição, contexto determinístico e prompts

**Input**: Design documents from `/specs/101-scouting-pack/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: incluídos. A FR-001 e o SC-003 exigem a conformidade da 001 só com os contratos, a US1 cen. 3 exige
verificação de fronteiras, e a US2 e a US3 são tabelas de casos — testes primeiro, falhando antes do código.

**Organization**: **Fase 4** do roadmap — US1, US2 e US3 (Phases 1–6, T001–T028); **Fase 5** — US4 (prioridade de
fontes) e US5 (`rag_first`, retriever, validators) — na seção "Fase 5" (Phases 7–11, T029–T044).

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
- [X] T027 Com o aval do mantenedor: commit e push do `ai-scouting`; criar a deploy key só de leitura no `agentic-app` e
  o segredo `AGENTIC_APP_DEPLOY_KEY` no `ai-scouting` (quickstart §7) e conferir os quatro jobs do `ci.yml` verdes
- [X] T028 [P] Atualizar no `agentic-app`: `CLAUDE.md` (seção "Código": o `ai-scouting` existe — pack `scouting` 0.1.0,
  manifest mínimo na Fase 4, prompt sem corpus, derivação pura com vigência em intervalo e dia de Brasília, suíte só com
  contratos e integração pelo grupo `platform`, CI com deploy key; "Fase 4 em andamento"), a linha da 101 em
  `specs/README.md` (status "Fase 4 implementada (US1, US2, US3)") e, no mesmo commit, o ponteiro do submódulo
  `ai-scouting`

---

# Fase 5 (2026-10-09): US4, US5 e a publicação da 104

**Escopo**: US4 (prioridades de fonte nas instruções) e US5 (`rag_first`, retriever e reranker da 103, validators da
104), com o prompt da Fase 5 e o ADR-026 já no core (`v0.2.0`). Decisões em [research.md](research.md) R16–R24;
tipos em [data-model.md](data-model.md), seção "Fase 5"; contrato em [contracts/scouting-pack.md](contracts/scouting-pack.md),
seção "Fase 5". A 104 não muda de código: passa a ser publicada pelo `pack.py`. Fora desta passada (R22): o
`agentic-deploy` (`CORE_REF`, modelo e5 e Qdrant na instalação). Caminhos como na Fase 4 (raiz em `ai-scouting/`).

## Phase 7: Setup da Fase 5

- [X] T029 `ai-scouting/pyproject.toml` (R20, R22; contracts/packaging.md "Fase 5"): `version = "0.2.0"`; em
  `[tool.uv.sources]`, `ai-core-contracts` e `ai-core` (grupo `platform`) pela tag `v0.2.0` (R22, nota: o `uv` não
  aceita duas fontes para os contratos; na `v0.2.0` eles são os `0.1.1`);
  `VERSION: Final = "0.2.0"` em `src/ai_scouting/pack.py`; `uv lock` e `uv sync --locked`. Os testes da Fase 4 que
  fixam `0.1.0` (manifest mínimo em `tests/test_pack.py`, versão em `tests/integration/test_platform.py`) passam a
  falhar até T034 e T037

---

## Phase 8: Foundational da Fase 5 — configuração do pack (bloqueia a US5)

- [X] T030 [P] `tests/test_config.py` (novo; R18; data-model "Configuração do pack"). **Testes primeiro**:
  `read_config(config)`, por casos: `{}` → `ValueError` nomeando `embedding_dir` (o default é `e5`);
  `{"embedder": "hashing"}` → `qdrant_url == "http://localhost:6333"`, `qdrant_path is None`, `index == "scouting"`,
  `default_limit == 5`, `max_limit == 30`; `{"qdrant_url": …, "qdrant_path": …}` → `ValueError` nomeando os dois
  ("exclusivo com `qdrant_path`"); `{"embedder": "e5", "embedding_dir": <dir sem arquivos>}` → `ValueError` nomeando
  `model.onnx` e `tokenizer.json`; com os dois arquivos (vazios) → aceito; `{"embedder": "hashing", "default_limit": 31}`
  com `max_limit` 30 → `ValueError` ("`1 ≤ default_limit ≤ max_limit`"); `SCOUTING_CONFIG_SCHEMA` tem `type: object`,
  `additionalProperties: false`, exatamente as propriedades `qdrant_url` (`pattern ^https?://`), `qdrant_path`
  (`minLength 1`), `index` (`pattern ^[a-z0-9][a-z0-9_-]*$`), `embedder` (`enum ["e5", "hashing"]`), `embedding_dir`
  (`minLength 1`), `default_limit` e `max_limit` (`integer`, `minimum 1`) — nenhuma com "key" no nome (FR-012); com
  `AI_SCOUTING_QDRANT_API_KEY` definida num valor sentinela, nenhuma mensagem de `ValueError` contém o valor
- [X] T031 `src/ai_scouting/pack.py` (R17, R18) (depende de T030): `COLLECTION: Final = "scouting"`;
  `SCOUTING_CONFIG_SCHEMA` (o da T030); `ScoutingConfig` (dataclass congelada: `qdrant_url: str | None`, `qdrant_path:
  str | None`, `index: str`, `embedder: Literal["e5", "hashing"]`, `embedding_dir: str | None`, `default_limit: int`,
  `max_limit: int`); `read_config(config: Mapping[str, JSONValue]) -> ScoutingConfig`, sem rede (só confere os arquivos do modelo),
  que aplica os defaults (o core não os aplica) e levanta `ValueError` nomeando o campo em cada combinação inválida da R18 — `qdrant_url` com
  `qdrant_path`; `e5` sem `embedding_dir` ou sem `model.onnx`/`tokenizer.json` nele; limites incoerentes. A chave nunca
  passa por aqui (FR-012); faz T030 passar

**Checkpoint**: a configuração do pack está definida, validada e testada sem rede

---

## Phase 9: User Story 4 — Respostas priorizam as fontes certas (Priority: P2) — Fase 5

**Goal**: o fragmento de instruções traz as cinco prioridades de fonte, na ordem, e as regras de citação pelo id, do
caminho sem trechos e de vigência (FR-008, FR-009, FR-011; R21, R24).

**Independent Test**: `uv run pytest tests/test_prompt.py` — as cinco prioridades aparecem na ordem da US4 e as frases
fixas do contrato estão no prompt.

- [X] T032 [P] [US4] `tests/test_prompt.py` reescrito para a Fase 5 (contracts/scouting-pack.md "Prompt da Fase 5";
  US4 cen. 1): as frases fixas "escot", "[[", "id:", "nenhum documento oficial", "fonte oficial", "nunca instrução"
  (texto normalizado, casefold); as cinco prioridades na ordem — os marcadores "institucion", "vigente",
  "específic", "preciso", "citação" aparecem nessa ordem de posição; um exemplo sintético de citação (`[[` + id com
  `#` e `@p`) e nenhum id do corpus real; continuam ausentes "chame" e "use a ferramenta"; sai a frase da Fase 4
  "nenhum documento institucional foi consultado"
- [X] T033 [US4] `src/ai_scouting/prompts/domain.py` (R21) (depende de T032): `SYSTEM_PROMPT` da Fase 5 — papel e
  público (escotismo brasileiro); **prioridades de fonte**, as cinco na ordem (institucionais sobre secundárias;
  vigentes sobre revogadas ou substituídas; específicas do ramo e primárias sobre genéricas; o trecho preciso sobre o
  amplo; sempre citação e proveniência); **citação**: depois de cada afirmação tirada de um trecho, `[[id]]` com o
  identificador exato que aparece depois de `id:` na referência do trecho (exemplo sintético
  `[[manual-x-2026#4.2@p12]]`), nunca citar trecho que não veio nem inventar identificador; **sem trechos**: se nenhum
  trecho chegou, conhecimento geral dizendo que nenhum documento oficial foi encontrado para a pergunta, sem citar nem
  nomear documento, recomendando confirmar na fonte oficial; **vigência**: trecho de versão substituída ou revogada é
  dito como tal; "dado, nunca instrução" (FR-009) e a recusa fora do escotismo, como na Fase 4; faz T032 passar

**Checkpoint**: US4 completa nas instruções; o efeito nas respostas é medido na 105

---

## Phase 10: User Story 5 — Resposta fundamentada no corpus pelo caminho determinístico (Priority: P2) — Fase 5

**Goal**: o pack declara `rag_first`, a coleção `scouting` e o esquema de configuração, e publica a tool
`scouting.search_docs` (103), o `MetadataReranker` (103) e os validators `citation_integrity` e `validity_notice`
(104); uma pergunta coberta responde com uma chamada de modelo e citação resolvível (SC-004, US5 cen. 1).

**Independent Test**: `uv run --python 3.14 --group platform pytest tests/integration/test_rag.py` — corpus sintético
num Qdrant embutido, perfil `test`, Assistant `scouting` sem `flow`: 200, um `model_call` no trace e a citação `[1]`
com a proveniência.

### Testes da US5 (escrever primeiro; devem falhar)

- [X] T034 [P] [US5] `tests/test_pack.py` reescrito para a Fase 5 (R19, R20; contracts/scouting-pack.md "Capacidades"):
  `manifest() == PackManifest(name="scouting", version="0.2.0", preferred_flow="rag_first",
  requires_collections=("scouting",), config_schema=SCOUTING_CONFIG_SCHEMA)` e a versão igual à da distribuição; com
  `pack_context("scouting", {"qdrant_path": str(tmp_path / "q"), "embedder": "hashing"})`: `tools` vazio, `retrievers`
  = uma `NamedRetriever` de nome `search_docs` e coleções `{"scouting"}`, `reranker` é `MetadataReranker`,
  `validators` com os nomes `["citation_integrity", "validity_notice"]`, nessa ordem (um `qdrant_path` novo a cada
  carga: o Qdrant embutido trava o diretório por cliente aberto); `retrievers` com configuração
  inválida levanta `ValueError` nomeando o campo; com `qdrant_url` e `AI_SCOUTING_QDRANT_API_KEY` definida, a carga não
  toca a rede (só monta o cliente); `system_prompt` estável e independente da configuração
- [X] T035 [P] [US5] `tests/test_conformance.py` (contracts/scouting-pack.md, conformidade nº 7): `assert_pack_conforms`
  e `check_pack` com `config={"qdrant_path": <tmp>, "embedder": "hashing"}`, um diretório por chamada (sem configuração, o default `e5` exige
  `embedding_dir` e a carga falharia — fail closed); o relatório sem itens no ambiente limpo e só
  `distribution.not_found` na instalação editável, como na Fase 4
- [X] T036 [P] [US5] `tests/integration/test_rag.py` (novo; grupo `platform`; R23; contracts/scouting-pack.md nº 9):
  `pytest.importorskip("ai_core")`; publica o corpus sintético da 103 (`tests/rag/retrieval/corpus.py`) num
  `AsyncQdrantClient(path=tmp)` com o `QdrantIndex` sob o alias `scouting`, o `HashingEmbedder` e o `Bm25Encoder`, e
  **fecha o cliente** (o modo embutido trava o diretório); `packs.yaml` com `scouting: {enabled: true, config:
  {qdrant_path: <tmp>, embedder: hashing}}`; `assistants.yaml` com o Assistant `scouting` sem `flow` (logo o preferido,
  `rag_first`), `packs: [scouting]`, `collections: [scouting]`, só `generation`; variáveis `AI_CORE_*` limpas e
  apontando os arquivos; `platform(profile="test", overrides={"providers": {"ollama": CitingProvider()}})`, com o
  `CitingProvider` escrito no próprio teste só com tipos do contrato 001 (`LLMProvider` + `name` + `probe` que devolve
  um objeto com `available=True`): no streaming, acha o primeiro `id: <x>]` da mensagem `tool` e responde
  `"Conforme o documento [[<x>]]."`. Espera-se: 200; `x_ai_core.citations` com um item cujo `chunk_id` é `<x>` e com
  documento e página; o texto com `[1]`; no trace da requisição (`plataforma.trace.trace(request_id)`), exatamente um
  `model_call` (SC-004) e um `coverage_gate` com `route == "generate"`; o provider recebeu `· id:` (ADR-026). Um
  segundo caso, com `AI_CORE_RAG_MIN_SCORE=1`: 200 sem `tool` nas mensagens; o `CitingProvider`, sem `id:` no contexto,
  responde "Nenhum documento oficial foi encontrado." sem citação, e `"ungrounded" in x_ai_core.flags` (FR-011; o aviso
  da 104)
- [X] T037 [P] [US5] `tests/integration/test_platform.py` (Fase 4, US1 cen. 1–2): o `packs.yaml` ganha `config:
  {qdrant_path: <tmp>, embedder: hashing}` (sem ela, o pack não carrega); a versão esperada passa a `0.2.0`; o
  Assistant `flow: chat` continua servindo. Dois casos novos (Edge Case "configuração inválida"; FR-012): `config:
  {embedder: e5}` sem diretório → `entry.status == "error"` e a mensagem cita `embedding_dir`; `config` com uma
  propriedade desconhecida (`api_key`) → o pack em erro pelo esquema — a chave não entra no `packs.yaml`

### Implementação da US5

- [X] T038 [US5] `src/ai_scouting/pack.py` (R19, R20) (depende de T031, T034–T037): `manifest()` da Fase 5;
  `retrievers(ctx)` — `read_config(ctx.config)`; com os imports de infraestrutura **dentro** do hook (como no
  `corpus_cli`), `AsyncQdrantClient(path=…)` ou `AsyncQdrantClient(url=…, api_key=os.environ.get(
  "AI_SCOUTING_QDRANT_API_KEY") or None)`, `E5Embedder(Path(embedding_dir).expanduser())` ou `HashingEmbedder()`,
  `Bm25Encoder()`, `QdrantIndex(client, config.index, embedder, sparse)`, `ScoutingRetriever(index,
  RetrievalConfig(default_limit=…, max_limit=…))` e `[search_docs(retriever, collection=COLLECTION)]`; `reranker(ctx)`
  → `MetadataReranker()`; `validators(ctx)` → `(CitationIntegrityValidator(), ValidityNoticeValidator())`; docstring
  do módulo da Fase 5 (o `pack.py` é a composition root; a chave só do ambiente — FR-012). Faz T034–T037 passarem
- [X] T039 [US5] `pyproject.toml`, `[tool.importlinter]`: conferir que o contrato "só o pack.py compõe" cobre `rag` e
  `validators` abaixo de `pack` e que "infraestrutura só em adapters/" não acusa o `pack.py` (que importa os adapters
  dentro dos hooks, como no `corpus_cli`); ajustar se preciso; `uv run lint-imports` com todos `KEPT`
- [X] T040 [US5] Rodar a suíte padrão (`uv run pytest`) e a integração (`uv run --python 3.14 --group platform pytest
  tests/integration`) até T034–T037 passarem, com `uv run mypy` e `uv run ruff check` limpos

**Checkpoint**: US4 e US5 completas; a 104 está publicada

---

## Phase 11: Polish da Fase 5

- [X] T041 Verificação completa dentro de `ai-scouting/`: `uv run pytest` em 3.14 e em 3.12 (`uv run --python 3.12
  pytest`), `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`, `uv run lint-imports`, a integração e a
  suíte do índice contra o servidor (`AI_SCOUTING_TEST_QDRANT_URL`), e o ambiente limpo em 3.12 (`pip install . pytest
  fpdf2` e `pytest tests --ignore=tests/integration`)
- [X] T042 Executar as §8–9 de [quickstart.md](quickstart.md) e, com o mantenedor, a §10 (índice real, e5 em
  `~/.cache/ai-scouting/e5-small`, `ai-core serve` com um modelo de geração); corrigir divergências entre o resultado e
  o "Esperado"
- [X] T043 [P] Documentação no `agentic-app`: em [data-model.md](data-model.md), a nota da Fase 4 que ainda cita
  `scouting_docs` passa a `scouting` (R17), e a linha da distribuição na tabela de identidade ganha "0.2.0 a partir
  da Fase 5"; linhas da 101 ("Fases 4 e 5 implementadas: US1–US5") e da 104 ("publicada
  pelo pack na Fase 5") em `specs/README.md`; seção "Código" de `CLAUDE.md` (pack `scouting` 0.2.0: `rag_first`, coleção
  `scouting`, `config_schema` com Qdrant por URL ou embutido e o embedder de teste, chave só no ambiente; tool
  `search_docs`, `MetadataReranker` e os validators da 104 publicados; prompt da Fase 5; o que segue: `agentic-deploy` e
  a 105)
- [X] T044 Com o aval do mantenedor: commit e push do `ai-scouting` e conferir o CI verde (os jobs `test`, `clean-env`,
  `platform` — agora contra o core `v0.2.0` — e `qdrant`); no `agentic-app`, o SDD e o ponteiro do submódulo no mesmo
  commit, e push

---

## Fase 5 — Dependencies & Execution Order

- **Setup (Phase 7)**: T029 primeiro (o lock precisa das tags novas)
- **Foundational (Phase 8)**: T030 → T031; bloqueia a US5, não a US4
- **US4 (Phase 9)**: depende só de T029; T032 → T033
- **US5 (Phase 10)**: depende da Phase 8; testes T034–T037 em paralelo; T038 → T039 → T040
- **Polish (Phase 11)**: T041 depois das histórias; T042 depois de T041; T043 em paralelo; T044 por último, com aval

## Parallel Example: Fase 5

```bash
# Depois de T029, juntos:
Task: "tests/test_config.py (T030)"
Task: "tests/test_prompt.py (T032)"

# Testes da US5, juntos (depois de T031):
Task: "tests/test_pack.py (T034)"
Task: "tests/test_conformance.py (T035)"
Task: "tests/integration/test_rag.py (T036)"
Task: "tests/integration/test_platform.py (T037)"
```

## Fase 5 — Implementation Strategy

1. Setup: versão e tags (contratos `contracts-v0.1.1`, core `v0.2.0`)
2. Configuração do pack (Phase 8) — a base do `retrievers`
3. US4: o prompt da Fase 5 (pequeno, independente)
4. US5: testes, `pack.py` — **PARE e VALIDE**: `test_rag.py` com uma chamada de modelo e citação `[1]` (SC-004)
5. Polish: verificação, quickstart (a §10 com o mantenedor), documentação, commit dos dois repositórios

### Depois desta fase

- `agentic-deploy`: `CORE_REF` em `v0.2.0`, o modelo e5 no estágio `packs` (`ai-scouting-corpus model fetch`), o Qdrant
  e o `config` do scouting no `packs.yaml` da instalação — feito na passada de encaixe da Fase 5 da 002 (T056–T062); o
  estágio `core` já clona o `agentic-app` sem submódulos, então o deploy não precisou do ajuste da CI do pack
- curador: confirmar os valores "A CONFIRMAR" do `corpus/corpus.yaml`
- 105: conjunto dourado, medida da US4 e calibração do limiar (`AI_CORE_RAG_MIN_SCORE`) e dos limites

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

---

## Passada de 2026-10-20: identidade Axon — US6 ([ADR-037](../../docs/adr/ADR-037-a-plataforma-se-chama-axon.md); research R25–R31)

**Goal**: `axon-scouting` 0.4.0 (`axon_scouting`, `axon-scouting-corpus`, grupo `axon.packs`, contratos 0.2 e core pela
`v0.7.0-rc1`), recusa de `AI_SCOUTING_*`, integração, CI e avaliação com os nomes novos, specs 101–106 nos nomes.

**Independent Test**: [quickstart.md, "Fase 9, incremento 9.5"](quickstart.md).

### Setup (no repositório `axon-scouting`, submódulo `ai-scouting/`)

- [X] T063 [US6] Linha de base: `git grep -cw agentic` no submódulo e nas specs 101–106; `git mv src/ai_scouting
  src/axon_scouting` (R25)
- [X] T064 [US6] Aplicar `rename101.py` (scratchpad, R27) à lista de arquivos de texto versionados do submódulo (menos
  `uv.lock`) e aos documentos vivos de `specs/101-*` a `specs/106-*` (`spec.md`, `design.md`, `data-model.md`,
  `quickstart.md`, `contracts/**`) — nunca `research.md`, `plan.md`, `tasks.md`, `checklists/`; protegendo
  `AGENTIC_APP_DEPLOY_KEY`, os nomes de submódulo da CI e a palavra `agentic`
- [X] T065 [US6] À mão (R25): `pyproject.toml` (`version = "0.4.0"`, `description`, `axon-ai-contracts>=0.2,<0.3`, fontes
  `ssh://git@github.com/CaioFerreiraB/axon.git` tag `v0.7.0-rc1` com `axon-ai/packages/{contracts,core}`, grupo
  `platform` com `axon-ai`); `src/axon_scouting/pack.py` (`VERSION = "0.4.0"`, `contract_version = "0.2"`); `uv lock`

### Tests (antes da T068)

- [X] T066 [P] [US6] `tests/test_legacy_environment.py` (R30): `legacy_environment` sem antigas → `None`; com
  `AI_SCOUTING_INDEX`, `AI_SCOUTING_FOO` e `AI_SCOUTING_QDRANT_URL=""` → uma linha por variável em ordem, sem valor; com
  `MY_AI_SCOUTING_X` e `AI_SCOUTINGX` → `None`; antiga e nova juntas → recusa; `ScoutingPack().retrievers(...)` com
  `AI_SCOUTING_INDEX` no ambiente → `ValueError` citando `AXON_SCOUTING_INDEX`; `corpus_cli()` com `status` e a variável
  antiga → `SystemExit(2)` e a mensagem; `find_spec("ai_scouting") is None`
- [X] T067 [P] [US6] `tests/test_pack.py`: versão `0.4.0` igual à de `version("axon-scouting")` e `contract_version == "0.2"`;
  `tests/integration/*.py`: a limpeza do ambiente com `("AXON_", "AI_CORE_", "AI_SCOUTING_")` (R28). Rodar T066 e ver falhar

### Implementation

- [X] T068 [US6] `src/axon_scouting/pack.py` (R26): `LEGACY_PREFIX`, `PREFIX`, `legacy_environment`, a chamada no início de
  `retrievers()` e de `corpus_cli()`; `API_KEY_VARIABLE = "AXON_SCOUTING_QDRANT_API_KEY"` e as demais variáveis (vêm da
  T064); docstrings

### Integration e verificação

- [X] T069 [US6] CI e avaliação (R28): conferir `.github/workflows/ci.yml` (`AXON_SCOUTING_TEST_QDRANT_URL`, comentários com
  `axon`) e `eval.yml` (`AXON_SCOUTING_*`, `AXON_PROFILE`, `AXON_PACKS_FILE`, `AXON_ASSISTANTS_FILE`, `axon eval run`,
  `axon-scouting-corpus`, filtros `src/axon_scouting/**`)
- [X] T070 [US6] Suítes (R31): `uv sync && uv run pytest && uv run mypy && uv run ruff check && uv run ruff format --check &&
  uv run lint-imports`; ambiente limpo em 3.12 (`uv pip install . pytest fpdf2`; `pytest tests --ignore=tests/integration`);
  `uv run --python 3.14 --group platform pytest tests/integration`; `tests/rag/index` contra um Qdrant local com
  `AXON_SCOUTING_TEST_QDRANT_URL`
- [X] T071 [US6] Quickstart da US6 à mão (CLI com a variável nova e com a antiga) e resíduos (SC-005): `git grep -nE
  'ai_scouting|ai-scouting|AI_SCOUTING_|ai_core|ai-core|AI_CORE_'` fora do histórico só na recusa e nos testes dela; nenhuma
  palavra `agentic` removida (`--word-diff`)
- [X] T072 [US6] Commit no `axon-scouting`; no `axon`, o ponteiro do submódulo e os documentos (specs 101–106,
  `specs/README.md` com a US6 da 101, `docs/roadmap.md`) num commit — os pushes só com o aval do mantenedor

### Dependencies (US6)

T063 → T064 → T065 → T066 ∥ T067 (veem falhar) → T068 → T069 → T070 → T071 → T072.

### Notas da execução (US6)

- Linha de base (T063): `agentic` no pack 26, nas specs 1xx 83; nenhuma ocorrência do flow `agentic` removida ao fim
  (`--word-diff`, só o nome do repositório e da instalação).
- A regra `ai_core → axon_ai` não vale para a extensão da resposta, que a 008 chama de `x_axon`: o `test_rag.py` saiu
  da substituição com `x_axon_ai` e foi corrigido; o caminho do comando no `test_eval.py` também (`axon`, não `axon-ai`).
- O link para o arquivo do ADR-021 no `design.md` foi preservado (o nome do arquivo de um ADR aceito não muda).
- `contracts/packaging.md` ganhou a seção "Fase 9 (2026-10-20)" com o estado atual; as seções das fases anteriores
  descrevem o que valia então. Os submódulos da tag `v0.7.0-rc1` ainda se chamam `ai-scouting` e `agentic-deploy`, então
  o `update = none` da CI segue com esses nomes até a tag seguinte ao fechamento.
- Suítes (T070): padrão 570 passed, 8 skipped; mypy, ruff check, ruff format e lint-imports (10 kept) limpos; ambiente
  limpo em 3.12 com `axon-ai-contracts` 0.2.0: 570 passed, 5 skipped; plataforma (3.14, `v0.7.0-rc1`): 9 passed; índice
  contra Qdrant v1.19.2 local: 130 passed, 4 skipped, e os 4 do e5 com o modelo em cache: 4 passed.
- CLI à mão (T071): `AXON_SCOUTING_INDEX=teste … status` → "índice teste: nenhum build publicado", 0; com
  `AI_SCOUTING_INDEX` e `AI_SCOUTING_QDRANT_API_KEY` → as duas linhas de recusa, sem o valor, 2.
- Fora do repositório, a mudar à mão: `~/.config/ai-core/` (o quickstart passou a `~/.config/axon/`, com variáveis
  `AXON_*`) e `~/.cache/ai-scouting/e5-small` (`~/.cache/axon-scouting/e5-small`).

---

## Passada de 2026-10-21: o pack prepara o e5 e carrega o índice do pacote ([ADR-041](../../docs/adr/ADR-041-o-pack-prepara-os-proprios-dados-no-build.md), [ADR-043](../../docs/adr/ADR-043-indice-do-scouting-gerado-no-desenvolvimento.md); research R32–R34)

- [X] T073 `pack.py`: `prepare`, `read_config(config, data_dir, require_model)`, `store`/`index_dir`/`embedder: pplx`,
  `_embedder` e a carga do `ArtifactIndex`; `contract_version` "0.2.1", versão `0.5.0`, contratos pela `v0.7.0-rc4`
  (R32, R33)
- [X] T074 [P] Testes de configuração, do pack e do `prepare`; conformidade sobre o artefato do pacote; integração do
  `rag_first` sobre um artefato (R34)
- [X] T075 [P] `README.md` do pack (instalação sem serviço, os dois embedders), `eval/packs.yaml` sem Qdrant e
  `eval/packs-pplx.yaml`

## Passada de 2026-10-27 (revisão do RAG; research R35; [ADR-045](../../docs/adr/ADR-045-filhotes-e-consulta-multifaceta-no-scouting.md))

- [X] T076 [US7] `filhotes` e `all_branches` em `context/lexicon.py`; `ScoutingContext.branches` e `to_slice` em
  `context/derivation.py`; casos em `tests/test_derivation.py` e `tests/test_lexicon.py`; o contrato
  `retrieval_filters` com `branches`.
- [X] T077 [US8] Os três parágrafos no `prompts/domain.py` e os testes de frase e de "nenhum fato" (R36).

## Passada de 2026-10-27, teste no ambiente de dev (research R37; [ADR-046](../../docs/adr/ADR-046-tipo-sugerido-ordena-no-scouting.md))

- [X] T078 `document_types` citados e `suggested_types` na derivação e na fatia; léxico só com tipos citáveis
  (`programa_educativo` fora, `guia` nos temas, "guia de"); ano relativo em `periods.py`; testes.
- [X] T079 Prompt sem as palavras do mecanismo (FR-024); teste.
