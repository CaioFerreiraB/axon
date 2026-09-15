# ADR-004 — Contratos no repositório do core, packs de domínio separados

- **Status:** Aceita · 2026-09-10
- **Specs afetadas:** [001-core-contracts](../../specs/001-core-contracts/spec.md), [010-core-generic-pack](../../specs/010-core-generic-pack/spec.md), todas as specs `1xx`
- **Origem:** arch-v1 Parte VIII

## Contexto

Packs de domínio precisam de contratos bem definidos para se plugar sem conhecer o core, e de ciclo de release próprio. Ao mesmo tempo, os contratos são mais instáveis justamente nas primeiras fases, e coordenar cada mudança entre vários repositórios custa caro.

## Decisão

O repositório `ai-core` é um uv workspace com três distribuições: `ai-core-contracts` (mínima, só Protocols e tipos, com versão própria), `ai-core` e `ai-generic` (pack de referência). Packs de domínio — `ai-scouting` e os próximos — vivem em repositórios próprios e dependem apenas de `ai-core-contracts`, com faixa semver e janela de depreciação de um minor.

## Alternativas rejeitadas

*Contratos como módulo de `ai-core` (`ai_core.contracts`).* Packs externos passariam a depender de `ai-core` inteiro, arrastando FastAPI, LangGraph e Qdrant, e a versão que fixam seria a do runtime: qualquer breaking change no core, mesmo fora dos contratos, bloquearia os packs pela faixa semver. Manter a distribuição separada dentro do mesmo repositório custa um `pyproject.toml`.

*Quatro repositórios (contracts, core, generic, scouting).* Toda mudança de contrato viraria release em contracts mais bump em três repositórios, justamente nas fases em que os contratos mais mudam. Contratos e pack genérico não têm dono nem ciclo de release diferentes dos do core; separá-los não compra nada.

*Monorepo com todos os packs.* Packs de domínio têm ciclo de release próprio e podem ter donos diferentes; morar no repositório do core amarraria o release deles ao do core.

## Consequências

- Mudança de contrato é um PR atômico no `ai-core`; packs externos adotam dentro da janela de depreciação
- `ai-core` lança versões sem forçar release nos packs externos, porque a faixa deles aponta para a versão dos contratos
- `ai-generic` tem o formato de um pack externo e serve de referência e de fixture do carregamento por entry point
- A independência é verificada por import-linter no CI do `ai-core` e de cada pack externo
- Custo: o repositório `ai-core` mantém duas linhas de versão (contratos e core); e, dentro do workspace, a fronteira entre `ai-generic` e o core depende de lint, não de separação física
