# Data Model — 103 Scouting Retrieval, Fase 5

Decisões em [research.md](research.md). Nada persiste: a 103 lê o índice da 102 e devolve `Chunk`s da 001.

## `RetrievalConfig` (`domain/config.py`)

| Campo | Default | Regra |
|---|---|---|
| `default_limit` | 5 | trechos devolvidos quando `search` vem sem `top_k` (a tool no loop agêntico) |
| `max_limit` | 30 | teto para o `top_k` pedido |

`1 ≤ default_limit ≤ max_limit`. Provisórios; a 105 calibra (FR-008).

## Filtros recebidos → `IndexFilters` (`domain/filters.py`)

| Chave (`retrieval_filters` da 101) | Tipo | Obrigatória | No `IndexFilters` |
|---|---|---|---|
| `effective_from`, `effective_until` | data ISO | sim | os mesmos |
| `include_superseded`, `previous_version` | bool | não (`False`) | os mesmos |
| `branch` | id de ramo | não | `branch` (ramo ou gerais) |
| `document_types` | lista de ids de tipo | não | `document_types` (restringe) |
| `topics` | lista de ids de tema | não | — ignorado (FR-009) |

Filtros `None`, data ausente ou inválida, tipo errado (ex.: `include_superseded: "sim"`) ou chave fora da tabela →
`InvalidFilters(key, message)`.

## Chave de ordem (`domain/ordering.py`)

```text
(-fusion_score, status != vigente, not branch_match, not type_match, chunk_id)
```

| Marca | Verdadeira quando |
|---|---|
| `branch_match` | os filtros pedem ramo e o trecho é desse ramo (geral não casa) |
| `type_match` | os filtros trazem `document_types` e o tipo do trecho está neles |

Chunk sem `fusion_score` nos metadados (de fora da 103) vai depois dos anotados, na ordem de entrada.

## `Chunk` devolvido (contrato 001)

| Campo | Origem |
|---|---|
| `chunk_id`, `text`, `document`, `version`, `status`, `section`, `page` | `IndexedChunk.to_chunk()` (102) |
| `score` | `IndexedChunk.similarity`, limitado a `[0, 1]` (clarificação 1, ADR-025) |
| `metadata` | o da 102 (`document_id`, `document_type`, `branch`, `jurisdiction`, `chapter`, `subsection`, `page_end`, datas, `superseded_by`) + `fusion_score`, `branch_match`, `type_match` |

## Erros

| Erro | Dono | Quando |
|---|---|---|
| `InvalidFilters` | 103 | filtros ausentes ou fora do contrato da 101 |
| `IndexUnavailable` | 102 | índice inexistente ou fora do ar (passa sem tradução) |
| `IndexMismatch` | 102 | embedder ou codificador esparso diferente do registrado (FR-012 da 102) |
| `ValueError` | 103 | `top_k < 1` |
