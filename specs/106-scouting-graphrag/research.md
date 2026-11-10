# Research — 106 Grafo de domínio e consultas do scouting

Decisões pré-aprovadas pelo [ADR-064](../../docs/adr/ADR-064-grafo-de-dominio-e-consultas-no-scouting.md) e pela
clarificação de 2026-11-10, levadas aqui sem re-pesquisa. Os números de base são os do `scouting` 0.11.1: acervo
0,9236, regressão 0,9768, síntese 0,8462 e programa-adultos 0,8409 (105 R26).

## R1 — A 106 é o módulo do grafo, e não um retriever

- **Decision**: a 106 fica com a ontologia, a construção offline, o grafo em memória, as consultas, o plano e o
  executor, em `rag/graph/`, e expõe o seam *Grafo de domínio*. A 103 continua sendo o retriever e o consome. A 101 o
  consome pela composição do `pack.py`.
- **Rationale** (ADR-064, item 1): o ganho medido nos ADRs 045 a 063 veio de frentes à frente da busca, e não de outra
  busca. Um retriever concorrente duplicaria a busca híbrida, os filtros e o reranker.
- **Alternatives**: a 106 como retriever substituto, que era o rascunho de 2026-09; manter os cinco mecanismos
  separados. As duas foram rejeitadas no ADR-064.

## R2 — A migração do `NormGraph` (G1)

- **Decision**: `NormGraph`, `NormSection`, `NormRelation`, o `ArtifactGraph`, `rag/ingestion/domain/graph.py` e a
  montagem do `scripts/grafo.py` passam para `rag/graph/`. O `graph.jsonl` é regravado no v2. A 101 troca `organs` por
  `entities` e `plan`, e a 103 executa o plano com a ordem e os tetos do `_by_organ`. O G1 é provado de dois jeitos:
  - os quatro conjuntos com o mesmo `fact_recall` em todos os itens;
  - um teste que compara os `chunk_id` à frente, antes e depois, para as perguntas do acervo.
- **Rationale** (ADR-064, item 2; FR-015; SC-001): mudar a arquitetura e o comportamento ao mesmo tempo confunde efeito
  com causa.
- **Alternatives**:
  - manter o `NormGraph` na 102 e criar o grafo novo ao lado: dois grafos;
  - migrar já no G2: a primeira medida misturaria a migração com o ganho.

## R3 — O papel do tipo de documento

- **Decision**: a tabela de papéis fica no `api.py` da 106 (`ROLES`, por `taxonomy_id`):
  - `norma`: estatuto, por, regulamento, resolucao, politica, lei;
  - `orientacao`: manual, planejamento_estrategico;
  - `registro`: ata, parecer, relatorio, manifestacao;
  - `comunicacao`: oficio, edital, boletim, posicionamento, recomendacao, apresentacao.

  Um tipo sem papel falha o build. O papel chega ao trecho pela 103 (`role`).
- **Rationale** (ADR-064, item 3; clarify Q5): o papel serve para filtrar, ordenar e orientar o prompt. Mantê-lo na 106
  não muda o seam nem o artefato da 102. As instruções normativas da DR-SP estão com o tipo `resolucao` na taxonomia e
  são normas (105 R26).
- **Alternatives**: o papel como campo do catálogo da 102 (mudaria o seam e regravaria o artefato); papel por
  documento (são 642 linhas curadas contra 18).

## R4 — Ontologia: ids, tipo e instância, sem pessoas

- **Decision**:
  - **Ids:** `tipo_inst:`, `tipo_orgao:`, `inst:`, `orgao:`, `cargo:`, `ramo:`, `secao:`, `area:`, `conceito:` e
    `doc:`.
  - **Nós do acervo:** a unidade pelo `unit_id` do artefato (`<doc_key>#u/…`, único), a versão pelo `doc_key` e o
    evento por `evento:<doc_key>#<n>`.
  - **Tipo e instância:** são distintos e se ligam por `INSTANCIA_DE`. `sobre` de uma instância inclui o tipo dela.
  - **Ids do G1:** os de hoje, `tipo_orgao:<slug>` e `tipo_inst:<slug>`.
- **Rationale** (ADR-064, item 4; decisões 1 e 2 do mantenedor): a norma disciplina o tipo, e a ata registra a
  instância. O `unit_id` do artefato já é único, então não há id novo para manter.
- **Alternatives**:
  - um id só para tipo e instância: a DR-SP e "a Diretoria Regional" do Estatuto seriam a mesma coisa;
  - pessoas como nós: rejeitado no ADR-064.

## R5 — O catálogo curado em dois arquivos

- **Decision**: os dados curados ficam em dois arquivos.
  - `corpus/organizacao.yaml` fica com a organização: tipos de instituição e de órgão, `instituicoes` e `orgaos` (a
    partir do G3, só com fonte), cargos e relações de governança. O cabeçalho de "rascunho" sai.
  - `corpus/dominio.yaml`, novo, fica com o programa: `ramos` (saem do `organizacao.yaml`), `secoes`, `areas`,
    `conceitos`, e as arestas `REGE`, `DE_RAMO` e `ATUA_EM`.

  Toda entrada tem `fonte`. A que tiver `fonte: a verificar` não entra no grafo, como hoje.
- **Rationale** (clarify Q3): a divisão é por tema. O `organizacao.yaml` já tem o formato e a conferência das fontes de
  governança, e o programa é curado separadamente. O ADR-064 deixava o arquivo ao clarify.
- **Alternatives**: um arquivo só, que era a recomendação do plano e não foi escolhida.

## R6 — `SOBRE` e as regras de aresta

- **Decision**: a aresta `SOBRE(modo)` vai da unidade à entidade, e o modo vem do papel. As regras, em ordem:
  1. o título da unidade nomeia a entidade, pelo nome mais longo (ADR-063);
  2. o regulamento cujo título nomeia um órgão vale inteiro (ADR-063);
  3. `branches` da unidade → `ramo:`;
  4. `kind` da unidade → `conceito:` (especialidade, etapa, bloco, insígnia, cargo);
  5. a categoria da taxonomia → `DE_AREA`;
  6. nas atas, o tema e a decisão de cada item da ficha, pelo `reconhecer` (G4);
  7. nas resoluções, a ementa (G5, R12).

  Instituições nunca valem pelo título do documento.
- **Rationale** (ADR-064, itens 4 e 7; ADR-063; 102 R42): os títulos e a árvore já dizem a maior parte, a regra é
  determinística e testável, e o ADR-063 mediu o "documento inteiro" para órgãos.
- **Alternatives**: extração de esquema livre por LLM (rejeitada no ADR-064); só o título, sem `branches` nem `kind`
  (perderia os guias, em que o ramo é o documento).

## R7 — Sete consultas com nome

- **Decision**: `reconhecer`, `sobre`, `aplicavel_a`, `documentos`, `itens`, `linha_do_tempo` e `ligados`, puras, em
  `domain/queries.py`, com as assinaturas do design.md (seção 3). Elas devolvem `Evidence`, e não trechos. O
  `reconhecer` também fica exposto no `api.py`.
- **Rationale** (ADR-064, item 5): as formas de pergunta dos conjuntos cabem nelas (relatório, 11.6), e cada uma
  generaliza um mecanismo de hoje.
- **Alternatives**: uma linguagem de consulta (Cypher, SPARQL) ou consultas escritas por modelo, rejeitadas no ADR-064.

## R8 — O plano em `retrieval_filters`

- **Decision**: o plano viaja em `retrieval_filters.plan` como `QueryPlan.to_json()`, e as entidades em `entities`.
  - **Esquema:** fechado, com versão 1, e é da 106 (`contracts/query-plan.schema.json`).
  - **Ausente ou vazio:** só a busca.
  - **Inválido:** só a busca, com um aviso no log que nomeia o campo, e nunca erro ao usuário.
  - **Chaves do filtro:** `entities` e `plan` entram no `KNOWN` da 103, e `organs` sai.
- **Rationale** (ADR-064, item 6; clarify Q5): core e contratos não mudam. O plano é um otimizador, e sem ele a
  resposta continua correta. Os filtros restringem a busca e, errados, mudariam a resposta, por isso falham explícitos
  (103 FR-007).
- **Alternatives**:
  - recusar o plano inválido como os filtros: troca uma resposta boa por erro;
  - um campo no contrato 001: mudaria os contratos.

## R9 — O executor, os tetos e quem escolhe os trechos

- **Decision**: o executor aplica as formas `simples`, `para_cada` e `intersecao`. Ele ordena por papel, nível e data,
  corta em até 3 documentos por consulta e devolve todos os trechos de cada unidade.
  - **A 103 escolhe os trechos:** até 3 por documento, pelo BM25 dela (`rag/retrieval/domain/terms.py`).
  - **Teto total:** 8 das 20 vagas para o grafo, repartidas por entidade em `para_cada`, a partir do G2. O G1 fica com
    3 × 3, como o ADR-063, para ser idêntico (analyze I1).
  - **Facetas:** a busca por faceta (ADR-045) continua na 103, e o `facet_rank` passa a ser `para_cada` sobre os ramos.
- **Rationale** (clarify Q1 e Q2; ADR-063; ADR-045): a 106 não lida com o texto da pergunta além do `reconhecer`, e os
  tetos de hoje são o ponto de partida medido. O teto total protege a busca, que acerta a maior parte.
- **Alternatives**:
  - a 106 escolher os trechos: levaria o BM25 para lá, ou o duplicaria;
  - sem teto total: um plano de 3 consultas tomaria as 20 vagas;
  - 10 de 20.

## R10 — O artefato `graph.jsonl` v2

- **Decision**: um registro JSON por linha:
  - `meta`, com a versão 2, o chunking do índice e o sha256 dos YAML curados;
  - `entity`;
  - `version`;
  - `unit`, só as usadas por alguma aresta;
  - `edge`;
  - `event`.

  O arquivo fica fora do manifesto, ao lado do índice. Na carga, um chunking diferente do manifesto é recusado com uma
  mensagem que manda rodar `scripts/grafo.py build`. Um arquivo ausente vale como grafo vazio, como hoje.
- **Rationale** (ADR-064, item 2; relatório, seção 6): o formato é diffável, carrega em dicionários e é o mesmo
  mecanismo do `summaries.jsonl`. A recusa evita um grafo que aponta para trechos de outro build.
- **Alternatives**: SQLite, ou o LlamaIndex `SimplePropertyGraphStore`, rejeitados no ADR-064 e no relatório, seção 6;
  pôr o grafo no manifesto, o que obrigaria a reindexar para mudar um apelido.

## R11 — Armazenamento em memória, sem serviço

- **Decision**: o `DomainGraph` é formado por dicionários imutáveis, montados uma vez por processo pelo
  `DomainGraphService` com uma trava, como o `ArtifactGraph` de hoje.
- **Rationale** (ADR-064, alternativas; relatório, seção 6): são poucos MB e travessias de 1 a 5 saltos.
- **Alternatives**: Neo4j (um serviço JVM de cerca de 1 GB numa VM pequena), SQLite, networkx (dependência para o que
  dicionários fazem).

## R12 — Fontes, origens e o modelo offline

- **Decision**: toda aresta e toda entidade curada têm `source` e `origin` (`curado`, `regra` ou `modelo_conferido`).
  - **Ementas (G5):** primeiro a regra, na primeira frase. Mede-se quantas ficam sem assunto, e só nessas roda o
    `gpt-4.1-mini` pelo OpenRouter, com a chave só no ambiente e o custo estimado e aprovado antes.
  - **Conferência:** a saída do modelo é conferida contra a página por código, como as fichas do ADR-062. O que não
    confere não entra, e fica no relatório do build.
- **Rationale** (ADR-064, item 7; clarify Q4; ADR-062): regra antes de modelo e modelo só conferido, com o mesmo
  mecanismo, já medido, das fichas.
- **Alternatives**: só regra (deixaria resoluções sem assunto); modelo em todas (menos determinístico onde a regra
  basta).

## R13 — Portas e adapters

- **Decision**: o seam `DomainGraphSource` é implementado pelo `DomainGraphService` (`service.py`). As portas
  secundárias são:
  - `GraphStore`, com o `ArtifactGraphStore` e o `MemoryGraphStore`;
  - `GraphSources`, offline, com o `ArtifactSources`;
  - `ResolutionSummarizer`, offline, com o adapter do OpenRouter e um simulado.

  As consultas, o executor, as regras de aresta e os papéis ficam puros no `domain/`.
- **Rationale** (ADR-012; constituição XIII): há porta só onde há I/O. O mesmo serviço roda sobre o artefato e sobre a
  memória, para a conformidade.
- **Alternatives**: o adapter implementar o seam direto, como o `ArtifactGraph` faz hoje com o `NormGraph`. Funciona,
  mas a conformidade passaria a testar a leitura do arquivo junto com as consultas.

## R14 — Import-linter

- **Decision**:
  - **Camadas do pack:** o contrato "só o pack.py compõe" passa a pôr `context | prompts | validators` acima de
    `rag`.
  - **Limite da 101:** um `forbidden` limita `axon_scouting.context` a `axon_scouting.rag.graph.api`, proibindo
    `rag.index`, `rag.retrieval`, `rag.ingestion`, `rag.graph.domain` e `rag.graph.adapters`.
  - **Camadas da 106:** `adapters` > `service` > `ports | domain` > `api`.
  - **`api.py`:** não importa o resto do módulo.
  - **Infraestrutura:** `yaml` e o SDK do modelo, só em `rag.graph.adapters`.
  - **Fora da 106:** os outros módulos importam só `rag.graph.api`.
- **Rationale** (constituição II e XIII; clarify Q5): a 101 escreve o plano com o esquema da 106, e nada em `rag/`
  importa `context/` hoje.
- **Alternatives**: a 101 montar o plano como dicionário solto, sem importar a 106: duas definições do contrato.

## R15 — Medida e versões

- **Decision**:
  - **Medida:** todo incremento roda os quatro conjuntos e mostra o `fact_recall` antes e depois, por item e por
    grupo (`scripts/eval_diff.py`, 105 FR-026).
  - **Bloqueio:** o que derruba um conjunto (abaixo da linha de base, tolerância 0,02) não entra.
  - **Versão:** cada incremento que muda o artefato ou o comportamento é um `scouting` menor, a partir do 0.12.0.
  - **Linhas de base:** são regravadas só com o aval do mantenedor, na PARADA 4.
- **Rationale** (ADR-064, consequências; plano SDD, seções 4 e 5).
- **Alternatives**: medir só o agregado, que esconde as quedas de item (105 R23).

## R16 — A consulta livre do mantenedor

- **Decision**: o `scripts/grafo.py` tem três subcomandos.
  - `query <consulta> <args>` roda as mesmas funções pelo `DomainGraphService` e imprime a evidência com a fonte e a
    origem de cada aresta.
  - `export --arrows [--entidade X --saltos N]` grava o subgrafo no JSON do arrows.app, o mesmo formato de
    `corpus/Organização Escoteira.revisado.json`.
  - `build` monta o grafo e imprime o relatório: contagens por aresta e origem, e o que ficou de fora e por quê.
- **Rationale** (ADR-064, consequências; relatório, seção 6): ver o grafo real no editor em que o planejado foi
  desenhado substitui o que o Neo4j daria.
- **Alternatives**: Neo4j local, ou SQLite para exploração. São possíveis offline, mas fora desta fase.

## R17 — Facetas como `para_cada`

- **Decision**: no G2, a derivação escreve `para_cada(branches, sobre([ramo]))` quando publica `branches` (ADR-045).
  - **Na 103:** a busca por faceta continua (uma busca por ramo, intercaladas), agora repartindo as vagas que sobram
    das frentes do grafo.
  - **Marcas:** `facet_rank` e `facet_order` continuam nos metadados, para o `MetadataReranker` não mudar.
- **Rationale** (ADR-064, item 5; ADR-045): o ramo é uma entidade como as outras, e a busca por faceta é o que fez
  `fact_recall` ir a 0,81 em 2026-10, então ela não sai.
- **Alternatives**: trocar a busca por faceta só pelo grafo. Perderia os trechos que o grafo não liga a um ramo
  (`branches` vazio).
