# Contrato — harness de avaliação (Fase 6)

Decisões em [research.md](../research.md) R13–R27; tipos em [data-model.md](../data-model.md), seção "Fase 6".
Seams preservados numa reescrita (Module Boundary): o **formato de conjunto dourado** e o **formato de relatório**.

## Conjunto dourado (YAML, `version: 1`)

```yaml
version: 1
name: exemplo
assistant: docs              # opcional; --assistant tem prioridade
k: [5, 20]                   # opcional
tolerances:                  # opcional; default 0.02 nas determinísticas
  recall@5: 0.02
items:
  - id: q001
    question: "Quem pode ser patrono de um grupo?"
    reference_time: "2026-10-07T12:00:00-03:00"
    expected_documents:
      - document: "Regulamento"
        section: "Regra 31"    # opcional
      - chunk_id: "doc#r31@p37" # opcional, com document
        document: "Regulamento"
    reference_answer: "Pessoas inspiradoras já falecidas…"   # opcional
    expected_citations:
      - document: "Regulamento"
    extra: {}                 # opcional, opaco: vai às métricas de domínio
```

Item com formato inválido vira `invalid` no relatório e não roda; o arquivo só é recusado (saída 2) se não for YAML ou
não tiver `items`.

## Métricas

As do [research.md](../research.md) R17 (core) e R18 (domínio, `<pack>:<nome>`). Só as determinísticas barram.

## CLI (registrada pela 011)

| Comando | Efeito | Saída |
|---|---|---|
| `ai-core eval run --golden <arq> [--assistant <nome>] [--judge <provider/modelo>] [--baseline <arq>] [--update-baseline] [--force] [--report <arq>] [--principal <subject>] [--group <g>]… [--annotate <texto>]…` (principal default `svc:eval`) | roda o conjunto, imprime as métricas e, com `--baseline`, a comparação | 0 sem regressão; 1 com regressão determinística; 2 entrada inválida |
| `ai-core eval compare <relatório> <relatório>…` | métricas lado a lado (benchmark, US4) e as anotações | 0; 2 relatório ilegível |

## Relatório (JSON, `version: 1`)

`golden_set`, `assistant`, `judge`, `started_at`, `core_version`, `k`, `metrics[]` (`name`, `value`, `variance`, `n`,
`deterministic`, `better`), `items[]` (`id`, `metrics`, `citations`, `flags`, `issue_kinds`, `gate_route`, `failure`),
`invalid[]`, `annotations[]`. A linha de base é um relatório.

## Verificações

| # | Verificação | Cenário |
|---|---|---|
| 1 | conjunto mínimo contra um pack de teste com retriever: todas as métricas do R17 no relatório | US2 cen. 1 |
| 2 | métrica de domínio declarada pelo pack aparece como `<pack>:<nome>` | US2 cen. 2 |
| 3 | regressão proposital no retriever de teste → saída 1 nomeando `recall@k` e o delta | US3 cen. 1 |
| 4 | juiz simulado com variância: média e variância reportadas, nunca barra | US3 cen. 2 |
| 5 | `compare` com dois relatórios de Assistants diferentes, lado a lado, com anotações | US4 cen. 1 |
| 6 | item inválido e juiz ausente: o resto roda; as métricas de juiz ausentes | Edge Cases |
| 7 | `reference_time` do item chega ao motor (as Turn Views o veem) | FR-003, ADR-013 |
