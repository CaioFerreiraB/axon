# Research — 105 Scouting Evaluation, Fase 6 (infraestrutura e conjunto semente)

> Insumos: [design.md](design.md) (pré-aprovado), ADR-013, ADR-027 (métricas de domínio pelo contrato de pack), o
> harness da 009 ([contracts/eval-harness.md](../009-core-observability-evaluation/contracts/eval-harness.md)), as três
> clarificações de 2026-10-13 e o código do `ai-scouting` (derivação da 101, índice da 102, validators da 104, CI).
> Escopo decidido: infraestrutura + conjunto semente provisório; US3–US5 (calibração, embedding, modelo local) esperam a
> curadoria, que fica para depois do desenvolvimento.

## R1 — Escopo da passada

**Decision**: US1 (formato e validação, sobre a semente), US2 (linha de base da semente) e a infraestrutura que as
US3–US5 vão usar: métricas de domínio (FR-003), conjunto semente provisório (FR-001), validação contra o catálogo do
corpus, configuração de avaliação versionada no repositório e o job de CI (FR-005). Nenhuma calibração (US3), escolha de
embedding (US4) ou de modelo local (US5).

**Rationale**: clarificação 1 — sem o conjunto curado, calibrar seria ajustar números a perguntas que ninguém fez
(princípio X); a infraestrutura não depende do conteúdo final.

**Alternatives**: as da clarificação 1 (só infraestrutura; adiar tudo).

## R2 — Métricas de domínio pelo hook `eval_metrics` (ADR-027)

**Decision**: módulo `ai_scouting/eval/metrics.py`, puro, com três `EvalMetric` declaradas pelo `pack.py`:

| Nome | Definição | `better` | Determinística |
|---|---|---|---|
| `context_accuracy` | fração dos campos de `item.extra["context"]` que casam com a derivação da 101 refeita para a pergunta e o dia de referência do item (R3); item sem `context` → `None` | higher | sim |
| `current_document_rate` | fração dos trechos **entregues** com status `vigente`, só em itens não históricos (sem `include_superseded` nem `previous_version` esperados); item histórico ou sem entregue → `None` | higher | sim |
| `validity_notice_rate` | item cujas citações finais incluem status diferente de `vigente`: 1 se a resposta tem a flag `non_current_source` (104), senão 0; item sem citação não vigente → `None` | higher | não (depende da geração) |

Citação resolvível e inventada já são métricas do core (009 R17) e não se repetem aqui. Nomes no relatório:
`scouting:<nome>`. "Não vigente" segue o `validity_notice` da 104: todo status diferente de `vigente`, inclusive vazio
(vigência não confirmada).

No corpus atual (uma versão por linhagem) a taxa de documento vigente vale 1 por construção e o aviso não se aplica a
nenhum item; as duas ganham sentido quando o catálogo tiver versões anteriores. Entram agora porque custam pouco e a
linha de base já as registra.

**Rationale**: design.md, tabela "Métricas de domínio"; a terceira linha do design ("aviso de não vigente quando
devido") entra porque custa uma regra sobre flags que o 104 já emite.

**Alternatives**: métrica de vigência sobre os candidatos (mede o filtro de recuperação, mas o que importa é o que chegou
ao modelo).

## R3 — Acerto da derivação de contexto (clarificação 3)

**Decision**: `extra.context` no item, com os campos opcionais `branch` (texto ou `null`), `topics` (lista), `document_types`
(lista), `effective_from` e `effective_until` (datas ISO), `include_superseded` e `previous_version` (booleanos). A métrica
refaz `derive_context(item.question, reference_day(item.reference_time))` — a mesma função pura que o
`prepare_context` usa — e compara campo a campo: listas como conjuntos, datas pelo intervalo de vigência, os demais por
igualdade. Valor = casados / declarados.

**Rationale**: a derivação é pura e determinística (101 FR-004, FR-005); refazê-la dá exatamente o que a preparação
produziu, sem expor a fatia do pack no core.

**Alternatives**: as da clarificação 3.

## R4 — Conjunto semente provisório (clarificação 1)

**Decision**: `ai-scouting/eval/golden.yaml` (fora do pacote, versionado com o pack), no formato `version: 1` da 009,
com `name: scouting-semente`, um comentário de cabeçalho e o campo `extra.provisional: true` em todo item, 8 a 12
perguntas escritas a partir dos documentos do corpus — cobrindo os quatro documentos, perguntas normativas (POR,
Estatuto, Resolução), uma consulta histórica (FR-002), uma do manual (narrativo) e uma fora do corpus —, cada uma com
`reference_time` fixo, evidência por documento (com `chunk_id` quando a regra ou artigo é inequívoco), resposta de
referência tirada do próprio trecho e, onde couber, `extra.context`. O mantenedor substitui o conteúdo na curadoria;
formato, validação e CI ficam.

**Rationale**: prova o pipeline de avaliação com o índice real e dá ao CI uma linha de base; marcar como provisório
evita que vire base de calibração.

**Alternatives**: conjunto sintético só nos testes (não exercita o corpus real nem o CI).

## R5 — Validação do conjunto contra o corpus (US1)

**Decision**: na suíte padrão do pack (sem o core, SC-003 da 101): `tests/eval/test_golden.py` lê `eval/golden.yaml`
com `pyyaml` e confere, para todo item, o formato mínimo (id, pergunta, `reference_time` com fuso, resposta de
referência, `provisional`; documentos e citações esperados ambos vazios — fora do corpus — ou ambos não vazios, US1
cen. 1) e que
toda evidência esperada nomeia o `title` de um documento do `corpus/corpus.yaml`, e todo `chunk_id` começa pelo
`<document_id>-<version>#` de um documento dele (a forma dos ids da 102); `extra.context` só com os campos do R3 e
ids de ramo, tema e tipo que existem no léxico da 101, com as datas como texto ISO entre aspas (sem aspas o YAML dá
`date`); item histórico — declarado (`include_superseded` ou `previous_version` verdadeiro) ou lido como tal pela
derivação da 101 — declara o marcador, `effective_from` e `effective_until` — a vigência esperada (US1 cen. 2). No
grupo `platform`, o harness da 009 roda o arquivo sem nenhum item inválido (pelo comando `ai-core eval run`, em
subprocesso).

**Rationale**: US1 Independent Test ("todos os documentos referenciados existem no corpus"); o core não conhece o corpus
(009, Edge Case).

**Alternatives**: validar só pelo harness (o core não sabe o que é o corpus).

## R6 — Configuração da avaliação no repositório

**Decision**: `ai-scouting/eval/` traz, além do `golden.yaml`, `packs.yaml` (o `scouting` com `qdrant_url:
http://localhost:6333`, `index: scouting` e `embedding_dir: .cache/e5`, relativo à raiz do repositório, de onde o
comando roda; `.cache/` entra no `.gitignore`), `assistants.yaml` (o Assistant `scouting` sem `flow`, com a coleção
`scouting`, geração `ollama/qwen3:1.7b` — no perfil `test` da 011 o provider `ollama` é o simulado — e a ACL admitindo
`svc:eval`) e `baseline.json` (a linha de base da semente, R8). Rodada manual com modelo real: os mesmos arquivos no
perfil `memory` (Ollama local) e, para a fidelidade, `--judge`.

**Rationale**: um lugar só para o que a CI e o operador rodam; a ACL explícita para o principal do harness (009 R21).

**Alternatives**: gerar os arquivos no próprio job (esconde a configuração que a linha de base pressupõe).

## R7 — Job de CI `eval` (clarificação 2)

**Decision**: workflow próprio `.github/workflows/eval.yml`, com `paths` em push e PR: `corpus/**`, `src/ai_scouting/rag/**`,
`src/ai_scouting/prompts/**`, `src/ai_scouting/pack.py`, `src/ai_scouting/eval/**`, `src/ai_scouting/context/**`, `eval/**`,
`pyproject.toml`, `uv.lock` e o próprio workflow; `workflow_dispatch` também. Passos: deploy key do `agentic-app`,
submódulos com `update = none`, `uv sync --locked --group platform`, cache do e5 em `.cache/e5` (`actions/cache`, chave
pelo hash de `src/ai_scouting/rag/index/adapters/e5.py`, o arquivo que fixa a revisão e os sha256 da 102) com
`ai-scouting-corpus model fetch .cache/e5` na falta, Qdrant de serviço (`v1.19.2`), ingestão do corpus
real (`ai-scouting-corpus ingest corpus/corpus.yaml`, com `AI_SCOUTING_QDRANT_URL` e `AI_SCOUTING_EMBEDDING_DIR`), e
`ai-core eval run --golden eval/golden.yaml --baseline eval/baseline.json --report report.json` com `AI_CORE_PROFILE=test`,
`AI_CORE_PACKS_FILE=eval/packs.yaml` e `AI_CORE_ASSISTANTS_FILE=eval/assistants.yaml`; o relatório vira artefato do job
(também quando falha). Saída 1 (regressão determinística) ou 2 (entrada inválida) falha o job. O filtro inclui
`context/` além do que a FR-005 lista, porque a derivação muda os filtros de recuperação e o acerto de contexto.

**Rationale**: clarificação 2; workflow à parte porque o filtro de caminhos do GitHub é por workflow.

**Alternatives**: as da clarificação 2.

## R8 — Linha de base da semente (US2)

**Decision**: gerada uma vez, com a mesma configuração da CI (perfil `test`, e5, corpus real, gerador simulado), e
commitada em `eval/baseline.json`; só as métricas determinísticas (recuperação e as duas de domínio determinísticas)
barram, e as demais variam por máquina sem efeito. Atualizar a base é um `--update-baseline` deliberado, num commit que
diz por quê.

**Rationale**: SC-001 (linha de base antes de qualquer calibração) e o harness da 009 (R20).

**Alternatives**: base gerada na CI a cada execução (nunca acusaria regressão).

## R9 — Versões e dependências

**Decision**: o pack sobe para `0.3.0` (capacidade nova: métricas de domínio); `ai-core-contracts>=0.1.2,<0.2`
(precisa de `ai_core_contracts.eval`); contratos e core pela mesma tag `v0.3.0` (nota do R22 da 101). O `agentic-deploy`
passa a `CORE_REF=v0.3.0` e ao commit novo do pack, para a avaliação rodar dentro da imagem (premissa da spec) — numa
passada de encaixe da 002, dona da instalação, depois desta (como na Fase 5); até lá a imagem segue com o pack 0.2.0,
que funciona com o core `v0.2.0`.

**Rationale**: ADR-014 (faixa pela `contract_version`), ADR-021 (tags), premissa "roda dentro de uma imagem de
instalação".

**Alternatives**: manter `>=0.1,<0.2` (instalaria contratos sem `eval` e quebraria na carga).

## R10 — Fronteiras de import

**Decision**: `ai_scouting.eval` importa só `ai_core_contracts`, `ai_scouting.context` (a derivação) e
`ai_scouting.rag.index.api` (`ValidityStatus`). No contrato "só o pack.py compõe", vira uma camada própria entre o
`pack` e a de baixo — `["ai_scouting.pack", "ai_scouting.eval", "ai_scouting.context | … | ai_scouting.rag"]` —, porque
os módulos da camada de baixo são independentes entre si e o `eval` precisa de `context`; entra também nas fontes de
"derivação e validators não alcançam modelo nem MCP" e de "os outros módulos do pack veem só o seam do índice", e o
`tests/test_purity.py` passa a varrer `eval/` (sem relógio: o dia vem do `reference_time` do item). Nenhuma
infraestrutura (sem `yaml` nem I/O — a leitura do arquivo é dos testes e do harness).

**Rationale**: princípio XIII; a métrica é pura.

**Alternatives**: nenhum.

## R11 — Fora desta passada

**Decision**: calibração de candidatos, trechos, tamanho de chunk e limiar do portão (US3), comparação de embeddings
(US4) e de modelos locais (US5): esperam o conjunto curado. O design e os candidatos (e5 small/base, bge-m3, hospedado;
Qwen3 1.7B, Gemma 4 E2B) ficam como estão.

**Rationale**: clarificação 1.

**Alternatives**: nenhum.

---

## Passada de 2026-10-21 ([ADR-043](../../docs/adr/ADR-043-indice-do-scouting-gerado-no-desenvolvimento.md))

## R12 — Eval sobre o artefato e a comparação dos modelos

- **Decision**: `eval/packs.yaml` só com `embedding_dir: .cache/e5` (o default é o artefato em memória); `eval/packs-
  pplx.yaml` com `embedder: pplx`; o workflow `eval` sem o serviço Qdrant e sem a ingestão, mas conferindo que o
  artefato espelha o corpus (102 R25). A linha de base não muda: rodada local com o artefato e o e5 deu exatamente as
  métricas da base (recall@5 0,8889, MRR 0,7222, `scouting:context_accuracy` 0,9).
- **Rationale** (ADR-043, item 7): o embedder é configuração do pack, que vale para a instalação; a comparação são duas
  rodadas, cada uma com o próprio `packs.yaml`, e não dois Assistants — a leitura do ADR que o harness da 009 permite.
- **Alternatives**: dois packs com nomes diferentes (o mesmo código instalado duas vezes).

---

## Passada de 2026-10-27 (revisão do RAG; [relatório](../../docs/revisao-rag-scouting-2026-10.md))

## R13 — Fatos pelo conteúdo: `scouting:fact_recall`

- **Decision**: o item declara `extra.facts` (texto, ou lista de redações alternativas); a métrica normaliza fatos e
  textos com o `normalize` da 101 e casa palavra a palavra (`contains_term`) no texto dos trechos de
  `EvalObservation.delivered`. O texto vem de uma função `chunk_id → texto` que o `pack.py` injeta: `chunk_texts` do
  adapter do artefato (`rag/index/adapters/artifact.py`), que lê `chunks.jsonl` na primeira consulta, conferindo o
  sha256 do manifesto. Só com `store: memory`; com o Qdrant, a métrica não é declarada. Determinística (o texto é do
  artefato, não da geração).
- **Rationale**: a evidência da 009 casa por documento, seção ou `chunk_id`; um stub "O Marco Simbólico" do manual
  certo contaria como acerto, e o `chunk_id` muda com o chunking — que a 102 vai mudar. O `EvalChunk` não traz texto, e
  o pack já tem o artefato: a injeção mantém a métrica pura (R10) e evita mudar o contrato 001.
- **Alternatives**: `EvalChunk.text` no contrato 001 (ADR e versão de contrato para o que o pack já resolve); uma suíte
  que simula o pipeline no pack (duplicaria o corte do gateway e o rerank do core, e mediria uma cópia).

## R14 — Corpus sem os PDFs no git: conferência pelo catálogo, semente e linha de base

- **Decision**: com os originais fora do git (decisão do mantenedor em 2026-10-26), o passo "o artefato espelha o
  corpus" do workflow `eval` deixa de reingerir e roda `tests/rag/ingestion/test_artifact_catalog.py`: valida o
  `corpus.yaml`, deriva a linhagem e compara, documento a documento, `fields`, `source_file` e `source_url` do
  `documents.jsonl` com o que a ingestão gravaria. A semente troca s08 e s09 (o "Escotistas em Ação — Ramo Lobinho"
  saiu do catálogo) pelas mesmas perguntas no Manual do Escotista — Ramo Lobinho (`cap4@p116`, `cap9@p297`), e a
  cobertura exige os tipos `por`, `estatuto`, `resolucao` e `manual` em vez de todos os títulos. A linha de base é
  refeita com o corpus de 593 documentos: recall@5 0,8889 → 0,7778 e MRR 0,7222 → 0,5778 — s02 (POR, data de fundação
  da UEL) e s07 (consulta de 2022) deixaram de achar a evidência entre os novos documentos.
- **Rationale**: o que se confere sem os PDFs é o que o catálogo decide; uma mudança de catálogo sem reingestão é o erro
  que o passo existia para pegar. O conteúdo dos PDFs só muda com quem os tem, e a reingestão continua lá.
- **Alternatives**: conferir o sha256 do `fontes.yaml` contra o `source_sha256` do artefato (acopla o teste a um arquivo
  de curadoria sem contrato); manter os PDFs no git (decisão contrária do mantenedor).

## R15 — O conjunto de regressão

- **Decision**: `eval/regression.yaml`, 20 itens com data de 2026-10-27: marco simbólico por ramo (5) e duas paráfrases;
  quatro agregados com os cinco ramos ("dos 5 ramos", "de cada ramo", "dos cinco ramos", os cinco nomeados); uma
  comparação (Lobinho × Sênior); lema por ramo (3) e de cada ramo; faixa etária do Lobinho e de cada ramo; a Regra 054
  e o sinal do Ramo Filhotes. `extra.group` agrupa (`individual`, `agregado`, `comparativo`, `normativo`). Validado em
  `tests/eval/test_regression.py`: formato, grupos e todo fato presente no texto do artefato. Linha de base em
  `eval/regression-baseline.json` (perfil `test`, artefato e e5): `fact_recall` 0,52 — marcos por ramo 4/5 (Pioneiro
  0), agregados 0,2–0,4, lemas e faixas etárias quase sempre 0 (só o POR os enuncia), Regra 054 0.
- **Rationale**: o mesmo conceito em várias formas e outros conceitos com o mesmo padrão (lema, faixa etária) impedem
  que uma correção acerte só a pergunta do exemplo. Os fatos de lema e faixa etária estão só no POR, então os itens
  medem também o defeito da ingestão das regras.
- **Alternatives**: acrescentar os itens à semente (a semente tem 8–12 itens e será trocada pela curadoria, FR-001).

## R16 — `branches` no contexto esperado ([ADR-045](../../docs/adr/ADR-045-filhotes-e-consulta-multifaceta-no-scouting.md))

- **Decision**: `CONTEXT_FIELDS` e a derivação refeita ganham `branches` (comparado como conjunto); a validação da
  semente aceita só ids do léxico; os agregados e o comparativo do conjunto de regressão declaram as facetas, e a
  `context_accuracy` desses 7 itens é 1,0 na linha de base de 2026-10-27 (`fact_recall` 0,81).
- **Rationale**: a busca por faceta depende da derivação; um léxico que deixe de casar "cada ramo" aparece aqui antes de
  aparecer no `fact_recall`.
- **Alternatives**: nenhum.
