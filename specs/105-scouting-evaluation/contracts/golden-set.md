# Contrato — conjunto dourado do scouting (Fase 6, semente)

Decisões em [research.md](../research.md) R4–R8; campos em [data-model.md](../data-model.md). O formato é o da 009
([contracts/eval-harness.md](../../009-core-observability-evaluation/contracts/eval-harness.md), `version: 1`); aqui, o
que o domínio exige a mais. Estas regras valem para a semente e para a versão curada.

## Arquivo

`axon-scouting/eval/golden.yaml`, com `version: 1`, `name` (`scouting-semente` até a curadoria) e `assistant: scouting`.

```yaml
# Conjunto SEMENTE PROVISÓRIO (spec 105, clarificação 1): perguntas escritas a partir do corpus, sem curadoria.
# Nenhuma calibração se decide sobre ele; a curadoria troca o conteúdo, não o formato.
version: 1
name: scouting-semente
assistant: scouting
items:
  - id: s01
    question: "…"
    reference_time: "2026-10-13T12:00:00-03:00"
    expected_documents:
      - document: "Princípios, Organização e Regras (POR)"
        chunk_id: "por-2025.2.1#regra31@p37"
    reference_answer: "…"
    expected_citations:
      - document: "Princípios, Organização e Regras (POR)"
    extra:
      provisional: true
      context: { branch: null, document_types: [por] }
```

## Regras de domínio (validação)

| # | Regra | Falha quando |
|---|---|---|
| 1 | todo item tem `id` único, `question`, `reference_time` com fuso (FR-006) e `reference_answer`; `expected_documents` e `expected_citations` são ambos vazios (pergunta fora do corpus) ou ambos não vazios (US1 cen. 1) | falta um deles, o fuso, ou só uma das duas listas vazia |
| 2 | todo `document` de evidência é o `title` de uma entrada de `corpus/corpus.yaml` | título fora do catálogo |
| 3 | todo `chunk_id` de evidência começa por `<document_id>-<version>#` de uma entrada do catálogo, e o `document` ao lado é o título dessa mesma entrada | prefixo desconhecido ou de outro documento |
| 4 | `extra.context` só com `branch`, `topics`, `document_types`, `effective_from`, `effective_until`, `include_superseded`, `previous_version` | campo a mais |
| 5 | ramo, temas e tipos são ids do léxico da 101; datas são texto ISO **entre aspas** (sem aspas, o YAML as lê como `date`, e a métrica compararia objeto com texto) | id inexistente, data que não é texto, data ilegível |
| 6 | item histórico — o que declara `include_superseded` ou `previous_version` verdadeiro, ou cuja pergunta a derivação da 101 lê como histórica — declara em `extra.context` o marcador, `effective_from` e `effective_until` (US1 cen. 2) | faltando |
| 7 | na semente, todo item tem `extra.provisional: true` | faltando |
| 8 | o leitor do harness da 009 não marca nenhum item como inválido | algum `invalid` |

## Composição da semente (FR-002, R4)

8 a 12 itens: os quatro documentos do corpus com ao menos uma evidência cada; perguntas normativas (POR, Estatuto,
Resolução); ao menos uma consulta histórica, num período em que um documento do corpus estava em vigor; ao menos uma
do manual (narrativo); uma fora do corpus (sem evidência esperada).

## Manutenção

Item que se revela ambíguo sai do arquivo com a justificativa na mensagem do commit que o remove (Edge Cases da spec);
resposta que mudou com uma nova versão de documento ganha um item novo com a data nova, e o antigo fica.

## Linha de base e CI

`eval/baseline.json` é um relatório da 009 gerado com a configuração da CI (R8). O job `eval` (R7) falha com saída 1
(regressão determinística além da tolerância) ou 2 (entrada inválida); métricas não determinísticas nunca barram.

## Verificações

| # | Verificação | Onde |
|---|---|---|
| 1 | regras 1–7 sobre `eval/golden.yaml`, só com os contratos | `tests/eval/test_golden.py` |
| 2 | um conjunto com documento fora do catálogo é recusado, nomeando item e documento | `tests/eval/test_golden.py` |
| 3 | regra 8: `axon eval run` com a semente, `invalid` vazio no relatório | `tests/integration/test_eval.py` (grupo `platform`) |
| 4 | o job `eval` roda a semente contra a linha de base sem regressão | `.github/workflows/eval.yml` |
