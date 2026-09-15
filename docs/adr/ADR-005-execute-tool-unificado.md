# ADR-005 — `execute_tool` unificado — retrieval é tool

- **Status:** Aceita · 2026-09-10
- **Specs afetadas:** [004-core-capability-gateway](../../specs/004-core-capability-gateway/spec.md), [005-core-execution-engine](../../specs/005-core-execution-engine/spec.md), [001-core-contracts](../../specs/001-core-contracts/spec.md)
- **Origem:** arch-v1 Parte VIII

## Contexto

O desenho original tinha nós separados `retrieve` e `call_mcp`, cada capacidade nova tendendo a virar um nó novo.

## Decisão

Um único ponto de execução de tools despacha por `ToolSpec.kind` (`retrieval` · `mcp` · `native`). Retrievers são expostos ao controller como tools.

## Consequências

- Adicionar capacidade nunca exige nó novo — só entrada no catálogo
- É a peça que torna a composição de packs uma união de conjuntos
- Timeout, limite de resposta, auditoria e fencing ficam num lugar só
- Custo: o `ToolSpec` carrega mais responsabilidade
- Nota de modularidade (2026-09-10): a lógica de despacho mora no *Capability Gateway* (spec 004), não no grafo; o grafo apenas chama o gateway. Isso mantém a reescrita do grafo independente da segurança de tools.
