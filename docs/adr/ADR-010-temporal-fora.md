# ADR-010 — Temporal fora da arquitetura

- **Status:** Aceita · 2026-09-10
- **Specs afetadas:** [005-core-execution-engine](../../specs/005-core-execution-engine/spec.md)
- **Origem:** arch-v1 Parte VIII

## Contexto

Uma versão inicial previa Temporal para orquestração durável.

## Decisão

Removido. Não há workflows de longa duração. O checkpointer do LangGraph cobre estado de execução.

## Consequências

Menos um serviço na VM de 12 GB. Se surgir ingestão de longa duração, avaliar fila simples antes de motor de workflow.
