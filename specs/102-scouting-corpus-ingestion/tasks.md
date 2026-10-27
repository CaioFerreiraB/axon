---

description: "Task list for 102 — ingestão do corpus e índice do scouting, Fase 5 (US1–US5)"
---

# Tasks: Ingestão do corpus, chunking estrutural e modelo de vigência

**Input**: Design documents from `/specs/102-scouting-corpus-ingestion/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: incluídos. A constituição exige suíte de conformidade para o seam exposto (`ChunkIndex`) e para cada porta
secundária, contra o adapter em memória e o real; catálogo, linhagem, estrutura e janelas são tabelas de casos —
testes primeiro, falhando antes do código.

**Organization**: a spec inteira é **Fase 5** do roadmap — US1 a US5. As regras puras compartilhadas (modelo do
índice, catálogo, linhagem, semântica dos filtros) e o adapter em memória ficam no Foundational; a US1 entrega o
pipeline ponta a ponta para um manual, com PDF, Qdrant, e5 e CLI (o MVP).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: user story da tarefa (US1–US5)

## Path Conventions

- Todo caminho começa em `ai-scouting/` (o submódulo → `CaioFerreiraB/ai-scouting`, ADR-021), salvo os que começam
  com `specs/`, `docs/` ou `CLAUDE.md` (raiz do `agentic-app`)
- `index/` = `src/ai_scouting/rag/index/`; `ingestion/` = `src/ai_scouting/rag/ingestion/`
- Comandos rodam dentro de `ai-scouting/`, com `XDG_DATA_HOME=$HOME/.local/share`
- Testes assíncronos usam `asyncio.run`, sem `pytest-asyncio` (convenção do pack)
- Código e testes do pack são commitados no `ai-scouting`; no `agentic-app`, só o SDD e o ponteiro do submódulo

---

## Phase 1: Setup

- [X] T001 Atualizar `pyproject.toml` (research R2, R17, R18): em `dependencies`, acrescentar `qdrant-client>=1.19,<2`,
  `onnxruntime>=1.24.2`, `tokenizers>=0.20,<1`, `numpy`, `snowballstemmer>=3,<4`, `pypdfium2>=5,<6` e `pyyaml>=6,<7`;
  `[project.scripts] ai-scouting-corpus = "ai_scouting.pack:corpus_cli"`; `fpdf2` no grupo `dev`; em `[tool.mypy]`,
  `[[tool.mypy.overrides]]` com `ignore_missing_imports = true` só para os módulos sem tipos que o mypy acusar
  (`onnxruntime`, `pypdfium2.*`, `snowballstemmer`). No `[tool.importlinter]` (o `include_external_packages = true`
  já presente permite nomear pacotes externos nos contratos `forbidden`), acrescentar os contratos de R18: (a) `layers`
  `ai_scouting.rag.index.adapters` → `ai_scouting.rag.index.domain` → `ai_scouting.rag.index.ports` →
  `ai_scouting.rag.index.api` (o domínio usa os tipos das portas, como `DocumentRecord` em `with_document`); (b) `layers` `ai_scouting.rag.ingestion.adapters` → `ai_scouting.rag.ingestion.service`
  → `ai_scouting.rag.ingestion.ports | ai_scouting.rag.ingestion.domain`; (c) `forbidden`: `ai_scouting.rag.index.api`
  ↛ `ai_scouting.rag.index.domain`, `.ports`, `.adapters` e `ai_scouting.rag.ingestion`; (d) `forbidden`: os módulos
  `ai_scouting.rag.index.api`, `.domain`, `.ports`, `ai_scouting.rag.ingestion.domain`, `.ports`, `.service` ↛
  `qdrant_client`, `onnxruntime`, `tokenizers`, `numpy`, `snowballstemmer`, `pypdfium2`, `yaml`; (e) `forbidden`:
  `ai_scouting.context`, `ai_scouting.prompts`, `ai_scouting.validators` ↛ `ai_scouting.rag.ingestion`,
  `ai_scouting.rag.index.domain`, `.ports`, `.adapters`; (f) o contrato `layers` existente passa a
  `ai_scouting.pack` acima de `ai_scouting.context | ai_scouting.prompts | ai_scouting.validators | ai_scouting.rag`
- [X] T002 Criar o esqueleto: `src/ai_scouting/rag/__init__.py`, `index/__init__.py`, `index/domain/__init__.py`,
  `index/adapters/__init__.py`, `ingestion/__init__.py`, `ingestion/domain/__init__.py`,
  `ingestion/adapters/__init__.py` (docstrings de uma linha: seam do índice; pipeline offline) e
  `tests/rag/__init__.py`, `tests/rag/index/__init__.py`, `tests/rag/ingestion/__init__.py`, `tests/fixtures/__init__.py`
  vazios (evitam colisão com `tests/test_text.py`); rodar `uv lock` e `uv sync --locked` (depende de T001) e confirmar
  que `uv pip list` tem as dependências novas e **não** tem `ai-core`
- [X] T003 [P] Acrescentar ao `.github/workflows/ci.yml` o job `qdrant` (Python 3.14): `services.qdrant` com a imagem
  `qdrant/qdrant:v1.19.2` e a porta `6333:6333`, os mesmos passos de checkout, `webfactory/ssh-agent` e `setup-uv` dos
  outros jobs, `uv sync --locked` e `uv run pytest tests/rag/index` com
  `env: AI_SCOUTING_TEST_QDRANT_URL: http://localhost:6333` (research R16)

---

## Phase 2: Foundational (bloqueia todas as histórias)

**⚠️ CRITICAL**: o modelo do seam, as portas, o catálogo, a linhagem, a semântica dos filtros e o índice em memória são
usados por todas as histórias.

- [X] T004 [P] Escrever `tests/rag/index/test_model.py` ([data-model.md](data-model.md), seções do seam): valores de
  `ValidityStatus` (`vigente`, `revogado`, `substituido`, `rascunho`), `STATUS_LABELS` (`substituido` → "substituído"),
  `DocumentType` (`por`, `resolucao`, `estatuto`, `manual`, `programa_educativo`, `guia`), `NORMATIVE_TYPES` (`por`,
  `resolucao`, `estatuto`), `BRANCHES` (`lobinho`, `escoteiro`, `senior`, `pioneiro`); `IndexFilters` recusa
  `effective_from > effective_until`; `IndexedChunk` recusa `page_start < 1`, `page_end < page_start` e `chunk_id` com
  espaço ou colchete; `to_chunk()` — `document` = `document_title`, `section` = `article` ou o cabeçalho mais
  específico (subseção, seção, capítulo), `page` = `page_start`, `score` 0.0 quando `None`, `metadata` com
  `document_id`, `document_type`, `branch`, `jurisdiction`, `chapter`, `subsection`, `page_end`, datas em ISO e
  `superseded_by`, e o resultado passa no construtor do `Chunk` da 001; `IndexVersion.compatible_with` ignora `built_at`
  e difere em `chunking`, `embedding` (nome, impressão digital ou dimensões) ou `sparse`
- [X] T005 Implementar `index/api.py` conforme [contracts/chunk-index.md](contracts/chunk-index.md): `ValidityStatus` e
  `DocumentType` (`StrEnum`), `STATUS_LABELS`, `NORMATIVE_TYPES`, `BRANCHES`, `IndexedChunk`, `IndexFilters`,
  `EmbeddingModel`, `IndexVersion`, `IndexUnavailable`, `IndexMismatch` (atributos `index` e `encoder`; mensagem com os
  dois) e o `Protocol` `ChunkIndex` (`search`, `get`, `async version`); só stdlib e `ai_core_contracts` (faz T004
  passar)
- [X] T006 Implementar `index/ports.py` ([data-model.md](data-model.md), "Escrita e originais"): `SparseVector`
  (`indices: tuple[int, ...] (u32, ordenados, únicos)`, `values` do mesmo tamanho — validado), `EncodedChunk`,
  `StoredDocument`, `DocumentRecord` (`StoredDocument` + `pages`), `Build`, `Original` e os `Protocol` `Embedder`,
  `SparseEncoder`, `IndexWriter` (`published`, `documents`, `create`, `write`, `copy`, `publish`, `discard`, com as
  docstrings do contrato) e `DocumentStore` (`original`)
- [X] T007 [P] Escrever `tests/rag/index/test_filters.py`, uma linha por regra de research R5, sobre `IndexedChunk`
  sintéticos: em vigor no intervalo (`effective_date ≤ until` e `expiry_date` nulo ou `≥ from`); `include_superseded=False`
  exige `expiry_date` nulo ou `≥ until`; `include_superseded=True` aceita substituída/revogada em vigor no intervalo;
  `previous_version=True` = `superseded_by` presente, `expiry_date < until` e (`successor_expiry_date` nulo ou `≥ until`);
  `branch` aceita o ramo e `None`; `document_types` vazio = todos; `rascunho` nunca casa
- [X] T008 Implementar `index/domain/filters.py`: `matches(filters: IndexFilters, chunk: IndexedChunk) -> bool` puro
  (faz T007 passar)
- [X] T009 [P] Escrever `tests/rag/ingestion/test_catalog.py` (FR-011, [contracts/corpus-catalog.md](contracts/corpus-catalog.md)):
  catálogo válido do contrato vira `CatalogEntry`s; raiz sem `documents` ou lista vazia; cada obrigatório ausente
  (`file`, `document_id`, `version`, `type`, `title`, `jurisdiction`, `effective_date`) listado por nome, vários na mesma
  entrada numa mensagem; campo desconhecido (`expiry_dte`); `document_id` fora de `^[a-z0-9]+(-[a-z0-9]+)*$`;
  `version` fora de `^[0-9a-z]+(\.[0-9a-z]+)*$` (ex.: `2026-1`); `version` numérica no YAML (`2023` sem aspas) aceita como
  texto `"2023"` e `1.10` recusado com dica de aspas; `type` fora da tabela; `branch` fora de `BRANCHES`; `status` só
  `rascunho` ou `revogado`; `revogado` sem `expiry_date`; data inválida; `file` absoluto ou com `..` saindo do diretório;
  (`document_id`, `version`) repetido; **todos** os problemas acumulados num resultado só
- [X] T010 [P] Escrever `tests/rag/ingestion/test_lineage.py` (FR-007, FR-008, SC-003, research R4): versão única →
  `vigente`; 2023 + 2026 com `supersedes: "2023"` → 2023 `substituido`, `superseded_by = "<id>-2026"`, `expiry_date` = véspera
  do `effective_date` da 2026, `successor_expiry_date` nulo; cadeia 2019 → 2023 → 2026 (`successor_expiry_date` da 2019 =
  `expiry_date` da 2023); sucessor `rascunho` não substitui; `revogado` declarado mantém o `expiry_date`; erros —
  `supersedes` inexistente, versão substituída por duas, ciclo, sucessor com `effective_date` ≤ o do antecessor,
  `expiry_date` declarado diferente da véspera do sucessor, duas versões não rascunho sem elo (mais de uma `vigente`);
  propriedade: para qualquer catálogo aceito, no máximo uma `vigente` por `document_id`
- [X] T011 Implementar `ingestion/domain/catalog.py`: `CatalogEntry` e `validate_catalog(raw: object, base_dir:
  PurePath) -> CatalogResult` (entradas ou `CatalogProblem(entry, key, fields, message)`, todos acumulados), com a
  tabela de [data-model.md](data-model.md) — checagem de caminho só textual (dentro de `base_dir`; a existência é do
  parser) (faz T009 passar)
- [X] T012 Implementar `ingestion/domain/lineage.py`: `Validity` (`status`, `effective_date`, `expiry_date`,
  `superseded_by`, `successor_expiry_date`), `derive_lineages(entries) -> LineageResult` (validades por chave de
  documento ou `LineageProblem(document_id, message)`), sem relógio (faz T010 passar)
- [X] T013 [P] Escrever `tests/rag/ingestion/test_clock.py` (suíte da porta `Clock`, contra `SystemClock` e
  `FixedClock`): `now()` devolve `datetime` com fuso UTC; duas leituras seguidas nunca andam para trás; o `FixedClock`
  devolve sempre o valor dado (o `SystemClock`, um instante a menos de 1 s do `datetime.now(UTC)` do teste)
- [X] T014 Implementar `ingestion/ports.py` (`ParsedDocument` com `source_sha256`, `pages: tuple[str, ...]` e `parser`;
  `Protocol`s `DocumentParser.parse(path: Path) -> ParsedDocument` e `Clock.now() -> datetime` UTC),
  `ingestion/adapters/clock.py` (`SystemClock`) e `ingestion/adapters/memory.py` (`MemoryParser` com páginas por caminho —
  caminho desconhecido levanta `FileNotFoundError` —, `sha256` do texto concatenado e `parser="memory"`; `FixedClock`)
- [X] T015 [P] Escrever `tests/rag/index/test_bm25.py` (suíte da porta `SparseEncoder`, research R11): `identity()` =
  `bm25-pt-v1;k1=1.2;b=0.75;avgdl=256`; ids iguais entre duas instâncias e entre processos (valor de `crc32` fixado no
  teste); "Art. 42" produz o termo de `42`; "organização" e "organizacao" dão o mesmo termo; stopwords ("de", "que")
  somem; `encode_query` dá peso 1.0 por termo distinto; `encode_passage` cresce com a frequência e satura; texto só de
  stopwords → vetor vazio; índices ordenados e únicos
- [X] T016 Implementar `index/adapters/bm25.py` (`Bm25Encoder`): dobra de caixa e acento, tokens `[a-z0-9]+`, stopwords
  do português (lista fixa no módulo), `snowballstemmer.stemmer("portuguese")`, id `zlib.crc32(radical.encode())`, peso de
  passagem `tf·(k1+1)/(tf + k1·(1−b+b·len/avgdl))` (faz T015 passar)
- [X] T017 Implementar `index/domain/scoring.py` e `index/domain/points.py`: cosseno; IDF
  `ln(1 + (N − n + 0.5)/(n + 0.5))`; RRF `Σ 1/(posição + 2)` com posição a partir de 0 (o do Qdrant, research R20);
  chave de ordenação (`-score`, `chunk_id`); `NAMESPACE_CHUNK`/`NAMESPACE_DOCUMENT` (UUIDs fixos no módulo) e
  `chunk_point_id`/`document_point_id` por `uuid5`; `with_document(chunk, record) -> IndexedChunk` (reescreve os campos de
  documento — metadados e vigência — a partir do registro, mantendo os estruturais)
- [X] T018 [P] Escrever `tests/rag/index/test_embedder.py` (suíte da porta `Embedder`), parametrizada por alvo:
  `HashingEmbedder` sempre; `len(vetor) == model().dimensions`; norma 1 (tolerância 1e-6); determinismo;
  `embed_query(t) != embed_passages([t])[0]`; lista vazia → lista vazia
- [X] T019 Escrever `tests/rag/index/test_conformance.py` ([contracts/chunk-index.md](contracts/chunk-index.md)), com um
  fixture de alvos (por ora só `MemoryIndex`; T031 acrescenta o Qdrant) e um corpus sintético pequeno montado com
  `HashingEmbedder` + `Bm25Encoder`: `published()` é `None` num índice novo e `search` levanta `IndexUnavailable`;
  `create` → `write` → `publish` torna os chunks visíveis em `get` e `search` de uma vez; `discard` não afeta o
  publicado; `documents(build)` devolve os registros sem páginas; `copy` preserva os vetores (mesma busca, mesmos
  scores) e reescreve a vigência; `get` na ordem pedida, ausentes omitidos, `score=None`; `search` respeita `limit`,
  ordena por score com desempate por `chunk_id`, é determinística e devolve `[]` para pergunta só de stopwords; o
  termo "42" traz o chunk `art42` (componente esparsa); `version()` = a versão gravada; `create` com o mesmo `built_at`
  de um build existente gera `-2`
- [X] T020 Implementar `index/adapters/memory.py`: `HashingEmbedder(dimensions=64, fingerprint="hashing-v1")` (saco de
  palavras com hash, normalizado, prefixos distintos para pergunta e passagem, `model()` com nome `hashing-test`, a
  impressão digital e as dimensões dadas) e `MemoryIndex(index_name, embedder, sparse)` (implementa `ChunkIndex`, `IndexWriter` e `DocumentStore` por
  estrutura; filtros por `domain.filters.matches`; cosseno, IDF e RRF por `domain.scoring`; alias e builds em
  dicionários) (faz T018 e T019 passarem para o alvo em memória)

**Checkpoint**: modelo, portas, catálogo, linhagem, filtros e índice em memória prontos.

---

## Phase 3: User Story 1 - Curador ingere um documento (Priority: P1) 🎯 MVP

**Goal**: o curador registra um manual no `corpus.yaml`, roda `ai-scouting-corpus ingest` e a coleção contém os chunks
com identificador estável, metadados e as duas representações; reingerir não duplica nada.

**Independent Test**: ingerir um manual de teste e consultar o índice: todos os chunks têm texto, metadados
obrigatórios e as duas representações; a segunda ingestão reaproveita tudo, com os mesmos ids.

### Tests for User Story 1

- [X] T021 [P] [US1] Escrever `tests/rag/ingestion/test_text.py` (research R7, limpeza): linha só com número de página
  sai; linha idêntica no topo ou no rodapé de mais da metade das páginas (mínimo 3) sai; `organiza-` + `ção` (minúscula
  a seguir) vira `organização`; `guarda-` + `Chuva` (maiúscula) não é unida; espaços colapsados; cada `Line` guarda a
  página de origem (1-indexada)
- [X] T022 [P] [US1] Escrever `tests/rag/ingestion/test_ids.py` (FR-005, research R9): `chunk_id` =
  `<document_id>-<version>#<seção>@p<página>` (ex.: `man-pio-2026#4.2.1@p87`); repetição de (seção, página) ganha `~2`,
  `~3`; só ASCII minúsculo, dígitos e `-._~#@`; `doc_key = "<document_id>-<version>"`; `content_key` =
  `sha256(source_sha256 | document_type | title | parser)` muda com qualquer um dos quatro
- [X] T023 [P] [US1] Escrever em `tests/rag/ingestion/test_chunking.py` os casos base das janelas (FR-004): cabeçalho
  numerado (`4`, `4.2`, `4.2.1` + texto com maiúscula inicial, sem ponto final, até 80 caracteres) e `CAPÍTULO <n>` abrem
  seção e quebram janela; parágrafos agrupados até `window_max=600` tokens estimados (`⌈caracteres/4⌉`); prefixo
  `[<título> · 4.2 Atividades]`; seção sem número vira `s<n>`; `ChunkingPolicy().identity()` =
  `estrutural-v1;janela=300-600`
- [X] T024 [P] [US1] Criar `tests/fixtures/pdfs.py` (geração com `fpdf2`, fonte core em latin-1): `narrative_pdf(path,
  pages)` (manual com cabeçalhos numerados e parágrafos acentuados), `empty_pdf(path, n)` (páginas sem texto); e
  `tests/rag/ingestion/test_parser.py` (suíte da porta `DocumentParser` contra `PdfiumParser` e `MemoryParser`): uma
  entrada por página, na ordem; acentos preservados; `source_sha256` = sha256 dos bytes do arquivo (pdfium); PDF sem
  texto → páginas vazias (a rejeição é do serviço); arquivo inexistente → `FileNotFoundError`
- [X] T025 [P] [US1] Escrever em `tests/rag/ingestion/test_service.py` a aceitação da US1 com `MemoryParser`,
  `HashingEmbedder`, `Bm25Encoder`, `MemoryIndex` e `FixedClock`: cen. 1 — um manual vira chunks com `chunk_id`,
  todos os metadados de [data-model.md](data-model.md) e vetores denso e esparso não vazios, e o relatório lista o
  documento como "codificado"; cen. 2 — a segunda execução publica um build novo com os **mesmos** ids, nenhum
  duplicado e nenhuma chamada ao embedder (todos "reaproveitado"); tudo ou nada — entrada sem `title` → relatório com o
  problema, nada escrito, build publicado intacto; PDF sem texto em nenhuma página → rejeitado "sem camada de texto
  (OCR fora do escopo)" e página vazia isolada → aviso; documento que sai do catálogo sai do índice e aparece em
  `removed`; índice publicado com versão incompatível → `ingest` recusa ("rode `reindex`") sem escrever
- [X] T026 [P] [US1] Escrever `tests/rag/ingestion/test_cli.py` ([contracts/ingestion-cli.md](contracts/ingestion-cli.md)),
  chamando `cli.main(argv, compose)` com uma composição em memória: `ingest` com sucesso → código 0 e relatório no
  formato do contrato; rejeição → código 1 e "nada foi aplicado"; variável obrigatória ausente ou índice indisponível →
  código 2; `status` lista versão e contagens; `AI_SCOUTING_QDRANT_API_KEY` nunca aparece em saída nem em erro
- [X] T027 [P] [US1] Acrescentar a `tests/rag/index/test_embedder.py` o alvo `E5Embedder`, pulado sem
  `AI_SCOUTING_EMBEDDING_DIR`, com `model()` = (`intfloat/multilingual-e5-small`, sha256 do `model.onnx`, 384) e a
  sanidade de [quickstart.md](quickstart.md) §3 (uma paráfrase fica mais perto do trecho do que um trecho de outro tema);
  e um teste sem rede de `fetch`: arquivo presente com sha256 certo não é baixado; sha256 errado → erro nomeando o arquivo
- [X] T028 [US1] Escrever `tests/rag/ingestion/test_integration.py`: `PdfiumParser` + `QdrantIndex` em modo local
  (`AsyncQdrantClient(location=":memory:")`) + `HashingEmbedder` + `Bm25Encoder`, catálogo em `tmp_path` com um manual
  gerado por `narrative_pdf`: ingestão publica o alias, `search` acha um trecho pela frase dele, `get` devolve todos os
  ids do relatório, reingestão mantém os ids (SC-002)

### Implementation for User Story 1

- [X] T029 [US1] Implementar `ingestion/domain/text.py` (`Line`, `clean_pages(pages) -> list[Line]`) e
  `ingestion/domain/ids.py` (`doc_key`, `chunk_ids(drafts) -> list[str]` com o desempate `~k`, `content_key`) (faz T021 e
  T022 passarem)
- [X] T030 [US1] Implementar `ingestion/domain/chunking.py`: `ChunkingPolicy` (`window_min=300`, `window_max=600`,
  `strategy="estrutural-v1"`, `identity()`), `ChunkDraft` e `narrative_chunks(lines, title, policy)` com cabeçalhos,
  parágrafos e empacotamento guloso até o máximo (a divisão por frases é da US4) (faz T023 passar)
- [X] T031 [US1] Implementar `index/adapters/qdrant.py` (`QdrantIndex`, research R12, R14): construtor recebe
  `AsyncQdrantClient`, nome do índice, `Embedder` e `SparseEncoder`; `create` cria a coleção `<índice>__<built_at
  AAAAMMDDTHHMMSSZ>` (sufixo `-n` se existir) com `dense` (cosseno, dimensão do embedder) e `sparse`
  (`modifier=IDF`), `metadata={"index_version": …}` e os índices de payload (`keyword`: `kind`, `doc_key`,
  `document_id`, `status`, `branch`, `document_type`; `datetime`: `effective_date`, `expiry_date`,
  `successor_expiry_date`); `write` grava o ponto de documento sem vetor (`kind="document"`) e os de chunk
  (`kind="chunk"`, ids `uuid5`); `copy` lê os chunks do `doc_key` com vetores e regrava com `with_document`;
  `documents` faz `scroll` em `kind="document"` sem as páginas; `publish` troca o alias numa operação e apaga o build
  anterior e os órfãos `<índice>__*`; `discard`; `search` com dois `prefetch` (denso da pergunta, esparso da pergunta,
  ambos com o filtro traduzido de `IndexFilters` — a tradução cobre toda a semântica de R5 e exclui `kind="document"` e
  `rascunho`) e `FusionQuery(RRF)`, depois ordena por (`-score`, `chunk_id`); `get`; `version` lê a `metadata` do
  build atrás do alias; alias ausente ou erro de conexão → `IndexUnavailable` sem a chave. Acrescentar ao fixture de
  T019 os alvos `QdrantIndex` modo local (sempre) e servidor (`AI_SCOUTING_TEST_QDRANT_URL`, coleções com prefixo único
  por teste e limpeza no fim) e fazer T019 passar nos três
- [X] T032 [P] [US1] Implementar `index/adapters/e5.py`: `E5Embedder(model_dir)` com `onnxruntime.InferenceSession` e
  `tokenizers.Tokenizer.from_file` (truncamento em 512, padding), entradas `input_ids`, `attention_mask`,
  `token_type_ids`, *mean pooling* com a máscara e normalização L2; prefixos `passage: `/`query: `; inferência em
  `asyncio.to_thread`, em lotes; `model()` com o sha256 do `model.onnx` calculado uma vez; e `fetch(model_dir)`:
  `https://huggingface.co/intfloat/multilingual-e5-small/resolve/614241f622f53c4eeff9890bdc4f31cfecc418b3/onnx/{model.onnx,tokenizer.json}`
  com sha256 `ca456c06b3a9505ddfd9131408916dd79290368331e7d76bb621f1cba6bc8665` e
  `0b44a9d7b51c3c62626640cda0e2c2f70fdacdc25bbbd68038369d14ebdf4c39`, gravando em arquivo temporário e renomeando só
  depois de conferir (faz T027 passar)
- [X] T033 [P] [US1] Implementar `ingestion/adapters/pdfium.py` (`PdfiumParser`: lê os bytes, `sha256`, texto de cada
  página por `get_textpage().get_text_range()`, `parser = f"pdfium-{pypdfium2.version}"`) (faz T024 passar)
- [X] T034 [US1] Implementar `ingestion/domain/report.py` (`DocumentOutcome`, `IngestionReport`) e
  `ingestion/service.py` (`IngestionService(parser, embedder, sparse, writer, store, clock, policy)`), `ingest(entries_raw,
  base_dir) -> IngestionReport` pelos passos de research R13: valida catálogo, deriva linhagens, analisa todos os PDFs
  (nenhum caractere em nenhuma página → rejeição; página vazia → aviso), gera os chunks (por enquanto todos narrativos),
  monta `IndexedChunk`s com a vigência; qualquer problema → relatório sem escrita; compara `IndexVersion` configurada
  com `published()` (ausente → primeiro build; incompatível → recusa); cria o build, copia o que tem a mesma
  `content_key` e codifica o resto (`embed_passages` em lote; `encode_passage`), grava, publica; exceção depois de
  `create` → `discard` e propaga (faz T025 passar)
- [X] T035 [US1] Implementar `ingestion/adapters/catalog_yaml.py` (`load_catalog(path) -> tuple[object, Path]` com
  `yaml.safe_load`, devolvendo o objeto bruto e o diretório) e `ingestion/adapters/cli.py` (`main(argv, compose) ->
  int` com `argparse`: `ingest`, `status`, `model fetch`; relatório e códigos de saída do contrato); e, no
  `src/ai_scouting/pack.py`, `corpus_cli() -> None` que lê `AI_SCOUTING_QDRANT_URL` (default `http://localhost:6333`),
  `AI_SCOUTING_QDRANT_API_KEY`, `AI_SCOUTING_INDEX` (default `scouting`) e `AI_SCOUTING_EMBEDDING_DIR`, monta
  `PdfiumParser`, `E5Embedder`, `Bm25Encoder`, `QdrantIndex`, `SystemClock` e o serviço, com os imports pesados dentro
  da função, e chama `sys.exit(cli.main(sys.argv[1:], compose))` (faz T026 e T028 passarem)

**Checkpoint**: MVP — um manual entra no Qdrant pela CLI, com ids estáveis e reaproveitamento.

---

## Phase 4: User Story 2 - Norma dividida pela própria estrutura (Priority: P1)

**Goal**: documentos de tipo normativo viram um chunk por artigo ou regra, com o caminho ancestral como prefixo e a
faixa de páginas.

**Independent Test**: ingerir uma norma de teste; cada artigo (ou regra) vira exatamente um chunk, com o prefixo
completo.

### Tests for User Story 2

- [X] T036 [P] [US2] Escrever `tests/rag/ingestion/test_structure.py` (FR-002, FR-003, SC-001, research R7):
  marcadores `TÍTULO II`, `CAPÍTULO III`/`Capítulo 4`, `SEÇÃO I`, `SUBSEÇÃO I`, `Art. 42`, `Art. 42-A`, `Art. 1º`,
  `Regra 033`, `ANEXO I` — sem distinguir caixa nem acento; `§ 1º`, `Parágrafo único`, `I –` e `a)` ficam dentro do
  chunk do artigo; cada artigo exatamente um chunk; prefixo exato `[Lei X · Título II · Capítulo III · Seção I]` com o
  título do catálogo; `chapter`/`section`/`subsection` com o nome do agrupamento ("Capítulo III – Dos Associados");
  `article` = "Art. 42"; artigo entre as páginas 3 e 4 → `page_start=3`, `page_end=4`; preâmbulo → janelas com seção
  `preambulo`; anexo → seção `anexo-i`; segundo `Art. 1` dentro do anexo → `~2`; texto sem nenhuma unidade → tudo
  narrativo com aviso
- [X] T037 [P] [US2] Acrescentar `normative_pdf(path, …)` a `tests/fixtures/pdfs.py` (título, capítulos, seções,
  artigos com parágrafos, incisos e alíneas, um artigo atravessando página) e à aceitação em
  `tests/rag/ingestion/test_service.py`: documento `por`/`resolucao`/`estatuto` → um chunk por unidade, todo chunk
  normativo com prefixo começando em `[<título>` e `article` preenchido (SC-001); `manual` com "Art. 3" no texto
  continua narrativo; normativo sem unidade → aviso "normativo sem unidade" no relatório; unidade acima de 512 tokens
  estimados → aviso; e um caso em `tests/rag/ingestion/test_integration.py` com o PDF normativo pelo `PdfiumParser`

### Implementation for User Story 2

- [X] T038 [US2] Implementar `ingestion/domain/structure.py`: tabela de marcadores (dado do módulo), `Heading`, `Unit`,
  `normative_chunks(lines, title, policy) -> NormativeResult` (unidades → `ChunkDraft` com prefixo e faixa de páginas;
  preâmbulo e anexos por `narrative_chunks`; nenhuma unidade → sinal de fallback) (faz T036 passar)
- [X] T039 [US2] Em `ingestion/service.py`, escolher o chunker por `type ∈ NORMATIVE_TYPES`, aplicar o fallback com
  aviso e acrescentar o aviso de unidade acima de 512 tokens estimados ao `DocumentOutcome` (faz T037 passar)

**Checkpoint**: normas e manuais seguem cada um a sua estratégia.

---

## Phase 5: User Story 3 - Vigência e substituição modeladas (Priority: P1)

**Goal**: cada versão carrega status e datas; ingerir um sucessor marca o antecessor `substituido`; rascunho nunca
aparece na busca; a busca por default traz só o que está em vigor na data.

**Independent Test**: ingerir a versão 2023 e depois a 2026 de um manual; a 2023 fica `substituido` apontando para a
2026, e a busca default traz só a 2026.

### Tests for User Story 3

- [X] T040 [P] [US3] Acrescentar a `tests/rag/index/test_conformance.py` os casos de vigência de
  [contracts/chunk-index.md](contracts/chunk-index.md), nos três alvos, com um manual 2023 (`expiry_date` 2026-02-28,
  `substituido`) e 2026 (`effective_date` 2026-03-01, `vigente`), um rascunho, uma norma geral (sem ramo) e um manual
  do ramo `escoteiro`: intervalo 2026-10-07..2026-10-07 → só 2026; 2023-01-01..2023-12-31 com `include_superseded` →
  2023 com `status="substituido"`; o mesmo sem `include_superseded` → nada da 2023; `previous_version` em 2026-10-07 →
  só 2023; rascunho em nenhuma combinação; `branch="pioneiro"` → pioneiro e gerais, nenhum `escoteiro`;
  `document_types=("por",)` → só POR
- [X] T041 [P] [US3] Acrescentar a `tests/rag/ingestion/test_service.py` a sucessão entre execuções (US3 cen. 1–2):
  execução 1 só com a 2023 → `vigente`; execução 2 com a 2026 `supersedes: "2023"` → 2023 `substituido`, `superseded_by =
  "<id>-2026"`, `expiry_date` = véspera da 2026, chunks da 2023 **reaproveitados** (sem recodificar) com a vigência
  reescrita; catálogo com duas vigentes na mesma linhagem → rejeição nomeando as versões e nada aplicado; versão
  `rascunho` indexada mas fora de qualquer busca; e, em `tests/rag/ingestion/test_cli.py`, `status` com contagem por
  linhagem e status e nenhuma linhagem com duas `vigente` (SC-003)

### Implementation for User Story 3

- [X] T042 [US3] Fazer T040 e T041 passarem, ajustando só `index/adapters/qdrant.py` (tradução dos filtros),
  `index/adapters/memory.py`, `index/domain/points.py` (`with_document`) e `ingestion/service.py`; completar `status` em
  `ingestion/adapters/cli.py` com a tabela por linhagem e status ([contracts/ingestion-cli.md](contracts/ingestion-cli.md))

**Checkpoint**: vigência e substituição verificadas no domínio, no serviço e nos três alvos do índice.

---

## Phase 6: User Story 4 - Material narrativo em janelas semânticas (Priority: P2)

**Goal**: janelas na faixa configurada, que respeitam seções e parágrafos e nunca cortam frase.

**Independent Test**: ingerir um capítulo narrativo; nenhum chunk corta uma frase no meio.

### Tests for User Story 4

- [X] T043 [P] [US4] Acrescentar a `tests/rag/ingestion/test_chunking.py` (FR-004, research R8), por tabela e por
  propriedade sobre textos gerados: todo chunk termina em fim de frase ou de seção; tamanho em
  [`window_min`, `window_max`] tokens estimados, exceto a última janela da seção e a frase única maior que o máximo
  (inteira, nunca cortada); parágrafo maior que o máximo divide-se em frases; `Art. 5`, `nº. 3`, `Sr.`, `Sra.`, `p.`,
  `ex.` e `etc.` não terminam frase; cabeçalho sempre quebra; `ChunkingPolicy(window_min=200, window_max=400)` muda
  `identity()` e, no serviço, deixa a versão incompatível com a publicada (`ingest` recusa); `window_min ≥ window_max` ou
  valores não positivos → `ValueError`

### Implementation for User Story 4

- [X] T044 [US4] Completar `ingestion/domain/chunking.py`: separador de frases (pontuação final + espaço + maiúscula,
  número ou aspas, com a lista de abreviações), divisão de parágrafo grande em frases, validação da `ChunkingPolicy`
  (faz T043 passar)

**Checkpoint**: janelas narrativas completas.

---

## Phase 7: User Story 5 - Texto original preservado e reindexação (Priority: P2)

**Goal**: o original de qualquer chunk é recuperável; trocar a estratégia ou o modelo reindexa de forma controlada; a
busca recusa codificação diferente da registrada.

**Independent Test**: reindexar com outro modelo de embedding sem perder documentos nem alterar identificadores de
documento; o original de um chunk volta pelas páginas dele.

### Tests for User Story 5

- [X] T045 [P] [US5] Acrescentar a `tests/rag/index/test_conformance.py`, nos três alvos: `original(chunk_id)` devolve
  documento, versão, faixa de páginas, o texto **bruto** daquelas páginas, arquivo e `sha256` (FR-009); id
  desconhecido → `None`; `QdrantIndex`/`MemoryIndex` construídos com um `HashingEmbedder` de outra impressão digital (ou
  um codificador esparso de outra identidade) → `search` levanta `IndexMismatch` cuja mensagem nomeia os dois modelos
  (FR-012); depois de publicar um build de versão nova, a mesma instância passa a ver a versão nova sem ser recriada
- [X] T046 [P] [US5] Acrescentar a `tests/rag/ingestion/test_service.py` (US5 cen. 1–2, FR-010): `reindex` com outro
  `HashingEmbedder` (outra impressão digital e outra dimensão) publica um build novo com todos os documentos, os mesmos
  `chunk_id`s e `doc_key`s, nenhum reaproveitado, e a versão nova registrada com `built_at` do relógio; dois `reindex`
  seguidos com a mesma configuração dão os mesmos `chunk_id`s e as mesmas contagens (FR-010); `reindex` com o catálogo
  rejeitado não escreve; `ingest` depois da troca de configuração recusa e manda rodar `reindex`; e, em
  `tests/rag/ingestion/test_cli.py`, `original <chunk_id>` imprime o texto e `reindex` devolve 0

### Implementation for User Story 5

- [X] T047 [US5] Implementar `original` no `QdrantIndex` e no `MemoryIndex` (payload do chunk → `doc_key` e faixa →
  páginas do ponto de documento) e a verificação de versão a cada `search` (lê a versão publicada, compara
  `embedding` com `embedder.model()` e `sparse` com `sparse.identity()`, `IndexMismatch` se divergirem) (faz T045
  passar)
- [X] T048 [US5] Implementar `IngestionService.reindex` (o caminho do `ingest` sem reaproveitamento, aceitando versão
  diferente da publicada) e `IngestionService.original(chunk_id)`, e os subcomandos `reindex` e `original` em
  `ingestion/adapters/cli.py` (faz T046 passar)

**Checkpoint**: todas as histórias funcionais.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [X] T049 [P] Escrever `tests/rag/test_vocabulary.py`: os ids de ramo e de tipo de documento do léxico da 101
  (`ai_scouting.context.lexicon`) são iguais a `BRANCHES` e aos valores de `DocumentType` (research R3; nota para a
  US5 da 101)
- [X] T050 [P] Criar `tests/fixtures/make_corpus.py <dir>` (quickstart §4): PDFs sintéticos de um manual 2023/2026
  (`supersedes`), uma norma `norma-teste` (`version: "1"`, `type: resolucao`) com `Art. 42` na página 3 e um rascunho, mais o `corpus.yaml` correspondente
- [X] T051 Verificação completa dentro de `ai-scouting/`: `uv run pytest` em 3.14 e em 3.12 (`uv run --python 3.12
  pytest`), `uv run ruff check`, `uv run ruff format --check`, `uv run mypy`, `uv run lint-imports`, a conformidade
  contra o servidor (quickstart §2) e o e5 real (quickstart §3); corrigir o que quebrar
- [X] T052 Executar [quickstart.md](quickstart.md) §4 (corpus sintético ponta a ponta, incluindo o catálogo quebrado
  de propósito) e corrigir divergências entre o resultado e o "Esperado"
- [X] T053 SC-005 ([quickstart.md](quickstart.md) §5, research R19): baixar do site oficial da UEB o POR consolidado, o
  estatuto, uma resolução e um manual de ramo para `~/corpus-ueb/` (fora do repositório); escrever o `corpus.yaml` de
  rascunho com versões e datas tiradas dos documentos; **parar para o curador (mantenedor) revisar o catálogo**; rodar
  `ingest` contra um Qdrant local; ajustar a tabela de marcadores de `ingestion/domain/structure.py` ao que o corpus
  real mostrar, sempre com um caso sintético do mesmo formato em `test_structure.py`; rodar também `reindex` sobre o mesmo catálogo; registrar no fim do [quickstart.md](quickstart.md) §5 a duração
  da ingestão e a da reindexação completa (primeira medida do SC-004) e a contagem de chunks por
  documento — nada do corpus real é commitado
- [X] T054 Com o aval do mantenedor: commit e push do `ai-scouting` e conferir os jobs do `ci.yml` verdes, inclusive o
  `qdrant`
- [X] T056 Corpus no repositório (clarificação de 2026-10-08): mover o catálogo revisado e os PDFs para
  `ai-scouting/corpus/` (git normal), acrescentar o campo opcional `source_url` ao catálogo
  (`ingestion/domain/catalog.py`, validado como link `http(s)://`), ao registro do documento (`index/ports.py`,
  `index/domain/points.py`) e ao `original` (CLI), com testes em `test_catalog.py`, `test_service.py`,
  `test_conformance.py` e `test_cli.py`; seção "Corpus" no `README.md` do pack
- [X] T055 [P] Atualizar no `agentic-app`: `CLAUDE.md` (seção "Código": a 102 existe — `rag/index` com o seam
  `ChunkIndex` e o adapter Qdrant por alias e build, `rag/ingestion` com catálogo, linhagem, estrutura, janelas e a CLI
  `ai-scouting-corpus`, e5-small provisório em ONNX, BM25 com IDF no Qdrant; "Fase 5 em andamento"), a linha da 102 em
  `specs/README.md` (status "Fase 5 implementada (US1–US5)") e, no mesmo commit, o ponteiro do submódulo `ai-scouting`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup**: T001 → T002 (o `uv lock` precisa do `pyproject.toml`); T003 em paralelo
- **Foundational**: T004 → T005 → T006; T007 → T008; T009 → T011; T010 → T012 (depois de T011); T013 → T014 (depois de T006);
  T015 → T016; T017 depois de T005; T018 e T019 → T020 (depois de T008, T016, T017). Bloqueia todas as histórias
- **US1**: depende do Foundational. Testes T021–T027 em paralelo; T028 depois de T024. Implementação: T029 → T030 →
  T034 → T035; T031, T032 e T033 em paralelo entre si e com T029–T030; T034 precisa de T029 e T030; T035 precisa de
  T031–T034
- **US2**: depende da US1 (o serviço e o chunker narrativo). T036 ∥ T037; T038 → T039
- **US3**: depende da US1 (adapter Qdrant e serviço); independe da US2. T040 ∥ T041 → T042
- **US4**: depende da US1 (mesmo `chunking.py`); independe da US2 e da US3. T043 → T044
- **US5**: depende da US1; independe das demais. T045 ∥ T046; T047 → T048
- **Polish**: T049 e T050 a qualquer momento depois do Foundational/US5; T051 depois de todas as histórias; T052 depois
  de T050 e T051; T053 depois de T052 (e da US2, que traz a estrutura normativa); T054 depois de T053; T055 em paralelo
  com T054

### Parallel Opportunities

- T003 em paralelo com todo o Setup
- No Foundational, as três frentes — modelo e filtros (T004–T008), catálogo e linhagem (T009–T012) e codificação
  (T015–T016) — correm em paralelo
- Na US1, os três adapters reais (Qdrant T031, e5 T032, pdfium T033) em paralelo
- Depois da US1, US3, US4 e US5 podem correr em paralelo entre si (arquivos de teste compartilhados ganham seções
  distintas; T042, T044 e T047–T048 tocam arquivos diferentes, exceto `service.py` em T042 e T048 — fazer em sequência)

---

## Parallel Example: User Story 1

```bash
Task: "tests/rag/ingestion/test_text.py (T021)"
Task: "tests/rag/ingestion/test_ids.py (T022)"
Task: "tests/rag/ingestion/test_chunking.py — casos base (T023)"
Task: "tests/fixtures/pdfs.py + tests/rag/ingestion/test_parser.py (T024)"
Task: "tests/rag/ingestion/test_service.py — US1 (T025)"
Task: "tests/rag/ingestion/test_cli.py (T026)"
Task: "tests/rag/index/test_embedder.py — alvo e5 (T027)"

# depois, os adapters reais:
Task: "index/adapters/qdrant.py (T031)"
Task: "index/adapters/e5.py (T032)"
Task: "ingestion/adapters/pdfium.py (T033)"
```

---

## Implementation Strategy

### MVP (US1)

1. Setup: dependências, esqueleto, lock, job `qdrant`
2. Foundational: seam, portas, catálogo, linhagem, filtros, BM25, índice em memória
3. US1: limpeza, ids, janelas base, Qdrant, e5, pdfium, serviço e CLI — **PARE e VALIDE**: um manual sintético entra
   pela CLI no Qdrant local, e a reingestão reaproveita tudo
4. US2 (normas), US3 (vigência), US4 (janelas completas), US5 (original e reindexação) — **PARE e VALIDE** cada uma
5. Polish: vocabulário, corpus de demonstração, verificação, quickstart, **corpus real com revisão do curador**, CI,
   documentação e ponteiro do submódulo

### Depois desta fase

- 103 (Fase 5): retriever e reranker sobre `ChunkIndex` (importa só `rag.index.api`)
- 104 (Fase 5): validators publicados pelo pack, com os status da 102
- 101 US5 (Fase 5): manifest com `rag_first`, `retrievers()` montando o `QdrantIndex`, prompt com citação
- Instalação (`agentic-deploy`): modelo no runtime e Qdrant ao lado do core

---

## Notes

- `api.py`, `domain/`, `ports.py` e `service.py` só importam stdlib, `ai_core_contracts` e o próprio módulo — o
  import-linter (T001) barra o resto
- Toda porta tem adapter em memória e a mesma suíte contra o real: `MemoryIndex`/`QdrantIndex`,
  `HashingEmbedder`/`E5Embedder`, `MemoryParser`/`PdfiumParser`; o `Bm25Encoder` é puro e serve aos dois papéis
- Nenhum número é calibrado aqui: janela, BM25 e modelo são provisórios e vão na versão do índice (princípio X)
- O corpus real nunca entra no repositório; os testes usam só PDFs gerados

---

## Passada de 2026-10-21: o índice gerado no desenvolvimento ([ADR-043](../../docs/adr/ADR-043-indice-do-scouting-gerado-no-desenvolvimento.md); research R21–R25)

- [X] T057 `domain/artifact.py` e `adapters/artifact.py` (`ArtifactIndex`); `MemoryStorage.put`/`export`; alvo
  `artefato` na suíte de conformidade e `tests/rag/index/test_artifact.py` (R21, R22)
- [X] T058 [P] `adapters/openrouter.py` e `tests/rag/index/test_openrouter.py` (R23)
- [X] T059 CLI: `ServiceOptions`, `--embedder`/`--dir`, `load-qdrant`; `copy_index` e a porta `IndexExport`;
  composição no `pack.py`; `ORT_DISABLE_TELEMETRY` no adapter do e5 (R24)
- [X] T060 O artefato do corpus real com o e5 em `src/axon_scouting/data/index/` (413 trechos); o workflow `eval`
  confere o determinismo (R25)
- [X] T061 Os vetores do `pplx` no artefato (`reindex --embedder pplx`, com o aval do mantenedor): os mesmos 413
  trechos, o conjunto de 1024 dimensões ao lado do e5; 9 s; artefato com 4,1 MB

## Passada de 2026-10-27 (revisão do RAG; research R26–R29)

- [X] T062 [US6] `domain/layout.py` (`TextLine`, `reading_order`) e `tests/rag/ingestion/test_layout.py` (R26).
- [X] T063 [US6] `ParsedDocument.reading`/`for_chunking`; o `PdfiumParser` com as caixas das linhas e `leitura-v1` na
  identidade; o serviço lê `for_chunking`; o PDF sintético com o título desenhado depois do corpo (`positioned_pdf`).
- [X] T064 [US6] `text.py`: bordas de até 4 linhas, critério do trecho (80%), marcador protegido, U+FFFE/U+00AD e
  número colado; casos em `test_text.py` (R27).
- [X] T065 [US6] `chunking.py`: corpo sem frase segue adiante (e a janela final curta junta-se à anterior), títulos
  completos, `estrutural-v2;janela=250-450`, frase maior que a janela dividida entre palavras; `structure.py` com o
  nome no prefixo, o texto solto curto na unidade seguinte e o nome que termina em preposição continuado; casos em
  `test_chunking.py` e `test_structure.py` e expectativas de prefixo atualizadas (R28).
- [X] T067 `ArtifactIndex._jsonl` separa as linhas só em `\n` (U+0085 e U+2028 no texto); caso em
  `tests/rag/index/test_artifact.py` (R29).
- [X] T066 [US6] Preparo do corpus inteiro antes/depois, `reindex` com o e5 e `tests/rag/ingestion/test_artifact_quality.py`
  (SC-006, R29).
- [X] T068 `filhotes` em `BRANCHES` e `branch: filhotes` nos três documentos do Ramo Filhotes no catálogo; `ingest`
  (só metadados) (R30).
