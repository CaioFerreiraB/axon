# ADR-043 — O índice do scouting é gerado no desenvolvimento e distribuído com o pack, com vetores de mais de um modelo

- **Status:** Aceita · 2026-10-21
- **Specs afetadas:** [102-scouting-corpus-ingestion](../../specs/102-scouting-corpus-ingestion/spec.md) (artefato do índice,
  índice em memória em produção, embedder remoto), [103-scouting-retrieval](../../specs/103-scouting-retrieval/spec.md)
  (codificação da pergunta pelo embedder escolhido), [101-scouting-pack](../../specs/101-scouting-pack/spec.md)
  (`config_schema` e `prepare`), [105-scouting-evaluation](../../specs/105-scouting-evaluation/spec.md) (comparação
  dos modelos)
- **Origem:** conversa com o mantenedor (2026-10-21): as instalações rodam em VMs pequenas, a ingestão de documentos
  grandes não deve rodar nelas, e o modelo de embedding no processo pesa demais

## Contexto

Hoje cada instalação ingere o corpus (PDFium, limpeza, chunking e embedding de todos os trechos) num Qdrant próprio e
codifica cada pergunta com o `multilingual-e5-small` no processo. Medido em 2026-10-21 na máquina do mantenedor: o e5
carregado ocupa ~860 MB estáveis, com pico de ~1,17 GB na carga; cada pergunta leva poucos milissegundos. O Qdrant com
os 413 trechos ocupa ~70 MB. A ingestão é o passo mais pesado e não precisa de nada da instalação: depende só do corpus,
do chunking e do modelo — tudo versionado no `axon-scouting`.

O modelo da pergunta precisa ser o mesmo da indexação (mesma revisão, mesma convenção de entrada): a 102 já registra o
modelo na versão do índice e recusa a mistura (`IndexMismatch`). Um candidato remoto é o
`perplexity/pplx-embed-v1-0.6b` (pesos abertos, MIT; 1024 dimensões com Matryoshka; no OpenRouter a US$ 0,004 por
milhão de tokens); a qualidade dele em português normativo só o eval da 105 responde.

## Decisão

1. **A ingestão roda no desenvolvimento ou no CI do pack, nunca na instalação.** Ela produz um **artefato do índice**,
   distribuído como dado do pacote Python: os trechos (texto, metadados, termos esparsos), o texto original de cada
   documento (102: chunks são índice, não substituto) e um manifesto com a versão do índice. Atualizar o corpus é
   lançar uma versão nova do pack.
2. **Vetores de mais de um modelo no mesmo artefato.** Os trechos e os ids são os mesmos para qualquer modelo (a
   ingestão é determinística); o artefato guarda um conjunto de vetores densos por modelo, cada um com o id, a revisão
   ou impressão digital e as dimensões no manifesto. Os primeiros: `e5` (local, ONNX) e `pplx`
   (`perplexity/pplx-embed-v1-0.6b`, remoto, pelo OpenRouter, normalizado na ingestão e na pergunta).
3. **A configuração escolhe o modelo.** `embedder: e5 | pplx | hashing` (o `hashing` segue só para suítes). O pack carrega
   só os vetores do escolhido e codifica a pergunta com o mesmo modelo; a combinação errada continua recusada. Default
   **`e5`**, sem dependência de terceiro, até o eval decidir.
4. **O índice de produção é em memória.** O pack carrega o artefato no processo (as fórmulas do `MemoryIndex` da 102,
   RRF sobre denso e esparso) — sem serviço de banco de vetores. O Qdrant continua como opção para corpus grande,
   carregado a partir do artefato por um comando da CLI do pack (sem PDF nem modelo), nunca na subida.
5. **O embedder remoto lê a própria chave** (`AXON_SCOUTING_EMBEDDING_API_KEY`), nunca a do core. A pergunta vai ao
   OpenRouter, como já vai na geração; falha do provedor é falha da recuperação (o `rag_first` encerra sem gerar).
6. **O `prepare` (ADR-041) baixa o e5 só quando ele é o escolhido.** Com `pplx`, a imagem não carrega modelo nenhum.
7. **A escolha se mede.** Dois Assistants, um por modelo, no mesmo conjunto dourado; `axon eval run` em cada um e `axon
   eval compare`, pelas métricas determinísticas (recall@k, MRR).

## Alternativas rejeitadas

*Ingestão na instalação* (hoje). Põe o passo mais pesado justamente na máquina menor, e cada instalação repete o mesmo
trabalho com o mesmo resultado.

*Snapshot do Qdrant no git.* Amarra o artefato ao formato de uma versão do Qdrant e obriga o serviço em toda instalação.

*Um artefato inteiro por modelo.* Duplica trechos e texto original, que não mudam com o modelo.

*Só o modelo remoto.* Torna toda instalação dependente de um terceiro para responder; o e5 local continua sendo a opção
de quem tem memória ou não quer mandar a pergunta para fora.

*O e5 quantizado em int8 desde já.* Reduziria a memória a cerca de um quarto, mas muda a qualidade; fica como terceiro
conjunto de vetores, se o eval o justificar.

## Consequências

- A instalação do scouting não precisa de Qdrant nem de PDF; a CLI `axon-scouting-corpus ingest` passa a gerar o
  artefato (e a ingestão deixa de constar no README da instalação).
- O repositório do pack cresce com os vetores (hoje menos de 3 MB); acima de algumas dezenas de MB, o artefato passa a
  ser asset de release, baixado e conferido pelo `prepare`.
- A versão do pack identifica o índice: a linha de base do eval fica presa a um artefato exato.
- A clarificação da 102 sobre o próximo candidato (`bge-m3` pelo Ollama) cede lugar ao `pplx`; outros modelos entram
  como mais um conjunto de vetores.
