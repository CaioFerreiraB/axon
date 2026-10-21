# Quickstart — 103 Scouting Retrieval (Fase 5)

Roteiro de verificação dentro de `axon-scouting/`, com `XDG_DATA_HOME=$HOME/.local/share`. Contrato:
[retrieval.md](contracts/retrieval.md).

## 1. Suíte padrão

```bash
uv run pytest && uv run mypy && uv run ruff check && uv run lint-imports
```

Esperado: verde. Cobre os filtros (tabela), a chave de ordem, o retriever e o reranker contra o `MemoryIndex` (US1–US5),
a conformidade do `Reranker` com chunks crus, a integração com o `QdrantIndex` em modo local e o campo `similarity` da
102 (ADR-025) na conformidade do índice.

## 2. Corpus real com o e5

Pré-requisito: o índice `scouting` ingerido a partir de `corpus/corpus.yaml` (quickstart da 102, §5) num Qdrant local.
É aqui — e no caso com o e5 de `test_integration.py`, que a CI pula por falta do modelo — que a paráfrase da US1
(cen. 2) é verificada.

```bash
export AXON_SCOUTING_QDRANT_URL=http://localhost:56333 AXON_SCOUTING_EMBEDDING_DIR=~/.cache/axon-scouting/e5-small
uv run python tests/rag/retrieval/sanity.py
```

| Pergunta (filtros do dia de hoje) | Esperado |
|---|---|
| "o que diz a Regra 033" | `por-…#regra33` no topo (termo exato, esparso) |
| "qual é a promessa do lobinho?" | a Regra 005 do POR entre os primeiros (denso) |
| "como conduzir a cerimônia de promessa na alcateia", `branch=lobinho` | só trechos do manual do Lobinho ou gerais |
| "quem compõe a Assembleia Nacional?", `document_types=["estatuto"]` | só artigos do Estatuto |
| uma pergunta sem relação com o corpus ("receita de bolo de cenoura") | melhor `score` visivelmente abaixo das anteriores — é o que o portão da 005 vai usar |

Anote os scores do topo de cada pergunta: são a primeira referência para o limiar que a 105 vai calibrar. O rerank de 30
candidatos deve levar menos de 1 ms (SC-003).

### Resultado de 2026-10-08 (corpus real, índice `scouting`, e5-small, máquina de desenvolvimento)

| Pergunta | Topo (chunk) | `score` do topo | Maior `score` entre os 3 primeiros |
|---|---|---|---|
| "o que diz a Regra 033" | `por-2025.2.1#regra33@p38` | 0,876 | 0,880 |
| "qual é a promessa do lobinho?" | `escotistas-em-acao-lobinho-2#11@p80` (a Regra 005 em 2º) | 0,900 | 0,917 |
| "como conduzir a cerimônia de promessa na alcateia", `branch=lobinho` | `escotistas-em-acao-lobinho-2#s10@p43` | 0,881 | 0,881 |
| "quem compõe a Assembleia Nacional?", `document_types=["estatuto"]` | `estatuto-2024#art16@p11` (o Art. 14 em 2º) | 0,858 | 0,865 |
| "receita de bolo de cenoura" (fora do corpus) | `estatuto-2024#art54@p32` | 0,812 | 0,838 |

O rerank de 30 candidatos levou 0,026 ms em média (SC-003). **A similaridade do e5 é comprimida**: perguntas cobertas
ficam em 0,85–0,92 e a pergunta fora do corpus ainda chega a 0,84 — a margem para o limiar do portão (005) é de uns
0,05, e o valor depende do modelo. É a primeira referência para a calibração da 105; um limiar "intuitivo" (0,5, 0,7)
deixaria passar qualquer pergunta.
