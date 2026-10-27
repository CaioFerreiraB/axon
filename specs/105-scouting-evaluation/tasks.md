---

description: "Task list for 105 — avaliação do domínio escoteiro, Fase 6 (infraestrutura e conjunto semente)"
---

# Tasks: Conjunto dourado e calibração do domínio escoteiro

**Input**: Design documents from `/specs/105-scouting-evaluation/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: incluídos — as tabelas de [domain-metrics.md](contracts/domain-metrics.md) e as regras de
[golden-set.md](contracts/golden-set.md) são os casos de aceite.

**Organization**: **Fase 6 — infraestrutura e semente** (clarificação 1): US1 e US2 sobre o conjunto semente
provisório. US3–US5 (calibração, embedding, modelo local) **não** estão aqui — esperam a curadoria, depois do
desenvolvimento (research R11). A troca de versão no `agentic-deploy` é uma passada de encaixe da 002, depois desta (R9).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: user story da tarefa (US1, US2)

## Path Conventions

- Caminhos a partir de `ai-scouting/` (submódulo), salvo os que começam com `specs/`, `docs/` ou `CLAUDE.md`
- Comandos dentro de `ai-scouting/`, com `XDG_DATA_HOME=$HOME/.local/share`; o `uv lock` precisa do agente SSH (a tag
  vem do repositório privado)

---

## Phase 1: Setup

- [X] T001 Em `pyproject.toml`: `version = "0.3.0"`; dependência `"ai-core-contracts>=0.1.2,<0.2"`; as duas fontes de
  `[tool.uv.sources]` (`ai-core-contracts` e `ai-core`) na tag `v0.3.0`, com o comentário acima dizendo que na v0.3.0 os
  contratos são os 0.1.2 (`ai_core_contracts.eval`); `uv lock` e `uv sync`. Em `src/ai_scouting/pack.py`, `VERSION =
  "0.3.0"`; em `tests/test_pack.py` e `tests/integration/test_platform.py`, a versão esperada `0.3.0`; na docstring de
  `tests/integration/test_rag.py`, "core `v0.3.0`" (research R9)
- [X] T002 Criar `src/ai_scouting/eval/__init__.py` (docstring: spec 105, métricas de domínio puras pelo hook
  `eval_metrics` — ADR-027 —, sem relógio e sem I/O; a execução é do harness da 009) e `tests/eval/__init__.py` vazio
- [X] T003 Em `pyproject.toml`, `[tool.importlinter]` (research R10): o contrato "só o pack.py compõe" passa a
  `layers = ["ai_scouting.pack", "ai_scouting.eval", "ai_scouting.context | ai_scouting.prompts |
  ai_scouting.validators | ai_scouting.rag"]`; `ai_scouting.eval` entra em `source_modules` de "derivação e validators
  não alcançam modelo nem MCP" (renomeado "derivação, validators e métricas não alcançam modelo nem MCP"), de "os outros
  módulos do pack veem só o seam do índice" e de "infraestrutura só em adapters/"; `uv run lint-imports` passa
- [X] T004 [P] Em `.gitignore`, `.cache/` (o e5 e os relatórios da avaliação local, R6); em `tests/test_purity.py`,
  `Path(ai_scouting.eval.__file__).parent` em `PURE` e a docstring citando a 105

---

## Phase 2: Foundational — campos de `extra.context` (bloqueia US1 e US2)

- [X] T005 Criar `src/ai_scouting/eval/metrics.py` só com o que a validação do conjunto (US1) e as métricas (US2)
  compartilham, a partir de [data-model.md](data-model.md) "`extra.context`": `CONTEXT_KEY = "context"`,
  `CONTEXT_FIELDS: Final = ("branch", "topics", "document_types", "effective_from", "effective_until",
  "include_superseded", "previous_version")` e `is_historical(extra: Mapping[str, JSONValue]) -> bool` ("`extra.context`
  com `include_superseded` ou `previous_version` verdadeiro"); reexportar em `eval/__init__.py`

---

## Phase 3: User Story 1 — Conjunto dourado (semente provisória) (P1) 🎯

**Goal**: o conjunto semente no formato da 009, validado contra o catálogo do corpus e o léxico, sem o core.

**Independent Test**: `uv run pytest tests/eval/test_golden.py` (regras 1–7 de [golden-set.md](contracts/golden-set.md)).

- [X] T006 [P] [US1] Criar `tests/eval/test_golden.py` com uma função local `_problems(golden: Mapping[str, Any],
  catalog: Mapping[str, Any]) -> list[str]` que aplica as regras 1–7 de [golden-set.md](contracts/golden-set.md) — `id`
  único, `question`, `reference_time` ISO com fuso, `reference_answer`; `expected_documents` e `expected_citations`
  "ambas vazias (pergunta fora do corpus) ou ambas não vazias"; todo `document` de `expected_documents`/`expected_citations` é o
  `title` de uma entrada de `documents` do `corpus/corpus.yaml`; todo `chunk_id` começa por `<document_id>-<version>#` da
  entrada cujo `title` é o `document` ao lado; `extra.context` só com `CONTEXT_FIELDS`; `branch` em
  `LEXICON.branches` ou `null`, `topics` em `{t.id for t in LEXICON.topics}`, `document_types` em
  `LEXICON.document_types`, datas como `str` (texto ISO entre aspas; `date` vindo de data sem aspas é problema) e
  legíveis por `date.fromisoformat`; item histórico — `is_historical(extra)` ou `derive_context(question,
  reference_day(reference_time))` com `include_superseded` ou `previous_version` — com o marcador, `effective_from` e
  `effective_until` em `extra.context`; `extra.provisional is True` — cada problema nomeando o `id` do item e o valor. Testes:
  `test_semente_sem_problemas` (lê `eval/golden.yaml` e `corpus/corpus.yaml` com `yaml.safe_load`, espera `[]`);
  `test_semente_tem_entre_8_e_12_itens`; `test_semente_cobre_os_quatro_documentos_um_historico_e_um_fora_do_corpus`
  (composição de golden-set.md); e casos negativos com conjuntos montados no teste — documento fora do catálogo (a
  mensagem nomeia item e documento), `chunk_id` com prefixo de outro documento, campo a mais em `extra.context`, tema
  inexistente, item histórico sem `effective_until`, pergunta "em 2022" sem `extra.context`, data sem aspas (`date`),
  `reference_time` sem fuso, `provisional` ausente, item sem `reference_answer`, item com documentos esperados e sem
  citações esperadas
- [X] T007 [US1] Escrever `eval/golden.yaml` (research R4; [golden-set.md](contracts/golden-set.md) "Arquivo" e
  "Composição"): cabeçalho comentado (semente provisória, clarificação 1, nenhuma calibração sobre ela), `version: 1`,
  `name: scouting-semente`, `assistant: scouting`, 8 a 12 itens `s01`… com `reference_time` fixo
  (`2026-10-13T12:00:00-03:00`, salvo o histórico), `extra.provisional: true` e, onde couber, `extra.context`.
  Perguntas escritas a partir do corpus: normativas do POR, do Estatuto e da Resolução CAN 08/2021; uma do manual
  "Escotistas em Ação — Ramo Lobinho" (com `branch: lobinho`); uma histórica num período em que a Resolução estava em
  vigor (ex.: "em 2022", `include_superseded: true`, `effective_from: "2022-01-01"`, `effective_until: "2022-12-31"` —
  datas entre aspas); uma fora do corpus, sem evidência nem citação esperadas e com a resposta de referência do caminho
  sem trechos. Todo item tem `reference_answer`. Cada `chunk_id` conferido no índice com `ai-scouting-corpus original <chunk_id>`
  (corpus ingerido num Qdrant local, quickstart passo 3) e a `reference_answer` tirada do próprio trecho (T006 passa)

**Checkpoint**: a semente é válida contra o corpus e o léxico, só com os contratos.

---

## Phase 4: User Story 2 — Linha de base registrada (P1)

**Goal**: as três métricas de domínio no relatório do harness, a configuração de avaliação no repositório, a linha de
base da semente e o job `eval` comparando com ela.

**Independent Test**: `uv run pytest tests/eval/test_metrics.py tests/test_pack.py tests/test_conformance.py` e
`uv run --python 3.14 --group platform pytest tests/integration/test_eval.py`; a rodada do quickstart passo 3 sai 0
contra `eval/baseline.json`.

- [X] T008 [P] [US2] Criar `tests/eval/test_metrics.py` com as três tabelas de
  [domain-metrics.md](contracts/domain-metrics.md), caso a caso e com os números da tabela, construindo `EvalItem`,
  `EvalObservation` e `EvalChunk` de `ai_core_contracts.eval` à mão: `context_accuracy` casos 1–8 (o 7 com a pergunta
  "Qual era a regra de uniforme em 2022?"; o 8 com `reference_time` `2026-10-13T22:30:00-03:00` e as datas
  `2026-10-13`), `current_document_rate` casos 1–6, `validity_notice_rate` casos 1–4; mais `name`, `better` e
  `deterministic` de cada classe, e duas chamadas iguais dando o mesmo valor
- [X] T009 [US2] Em `src/ai_scouting/eval/metrics.py`, as classes de [data-model.md](data-model.md) "Métricas de
  domínio", com `name`/`better`/`deterministic` como atributos de classe: `ContextAccuracy` (`context_accuracy`,
  `higher`, `True`) — sem `extra.context` ou vazio → `None`; obtido = `derive_context(item.question,
  reference_day(item.reference_time))`; por campo declarado em `CONTEXT_FIELDS`: `branch` por igualdade, `topics` e
  `document_types` como conjuntos, `effective_from`/`effective_until` (texto) contra `validity.start.isoformat()`/
  `validity.end.isoformat()`,
  booleanos por igualdade; campo fora de `CONTEXT_FIELDS` ignorado; valor = casados / declarados —;
  `CurrentDocumentRate` (`current_document_rate`, `higher`, `True`) — item histórico ou `delivered` vazio → `None`;
  senão entregues com `status == ValidityStatus.VIGENTE` (status `None` conta como não vigente) / entregues —;
  `ValidityNoticeRate` (`validity_notice_rate`, `higher`, `False`) — nenhuma citação com status diferente de `vigente`
  (inclusive ausente) → `None`; senão `1.0` com a flag `non_current_source`, `0.0` sem ela —; reexportar em
  `eval/__init__.py` (T008 passa)
- [X] T010 [US2] Em `src/ai_scouting/pack.py`, `def eval_metrics(self, ctx: PackContext) -> Sequence[EvalMetric]`
  devolvendo `(ContextAccuracy(), CurrentDocumentRate(), ValidityNoticeRate())`, nessa ordem; em `tests/test_pack.py`, o
  teste dos nomes e da ordem; `tests/test_conformance.py` segue sem nenhum item no relatório (a etapa `eval_metric.*` dos
  contratos 0.1.2 aceita as três)
- [X] T011 [P] [US2] Criar `eval/packs.yaml` (o `scouting` habilitado com `config: {qdrant_url:
  "http://localhost:6333", index: scouting, embedding_dir: .cache/e5}`) e `eval/assistants.yaml` (o Assistant
  `scouting`, `visibility: public`, `auth: {schemes: [oidc, api_key], allow: ["svc:eval"]}`, sem `flow`, `packs:
  [scouting]`, `collections: [scouting]`, `models: {generation: ollama/qwen3:1.7b, allow: ["ollama/*"]}`, e `api_keys:
  {admin_group: admin}`), cada um com um comentário de cabeçalho dizendo para que serve e de onde roda (research R6)
- [X] T012 [US2] Criar `tests/integration/test_eval.py` (grupo `platform`, `pytest.importorskip("ai_core")`; só a
  superfície da 011: variáveis `AI_CORE_*` e o comando `ai-core` do próprio ambiente,
  `Path(sys.executable).with_name("ai-core")`, em `subprocess.run` com `capture_output` — cada rodada num processo, que
  solta a trava do Qdrant embutido ao sair): publicar o
  corpus sintético da 103 num Qdrant embutido com o embedder de teste (como `_publish` de `test_rag.py`), um
  `packs.yaml` temporário com `qdrant_path` e `embedder: hashing`, `AI_CORE_PROFILE=test`, `AI_CORE_ASSISTANTS_FILE` =
  `eval/assistants.yaml`. Testes: (a) um conjunto de dois itens sobre documentos do corpus sintético, com
  `extra.context` — `ai-core eval run --golden … --report …` sai 0 e o relatório traz
  `scouting:context_accuracy`, `scouting:current_document_rate` e `scouting:validity_notice_rate`, com
  `deterministic` verdadeiro nas duas primeiras; (b) `eval/golden.yaml` roda com `invalid == []` no relatório
  (regra 8 de golden-set.md); (c) a segunda rodada com `--baseline` apontando o relatório da primeira sai 0 (US2
  Independent Test)
- [X] T013 [US2] Gerar `eval/baseline.json` com a configuração da CI (quickstart passo 3 + `--update-baseline`): Qdrant
  `v1.19.2` em Docker, `ai-scouting-corpus model fetch .cache/e5`, ingestão de `corpus/corpus.yaml`, `ai-core assistants
  validate` com as mesmas variáveis (sai 0) e `ai-core eval run` no perfil `test`; nenhum item inválido nem aviso "evidência não vista" (se houver, corrigir o `chunk_id` em
  `eval/golden.yaml` e regerar); repetir a rodada sem `--update-baseline` e conferir saída 0 com deltas zero nas
  determinísticas (SC-001; research R8)
- [X] T014 [US2] Criar `.github/workflows/eval.yml` (research R7): `on` em `push` para `main` e `pull_request` com
  `paths` (`corpus/**`, `src/ai_scouting/rag/**`, `src/ai_scouting/prompts/**`, `src/ai_scouting/context/**`,
  `src/ai_scouting/eval/**`, `src/ai_scouting/pack.py`, `eval/**`, `pyproject.toml`, `uv.lock`,
  `.github/workflows/eval.yml`) e `workflow_dispatch`; um job com serviço `qdrant/qdrant:v1.19.2` na porta 6333; passos:
  checkout, `webfactory/ssh-agent` com `AGENTIC_APP_DEPLOY_KEY`, submódulos do `agentic-app` com `update = none` (como no
  `ci.yml`), `astral-sh/setup-uv` com Python 3.14, `uv sync --locked --group platform`, `actions/cache` de `.cache/e5`
  com a chave `e5-${{ hashFiles('src/ai_scouting/rag/index/adapters/e5.py') }}`, `uv run ai-scouting-corpus model fetch
  .cache/e5` (só baixa o que falta ou difere), ingestão com `AI_SCOUTING_QDRANT_URL=http://localhost:6333` e
  `AI_SCOUTING_EMBEDDING_DIR=.cache/e5`, e `uv run --group platform ai-core eval run --golden eval/golden.yaml
  --baseline eval/baseline.json --report report.json` com `AI_CORE_PROFILE=test`, `AI_CORE_PACKS_FILE=eval/packs.yaml`
  e `AI_CORE_ASSISTANTS_FILE=eval/assistants.yaml`; `actions/upload-artifact` de `report.json` com `if: always()`.
  Comentário de cabeçalho com a spec, a clarificação 2 e "só métricas determinísticas barram"

**Checkpoint**: a linha de base da semente existe e uma segunda rodada a compara sem regressão.

---

## Phase 5: Polish & Cross-Cutting Concerns

- [X] T015 [P] Em `README.md` do `ai-scouting`, seção "Avaliação": o conjunto semente provisório (substituído na
  curadoria), as três métricas, o comando local (quickstart passo 3), a linha de base deliberada (`--update-baseline`) e
  o job `eval`
- [X] T016 Verificação completa dentro de `ai-scouting/`: `uv run pytest && uv run mypy && uv run ruff check && uv run
  ruff format --check && uv run lint-imports`; `uv run --python 3.14 --group platform pytest tests/integration`; o
  ambiente limpo do job `clean-env` (Python 3.12, `uv pip install . pytest fpdf2`, `pytest -q tests
  --ignore=tests/integration`) — o `test_golden.py` roda nele (o `pyyaml` é dependência do pack)
- [X] T017 [P] SDD e docs no `agentic-app`: `specs/105-scouting-evaluation/quickstart.md` com uma tabela dos números da
  linha de base da semente (T013); `specs/README.md` (linha da 105: infraestrutura e semente na Fase 6, calibração
  depois da curadoria); `docs/roadmap.md` (Fase 6: 009 e a infraestrutura da 105 feitas, US3–US5 da 105 adiadas até a
  curadoria); `CLAUDE.md` (parágrafo da Fase 6: o pack 0.3.0 com as métricas de domínio, `eval/` com a semente e a
  linha de base, o job `eval`; o `agentic-deploy` pendente da passada de encaixe da 002); marcar as tarefas com `[X]`
- [X] T018 Com aprovação do mantenedor: commit e push no `ai-scouting` (pack 0.3.0) e, no `agentic-app`, o SDD da 105
  com o ponteiro do submódulo; conferir na CI do `ai-scouting` os jobs `lint`, `test`, `clean-env`, `platform`,
  `qdrant` e `eval` — se o `eval` divergir da base local só por diferença numérica de CPU, regravar `eval/baseline.json`
  a partir do relatório do próprio job (artefato) num commit que diz por quê (R8)

---

## Dependencies & Execution Order

- **Setup (T001–T004)**: T001 primeiro (a tag `v0.3.0` traz `ai_core_contracts.eval`); T002 antes de T003 (o
  import-linter recusa módulo inexistente); T004 depois de T002
- **Foundational (T005)**: depois do Setup; bloqueia US1 (T006 usa `CONTEXT_FIELDS` e `is_historical`) e US2
- **US1 (T006–T007)**: T006 antes de T007 (o teste define a validação que o arquivo cumpre); T007 precisa do corpus
  ingerido num Qdrant local para conferir os ids
- **US2 (T008–T014)**: T008 → T009 → T010; T011 em paralelo com T008–T010; T012 depois de T010, T011 e T007; T013
  depois de T007, T010 e T011; T014 depois de T013 (compara com a base)
- **Polish (T015–T018)**: depois das duas histórias; T018 por último

### Parallel Opportunities

- T004 com T003 (arquivos diferentes)
- T008 (testes das métricas) com T011 (arquivos de avaliação) e com T006/T007 (US1)
- T015 com T017

## Parallel Example: User Story 2

```text
T008 tests/eval/test_metrics.py          (tabelas de domain-metrics.md)
T011 eval/packs.yaml + eval/assistants.yaml
```

## Implementation Strategy

1. Setup + Foundational: o pack resolve os contratos 0.1.2 e o `eval/` existe dentro das fronteiras.
2. **MVP — US1**: a semente válida contra o corpus, só com os contratos.
3. US2: métricas → hook → configuração → integração → linha de base → job `eval`.
4. Polish: documentação, verificação completa e, com aprovação, commit, push e a CI.
5. Depois desta lista (fora dela): a passada de encaixe da 002 no `agentic-deploy` (`CORE_REF=v0.3.0`, pack 0.3.0) e,
   depois do desenvolvimento, a curadoria — que troca a semente e destrava US3–US5.

---

## Passada de 2026-10-21 ([ADR-043](../../docs/adr/ADR-043-indice-do-scouting-gerado-no-desenvolvimento.md); research R12)

- [X] T019 `eval/packs.yaml` sobre o artefato; `eval/packs-pplx.yaml`; workflow `eval` sem Qdrant; rodada local igual à
  linha de base
- [X] T020 A comparação `e5` × `pplx` (`axon eval compare`, perfil `test`, conjunto semente): recall@5 e recall@20
  0,889 nos dois, MRR 0,722 (e5) e 0,833 (pplx), `context_accuracy` 0,9 e `current_document_rate` 1,0 nos dois; as
  duas rodadas sem regressão contra a base. Semente provisória: nada se decide; o default segue `e5` até a curadoria

## Passada de 2026-10-27 (revisão do RAG; research R13–R15)

- [X] T021 [US6] `FactRecall` e `expected_facts` em `src/axon_scouting/eval/metrics.py` (FR-014, R13), com os casos em
  `tests/eval/test_metrics.py`.
- [X] T022 [US6] `chunk_texts(root)` em `rag/index/adapters/artifact.py`; `pack.py` declara a `fact_recall` com
  `store: memory` (`_artifact_root` compartilhado com `retrievers`); caso em `tests/test_pack.py`.
- [X] T023 [US6] `eval/regression.yaml` (R15) e `tests/eval/test_regression.py` (FR-015).
- [X] T024 Semente: s08 e s09 no Manual do Escotista — Ramo Lobinho; cobertura por tipo em `tests/eval/test_golden.py`
  (R14).
- [X] T025 `tests/rag/ingestion/test_artifact_catalog.py` e o workflow `eval` sem reingestão, com o conjunto de
  regressão (FR-016, R14).
- [X] T026 Linhas de base: `eval/baseline.json` refeita (`--force`, R14) e `eval/regression-baseline.json` nova (R15);
  README do pack (corpus sem PDFs, conjunto de regressão).
- [X] T027 `branches` em `CONTEXT_FIELDS`, na derivação refeita e na validação da semente; facetas declaradas no conjunto
  de regressão; linha de base regravada (R16).
- [X] T028 `AbsenceClaimRate` (FR-017, R17), declarada pelo pack; `eval/assistants-openrouter.yaml`.
- [X] T029 Rodada com modelo real e juiz no conjunto de regressão, antes (prompt de `f84efad`) e depois (101 R36), e
  a leitura das respostas de cobertura parcial (R17).
- [X] T030 A faixa etária na redação da Regra 013; linha de base 0,90 (R18).
