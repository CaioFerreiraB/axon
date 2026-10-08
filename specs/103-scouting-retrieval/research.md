# Research — 103 Scouting Retrieval, Fase 5 (US1–US5)

Insumos pré-aprovados: [design.md](design.md), [spec.md](spec.md) §Clarifications (sessão de 2026-10-08),
[ADR-006](../../docs/adr/ADR-006-rag-first-default-scouting.md), [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md),
[ADR-013](../../docs/adr/ADR-013-seams-transversais-trace-e-tempo.md) e o novo
[ADR-025](../../docs/adr/ADR-025-indice-do-scouting-devolve-a-similaridade-densa.md). Seams conferidos no código: o
índice da 102 (`ai_scouting.rag.index.api`, implementado em 2026-10-08: `ChunkIndex.search` com RRF, `IndexFilters`
por intervalo, ramo-ou-geral, tipos, `previous_version`), os contratos `Retriever`, `Reranker`, `NamedRetriever` e
`RETRIEVAL_TOOL_PARAMETERS` (001, `contracts-v0.1.0`), o gateway da 004 (a tool de recuperação chama
`retriever.search(query, top_k?, filters=fatia do pack)`, sem rerank) e o kit de conformidade (chama `rerank` com
chunks sem metadados). Contrato de filtros da 101: [retrieval-filters.md](../101-scouting-pack/contracts/retrieval-filters.md).
Sonda de 2026-10-08: `query_points` com fusão devolve os vetores densos (`with_vectors=["dense"]`) no servidor
`v1.19.2` e no modo local. Escopo: **US1–US5**.

## R1 — Escopo, localização e toques fora do módulo

**Decision** (design.md): `src/ai_scouting/rag/retrieval/` com `domain/` (filtros recebidos → `IndexFilters`,
configuração e a chave de ordem — puro), `retriever.py` (`ScoutingRetriever`, o `Retriever` da 001, e o construtor da
tool `search_docs`) e `reranker.py` (`MetadataReranker`, o `Reranker` da 001). Sem `ports.py` nem `adapters/`: a 103 não
faz I/O próprio — o índice é o seam da 102, injetado —, e o reranker hospedado (v2) ou local (v3) entra como adapter
quando existir (princípio XII). Toques fora: a 102 implementa o campo `similarity` (ADR-025) em `rag/index/api.py`, nos
dois adapters e na conformidade; o `pyproject.toml` ganha os contratos do import-linter. O `pack.py` **não** muda
aqui: publicar o retriever, o reranker e o manifest com `rag_first` é a US5 da 101.

**Rationale**: a 103 entrega as capacidades e a tool; quem compõe o pack é a 101, como a 104 fez com os validators.

**Alternatives considered**: ligar no `pack.py` já (mistura a US5 da 101 — manifest, `config_schema`, prompt — nesta
passada); `ports.py` para o índice (o índice já é um `Protocol` publicado; uma porta por cima seria porta para
porta).

## R2 — O score devolvido é a similaridade densa (clarificação 1, ADR-025)

**Decision**: o `Chunk.score` entregue ao core é a `similarity` do `IndexedChunk` (cosseno denso pergunta × trecho),
limitada a `[0, 1]`. A fusão continua decidindo a ordem; o score dela vai em `Chunk.metadata["fusion_score"]`.

**Rationale**: o portão de cobertura da 005 compara o melhor score com um limiar, e a 005 une resultados de packs por
score; os dois exigem um número absoluto. O cosseno do e5 normalizado já fica em `[-1, 1]` e, na prática, positivo; o
limite a `[0, 1]` cumpre a spec (FR-004) sem alterar a ordem entre valores positivos.

**Alternatives considered**: o RRF (relativo — clarificação 1, opções B e C); normalizar o RRF por pergunta
(continua relativo).

## R3 — Filtros recebidos → `IndexFilters` (FR-002, FR-003, FR-009)

**Decision**: função pura `domain/filters.py:index_filters(raw) -> IndexFilters` sobre o `retrieval_filters` da 101:

| Chave da 101 | No índice |
|---|---|
| `effective_from`, `effective_until` (ISO) | os mesmos campos; **obrigatórios** |
| `include_superseded`, `previous_version` | os mesmos (default `False`) |
| `branch` | `branch` (o índice inclui os gerais) |
| `document_types` | `document_types` (restringe — 101 contrato, 103 US5) |
| `topics` | ignorado (FR-009) |

Filtros ausentes (`None`), sem as datas, com tipo errado ou com chave desconhecida → `InvalidFilters`, nomeando a chave.
O retriever nunca lê o relógio (FR-002): sem datas, não há como escolher a vigência, e chutar "hoje" seria falha
silenciosa.

**Rationale**: o contrato de filtros diz "nenhuma chave nova sem atualizar este contrato e a 103"; rejeitar a chave
desconhecida faz a deriva aparecer no primeiro teste, não numa resposta errada. Ramo e tipo inválidos já são recusados
pelo próprio `IndexFilters` da 102.

**Alternatives considered**: ignorar chave desconhecida (a deriva passaria em silêncio); default "hoje" sem filtros
(relógio na 103 — viola FR-002 e ADR-013).

## R4 — Ordem: fusão, com desempate por metadados (clarificação 2, FR-005)

**Decision**: chave de ordem pura (`domain/ordering.py`), igual no retriever e no reranker:

```text
(-fusion_score, não vigente, não específico do ramo pedido, não do tipo sugerido, chunk_id)
```

"Específico do ramo" = o trecho tem ramo e ele é o dos filtros; "tipo sugerido" = os filtros trazem `document_types`
e o tipo do trecho está nele (com a restrição da US5, todo candidato casa — o critério só pesa se a restrição virar
preferência um dia). O retriever calcula essas marcas na busca — é quem conhece os filtros — e as grava em
`Chunk.metadata` (`fusion_score`, `branch_match`, `type_match`); o reranker lê dali. Nenhum peso numérico.

**Rationale**: é o teste da US4 ("entre empatados na fusão, o vigente e específico do ramo fica acima") sem número para
calibrar (princípio X). O RRF é por posição, então empates são comuns (todo trecho que só uma das buscas achou em
primeiro lugar tem 0,5) — o desempate tem efeito real. Gravar as marcas no `Chunk` deixa o reranker independente da
ordem de entrada: a 005 une resultados por score antes do rerank, e o score agora é a similaridade.

**Alternatives considered**: reforço com pesos (clarificação 2, opção B); o reranker receber os filtros (o contrato
`Reranker.rerank(query, documents, top_k)` não os tem).

## R5 — O reranker com chunks de fora

**Decision**: chunk sem `fusion_score` nos metadados (de outro pack, ou os chunks crus do kit de conformidade) vai
depois dos anotados, na ordem de entrada (ordenação estável); depois corta em `top_k`. Nunca levanta exceção por
metadado ausente; `top_k < 1` é `ValueError`.

**Rationale**: o kit de conformidade da 001 chama `rerank` com chunks sem metadados e exige no máximo `top_k`, todos da
entrada; e a 005 pode passar a mistura de vários packs. Determinístico nos dois casos.

**Alternatives considered**: recusar chunks sem anotação (quebra a conformidade e a composição de packs).

## R6 — Quantidades (FR-008) e a tool no loop agêntico (FR-006)

**Decision**: `RetrievalConfig(default_limit=5, max_limit=30)`, validada (`1 ≤ default_limit ≤ max_limit`). O
`search(query, top_k=None, filters)` usa `top_k` quando vem — limitado a `max_limit` — e `default_limit` quando não vem.
O `rerank(..., top_k=5)` corta em `top_k`. A tool `scouting.search_docs` é o mesmo retriever num `NamedRetriever`
(nome `search_docs`, coleção = nome do índice, default `scouting`); o gateway da 004 a chama sem `top_k` quando o
modelo não pede, então o controller recebe os `default_limit` melhores, já na ordem da R4.

**Rationale**: no `rag_first` a 005 pede os candidatos explicitamente (20–30, a faixa da spec) e o reranker corta em
3–8; no loop agêntico não há rerank, e 20 trechos de até 600 tokens encheriam o contexto do controller (princípio V:
"o menor conjunto suficiente"). O teto protege contra o modelo pedir `top_k` enorme — o esquema da tool não tem
máximo. Números provisórios, calibrados na 105.

**Alternatives considered**: default 20 do contrato (contexto cheio no loop); rerank dentro do retriever (dobraria o
trabalho no `rag_first`; com a R4 a ordem já sai igual).

## R7 — Erros (FR-007)

**Decision**: `IndexUnavailable` e `IndexMismatch` (102) passam sem tradução — já são explícitos e tipados;
`InvalidFilters` (R3) é da 103. Pergunta vazia ou só com termos de parada → `[]` (102).

**Rationale**: "coleção indisponível: erro explícito, não resultado vazio". Embrulhar os erros da 102 só esconderia o
tipo.

**Alternatives considered**: devolver `[]` com aviso (o portão escalaria em silêncio).

## R8 — Conversão para o `Chunk` da 001 (FR-004)

**Decision**: `chunk = indexed.to_chunk()` (proveniência completa: documento = título do catálogo, versão, status
ASCII, seção, página inicial e os metadados de documento) com `score` trocado pela similaridade (R2) e `metadata`
acrescida de `fusion_score`, `branch_match` e `type_match`.

**Rationale**: a 102 já define a conversão; a 103 só decide o número do score e acrescenta as marcas da ordem.

**Alternatives considered**: montar o `Chunk` campo a campo (duplica a 102).

## R9 — Fronteiras de import

**Decision**: contratos novos no `pyproject.toml` do pack: `layers` `rag.retrieval.retriever | rag.retrieval.reranker`
→ `rag.retrieval.domain`; `forbidden`: `rag.retrieval` ↛ `rag.index.domain`, `.ports`, `.adapters`,
`rag.ingestion` e as bibliotecas de infraestrutura (`qdrant_client`, `onnxruntime`, `tokenizers`, `numpy`,
`snowballstemmer`, `pypdfium2`, `yaml`).

**Rationale**: princípio XIII — um módulo vê do outro só o `api.py`.

**Alternatives considered**: nenhum.

## R10 — Testes

**Decision**: domínio por tabela (filtros, chave de ordem, configuração); retriever e reranker com o `MemoryIndex` da
102 e o `HashingEmbedder` (US1–US5, inclusive "Regra 33"/"Art. 42" pelo esparso e o desempate da US4); conformidade
do `Reranker` com chunks crus, como o kit faz; integração com o `QdrantIndex` em modo local; sanidade com o e5 real e o
corpus real no quickstart (paráfrase, termo exato, histórico, ramo). SC-001 e SC-002 são medidos na 105; SC-003 (rerank
sem atraso perceptível) é medido no quickstart — ordenar 30 itens custa microssegundos.

**Rationale**: o `MemoryIndex` foi feito para os testes da 103 (R16 da 102), com as mesmas fórmulas do Qdrant.

**Alternatives considered**: testar só contra Qdrant (mais lento, sem ganho de cobertura).

## R11 — Notas para consumidores (fora desta passada)

**Decision**: registrar, sem implementar: (a) 101 US5 — `retrievers()` devolve `search_docs(ScoutingRetriever(index,
config), collection=...)`, `reranker()` devolve `MetadataReranker()`, o manifest declara `requires_collections` com o
nome do índice e `rag_first`; (b) 005 US3 — pedir os candidatos com `top_k` explícito (20–30), tratar exceção do
retriever como erro explícito (não "sem resultados"), comparar o limiar com o `score` (similaridade, `[0, 1]`) e não
depender da ordem de entrada no rerank; (c) 105 — os botões são `default_limit`, `max_limit`, o `top_k` de candidatos
da 005, o N do rerank e o limiar do portão.

**Rationale**: decisões das specs donas, que só precisam saber o que a 103 entrega.

**Alternatives considered**: nenhum.
