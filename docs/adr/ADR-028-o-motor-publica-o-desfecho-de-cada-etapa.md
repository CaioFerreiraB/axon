# ADR-028 — O motor publica o desfecho de cada etapa

- **Status:** Aceita · 2026-10-13
- **Specs afetadas:** [005-core-execution-engine](../../specs/005-core-execution-engine/spec.md) (evento novo no seam
  Execution Engine, FR-012a), [008-core-http-api](../../specs/008-core-http-api/spec.md) (mostra a timeline no Open WebUI,
  FR-005a), [009-core-observability-evaluation](../../specs/009-core-observability-evaluation/spec.md) (o harness
  ignora o evento novo; o trace não muda)
- **Origem:** pedido do mantenedor depois da prova no Open WebUI (2026-10-13): o bloco de "pensamento" mostrava cinco
  frases fixas, sem as chamadas, os retornos e as decisões da execução

## Contexto

O seam Execution Engine publica `ProgressEvent(stage, detail)`, que significa "uma etapa começou". O `detail` é texto
livre e curto (número da iteração, nome da tool, uma contagem). Todo o resto fica no estado do grafo, que não é contrato
(ADR-011), ou só no trace (009), que a API não lê:

- que tool foi chamada e com que argumentos;
- quantos trechos voltaram e de quais documentos;
- o que o portão e o controller decidiram;
- qual modelo gerou e quantos tokens usou.

O trace também não serviria: pelo ADR-017, ele nunca carrega argumentos de tool, porque é lido pelo operador, e a
consulta é por requisição depois do fato, sem assinatura em tempo real.

O usuário quer acompanhar a execução no Open WebUI como uma timeline. O v0.12 já tem esse componente: eventos `status`
na chave `event` do chunk SSE viram uma linha viva com histórico expansível (008 research R42).

## Decisão

1. O `ExecutionEvent` ganha um membro: `StepFinished(stage, outcome)`. Ele sai quando uma etapa termina, depois de
   todos os eventos dela. `ProgressEvent` não muda e continua significando "uma etapa começou".
2. `outcome` é um desfecho tipado, ou `None` quando não há o que contar (`prepare_context`, `validate_answer`). Os
   desfechos possíveis:
   - `ToolCallsOutcome` (`retrieve`, `execute_tool`): uma `ToolCallSummary` por chamada, com nome, tipo, argumentos,
     status, corte e as fontes (`SourceRef`: documento, seção, página) dos trechos que voltaram;
   - `RerankOutcome` (`rerank`): candidatos, fontes mantidas e packs cujo reranker falhou;
   - `GateOutcome` (`gate`): cobertura, melhor score, limiar, rota e trechos entregues;
   - `ControllerOutcome` (`controller`): iteração, ação (`tool`, `answer`, `invalid`, `failed`), modelo, tool,
     argumentos e motivo. Os limites de iterações e de contexto não chamam o controller e não ganham desfecho: chegam
     como registros `notice` no `FinalEvent`, como já chegavam;
   - `GenerationOutcome` (`generate`): modelo e tokens de entrada e de saída, quando o provider os informa;
   - `CatalogOutcome` (`load_capabilities`): quantas tools e os aliases MCP indisponíveis, sem o motivo.
3. Os desfechos **nunca** carregam texto de trecho, conteúdo de resultado de tool, texto de erro de tool, prompt ou
   resposta. Os argumentos de tool **podem** ir: o stream é entregue ao próprio Principal que fez o pedido, e os
   argumentos saem da conversa dele. A regra do ADR-017 continua valendo para o trace, que não muda.
4. Com `stream=False`, o motor continua entregando só o `FinalEvent`.
5. O motor não mede tempo. Quem consome o evento mede o intervalo entre `ProgressEvent` e `StepFinished`; na 008, pelo
   `Clock` (princípio XIII).

## Alternativas rejeitadas

*Texto mais rico no `detail`.* Não cabe a resposta da etapa: o `ProgressEvent` sai antes do trabalho, e um texto livre
obrigaria a 008 a interpretar frases para formatar.

*Um `ProgressEvent` com fase (`start`/`end`) e um mapeamento livre de fatos.* Perde a validação na construção e a
checagem de tipos. Além disso, quem hoje trata todo `ProgressEvent` como "etapa começou" passaria a receber dois por
etapa.

*Ler o trace em tempo real (um tee por requisição no Trace Sink).* O trace não carrega argumentos (ADR-017) nem
fontes no momento da recuperação. O tee também acoplaria a API à 009 por um caminho que o seam não promete.

## Consequências

- O seam da 005 cresce de forma aditiva. Consumidores que fazem `match` sobre o evento sem caso para `StepFinished` o
  ignoram: a 008 no modo `reasoning` e na resposta sem streaming, e o harness da 009, que usa `isinstance`.
- A conformidade do seam passa a conferir um `StepFinished` depois do trabalho de cada etapa.
- A 008 ganha o modo de progresso `status` (cabeçalho `x-ai-core-progress`), que mostra a timeline no Open WebUI. Sem o
  cabeçalho, nada muda para o cliente.
- Uma etapa nova do motor sai com `outcome=None` até ganhar um desfecho próprio, que se acrescenta por ADR.
