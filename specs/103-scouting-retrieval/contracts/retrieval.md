# Contrato — retriever, reranker e a tool `search_docs`

Dono: 103. Consumidores: o pack (101 US5, que os publica) e, através dele, o core (005 no `rag_first`, 004 na tool do
loop agêntico). Implementam os contratos `Retriever` e `Reranker` da 001; a única dependência interna é
`axon_scouting.rag.index.api` (102). Decisões em [research.md](../research.md); tipos em [data-model.md](../data-model.md).

```python
class ScoutingRetriever:                                     # rag/retrieval/retriever.py — implementa Retriever (001)
    def __init__(self, index: ChunkIndex, config: RetrievalConfig = RetrievalConfig()) -> None: ...

    async def search(self, query: str, *, top_k: int | None = None,
                     filters: Mapping[str, JSONValue] | None = None) -> Sequence[Chunk]:
        """Busca híbrida no índice com os filtros da 101 traduzidos (R3). Devolve no máximo `top_k` (ou
        `default_limit`; nunca mais que `max_limit`), na ordem da R4, com `score` = similaridade e as marcas de ordem
        nos metadados. Erros: InvalidFilters, IndexUnavailable, IndexMismatch, ValueError (top_k < 1)."""


def search_docs(retriever: ScoutingRetriever, *, collection: str = "scouting") -> NamedRetriever:
    """A tool `scouting.search_docs` (FR-006): nome `search_docs`, a coleção que o grant precisa conceder."""


class MetadataReranker:                                      # rag/retrieval/reranker.py — implementa Reranker (001)
    async def rerank(self, query: str, documents: Sequence[Chunk], *, top_k: int = 5) -> Sequence[Chunk]:
        """Reordena pela chave da R4 lendo os metadados (chunk de fora vai depois, na ordem de entrada) e corta em
        `top_k`. Sem pesos, sem modelo, sem I/O."""
```

| Regra | Verificação |
|---|---|
| US1 — fusão nativa | "o que diz a Regra 33" traz `regra33` (esparso); a paráfrase de um trecho o traz (denso, e5 no quickstart) |
| US2 — só o vigente por default | manual 2023/2026 indexados; filtros do dia de hoje → só 2026 |
| US3 — data passada | período 2023 com `include_superseded` → a 2023, com `status="substituido"` |
| US4 — desempate | dois candidatos empatados na fusão: o vigente e específico do ramo fica acima do geral; no máximo `top_k` |
| US5 — filtros de contexto | `branch="pioneiro"` → pioneiro e gerais; `document_types=["por"]` → só POR |
| FR-004 | todo `Chunk` com proveniência completa e `score` em `[0, 1]` |
| FR-007 | índice inexistente → `IndexUnavailable`, nunca `[]` |
| FR-009 | `topics` não mudam o resultado |
| R3 | filtros `None`, sem datas ou com chave desconhecida → `InvalidFilters` |
| R5 | `rerank` com chunks sem metadados (como o kit da 001): no máximo `top_k`, todos da entrada, sem exceção |
| R6 | sem `top_k` → `default_limit`; `top_k` acima de `max_limit` → `max_limit` |
