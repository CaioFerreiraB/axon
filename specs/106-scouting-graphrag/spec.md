# Feature Specification: Grafo de domínio e consultas do scouting

**Feature Branch**: `106-scouting-graphrag` (git: `feat/106-grafo-de-dominio`)

**Created**: 2026-09-10 · **Reescrita**: 2026-11-10

**Status**: Draft (Fase 8)

**Input**: [ADR-064](../../docs/adr/ADR-064-grafo-de-dominio-e-consultas-no-scouting.md), que redefine esta spec: o
rascunho de 2026-09 ("um retriever alternativo que substitui a 103") foi rejeitado. Também o
[relatório do grafo](../../docs/avaliacao-grafo-rag-scouting-2026-11.md) (seções 5, 7, 8, 10 e 11) e o
[plano SDD da Fase 8](../../docs/plano-sdd-grafo-de-dominio-scouting-2026-11.md). A ontologia, que era a FR-004 com
`NEEDS CLARIFICATION`, foi resolvida pelo ADR-064 e pelo [design.md](design.md).

## Module Boundary *(mandatory)*

- **Módulo**: Grafo de domínio do scouting. É dono de quatro coisas: a ontologia, a construção offline do grafo a
  partir do acervo, o grafo em memória e as consultas com nome, com o esquema do plano e o executor.
- **Repositório / distribuição**: `axon-scouting` → `src/axon_scouting/rag/graph/` (`api.py`, `domain/`,
  `adapters/`) e `scripts/grafo.py`.
- **Consome (seams)**: só na construção offline, o que a 102 publica (*Índice do scouting*, *Árvore de unidades*,
  *Catálogo de documentos*, *Resumos das atas*) e os dados curados do acervo (`corpus/organizacao.yaml`,
  `corpus/taxonomia.yaml`, as fichas das atas). Na pergunta, nenhum seam: só o próprio artefato.
- **Expõe (seams)**: **Grafo de domínio**. Os consumidores são:
  - a 103, que executa o plano e recebe a evidência;
  - a 101, pela composição do `pack.py`: os apelidos das entidades, o reconhecimento e o esquema do plano;
  - o mantenedor, pela linha de comando.
- **Depende de infraestrutura (via portas)**: leitura do artefato. Só offline: os arquivos do acervo e um modelo de
  linguagem com a chave no ambiente (G5, conferido por código).
- **Não conhece**: o core, os flows, os validators e a busca híbrida. A 106 nunca busca trechos por texto: ela devolve
  a evidência, e a 103 escolhe e entrega os trechos.
- **Substituição**: o que precisa continuar verdadeiro é o seam (`QueryPlan`, `Evidence`, as consultas e o
  reconhecimento) e o formato do `graph.jsonl`. O armazenamento, a construção e a forma interna dos dicionários são
  livres.
- **Insumo técnico**: [design.md](design.md); [ADR-064](../../docs/adr/ADR-064-grafo-de-dominio-e-consultas-no-scouting.md),
  [ADR-063](../../docs/adr/ADR-063-grafo-das-normas-por-orgao-no-scouting.md),
  [ADR-062](../../docs/adr/ADR-062-busca-global-pelas-fichas-das-atas-no-scouting.md),
  [ADR-049](../../docs/adr/ADR-049-taxonomia-e-a-tipologia-do-acervo-no-scouting.md),
  [ADR-048](../../docs/adr/ADR-048-arvore-de-unidades-e-enumeracao-no-scouting.md),
  [ADR-047](../../docs/adr/ADR-047-lista-de-documentos-do-acervo-no-scouting.md),
  [ADR-045](../../docs/adr/ADR-045-filhotes-e-consulta-multifaceta-no-scouting.md),
  [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md).

## Clarifications

### Session 2026-11-10

- Q: O grafo diz quais documentos e unidades tratam da entidade; quem escolhe, dentro de cada documento, os até 3
  trechos que mais casam com a pergunta? → A: A 103. A 106 devolve a evidência com todos os trechos da unidade, já
  ordenada e cortada em documentos. A 103 escolhe até 3 por documento pelos termos da pergunta (o BM25 dela) e aplica
  o teto total. A 106 não lida com o texto da pergunta além do `reconhecer`.
- Q: Quantas das 20 vagas o grafo pode ocupar à frente da busca? → A: Por consulta, até 3 documentos e 3 trechos por
  documento (ADR-063). No total do grafo, 8 das 20 vagas, que em `para_cada` se repartem por entidade. São constantes,
  ajustadas depois de medidas no G2.
- Q: Onde ficam as entidades curadas novas? → A: Em dois arquivos. O `corpus/organizacao.yaml` fica com a
  organização: tipos de instituição e de órgão, instituições e órgãos reais com fonte, cargos e relações de
  governança. O `corpus/dominio.yaml`, novo, fica com o programa: ramos (que saem do `organizacao.yaml`), tipos de
  seção, áreas e conceitos, mais as arestas curadas `REGE`, `DE_RAMO` e `ATUA_EM` que partem deles.
- Q: Quando o modelo offline entra na ementa das resoluções (G5)? → A: Depois da regra. A regra lê a primeira frase
  ("Altera…", "Aprova…", "Dispõe sobre…"), e mede-se quantas ficam sem assunto. Só nessas roda o modelo, com o custo
  estimado e mostrado ao mantenedor antes e a fonte conferida contra a página.
- Q: Quem é dono do esquema do plano e da tabela de papéis? → A: A 106, os dois no `api.py`. A 101 importa só esse
  `api.py` para escrever o plano, e a 103 o lê de `retrieval_filters`. A 102 não muda, e o papel chega ao trecho como
  metadado pela 103.

## User Scenarios & Testing *(mandatory)*

Os atores são quem pergunta (escotista, dirigente, jovem), pelo Assistant `scouting`, e o mantenedor, que cura o
acervo e o grafo. Toda história é medida pelos quatro conjuntos da 105 (acervo, regressão, síntese e
programa-adultos), com o `fact_recall` antes e depois, por item (105 FR-026).

### User Story 1 - O grafo de domínio de pé, sem mudar nada para quem pergunta (Priority: P1) — G1

O grafo das normas por órgão (ADR-063) passa a morar no módulo novo, num formato que já tem lugar para todas as
entidades e arestas com fonte e origem. A pergunta sobre um órgão continua recebendo as mesmas seções, na mesma ordem.

**Why this priority**: é a base de todas as outras, e o único jeito de mudar a arquitetura sem confundir efeito com
causa é provar que a mudança de lugar não muda nada.

**Independent Test**: com o grafo novo, os quatro conjuntos dão números idênticos aos do `scouting` 0.11.1, item a
item, e os trechos à frente da busca são os mesmos para cada pergunta do acervo.

**Acceptance Scenarios**:

1. **Given** a pergunta "quem fiscaliza as contas da Diretoria Regional?", **When** ela é respondida, **Then** chegam,
   à frente, as mesmas seções do Estatuto e do Regulamento da Região SP que chegavam no 0.11.1, na mesma ordem.
2. **Given** o grafo construído, **When** os invariantes rodam, **Then** toda aresta tem fonte resolvível e origem, e
   nenhuma aponta para entidade inexistente.
3. **Given** uma pergunta que não nomeia nenhum órgão, **When** ela é respondida, **Then** o resultado é o da busca
   híbrida, como hoje.

---

### User Story 2 - Perguntas sobre cargos, ramos, seções, áreas e conceitos (Priority: P1) — G2

Quem pergunta "que requisitos um adulto precisa cumprir para atuar como escotista?", "um pioneiro pode atuar como
escotista?" ou "qual a idade mínima para ser chefe de seção em cada ramo?" recebe as unidades das normas e das
orientações que tratam dessas entidades, e não só as que a busca acha pelo vocabulário. Quando a pergunta nomeia duas
entidades, chegam as unidades que tratam das duas. Quando pede "cada ramo", cada ramo tem a sua vaga.

**Why this priority**: as falhas que restam no 0.11.1 são todas desta forma: 7 itens do acervo, 3 da regressão e os
grupos `cada_ramo`, `obrigatorio` e `lista_documentos` do programa-adultos.

**Independent Test**: os 10 itens que falham no acervo e na regressão e os grupos correspondentes do programa-adultos
sobem, e nenhum conjunto cai.

**Acceptance Scenarios**:

1. **Given** "que requisitos um adulto precisa cumprir para atuar como escotista?", **When** respondida, **Then** chegam
   as unidades que tratam do cargo de escotista no POR e as das políticas da área de gestão de adultos.
2. **Given** uma pergunta que nomeia um ramo e um cargo, **When** respondida, **Then** à frente vêm as unidades que
   tratam dos dois ao mesmo tempo.
3. **Given** "… em cada ramo", **When** respondida, **Then** cada ramo tem vagas reservadas, como a consulta por faceta
   de hoje (ADR-045), que passa a ser um caso desta.
4. **Given** uma pergunta sem entidade reconhecida, **When** respondida, **Then** o plano é vazio e a busca segue como
   hoje.

---

### User Story 3 - Perguntas situadas numa instituição (Priority: P2) — G3

Quem pergunta "no GE Professora Inah de Mello, quem aprova o balanço anual?" recebe o que vale para aquele grupo, de
cima para baixo: o Estatuto da UEB, o Regulamento da Região SP e o estatuto do grupo. As instituições e os órgãos
reais (a UEB, a Região SP, a DR-SP, o GE Inah…) existem no grafo, cada um com a fonte de onde saiu.

**Why this priority**: o caso existe (`inah-balanco-rejeitado`, 0,5 no 0.11.1), mas é menos frequente que a US2.

**Independent Test**: `inah-balanco-rejeitado` chega a 1, e nenhum conjunto cai.

**Acceptance Scenarios**:

1. **Given** uma pergunta que cita o GE Inah e um órgão do grupo, **When** respondida, **Then** chegam as unidades das
   normas que se aplicam ao GE e tratam daquele órgão, da norma de cima para a de baixo.
2. **Given** uma instituição citada que o acervo não registra, **When** respondida, **Then** a pergunta segue sem a
   cadeia de aplicabilidade, e nenhuma instituição é inventada.

---

### User Story 4 - O histórico pelas atas (Priority: P2) — G4

Quem pergunta pelo histórico de um cargo, de um órgão ou de um documento ("o que foi decidido sobre o Regulamento
Regional nas atas desde 2014?", "quais foram os mandatos das três últimas diretorias regionais?") recebe os eventos
datados das fichas das atas que tratam daquela entidade, e não só os de um órgão e de um ano.

**Why this priority**: a síntese já tem uma busca própria (ADR-062), e o ganho é nos 3 itens de 0,33 e no grupo
`historico` do programa-adultos.

**Independent Test**: a síntese não cai, e os 3 itens de 0,33 e o grupo `historico` sobem. A busca de resumos de hoje
vira uma fachada da linha do tempo, com o mesmo nome de tool e a mesma saída.

**Acceptance Scenarios**:

1. **Given** uma pergunta de histórico sobre um documento, **When** respondida, **Then** chegam os eventos das atas
   que tratam desse documento, por data, com a página da ata.
2. **Given** um item de ficha que nomeia uma pessoa, **When** o grafo é construído, **Then** a pessoa não vira
   entidade, e o nome fica só no texto do evento.

---

### User Story 5 - O que mudou numa norma e o que um órgão publicou (Priority: P2) — G5

Quem pergunta "que resolução mudou as regras para abrir uma seção do Ramo Filhotes?" ou "o que a Diretoria Regional
publicou sobre formação de adultos?" recebe as resoluções que alteram, revogam ou substituem a norma e os documentos do
órgão emissor sobre o assunto. O assunto de cada resolução vem da ementa, porque o título é só o número.

**Why this priority**: as resoluções são a maior fatia do acervo (273) e hoje nada diz do que tratam além do texto
corrido. O custo pode incluir o modelo offline.

**Independent Test**: os grupos `mudanca` e `publicacoes` do programa-adultos não caem, e os itens desses grupos que
estão abaixo de 1 sobem. Toda ligação entre documentos tem fonte.

**Acceptance Scenarios**:

1. **Given** uma resolução que "altera a Regra 178" de um POR em que essa regra mudou de número, **When** o grafo é
   construído, **Then** a ligação aponta para a regra pelo título, e não só pelo número.
2. **Given** uma resolução cuja ementa a regra não resolve, **When** o modelo offline propõe o assunto, **Then** a
   aresta só entra com a fonte conferida por código contra a página, e o custo foi estimado antes da rodada.

---

### User Story 6 - As listas como consultas do grafo (Priority: P3) — G6

A lista de documentos (ADR-047) e a lista de unidades com nome (ADR-048) passam a ser consultas do grafo. As tools
continuam com o mesmo nome e a mesma saída, e para quem pergunta nada muda.

**Why this priority**: não traz ganho por si, mas tira duas estruturas paralelas do retriever.

**Independent Test**: acervo e regressão sem cair, e as tools `list_documents` e `list_units` devolvem o mesmo
conteúdo para as perguntas de lista dos conjuntos.

**Acceptance Scenarios**:

1. **Given** "quais são as políticas nacionais?", **When** respondida, **Then** a mesma lista de fichas do acervo de
   hoje chega à geração.

---

### User Story 7 - O mantenedor consulta e confere o grafo (Priority: P1) — todos os incrementos

O mantenedor roda qualquer das consultas na linha de comando, com os mesmos parâmetros que a busca usa, e vê o grafo
construído no editor onde desenhou o planejado. Os invariantes do grafo rodam na suíte do pack.

**Why this priority**: sem ver o grafo real, a curadoria das entidades e dos apelidos é às cegas. Os invariantes são o
que garante a FR-002 e a FR-003.

**Independent Test**: `scripts/grafo.py query sobre cargo:escotista --papeis norma` lista as unidades com a fonte de
cada aresta, e o export abre no arrows.app.

**Acceptance Scenarios**:

1. **Given** o grafo construído, **When** o mantenedor consulta uma entidade, **Then** vê as unidades, o documento, o
   papel, a data e a fonte e a origem de cada aresta.
2. **Given** uma aresta sem fonte resolvível, **When** a suíte roda, **Then** o teste de invariantes falha nomeando a
   aresta.

---

### User Story 8 - Força normativa (Priority: P3, opcional) — G7

Cada unidade de norma leva a força dela (`obriga`, `proibe`, `faculta`, `recomenda`), e a resposta separa o que é
obrigatório do que é recomendado.

**Why this priority**: é opcional nesta fase (ADR-064). Só entra se o mantenedor pedir depois do G6.

**Independent Test**: nos itens `obrigatorio` do programa-adultos, a fidelidade pelo juiz numa rodada manual com modelo
real.

---

### Edge Cases

- **Sem `graph.jsonl`:** o grafo é vazio, e a busca segue só com o índice, como hoje.
- **`graph.jsonl` de outro build** (o chunking difere do manifesto do índice): a carga falha com erro explícito, que
  manda reconstruir o grafo. Nunca há grafo silenciosamente errado.
- **Plano inválido ou de versão desconhecida:** a busca segue sem as frentes do grafo, com aviso no log. A resposta
  continua correta, só sem o ganho.
- **Entidade reconhecida sem nenhuma unidade:** a consulta volta vazia, e as vagas ficam para a busca.
- **Duas entidades em que uma contém a outra pelo nome** ("conselho consultivo regional" × "conselho consultivo"):
  vale o nome mais longo (ADR-063).
- **Relação proposta por modelo que a página não confirma:** não entra. A fonte prevalece, e o caso fica no relatório
  da construção para curadoria.
- **Documento substituído:** a unidade da versão antiga leva a vigência da versão. A consulta respeita o período e a
  vigência do pedido, como os filtros de hoje.
- **Regra renumerada entre versões do POR:** a ligação casa pelo título da regra (105 R26).
- **Pergunta sobre uma pessoa:** nenhuma entidade é reconhecida, e a pergunta segue pela busca textual nas fichas e nos
  trechos.
- **Instituição sem fonte no acervo:** não é cadastrada (decisão 1 do mantenedor).

## Requirements *(mandatory)*

### Functional Requirements

**Ontologia e construção**

- **FR-001**: O grafo DEVE ter as entidades do ADR-064, com id `prefixo:slug`, nome, apelidos, fonte e origem:
  - tipos de instituição e de órgão;
  - instituições e órgãos reais, só com fonte;
  - cargos;
  - ramos;
  - tipos de seção;
  - áreas;
  - conceitos;
  - documentos.

  Tipo e instância DEVEM ser entidades distintas, ligadas por `INSTANCIA_DE`. Pessoas NÃO DEVEM ser entidades.
  As curadas ficam em dois arquivos, cada entrada com a fonte:
  - `corpus/organizacao.yaml`: tipos de instituição e de órgão, instituições e órgãos reais, cargos e relações de
    governança;
  - `corpus/dominio.yaml`: ramos, tipos de seção, áreas e conceitos, e as arestas `REGE`, `DE_RAMO` e `ATUA_EM`.
- **FR-002**: Toda aresta e toda entidade curada DEVEM ter `fonte` (trecho ou unidade do artefato, item de ficha com
  a página, entrada da taxonomia ou do catálogo curado) e `origem` (`curado`, `regra` ou `modelo_conferido`).
- **FR-003**: Uma aresta proposta por modelo DEVE ser feita offline e só entrar com a fonte conferida por código contra
  a página. Nenhuma aresta DEVE ser citada como fonte: a citação continua sendo o trecho (104).
- **FR-004** (resolvida pelo ADR-064): A ontologia é a do [design.md](design.md), seção 2. Ela é curada nos dois
  arquivos da FR-001 e derivada do acervo por regra, com o modelo só offline e conferido. A extração de esquema livre
  NÃO DEVE ser usada.
- **FR-005**: Todo tipo de documento da taxonomia DEVE ter um papel (`norma`, `orientacao`, `registro`, `comunicacao`),
  numa tabela do `api.py` da 106, por `taxonomy_id`. Um tipo sem papel DEVE falhar a construção. A 102 não muda.
- **FR-006**: A aresta central DEVE ser `SOBRE` (unidade → entidade), com o modo vindo do papel do documento:
  `disciplina`, `orienta`, `registra` ou `comunica`. Ela vale para todo tipo de documento.
- **FR-007**: As relações de governança (`ELEGE`, `FISCALIZA`…) DEVEM ficar no grafo com a fonte e NÃO DEVEM entrar na
  busca automática. Só a consulta `ligados` as devolve.
- **FR-008**: O grafo DEVE ser construído offline, sem rede (exceto o modelo do G5, explícito), por
  `scripts/grafo.py build`, e gravado em `graph.jsonl` (v2) ao lado do índice do pacote, fora do manifesto, com a
  versão do chunking do índice de que saiu.

**Consultas, plano e executor**

- **FR-009**: As consultas DEVEM ser sete funções puras com nome:
  - `reconhecer`;
  - `sobre`;
  - `aplicavel_a`;
  - `documentos`;
  - `itens`;
  - `linha_do_tempo`;
  - `ligados`.

  Elas usam as assinaturas do design.md e devolvem evidência (unidade ou evento, documento, papel, data e a fonte da
  aresta), e não trechos.
- **FR-010**: `reconhecer` DEVE ser a mesma função na derivação (101), no executor e na linha de comando, pelo nome
  mais longo e na ordem da menção.
- **FR-011**: O plano DEVE ser dados num esquema fechado (`QueryPlan`, no `api.py` da 106, com versão, forma
  `simples`, `para_cada` ou `intersecao` e as consultas com os parâmetros da assinatura), com `to_json`/`from_json`.
  A 101 importa só esse `api.py`. Um campo desconhecido DEVE
  ser recusado, nomeando o campo. NÃO DEVE haver linguagem de consulta em tempo de execução.
- **FR-012**: O executor DEVE aplicar as duas regras de composição:
  - `para_cada` reparte as vagas por entidade;
  - a interseção filtra a evidência da primeira consulta pelas seguintes.

  Ele DEVE ordenar por papel, nível (de cima para baixo), camada (direta, termo genérico, área) e data. A evidência
  DEVE levar todos os trechos de cada unidade. O corte em documentos é da 103 (R19, aprovado em 2026-11-11).
- **FR-012a**: A 103 DEVE ordenar os documentos de cada grupo por papel, nível e camada e, entre esses, pela relevância
  à pergunta, ficando com até 3. Dentro de cada documento, DEVE escolher até 3 trechos pela posição numa busca híbrida
  funda, com o BM25 como desempate (R19). Também DEVE limitar as
  frentes do grafo a 8 das 20 vagas, repartidas por entidade em `para_cada`, a partir do G2 (no G1, os tetos do
  ADR-063, FR-015). Os tetos são constantes, ajustáveis depois de medidos.
- **FR-013**: A busca híbrida DEVE rodar em toda pergunta. O grafo só ocupa as primeiras vagas, e sem plano, ou com
  plano vazio ou inválido, a entrega DEVE ser a da busca.
- **FR-014**: A evidência DEVE levar o papel do documento até o trecho entregue (metadado `role`), para o prompt da 101.

**Migração e incrementos**

- **FR-015**: O `NormGraph`, o `NormSection` e o `NormRelation`, a construção do ADR-063 e o `scripts/grafo.py` DEVEM
  passar para a 106. O G1 DEVE reproduzir a ordem e os tetos do `graph_rank` de hoje, com os quatro conjuntos idênticos
  ao 0.11.1.
- **FR-016**: As tools `search_summaries`, `list_documents` e `list_units` DEVEM continuar com o mesmo nome e a mesma
  saída, como fachadas de `linha_do_tempo` (G4), `documentos` e `itens` (G6).
- **FR-017**: Cada incremento que muda o artefato ou o comportamento DEVE:
  - ser uma versão menor do `scouting`, a partir do 0.12.0;
  - registrar o `fact_recall` antes e depois, por item, nos quatro conjuntos (105 FR-026).

  O que derruba um conjunto NÃO DEVE entrar.

**Mantenedor**

- **FR-018**: `scripts/grafo.py query <consulta> <args>` DEVE rodar as mesmas funções da busca e mostrar a fonte e a
  origem de cada aresta. `scripts/grafo.py export --arrows` DEVE gravar o grafo no formato do arrows.app.
- **FR-019**: A suíte do pack DEVE conferir os invariantes do artefato:
  - fonte resolvível;
  - nenhum id órfão;
  - toda aresta `modelo_conferido` conferida;
  - todo tipo da taxonomia com papel;
  - o chunking do grafo igual ao do índice.
- **FR-020**: No G5, o assunto das resoluções DEVE sair primeiro por regra, da primeira frase da ementa. O modelo
  offline DEVE rodar só nas que a regra não resolve, com o custo estimado e aprovado pelo mantenedor antes e a fonte
  conferida contra a página (FR-003).

### Key Entities

- **Entidade**: o que uma pergunta pode nomear (tipo de instituição ou de órgão, instituição, órgão, cargo, ramo, tipo
  de seção, área, conceito, documento), com id, nome, apelidos, fonte e origem.
- **Unidade**: um nó da árvore da 102 (artigo, regra, capítulo, item de pauta, especialidade…), com os trechos, os ramos
  e o documento.
- **Evento**: um item datado de uma ficha de ata (reunião, deliberação, eleição), com a página.
- **Aresta**: o tipo (`SOBRE` com o modo, `PARTE_DE`, `APLICA_SE_A`, `EMITIDO_POR`, `DE_AREA`, `REGE`, `ALTERA`…), as
  pontas, a fonte e a origem.
- **Papel**: `norma`, `orientacao`, `registro` ou `comunicacao`, por tipo de documento.
- **Plano** (`QueryPlan`): a forma e as consultas com os parâmetros. A 101 o escreve, e o executor o roda.
- **Evidência**: o que uma consulta devolve. A 103 a transforma em trechos.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: No G1, os quatro conjuntos dão o mesmo `fact_recall` do 0.11.1 em 100% dos itens.
- **SC-002**: Em todo build, 100% das arestas e das entidades curadas têm fonte resolvível e origem. Há 0 ids órfãos e
  0 arestas de modelo sem conferência.
- **SC-003**: Do G2 em diante, nenhum incremento entra com um conjunto abaixo da linha de base vigente (tolerância
  0,02 do agregado), e toda queda de item fica registrada com a causa.
- **SC-004**: Depois do G2, a média dos 10 itens que falham no acervo e na regressão do 0.11.1 sobe, e pelo menos
  metade deles chega a 1.
- **SC-005**: Depois do G3, `inah-balanco-rejeitado` (programa-adultos) chega a 1.
- **SC-006**: Depois do G4, a síntese não cai, e a média dos 3 itens de 0,33 sobe.
- **SC-007**: Nenhuma mudança no core, nos contratos nem na 104 em toda a fase.
- **SC-008**: Na pergunta, o grafo não pede serviço novo, e as consultas de uma pergunta levam menos de 50 ms na
  máquina do mantenedor.
- **SC-009**: O mantenedor roda as sete consultas na linha de comando e abre o grafo construído no arrows.app.

## Assumptions

- As decisões do mantenedor de 2026-11-10 valem:
  1. as instâncias com fonte;
  2. nenhuma pessoa como nó;
  3. o conjunto de avaliação primeiro, feito na 105 US7;
  4. a governança fora da busca.
- O planejador (um modelo que escolhe entidades e forma) vem depois, noutro ADR. Nesta fase, o plano é escrito pelo
  léxico da 101.
- As linhas de base do 0.11.1 são: acervo 0,9236, regressão 0,9768, síntese 0,8462 e programa-adultos 0,8409.
- A 102 continua dona da árvore de unidades, do catálogo e das fichas. A 106 os lê offline.
- O custo do modelo offline do G5 é estimado e mostrado ao mantenedor antes da rodada, como o das fichas (ADR-062).
