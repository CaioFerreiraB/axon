# Contrato — seam *Índice do scouting* e portas do índice

Dono: 102. Consumidores do seam: 103 e 106 (`ChunkIndex` e o modelo); 104 (só os valores de `ValidityStatus`). Interno
ao repositório `axon-scouting` — não é seam do core. Decisões em [research.md](../research.md) R5, R12, R14, R16;
tipos em [data-model.md](../data-model.md).

## Seam — `axon_scouting.rag.index.api`

Publica: `ValidityStatus`, `STATUS_LABELS`, `taxonomy_id`, `SCOPES`, `BRANCHES`, `IndexedChunk`,
`IndexFilters`, `EmbeddingModel`, `IndexVersion`, `IndexUnavailable`, `IndexMismatch`, `ChunkIndex`. Importa só stdlib e
`axon_ai_contracts` (para `Chunk`).

```python
class ChunkIndex(Protocol):
    async def search(self, query: str, *, filters: IndexFilters, limit: int) -> list[IndexedChunk]:
        """Busca densa + esparsa com fusão no próprio armazenamento, já filtrada; no máximo `limit`, por score
        decrescente e, no empate, por `chunk_id`. Pergunta vazia ou só com termos de parada → []."""

        # Cada resultado traz `similarity`: o cosseno entre o vetor denso da pergunta e o do trecho (ADR-025).

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
| tipos | `document_types=("por",)` → só POR; o tipo é o id da taxonomia (ADR-049), não um enum fixo |
| órgão e abrangência (ADR-049) | `bodies=("assembleias",)` → só documentos cuja categoria ou subcategoria é Assembleias; `scopes=("regional",)` → só os de nível regional |
| fusão | termo exato ("42") traz o `art42` pelo esparso; o vizinho denso também entra |
| determinismo | mesma busca duas vezes → mesma lista; empates ordenados por `chunk_id` |
| `get` | ordem pedida; ausente omitido; `similarity` é `None` |
| similaridade (ADR-025) | todo resultado de `search` traz `similarity` em `[-1, 1]` — o cosseno denso pergunta × trecho —, igual nos adapters para os mesmos vetores; o trecho idêntico à pergunta tem a maior |
| versão | `version()` devolve a gravada pelo build publicado |
| FR-012 | embedder com outra impressão digital (ou outro codificador esparso) → `IndexMismatch` com os dois nomes |
| indisponível | índice inexistente → `IndexUnavailable`, não lista vazia |
| conversão | `to_chunk()` cumpre o `Chunk` da 001 (`document` = título; `page` = página inicial) |

### Catálogo de documentos ([ADR-047](../../../docs/adr/ADR-047-lista-de-documentos-do-acervo-no-scouting.md))

```python
@dataclass(frozen=True, slots=True, kw_only=True)
class CatalogEntry:
    """Um documento do acervo: `doc_key`, os campos de documento de `IndexedChunk` (identidade, tipo, título,
    jurisdição, ramo e vigência, com os mesmos nomes) e `source_url`."""


@runtime_checkable
class DocumentCatalog(Protocol):
    async def catalog(self, *, filters: IndexFilters) -> list[CatalogEntry]:
        """Os documentos que `filters` admite — a semântica da busca —, em ordem de `doc_key`; `IndexUnavailable` sem
        build publicado."""
```

| Regra | Verificação (conformidade, contra memória, artefato e Qdrant) |
|---|---|
| mesma semântica da busca | os casos de vigência, ramo e tipo da tabela acima admitem os mesmos documentos |
| link | `source_url` do registro do documento |
| indisponível | sem build publicado → `IndexUnavailable` |

### Árvore de unidades ([ADR-048](../../../docs/adr/ADR-048-arvore-de-unidades-e-enumeracao-no-scouting.md))

```python
Shape = Literal["prose", "list"]

# Campos novos de IndexedChunk (e do registro de documento, para os quatro primeiros):
#   category, subcategory, level, semantic_type   — da entrada da taxonomia (pasta do arquivo), os rótulos
#   document_type: str                              — o id do tipo da taxonomia (ADR-049; antes, o enum DocumentType)
#   bodies: tuple[str, ...]                         — ids da categoria e da subcategoria (ADR-049)
#   scope: str | None                               — um de SCOPES: o nível da taxonomia, senão o da jurisdição
#   path: tuple[UnitRef, ...]                       — as unidades acima do trecho, da raiz para baixo
#   unit_kind: str | None                           — o tipo da unidade mais próxima ("especialidade", "artigo"…)
#   shape: Shape
#   branches: tuple[str, ...]                       — vazio = geral; substitui o `branch` único na filtragem

@dataclass(frozen=True, slots=True, kw_only=True)
class UnitRef:
    unit_id: str            # "<doc_key>#u/<caminho>", estável entre reingestões do mesmo texto
    kind: str
    title: str


@dataclass(frozen=True, slots=True, kw_only=True)
class UnitEntry:
    """Uma unidade de um documento: `unit_id`, `kind`, `title`, `page_start`/`page_end`, `path` (as de cima), `branches`
    e os campos de documento de `CatalogEntry` (identidade, título, vigência)."""


@dataclass(frozen=True, slots=True, kw_only=True)
class UnitKind:
    name: str               # "especialidade"
    label: str              # "Especialidade"
    plurals: tuple[str, ...]


@runtime_checkable
class DocumentOutline(Protocol):
    async def unit_kinds(self) -> tuple[UnitKind, ...]:
        """Os tipos de unidade do build publicado (os de `estrutura.yaml` na ingestão)."""

    async def units(self, kind: str, *, filters: IndexFilters) -> list[UnitEntry]:
        """As unidades de `kind` em documentos que `filters` admite — com os ramos da unidade —, na ordem do documento
        (por `doc_key`, depois página). Tipo desconhecido → []."""

    async def outline(self, doc_key: str) -> list[UnitEntry]:
        """A árvore do documento em pré-ordem, sem texto; documento inexistente → []."""

# IndexFilters ganha `shape: Shape | None` (None = qualquer).
```

| Regra | Verificação (conformidade, contra memória, artefato e Qdrant) |
|---|---|
| ramos por unidade | grupo `branches=("pioneiro",)` num documento sem ramo: `branch="pioneiro"` admite, `branch="lobinho"` não; documento sem ramos continua geral |
| `units` | as especialidades de um guia declarado, na ordem do sumário, com página e o eixo no `path`; os mesmos filtros de vigência da busca |
| `outline` | pré-ordem; cada `unit_id` aparece uma vez; o `path` de todo trecho é um prefixo de um caminho do `outline` |
| `shape` | `IndexFilters(shape="list")` → só trechos `list` |
| rótulo | o prefixo do trecho traz "Tipo: título" de cada nível do `path` |
| estabilidade | reingerir o mesmo PDF com o mesmo `estrutura.yaml` → os mesmos `unit_id` |

## Portas secundárias — `axon_scouting.rag.index.ports`

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
| `Embedder` | `E5Embedder` (`adapters/e5.py`) | `HashingEmbedder` (`adapters/memory.py`) | dimensão = `model().dimensions`; norma 1; determinismo; `embed_query(t) != embed_passages([t])[0]` (prefixos do e5); o real só com `AXON_SCOUTING_EMBEDDING_DIR` |
| `SparseEncoder` | `Bm25Encoder` (`adapters/bm25.py`) | o mesmo (puro) | ids estáveis entre execuções; "Art. 42" contém o termo de `42`; acentos dobrados; pergunta com peso 1 por termo |
| `IndexWriter` + `DocumentStore` | `QdrantIndex` (`adapters/qdrant.py`) | `MemoryIndex` (`adapters/memory.py`) | publicar troca o que `ChunkIndex` vê de uma vez; `copy` preserva vetores e reescreve vigência; `discard` não afeta o publicado; `original` devolve as páginas da faixa do chunk |

O `QdrantIndex` implementa as três (`ChunkIndex`, `IndexWriter`, `DocumentStore`) sobre o mesmo cliente assíncrono e
recebe `Embedder` e `SparseEncoder` na construção — com eles codifica a pergunta e confere a FR-012 a cada busca. Alvos
da suíte: `MemoryIndex`; `QdrantIndex` no modo local (`AsyncQdrantClient(location=":memory:")`, sempre); `QdrantIndex`
contra servidor quando `AXON_SCOUTING_TEST_QDRANT_URL` existe (job `qdrant` da CI, imagem `qdrant/qdrant:v1.19.2`).
