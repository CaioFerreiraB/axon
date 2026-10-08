# ADR-025 — O índice do scouting devolve a similaridade densa de cada resultado

- **Status:** Aceita · 2026-10-08
- **Specs afetadas:** [102-scouting-corpus-ingestion](../../specs/102-scouting-corpus-ingestion/spec.md) (seam *Índice
  do scouting*: campo aditivo `similarity` no `IndexedChunk` — contracts/chunk-index.md, data-model.md),
  [103-scouting-retrieval](../../specs/103-scouting-retrieval/spec.md) (usa o campo como `score` do `Chunk`). Os outros
  consumidores do seam não mudam: a 106 (Fase 8) e a 104 (só os valores de status).
- **Origem:** clarificação 1 da 103 (2026-10-08), aceita pelo mantenedor

## Contexto

O portão de cobertura do `rag_first` (005 FR-007) escala para o loop quando o melhor score fica abaixo de um limiar. O
`ChunkIndex.search` da 102 devolve o score da fusão RRF (`Σ 1/(posição + 2)`): ele só diz em que posição o trecho
ficou nas duas buscas. O primeiro colocado tem sempre 0,5 ou mais, mesmo quando nada no índice responde à pergunta —
com ele, o portão nunca escalaria por "score baixo", só por "nenhum resultado". A 005 também une os resultados de
vários packs por score, o que exige um número comparável entre packs.

## Decisão

1. `IndexedChunk` ganha `similarity: float | None = None`: o cosseno entre o vetor denso da pergunta e o do trecho.
   `search` o preenche em todo resultado; `get` o deixa `None`. `score` continua sendo o da fusão, e a ordem de `search`
   não muda.
2. O adapter calcula o cosseno no cliente, com os vetores densos que a busca já devolve (`with_vectors=["dense"]` no
   Qdrant — verificado no servidor `v1.19.2` e no modo local em 2026-10-08); o adapter em memória usa os vetores que
   guarda. Nenhuma consulta extra.
3. `to_chunk()` não muda (o `Chunk.score` dele é o da fusão). Quem decide que número vai para o `Chunk` entregue ao
   core é o consumidor: a 103 usa `similarity` (clarificação 1 da 103).
4. A suíte de conformidade da 102 passa a exigir `similarity` em `[-1, 1]` em todo resultado de `search`, igual nos
   adapters para os mesmos vetores, e `None` em `get`.

## Alternativas rejeitadas

*Score do RRF no portão.* Relativo à pergunta: o portão ficaria cego para "nada relevante".

*Uma segunda busca só densa para obter a similaridade.* Dobra a latência da recuperação para obter um número que os
vetores devolvidos já permitem calcular.

*Trocar o `score` do `IndexedChunk` pela similaridade.* Perderia a ordem da fusão, que o reranker v1 da 103 usa para
desempatar (clarificação 2 da 103), e mudaria o significado de um campo existente.

## Consequências

- O limiar do portão (calibrado na 105) passa a ter significado absoluto: "o trecho mais próximo está a tal distância
  da pergunta".
- A similaridade depende do modelo de embedding: trocar o modelo (reindexação) muda a escala, e o limiar precisa ser
  medido de novo — o que a FR-012 da 102 já amarra à versão do índice.
- Mudança aditiva: nenhum consumidor existente quebra; a 102 implementa o campo numa tarefa da passada da 103.
