# Data Model — 102 Corpus Ingestion, Fase 5

Decisões em [research.md](research.md). Tipos publicados no seam ficam em `rag/index/api.py`; os de escrita e
codificação, em `rag/index/ports.py`; os do pipeline, em `rag/ingestion/`. Todos são `dataclass(frozen=True)`.

## Vocabulários (seam — `rag/index/api.py`)

| Nome | Valores | Origem |
|---|---|---|
| `ValidityStatus` | `vigente`, `revogado`, `substituido`, `rascunho` | FR-007 (ids ASCII; R14) |
| `STATUS_LABELS` | `vigente` → "vigente", `revogado` → "revogado", `substituido` → "substituído", `rascunho` → "rascunho" | para quem exibe (104) |
| `DocumentType` | `por`, `resolucao`, `estatuto`, `manual`, `programa_educativo`, `guia` | FR-002, clarificação 3 |
| `NORMATIVE_TYPES` | `por`, `resolucao`, `estatuto` | FR-002 |
| `BRANCHES` | `lobinho`, `escoteiro`, `senior`, `pioneiro` | ids da 101 (R3) |

## Corpus Catalog → `CatalogEntry` (`ingestion/domain/catalog.py`)

Uma entrada por versão de documento. Formato do arquivo em [contracts/corpus-catalog.md](contracts/corpus-catalog.md).

| Campo | Tipo | Obrigatório | Regra |
|---|---|---|---|
| `file` | caminho relativo | sim | dentro do diretório do catálogo; existe |
| `document_id` | slug | sim | `^[a-z0-9]+(-[a-z0-9]+)*$` — a linhagem |
| `version` | texto | sim | `^[0-9a-z]+(\.[0-9a-z]+)*$` (sem hífen) |
| `type` | `DocumentType` | sim | tabela fixa |
| `title` | texto | sim | não vazio; vai no prefixo e na citação |
| `jurisdiction` | texto | sim | não vazio (ex.: `nacional`) |
| `effective_date` | data | sim | início da vigência |
| `branch` | id de ramo | não | ausente = documento geral |
| `publication_date` | data | não | |
| `expiry_date` | data | não | obrigatório com `status: revogado`; derivado para substituídas (R4) |
| `supersedes` | versão | não | versão da mesma linhagem |
| `status` | `rascunho` \| `revogado` | não | os demais status são derivados |
| `source_url` | link | não | `https?://` sem espaço — o arquivo oficial; vai para o registro, fora da chave de conteúdo |

Validação acumula todos os problemas: `CatalogProblem(entry: int, key: str | None, fields: tuple[str, ...], message)`.

## Lineage → `Validity` (`ingestion/domain/lineage.py`)

Derivação pura sobre todas as entradas válidas (R4).

| Campo | Tipo | Regra |
|---|---|---|
| `status` | `ValidityStatus` | rascunho/revogado declarados; `substituido` se há sucessor não rascunho; senão `vigente` |
| `effective_date` | data | do catálogo |
| `expiry_date` | data \| `None` | declarado; para `substituido`, a véspera do `effective_date` do sucessor |
| `superseded_by` | chave de documento \| `None` | `<document_id>-<versão do sucessor>` |
| `successor_expiry_date` | data \| `None` | o `expiry_date` do sucessor (para `previous_version`, R5) |

Erros de linhagem (`LineageProblem(document_id, message)`): `supersedes` inexistente; versão substituída por duas;
ciclo; sucessor que não começa depois do antecessor; `expiry_date` declarado diferente da véspera do sucessor; mais de
uma `vigente`. Invariante: **no máximo uma `vigente` por `document_id`** (SC-003).

```text
            rascunho ──(curador tira o status)──▶ vigente ──(entra sucessor não rascunho)──▶ substituido
                                                    │
                                                    └──(curador declara revogado + expiry_date)──▶ revogado
```

Toda transição acontece no catálogo; a ingestão só a recalcula (o índice espelha o catálogo).

## Estrutura e chunks (`ingestion/domain/`)

| Tipo | Campos | Notas |
|---|---|---|
| `ParsedDocument` (porta `DocumentParser`) | `source_sha256`, `pages: tuple[str, ...]`, `parser: str` | páginas brutas, 1-indexadas pela posição; `parser` = adapter + versão |
| `Line` | `text`, `page` | depois da limpeza (R7) |
| `Heading` | `level` (`title`, `chapter`, `section`, `subsection`, `annex`), `label` ("Capítulo III"), `name` ("Dos Associados") | |
| `Unit` | `kind` (`article`, `rule`), `label` ("Art. 42", "Regra 33"), `key` (`art42`, `regra33`), linhas | uma unidade = um chunk (FR-002) |
| `ChunkDraft` | `section_key`, `prefix`, `body`, `page_start`, `page_end`, `chapter`, `section`, `subsection`, `article`, `kind` (`normative`/`narrative`) | antes do id e dos metadados |
| `ChunkingPolicy` | `window_min=300`, `window_max=600` (tokens estimados = ⌈caracteres/4⌉), `strategy="estrutural-v1"` | `identity()` → `"estrutural-v1;janela=300-600"` |

## `IndexedChunk` (seam — `rag/index/api.py`)

| Campo | Tipo | Origem |
|---|---|---|
| `chunk_id` | texto | R9: `<document_id>-<version>#<seção>@p<página>[~k]` |
| `text` | texto | prefixo ancestral + `\n` + corpo (FR-003) |
| `document_id`, `version`, `doc_key` | texto | catálogo; `doc_key = "<document_id>-<version>"` |
| `document_type` | `DocumentType` | catálogo |
| `document_title` | texto | catálogo |
| `branch` | id \| `None` | catálogo (`None` = geral) |
| `jurisdiction` | texto | catálogo |
| `chapter`, `section`, `subsection` | texto \| `None` | estrutura (cabeçalho com nome) |
| `article` | texto \| `None` | rótulo da unidade normativa ("Art. 42", "Regra 33") |
| `page_start`, `page_end` | int ≥ 1 | faixa de páginas (US2 cen. 2) |
| `publication_date`, `effective_date`, `expiry_date` | data \| `None` | catálogo + linhagem |
| `superseded_by`, `successor_expiry_date` | texto/data \| `None` | linhagem |
| `status` | `ValidityStatus` | linhagem |
| `score` | float \| `None` | preenchido por `search`; `None` em `get` |

`to_chunk()` → `Chunk` da 001: `chunk_id`, `text`, `score` (0.0 se `None`), `document` = `document_title`, `version`,
`status`, `section` = `article` ou o cabeçalho mais específico, `page` = `page_start`; `metadata` = `document_id`,
`document_type`, `branch`, `jurisdiction`, `chapter`, `subsection`, `page_end`, as datas em ISO e `superseded_by`.

## `IndexFilters` (seam)

| Campo | Tipo | Default | Semântica |
|---|---|---|---|
| `effective_from` | data | — | início do intervalo (inclusivo) |
| `effective_until` | data | — | fim do intervalo (inclusivo); `from ≤ until` |
| `include_superseded` | bool | `False` | R5 |
| `previous_version` | bool | `False` | R5 |
| `branch` | id \| `None` | `None` | o ramo ou geral |
| `document_types` | tupla de `DocumentType` | `()` | vazio = todos |

Predicado puro `matches(filters, chunk) -> bool` em `rag/index/domain/filters.py` (R5).

## Versão do índice (seam)

| Tipo | Campos |
|---|---|
| `EmbeddingModel` | `name` (`intfloat/multilingual-e5-small`), `fingerprint` (sha256 do `model.onnx`), `dimensions` (384) |
| `IndexVersion` | `chunking` (identidade da `ChunkingPolicy`), `embedding: EmbeddingModel`, `sparse` (`bm25-pt-v1;k1=1.2;b=0.75;avgdl=256`), `built_at` (UTC) |

`IndexVersion.compatible_with(other)`: iguais em `chunking`, `embedding` e `sparse` (`built_at` não conta). Gravada na
`metadata` da coleção do build (R12).

## Escrita e originais (`rag/index/ports.py`)

| Tipo | Campos |
|---|---|
| `SparseVector` | `indices: tuple[int, ...]` (u32, ordenados, únicos), `values: tuple[float, ...]` |
| `EncodedChunk` | `chunk: IndexedChunk` (sem score), `dense: tuple[float, ...]`, `sparse: SparseVector` |
| `DocumentFields` | os campos de documento que todo chunk da versão repete: `document_id`, `version`, `document_type`, `document_title`, `jurisdiction`, `branch`, `publication_date`, `effective_date`, `expiry_date`, `status`, `superseded_by`, `successor_expiry_date`; `doc_key` derivado |
| `StoredDocument` | `fields: DocumentFields`, `content_key`, `source_file`, `source_sha256`, `chunk_ids`, `source_url`; `doc_key` derivado |
| `DocumentRecord` | `StoredDocument` + `pages: tuple[str, ...]` (texto original bruto) |
| `Build` | `name` (`<índice>__<AAAAMMDDTHHMMSSZ>`, com `-<n>` se o nome já existe), `version: IndexVersion` |
| `Original` | `chunk_id`, `doc_key`, `document_title`, `version`, `page_start`, `page_end`, `pages` (o texto delas), `source_file`, `source_sha256`, `source_url` |

`content_key = sha256(source_sha256 | document_type | title | parser)` — igual entre builds = chunks reaproveitáveis
(R13).

## Relatório (`ingestion/domain/report.py`)

| Tipo | Campos |
|---|---|
| `DocumentOutcome` | `doc_key`, `chunks`, `reused: bool`, `normative_units`, `warnings` (página sem texto, normativo sem unidade, unidade acima de 512 tokens estimados) |
| `IngestionReport` | `ok`, `problems` (catálogo, linhagem, parser, versão), `documents`, `removed` (doc_keys que saíram), `version`, `build`; a duração é medida pela CLI |

## Mapa no Qdrant (detalhe do adapter, não seam)

| Elemento | Forma |
|---|---|
| alias | nome do índice (`AI_SCOUTING_INDEX`, default `scouting`) → build publicado. É a "coleção" da spec e do grant (a que o retriever declara) |
| coleção | `<índice>__<carimbo>`; `metadata = {"index_version": …}` |
| vetores | `dense` (cosseno, dimensão do embedder), `sparse` (`modifier=IDF`) |
| ponto de chunk | id `uuid5(NAMESPACE_CHUNK, chunk_id)`; payload = `IndexedChunk` sem `score` + `kind="chunk"` |
| ponto de documento | id `uuid5(NAMESPACE_DOCUMENT, doc_key)`; sem vetor; payload = `DocumentRecord` + `kind="document"` |
| índices de payload | `keyword`: `kind`, `doc_key`, `document_id`, `status`, `branch`, `document_type`; `datetime`: `effective_date`, `expiry_date`, `successor_expiry_date` |
