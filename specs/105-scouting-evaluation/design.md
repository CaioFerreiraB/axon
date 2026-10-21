# Design — 105 Scouting Evaluation

> Insumo técnico pré-aprovado para `/speckit-plan`. Origem: arch-v1 §21, §27, §29, Parte IX.

## Conjunto dourado

```text
conjunto dourado
├── pergunta
├── documentos que DEVEM ser recuperados   → mede retrieval
├── resposta de referência                 → mede geração
├── citações esperadas                     → mede fundamentação
├── data de referência (todo item)         → fixa reference_time da execução [ADR-013]
└── effective_on esperado (se histórica)   → mede derivação de contexto (101)
```

A data de referência torna cada item reproduzível: revogar um documento depois da curadoria não muda o resultado de
itens antigos. Sem ela, o mesmo caso passaria hoje e falharia amanhã, sem mudança de código. O harness fixa essa data
chamando o motor em processo; a API HTTP não aceita data de referência (008 FR-012). Por isso a avaliação roda dentro de
uma imagem de instalação com `axon-ai` e `axon-scouting` (`axon eval run …`), sem que o pack dependa do `axon-ai`.

Começar pequeno: 30–50 perguntas reais do domínio escoteiro valem mais que 500 sintéticas.

## Métricas de domínio (somam-se às genéricas da 009)

| Métrica | Mede |
|---|---|
| Taxa de documento vigente | 103 — filtro de vigência |
| Acerto de derivação de contexto (ramo, tema, data) | 101 |
| Taxa de citação resolvível / inventada | 104 |
| Taxa de aviso de não vigente quando devido | 104 |

## Calibração (arch-v1 Parte IX)

`top_k` de retrieval, quantidade após rerank, tamanho de chunk, sobreposição, limiar do portão de cobertura. Todos com faixa inicial sugerida, todos a fixar empiricamente na Fase 6.

## Embedding

| Candidato | Prós | Contras |
|---|---|---|
| `multilingual-e5-small/base` | leve, roda em ARM CPU | qualidade média em português técnico |
| `bge-m3` | forte, denso + esparso num modelo | pesado; viável só se ingestão for offline |
| Embedding hospedado | melhor qualidade, zero CPU local | custo por documento, dependência externa |

## Portas e adapters **[ADR-012]**

Este submódulo é conteúdo (conjunto dourado) e métricas de domínio; não tem portas próprias. Ele alimenta o Eval
Harness da 009, que é o adapter primário que executa os itens contra o Assistant `scouting`.

| Porta | Tipo | Adapters | Teste |
|---|---|---|---|
| Formato de conjunto dourado (009) | seam consumido | arquivos versionados em `eval/` | validação de formato pelo harness |
| Métricas de domínio | implementadas aqui, fornecidas ao harness | funções puras | fixtures de resultado |

## LLM local

Comparar `Qwen3 1.7B` e `Gemma 4 E2B`: tokens/s · TTFT · RAM · CPU · qualidade em português · tool calling · fidelidade em RAG. As duas últimas são as decisivas.
