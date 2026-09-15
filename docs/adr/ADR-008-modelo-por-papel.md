# ADR-008 — Modelo por papel

- **Status:** Aceita · 2026-09-10
- **Specs afetadas:** [006-core-llm-providers](../../specs/006-core-llm-providers/spec.md), [003-core-assistants-access](../../specs/003-core-assistants-access/spec.md)
- **Origem:** arch-v1 Parte VIII

## Contexto

O desenho original fixava um provider e um modelo por requisição, usados para tudo.

## Decisão

O Assistant declara modelo por papel: `controller`, `generation` e opcionalmente `rerank`, com allowlist de providers.

## Consequências

- Controller pode usar modelo forte remoto (poucos tokens, alto valor) e geração usar modelo local
- Torna viável o loop agêntico em hardware modesto
- Custo: uma dimensão a mais na configuração
