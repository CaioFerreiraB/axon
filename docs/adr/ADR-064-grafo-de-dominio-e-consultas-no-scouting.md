# ADR-064 — No scouting, um grafo de domínio com sete consultas com nome, e a 106 passa a ser o módulo dele

- **Status:** Aceita · 2026-11-10. O mantenedor aceitou a proposta ("pode seguir").
- **Substitui e refina:** substitui o item 3 do [ADR-063](ADR-063-grafo-das-normas-por-orgao-no-scouting.md) (o seam
  `NormGraph` no *Índice do scouting*). Refina:
  - os itens 4 e 5 do ADR-063: `organs` vira `entities`, e o `graph_rank` vira um caso de `sobre`;
  - o [ADR-045](ADR-045-filhotes-e-consulta-multifaceta-no-scouting.md): o `facet_rank` vira um caso de `para_cada`;
  - o [ADR-047](ADR-047-lista-de-documentos-do-acervo-no-scouting.md), o
    [ADR-048](ADR-048-arvore-de-unidades-e-enumeracao-no-scouting.md) e o
    [ADR-062](ADR-062-busca-global-pelas-fichas-das-atas-no-scouting.md): as tools deles viram fachadas de
    `documentos`, `itens` e `linha_do_tempo`.
- **Specs afetadas:**
  - [106-scouting-graphrag](../../specs/106-scouting-graphrag/spec.md): redefinida, é o módulo do grafo de domínio e
    das consultas, com o seam novo *Grafo de domínio*.
  - [101-scouting-pack](../../specs/101-scouting-pack/spec.md): a derivação publica `entities` e `plan`.
  - [102-scouting-corpus-ingestion](../../specs/102-scouting-corpus-ingestion/spec.md): o `NormGraph` sai do seam
    *Índice do scouting*.
  - [103-scouting-retrieval](../../specs/103-scouting-retrieval/spec.md): o retriever executa o plano, e as frentes
    viram uma só.
  - [105-scouting-evaluation](../../specs/105-scouting-evaluation/spec.md): o conjunto `programa-adultos.yaml`, escrito
    antes do código.
- **Origem:** o relatório [O grafo do RAG do scouting](../avaliacao-grafo-rag-scouting-2026-11.md), seções 5, 7, 8, 10
  e 11, aprovado pelo mantenedor em 10/11 ("pode montar o plano"), e o
  [plano SDD da Fase 8](../plano-sdd-grafo-de-dominio-scouting-2026-11.md). As falhas que restam no `scouting` 0.11.1
  são de programa educativo e de adultos:
  - **acervo**, 0,9236: `requisitos-do-escotista` em 0,0, quatro itens em 0,5 e dois em 0,67;
  - **regressão**, 0,9768: `marco-5-ramos`, `marco-ramos-nomeados` e `etapas-cada-ramo`;
  - **síntese**, 0,8462: três itens em 0,33, sobre mandatos, delegados e alterações do regulamento.

## Contexto

O retriever do scouting tem hoje cinco mecanismos que trazem trechos à frente da busca. Cada um foi feito para uma
falha medida e tem estrutura própria:

| Mecanismo | ADR | Consulta que faz |
|---|---|---|
| `graph_rank` | 063 | órgão → seções das normas que o disciplinam |
| `search_summaries` | 062 | órgão, ano, abrangência → fichas de ata |
| `list_documents` | 047, 049 | tipo, órgão, abrangência → fichas do acervo |
| `list_units` | 048 | tipo de unidade, ramo → unidades com nome |
| `facet_rank` | 045 | ramo → uma busca por ramo |

São cinco consultas a um grafo que não existe como um só. Cada forma nova de pergunta pede hoje um mecanismo novo, com
teto e marca próprios. As que falham ("requisitos do escotista", "cada ramo", "patrulha sem adultos") nomeiam
entidades que o grafo do ADR-063 não conhece: cargos, ramos, tipos de seção, áreas e conceitos.

## Decisão

### 1. A 106 é o módulo do grafo de domínio e das consultas

A 106 deixa de ser "um retriever alternativo que substitui a 103". Ela é **o módulo do grafo de domínio**, em
`axon_scouting/rag/graph/` (`api.py`, `domain/`, `adapters/`). É dona de quatro coisas:

- a ontologia;
- a construção offline do grafo;
- o armazenamento em memória;
- as consultas, o esquema do plano e o executor.

O seam novo é **Grafo de domínio**, no `api.py` da 106. Ele traz os tipos das entidades e das arestas, o `QueryPlan`
(com `to_json`/`from_json`), a `Evidence` e a porta das consultas. Consumidores:

- a **103**, que continua sendo o retriever e executa o plano;
- a **101**, pela composição do `pack.py`: os apelidos das entidades para o léxico e o `QueryPlan` para escrever o plano.

A 106 consome, só offline e pelos seams que já existem, o que a 102 produz: o artefato do índice, a árvore de unidades
(`DocumentOutline`), o catálogo (`DocumentCatalog`) e as fichas das atas (`MeetingSummaries`).

### 2. O `NormGraph` sai da 102 para a 106

- Mudam de lugar: `NormSection`, `NormRelation`, a porta `NormGraph`, o `ArtifactGraph`,
  `rag/ingestion/domain/graph.py` e a montagem do `scripts/grafo.py`. Vão para `rag/graph/`. O `scripts/grafo.py`
  continua o ponto de entrada (`build`) e ganha `query` e `export --arrows`.
- O seam *Índice do scouting* fica sem o grafo. A 102 continua dona das unidades, do catálogo e das fichas.
- O artefato é o `graph.jsonl` v2: entidades e arestas, cada uma com `fonte` e `origem`. Continua fora do manifesto,
  ao lado do índice, commitado no pacote.

### 3. Cada tipo de documento tem um papel

A tabela é curada e mora na 106, indexada pelo tipo da taxonomia (`taxonomy_id`, ADR-049). A 102 não muda.

| Papel | Tipos da taxonomia (documentos no acervo) | O que a unidade dá à resposta |
|---|---|---|
| `norma` | Estatuto (2), P.O.R. (1), Regulamento (7), Resolução (273), Política (16), Lei (1) | o que vale, com vigência |
| `orientacao` | Manual (38), Planejamento Estratégico (1) | como fazer, o que se recomenda |
| `registro` | Ata (256), Parecer (3), Relatório (14), Manifestação (1) | o que aconteceu ou foi decidido, com data |
| `comunicacao` | Ofício (7), Edital (5), Boletim (4), Posicionamento (5), Recomendação (4), Apresentação (4) | o que um órgão comunicou, com data |

O papel tem três usos:

- **filtrar** a consulta ("só normas");
- **ordenar** a entrega: norma antes de orientação, a norma de cima antes da de baixo, registro por data;
- **dizer ao prompt como falar** ("o Estatuto determina" × "a ata de 2019 registra"). O papel chega ao trecho como
  metadado, pela 103.

Um tipo novo na taxonomia sem papel falha o build do grafo.

### 4. As entidades e a aresta central, `SOBRE`

**Entidades.** Todas são curadas, com nome, apelidos e fonte:

- tipos de instituição e de órgão;
- as instâncias de instituição e de órgão de que houver informação no acervo (decisão 1 do mantenedor). A que não tem
  fonte fica de fora;
- cargos;
- ramos e tipos de seção;
- áreas;
- conceitos;
- os próprios documentos.

Pessoas não são entidades (decisão 2): o nome de quem foi eleito fica no texto do evento.

Os ids têm a forma `tipo:slug` (`cargo:escotista`, `ramo:pioneiro`, `orgao:dr_sp`, `inst:ge_inah`,
`doc:<document_id>`, `area:…`, `conceito:…`). Tipo e instância são entidades distintas, ligadas por `INSTANCIA_DE`. A
norma disciplina o tipo, e a ata registra a instância. Por isso `sobre` de uma instância inclui o que trata do tipo
dela. A lista de prefixos fica no `design.md` da 106.

**A aresta `SOBRE`.** Vai da unidade à entidade e quer dizer "esta unidade trata desta entidade". Ela leva um **modo**,
que vem do papel do documento:

| Papel | Modo |
|---|---|
| norma | `disciplina` |
| orientação | `orienta` |
| registro | `registra` |
| comunicação | `comunica` |

Vale para qualquer tipo da taxonomia. O `DISCIPLINA` do ADR-063 é o caso "norma × órgão". Como os documentos também
são entidades, "o que as atas dizem do Regulamento Regional" é a mesma consulta que "o que as normas dizem da Diretoria
Regional".

**As outras arestas:**

- de estrutura: `CONTEM` (documento → unidade), `GERA` (unidade → evento datado: reunião, deliberação, eleição,
  alteração), `INSTANCIA_DE`, `PARTE_DE` (órgão → instituição, instituição → instituição), `DE_RAMO` (tipo de seção →
  ramo) e `ATUA_EM` (cargo → tipo de seção ou órgão);
- de documento: `EMITIDO_POR` (→ órgão), `APLICA_SE_A` (→ instituição), `DE_AREA` (→ área), e `ALTERA`, `REVOGA` e
  `SUBSTITUI` (documento → documento);
- de domínio: `REGE` (área → cargo, ramo, tipo de seção), `CITA` (unidade → unidade) e `DE` (evento → órgão, cargo ou
  documento);
- de governança: `ELEGE`, `FISCALIZA`… (decisão 4). Ficam **fora da busca automática** até uma pergunta medida
  pedir, e só `ligados` as consulta.

### 5. Sete consultas e duas regras de composição

As consultas são funções puras sobre os dicionários carregados do artefato, no `domain/` da 106, cada uma com teste.
Devolvem **evidência**, e não resposta. Cada item da evidência traz:

- a unidade ou o evento;
- o documento;
- o papel;
- a data;
- a fonte da aresta que o trouxe.

| # | Consulta | Entrada | Devolve | Substitui ou generaliza |
|---|---|---|---|---|
| 1 | `reconhecer(texto)` | a pergunta | as entidades mencionadas, pelos apelidos, pelo nome mais longo | `organ_terms` e o léxico de ramos |
| 2 | `sobre(entidades, modo=todas\|alguma, papeis, tipos, ramo, periodo)` | uma ou mais entidades | as unidades que tratam delas, em qualquer tipo de documento | `graph_rank`, `facet_rank` |
| 3 | `aplicavel_a(instituicao, papeis=norma)` | uma instituição | os documentos que valem para ela, subindo o `PARTE_DE`, de cima para baixo | nova |
| 4 | `documentos(tipo, emissor, aplica_se_a, area, ramo, periodo, vigente)` | filtros | documentos | `list_documents` |
| 5 | `itens(tipo_de_unidade, de, ramo)` | o tipo de unidade ou de entidade e o dono | unidades com nome ou entidades filhas, com fonte | `list_units` |
| 6 | `linha_do_tempo(alvo, eventos, periodo)` | entidade ou documento | eventos datados | `search_summaries` |
| 7 | `ligados(alvo, relacoes)` | unidade, documento ou entidade | os vizinhos, com a fonte: citações, alterações, governança | `NormGraph.relations`, hoje sem uso |

As duas regras ficam no executor, e não em consultas novas:

- **`para_cada(entidades, consulta)`** responde "cada ramo" e as comparações. Roda a consulta para cada entidade e
  reparte as vagas entre elas, as do grafo e as da busca, como o `facet_rank` faz hoje com a busca por ramo.
- **Interseção.** `sobre([A, B], modo=todas)` traz as unidades que tratam das duas entidades ao mesmo tempo. E
  `aplicavel_a` filtra `sobre` pela instituição.

`reconhecer` é a mesma função na derivação (101), no executor e no `scripts/grafo.py query`. Os apelidos chegam à
derivação pelo `pack.py`, que os injeta no léxico como hoje injeta os `organ_terms`, e ela continua pura.

### 6. O plano viaja em `retrieval_filters`

A pergunta vira um **plano**: dados num esquema fechado (`QueryPlan`) que dizem quais consultas rodar, com quais
entidades e em que forma (simples, `para_cada` ou interseção).

- **Quem escreve:** a derivação (101), pelo léxico. Ela publica `entities` (que substitui `organs`) e `plan` em
  `retrieval_filters`.
- **Quem roda:** o executor da 106, chamado pela 103. É código fixo.
- **Não há linguagem de consulta em tempo de execução.** O modelo nunca escreve consulta. O planejador, num incremento
  futuro e noutro ADR, só vai escolher entidades de um enum.
- **Core e contratos não mudam.** O plano viaja opaco, como os filtros de hoje, e plano ausente ou inválido deixa a
  pergunta seguir como hoje, só com a busca.

### 7. Toda aresta tem fonte e origem

Toda aresta (e toda entidade curada) tem:

- uma **`fonte`**: o trecho ou a unidade do artefato, o item da ficha de ata com a página, ou a entrada da taxonomia
  ou do catálogo curado que a justifica;
- uma **`origem`**, com três valores:
  - `curado`: no catálogo curado, com a fonte e a citação;
  - `regra`: por regra sobre títulos, tipos de unidade, `branches`, a pasta e o nível da taxonomia, ou o texto
    ("Revoga a Resolução…");
  - `modelo_conferido`: por modelo, **só offline**, com a fonte conferida por código contra a página, como as fichas
    do ADR-062. O que não confere não entra.

Vale a ordem "regra antes de modelo", e não há extração de esquema livre. O modelo offline entra só onde a regra não
alcança, com o custo estimado antes. O primeiro caso previsto é a ementa das resoluções que a primeira frase não
resolve.

A aresta **nunca é citada**: ela só leva a trechos, e a citação continua sendo o trecho, pela 104, que não muda. Assim
a FR-002 e a FR-003 da 106 continuam valendo: a origem fica registrada, e o que um modelo propôs nunca aparece como
fonte de documento.

### 8. O grafo ocupa as primeiras vagas, com teto, e a busca híbrida roda sempre

- **Ordem.** As frentes do grafo vêm primeiro, na ordem das consultas do plano. Depois vem a busca híbrida (e5 + BM25),
  que roda em toda pergunta. Um trecho que aparece nas duas fica só na primeira posição.
- **Teto por consulta.** É o do ADR-063: até 3 documentos e, em cada documento, até 3 trechos, os que mais casam com a
  pergunta (o BM25 de `domain/terms.py`).
- **Teto total do grafo.** 8 das 20 vagas, ajustável depois de medido. `para_cada` reparte as vagas entre as entidades.
- **Sem entidade reconhecida,** o plano fica vazio e a pergunta segue como hoje.
- **As tools continuam com o mesmo nome e a mesma saída:** `search_summaries`, `list_documents` e `list_units` viram
  fachadas de `linha_do_tempo`, `documentos` e `itens`.

### Pontos que o `/speckit-clarify` da 106 confirma

O plano SDD (seção 6) traz recomendações, e este ADR as adota. O clarify pode confirmá-las ou trocá-las antes do
`/speckit-plan`:

- o esquema do plano é da 106 (item 1);
- a tabela de papéis é da 106, pelo tipo da taxonomia (item 3);
- os tetos (item 8);
- o catálogo curado é um arquivo só, `corpus/organizacao.yaml`, com seções novas para cargos, ramos e tipos de seção,
  áreas, conceitos e instâncias;
- o modelo offline na ementa só depois de medir o que a regra cobre (item 7).

## Alternativas rejeitadas

- **LlamaIndex (`PropertyGraphStore` e a extração dele).** O armazenamento é o mesmo que o nosso, dicionários em
  memória persistidos em arquivo, e vem com uma dependência enorme. A extração dele é de esquema livre.
- **Neo4j, ou outro serviço de grafo, na instalação.** É um serviço JVM com cerca de 1 GB de RAM numa VM pequena, mais
  o backup. Ganharia só a exploração visual e o Cypher, e o mantenedor os tem offline: o `scripts/grafo.py export
  --arrows` mostra o grafo no editor onde ele foi desenhado. O grafo tem centenas de entidades e algumas dezenas de
  milhares de arestas, poucos MB em memória. SQLite também não ganha nada: ninguém consulta ad hoc em produção.
- **Texto para Cypher, ou qualquer consulta escrita por modelo em tempo de pergunta.** Um modelo pequeno escreve
  consulta errada sem que ninguém perceba. As formas de pergunta cabem em sete funções com nome, e o modelo, quando
  entrar (o planejador), escolhe entidades de um enum.
- **Extração livre de entidades e relações por LLM.** O resultado não é verificável e é ruidoso. O ADR-063 mostrou que
  títulos, tipos de unidade e a taxonomia ligam a maior parte por regra. O modelo fica offline, com a fonte conferida.
- **Pessoas como nós (decisão 2 do mantenedor).** O ganho é baixo, e o custo é desambiguar homônimos e manter o
  cadastro. A pergunta sobre uma pessoa segue pela busca textual nas fichas e nos trechos.
- **A 106 como retriever substituto da 103 (o rascunho de 2026-09).** Duplicaria a busca híbrida, os filtros e o
  reranker, e o ganho medido vem de frentes à frente da busca, não de outra busca. O grafo é um módulo que o retriever
  consulta.
- **Manter os cinco mecanismos separados.** Cada forma nova de pergunta pediria um sexto, com estrutura, teto e marca
  próprios. "O que mudou numa norma" e "o que um órgão publicou" já não cabem em nenhum dos cinco.

## Consequências

**Seams** (a atualizar no `specs/README.md`):

- seam novo *Grafo de domínio* (106 → 101 e 103);
- o `NormGraph` sai do *Índice do scouting*;
- no diagrama, entram `S103 --> S106` e `S101 --> S106`, e fica `S106 --> S102`.

**Specs:**

- **101, 102 e 103** ganham um FR cada que cita este ADR, mais um registro no `research.md`, como no ADR-063:
  - a 101 troca `organs` por `entities` e `plan`;
  - a 102 remete o grafo à 106;
  - a 103 executa o plano e une as frentes.
- **105** ganha a US7, o conjunto `eval/programa-adultos.yaml`, com cerca de 30 itens, metade de controle, e as formas
  da seção 11.6 do relatório. A linha de base dele é gravada com o 0.11.1 **antes de qualquer código**.
- **104, core e contratos não mudam.**

**Implementação, em incrementos medidos (G1 a G6, e G7 opcional):**

- O **G1** só muda de lugar o que existe e grava o `graph.jsonl` v2. Os quatro conjuntos (acervo, regressão, síntese e
  programa-adultos) têm de dar números **idênticos** aos do 0.11.1.
- Cada incremento seguinte mostra o `fact_recall` antes e depois, por item, nos quatro conjuntos. O que derrubar um
  conjunto não entra.
- Cada incremento que muda o artefato ou o comportamento é um `scouting` menor, a partir do 0.12.0.

**Invariantes do artefato,** num teste como o `test_artifact_quality.py`:

- toda aresta tem fonte resolvível;
- nenhum id de entidade é órfão;
- toda aresta `modelo_conferido` foi conferida;
- todo tipo da taxonomia tem papel.

**Instalação:** nada novo. A cópia do índice já leva o `graph.jsonl`, e o v2 é um arquivo maior no mesmo lugar.

**Manutenção:**

- uma entidade nova é uma entrada no catálogo curado, com a fonte, seguida de um `scripts/grafo.py build`;
- uma ingestão nova pede o build de novo;
- o mantenedor consulta o grafo com `scripts/grafo.py query <consulta> <args>`, que roda as mesmas funções, e o vê no
  arrows.app.

**Fora desta fase:**

- o **planejador** (papel opcional do Model Router, que muda o core e pede outro ADR);
- a **força normativa** da unidade (`obriga`, `proibe`, `faculta`, `recomenda`), que fica como incremento opcional, o G7.
