---

description: "Task list for 103 — retrieval híbrido e rerank do scouting, Fase 5 (US1–US5)"
---

# Tasks: Retrieval híbrido e rerank do scouting

**Input**: Design documents from `/specs/103-scouting-retrieval/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: incluídos. A constituição exige conformidade dos seams expostos (`Retriever` e `Reranker` da 001) e do seam
alterado da 102 (ADR-025); filtros e ordem são tabelas de casos — testes primeiro, falhando antes do código.

**Organization**: a spec inteira é **Fase 5** — US1 a US5. O Foundational traz o campo `similarity` da 102
(ADR-025) e o domínio puro (configuração, filtros, chave de ordem); a US1 entrega o retriever e a tool.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: user story da tarefa (US1–US5)

## Path Conventions

- Todo caminho começa em `ai-scouting/` (submódulo → `CaioFerreiraB/ai-scouting`), salvo os que começam com `specs/`,
  `docs/` ou `CLAUDE.md` (raiz do `agentic-app`)
- `retrieval/` = `src/ai_scouting/rag/retrieval/`; `index/` = `src/ai_scouting/rag/index/`
- Comandos rodam dentro de `ai-scouting/`, com `XDG_DATA_HOME=$HOME/.local/share`; testes assíncronos com
  `asyncio.run`
- Código do pack é commitado no `ai-scouting`; no `agentic-app`, o SDD e o ponteiro do submódulo

---

## Phase 1: Setup

- [X] T001 No `pyproject.toml`, acrescentar os contratos do import-linter de research R9: `layers`
  `ai_scouting.rag.retrieval.retriever | ai_scouting.rag.retrieval.reranker` → `ai_scouting.rag.retrieval.domain`;
  `forbidden`: `ai_scouting.rag.retrieval` ↛ `ai_scouting.rag.index.domain`, `ai_scouting.rag.index.ports`,
  `ai_scouting.rag.index.adapters`, `ai_scouting.rag.ingestion`, `qdrant_client`, `onnxruntime`, `tokenizers`, `numpy`,
  `snowballstemmer`, `pypdfium2`, `yaml`
- [X] T002 Criar o esqueleto: `retrieval/__init__.py` (docstring: retriever e reranker do scouting, spec 103),
  `retrieval/domain/__init__.py` e `tests/rag/retrieval/__init__.py` (vazio); `retriever.py` e `reranker.py` nascem nas
  US1 e US4 (o contrato de camadas da T001 exige que os módulos existam — criar os dois com só a docstring)

---

## Phase 2: Foundational (bloqueia todas as histórias)

**⚠️ CRITICAL**: a similaridade da 102 e o domínio (configuração, filtros, ordem) servem a todas as histórias.

- [X] T003 [P] Acrescentar a `tests/rag/index/test_conformance.py` (alvos memória, Qdrant local e servidor) os casos do
  ADR-025: todo resultado de `search` tem `similarity` em `[-1, 1]`; um trecho com o mesmo texto da pergunta tem a maior
  similaridade; `get` devolve `similarity=None`; a similaridade de um mesmo trecho para a mesma pergunta é igual no
  `MemoryIndex` e no `QdrantIndex` (tolerância 1e-5); e a `tests/rag/index/test_model.py`: `IndexedChunk` recusa
  `similarity` fora de `[-1, 1]` (tolerância 1e-6) e `to_chunk()` continua usando `score` (a fusão)
- [X] T004 Implementar o ADR-025 na 102: `IndexedChunk.similarity: float | None = None` com a validação em
  `index/api.py`; `chunk_from_payload(payload, score=None, similarity=None)` em `index/domain/points.py`; no
  `MemoryIndex.search`, a similaridade é `cosine(dense_query, e.dense)`; no `QdrantIndex.search`,
  `query_points(..., with_vectors=["dense"])` e a mesma função `cosine` de `index/domain/scoring.py` sobre o vetor
  devolvido (faz T003 passar nos três alvos)
- [X] T005 [P] Escrever `tests/rag/retrieval/test_config.py`: `RetrievalConfig()` = (`default_limit=5`, `max_limit=30`);
  "`1 ≤ default_limit ≤ max_limit`" — (0, 30), (31, 30) e (5, 0) levantam `ValueError`
- [X] T006 [P] Escrever `tests/rag/retrieval/test_filters.py` com a tabela de [data-model.md](data-model.md): o
  exemplo do contrato da 101 vira o `IndexFilters` esperado (datas, `include_superseded`, `previous_version`, `branch`,
  `document_types`); só as datas → defaults `False`, sem ramo, sem tipos; `topics` não muda o resultado; `None`, sem
  `effective_from`, sem `effective_until`, data inválida (`"2026-13-01"`), `include_superseded: "sim"`, `document_types`
  que não é lista e chave desconhecida (`"tema"`) → `InvalidFilters` nomeando a chave; ramo ou tipo fora do vocabulário
  → `InvalidFilters` (o `ValueError` do `IndexFilters` traduzido)
- [X] T007 [P] Escrever `tests/rag/retrieval/test_ordering.py`: `marks(indexed, filters)` dá `branch_match` só com ramo
  pedido e igual ao do trecho (geral não casa) e `type_match` só com `document_types` pedidos e o tipo dentro; a chave
  `(-fusion_score, status != vigente, not branch_match, not type_match, chunk_id)` ordena uma tabela de chunks (fusão
  maior primeiro; no empate, vigente; depois ramo; depois tipo; depois `chunk_id`); `ordered(chunks)` põe os chunks sem
  `fusion_score` nos metadados depois dos anotados, na ordem de entrada
- [X] T008 Implementar `retrieval/domain/config.py` (`RetrievalConfig`), `retrieval/domain/filters.py`
  (`InvalidFilters(key, message)`, `index_filters(raw: Mapping[str, JSONValue] | None) -> IndexFilters`) e
  `retrieval/domain/ordering.py` (`FUSION_SCORE`, `BRANCH_MATCH`, `TYPE_MATCH` como nomes de chave; `marks`,
  `sort_key`, `ordered`) — só stdlib, `ai_core_contracts` e `rag.index.api` (faz T005–T007 passarem)

**Checkpoint**: índice com similaridade nos três alvos; domínio da 103 pronto.

---

## Phase 3: User Story 1 - Busca híbrida com fusão na própria base (Priority: P1) 🎯 MVP

**Goal**: uma consulta roda densa e esparsa com fusão no índice e devolve candidatos com proveniência, score absoluto e
a ordem da fusão; o retriever também é a tool `scouting.search_docs`.

**Independent Test**: para uma pergunta com termo exato ("Regra 33") e outra parafraseada, o trecho esperado aparece
entre os candidatos.

### Tests for User Story 1

- [X] T009 [P] [US1] Escrever em `tests/rag/retrieval/test_retriever.py` (com `MemoryIndex` + `HashingEmbedder` +
  `Bm25Encoder` da 102 e um corpus sintético pequeno — POR com `regra33` e `regra5`, manual, norma): "o que diz a Regra
  33" traz `regra33` no topo (componente esparsa — US1 cen. 1); cada `Chunk` tem `chunk_id`, `document` (título),
  `version`, `status`, `section`, `page` e `score` em `[0, 1]` igual à `similarity` limitada (FR-004); `metadata` traz
  `fusion_score`, `branch_match`, `type_match` e os campos da 102; a ordem é a da chave da R4; sem `top_k` → 5; `top_k=50`
  → no máximo 30; `top_k=0` → `ValueError`; pergunta só de stopwords → `[]`; índice sem build →
  `IndexUnavailable` (FR-007); embedder divergente → `IndexMismatch`; `search_docs(retriever, collection="scouting")`
  é um `NamedRetriever` com nome `search_docs`, coleções `{"scouting"}`, descrição não vazia e o próprio retriever
- [X] T010 [P] [US1] Escrever `tests/rag/retrieval/test_integration.py`: o mesmo corpus no `QdrantIndex` em modo local
  devolve, para "o que diz a Regra 33", o mesmo topo e os mesmos `chunk_id`s que o `MemoryIndex`; e um caso com o
  `E5Embedder` (pulado sem `AI_SCOUTING_EMBEDDING_DIR`): a paráfrase "o que levar para acampar com a patrulha" traz o
  trecho de acampamento entre os 3 primeiros e com `score` maior que o de um trecho de outro tema (US1 cen. 2)

### Implementation for User Story 1

- [X] T011 [US1] Implementar `retrieval/retriever.py`: `ScoutingRetriever(index: ChunkIndex, config: RetrievalConfig =
  RetrievalConfig())` com `async search(query, *, top_k: int | None = None, filters=None) -> list[Chunk]` (filtros por
  `index_filters`, limite por R6, `index.search(query, filters=..., limit=...)`, `marks`, conversão `to_chunk()` com
  `score = min(max(similarity, 0.0), 1.0)` e os metadados de ordem, `ordered`) e `search_docs(retriever, *, collection:
  str = "scouting") -> NamedRetriever` com a descrição da tool em português neutro ("Busca trechos dos documentos
  oficiais dos Escoteiros do Brasil — POR, estatuto, resoluções e manuais. Por padrão, só os vigentes na data da
  conversa; numa consulta sobre um período passado, também as versões anteriores, marcadas como tal. Devolve cada
  trecho com documento, versão e página.") (faz T009 e T010 passarem)

**Checkpoint**: MVP — o retriever responde com a fusão, score absoluto e a tool pronta para o pack.

---

## Phase 4: User Story 2 - Só o vigente, por default (Priority: P1)

**Goal**: com os filtros default da 101 (o dia de referência), nada revogado, substituído ou rascunho aparece.

**Independent Test**: com as versões 2023 e 2026 de um manual indexadas, a busca default traz só a 2026.

### Tests for User Story 2

- [X] T012 [P] [US2] Acrescentar a `tests/rag/retrieval/test_retriever.py`: manual 2023 (`substituido`, fim em
  2026-02-28) e 2026 (`vigente`) e um rascunho 2027 indexados; filtros do dia 2026-10-07 (formato da 101) → só a 2026,
  nenhum rascunho; e, em `tests/test_purity.py`, acrescentar `ai_scouting.rag.retrieval` à lista de pacotes puros,
  trocando a varredura para subpastas (`rglob("*.py")`, para cobrir `retrieval/domain/`) — o retriever não lê o relógio
  (FR-002)

### Implementation for User Story 2

- [X] T013 [US2] Fazer T012 passar ajustando só `retrieval/domain/filters.py` ou `retrieval/retriever.py`, se preciso

---

## Phase 5: User Story 3 - Busca numa data passada (Priority: P2)

**Goal**: a consulta histórica traz o que estava vigente no período, com o status atual de cada trecho.

**Independent Test**: data de referência em 2023 traz a versão 2023, com status `substituido`.

### Tests for User Story 3

- [X] T014 [P] [US3] Acrescentar a `tests/rag/retrieval/test_retriever.py`: filtros 2023-01-01..2023-12-31 com
  `include_superseded: true` → a 2023, com `Chunk.status == "substituido"` e `metadata["superseded_by"] ==
  "manual-x-2026"`; os mesmos sem `include_superseded` → a 2023 ainda (estava em vigor no fim de 2023); `previous_version:
  true` no dia 2026-10-07 → só a 2023

### Implementation for User Story 3

- [X] T015 [US3] Fazer T014 passar ajustando só `retrieval/`, se preciso

---

## Phase 6: User Story 4 - Rerank barato na v1 (Priority: P2)

**Goal**: o reranker mantém a ordem da fusão, desempata por metadados e corta em N, sem pesos e sem modelo.

**Independent Test**: entre dois candidatos empatados na fusão, o vigente e específico do ramo fica acima do geral.

### Tests for User Story 4

- [X] T016 [P] [US4] Escrever `tests/rag/retrieval/test_reranker.py`: 30 candidatos anotados → no máximo `top_k`, na
  ordem da chave da R4 (US4 cen. 1); dois empatados na fusão, um geral e um do ramo pedido → o do ramo primeiro; o
  resultado não depende da ordem de entrada (entrada embaralhada e ordenada por `score` dão a mesma saída); chunks crus,
  como o kit da 001 (`chunk("a"), chunk("b"), chunk("c")`, `top_k=2`) → 2 chunks, todos da entrada, sem exceção (R5);
  mistura de anotados e crus → crus depois, na ordem de entrada; `top_k=0` → `ValueError`; `top_k` maior que a entrada →
  todos; o reranker é instância de `Reranker` (001) e `rerank` é assíncrono

### Implementation for User Story 4

- [X] T017 [US4] Implementar `retrieval/reranker.py`: `MetadataReranker` com `async rerank(query, documents, *, top_k:
  int = 5) -> list[Chunk]` usando `ordered` de `retrieval/domain/ordering.py` e o corte (faz T016 passar)

---

## Phase 7: User Story 5 - Filtros de contexto aplicados (Priority: P3)

**Goal**: ramo e tipos de documento publicados pela 101 restringem a busca; temas não interferem.

**Independent Test**: com filtro ramo = pioneiro, nenhum trecho de outro ramo aparece.

### Tests for User Story 5

- [X] T018 [P] [US5] Acrescentar a `tests/rag/retrieval/test_retriever.py`: com manuais do `pioneiro` e do `escoteiro`
  e um POR geral, `branch: "pioneiro"` → só pioneiro e geral, com `branch_match` verdadeiro nos do pioneiro; sem ramo →
  todos; `document_types: ["por"]` → só POR, com `type_match` verdadeiro; `topics: ["uniforme"]` acrescentado aos
  filtros não muda nenhum resultado (FR-009); um ramo sem nenhum trecho próprio combinado com `document_types` que
  nenhum trecho geral tem → `[]`, sem erro (caso de borda "nenhum resultado após filtros")

### Implementation for User Story 5

- [X] T019 [US5] Fazer T018 passar ajustando só `retrieval/`, se preciso

**Checkpoint**: todas as histórias funcionais.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T020 [P] Criar `tests/rag/retrieval/sanity.py` (roteiro do [quickstart.md](quickstart.md) §2; não é teste da
  CI): monta `QdrantIndex` + `E5Embedder` + `Bm25Encoder` com `AI_SCOUTING_QDRANT_URL`, `AI_SCOUTING_EMBEDDING_DIR` e
  `AI_SCOUTING_INDEX`, roda as cinco perguntas da tabela do quickstart com os filtros do dia (formato da 101), imprime os
  3 primeiros de cada uma com `score`, `fusion_score` e `chunk_id`, e mede o tempo de `MetadataReranker.rerank` sobre 30
  candidatos
- [X] T021 Verificação completa dentro de `ai-scouting/`: `uv run pytest` em 3.14 e em 3.12, `uv run ruff check`,
  `uv run ruff format --check`, `uv run mypy`, `uv run lint-imports`, a conformidade do índice contra o servidor
  (`AI_SCOUTING_TEST_QDRANT_URL`) e os casos com o e5 (`AI_SCOUTING_EMBEDDING_DIR`); corrigir o que quebrar
- [X] T022 Executar [quickstart.md](quickstart.md) §2 com o índice `scouting` do corpus real (reingerir a partir de
  `corpus/corpus.yaml` se o Qdrant local tiver sido recriado) e registrar no fim do quickstart, numa tabela, os scores do
  topo de cada pergunta (primeira referência para o limiar da 105) e o tempo do rerank (SC-003); corrigir divergências
  entre o resultado e o "Esperado"
- [X] T023 Com o aval do mantenedor: commit e push do `ai-scouting` e conferir os jobs do `ci.yml` verdes
- [X] T024 [P] Atualizar no `agentic-app`: `CLAUDE.md` (seção "Código", parágrafo da Fase 5: a 103 existe —
  `ScoutingRetriever` sobre `rag.index.api`, score = similaridade densa (ADR-025), ordem da fusão com desempate por
  metadados, `MetadataReranker`, tool `search_docs` com default de 5 trechos; a 102 devolve `similarity`), a linha da
  103 em `specs/README.md` (status "Fase 5 implementada (US1–US5)") e, no mesmo commit, o ponteiro do submódulo
  `ai-scouting`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup**: T001 → T002
- **Foundational**: T003 → T004; T005, T006 e T007 em paralelo → T008. Bloqueia todas as histórias
- **US1**: depende do Foundational. T009 ∥ T010 → T011
- **US2**: depende da US1 (o retriever). T012 → T013
- **US3**: depende da US1. T014 → T015
- **US4**: depende só do Foundational (a chave de ordem); T016 → T017. Pode correr junto com a US1
- **US5**: depende da US1. T018 → T019
- **Polish**: T020 depois da US4 (usa o reranker); T021 depois de todas; T022 depois de T020 e T021; T023 depois de
  T022; T024 em paralelo com T023

### Parallel Opportunities

- No Foundational, T003–T004 (102) e T005–T008 (domínio da 103) são frentes independentes
- A US4 (reranker) corre em paralelo com a US1 (retriever): arquivos distintos, mesma chave de ordem
- US2, US3 e US5 acrescentam seções distintas a `test_retriever.py` — fazer em sequência para não conflitar no arquivo

---

## Parallel Example: Foundational e US1

```bash
Task: "tests/rag/index/test_conformance.py + test_model.py — similarity (T003)"
Task: "tests/rag/retrieval/test_config.py (T005)"
Task: "tests/rag/retrieval/test_filters.py (T006)"
Task: "tests/rag/retrieval/test_ordering.py (T007)"

# depois do Foundational:
Task: "tests/rag/retrieval/test_retriever.py — US1 (T009)"
Task: "tests/rag/retrieval/test_integration.py (T010)"
Task: "tests/rag/retrieval/test_reranker.py — US4 (T016)"
```

---

## Implementation Strategy

### MVP (US1)

1. Setup: import-linter e esqueleto
2. Foundational: similaridade na 102 (ADR-025) + configuração, filtros e ordem
3. US1: retriever e tool — **PARE e VALIDE**: termo exato e paráfrase (com o e5), score absoluto, erros explícitos
4. US2, US3 (vigência), US4 (rerank), US5 (ramo e tipos) — **PARE e VALIDE** cada uma
5. Polish: sanidade com o corpus real, verificação, CI, documentação e ponteiro do submódulo

### Depois desta fase

- 101 US5: publicar `search_docs` e o `MetadataReranker` no `pack.py`, manifest com `rag_first` e `requires_collections`
- 005 US3–US4: `rag_first` com o portão sobre o `score` (similaridade)
- 104: publicação dos validators

---

## Notes

- `rag.retrieval` só importa stdlib, `ai_core_contracts` e `rag.index.api` — o import-linter (T001) barra o resto
- Nenhum peso numérico no rerank (princípio X); quantidades são `RetrievalConfig`
- O retriever nunca lê o relógio: as datas vêm nos filtros da 101 (FR-002)

---

## Passada de 2026-10-21 ([ADR-043](../../docs/adr/ADR-043-indice-do-scouting-gerado-no-desenvolvimento.md); research R12)

- [X] T025 Nada a mudar no retriever; a composição do embedder é da 101 (T073) e a prova, da integração do `rag_first`
