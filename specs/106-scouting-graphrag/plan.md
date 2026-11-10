# Implementation Plan: Grafo de domínio e consultas do scouting (Fase 8)

**Branch**: `feat/106-grafo-de-dominio` (no `axon` e no `axon-scouting`) | **Date**: 2026-11-10 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/106-scouting-graphrag/spec.md`

**Architecture inputs** *(PROJECT OVERRIDE — axon)*: lidos o [design.md](design.md), com a seção "Portas e adapters";
os ADRs da Module Boundary (064, 063, 062, 049, 048, 047, 045) e o ADR-012; a clarificação de 2026-11-10; e, no
`axon-scouting` 0.11.1, o `NormGraph` e o `ArtifactGraph`, a construção do ADR-063 (`rag/ingestion/domain/graph.py`,
`scripts/grafo.py`), o `ScoutingRetriever` (`_by_organ`, `_by_facet`), as tools de resumo, de lista e de unidades, os
filtros (`KNOWN`), a derivação (`organs`), o `pack.py`, o `organizacao.yaml`, a taxonomia, as fichas das atas e os
contratos do import-linter. As decisões foram levadas ao [research.md](research.md) sem re-pesquisa. Nenhum ADR novo:
a clarificação trocou o "arquivo só" do catálogo curado por dois arquivos, o que o próprio ADR-064 deixa ao clarify.

## Summary

A Fase 8 junta num **grafo de domínio** os cinco mecanismos que hoje trazem trechos à frente da busca do scouting:
- `graph_rank` (ADR-063);
- `search_summaries` (062);
- `list_documents` (047);
- `list_units` (048);
- `facet_rank` (045).

O grafo fica em memória, lido do `graph.jsonl` v2 do artefato. Tem entidades curadas e derivadas, a aresta central
`SOBRE` com o modo pelo papel do documento, sete consultas puras com nome, um plano em esquema fechado que a derivação
(101) escreve e um executor que a 103 chama. A busca híbrida roda sempre, e o grafo ocupa até 8 das 20 vagas.

A entrega é em seis incrementos medidos (G1 a G6, mais o G7 opcional), cada um com o `fact_recall` antes e depois, por
item, nos quatro conjuntos. O G1 só muda de lugar o que existe e tem de dar números idênticos aos do 0.11.1.

## Technical Context

**Language/Version**: Python 3.12+ no pacote (o piso dos contratos); a avaliação e o grupo `platform`, em 3.14.

**Primary Dependencies**:
- `axon-ai-contracts` da tag do core em uso, sem mudança;
- `pyyaml`, que já está, só na construção offline e nos adapters;
- o SDK `openai` para o OpenRouter, só no `adapters/summarizer.py` do G5, offline e opcional.

O grafo em si não traz dependência nova: são dicionários em memória.

**Storage**: `src/axon_scouting/data/index/graph.jsonl` (v2), ao lado do índice, fora do manifesto, commitado no
pacote. Os dados curados ficam em `corpus/organizacao.yaml` e `corpus/dominio.yaml` (novo).

**Testing**: pytest em três camadas:
- **unitários** das consultas, do executor, das regras de aresta e do plano, sobre grafos sintéticos;
- **conformidade** do seam *Grafo de domínio* contra o `MemoryGraphStore` e o `ArtifactGraphStore` real;
- **invariantes do artefato** (`tests/rag/graph/test_graph_artifact.py`), mais o teste de identidade do G1 (os
  `chunk_id` à frente, antes e depois).

Os quatro conjuntos da 105 rodam pelo harness e são comparados com o `scripts/eval_diff.py`.

**Target Platform**: o pack `scouting` na instalação (`axon-deploy`, `axon-cfblabs`), sem serviço novo, e a máquina do
mantenedor para a construção offline.

**Project Type**: um módulo do pack de domínio (biblioteca), com um script offline.

**Performance Goals**: as consultas de uma pergunta em menos de 50 ms (SC-008), e a carga do grafo uma vez por
processo, com poucos MB.

**Constraints**:
- core e contratos sem mudança;
- consultas puras, sem I/O nem relógio;
- nenhuma linguagem de consulta em tempo de pergunta;
- modelo só offline e conferido;
- governança fora da busca;
- nenhuma pessoa como nó;
- o G1 com números idênticos.

**Scale/Scope**: centenas de entidades e algumas dezenas de milhares de arestas `SOBRE`, sobre 642 documentos e cerca
de 15,7 mil trechos. Um módulo novo (`rag/graph/`) e mudanças em `context/` (101), `rag/retrieval/` (103),
`rag/index/` (102: sai o grafo), `pack.py`, `scripts/grafo.py`, `pyproject.toml` (import-linter) e `corpus/`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

- **I (núcleo agnóstico):** PASS. Tudo fica no pack, e o core não muda.
- **II (seams):** PASS com ADR. O seam novo *Grafo de domínio* e a saída do `NormGraph` do *Índice do scouting* estão
  no ADR-064. Os consumidores (101, 102, 103) ganham um FR cada nas passadas de encaixe.
- **V (determinismo antes de LLM):** PASS. As consultas, o executor e o plano são código fixo e testado. O modelo só
  aparece offline (G5) e conferido.
- **VI (conteúdo externo não confiável):** PASS. O modelo nunca escreve consulta, e a saída offline dele só vira aresta
  com a fonte conferida.
- **VII (falha explícita):** PASS. Um grafo de outro build é recusado na carga. O plano inválido cai na busca, que
  continua correta, com aviso, e isso está registrado no R8.
- **IX (proveniência e vigência):** PASS. Toda aresta tem fonte e origem, a citação continua sendo o trecho, e a
  vigência vem da versão do documento.
- **X (medir antes de calibrar):** PASS. A linha de base do programa-adultos foi gravada antes (105 US7), os tetos são
  os do ADR-063 até medir, e todo incremento mostra o antes e depois.
- **XII (simplicidade):** PASS. Dicionários em memória, sem serviço novo.
- **XIII (portas e adapters):** PASS. Ver abaixo.

**Module boundary gate** *(PROJECT OVERRIDE — principle II, mandatory)*:

- [x] O código fica em `rag/graph/` e `scripts/grafo.py`. As mudanças fora dele (101, 102, 103 e `pack.py`) vêm das
  passadas de encaixe com FR próprio, e as tarefas levam a spec de origem.
- [x] Seams consumidos, com dono: na construção offline, os da 102 (*Índice*, *Árvore de unidades*, *Catálogo*,
  *Resumos das atas*), pelo artefato. Na pergunta, nenhum.
- [x] O seam exposto (*Grafo de domínio*) tem uma suíte de conformidade planejada (`tests/rag/graph/contract/`).
- [x] Mudança de seam com o ADR-064 e as specs consumidoras listadas (101, 102, 103).
- [x] O import-linter cobre o código novo: as camadas da 106, `context` limitado a `rag.graph.api` e a infraestrutura
  só em `adapters/` (R14).

**Ports & adapters gate** *(PROJECT OVERRIDE — principle XIII, ADR-012, mandatory)*:

- [x] `api.py`, `domain/`, `ports.py`, `service.py` e `adapters/`.
- [x] `api.py`, `domain/`, `ports.py` e `service.py` não importam infraestrutura (`yaml`, SDK de modelo), que fica em
  `adapters/`.
- [x] Os outros módulos importam só o `api.py`, e o `api.py` não importa o resto do módulo.
- [x] O I/O (leitura do `graph.jsonl`, do artefato e do `corpus/`, e o modelo offline) passa por porta. O `domain/` não
  faz I/O.
- [x] Só há porta para I/O: `GraphStore`, `GraphSources` e `ResolutionSummarizer`. As regras e as consultas não são
  portas.
- [x] Cada porta secundária tem um adapter em memória e conformidade contra o real. O `ResolutionSummarizer` tem o
  simulado na suíte, e o real só numa integração com chave.
- [x] Só o `pack.py` e o `scripts/grafo.py` instanciam o serviço e os adapters.

## Project Structure

### Documentation (this feature)

```text
specs/106-scouting-graphrag/
├── spec.md              # reescrita em 2026-11-10 (ADR-064)
├── design.md            # insumo técnico pré-aprovado
├── plan.md              # este arquivo
├── research.md          # R1–R17 (Decision / Rationale (ADR) / Alternatives)
├── data-model.md        # entidades, nós, arestas, papel, plano, evidência, registros do graph.jsonl
├── quickstart.md        # construir, conferir, consultar e medir
├── contracts/
│   ├── domain-graph-seam.md      # o seam: DomainGraphSource, Evidence, Frentes, reconhecer, ROLES
│   ├── query-plan.schema.json    # o esquema do plano (retrieval_filters.plan)
│   ├── graph-jsonl-v2.md         # o formato do artefato
│   └── grafo-cli.md              # scripts/grafo.py build | query | export
├── checklists/requirements.md
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
axon-scouting/
├── corpus/
│   ├── organizacao.yaml          # + instituicoes, orgaos (G3); cargos ampliados (G2); sem ramos (vão ao dominio.yaml)
│   └── dominio.yaml              # novo (G2): ramos, secoes, areas, conceitos; REGE, DE_RAMO, ATUA_EM
├── scripts/grafo.py              # build | query | export --arrows (106)
├── src/axon_scouting/
│   ├── rag/graph/                # 106 (novo)
│   │   ├── api.py                # seam Grafo de domínio
│   │   ├── ports.py              # GraphStore, GraphSources, ResolutionSummarizer
│   │   ├── service.py            # DomainGraphService
│   │   ├── domain/
│   │   │   ├── model.py          # DomainGraph
│   │   │   ├── roles.py          # tabela de papéis (reexportada por api.py como ROLES)
│   │   │   ├── build/            # regras de aresta por tipo (vem de rag/ingestion/domain/graph.py)
│   │   │   ├── queries.py        # as sete consultas
│   │   │   └── executor.py       # plano, composição, documentos por consulta
│   │   └── adapters/
│   │       ├── artifact.py       # ArtifactGraphStore + escritor do v2 (vem de rag/index/adapters/graph.py)
│   │       ├── memory.py         # MemoryGraphStore
│   │       ├── sources.py        # ArtifactSources (offline)
│   │       └── summarizer.py     # G5
│   ├── rag/index/api.py          # 102: sai NormGraph, NormSection, NormRelation
│   ├── rag/retrieval/            # 103: executa o plano; KNOWN com entities e plan; fachadas (G4, G6)
│   ├── context/                  # 101: entities e plan na derivação; léxico com os apelidos das entidades
│   ├── data/index/graph.jsonl    # v2
│   └── pack.py                   # compõe DomainGraphService(ArtifactGraphStore)
├── tests/rag/graph/
│   ├── contract/                 # seam e GraphStore (memória e artefato)
│   ├── unit/                     # consultas, executor, plano, regras de aresta, papéis
│   └── test_graph_artifact.py    # invariantes do artefato (FR-019)
└── pyproject.toml                # import-linter (R14); versão por incremento (0.12.0…)
```

**Structure Decision**: o módulo segue o layout do ADR-012 em `rag/graph/`, como o `rag/index/` e o
`rag/ingestion/`. As mudanças na 101, na 102 e na 103 são as das passadas de encaixe, com um FR em cada spec e tarefas
marcadas pela spec de origem.

## Seam Notes for Consumers

| Consumidor | O que precisa saber |
|---|---|
| 103 (`rag/retrieval/`) | Recebe `DomainGraphSource` no `ScoutingRetriever` (no lugar do `NormGraph`); lê `plan` de `retrieval_filters` com `QueryPlan.from_json` (inválido → só a busca e aviso no log); `run(plan)` devolve `Frentes`; ela escolhe até 3 trechos por documento e limita o grafo a 8 das 20 vagas; marca `graph_rank`, `graph_query` e `role`. `KNOWN` ganha `entities` e `plan` e perde `organs` (G1). As tools de resumo, lista e unidades viram fachadas (G4, G6). |
| 101 (`context/`) | O léxico recebe `entity_terms` (sucessor de `organ_terms`) pelo `pack.py`; a derivação publica `entities` e `plan` (`QueryPlan.to_json()`), importando só `rag.graph.api`. |
| 102 (`rag/index/`) | Perde `NormGraph`/`NormSection`/`NormRelation` e o adapter do grafo; o artefato continua sendo dela, e o `graph.jsonl` continua ao lado, escrito pela 106. |
| `pack.py` | Compõe `DomainGraphService(ArtifactGraphStore(<dir do artefato>))` uma vez por configuração, como o `_graph` de hoje. |
| Instalação (`axon-deploy`, `axon-cfblabs`) | Nada novo: a cópia do índice já leva o `graph.jsonl`. |

## Constitution Check — pós-design (Phase 1)

Reavaliado com [data-model.md](data-model.md), [contracts/](contracts/) e [quickstart.md](quickstart.md): **PASS**.

- **II:** o seam está descrito em `contracts/domain-graph-seam.md`, e o formato do artefato em `graph-jsonl-v2.md`. O
  plano tem um JSON Schema fechado (`additionalProperties: false`).
- **V e VI:** o plano não carrega texto livre além de ids de entidade, papéis, tipos, ramos e período. O executor
  recusa nome de consulta e parâmetro desconhecidos.
- **X:** o quickstart mede os quatro conjuntos, por item, em todo incremento.
- **XIII:** a única porta com rede (`ResolutionSummarizer`) é offline e tem simulado.

## Complexity Tracking

| Violação ou desvio | Por quê | Alternativa mais simples rejeitada porque |
|---|---|---|
| Plano inválido não é erro (diferente dos filtros, que falham explícitos, 103 FR-007) | o plano só otimiza: sem ele, a busca continua correta, e um erro derrubaria a resposta por um defeito de otimização | recusar a requisição: troca uma resposta boa por um erro para quem pergunta (R8) |
| `context` (101) passa a importar `rag.graph.api` | o esquema do plano e o `reconhecer` são da 106 (clarify de 2026-11-10) | duplicar o esquema na 101 como dicionário solto: duas definições do mesmo contrato, que divergiriam (R14) |
