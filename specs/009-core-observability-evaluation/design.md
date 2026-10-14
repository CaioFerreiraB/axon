# Design — 009 Observability & Evaluation

> Insumo técnico pré-aprovado para `/speckit-plan`. Origem: arch-v1 §29, §27; ADR-007, ADR-012, ADR-013; Fase 9:
> ADR-033, ADR-034 e o plano da Fase 9 (2026-10-13).

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

## Destinos, uso, custo e Langfuse (Fase 9, [ADR-034](../../docs/adr/ADR-034-trace-com-destinos-e-conteudo-opcional.md))

**Fan-out.** `TraceService(exporters=[principal, uso, langfuse])` no lugar do exporter único — muda a porta interna
`TraceExporter`, não o seam. Cada destino declara `accepts_content: bool`; a falha de um é isolada e contada. O
`ModelExchange` é descartado no próprio `TraceService` com a captura desligada e só vai a destinos com `accepts_content`.

**Uso.**

- Projeção pura em `observability/domain/usage.py`: `execution_started`, `model_call` e `execution_finished` viram
  linhas; o Assistant da chamada vem do `execution_started` da mesma requisição (mapa com TTL — as chamadas de uma
  requisição são sequenciais).
- Tabelas no schema `observability` ([ADR-015](../../docs/adr/ADR-015-persistencia-postgres-por-modulo.md)):
  `model_calls(request_id, at, origin, assistant, provider, model, role, input_tokens, output_tokens, duration_ms,
  failed)` e `executions(request_id, started_at, finished_at, origin, assistant, flow, ok, duration_ms)`. A origem
  (`production`/`evaluation`) é fixada pela composition root ao montar o destino: `ai-core eval run` monta com
  `evaluation` (clarificação de 2026-10-13). Linhas brutas, sem agregados
  pré-calculados.
- Buffer limitado (`deque`), `emit` continua síncrono; esvaziado a cada 2 s por uma `PeriodicTask` do ciclo de vida da
  app e no `Platform.aclose()` (CLI e harness também esvaziam); excesso descartado e contado (`trace:usage` na saúde).
- Consulta: `date_trunc('day', at AT TIME ZONE tz)`; o adapter de memória calcula igual em Python. Fuso padrão
  `AI_CORE_USAGE_TIMEZONE` (UTC; a instalação usa `America/Sao_Paulo`). Retenção `AI_CORE_USAGE_RETENTION_DAYS`
  (padrão 400), expurgo diário.

**Preços.** `prices(provider, model, usd_per_mtok_in, usd_per_mtok_out, effective_from)`; custo calculado na consulta
pelo preço vigente em cada dia. Os preços ficam aqui, não na 006: a 009 não pode importar `ai_core.llm`
(import-linter), e o custo é projeção de relatório, não roteamento.

**Langfuse.**

- Candidato recomendado (spike no research): `opentelemetry-sdk` + exportador OTLP/HTTP para
  `{host}/api/public/otel/v1/traces` com Basic auth; o `BatchSpanProcessor` dá a fila limitada que descarta em vez de
  bloquear. Já permitido em `observability/adapters/` (ADR-013; o import-linter barra fora dele). Alternativa: a API de
  ingestão com `httpx`.
- Mapeamento: `ExecutionStarted`/`ExecutionFinished` → trace raiz (nome = Assistant; flow e packs como metadados);
  `ModelCall` → generation (início = `at − duration_ms`, modelo, uso; nível de erro em falha); `ToolCall` → span;
  `ControllerDecision`, `CoverageGate`, `ValidationRun`, `Retrieval` → eventos; `ExecutionError` → evento de erro
  (mensagem redigida); `ModelExchange` → entrada e saída da generation. Traces raiz órfãos fecham por TTL.
- `reload()` ao gravar os ajustes: reconstrói o exportador e esvazia o antigo. "Testar conexão": GET autenticado num
  endpoint público do Langfuse (confirmar no spike). Item de saúde não crítico `trace:langfuse`.

**Ajustes e segredos.** Precedência pura em `domain/` (instalação > runtime > padrão, com a origem por campo);
`AI_CORE_LANGFUSE_{HOST,PUBLIC_KEY,SECRET_KEY}` é tudo ou nada (parcial = erro de configuração que nomeia a
variável que falta); `AI_CORE_LANGFUSE_CAPTURE_CONTENT` vale à parte. Chave secreta de runtime cifrada pela porta
`SecretCipher` (AES-GCM, subchave HKDF `ai-core/observability/v1` de `AI_CORE_MASTER_KEY`, [ADR-033](../../docs/adr/ADR-033-segredos-de-runtime-cifrados-com-a-chave-mestra.md)); sem chave
mestra, gravar a secreta é recusado.

**Conteúdo.** `ModelExchange(request_id, role, provider, model, messages, output)`, emitido pela 006 logo depois do
`ModelCall`; o destino os pareia pela ordem. Redação de credenciais e corte por mensagem (16 KB). JSONL e memória nunca o
recebem — teste de conformidade dos destinos.

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
| `TraceExporter` | secundária | arquivo (Fase 1); Fase 9: lista de destinos (principal, uso, Langfuse), cada um com `accepts_content` | em memória; falha de um destino não interrompe a execução nem os outros |
| Usage Report, Price Book, Trace Destinations | primária (seams, Fase 9) | `observability/service.py` | relatório contra chamadas emitidas; precedência de ajustes; segredo só de escrita |
| `UsageStore` | secundária (Fase 9) | memória → Postgres | conformidade memória + Postgres (fuso, vigência de preço) |
| `PriceStore` | secundária (Fase 9) | memória → Postgres | conformidade memória + Postgres |
| `DestinationSettingsStore` | secundária (Fase 9) | memória → Postgres | conformidade memória + Postgres |
| `SecretCipher` | secundária (Fase 9) | AES-GCM + HKDF | chave fixa de teste |
| `LangfuseTransport` | secundária (Fase 9) | OTLP/HTTP (ou API de ingestão) | Langfuse simulado; travado não bloqueia |
| `Clock` | secundária | sistema | relógio fixo |
| Eval Harness | adapter primário sobre `ExecutionEngine` (005) | `eval/service.py` + CLI | conjunto dourado mínimo contra o pack de referência |
| `BaselineStore` | secundária | arquivo versionado | em memória |
| `Judge` | secundária (só offline) | modelo via `LLMProvider` | juiz simulado |

Trace e harness ficam em lados opostos do hexágono; dividir esta spec em duas é opcional.
