# ADR-007 — Verificação mecânica de citação em vez de LLM judge online

- **Status:** Aceita · 2026-09-10
- **Specs afetadas:** [104-scouting-citations](../../specs/104-scouting-citations/spec.md), [005-core-execution-engine](../../specs/005-core-execution-engine/spec.md), [009-core-observability-evaluation](../../specs/009-core-observability-evaluation/spec.md)
- **Origem:** arch-v1 Parte VIII

## Contexto

`validate_answer` estava especificado sem definir o que valida.

## Decisão

`validate_answer` é determinístico. A checagem central: toda citação emitida deve mapear para um `chunk_id` presente no contexto daquela geração. Citação não resolvível é removida e registrada. Julgamento por LLM fica no harness offline.

## Consequências

- Custo zero de tokens, latência desprezível
- Elimina a maior parte da alucinação de citação — o modo de falha mais grave do domínio, porque citação inventada é convincente
- Evita usar um modelo de 1.7B como juiz, o que seria ruído
- Custo: não detecta resposta que distorce um trecho realmente citado — coberto pela métrica de fidelidade no harness offline
