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

---

## Passada de 2026-10-21 ([ADR-043](../../docs/adr/ADR-043-indice-do-scouting-gerado-no-desenvolvimento.md))

## R12 — O embedder da pergunta

- **Decision**: nada muda no `ScoutingRetriever`: ele recebe o `ChunkIndex` composto pelo `pack.py` (101 R33), que já
  codifica a pergunta com o embedder dos vetores. A `EmbeddingUnavailable` do `pplx` atravessa o `search` como exceção, e
  o gateway da 004 a devolve como recuperação com erro — o `rag_first` encerra sem gerar.
- **Rationale** (ADR-043, itens 3 e 5): o seam do índice esconde o modelo; a 103 só precisava não engolir a exceção, e
  não engole.
- **Alternatives**: degradar para o esparso sem o denso (mudaria a fusão e esconderia a falha).

---

## Passada de 2026-10-27 (revisão do RAG; [ADR-045](../../docs/adr/ADR-045-filhotes-e-consulta-multifaceta-no-scouting.md))

## R13 — Busca por faceta

- **Decision**: `domain/filters.py` aceita `branches` (dois ids ou mais, sem repetir, nunca com `branch`) e o expõe
  por `facets(raw)`; `index_filters` continua dando os filtros do índice. `ScoutingRetriever._by_facet`: para cada ramo,
  `index.search(f"{pergunta} Ramo {nome}", filters=… branch=ramo, limit=top_k)`, guardando os primeiros
  `ceil(top_k / facetas)` que nenhuma faceta anterior levou; marcas `facet`, `facet_rank` (posição entre os guardados)
  e `facet_order` nos metadados. `ordering.sort_key` começa por `(facet_rank, facet_order)` — zero sem facetas —, então
  o `MetadataReranker` devolve um de cada ramo antes do segundo de qualquer um. `BRANCH_NAMES` dá o nome do ramo.
- **Rationale**: medido no índice de 2026-10-27 (E10 da revisão refeito): com "pergunta + Ramo X" e o filtro, a
  evidência do marco simbólico e do lema fica em 1º lugar em 9 de 10 combinações; reescrever a pergunta ("do Ramo X")
  não ganha nada. Com o limite repartido na busca, o 1º lugar mudava (o índice corta as listas densa e esparsa no limite
  antes do RRF), e o ganho caía de 0,82 para 0,79 no `fact_recall`. A posição conta só os guardados: um trecho geral
  levado pela faceta anterior não pode tirar a posição 0 de outra.
- **Efeito** (105, regressão): `fact_recall` 0,75 → 0,81; "dos 5 ramos" e "dos cinco ramos" 0,8. "De cada ramo" e os
  cinco nomeados ficam em 0,4: dentro da faceta, a fusão põe em primeiro a definição genérica ("O Marco Simbólico é um
  conjunto…") — a seleção que lê a pergunta é do reranker v2/v3.
- **Alternatives**: um único índice com filtro "algum destes ramos" (devolve os mais parecidos, como antes);
  decompor no core (o ramo é domínio, princípio I).

## R14 — O reranker que lê a pergunta: medido e não adotado

- **Decision**: o v1 (`MetadataReranker`) continua. Nenhum cross-encoder entra, e o corte do gateway nos candidatos do
  `rag_first` fica como está (o ajuste no core, condicional à medição, não se justificou). O ganho que sobrou na mesa é
  de configuração da instalação — `AXON_RAG_PASSAGES` 10 em vez de 5 —, não de modelo.
- **Rationale** — o caminho do `rag_first` simulado com o código real (retriever com as facetas, `render_within` do
  core, reranker, N primeiros) nos 20 itens do conjunto de regressão e nos itens da semente com `chunk_id`, conferido
  contra o harness (0,81 e 0,667 com o v1); cross-encoders multilíngues em ONNX no CPU, Apache-2.0, fixados por
  revisão (`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1@1427fd65`, `onnx-community/bge-reranker-v2-m3-ONNX@6f5ff652`),
  2 threads, como numa VM pequena; com facetas, o cross-encoder reordena dentro de cada ramo e mantém a intercalação:

| reranker | candidatos | corte | N | `fact_recall` | semente | p50 (2 threads) | RAM a mais |
|---|---:|---|---:|---:|---:|---:|---:|
| `MetadataReranker` (v1) | 20 | 16 KB | 5 | 0,81 | 0,667 | — | — |
| `mmarco-mMiniLMv2-L12-H384-v1` (quint8) | 20 | 16 KB | 5 | 0,81 | 0,667 | 1,7 s | +300 MB |
| `bge-reranker-v2-m3` (int8) | 20 | 16 KB | 5 | 0,82 | 0,667 | 5,8 s | +1,1 GB |
| `mmarco-mMiniLMv2-L12-H384-v1` (quint8) | 20 | sem | 5 | 0,77 | 0,667 | 3,0 s | +300 MB |
| `bge-reranker-v2-m3` (int8) | 20 | sem | 5 | 0,78 | 0,667 | 10,3 s | +1,1 GB |
| `bge-reranker-v2-m3` (int8) | 40 | sem | 5 | 0,78 | 0,778 | 15,9 s | +1,1 GB |
| `bge-reranker-v2-m3` (int8) | 20 | 16 KB | 10 | 0,86 | 0,667 | 5,7 s | +1,1 GB |
| `MetadataReranker` (v1) | 20 | 16 KB | 10 | 0,86 | 0,667 | — | — |

  O pequeno empata com o v1; o grande ganha +0,01 por 5,8 s e 1,1 GB a cada pergunta. Sem o corte do gateway, piora:
  mais candidatos trazem mais trecho genérico, e nenhum dos dois o separa da evidência. Com 10 trechos, o v1 e o grande
  chegam aos mesmos 0,86 — o ganho é do número de trechos. O que falta ("de cada ramo", os cinco nomeados, as faixas
  etárias) é de **recuperação**: dentro da faceta, a evidência não está entre os candidatos que sobram, e a das faixas
  etárias está no POR, que é geral.
- **Alternatives**: um reranker hospedado (Cohere, Jina, Voyage) — não medido: não havia chave nesta máquina, e nada
  na medição local sugere que a ordem seja o gargalo; fica para quando um candidato de recuperação deixar a evidência
  entre os candidatos e a ordem voltar a importar. O mMiniLM com 10 trechos e o bge-m3 com 40 candidatos e 10 trechos
  não terminaram (memória, rodando em paralelo); não mudam a conclusão.

## R15 — `suggested_types` como marca de ordem ([ADR-046](../../docs/adr/ADR-046-tipo-sugerido-ordena-no-scouting.md))

- **Decision**: `domain/filters.py` aceita `suggested_types` (lista de tipos conhecidos; outro valor é
  `InvalidFilters`) e o expõe por `suggested_types(raw)`; `ordering.marks(chunk, filters, preferred)` liga
  `type_match` para o tipo citado ou o sugerido; o retriever passa os sugeridos a cada `_to_chunk`, também por faceta.
- **Rationale**: o tipo sugerido é palpite do léxico; como filtro, escondia os guias e zerava as perguntas de
  especialidades.
- **Alternatives**: peso numérico na fusão (FR-005 proíbe peso na v1; outro ADR se a medição pedir).
