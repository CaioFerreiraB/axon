# Implementation Plan: Retrieval híbrido e rerank do scouting (Fase 5)

**Branch**: `103-scouting-retrieval` | **Date**: 2026-10-08 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/103-scouting-retrieval/spec.md`

**Architecture inputs** *(PROJECT OVERRIDE — agentic-app)*: before filling Technical Context, READ
`/specs/103-scouting-retrieval/design.md` (including its "Portas e adapters" section) and every ADR listed
in the spec's Module Boundary, plus ADR-012 (architectural style). Decisions recorded there are
**pre-approved**: carry them into this plan and into `research.md` as
"Decision / Rationale (ADR-xxx) / Alternatives", do not re-research them. Any deviation requires a
new ADR in `docs/adr/` and must be listed in Complexity Tracking.

Insumos lidos: [design.md](design.md), ADR-006, ADR-012, ADR-013; as três clarificações de 2026-10-08; o índice da 102
já implementado (`ai_scouting.rag.index.api`); os contratos `Retriever`, `Reranker`, `NamedRetriever` e
`RETRIEVAL_TOOL_PARAMETERS` (001); o gateway da 004 (como a tool de recuperação chama o retriever); o kit de
conformidade da 001 (como chama o reranker); o contrato de filtros da 101; a 005 (portão por melhor score, união de
packs por score). Sonda de 2026-10-08: o Qdrant devolve os vetores densos numa busca com fusão (servidor e modo local).
A clarificação 1 muda o seam da 102 (campo aditivo `similarity`): registrada no
[ADR-025](../../docs/adr/ADR-025-indice-do-scouting-devolve-a-similaridade-densa.md), com o contrato e o data-model da
102 atualizados. O design.md ganhou duas notas de origem (score e desempate).

## Summary

Implementar no `ai-scouting` o retriever e o reranker do scouting sobre o seam do índice da 102. O `ScoutingRetriever`
traduz os filtros que a 101 publica (vigência como intervalo, consulta histórica, versão anterior, ramo, tipos; temas
ignorados) para `IndexFilters`, sem ler relógio, chama a busca híbrida com fusão nativa e devolve `Chunk`s da 001 com
proveniência completa e `score` = similaridade densa (o número absoluto que o portão do `rag_first` precisa); a ordem é
a da fusão, com empates desfeitos por metadados (vigente, ramo específico, tipo sugerido) sem nenhum peso. O
`MetadataReranker` aplica a mesma ordem a partir das marcas gravadas nos metadados e corta em N. O retriever também é a
tool `scouting.search_docs` do loop agêntico, com um default pequeno de trechos. Junto, a 102 passa a devolver a
similaridade em cada resultado (ADR-025). Escopo: **US1–US5**.

## Technical Context

**Language/Version**: Python ≥ 3.12 (piso do pack); suíte em 3.12 e 3.14

**Primary Dependencies**: nenhuma nova — `ai-core-contracts` (contratos 001) e o índice da 102 (`rag.index.api`); os
adapters do índice (Qdrant, e5, BM25) entram só nos testes de integração e na sanidade

**Storage**: N/A — a 103 lê o índice da 102; nada persiste

**Testing**: pytest; domínio por tabela; retriever e reranker contra o `MemoryIndex` da 102; conformidade do
`Reranker` com chunks crus (como o kit da 001); integração com o `QdrantIndex` em modo local; sanidade com o e5 e o
corpus real (quickstart); a conformidade do índice da 102 ganha os casos de `similarity`

**Target Platform**: o processo do core no hardware alvo (ARM64, 2 OCPU, 12 GB), via o pack

**Project Type**: módulo de pack de domínio (capacidades `Retriever`/`Reranker` da 001)

**Performance Goals**: o rerank v1 é uma ordenação de até 30 itens — microssegundos (SC-003); o custo da recuperação é
o da 102 (codificar a pergunta no e5 + uma consulta ao Qdrant)

**Constraints**: nenhum relógio (FR-002); nenhum peso numérico no rerank (princípio X); erro explícito, nunca vazio
silencioso (FR-007); só `rag.index.api` da 102 (princípio XIII); quantidades provisórias e configuráveis (FR-008)

**Scale/Scope**: 1 pacote (`rag/retrieval`: `domain/`, `retriever.py`, `reranker.py`); 1 campo novo no seam da 102;
corpus inicial de 413 chunks

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Resultado | Evidência |
|---|---|---|
| I. Núcleo agnóstico | ✅ | Tudo no `ai-scouting`; nada muda no `ai-core/` |
| II. Seams | ✅ | Consome `Retriever`/`Reranker`/`Chunk`/`NamedRetriever` (001), o índice (102, só `api`) e os filtros da 101 (dados opacos pelo core); a mudança no seam da 102 tem ADR-025 com os consumidores listados |
| III. O core orquestra | ✅ | Retriever e reranker são capacidades; quem decide recuperar, portão e escalada é a 005 |
| IV. Assistant é a fronteira | ✅ | A tool só aparece se o grant concede a coleção (`NamedRetriever.collections`); os filtros vêm da fatia do pack, nunca do modelo |
| V. Determinismo | ✅ | Filtros e ordem são funções puras; nenhuma chamada de modelo; o contexto da tool no loop é pequeno (default 5) |
| VI. Conteúdo externo | ✅ | Os trechos voltam ao core como dados; a cerca é do gateway (004) |
| VII. Falha fechada | ✅ | Filtros ausentes ou fora do contrato → `InvalidFilters`; índice indisponível ou divergente → erro tipado, nunca `[]` |
| VIII. Modelos por papel | N/A | Sem LLM; o embedder é o da 102 |
| IX. Proveniência e vigência | ✅ | Vigente por default; consulta histórica com status atual preservado; proveniência completa em cada `Chunk` |
| X. Medir antes de calibrar | ✅ | Desempate sem pesos; quantidades e limiar provisórios e configuráveis; a 105 mede |
| XI. Streaming | N/A | — |
| XII. Simplicidade | ✅ | Sem portas nem adapters próprios; o rerank v1 é uma ordenação; `topics` ignorados |
| XIII. Portas e adapters | ✅ | Ver gate abaixo |

**Module boundary gate** *(PROJECT OVERRIDE — principle II, mandatory)*:

- [x] Source changes stay inside this module's paths — `ai-scouting/src/ai_scouting/rag/retrieval/**`,
  `ai-scouting/tests/rag/retrieval/**`; toques declarados: `rag/index/api.py` e os dois adapters do índice + a
  conformidade da 102 (ADR-025), `pyproject.toml` (import-linter); no `agentic-app`, o SDD da 103, o ADR-025 e o
  contrato/data-model da 102
- [x] Every consumed seam is listed with its owner spec; no internals of other modules are used — 001 (`Retriever`,
  `Reranker`, `Chunk`, `NamedRetriever`, `JSONValue`), 102 (`ChunkIndex`, `IndexFilters`, `IndexedChunk`,
  `ValidityStatus`, `IndexUnavailable`, `IndexMismatch` — só `rag.index.api`), 101 (formato de `retrieval_filters`,
  como dado)
- [x] Every seam this module exposes has a conformance test planned — [contracts/retrieval.md](contracts/retrieval.md):
  o `Retriever` e o `Reranker` com os casos das US e a regra do kit da 001 para o reranker
- [x] No seam changes — or each change has an ADR and the affected consumer specs are listed — ADR-025 (102: campo
  aditivo; consumidores 103 e 106; 104 não muda)
- [x] Import boundaries (import-linter) cover the new code — R9

**Ports & adapters gate** *(PROJECT OVERRIDE — principle XIII, ADR-012, mandatory)*:

- [x] The module follows `api.py` / `domain/` / `ports.py` / `service.py` / `adapters/` — `domain/` (puro) e os dois
  implementadores dos contratos (`retriever.py`, `reranker.py`), que fazem o papel de `service.py`; sem `api.py` (o seam
  exposto são os contratos da 001), sem `ports.py`/`adapters/` (a 103 não faz I/O próprio; o índice é um seam
  injetado — design.md, "Portas e adapters")
- [x] `api.py`, `domain/`, `ports.py` and `service.py` import no infrastructure framework — só stdlib,
  `ai_core_contracts` e `rag.index.api`; o import-linter proíbe as bibliotecas de infraestrutura em `rag.retrieval`
- [x] Other modules are imported only through their `api.py` — da 102, só `rag.index.api`
- [x] All I/O, time, randomness, secrets and trace go through a secondary port; `domain/` does no I/O — a única I/O é
  a do índice (seam); sem relógio (as datas vêm nos filtros), sem aleatoriedade, sem segredo; o trace da recuperação é
  do core (005)
- [x] Every secondary port exists for I/O, non-determinism or a planned swap — nenhuma porta nova; o reranker v2/v3
  entra como adapter quando existir
- [x] Every secondary port has an in-memory adapter and a conformance suite — N/A (nenhuma porta); os testes usam o
  `MemoryIndex` da 102
- [x] Services and adapters of other modules are instantiated only in the composition root — a 103 recebe o índice
  pronto; montar `QdrantIndex` + retriever + reranker é do `pack.py` (101 US5)

**Resultado do gate (antes da Phase 0)**: PASS.

## Project Structure

### Documentation (this feature)

```text
specs/103-scouting-retrieval/
├── spec.md
├── design.md            # notas de origem: score = similaridade (ADR-025), rerank v1 = desempate sem pesos
├── plan.md              # este arquivo
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   └── retrieval.md     # ScoutingRetriever, MetadataReranker, search_docs
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
ai-scouting/
├── pyproject.toml                         # + contratos do import-linter para rag.retrieval (R9)
├── src/ai_scouting/rag/
│   ├── index/                             # 102 — toque do ADR-025
│   │   ├── api.py                         # + IndexedChunk.similarity
│   │   ├── domain/points.py               # chunk_from_payload(..., similarity=…)
│   │   └── adapters/{qdrant.py,memory.py} # similaridade calculada com os vetores densos devolvidos
│   └── retrieval/
│       ├── __init__.py
│       ├── domain/
│       │   ├── __init__.py
│       │   ├── config.py                  # RetrievalConfig (R6)
│       │   ├── filters.py                 # index_filters(raw) -> IndexFilters; InvalidFilters (R3)
│       │   └── ordering.py                # marcas e chave de ordem (R4, R5)
│       ├── retriever.py                   # ScoutingRetriever, search_docs (R2, R6–R8)
│       └── reranker.py                    # MetadataReranker (R4, R5)
└── tests/rag/
    ├── index/test_conformance.py          # + casos de similarity (ADR-025)
    └── retrieval/
        ├── __init__.py
        ├── test_filters.py                # tabela da R3
        ├── test_ordering.py               # chave e marcas (R4, R5)
        ├── test_retriever.py              # US1, US2, US3, US5; FR-004, FR-007, FR-009; limites (R6)
        ├── test_reranker.py               # US4; chunks crus (kit da 001)
        ├── test_integration.py            # QdrantIndex local + HashingEmbedder
        └── sanity.py                      # roteiro do quickstart §2 (e5 + corpus real; não é teste da CI)
```

**Structure Decision**: o layout do design.md, sem `adapters/` até existir um reranker v2/v3; a chave de ordem fica em
`domain/` para o retriever e o reranker usarem a mesma.

## Seam Notes for Consumers

| Consumidor | O que precisa saber |
|---|---|
| 101 US5 | `retrievers()` → `[search_docs(ScoutingRetriever(index, config), collection=<nome do índice>)]`; `reranker()` → `MetadataReranker()`; o manifest declara `requires_collections` com o mesmo nome e `preferred_flow="rag_first"`; `RetrievalConfig` pode vir do `config_schema` |
| 005 US3 | Pedir os candidatos com `top_k` explícito (20–30); o `score` é a similaridade em `[0, 1]` — é ele que o limiar compara; exceção do retriever é erro explícito, não "sem resultados"; o rerank não depende da ordem de entrada |
| 004 (sem mudança) | A tool `scouting.search_docs` sem `top_k` devolve 5 trechos já ordenados |
| 104 | `Chunk.status` é o id ASCII da 102; `Chunk.document` é o título do catálogo; `Chunk.metadata` traz `document_id` e as datas |
| 105 | Botões: `default_limit`, `max_limit`, o `top_k` de candidatos da 005, o N do rerank e o limiar do portão (escala da similaridade do e5) |
| 102 | Implementa `similarity` (ADR-025) nesta passada; nenhum outro consumidor muda |

## Constitution Check — pós-design (Phase 1)

Reavaliado com [data-model.md](data-model.md), [contracts/retrieval.md](contracts/retrieval.md) e
[quickstart.md](quickstart.md): **PASS**.

- II: o único seam alterado (102) tem ADR, contrato e data-model atualizados; a 103 não importa nada além de
  `rag.index.api`.
- V/X: a chave de ordem não tem número; as quantidades são configuração com defaults dentro das faixas da spec.
- VII: a tabela de erros do data-model cobre filtros, índice e `top_k`.
- IX: a tabela de verificação do contrato cobre vigente por default, histórico com status atual e proveniência.

## Complexity Tracking

> Nenhuma violação. Complexidade adicional justificada (princípio XII):

| Complexidade | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Campo `similarity` no seam da 102 (ADR-025) | o portão da 005 e a união de packs precisam de um score absoluto | o RRF é por posição; uma segunda busca só densa dobraria a latência |
| Marcas de ordem nos metadados do `Chunk` | o reranker não recebe os filtros e não pode depender da ordem de entrada (a 005 une por score) | passar filtros ao reranker mudaria o contrato 001 |
