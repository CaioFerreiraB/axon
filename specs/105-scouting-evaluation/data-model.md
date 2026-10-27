# Data Model — 105 Scouting Evaluation, Fase 6

Decisões em [research.md](research.md). O formato do arquivo é o da 009
([contracts/eval-harness.md](../009-core-observability-evaluation/contracts/eval-harness.md)); aqui, só o que o domínio
acrescenta.

## Item do conjunto semente (`eval/golden.yaml`)

Os campos da 009 (`id`, `question`, `reference_time`, `expected_documents`, `reference_answer`, `expected_citations`,
`extra`), com estas regras do domínio:

| Campo | Regra |
|---|---|
| `reference_answer` | obrigatória em todo item |
| `expected_documents`, `expected_citations` | ambas vazias (pergunta fora do corpus) ou ambas não vazias |
| `expected_documents[].document`, `expected_citations[].document` | o `title` de um documento de `corpus/corpus.yaml` |
| `expected_documents[].chunk_id`, `expected_citations[].chunk_id` | opcional; começa por `<document_id>-<version>#` de um documento do catálogo |
| `extra.provisional` | `true` em todo item da semente (R4) |
| `extra.context` | opcional; só os campos abaixo |

### `extra.context` (R3)

| Campo | Tipo | Comparação com a derivação da 101 |
|---|---|---|
| `branch` | `str \| null` | igualdade (id do léxico: `lobinho`, `escoteiro`, `senior`, `pioneiro`; `null` = sem ramo) |
| `topics` | lista de ids de tema do léxico | conjunto |
| `document_types` | lista de ids de tipo do léxico | conjunto |
| `effective_from`, `effective_until` | texto ISO entre aspas (`"2022-01-01"`) | igualdade com o início / fim da vigência derivada, em ISO |
| `include_superseded`, `previous_version` | bool | igualdade |

## Métricas de domínio (`axon_scouting/eval/metrics.py`, R2)

| Classe | `name` | `better` | `deterministic` | `measure(item, observation)` |
|---|---|---|---|---|
| `ContextAccuracy` | `context_accuracy` | `higher` | `True` | casados / declarados em `extra.context`; sem `context` → `None` |
| `CurrentDocumentRate` | `current_document_rate` | `higher` | `True` | entregues com status `vigente` / entregues, em item não histórico; senão `None` |
| `ValidityNoticeRate` | `validity_notice_rate` | `higher` | `False` | 1 ou 0 pela flag `non_current_source`, em item com citação não `vigente`; senão `None` |
| `FactRecall` | `fact_recall` | `higher` | `True` | fatos de `extra.facts` no texto dos entregues / fatos; sem `facts` → `None` (R13) |

Item histórico = `extra.context` com `include_superseded` ou `previous_version` verdadeiro; ele declara obrigatoriamente
`effective_from` e `effective_until` (US1 cen. 2). Pergunta que a derivação da 101 lê como histórica também precisa
declarar o marcador e as datas.

## Arquivos de avaliação (`axon-scouting/eval/`, R6)

| Arquivo | Conteúdo |
|---|---|
| `golden.yaml` | o conjunto semente (provisório) |
| `packs.yaml` | o `scouting` com `qdrant_url` (`http://localhost:6333`), `index` e `embedding_dir: .cache/e5` |
| `assistants.yaml` | o Assistant `scouting` (`rag_first`, coleção `scouting`, geração do perfil, ACL com `svc:eval`) |
| `baseline.json` | o relatório da rodada de referência da semente (R8; refeito no corpus de 593 documentos, R14) |
| `regression.yaml` | o conjunto de regressão da recuperação (US6, R15) |
| `regression-baseline.json` | o relatório da rodada de referência do conjunto de regressão (R15) |

## Item do conjunto de regressão (`eval/regression.yaml`, R15)

O formato da 009, sem evidência por documento: `id`, `question`, `reference_time` (com fuso), `reference_answer`
opcional e, em `extra`, `group` (`individual`, `agregado`, `comparativo`, `normativo`) e `facts` (lista não vazia; cada
fato é texto ou lista de redações alternativas, e existe no texto do artefato).
