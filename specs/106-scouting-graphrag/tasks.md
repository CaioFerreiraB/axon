# Tasks: Grafo de domínio e consultas do scouting (Fase 8)

**Input**: [spec.md](spec.md), [plan.md](plan.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/](contracts/) e [quickstart.md](quickstart.md).

**Escopo**: as US1 a US7 (G1 a G6 e a consulta do mantenedor). A US8 (G7) é opcional, na última fase. As tarefas de
outras specs levam a spec de origem, como **[101]**, **[102]** e **[103]**, e são as passadas de encaixe do ADR-064
(101 FR-037, 102 FR-037, 103 FR-022). Nada de editar outra spec além disso.

**Caminhos**: relativos a `axon-scouting/`, salvo quando indicado. Código e dados ficam no submódulo, na branch
`feat/106-grafo-de-dominio`. No `axon` mudam só o SDD e o ponteiro do submódulo.

**Testes**: são pedidos pela spec, nas FR-019 e SC-001 e na conformidade do seam. Cada fase os traz antes do código
que eles cobrem.

**Fim de cada incremento**: os quatro conjuntos, o `eval_diff.py` por item (quickstart, seção 4) e a **PARADA 4**. O
incremento seguinte só começa com o aval do mantenedor.

## Format: `[ID] [P?] [Story] [spec de origem?] Description`

---

## Phase 1: Setup

- [X] T001 Criar o esqueleto de `src/axon_scouting/rag/graph/`, com `__init__.py`, `api.py`, `ports.py`, `service.py`,
  `domain/__init__.py`, `domain/build/__init__.py` e `adapters/__init__.py`, e de `tests/rag/graph/`, com
  `contract/`, `unit/` e `__init__.py`.
- [X] T002 Acrescentar ao `pyproject.toml` os contratos do import-linter do R14:
  - o contrato "só o pack.py compõe" com `context | prompts | validators` acima de `rag`;
  - um `forbidden` que limita `axon_scouting.context` a `axon_scouting.rag.graph.api`, proibindo `rag.index`,
    `rag.retrieval`, `rag.ingestion`, `rag.graph.domain`, `rag.graph.service`, `rag.graph.ports` e
    `rag.graph.adapters`;
  - as camadas `rag.graph.adapters` > `rag.graph.service` > `rag.graph.ports | rag.graph.domain` > `rag.graph.api`;
  - o `api.py` não importa o resto da 106;
  - `yaml` e `openai` proibidos fora de `rag.graph.adapters`;
  - `rag.retrieval` vê só `rag.graph.api`.

  Rodar `uv run lint-imports`.

---

## Phase 2: Foundational (bloqueia todas as US)

**Objetivo**: os tipos do seam, o plano, os papéis e o grafo em memória, sem mudar nada do comportamento.

- [X] T003 [P] Testes unitários do plano em `tests/rag/graph/unit/test_plan.py`:
  - `to_json`/`from_json` de ida e volta;
  - `version` ≠ 1 → `PlanInvalid("version")`;
  - `q` fora de `sobre|aplicavel_a|documentos|itens|linha_do_tempo|ligados`;
  - chave de `args` desconhecida → `PlanInvalid("consultas[i].args.<chave>")`;
  - `consultas` com "até 4" e `para_cada` com "até 6 ids de entidade", só com a forma `para_cada`;
  - padrão de id de entidade `^(\$cada|(tipo_inst|tipo_orgao|inst|orgao|cargo|ramo|secao|area|conceito|doc):[a-z0-9_.-]+)$`.

  A suíte valida, também, cada plano dos testes contra `../specs/106-scouting-graphrag/contracts/query-plan.schema.json`,
  copiado para `tests/rag/graph/query-plan.schema.json`.
- [X] T004 [P] Testes unitários de `reconhecer` em `tests/rag/graph/unit/test_reconhecer.py`:
  - termo mais longo vence ("conselho consultivo regional" → regional);
  - sem sobreposição;
  - ordem da primeira menção;
  - texto sem termo → `()`.
- [X] T005 [P] Testes unitários dos papéis em `tests/rag/graph/unit/test_roles.py`:
  - os 18 `taxonomy_id` da R3 com o papel certo;
  - `MODE_OF`;
  - a função que confere a taxonomia acusa um tipo sem papel.
- [X] T006 Implementar `src/axon_scouting/rag/graph/api.py` pelo `contracts/domain-graph-seam.md`:
  - `Role`, `Mode`, `Origin`, `QueryName`;
  - `ROLES` (a tabela da R3), `MODE_OF`, `Aliases`, `reconhecer`;
  - `PlanInvalid`, `QueryStep`, `QueryPlan` (com `to_json`/`from_json`);
  - `EdgeRef`, `EventRef`, `Evidence`, `FrontGroup`, `Frentes`, `GraphUnavailable`;
  - o `DomainGraphSource` (Protocol).

  O `api.py` não importa nada da 106 além do que define, nem a 101: o `reconhecer` recebe o texto e os termos já
  normalizados por quem o chama (a 101, com `context/text.py`).
- [X] T007 Implementar `src/axon_scouting/rag/graph/domain/model.py`:
  - `DomainGraph`, com dicionários imutáveis de entidades, versões, unidades, arestas por tipo e ponta, eventos e
    termos;
  - `from_records(records)`, que valida as pontas e os campos obrigatórios do `contracts/graph-jsonl-v2.md`, e um
    registro inválido levanta `ValueError` nomeando a linha.
- [X] T008 Implementar `src/axon_scouting/rag/graph/ports.py`:
  - `GraphStore` (`records() -> Iterable[GraphRecord]`, `GraphUnavailable` no chunking divergente);
  - `GraphSources`, offline: trechos com o `path`, versões do catálogo, fichas, `organizacao.yaml`, `dominio.yaml` e
    taxonomia como mapeamentos;
  - `ResolutionSummarizer`, offline.
- [X] T009 [P] Implementar `src/axon_scouting/rag/graph/adapters/memory.py` (`MemoryGraphStore`) e
  `src/axon_scouting/rag/graph/adapters/artifact.py` (`ArtifactGraphStore`):
  - lê `graph.jsonl` v2;
  - arquivo ausente → nenhum registro;
  - `meta.chunking` diferente do `manifest.json` do mesmo diretório → `GraphUnavailable` com a mensagem "rode
    `scripts/grafo.py build`";
  - `kind` desconhecido é ignorado;
  - inclui o `write_graph_v2(path, records)`, com a ordem e a ordenação do contrato.
- [X] T010 Suíte de conformidade de `GraphStore` em `tests/rag/graph/contract/test_graph_store.py`, contra
  `MemoryGraphStore` e `ArtifactGraphStore` (num diretório temporário com um `manifest.json`):
  - ida e volta dos registros;
  - arquivo ausente;
  - chunking divergente.
- [X] T010a Implementar `MemorySources` em `src/axon_scouting/rag/graph/adapters/memory.py` (o `GraphSources` sobre
  mapeamentos em memória) e a suíte de conformidade em `tests/rag/graph/contract/test_graph_sources.py`, contra o
  `MemorySources` e, depois do T017, contra o `ArtifactSources`, num diretório temporário com um artefato mínimo e YAML
  mínimos.
  Constituição XIII: toda porta secundária tem adapter em memória e conformidade contra o real.

**Checkpoint**: tipos do seam, plano e grafo em memória testados, e nada ligado ao pack.

---

## Phase 3: User Story 1 — o grafo de pé, sem mudar nada (Priority: P1) — G1 🎯 MVP

**Objetivo**: migrar o grafo do ADR-063 para a 106, gravar o v2 e trocar `organs` por `entities` e `plan`, com os
quatro conjuntos idênticos ao 0.11.1.

**Teste independente**:
- os quatro conjuntos com "Nenhum item mudou" (quickstart, seção 4);
- o `test_g1_identity.py` passando.

### Testes da US1

- [X] T011 [P] [US1] Antes de qualquer mudança, gravar a referência do G1 em
  `tests/rag/graph/fixtures/g1_reference.json`: para cada pergunta de `eval/acervo.yaml`, `eval/regression.yaml`,
  `eval/sintese.yaml` e `eval/programa-adultos.yaml`, os `chunk_id` com `graph_rank`, em ordem, que o `ScoutingRetriever`
  do 0.11.1 devolve com os filtros da derivação. O gerador rodou fora do repositório e não foi commitado, porque
  importava o `NormGraph` (R18).
- [X] T012 [P] [US1] Teste `tests/rag/graph/test_g1_identity.py`: com o grafo v2 e o caminho novo (plano), os
  `chunk_id` à frente de cada pergunta são iguais aos de `g1_reference.json`, na mesma ordem.
- [X] T013 [P] [US1] Testes unitários de `sobre`, restrito a órgão, em `tests/rag/graph/unit/test_sobre_orgao.py`, sobre
  um grafo sintético:
  - a ordem do 0.11.1: entidade na ordem da menção, depois nível, `doc_key` e `unit_id`;
  - um `sobre` com dois órgãos dá **um** grupo, com até 3 documentos no total, como o `_by_organ`;
  - a instância inclui o tipo;
  - a governança nunca vem;
  - entidade inexistente → vazio.
- [X] T014 [P] [US1] Conformidade do seam em `tests/rag/graph/contract/test_domain_graph_seam.py`, contra o
  `DomainGraphService` com `MemoryGraphStore`, e com o `ArtifactGraphStore` sobre o `graph.jsonl` do pacote. São as
  garantias 1 a 8 do `contracts/domain-graph-seam.md`.

### Implementação da US1

- [X] T015 [US1] [102] Mover `rag/ingestion/domain/graph.py` para `src/axon_scouting/rag/graph/domain/build/organs.py`
  (`Organ`, `ChunkPlace`, `Section`, `Relation`, `organs_from_mapping`, `cargo_terms`, `relations_from_mapping`,
  `sections`), sem mudar a regra, com os testes (`tests/rag/ingestion/…graph…` → `tests/rag/graph/unit/`).
- [X] T016 [US1] Implementar `src/axon_scouting/rag/graph/domain/build/records.py`, que converte o resultado da
  construção do ADR-063 nos registros v2:
  - `entity` (`tipo_orgao:`/`tipo_inst:` com `terms` iguais aos `organ_terms` de hoje);
  - `version` (com `role` por `ROLES`);
  - `unit` (as seções);
  - `edge` (`SOBRE`, modo `disciplina`, `origin: regra`, `source` = `unit_id`; e as 22 de governança com
    `origin: curado` e `source` = o `chunk_id` conferido);
  - `meta` (o chunking do manifesto e os sha256 dos YAML).
- [X] T017 [US1] Implementar `src/axon_scouting/rag/graph/adapters/sources.py` (`ArtifactSources`): o `places()` de
  hoje (trechos com `path`), o catálogo de `documents.jsonl`, os YAML do `corpus/` e o manifesto. O `yaml` é lido só
  aqui.
- [X] T018 [US1] Reescrever `scripts/grafo.py build` para compor `ArtifactSources` → `domain/build` →
  `write_graph_v2` e imprimir o relatório, pelo `contracts/grafo-cli.md`. Saídas: 0, 1 (invariante) e 2 (YAML
  inválido).
- [X] T019 [US1] Implementar `src/axon_scouting/rag/graph/domain/queries.py` com `sobre`, ainda só com arestas
  `SOBRE` para `tipo_orgao:`/`tipo_inst:`, `papeis`, a ordem da garantia 2 do contrato (a posição da entidade, papel,
  nível por `SCOPE_ORDER`, `doc_key`, `unit_id`) e o corte em 3 documentos. Também `ligados`, só para as relações de governança, que o `NormGraph.relations` dava.
- [X] T020 [US1] Implementar `src/axon_scouting/rag/graph/domain/executor.py` (`executar(g, plano) -> Frentes`) para a
  forma `simples`. As formas `para_cada` e `intersecao` levantam `NotImplementedError` até o G2.
- [X] T021 [US1] Implementar `src/axon_scouting/rag/graph/service.py` (`DomainGraphService(store: GraphStore)`), com
  a carga única e com trava (como o `ArtifactGraph`), `aliases()`, `run(plan)` e `query(name, **args)`.
- [X] T022 [US1] Rodar `uv run python scripts/grafo.py build` e commitar o `src/axon_scouting/data/index/graph.jsonl`
  v2. Conferir no relatório as 28 seções e as 22 relações do 0.11.1.
- [X] T023 [US1] [102] Remover `NormGraph`, `NormSection` e `NormRelation` de `src/axon_scouting/rag/index/api.py` e
  apagar `src/axon_scouting/rag/index/adapters/graph.py`. Atualizar os imports e os testes que os usavam.
- [X] T024 [US1] [103] Em `src/axon_scouting/rag/retrieval/domain/filters.py`:
  - `KNOWN` ganha `entities` e `plan` e perde `organs`;
  - `entities(raw)` devolve a tupla de ids;
  - `plan(raw)` devolve um `QueryPlan | None`, com `PlanInvalid` → `None` mais um `logging.warning` que nomeia o campo.

  Com testes em `tests/rag/retrieval/`.
- [X] T025 [US1] [103] Em `src/axon_scouting/rag/retrieval/retriever.py`:
  - o `ScoutingRetriever` recebe `graph: DomainGraphSource | None`;
  - `_by_organ` vira `_by_plan`, que chama `run(plan)`, pega os trechos no `ChunkIndex.get`, escolhe até 3 por
    documento pelo `_best` e pelo BM25 de hoje, **sem teto total no G1** (3 × 3 = 9, como hoje);
  - marca `graph_rank`, `graph_query` e `role`;
  - sem plano, nada à frente.

  O resto da busca não muda. Constantes novas em `domain/ordering.py`: `GRAPH_QUERY` e `ROLE`.
- [X] T026 [US1] [101] Em `src/axon_scouting/context/lexicon.py`, `organ_terms` vira `entity_terms` (ids `tipo_orgao:` e
  `tipo_inst:`). Em `src/axon_scouting/context/derivation.py`:
  - `_organs` vira `_entities`, com o `reconhecer` de `rag.graph.api` e as mesmas exclusões da 101 R43;
  - a derivação publica `entities` e `plan` (`QueryPlan(consultas=(QueryStep(q="sobre", args={"entidades": [...],
    "papeis": ["norma"]}),))`, vazio sem entidades) no lugar de `organs`.

  Atualizar os testes de `tests/context/`.
- [X] T027 [US1] Em `src/axon_scouting/pack.py`:
  - `_graph` compõe `DomainGraphService(ArtifactGraphStore(_artifact_dir(config)))`;
  - `_organ_terms` vira `_entity_terms` (`aliases()`);
  - o `ScoutingRetriever` recebe o serviço.

  Atualizar `tests/test_pack.py`.
- [X] T028a [US1] Teste de tempo em `tests/rag/graph/test_graph_timing.py` (SC-008): com o `graph.jsonl` do pacote já
  carregado, o `run(plan)` das perguntas de `eval/acervo.yaml` leva menos de 50 ms cada, com a mediana impressa.
  Repetir no T043.
- [X] T028 [US1] Rodar T012 a T014 e T028a, `uv run pytest && uv run mypy && uv run ruff check && uv run lint-imports` e a
  integração `uv run --python 3.14 --group platform pytest tests/integration`.
- [X] T029 [US1] Medir os quatro conjuntos (quickstart da 106, seção 4) e o `eval_diff.py` por item. Esperado:
  "Nenhum item mudou" nos quatro. Registrar no research da 106 (R18, a medida do G1). O `scouting` vai a 0.12.0 em
  `pyproject.toml`.
- [X] T030 [US1] Corrigir o cabeçalho do `corpus/organizacao.yaml` (o "RASCUNHO… não é lido por nenhum código" é de
  antes do ADR-063).

**Checkpoint G1 — PARADA 4**: os números ao mantenedor, com os quatro conjuntos idênticos.

---

## Phase 4: User Story 7 — o mantenedor consulta e confere (Priority: P1), entregue com o G1

**Objetivo**: consulta livre, export e invariantes. Os comandos crescem a cada incremento.

**Teste independente**: `scripts/grafo.py query sobre tipo_orgao:diretoria_regional --papeis norma` lista as seções
com a fonte, e o export abre no arrows.app.

- [X] T031 [P] [US7] Teste dos invariantes em `tests/rag/graph/test_graph_artifact.py`, sobre o `graph.jsonl`
  commitado:
  - toda `source` resolve (o `chunk_id` ou o `unit_id` existe no `chunks.jsonl`, a pasta existe na taxonomia, a página
    da ficha existe);
  - nenhuma aresta aponta para id inexistente;
  - todo `modelo_conferido` tem `checked: true`;
  - todo `taxonomy_id` de `documents.jsonl` está em `ROLES`;
  - o `meta.chunking` é igual ao do `manifest.json`;
  - nenhuma entidade de pessoa.
- [X] T032 [US7] `scripts/grafo.py query <consulta> <args>` e `scripts/grafo.py plan "<pergunta>"` pelo
  `contracts/grafo-cli.md`, com uma linha por evidência (documento, unidade e título, papel, data, aresta, fonte e
  origem) e `--json`. O `plan` compõe a derivação da 101 com os termos do grafo, como o `pack.py`.
- [X] T033 [US7] `scripts/grafo.py export --arrows [--entidade X --saltos N] [--sem-unidades]`, no formato de
  `corpus/Organização Escoteira.revisado.json`, com o teste de forma em `tests/rag/graph/unit/test_export_arrows.py`.

**Checkpoint**: entra na mesma PARADA 4 do G1.

---

## Phase 5: User Story 2 — cargos, ramos, seções, áreas e conceitos (Priority: P1) — G2

**Objetivo**: entidades curadas, `SOBRE` de norma e orientação, a área, `para_cada` e a interseção. O plano é escrito
pela forma da pergunta.

**Teste independente**:
- os 10 itens que falham no acervo e na regressão sobem, com SC-004 (média sobe, metade a 1);
- `cada_ramo`, `duas_entidades`, `requisitos` e `obrigatorio` do programa-adultos não caem;
- nenhum conjunto cai.

- [X] T034 [US2] Criar `corpus/dominio.yaml` (`version: 1`), com os `ramos` saindo do `organizacao.yaml`, mais:
  - `secoes` (ninhada, alcateia, tropa escoteira, tropa sênior/guia, clã, com `DE_RAMO`);
  - `areas` (programa educativo, gestão de adultos, espaços seguros, gestão institucional, relações institucionais,
    rede de jovens líderes…, cada uma com as categorias da taxonomia que ela agrupa);
  - `conceitos` (especialidade, insígnia, etapa, bloco, progressão, promessa, Insígnia de Madeira, modalidades do Ar e
    do Mar, reconhecimento…, com apelidos e o tipo de unidade da árvore quando houver);
  - `rege` (área → cargo, ramo, seção).

  Toda entrada tem `fonte` (`chunk_id`) e `citacao`.
- [X] T035 [US2] Ampliar os `cargos` do `corpus/organizacao.yaml` com os de programa e adultos:
  - escotista, chefe de seção (Chefe de Alcateia, Chefe de Tropa Escoteira, Chefe de Tropa Sênior/Guia, Mestre
    Pioneiro);
  - assistente;
  - APF;
  - diretor de métodos educativos;
  - diretor de programa educativo e gestão de adultos;
  - comissário distrital;
  - monitor.

  Cada um com apelidos, `atua_em` e fonte (POR, Perfis de Cargos, Política Nacional de Adultos).
- [X] T036 [P] [US2] Testes das regras de aresta em `tests/rag/graph/unit/test_build_sobre.py`, sobre um acervo
  sintético:
  - título → entidade pelo nome mais longo;
  - `branches` → `ramo:`;
  - `unit_kind` → `conceito:`;
  - categoria → `DE_AREA`;
  - modo pelo papel;
  - instituição nunca pelo título do documento.
- [X] T037 [US2] Implementar `src/axon_scouting/rag/graph/domain/build/sobre.py` com as regras do R6, itens 1 a 5,
  para todos os tipos de documento, e `build/domain.py`, que lê `dominio.yaml` e os cargos e gera `entity`, `REGE`,
  `DE_RAMO` e `ATUA_EM`. O `ArtifactSources` passa a ler o `dominio.yaml`.
- [X] T038 [P] [US2] Testes de `sobre` completo e do executor em `tests/rag/graph/unit/test_sobre.py` e
  `test_executor.py`:
  - `modo=todas` (a mesma unidade ou a seção mãe);
  - o salto `REGE`+`DE_AREA` depois das diretas;
  - `papeis` e `tipos`;
  - `para_cada` com `$cada` e grupos por entidade;
  - interseção com `documentos`;
  - a ordem por papel, nível e data.
- [X] T039 [US2] Completar `sobre` em `domain/queries.py` e as formas `para_cada` e `intersecao` em
  `domain/executor.py`.
- [X] T040 [US2] [103] No `retriever.py`:
  - o teto total entra aqui, medido: `GRAPH_TOTAL: Final = 8`, repartido por grupo de `para_cada` (`ceil(8/n)`);
  - a busca por faceta (ADR-045) continua e reparte as vagas que sobram, com `facet_rank` e `facet_order` como hoje
    (R17).

  Testes em `tests/rag/retrieval/`.
- [X] T041 [US2] [101] Na derivação (`src/axon_scouting/context/derivation.py`), a tabela "forma → plano":
  - entidades sem forma especial → `sobre(entidades, papeis=[norma, orientacao])`;
  - duas entidades de tipos diferentes → `modo=todas`;
  - `branches` → `para_cada(branches, sobre([$cada, …]))`;
  - síntese, lista e enumeração mantêm os mecanismos de hoje, com o plano vazio para elas até o G4 e o G6.

  O léxico recebe todos os `entity_terms`. Testes em `tests/context/`.
- [ ] T042 [US2] [101] O prompt (`src/axon_scouting/prompts/`) usa o metadado `role` do trecho para falar pela
  natureza ("o Estatuto determina" × "o manual orienta"), só se a medida com modelo real mostrar ganho. A medida é a
  fidelidade pelo juiz (`eval/assistants-openrouter.yaml`, juiz `gpt-4.1-mini`) no programa-adultos, antes e depois
  da mudança do prompt. Sem ganho, fica registrado e adiado. **Adiada no G2** (R19): pede a rodada com modelo real.
- [X] T043 [US2] `scripts/grafo.py build`, os invariantes (T031), o teste de tempo (T028a), a suíte completa e a medida dos quatro conjuntos com
  o `eval_diff.py`. Registrar no research da 106 (R19, a medida do G2), com os 10 itens alvo, item a item. O `scouting`
  vai a 0.13.0.

**Checkpoint G2 — PARADA 4.**

---

## Phase 6: User Story 3 — perguntas situadas numa instituição (Priority: P2) — G3

**Teste independente**: `inah-balanco-rejeitado` chega a 1 (SC-005), e nenhum conjunto cai.

- [X] T044 [US3] Acrescentar ao `corpus/organizacao.yaml`:
  - `instituicoes`: OMME, Região Interamericana, UEB, Região SP, GE Prof. Inah de Mello, e os distritos e grupos que o
    acervo nomeia com fonte;
  - `orgaos`: as instâncias com documento no acervo, como DR-SP, AR-SP, CCR-SP, CAN, DEN, a Comissão Fiscal Regional
    SP, a Comissão Regional Pioneira SP e o Conselho Regional Jovem SP.

  Cada uma com `instancia_de`, `parte_de` e fonte. A que não tem fonte fica de fora (decisão 1).
- [X] T045 [P] [US3] Testes em `tests/rag/graph/unit/test_aplicavel_a.py` e `test_build_taxonomy.py`:
  - `PARTE_DE` até 5 níveis, de cima para baixo;
  - `APLICA_SE_A` e `EMITIDO_POR` pela pasta, pelo nível e pela subpasta da taxonomia;
  - a interseção `sobre` ∩ `aplicavel_a`.
- [X] T046 [US3] Implementar `build/taxonomy.py` (`APLICA_SE_A`, `EMITIDO_POR`) e `aplicavel_a` em
  `domain/queries.py`.
- [X] T047 [US3] [101] A derivação reconhece a instituição citada (`inst:`) e escreve a interseção
  `sobre(...) ∩ aplicavel_a(inst)`. Testes em `tests/context/`.
- [X] T048 [US3] Build, invariantes, suíte e medida dos quatro conjuntos. Registrar no research (R20). O `scouting` vai
  a 0.14.0.

**Checkpoint G3 — PARADA 4.**

---

## Phase 7: User Story 4 — o histórico pelas atas (Priority: P2) — G4

**Teste independente**: a síntese não cai, a média dos 3 itens de 0,33 sobe (SC-006), e `historico` sobe.

- [X] T049 [P] [US4] Testes em `tests/rag/graph/unit/test_eventos.py` e `test_linha_do_tempo.py`:
  - um item de ficha vira `event` com a página;
  - `GERA` e `DE` pelo `reconhecer` no tema e na decisão, mais o órgão da ata;
  - pessoa nunca vira entidade;
  - a ordem por data;
  - os filtros de `eventos` e `periodo`.
- [X] T050 [US4] Implementar `build/minutes.py`, que lê `corpus/resumos/atas/*.yaml` pelo `ArtifactSources` (só os itens
  `conferido: true`), e `linha_do_tempo` em `domain/queries.py`.
- [X] T051 [US4] [103] `src/axon_scouting/rag/retrieval/summaries.py`: o `SummariesRetriever` vira uma fachada de
  `linha_do_tempo`. O nome da tool, a descrição e a forma da saída (`summary_rank`) não mudam. Os `SummaryEntry` da 102
  continuam como texto do resumo. Testes que comparam a saída para as perguntas da síntese.
- [X] T052 [US4] [101] A derivação escreve `linha_do_tempo(alvo, eventos, periodo)` quando publica `synthesis` com uma
  entidade reconhecida. Testes em `tests/context/`.
- [X] T053 [US4] Build, invariantes, suíte e medida dos quatro conjuntos. Registrar no research (R21). O `scouting` vai
  a 0.15.0.

**Checkpoint G4 — PARADA 4.**

---

## Phase 8: User Story 5 — o que mudou numa norma e o que um órgão publicou (Priority: P2) — G5

**Teste independente**: `mudanca` e `publicacoes` não caem, e os itens abaixo de 1 sobem. Toda ligação tem fonte.

- [X] T054 [P] [US5] Testes em `tests/rag/graph/unit/test_build_resolutions.py`:
  - ementa por regra (primeira frase "Altera…/Aprova…/Dispõe sobre…/Revoga…");
  - `ALTERA` e `REVOGA` com o alvo pelo título da regra, inclusive renumerada (CAN 11/2021 "Regra 178" → a regra 183
    do POR 2025 pelo título "Distintivos de Idiomas");
  - `SUBSTITUI` pela linhagem;
  - `CITA` ("Regra 054", "art. 27");
  - os apelidos de `doc:` pelo número ("Resolução CAN 15/2025").
- [X] T055 [US5] Implementar `build/resolutions.py` (regra) e `ligados` completo em `domain/queries.py`. Medir e
  imprimir no relatório do build quantas resoluções ficaram sem assunto.
- [X] T056 [US5] Estimar o custo do modelo nas resoluções sem assunto (tokens × preço do `gpt-4.1-mini` no OpenRouter)
  e **mostrar ao mantenedor antes de rodar** (FR-020).
- [X] T057 [US5] Só com o aval do T056 (feito de outro modo, por decisão do mantenedor: as propostas são da própria sessão,
  em `corpus/resumos/resolucoes/assuntos.yaml`, conferidas pelo build; sem `ResolutionSummarizer` — R22):
  - `src/axon_scouting/rag/graph/adapters/summarizer.py` (`ResolutionSummarizer` pelo OpenRouter, chave só em
    `AXON_OPENROUTER_API_KEY`) e o simulado em `tests/`;
  - a conferência da fonte por código contra a página, como `rag/ingestion/domain/minutes.py` faz;
  - `scripts/grafo.py build --summarize-resolutions` grava as propostas conferidas em `corpus/resumos/resolucoes/`;
  - a suíte de conformidade do `ResolutionSummarizer` em `tests/rag/graph/contract/test_summarizer.py`, que roda
    sempre contra o simulado e contra o real só com `AXON_OPENROUTER_API_KEY` no ambiente (pulada sem ela, como a
    integração paga da 006).
- [X] T058 [US5] [101] A derivação escreve `ligados(doc, [ALTERA, REVOGA])` e `documentos(emissor=…) ∩ sobre(area)`
  pelas formas "o que mudou / que resolução alterou" e "o que o órgão publicou". Testes em `tests/context/`.
- [X] T059 [US5] Build, invariantes, suíte e medida dos quatro conjuntos. Registrar no research (R22), com o custo
  real. O `scouting` vai a 0.16.0.

**Checkpoint G5 — PARADA 4.**

---

## Phase 9: User Story 6 — as listas como consultas (Priority: P3) — G6

**Teste independente**: acervo e regressão sem cair, e as tools de lista com a mesma saída para as perguntas de lista
dos conjuntos.

- [ ] T060 [P] [US6] Testes de identidade da saída de `list_documents` e `list_units` antes e depois, para as perguntas
  dos grupos `lista`, `lista_documentos` e `lista_itens`, em `tests/rag/retrieval/test_list_facades.py`, com a
  referência gravada antes da mudança.
- [ ] T061 [US6] Implementar `documentos` e `itens` em `domain/queries.py` (as versões e as unidades do grafo, com a
  ordem de hoje). O build passa a pôr no grafo as unidades dos tipos com nome do ADR-048 (especialidade, insígnia,
  etapa, cargo…), com `CONTEM`, para o `itens` listar sem a árvore da 102.
- [ ] T062 [US6] [103] `src/axon_scouting/rag/retrieval/catalog.py` e `units.py` viram fachadas de `documentos` e
  `itens`, com o mesmo nome de tool, a mesma descrição e as mesmas fichas (`catalog_rank`, `structure_rank`).
- [ ] T063 [US6] Build, invariantes, suíte e medida dos quatro conjuntos. Registrar no research (R23). O `scouting` vai
  a 0.17.0.

**Checkpoint G6 — PARADA 4.**

---

## Phase 10: User Story 8 — força normativa (Priority: P3) — G7, **OPCIONAL**

Só com pedido explícito do mantenedor depois do G6.

- [ ] T064 [US8] A força da unidade (`obriga`, `proibe`, `faculta`, `recomenda`) pelos modais, por regra, e o modelo
  offline conferido nos ambíguos, como atributo da `unit`. O metadado vai ao trecho pela 103, e o prompt da 101 separa
  "obrigatório" e "recomendado". A medida é a fidelidade pelo juiz nos itens `obrigatorio`, numa rodada manual com
  modelo real (`eval/assistants-openrouter.yaml`).

---

## Phase 11: Polish & Cross-Cutting

- [ ] T065 Atualizar o README do pack (`README.md`) com o grafo: `scripts/grafo.py build|query|plan|export` e quando
  reconstruir.
- [ ] T066 No `axon`, para cada incremento:
  - o FR e o research de encaixe já existem;
  - atualizar a linha da 106 em `specs/README.md`, a Fase 8 de `docs/roadmap.md` e o parágrafo da Fase 8 do
    `CLAUDE.md`;
  - rodar `graphify update .`;
  - o ponteiro do submódulo.
- [ ] T067 Conferir a instalação. A cópia do índice no `axon-deploy/template` e no `axon-cfblabs` já leva o
  `graph.jsonl`, então confirmar que nada mais é preciso. Nada de imagem nem de deploy sem pedido.

---

## Dependencies & Execution Order

- **Setup → Foundational → G1 (US1 + US7) → G2 → G3 → G4 → G5 → G6 → (G7).** Os incrementos são sequenciais por
  decisão do plano: cada um parte da linha de base que o anterior deixou, e a PARADA 4 fica entre eles.
- **Dentro de um incremento:** testes → construção (`build/`) → consultas e executor → encaixes [103] e [101] →
  `build` do artefato → medida.
- **Encaixes:**
  - [102] T015 e T023 só no G1;
  - [103] T024, T025, T040, T051 e T062;
  - [101] T026, T041, T042, T047, T052 e T058.

## Parallel Opportunities

- Foundational: T003, T004 e T005 juntos, e T009 ao lado de T007.
- G1: T011, T013 e T014 juntos, antes da implementação. T011 tem de rodar **antes** de qualquer mudança no retriever.
- G2: T036 e T038 juntos, e T034 e T035 (dados) ao lado dos testes.
- Nos demais, os testes [P] de cada fase juntos.

## Parallel Example: User Story 1

```text
T011 (referência do G1, no código do 0.11.1)  ┐
T013 (unitários de sobre/órgão)               ├─ juntos
T014 (conformidade do seam)                   ┘
→ T015…T027 em ordem → T028 → T029 (medida) → PARADA 4
```

## Implementation Strategy

- **MVP = G1 (US1 + US7):** a arquitetura nova, sem mudança de comportamento, provada pelos números idênticos e pela
  identidade dos `chunk_id`.
- **Entrega incremental:** G2 é o maior ganho esperado (as falhas de programa e adultos). G3 a G6 seguem, cada um
  medido.
- **Regra de entrada:** um incremento que derruba um conjunto não entra. Investiga-se ou se reporta (SC-003).
- **Versões:** 0.12.0 (G1), 0.13.0 (G2), 0.14.0 (G3), 0.15.0 (G4), 0.16.0 (G5), 0.17.0 (G6). Nada de tag, imagem ou
  deploy sem pedido.
