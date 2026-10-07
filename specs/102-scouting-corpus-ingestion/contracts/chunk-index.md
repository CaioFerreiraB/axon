# Contrato — seam *Índice do scouting* e portas do índice

Dono: 102. Consumidores do seam: 103 e 106 (`ChunkIndex` e o modelo); 104 (só os valores de `ValidityStatus`). Interno
ao repositório `ai-scouting` — não é seam do core. Decisões em [research.md](../research.md) R5, R12, R14, R16;
tipos em [data-model.md](../data-model.md).

## Seam — `ai_scouting.rag.index.api`

Publica: `ValidityStatus`, `STATUS_LABELS`, `DocumentType`, `NORMATIVE_TYPES`, `BRANCHES`, `IndexedChunk`,
`IndexFilters`, `EmbeddingModel`, `IndexVersion`, `IndexUnavailable`, `IndexMismatch`, `ChunkIndex`. Importa só stdlib e
`ai_core_contracts` (para `Chunk`).

```python
class ChunkIndex(Protocol):
    async def search(self, query: str, *, filters: IndexFilters, limit: int) -> list[IndexedChunk]:
        """Busca densa + esparsa com fusão no próprio armazenamento, já filtrada; no máximo `limit`, por score
        decrescente e, no empate, por `chunk_id`. Pergunta vazia ou só com termos de parada → []."""

    async def get(self, chunk_ids: Sequence[str]) -> list[IndexedChunk]:
        """Os chunks existentes, na ordem pedida, com `score=None`; ids ausentes são omitidos."""

    async def version(self) -> IndexVersion:
        """A versão do build publicado."""


class IndexUnavailable(Exception):
    """Índice inexistente, servidor fora ou build sem versão. A mensagem nomeia o índice; nunca a credencial."""


class IndexMismatch(Exception):
    """A codificação desta instância difere da do build publicado (FR-012). Atributos `index` e `encoder`, com
    nome e impressão digital do embedder e a identidade do codificador esparso; a mensagem nomeia os dois."""
```

| Regra | Verificação (suíte de conformidade, contra memória e Qdrant) |
|---|---|
| filtros de vigência (R5) | versões 2023/2026 de um manual: default no dia de hoje → só 2026; intervalo 2023 com `include_superseded` → 2023 com `status="substituido"`; `previous_version` em 2026-10-07 → só 2023 |
| rascunho nunca aparece | documento `rascunho` indexado, nenhuma combinação de filtros o devolve |
| ramo inclui gerais | `branch="pioneiro"` → chunks do pioneiro e sem ramo; nenhum de outro ramo |
| tipos | `document_types=("por",)` → só POR |
| fusão | termo exato ("42") traz o `art42` pelo esparso; o vizinho denso também entra |
| determinismo | mesma busca duas vezes → mesma lista; empates ordenados por `chunk_id` |
| `get` | ordem pedida; ausente omitido |
| versão | `version()` devolve a gravada pelo build publicado |
| FR-012 | embedder com outra impressão digital (ou outro codificador esparso) → `IndexMismatch` com os dois nomes |
| indisponível | índice inexistente → `IndexUnavailable`, não lista vazia |
| conversão | `to_chunk()` cumpre o `Chunk` da 001 (`document` = título; `page` = página inicial) |

## Portas secundárias — `ai_scouting.rag.index.ports`

```python
class Embedder(Protocol):
    def model(self) -> EmbeddingModel: ...                       # nome, impressão digital, dimensões
    async def embed_passages(self, texts: Sequence[str]) -> list[tuple[float, ...]]: ...
    async def embed_query(self, text: str) -> tuple[float, ...]: ...


class SparseEncoder(Protocol):
    def identity(self) -> str: ...                               # "bm25-pt-v1;k1=1.2;b=0.75;avgdl=256"
    def encode_passage(self, text: str) -> SparseVector: ...
    def encode_query(self, text: str) -> SparseVector: ...


class IndexWriter(Protocol):
    async def published(self) -> Build | None: ...               # build atrás do alias, com a versão
    async def documents(self, build: str) -> list[StoredDocument]: ...
    async def create(self, version: IndexVersion) -> Build:
        """Coleção nova e vazia, com a versão na metadata, chamada `<índice>__<built_at AAAAMMDDTHHMMSSZ>`;
        se o nome já existe (duas execuções no mesmo segundo, relógio fixo nos testes), acrescenta `-2`, `-3`…"""
    async def write(self, build: str, document: DocumentRecord, chunks: Sequence[EncodedChunk]) -> None: ...
    async def copy(self, source: str, target: str, document: DocumentRecord) -> None:
        """Copia os chunks de `document.doc_key` com os vetores, reescrevendo os campos de documento (metadados e
        vigência) a partir de `document`; grava o registro do documento em `target`."""
    async def publish(self, build: str) -> None:
        """Alias → `build` numa operação; depois apaga o build anterior e os builds órfãos do mesmo índice."""
    async def discard(self, build: str) -> None: ...


class DocumentStore(Protocol):
    async def original(self, chunk_id: str) -> Original | None: ...
```

| Porta | Real | Em memória | Suíte |
|---|---|---|---|
| `Embedder` | `E5Embedder` (`adapters/e5.py`) | `HashingEmbedder` (`adapters/memory.py`) | dimensão = `model().dimensions`; norma 1; determinismo; `embed_query(t) != embed_passages([t])[0]` (prefixos do e5); o real só com `AI_SCOUTING_EMBEDDING_DIR` |
| `SparseEncoder` | `Bm25Encoder` (`adapters/bm25.py`) | o mesmo (puro) | ids estáveis entre execuções; "Art. 42" contém o termo de `42`; acentos dobrados; pergunta com peso 1 por termo |
| `IndexWriter` + `DocumentStore` | `QdrantIndex` (`adapters/qdrant.py`) | `MemoryIndex` (`adapters/memory.py`) | publicar troca o que `ChunkIndex` vê de uma vez; `copy` preserva vetores e reescreve vigência; `discard` não afeta o publicado; `original` devolve as páginas da faixa do chunk |

O `QdrantIndex` implementa as três (`ChunkIndex`, `IndexWriter`, `DocumentStore`) sobre o mesmo cliente assíncrono e
recebe `Embedder` e `SparseEncoder` na construção — com eles codifica a pergunta e confere a FR-012 a cada busca. Alvos
da suíte: `MemoryIndex`; `QdrantIndex` no modo local (`AsyncQdrantClient(location=":memory:")`, sempre); `QdrantIndex`
contra servidor quando `AI_SCOUTING_TEST_QDRANT_URL` existe (job `qdrant` da CI, imagem `qdrant/qdrant:v1.19.2`).
