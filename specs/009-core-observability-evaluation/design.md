# Design — 009 Observability & Evaluation

> Insumo técnico pré-aprovado para `/speckit-plan`. Origem: arch-v1 §29, §27; ADR-007, ADR-012, ADR-013.

## Localização

```text
ai-core/packages/core/src/ai_core/
├── observability/          # lado secundário: trace
│   ├── api.py              # seam Trace Sink (emissão) + consulta de trace por request_id
│   ├── domain/             # redação de credenciais, retenção — puro
│   ├── ports.py            # TraceExporter
│   ├── service.py
│   └── adapters/           # exporter: arquivo (Fase 1) → Postgres ou ferramenta (plano); memória (teste)
└── eval/                   # lado primário: harness
    ├── api.py              # formato de conjunto dourado, formato de relatório
    ├── domain/             # métricas determinísticas, comparação com baseline e tolerância — puro
    ├── ports.py            # BaselineStore, Judge (LLM, só offline)
    ├── service.py          # runner: executa itens pela porta ExecutionEngine (005)
    └── adapters/           # baseline em arquivo, juiz LLM, CLI
```

## Trace Sink [ADR-013]

Porta de emissão. 004 (chamadas de tool), 005 (iterações, decisões, validações) e 006 (chamadas de modelo) emitem
dados com o `request_id`; nenhum deles conhece o backend nem o harness.

> Resolvido na clarificação de 2026-09-17: a candidata "**API do OpenTelemetry** como porta" foi **rejeitada** — ela
> poria uma biblioteca externa no seam e, com ela, nos `api.py` de 004, 005 e 006, contra o princípio XIII. O seam é
> contrato próprio, com eventos tipados publicados por este módulo (um método de emissão; evento novo é tipo novo, sem
> mudar o seam). O SDK e o exporter do OpenTelemetry seguem sendo candidatos — como **adapters** do `TraceExporter`,
> montados pela composition root (011). A semântica do seam é a que este design descreve.

## Trace

Um trace por requisição, cobrindo: assistant resolvido, packs ativos, tools em catálogo, cada iteração do controller, cada tool executada com latência, chunks recuperados com score, tokens por papel, validators e seus resultados.

Sem isso, depurar por que o controller escolheu determinada tool é adivinhação.

## Harness de avaliação

A versão v0 afirmava corretamente que os números do RAG "devem ser calibrados empiricamente" — sem harness, não há empiria.

```text
conjunto dourado
├── pergunta
├── documentos que DEVEM ser recuperados   → mede retrieval
├── resposta de referência                 → mede geração
├── citações esperadas                     → mede fundamentação
└── data de referência                     → fixa reference_time da execução [ADR-013]
```

| Camada | Métrica |
|---|---|
| Retrieval | recall@k, MRR, taxa de documento vigente (métrica de domínio, fornecida pelo pack) |
| Rerank | ganho de precisão sobre baseline |
| Geração | fidelidade ao trecho, cobertura |
| Citação | taxa de citação resolvível, taxa de citação inventada |
| Operação | latência p50/p95, tokens por resposta |

Roda em CI a cada mudança de chunking, prompt, retriever ou modelo. **É o que responde se uma mudança melhorou ou piorou.**

O harness é o **único caminho que fixa `reference_time`** (008 FR-012, ADR-013): executa cada item em processo, pela
porta `ExecutionEngine`, passando a data do item no `ExecutionRequest`. É exposto como subcomando `ai-core eval run`
(registrado pela 011) e roda dentro de uma imagem de instalação que contém os packs avaliados.

Começar pequeno: 30–50 perguntas reais do domínio valem mais que 500 sintéticas.

## Julgamento por LLM

Pertence **só** ao harness offline (ADR-007) — fidelidade ("a resposta é fiel ao trecho?"). No caminho da requisição, apenas validação mecânica.

## Benchmark de modelos

```text
tokens/s · tempo até primeiro token · RAM · CPU
qualidade em português · tool calling · fidelidade em RAG
```

## Portas e adapters **[ADR-012]**

| Porta | Tipo | Adapters por fase | Teste |
|---|---|---|---|
| Trace Sink | primária (seam, emissão) | `observability/service.py` | emissores gravam num sink em memória |
| Consulta de trace | primária (seam) | `observability/service.py` | por `request_id` |
| `TraceExporter` | secundária | arquivo (Fase 1) → a decidir no plano | em memória; falha do exporter não interrompe a execução |
| Eval Harness | adapter primário sobre `ExecutionEngine` (005) | `eval/service.py` + CLI | conjunto dourado mínimo contra o pack de referência |
| `BaselineStore` | secundária | arquivo versionado | em memória |
| `Judge` | secundária (só offline) | modelo via `LLMProvider` | juiz simulado |

Trace e harness ficam em lados opostos do hexágono; dividir esta spec em duas é opcional.
