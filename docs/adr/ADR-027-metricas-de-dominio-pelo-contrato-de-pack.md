# ADR-027 — Métricas de domínio pelo contrato de pack

- **Status:** Aceita · 2026-10-13
- **Specs afetadas:** [001-core-contracts](../../specs/001-core-contracts/spec.md) (protocolo de métrica e o hook
  opcional; contratos `0.1.2`), [002-core-pack-runtime](../../specs/002-core-pack-runtime/spec.md) (coleta o hook e o
  expõe ao harness), [009-core-observability-evaluation](../../specs/009-core-observability-evaluation/spec.md) (o harness
  calcula e reporta), [105-scouting-evaluation](../../specs/105-scouting-evaluation/spec.md) (primeiro consumidor)
- **Origem:** clarificação de 2026-10-13 da 009 (pergunta 3), aceita pelo mantenedor

## Contexto

O harness da 009 mede recuperação, rerank, geração, citação e operação de forma genérica. Algumas métricas só fazem
sentido no domínio — a "taxa de documento vigente" do scouting, por exemplo —, e a FR-005 da 009 exige que o harness as
aceite e as ponha no mesmo relatório, sob a mesma linha de base. Um pack, porém, só depende de `ai-core-contracts`
(ADR-004, ADR-014): não pode importar o harness.

## Decisão

1. O contrato 001 ganha, num módulo próprio (`ai_core_contracts.eval`), três tipos **aditivos**:
   - `EvalItem` — o que o item do conjunto dourado declara: pergunta, data de referência, evidências esperadas
     (documento, seção opcional, id de trecho opcional), resposta de referência, citações esperadas e `extra` (campos de
     domínio, opacos para o core);
   - `EvalObservation` — o que a execução produziu: resposta, citações, flags, os trechos recuperados, reordenados e
     entregues (id, score e proveniência, sem texto) e os tipos de registro;
   - `EvalMetric` (Protocol) — `name`, `better` (`"higher"` ou `"lower"`), `deterministic` e `measure(item,
     observation) -> float | None` (síncrono, puro; `None` = não se aplica ao item).
2. Um Protocol separado, `ProvidesEvalMetrics`, declara o hook opcional `eval_metrics(ctx) -> Sequence[EvalMetric]`;
   `PackBase` ganha o default `()`. O `AgentPack` **não** muda: pack sem o hook continua conforme.
3. A 002 chama o hook uma vez, na carga, como os outros hooks de catálogo, confere o tipo e o expõe ao harness por um
   seam próprio (`PackEvalMetrics.eval_metrics(composition)`), com o nome do pack de cada métrica.
4. O harness da 009 calcula as métricas de domínio item a item, agrega como as do core e as compara com a linha de base
   e a tolerância; só as `deterministic` podem barrar o CI.
5. Os contratos sobem para `0.1.2`. Um pack que declara métricas pede `ai-core-contracts>=0.1.2,<0.2`.

## Alternativas rejeitadas

*O pack calcula fora, sobre o relatório do harness.* Sem mudança no contrato, mas a linha de base e a barreira de CI
ficariam em dois lugares, e o "mesmo relatório" da US2 virava anexo.

*Um entry point próprio para métricas.* Separa a métrica do pack que a entende e duplica a descoberta da 002.

*Pôr `eval_metrics` no `AgentPack`.* Quebraria a conformidade de todo pack que não herda de `PackBase`.

## Consequências

- O 001 publica três tipos e um Protocol novos; a suíte de conformidade passa a conferir o hook quando presente.
- A 002 coleta mais um hook e ganha um seam pequeno, consumido só pela 009.
- O formato do item (`EvalItem`) vive no contrato porque é o que a métrica lê; o arquivo do conjunto dourado continua
  sendo formato da 009, que o converte.
