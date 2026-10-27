# ADR-045 — Ramo Filhotes e pergunta sobre vários ramos no scouting

- **Status:** Aceita · 2026-10-27
- **Specs afetadas:** [101-scouting-pack](../../specs/101-scouting-pack/spec.md) (léxico, derivação e o contrato
  `retrieval_filters`), [102-scouting-corpus-ingestion](../../specs/102-scouting-corpus-ingestion/spec.md) (ids de ramo
  do índice e do catálogo), [103-scouting-retrieval](../../specs/103-scouting-retrieval/spec.md) (busca por faceta e a
  ordem que o reranker reconstrói), [105-scouting-evaluation](../../specs/105-scouting-evaluation/spec.md) (o campo novo
  em `extra.context`)
- **Origem:** revisão do RAG de 2026-10-27 ([relatório](../revisao-rag-scouting-2026-10.md)): "Qual o marco simbólico
  dos 5 ramos?" chegava à geração com a formulação de um ramo só

## Contexto

O pack conhece quatro ramos — Lobinho, Escoteiro, Sênior e Pioneiro. O Ramo Filhotes, que o POR 2025 já regula
(Capítulo 8), não tem id: o catálogo não aceita `branch: filhotes`, os documentos dele são "gerais" e entram em toda
busca filtrada por outro ramo, e uma pergunta sobre Filhotes não filtra nada.

Uma pergunta sobre vários ramos ("de cada ramo", "dos 5 ramos", ou dois ramos nomeados) também não filtra (101 R8: na
dúvida, nenhum filtro), e a recuperação devolve os trechos que mais se parecem com a pergunta inteira — em geral, de um
ou dois ramos. O core entrega à geração os primeiros `AXON_RAG_PASSAGES` (5) na ordem do reranker do pack. Medido no
índice de 2026-10-27: com uma subbusca por ramo ("pergunta + Ramo X", filtro do ramo), a evidência do marco simbólico
e do lema fica em 1º lugar em 9 das 10 combinações; na busca única, uma ou duas facetas de cinco chegam à geração.

## Decisão

1. **`filhotes` é um id de ramo** do pack: no índice (`BRANCHES`, 102), no catálogo (`branch: filhotes`) e no léxico da
   101 (filhote, filhotes, ramo filhotes, ninhada, ninhadas). A ordem dos ids é a das idades: filhotes, lobinho,
   escoteiro, senior, pioneiro.
2. **A derivação publica as facetas** quando a pergunta cita dois ramos ou mais, ou usa um marcador de totalidade do
   léxico ("cada ramo", "os ramos", "5 ramos", …; com o marcador, os cinco ramos): `branches` no contexto e nos
   `retrieval_filters`, na ordem do léxico, e nenhum `branch`. Um ramo só continua `branch`. O contrato
   `retrieval_filters` (101 → 103) ganha a chave `branches` (lista de ids, dois ou mais).
3. **O retriever busca por faceta**: com `branches`, uma busca por ramo, com o filtro do ramo e a pergunta seguida do
   nome do ramo, e `top_k` repartido entre as facetas. O resultado intercala as facetas — o primeiro de cada ramo, depois
   o segundo… —, sem trecho repetido (um trecho geral achado por duas facetas fica na primeira), e grava nos metadados a
   faceta e a posição dentro dela. O `MetadataReranker` reconstrói essa ordem pelas marcas (como já faz com a fusão), e o
   core entrega à geração, nos primeiros trechos, um de cada ramo.
4. **Nada muda no core nem no contrato 001**: `retrieval_filters` é opaco para o core, e o reranker devolve os trechos
   da recuperação, sem repetir, no máximo `top_k` (005).

Precedência editorial **não** entra: a revisão supôs que os "Competências e Rotas de Aprendizagem" de 2019 fossem
edições preliminares, mas "PRELIMINAR" neles é o nome de um nível de competência. As formulações divergentes deles diante
dos manuais de 2025–26 são uma questão de curadoria — se um documento substitui o outro —, e o catálogo já a resolve com
`supersedes` e as datas de vigência.

## Consequências

- Os documentos de Filhotes deixam de aparecer nas buscas filtradas por outro ramo, e uma pergunta sobre Filhotes
  filtra.
- Uma pergunta sobre os cinco ramos entrega um trecho por ramo com os 5 trechos do default; com `AXON_RAG_PASSAGES`
  maior, dois ou mais por ramo. O que fica em 1º lugar dentro de cada faceta ainda é a ordem da fusão: a seleção que lê a
  pergunta é a do reranker v2/v3 (103), à parte.
- O corte do gateway sobre os candidatos (16 KB, 004/005) mantém os primeiros da lista intercalada — dois ou três de
  cada ramo com 20 candidatos —, então não tira faceta nenhuma.
- A 105 aceita `branches` em `extra.context`; a semente e o conjunto de regressão podem declarar a derivação esperada.
- Mudar a lista de ramos de novo exige atualizar o léxico, `BRANCHES`, o contrato `retrieval_filters` e este ADR juntos.

## Alternativas

- **Mais candidatos ou mais trechos, sem faceta**: medido na revisão (E2–E4): nem com 60 candidatos e 20 trechos a busca
  única cobre os cinco ramos.
- **Reescrever a pergunta por faceta** (tirar "dos 5 ramos" e pôr "do Ramo X"): mesma qualidade que acrescentar o nome
  do ramo na medição, com uma regra de texto a mais.
- **Decompor no core** (uma etapa de "subperguntas" no `rag_first`): a faceta é conceito do domínio, e o core é
  agnóstico (princípio I).
- **Chunk com ramo próprio** (a regra do POR do Capítulo 8 marcada como Filhotes): o ramo é metadado de documento no
  índice (102); muda o modelo do trecho e fica para quando a medição pedir.
