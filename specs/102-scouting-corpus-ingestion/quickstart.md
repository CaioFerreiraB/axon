# Quickstart — 102 Corpus Ingestion (Fase 5)

Roteiro de verificação. Tudo roda dentro de `ai-scouting/` (submódulo); nesta máquina, com
`XDG_DATA_HOME=$HOME/.local/share`. Contratos: [chunk-index](contracts/chunk-index.md),
[corpus-catalog](contracts/corpus-catalog.md), [ingestion-cli](contracts/ingestion-cli.md).

## 1. Suíte padrão (sem servidor, sem modelo)

```bash
uv sync
uv run pytest && uv run mypy && uv run ruff check && uv run lint-imports
```

Esperado: verde. Cobre o domínio (catálogo, linhagem, limpeza, estrutura, janelas, ids), o serviço com adapters em
memória (US1–US5), a conformidade do `ChunkIndex`/`IndexWriter`/`DocumentStore` contra o `MemoryIndex` **e** contra o
`QdrantIndex` no modo local, o `PdfiumParser` sobre PDFs gerados no teste e as fronteiras de import. Os casos que
exigem servidor Qdrant ou o modelo e5 aparecem como pulados.

| Cenário | Onde é provado |
|---|---|
| US1 cen. 1–2: chunks com id, metadados e as duas representações; reingestão sem duplicata e com os mesmos ids | aceitação do serviço + integração (pdfium + Qdrant local) |
| US2 cen. 1–2: um artigo/regra = um chunk, prefixo completo, faixa de páginas | domínio (estrutura) + aceitação |
| US3 cen. 1–2: 2023 vira `substituido` apontando para 2026; rascunho fora da busca | domínio (linhagem) + conformidade |
| US4: janelas na faixa, nenhuma frase cortada | domínio (janelas), por propriedade |
| US5 cen. 1–2: original recuperável de qualquer chunk; reindexação com outro embedder mantém todos os documentos e registra a versão | aceitação + conformidade |
| FR-012: embedder diferente do registrado → recusa nomeando os dois | conformidade |

## 2. Conformidade contra o servidor Qdrant

```bash
docker run -d --rm --name ai-scouting-qd -p 56333:6333 qdrant/qdrant:v1.19.2
AI_SCOUTING_TEST_QDRANT_URL=http://localhost:56333 uv run pytest tests/rag/index
docker stop ai-scouting-qd
```

Esperado: os mesmos casos de conformidade, agora contra o servidor (é o que o job `qdrant` da CI roda).

## 3. Modelo e5 de verdade

```bash
uv run ai-scouting-corpus model fetch ~/.cache/ai-scouting/e5-small
AI_SCOUTING_EMBEDDING_DIR=~/.cache/ai-scouting/e5-small uv run pytest tests/rag/index -k e5
```

Esperado: `model fetch` baixa ~490 MB e confere os sha256 da revisão fixada (rodar de novo não baixa); a suíte do
`Embedder` passa contra o `E5Embedder` (dimensão 384, norma 1, pergunta ≠ passagem). Uma paráfrase de um trecho fica
mais perto dele do que de um trecho de outro tema (sanidade, não calibração).

## 4. Ingestão ponta a ponta com um corpus sintético

```bash
docker run -d --rm --name ai-scouting-qd -p 56333:6333 qdrant/qdrant:v1.19.2
export AI_SCOUTING_QDRANT_URL=http://localhost:56333 AI_SCOUTING_EMBEDDING_DIR=~/.cache/ai-scouting/e5-small
uv run python tests/fixtures/make_corpus.py /tmp/corpus-demo      # PDFs sintéticos + corpus.yaml (manual 2023/2026, norma, rascunho)
uv run ai-scouting-corpus ingest /tmp/corpus-demo/corpus.yaml       # código 0; build publicado
uv run ai-scouting-corpus ingest /tmp/corpus-demo/corpus.yaml       # tudo "reaproveitado"; mesmos ids (SC-002)
uv run ai-scouting-corpus status                                    # 1 vigente por linhagem (SC-003)
uv run ai-scouting-corpus original 'norma-teste-1#art42@p3'         # texto original da página (FR-009)
```

Depois, quebre o catálogo de propósito — tire o `title` de uma entrada e declare uma segunda versão vigente — e rode
`ingest`: código 1, os dois problemas listados, e `status` mostra o build anterior intacto.

## 5. Corpus real (SC-005, manual)

1. Baixar do site oficial da UEB o POR consolidado, o estatuto, uma resolução e um manual de ramo para uma pasta fora
   do repositório (ex.: `~/corpus-ueb/`).
2. Escrever `~/corpus-ueb/corpus.yaml` de rascunho com versões e datas tiradas dos próprios documentos
   ([formato](contracts/corpus-catalog.md)).
3. **O curador revisa o catálogo.**
4. `uv run ai-scouting-corpus ingest ~/corpus-ueb/corpus.yaml` contra o Qdrant local.

Esperado: nenhuma rejeição; o relatório mostra unidades normativas reconhecidas no POR, no estatuto e na resolução
(nenhum aviso de "normativo sem unidade"); `status` com uma vigente por linhagem; amostra de chunks normativos com o
prefixo completo e o rótulo da unidade (SC-001); a duração anotada como primeira medida do SC-004. Ajustes na tabela
de marcadores pedidos pelo corpus real entram com teste sintético do mesmo formato. Nada do corpus real é commitado.
