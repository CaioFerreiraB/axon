# ADR-062 — No scouting, a pergunta de síntese recebe resumos das atas: fichas de reunião extraídas offline e uma linha do tempo por órgão e ano

- **Status:** Aceita · 2026-11-09 (o mantenedor aprovou a busca global por resumos prontos, "vamos seguir com isso", no
  plano do relatório [Diretoria Regional](../revisao-rag-scouting-2026-11-diretoria-regional.md))
- **Specs afetadas:**
  - [101-scouting-pack](../../specs/101-scouting-pack/spec.md): o pedido `synthesis` e o prompt.
  - [102-scouting-corpus-ingestion](../../specs/102-scouting-corpus-ingestion/spec.md): as fichas, os resumos e o
    seam `MeetingSummaries`.
  - [103-scouting-retrieval](../../specs/103-scouting-retrieval/spec.md): a tool `search_summaries`.
  - [105-scouting-evaluation](../../specs/105-scouting-evaluation/spec.md): o conjunto de síntese.
- **Origem:** o relatório separou as perguntas pontuais, cuja resposta está num artigo, das de síntese, cuja resposta
  está espalhada pelas atas ("quem foram os diretores-presidentes desde 2016?", "onde se reuniu o Conselho Consultivo
  entre 2017 e 2019?"). Vinte trechos não cobrem 39 atas da Assembleia Regional; o conjunto `eval/sintese.yaml`, escrito
  antes da mudança, mediu `fact_recall` 0,4551.

## Contexto

O acervo tem 256 atas, cerca de 1,8 milhão de tokens: 104 do CAN, 39 da Assembleia Nacional, 39 da Assembleia Regional
SP, 33 da Rede de Jovens Líderes, 33 dos Conselhos Consultivos, 6 do Programa Educativo regional e 2 da Comissão
Fiscal Nacional.

O GraphRAG da Microsoft responderia à síntese com map-reduce sobre resumos de comunidades, o que custa várias chamadas
de modelo por pergunta, e os resumos não têm nem página nem vigência. Resumir em prosa por período tem outros dois
problemas: exige uma segunda passada do modelo, e 256 resumos em prosa não se revisam.

## Decisão

1. **Uma ficha estruturada por ata, extraída offline.**
   - `scripts/fichas.py extract` lê a ata página por página, como o artefato a guarda, e pede ao modelo, num esquema
     JSON estrito:
     - o tipo, a data e o local da reunião;
     - as deliberações, com a decisão nas palavras da ata;
     - as eleições, com o nome como a ata escreve;
     - os números da reunião.
   - Cada item leva a página.
   - O modelo padrão é o `openai/gpt-4.1-mini` pelo OpenRouter, com a chave só no ambiente.
   - A ficha vai para `corpus/resumos/atas/<doc_key>.yaml`, no git.
   - Só se reextrai quando o texto muda (`extracao.fontes_sha256`).
2. **Cada item é conferido por código contra a página.** A página citada, ou uma vizinha, precisa conter ao menos 60%
   das palavras de conteúdo do item, e um número precisa aparecer com os mesmos algarismos. O item que não confere fica
   na ficha com `conferido: false`, para revisão, e não entra no índice. A revisão humana é por amostra.
3. **Os resumos são montados por código, sem modelo** (`scripts/fichas.py build`, `rag/ingestion/domain/minutes.py`):
   - **a ficha da reunião**: só com os itens conferidos;
   - **a linha do tempo do órgão** (a categoria da pasta, com a abrangência) **num ano**:
     - uma linha por item conferido, em ordem de data, com "ata de dd/mm/aaaa, p. N";
     - sem os itens de procedimento (mesa, comissões assessoras, ata anterior, pauta);
     - a decisão encurtada;
     - a mesma linha das duas vias de uma ata (as cópias de cartório) uma vez só.
   - Partes de até ~1.800 caracteres.
   - Tudo vai para `summaries.jsonl`, ao lado do índice do pacote. Ele não tem vetores nem entra no manifesto: os
     resumos não passam pela busca densa.
4. **Seam *Índice do scouting* (102 → 103):** `SummaryEntry` e a porta `MeetingSummaries.summaries()`. O adapter
   `ArtifactSummaries` lê o arquivo nos dois armazenamentos (memória e Qdrant), porque o artefato vem no pacote.
5. **Pedido de síntese (101):** `synthesis: {year_from, year_until, scopes, bodies}`. Ele aparece com:
   - um marcador ("ao longo", "desde", "quem foram", "onde se reuniu", "decidiu", "nas atas", "quantos delegados"…);
   - ou uma palavra de reunião (assembleia, reunião, ata, gestão, eleito) e um ano.

   Os anos: o menor e o maior citados; "desde 2016" vai até o ano de referência; "nos anos 2000", a década. As palavras
   que também aparecem em perguntas pontuais ("em que cidade", "reeleito", "chapas") não disparam sozinhas.
6. **A tool `scouting.search_summaries` (103)** só responde ao pedido de síntese:
   - **Candidatos**: escolhidos pela abrangência e pelos anos. Com um ano só, a janela vai de um ano antes a três
     depois.
   - **Órgão nomeado**: só os resumos dele; sem nenhum, os que falam dele (as eleições da Diretoria Regional estão nas
     atas da Assembleia).
   - **Ordem**: pelos termos da pergunta (plural reduzido, frequência saturada, IDF), com bônus para o ano citado, os
     anos recentes quando a pergunta pede "as últimas" e a abertura da ficha quando ela pergunta "onde".
   - **Limites**: no máximo 2 partes por ano ou reunião (a melhor de cada uma antes da segunda de qualquer outra), 6
     linhas do tempo e 10 resumos.
   - **Posição**: os resumos vêm à frente dos trechos (marca `summary_rank`), e os trechos das atas continuam vindo pela
     busca comum.
7. **O prompt** manda responder em ordem de data, dizer de que ata e página vem cada fato, citar o resumo e nunca
   apresentá-lo como regra.

## Alternativas rejeitadas

- **Map-reduce na hora da pergunta** (GraphRAG global): várias chamadas por pergunta; o `rag_first` faz uma.
- **Resumo em prosa por órgão e período**: segunda passada de modelo, revisão inviável e nenhuma página por fato.
- **Resumos com vetor no índice**: mudaria o artefato e o manifesto a cada ata. Com órgão, abrangência e anos, a
  seleção por metadado e termos basta, e é determinística.
- **Entregar resumos a toda pergunta**: numa pergunta pontual, eles tomariam as vagas do artigo, o mesmo abafamento das
  atas.

## Consequências

- **Extração.**
  - Piloto nas 58 atas regionais de SP: 1.796 de 1.902 itens conferidos (94,4%), US$ 0,36. A ata de 1996, com OCR
    ruim, teve 18 de 64.
  - As 256 atas: 5.298 de 5.677 itens conferidos (93,3%), cerca de US$ 1,30, e 1.196 resumos (680 partes de ficha, 516
    de linha do tempo), 2,4 MB.
  - Duas atas falharam na primeira passada (uma eleição sem nome). O extrator passou a descartar o item incompleto em
    vez da ficha.
- **Medição com os mesmos fatos.**
  - O conjunto de síntese foi de 0,4551 (sem resumos) a 0,8718 no piloto e a **0,8462** com as 256 atas. Com mais
    órgãos concorrendo, a seleção ganhou o filtro por órgão nomeado e a melhor parte de cada ano antes da segunda. Só o
    item "mandatos das três últimas Diretorias" ficou abaixo do piloto (0,33), e ele não foi ajustado à parte.
  - Os itens de controle subiram junto.
  - `golden`, regressão (0,9768) e acervo (0,8768) ficaram iguais, e nenhuma das 84 perguntas pontuais pede síntese.
- O `eval.yml` do pack ganha o conjunto de síntese, e os caminhos `src/axon_scouting/data/**` passam a disparar o
  workflow.
- **Instalação**: a cópia do índice em `axon-cfblabs/packages/scouting-index/` precisa levar `summaries.jsonl` junto.
- **Atualização**: atas novas exigem `extract` e `build` no desenvolvimento, como a ingestão.
- **Grafo**: as eleições das fichas viram instâncias de `ELEGE` quando o grafo da Fase 2 for construído.
