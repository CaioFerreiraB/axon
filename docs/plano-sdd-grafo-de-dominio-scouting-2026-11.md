# Plano SDD — o grafo de domínio e as consultas do scouting (Fase 8, spec 106)

*Escrito em 2026-11-10 para uma sessão nova conduzir o processo de spec-kit. Base: o relatório
[`avaliacao-grafo-rag-scouting-2026-11.md`](avaliacao-grafo-rag-scouting-2026-11.md), seções 5, 7, 8 e 11, aprovado
pelo mantenedor ("pode montar o plano").*

## 0. Como usar este plano

- Siga o `CLAUDE.md` da raiz (regras 1 a 7, fluxo por spec, graphify) e a constituição.
- As decisões da seção 2 **já foram tomadas**. Leve-as aos artefatos sem re-pesquisar e sem reabrir; uma divergência
  vira pergunta ao mantenedor, não mudança silenciosa.
- Há **paradas obrigatórias** (seção 4). Nelas, apresente o que foi feito e espere o aval antes de seguir.
- Nada de merge, tag, publicação de imagem ou deploy sem pedido explícito.
- Escreva em português, com os títulos de seção dos templates em inglês.

## 1. O que se quer

Hoje o retriever do scouting tem cinco mecanismos que trazem trechos à frente da busca, cada um feito para uma falha:

- `graph_rank` (ADR-063): as seções das normas sobre um órgão;
- `search_summaries` (ADR-062): as fichas das atas;
- `list_documents` (ADR-047): a lista de documentos;
- `list_units` (ADR-048): a lista de unidades com nome;
- `facet_rank` (ADR-045): uma busca por ramo.

Eles são cinco consultas a um grafo que não existe como um só. A Fase 8 junta tudo:

1. **Um grafo de domínio** em memória, no artefato. As entidades são instituições e órgãos (instâncias), cargos,
   ramos e tipos de seção, áreas e conceitos, além dos próprios documentos. As arestas têm fonte.
2. **Uma aresta central, `SOBRE`** (unidade → entidade), com um **modo** que vem do **papel** do tipo de documento:
   - norma: `disciplina`;
   - orientação: `orienta`;
   - registro: `registra`;
   - comunicação: `comunica`.

   Vale para estatuto, POR, resolução, política, manual, guia, ata, parecer, ofício e qualquer outro tipo da
   taxonomia.
3. **Sete consultas com nome**, puras e testadas, mais duas regras de composição no executor:
   - `reconhecer`, `sobre`, `aplicavel_a`, `documentos`, `itens`, `linha_do_tempo` e `ligados`;
   - `para_cada` e a interseção.
4. **Um plano por pergunta**: dados num esquema fechado, que a derivação (101) escreve e um executor fixo roda. Não há
   linguagem de consulta em tempo de execução.
5. **A busca híbrida continua sempre.** O grafo só ocupa as primeiras vagas, com teto.

As falhas de hoje que motivam o trabalho, nas linhas de base do `scouting` 0.11.1, são todas de programa educativo e
adultos:

| Conjunto | `fact_recall` | Itens abaixo de 1 |
|---|---|---|
| acervo | 0,9236 (48 itens) | `requisitos-do-escotista` 0,0; `reconhecimento-de-cada-ramo`, `blocos-escoteiro-e-senior`, `patrulhas-escoteiro-e-senior` e `passagem-senior-pioneiro` 0,5; `tamanho-das-equipes` e `patrulha-sem-adultos` 0,67 |
| regressão | 0,9768 (28 itens) | `marco-5-ramos` e `marco-ramos-nomeados` 0,8; `etapas-cada-ramo` 0,75 |
| síntese | 0,8462 (13 itens) | `mandatos-da-diretoria-regional`, `delegados-a-assembleia-nacional` e `alteracoes-do-regulamento-regional` 0,33 |

### Leitura obrigatória, nesta ordem

1. O relatório: seções 5 (grafo de domínio), 7 (plano), 8 (decisões), 10 e 11 (consultas). Use o `Read` com `offset`
   pelos títulos.
2. `docs/adr/ADR-061`, `ADR-062` e `ADR-063` (o padrão a seguir) e `docs/adr/README.md`.
3. `specs/README.md`: a tabela de seams, as linhas da 101 a 106 e o diagrama de dependências.
4. `specs/106-scouting-graphrag/spec.md` e `design.md`: o rascunho a reescrever.
5. Os FRs e o `research.md` que o ADR-063 deixou: 101 FR-036 e R43; 102 FR-036, R42 e R43; 103 FR-021, R21 e R22.
6. No submódulo `axon-scouting/`:
   - `corpus/organizacao.yaml`, `corpus/taxonomia.yaml` e `corpus/Organização Escoteira.json` (o desenho do
     mantenedor);
   - `src/axon_scouting/rag/index/api.py` (`NormGraph`, `MeetingSummaries`, `DocumentCatalog`, `DocumentOutline`);
   - `rag/index/adapters/graph.py`;
   - `rag/ingestion/domain/graph.py`;
   - `scripts/grafo.py`;
   - `rag/retrieval/retriever.py` (`_by_organ`), `summaries.py`, `catalog.py` e `units.py`;
   - `context/lexicon.py`;
   - `pack.py`.
7. `specs/105-scouting-evaluation/quickstart.md`, para rodar os conjuntos.

## 2. Decisões já tomadas (não reabrir)

**Do mantenedor, em 2026-11-10:**

1. **Instâncias.** Cadastrar todas as instâncias de que já houver informação, cada uma com a fonte de onde saiu. A
   que não tem fonte fica de fora.
2. **Pessoas: não.** Modelam-se cargos, e os nomes de pessoas ficam só no texto dos eventos das atas.
3. **Ordem.** O conjunto de avaliação de programa e adultos vem primeiro, escrito antes de qualquer código.
4. **Governança fora da busca.** As relações de governança (ELEGE, FISCALIZA…) continuam fora da busca automática até
   uma pergunta medida pedir. Elas podem ser consultadas por `ligados`.

**Da revisão (relatório, seções 3, 6 e 10):**

- **Armazenamento.** JSONL no artefato, carregado em dicionários. Nada de Neo4j, SQLite, LlamaIndex ou outro serviço
  na instalação.
- **Arestas.** Regra antes de modelo, e modelo só offline, com a fonte conferida por código contra a página (como as
  fichas do ADR-062). Nada de extração de esquema livre. Toda aresta tem `fonte` e `origem` (`curado`, `regra` ou
  `modelo_conferido`), e a 106 FR-002 e FR-003 continuam valendo.
- **Consultas.** Funções tipadas. O modelo nunca escreve consulta: o planejador (incremento futuro) só escolhe
  entidades de um enum.
- **Consulta livre só offline, para o mantenedor:** `scripts/grafo.py query` e o export para o arrows.app.
- **Core e contratos não mudam nesta fase.** O plano viaja opaco em `retrieval_filters`, como os filtros de hoje.
- **Fora desta fase:** o planejador (ver seção 8) e a força normativa, que pode entrar como incremento opcional (G7).

**Fatos do acervo que o desenho precisa respeitar:**

- São 642 documentos e 20 tipos. Os maiores são Resolução (273), Ata (256), Manual (38), Política (16) e Relatório
  (14). Os níveis regional e local são só da Região SP e do GE Prof. Inah de Mello.
- **O título das resoluções é só o número** ("Resolução CAN 08/1995"). O assunto tem que sair da ementa.
- O texto das resoluções já traz ligações entre documentos: 180 revogam algo, 61 alteram e 89 citam regras do POR.
  Elas dão arestas por regra.
- **Atas.** As fichas (680) e as linhas do tempo (516) já existem e foram conferidas por página. Falta ligar cada
  deliberação e cada eleição às entidades.
- A árvore de unidades já tem `secao`, `artigo`, `capitulo`, `item_de_pauta`, `especialidade`, `regra`, `bloco`,
  `reuniao`, `eixo`, `insignia`, `cargo` e `pergunta`, e o chunk já leva `branches`.

## 3. Arquitetura-alvo e fronteiras

A 106 deixa de ser "um retriever alternativo que substitui a 103". Ela passa a ser **o módulo do grafo de domínio e
das consultas**, consumido pela 103 (que continua sendo o retriever) e, pela composição do `pack.py`, pela 101. Isso
muda seams, e por isso pede o ADR-064.

| Spec | O que muda | Onde |
|---|---|---|
| **106** | Ontologia, construção offline do grafo, armazenamento em memória, as sete consultas, o esquema do plano e o executor. O seam novo é **Grafo de domínio** (`api.py`: entidades, arestas, `QueryPlan`, `Evidence`, a porta das consultas). Migram para cá o `NormGraph`/`ArtifactGraph`, o `rag/ingestion/domain/graph.py` e o `scripts/grafo.py`. | `axon_scouting/rag/graph/` (`api.py`, `domain/`, `adapters/`), `scripts/grafo.py` |
| **102** | Perde o `NormGraph` do seam *Índice do scouting*, que vai para a 106. Continua dona de unidades, catálogo e fichas, que a 106 lê offline pelos seams que já existem. | FR que remete à 106; o grafo continua fora do manifesto |
| **101** | A derivação publica `entities` (substitui `organs`) e `plan` em `retrieval_filters`. Os termos de reconhecimento continuam injetados pelo `pack.py`, como os `organ_terms` hoje. | `context/` |
| **103** | O retriever executa o plano pelo seam da 106. As frentes viram uma só, com teto por consulta. `search_summaries`, `list_documents` e `list_units` viram fachadas de `linha_do_tempo`, `documentos` e `itens`. | `rag/retrieval/` |
| **105** | US nova: o conjunto `eval/programa-adultos.yaml`, com linha de base e job na CI. | `eval/` |
| 104, core, contratos | não mudam | — |

Atualize o `specs/README.md`:
- a linha da 106, para "grafo de domínio e consultas", na Fase 8;
- a tabela de seams: um seam *Grafo de domínio* (106 → 101 e 103), e o `NormGraph` fora do *Índice do scouting*;
- o diagrama: `S103 --> S106` e `S101 --> S106`, mantendo `S106 --> S102`.

Atualize também o `docs/roadmap.md`, Fase 8.

## 4. A sequência do SDD

Com o spec-kit 1.0.6, as skills usam a spec ativa. Antes de cada passada, troque com
`SPECIFY_FEATURE_DIRECTORY=specs/NNN-nome` ou editando `.specify/feature.json`, que hoje aponta para a 013.

### Passo A — ADR-064 (proposto)

`docs/adr/ADR-064-grafo-de-dominio-e-consultas-no-scouting.md`, no formato do ADR-063 (Status, Specs afetadas, Origem,
Contexto, Decisão, Alternativas rejeitadas, Consequências). A decisão traz:

1. a 106 redefinida e o seam novo;
2. a migração do `NormGraph`;
3. a tabela de papéis;
4. a aresta `SOBRE` com modo;
5. as sete consultas e as duas regras;
6. o plano em `retrieval_filters`;
7. as fontes e origens das arestas;
8. os tetos de vagas.

Nas alternativas rejeitadas: LlamaIndex, Neo4j, texto-para-Cypher, extração livre, pessoas como nós, a 106 como
retriever substituto e manter os cinco mecanismos separados. Registre o ADR em `docs/adr/README.md` como **Proposto**.

> **PARADA 1.** Mostre o ADR ao mantenedor. Só com o aceite ele vira **Aceita** e o resto começa.

### Passo B — conjunto de avaliação primeiro (105)

1. `/speckit-specify` na 105: a US7, "Conjunto de programa, adultos e formas de pergunta" (P1), com FR e SC.
2. `/speckit-clarify` só se houver ambiguidade real.
3. `/speckit-plan` e `/speckit-tasks` limitados à US7, com o registro no `research.md`.
4. `/speckit-implement`: escrever `axon-scouting/eval/programa-adultos.yaml` pelo método do `acervo.yaml` (105 R22):
   - perguntas escritas **lendo os PDFs**, com os fatos conferidos no texto;
   - cerca de 30 itens, metade de **controle**;
   - grupos pelas formas da seção 11.6 do relatório:
     - o que é;
     - quem pode e requisitos;
     - duas entidades;
     - lista de documentos;
     - lista de itens;
     - cada ramo e comparação;
     - situada no GE Inah;
     - normativa de órgão;
     - histórico de cargo, de órgão e de documento;
     - o que mudou numa norma (resoluções);
     - o que um órgão publicou;
     - obrigatório × recomendado.
5. Gravar a **linha de base com o 0.11.1, antes de qualquer código**, e acrescentar o job no `eval.yml`.

> **PARADA 2.** Mostre ao mantenedor as perguntas, os fatos e a linha de base.

### Passo C — a 106 de verdade

1. Reescreva o `specs/106-scouting-graphrag/design.md`, o insumo técnico, com:
   - o ADR-064;
   - a ontologia (tipos, ids no formato `tipo:slug` — `cargo:escotista`, `ramo:pioneiro`, `orgao:dr_sp`,
     `inst:ge_inah`, `doc:<document_id>`, `area:…`, `conceito:…`);
   - a tabela de papéis;
   - a tabela "de onde vem cada aresta, tipo por tipo" (relatório, 11.7);
   - as assinaturas das consultas;
   - o esquema do plano;
   - a seção "Portas e adapters" (regra 7 do `CLAUDE.md`).
2. `SPECIFY_FEATURE_DIRECTORY=specs/106-scouting-graphrag` e `/speckit-specify`, para reescrever a spec. O status sai
   de "Draft (futuro)", o *Module Boundary* é o novo, e a FR-004 (`NEEDS CLARIFICATION` da ontologia) é resolvida pelo
   ADR-064. As user stories seguem os incrementos G1 a G6 da seção 5.
3. `/speckit-clarify`: as perguntas abertas da seção 6, no máximo 5, cada uma com a recomendação.
4. `/speckit-plan` (`plan.md`, `research.md` com Decision / Rationale (ADR) / Alternatives, `data-model.md`,
   `contracts/` com o seam e o esquema do plano, `quickstart.md`).
5. As passadas de encaixe na 101, na 102 e na 103, como o ADR-063 fez: um FR novo em cada spec, que cita o ADR-064, e
   um registro no `research.md` de cada uma. Nada de editar o interior de outra spec além disso.
6. `/speckit-tasks` na 106, com as tarefas da 101, da 102 e da 103 marcadas pela spec de origem, e `/speckit-analyze`.

> **PARADA 3.** Mostre ao mantenedor a spec, o plano, as tarefas e o relatório do analyze.

### Passo D — implementação, um incremento por vez

`/speckit-implement` incremento a incremento (seção 5). Ao fim de cada um, rode os quatro conjuntos (acervo,
regressão, síntese e programa-adultos) e mostre o `fact_recall` antes e depois, por item. Um incremento que derruba
um conjunto não entra: investigue ou reporte.

> **PARADA 4**, a cada incremento: os números ao mantenedor antes do seguinte.

## 5. Incrementos de implementação

| Inc. | Entrega | Medida e critério |
|---|---|---|
| **G1** | **A 106 de pé, sem mudar o comportamento.** Migra o `NormGraph`/`ArtifactGraph`, a construção e o `scripts/grafo.py` para `rag/graph/`; o `graph.jsonl` v2 (entidades, arestas com `fonte` e `origem`); `reconhecer`; `sobre` limitado a órgão, que reproduz o `graph_rank`. | Os quatro conjuntos **idênticos** ao 0.11.1. |
| **G2** | **Entidades e `sobre` para norma e orientação.** Cargos, ramos, tipos de seção, áreas e conceitos no catálogo curado, com apelidos e fonte. `SOBRE` por regra: títulos de seção, capítulo e regra, `branches`, unidades `especialidade`/`etapa`/`bloco`, área pela categoria. A derivação publica `entities` e `plan`. O executor faz `para_cada` e a interseção, e o `facet_rank` vira um caso. | As 7 falhas do acervo e as 3 da regressão; os grupos correspondentes do programa-adultos; nenhum conjunto cai. |
| **G3** | **`aplicavel_a`.** As instâncias (decisão 1) e o `PARTE_DE`; `APLICA_SE_A` e `EMITIDO_POR` pela pasta e pelo nível da taxonomia; a instituição na derivação. | Perguntas situadas (GE Inah). |
| **G4** | **`linha_do_tempo` e as atas.** `SOBRE` e eventos (reunião, deliberação, eleição) a partir das fichas, por `reconhecer` em cada item; `search_summaries` vira fachada. | A síntese não cai, e os 3 itens de 0,33 são o alvo; histórico no programa-adultos. |
| **G5** | **Resoluções e `ligados`.** A ementa (regra na primeira frase; o modelo offline, conferido, só no que sobrar, com o custo estimado antes); `ALTERA`, `REVOGA` e `SUBSTITUI` por regra; `ligados`. | "O que mudou numa norma" e "o que um órgão publicou" no programa-adultos. |
| **G6** | **`documentos` e `itens`** absorvem `list_documents` e `list_units`, que viram fachadas. | Acervo e regressão sem cair. |
| G7 (opcional) | Força normativa da unidade (relatório, 5.5). | Os itens "obrigatório × recomendado", pela fidelidade do juiz numa rodada manual. |

Em todos os incrementos:
- **Consulta livre para o mantenedor.** `scripts/grafo.py query <consulta> <args>` roda as mesmas funções, e
  `scripts/grafo.py export --arrows` grava o grafo para o arrows.app.
- **Invariantes do artefato**, num teste como o `test_artifact_quality.py`: toda aresta tem fonte resolvível, nenhum
  id de entidade é órfão, e as arestas `modelo_conferido` foram conferidas.
- **Versão.** Um `scouting` menor por incremento que muda o artefato ou o comportamento, a partir do 0.12.0.

## 6. Perguntas abertas para o `/speckit-clarify` (com recomendação)

1. **Quem é dono do esquema do plano?** Recomendado: a 106, no `api.py` (`QueryPlan` com `to_json`/`from_json`). A
   101 importa só esse `api.py` (regra 7), e a 103 o lê de `retrieval_filters`.
2. **Onde mora a tabela de papéis?** Recomendado: na 106, por `semantic_type` da taxonomia, sem mudar a 102. O papel
   chega ao trecho como metadado pela 103, para o prompt da 101 usar.
3. **Tetos de vagas.** Recomendado: manter os do ADR-063 por consulta (3 documentos × 3 trechos), com um teto total do
   grafo de 8 das 20 vagas, ajustável depois de medido.
4. **O catálogo curado.** Ampliar o `corpus/organizacao.yaml` (que hoje tem `cargos`, `ramos` e `relacoes`) ou criar
   um `corpus/dominio.yaml` para áreas e conceitos? Recomendado: um arquivo só, `organizacao.yaml`, com seções novas.
5. **O modelo offline na ementa das resoluções (G5).** Só depois de medir quantas a regra cobre? Recomendado: sim, a
   regra primeiro e o modelo só no resto, com o custo estimado antes, como as fichas (`gpt-4.1-mini` pelo OpenRouter,
   chave só no ambiente).

## 7. Repositórios, branches e verificação

- **SDD no `axon`** (specs, ADR, `specs/README.md`, roadmap): branch `feat/106-grafo-de-dominio`, PR só quando pedido.
- **Código e dados no `axon-scouting`** (submódulo): branch de mesmo nome. Aqui só muda o ponteiro do submódulo.
- **`graphify`.** Rode `graphify query` antes de explorar código e `graphify update .` depois de mudar código no
  `axon`. O submódulo fica fora do grafo.
- **`uv`.** Nesta máquina, sempre com `XDG_DATA_HOME=$HOME/.local/share`.
- **Verificação do pack**, dentro de `axon-scouting/`:
  - `uv run pytest && uv run mypy && uv run ruff check && uv run lint-imports`;
  - a integração com `uv run --python 3.14 --group platform pytest tests/integration`;
  - o import-linter com um contrato para `rag/graph/`: o `domain/` não importa adapters, e os outros módulos só importam
    o `api.py`.
- **Conjuntos:** os comandos do `specs/105-scouting-evaluation/quickstart.md`, com `eval/acervo.yaml`,
  `eval/regression.yaml`, `eval/sintese.yaml` e `eval/programa-adultos.yaml` e as linhas de base respectivas. A CI
  roda os mesmos em `.github/workflows/eval.yml`.
- **Reconstrução do grafo:** `scripts/grafo.py build`. O `graph.jsonl` é commitado no pacote, como hoje.

## 8. Depois desta fase: o planejador (outro ADR, outra sessão)

Não faz parte deste plano. Fica registrado para não ser feito por engano no meio dele (relatório, seção 9.3, revista).

- O planejador mora no `scouting` (101), dentro do `prepare_context`: prompt, esquema com o enum das entidades do
  grafo e a junção com o léxico.
- O core só empresta uma chamada de modelo pelo Model Router: papel opcional `planner`, uma chamada, saída por
  esquema, falha → `None`. Isso exige um ADR do core e passadas na 001, 005, 006, 003 e 011, além de tags novas.
- Vem em dois degraus (só reescritas; depois entidades e forma) e só depois de G2 e G3 medidos. O plano de consultas
  da seção 3 é o lugar onde a saída dele entra.
