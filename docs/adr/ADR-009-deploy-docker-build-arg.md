# ADR-009 — Deploy por imagem Docker com build-arg

- **Status:** Aceita · 2026-09-10
- **Specs afetadas:** [002-core-pack-runtime](../../specs/002-core-pack-runtime/spec.md)
- **Origem:** arch-v1 Parte VIII

## Contexto

O operador precisa escolher quais packs, vindos de repositórios separados, compõem a instalação.

## Decisão

Repositório de deployment próprio, com Dockerfile que recebe a lista de packs por build-arg e roda `ai-core packs check` no build.

## Consequências

- Instalação imutável e reproduzível; sem venv gravável em runtime
- Incompatibilidade de contrato falha o build, não a produção
- Packs vêm de PyPI ou de URL de git, com packaging Python padrão
- Adicionar pack é uma linha mais rebuild
- Custo: adicionar pack exige rebuild — aceitável, e é o que garante reprodutibilidade
