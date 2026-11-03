# Contrato — métricas de domínio do scouting (Fase 6)

Decisões em [research.md](../research.md) R2, R3, R10 e R13; tipos em [data-model.md](../data-model.md). Implementam
`EvalMetric` do contrato 001 (`axon_ai_contracts.eval`, ADR-027) e são declaradas pelo `pack.py` em `eval_metrics(ctx)`,
nesta ordem. O harness da 009 as reporta como `scouting:<nome>`.

## Superfície

| Classe (`axon_scouting.eval`) | `name` | `better` | `deterministic` |
|---|---|---|---|
| `ContextAccuracy` | `context_accuracy` | `higher` | `True` |
| `CurrentDocumentRate` | `current_document_rate` | `higher` | `True` |
| `ValidityNoticeRate` | `validity_notice_rate` | `higher` | `False` |
| `FactRecall` | `fact_recall` | `higher` | `True` |

A `FactRecall` só é declarada com `store: memory` (FR-014): recebe do `pack.py` a função que dá o texto de um trecho
pelo `chunk_id`, lida do artefato do índice na primeira consulta.

Puras e síncronas: sem relógio, sem I/O, sem estado entre itens. `None` = não se aplica ao item (o harness não o conta
no agregado).

## `context_accuracy`

Esperado = `item.extra["context"]` (só os campos declarados). Obtido = `derive_context(item.question,
reference_day(item.reference_time))` da 101.

| # | Item | Resultado |
|---|---|---|
| 1 | sem `extra.context` (ou `context` vazio) | `None` |
| 2 | declara `branch: lobinho` e a derivação dá `lobinho` | `1.0` |
| 3 | declara `branch: null` e a derivação não acha ramo | `1.0` |
| 4 | declara `topics: [uniforme]`, derivação dá `(uniforme, cerimonias)` | `0.0` (conjunto diferente) |
| 5 | declara `document_types: [estatuto, por]`, derivação dá `(por, estatuto)` | `1.0` (ordem não conta) |
| 6 | declara 4 campos, 3 casam | `0.75` |
| 7 | consulta histórica "em 2022": `include_superseded: true`, `effective_from: 2022-01-01`, `effective_until: 2022-12-31` | `1.0` |
| 8 | `reference_time` às 22h de Brasília do dia D (D+1 em UTC), item sem período: `effective_from` e `effective_until` = D | `1.0` |
| 9 | campo fora do R3 em `extra.context` | ignorado na métrica (a validação do conjunto o recusa antes) |

## `current_document_rate`

Item histórico = `extra.context` com `include_superseded` ou `previous_version` verdadeiro.

| # | Item e observação | Resultado |
|---|---|---|
| 1 | item histórico | `None` |
| 2 | nenhum trecho entregue (`delivered` vazio) | `None` |
| 3 | 5 entregues, todos `vigente` | `1.0` |
| 4 | 4 entregues: 3 `vigente`, 1 `substituido` | `0.75` |
| 5 | entregue com status ausente (`None`) | conta como não vigente |
| 6 | candidatos (`retrieved`) não vigentes, entregues todos vigentes | `1.0` (mede o que chegou ao modelo) |

## `validity_notice_rate`

"Não vigente" como no `validity_notice` da 104: status diferente de `vigente`, inclusive vazio.

| # | Observação | Resultado |
|---|---|---|
| 1 | sem citações, ou todas `vigente` | `None` |
| 2 | uma citação `revogado` e a flag `non_current_source` | `1.0` |
| 3 | uma citação `substituido` e nenhuma flag | `0.0` |
| 4 | citação sem `status` e a flag | `1.0` |

## `fact_recall`

Fatos e textos normalizados como na 101 (`normalize`); casamento por palavra inteira (`contains_term`). Um fato é texto
ou lista de redações alternativas (basta uma).

| # | `extra.facts` / entregues | Resultado |
|---|---|---|
| 1 | sem `extra.facts` | `None` |
| 2 | dois fatos, os dois no texto entregue | `1.0` |
| 3 | dois fatos, um no texto entregue | `0.5` |
| 4 | um fato com alternativas, uma delas no texto | `1.0` |
| 5 | nada entregue, ou `chunk_id` sem texto | `0.0` |
| 6 | o fato só aparece como parte de palavra maior | `0.0` |

## Verificações

| # | Verificação | Onde |
|---|---|---|
| 1 | as tabelas acima, caso a caso | `tests/eval/test_metrics.py` |
| 2 | a conformidade da 001 com o pack aceita as três (`eval_metric.*` sem problema) | `tests/test_conformance.py` |
| 3 | `eval/` não lê relógio | `tests/test_purity.py` |
| 4 | numa rodada pelo harness, as três aparecem como `scouting:<nome>` | `tests/integration/test_eval.py` (grupo `platform`) |
| 5 | com o índice em memória, a `fact_recall` lê o texto do artefato | `tests/test_pack.py` |
