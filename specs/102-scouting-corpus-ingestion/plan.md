# Implementation Plan: Ingestão do corpus, chunking estrutural e modelo de vigência (Fase 5)

**Branch**: `102-scouting-corpus-ingestion` | **Date**: 2026-10-07 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/102-scouting-corpus-ingestion/spec.md`

**Architecture inputs** *(PROJECT OVERRIDE — agentic-app)*: before filling Technical Context, READ
`/specs/102-scouting-corpus-ingestion/design.md` (including its "Portas e adapters" section) and every ADR listed
in the spec's Module Boundary, plus ADR-012 (architectural style). Decisions recorded there are
**pre-approved**: carry them into this plan and into `research.md` as
"Decision / Rationale (ADR-xxx) / Alternatives", do not re-research them. Any deviation requires a
new ADR in `docs/adr/` and must be listed in Complexity Tracking.

Insumos lidos: [design.md](design.md), ADR-010, ADR-012, ADR-013 e ADR-021; as cinco clarificações de 2026-10-07; a
constituição (stack: "Qdrant — adapter do índice do scouting"). Consumidores conferidos: 103 (spec e design), 104
(data-model e `validators/notice.py`: status dobrados), 101 (contrato `retrieval_filters`, léxico). Verificado em
2026-10-07: PyPI (wheels `aarch64` e Python 3.12–3.14 de todas as dependências novas), Hugging Face (revisão e sha256 do
`multilingual-e5-small` em ONNX) e uma sonda contra o Qdrant `v1.19.2` e o modo local do `qdrant-client` 1.19.1
(research R12). Quatro pontos do design.md foram refinados antes de existir implementação ou consumidor e ganharam nota
de origem no próprio arquivo: `IndexFilters` com intervalo e `previous_version` (101 clarificação 4 — R5), `version()`
assíncrono e `score` no `IndexedChunk` (R14), as portas de codificação e escrita em `rag/index/ports.py` (R16) e o
`DocumentStore` decidido como payload no próprio build (R15). O modelo de embedding sai da tabela "em aberto" para a
escolha provisória da clarificação 2. Nenhum ADR novo: nenhum seam implementado muda.

## Summary

Construir o índice do scouting e a ingestão offline no `ai-scouting`. O curador mantém um catálogo `corpus.yaml` (uma
entrada por versão de documento, com tipo, ramo, datas e `supersedes`) e roda `ai-scouting-corpus ingest`: o catálogo
é validado por inteiro, a vigência de cada linhagem é derivada sem relógio (status pela posição na linhagem; vigência
numa data pelas datas), os PDFs são lidos com PDFium, normas são divididas por artigo ou regra com o caminho ancestral
como prefixo, manuais em janelas que não cortam frase, e cada chunk ganha id determinístico, vetor denso
(`multilingual-e5-small` em ONNX, no processo) e esparso (BM25 com stemmer português, IDF no Qdrant). Cada execução é
tudo ou nada e publica um build novo do índice por troca atômica de alias, reaproveitando os vetores do que não mudou;
`reindex` recodifica tudo. O seam `ChunkIndex` faz busca híbrida com RRF nativo e os filtros de vigência, ramo e tipo,
e recusa a busca se o modelo de embedding diverge do registrado. O texto original de cada página fica no build e é
recuperável de qualquer chunk. Escopo: **US1–US5** (a spec inteira).

## Technical Context

**Language/Version**: Python ≥ 3.12 (piso do pack, 101 R3); suíte em 3.12 e 3.14; o core roda o pack em 3.14

**Primary Dependencies**: `ai-core-contracts>=0.1,<0.2` (já existente); novas — `qdrant-client>=1.19,<2`,
`onnxruntime>=1.24.2`, `tokenizers>=0.20,<1`, `numpy`, `snowballstemmer>=3,<4`, `pypdfium2>=5,<6`, `pyyaml>=6,<7`;
desenvolvimento: `fpdf2` (PDFs sintéticos). Modelo: `intfloat/multilingual-e5-small`, revisão `614241f6…`, ONNX fp32
(R2, R10)

**Storage**: Qdrant — um build por coleção, alias = nome do índice, versão do índice na `metadata` da coleção, pontos
de chunk (denso + esparso com IDF) e pontos de documento sem vetor com o texto original (R12, R15). Nada em Postgres

**Testing**: pytest; domínio puro por tabela e por propriedade; serviço com adapters em memória (aceitação US1–US5);
uma suíte de conformidade do índice contra `MemoryIndex`, `QdrantIndex` em modo local (sempre) e servidor
(`AI_SCOUTING_TEST_QDRANT_URL`); suítes das portas `Embedder` (e5 real só com `AI_SCOUTING_EMBEDDING_DIR`),
`SparseEncoder` e `DocumentParser` (PDFs gerados com `fpdf2`); import-linter; mypy strict

**Target Platform**: busca no processo do core, imagem Linux ARM64 (2 OCPU, 12 GB, sem GPU); ingestão offline onde o
curador estiver (máquina dele ou o container da instalação), falando com o mesmo Qdrant

**Project Type**: módulo de um pack de domínio (biblioteca do pack + CLI offline)

**Performance Goals**: codificar a pergunta em dezenas de ms na CPU alvo (e5-small, 384 dimensões) — uma fração da
chamada de modelo (5–15 tok/s); reingestão sem mudança sem recodificar nada; reindexação completa do corpus inicial
medida e anotada como primeira linha do SC-004

**Constraints**: nenhum relógio na derivação de vigência; nenhum download em runtime (modelo fixado por revisão e
sha256); falha fechada (catálogo inválido → nada aplicado; modelo divergente → busca recusada; índice ausente → erro,
não vazio); nenhum número calibrado — janela 300–600 tokens estimados e BM25 (`k1=1.2`, `b=0.75`, `avgdl=256`) são
provisórios e entram na versão do índice para a 105 medir (princípio X)

**Scale/Scope**: corpus inicial de 4 documentos (SC-005), dezenas no horizonte; milhares de chunks; 2 pacotes
(`rag/index`, `rag/ingestion`), 6 portas secundárias + o seam, 1 CLI com 5 subcomandos

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Resultado | Evidência |
|---|---|---|
| I. Núcleo agnóstico | ✅ | Tudo no `ai-scouting`; nenhuma linha do `ai-core/` muda |
| II. Seams | ✅ | Consome só o `Chunk` da 001; expõe o seam *Índice do scouting* (modelo + `ChunkIndex`), com suíte de conformidade; não importa 101, 103 nem 104 |
| III. O core orquestra | ✅ | Ingestão é processo offline do pack; a busca entra no core só pelo retriever da 103 |
| IV. Assistant é a fronteira | ✅ | O índice não amplia acesso: a 103 o expõe como retriever, e o core só o oferece se o grant tiver a coleção |
| V. Determinismo | ✅ | Catálogo, linhagem, estrutura, janelas, ids e filtros são funções puras; nenhuma chamada de LLM na ingestão |
| VI. Conteúdo externo | ✅ | O texto dos chunks é dado; a cerca no contexto é do core (004) e a instrução "dado, nunca instrução" é da 101 |
| VII. Falha fechada | ✅ | Tudo ou nada por execução (R13); `IndexMismatch` (FR-012) e `IndexUnavailable` (103 FR-007); campo desconhecido no catálogo é erro |
| VIII. Modelos por papel | N/A | Embedding não é papel de LLM do core; o modelo é explícito e fixado por revisão e hash |
| IX. Proveniência e vigência | ✅ | Original bruto por página preservado (R15); status e datas em cada chunk; no máximo uma vigente por linhagem, por construção (R4) |
| X. Medir antes de calibrar | ✅ | e5-small provisório (clarificação 2); números de janela e BM25 gravados na versão do índice; nenhum limiar inventado (R6, R8, R11) |
| XI. Streaming | N/A | — |
| XII. Simplicidade | ✅ | Um caminho para ingestão e reindexação; sem extras de instalação; sem porta para o catálogo; sem originais fora do Qdrant; sem trava distribuída |
| XIII. Portas e adapters | ✅ | Ver gate abaixo |

**Module boundary gate** *(PROJECT OVERRIDE — principle II, mandatory)*:

- [x] Source changes stay inside this module's paths — `ai-scouting/src/ai_scouting/rag/{index,ingestion}/**`,
  `ai-scouting/tests/rag/**`, `ai-scouting/tests/fixtures/**`; toques declarados: `pack.py` (só a função
  `corpus_cli`, a composition root da CLI — R1, R17), `pyproject.toml`, `uv.lock`, `.github/workflows/ci.yml`; no
  `agentic-app`, só o SDD e o ponteiro do submódulo
- [x] Every consumed seam is listed with its owner spec; no internals of other modules are used — `Chunk` e `JSONValue`
  (001, `ai_core_contracts`); os ids de tipo e ramo coincidem com o léxico da 101 por valor, sem import (R3)
- [x] Every seam this module exposes has a conformance test planned — [contracts/chunk-index.md](contracts/chunk-index.md):
  uma suíte contra memória, Qdrant local e Qdrant servidor
- [x] No seam changes — o seam *Índice do scouting* nasce aqui; os refinamentos do design.md (R5, R14) acontecem antes
  de qualquer implementação ou consumidor, e as specs consumidoras (103, 106) o citam só pelo nome
- [x] Import boundaries (import-linter) cover the new code — R18

**Ports & adapters gate** *(PROJECT OVERRIDE — principle XIII, ADR-012, mandatory)*:

- [x] The module follows `api.py` / `domain/` / `ports.py` / `service.py` / `adapters/` — `rag/index/` tem `api.py`
  (seam), `domain/` (filtros, pontuação em memória, ids de ponto), `ports.py` e `adapters/`; não tem `service.py`
  porque o seam é implementado direto pelos adapters de armazenamento (a busca é delegada ao Qdrant — design.md).
  `rag/ingestion/` tem `domain/`, `ports.py`, `service.py` e `adapters/`; não tem `api.py` porque não expõe seam (a
  entrada é a CLI)
- [x] `api.py`, `domain/`, `ports.py` and `service.py` import no infrastructure framework — só stdlib e
  `ai_core_contracts`; `qdrant_client`, `onnxruntime`, `tokenizers`, `numpy`, `snowballstemmer`, `pypdfium2` e `yaml`
  só em `adapters/` (import-linter, R18)
- [x] Other modules are imported only through their `api.py` — a ingestão importa `rag.index.api` e `rag.index.ports`
  (mesmo módulo, 102); `context`, `prompts`, `validators` e a futura `rag.retrieval` só podem importar
  `rag.index.api`; `api.py` não importa o resto do índice
- [x] All I/O, time, randomness, secrets and trace go through a secondary port; `domain/` does no I/O — Qdrant,
  modelo e PDF atrás de portas; tempo pela porta `Clock` (nome do build e `built_at`); a chave do Qdrant só no
  adapter, lida pela composição; sem aleatoriedade (ids por `uuid5`); trace não se aplica (processo offline; a busca é
  rastreada pelo core no evento de tool)
- [x] Every secondary port exists for I/O, non-determinism or a planned swap — `Embedder` (troca prevista:
  bge-m3, hospedado), `SparseEncoder` (troca prevista com o bge-m3), `IndexWriter`/`DocumentStore` (I/O),
  `DocumentParser` (I/O), `Clock` (tempo); o catálogo não é porta (entrada da CLI), nem as regras de estrutura
- [x] Every secondary port has an in-memory adapter and a conformance suite that also runs against the real adapter — R16
- [x] Services and adapters of other modules are instantiated only in the composition root — `pack.py` monta a CLI
  (`corpus_cli`); a montagem do `QdrantIndex` para a busca é da US5 da 101

**Resultado do gate (antes da Phase 0)**: PASS.

## Project Structure

### Documentation (this feature)

```text
specs/102-scouting-corpus-ingestion/
├── spec.md
├── design.md            # notas de origem: filtros por intervalo, version() assíncrono, portas no índice, originais no build, e5-small provisório
├── plan.md              # este arquivo
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── chunk-index.md     # seam ChunkIndex + portas do índice e suas suítes
│   ├── corpus-catalog.md  # formato e regras do corpus.yaml
│   └── ingestion-cli.md   # ai-scouting-corpus: configuração, subcomandos, saída
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
ai-scouting/                                   # submódulo → CaioFerreiraB/ai-scouting (ADR-021)
├── pyproject.toml                             # dependências novas (R2), script ai-scouting-corpus, import-linter (R18), mypy
├── uv.lock
├── .github/workflows/ci.yml                   # + job qdrant (serviço qdrant/qdrant:v1.19.2, AI_SCOUTING_TEST_QDRANT_URL)
├── src/ai_scouting/
│   ├── pack.py                                # + corpus_cli(): compõe a CLI (imports pesados dentro da função)
│   └── rag/
│       ├── __init__.py
│       ├── index/                             # seam "Índice do scouting" — consumido por 103, 106; 104 (modelo)
│       │   ├── api.py                         # ValidityStatus, DocumentType, BRANCHES, IndexedChunk, IndexFilters,
│       │   │                                  # EmbeddingModel, IndexVersion, ChunkIndex, IndexUnavailable, IndexMismatch
│       │   ├── domain/
│       │   │   ├── filters.py                 # semântica de IndexFilters (R5) — predicado puro
│       │   │   ├── scoring.py                 # cosseno, IDF e RRF da emulação em memória; desempate determinístico
│       │   │   └── points.py                  # uuid5 de chunk e documento; campos de documento de um chunk
│       │   ├── ports.py                       # Embedder, SparseEncoder, IndexWriter, DocumentStore + tipos de escrita
│       │   └── adapters/
│       │       ├── qdrant.py                  # QdrantIndex: ChunkIndex + IndexWriter + DocumentStore (R12–R15)
│       │       ├── memory.py                  # MemoryIndex, HashingEmbedder
│       │       ├── e5.py                      # E5Embedder (ONNX, mean pooling, prefixos; R10) + fetch da revisão fixada
│       │       └── bm25.py                    # Bm25Encoder (R11)
│       └── ingestion/
│           ├── domain/
│           │   ├── catalog.py                 # CatalogEntry, validação (R3)
│           │   ├── lineage.py                 # Validity, derivação e erros de linhagem (R4)
│           │   ├── text.py                    # limpeza: cabeçalho/rodapé, hifenização, linhas com página (R7)
│           │   ├── structure.py               # marcadores normativos, unidades, prefixo (R7)
│           │   ├── chunking.py                # ChunkingPolicy, janelas narrativas, frases (R8)
│           │   ├── ids.py                     # chunk_id, doc_key, content_key (R9, R13)
│           │   └── report.py                  # IngestionReport
│           ├── ports.py                       # DocumentParser, Clock
│           ├── service.py                     # IngestionService: ingest/reindex (R13), status, original
│           └── adapters/
│               ├── pdfium.py                  # PdfiumParser (R6)
│               ├── catalog_yaml.py            # lê o corpus.yaml → mapeamentos
│               ├── clock.py                   # SystemClock
│               ├── memory.py                  # MemoryParser, FixedClock (testes)
│               └── cli.py                     # argumentos, relatório, códigos de saída (R17)
└── tests/
    ├── fixtures/
    │   ├── pdfs.py                            # geração de PDFs sintéticos com fpdf2 (norma, manual, sem texto)
    │   └── make_corpus.py                     # corpus de demonstração do quickstart
    └── rag/
        ├── index/
        │   ├── test_filters.py                # tabela da semântica R5
        │   ├── test_conformance.py            # suíte do seam + IndexWriter + DocumentStore: memória, Qdrant local, servidor
        │   ├── test_embedder.py               # suíte do Embedder: HashingEmbedder; E5Embedder com AI_SCOUTING_EMBEDDING_DIR
        │   ├── test_bm25.py                   # suíte do SparseEncoder
        │   └── test_model.py                  # IndexedChunk.to_chunk, IndexVersion.compatible_with
        └── ingestion/
            ├── test_catalog.py                # FR-011: campos faltantes, inválidos, desconhecidos
            ├── test_lineage.py                # FR-007, FR-008, SC-003; erros de linhagem
            ├── test_text.py                   # limpeza
            ├── test_structure.py              # US2, SC-001: unidade = chunk, prefixo, faixa de páginas, normativo sem unidade
            ├── test_chunking.py               # US4: faixa, frase inteira, seção como fronteira (propriedade)
            ├── test_ids.py                    # FR-005, R9: formato, desempate, caracteres
            ├── test_service.py                # aceitação US1–US5 com adapters em memória; tudo ou nada; reaproveitamento
            ├── test_parser.py                 # suíte do DocumentParser: PdfiumParser e MemoryParser
            ├── test_cli.py                    # códigos de saída, relatório, chave do Qdrant nunca impressa
            └── test_integration.py            # pdfium + QdrantIndex (local) + HashingEmbedder, ponta a ponta
```

**Structure Decision**: o layout do design.md com o hexágono do ADR-012 dentro de cada pacote, as portas de codificação
e escrita no índice (R16) e o `pack.py` como composition root também do processo offline (R1, R17).

## Seam Notes for Consumers

| Consumidor | O que precisa saber |
|---|---|
| 103 (Fase 5) | Importa só `ai_scouting.rag.index.api`. Monta `IndexFilters` a partir do `retrieval_filters` da 101 (mesmas chaves: `effective_from`, `effective_until`, `include_superseded`, `previous_version`, `branch`, `document_types`; `topics` não chega ao índice). `search` já devolve só o que passa nos filtros, com `score` de RRF (por posição), ordenado e com desempate por `chunk_id`; `IndexUnavailable` e `IndexMismatch` são os erros explícitos da FR-007 dela. `IndexedChunk.to_chunk()` dá o `Chunk` da 001 |
| 104 (Fase 5) | `status` é um de `vigente`, `revogado`, `substituido`, `rascunho` (ASCII — o que ela já compara dobrado); `STATUS_LABELS` tem a forma com acento para o aviso. `Chunk.document` é o título do catálogo; o `chunk_id` não tem espaço nem colchete. Um antecessor ainda em vigor por datas, com sucessor de vigência futura, chega `substituido` (R4) |
| 101 US5 (Fase 5) | `retrievers()` monta `QdrantIndex(client, index_name, E5Embedder(dir), Bm25Encoder())` com a configuração da instalação (URL, chave, nome do índice, diretório do modelo — mesmas variáveis da CLI ou o `config_schema` do pack, decisão dela). Os ids de tipo e de ramo do léxico precisam continuar iguais a `DocumentType` e `BRANCHES` (um teste de consistência no pack) |
| 106 (Fase 8) | Lê chunks por `get(chunk_ids)` e o modelo; não precisa de nada novo |
| 105 (Fase 6) | Compara embedders e estratégias trocando o adapter de `Embedder` ou a `ChunkingPolicy` e rodando `reindex`; a versão do índice registra o que foi medido |
| Instalação (`agentic-deploy`, 002 US5) | Runtime precisa do diretório do modelo (`ai-scouting-corpus model fetch` no estágio `packs`, copiado para o `runtime`) e de um Qdrant ao lado do core; nada disso nesta passada |

## Constitution Check — pós-design (Phase 1)

Reavaliado com [data-model.md](data-model.md), [contracts/](contracts/) e [quickstart.md](quickstart.md): **PASS**.

- II: o seam publicado é exatamente o do design.md (modelo + `ChunkIndex`), com os quatro refinamentos anotados; o
  schema do Qdrant ficou no adapter (data-model, "Mapa no Qdrant — detalhe do adapter").
- V/VII: o contrato do catálogo lista cada rejeição; nenhuma rejeição aplica nada; a CLI devolve 1 com rejeição e 2
  com falha de infraestrutura.
- IX: a máquina de estados da linhagem garante uma vigente por linhagem; o `DocumentStore` devolve o original bruto da
  faixa de páginas de qualquer chunk.
- X: a versão do índice carrega a identidade da estratégia de chunking, do embedder (com hash dos pesos) e do
  codificador esparso — é o que a 105 vai variar e medir.
- XIII: cada porta da tabela do contrato tem adapter em memória e alvo real na mesma suíte.

## Complexity Tracking

> Nenhuma violação. Complexidade adicional justificada (princípio XII):

| Complexidade | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Build novo + alias a cada ingestão (R13) | leitores nunca veem estado parcial; falha no meio não toca o publicado; um caminho só para ingestão e reindexação | atualizar no lugar expõe duplicatas durante a escrita e deixa o índice misturado se falhar; troca de dimensão do embedding exigiria outro caminho de qualquer jeito |
| Adapter próprio do e5 em ONNX + `model fetch` (R10) | escolha da clarificação 2; impressão digital verificável (FR-010); runtime sem rede | `fastembed` não traz o e5-small e adiciona dependências e um registro de modelos; `sentence-transformers` exige torch |
| Três alvos na suíte do índice (memória, Qdrant local, servidor) | o adapter em memória serve aos testes da 103; o modo local cobre o adapter real em qualquer máquina; o servidor fecha diferenças de comportamento | só servidor deixaria a suíte padrão dependente de Docker; só memória não testaria o adapter real |
| `successor_expiry_date` denormalizado (R4, R5) | `previous_version` (101) num filtro só | buscar a versão anterior exigiria duas consultas e agrupamento por linhagem na 103 |
