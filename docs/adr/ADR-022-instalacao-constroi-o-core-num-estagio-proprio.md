# ADR-022 — A instalação constrói o core num estágio do próprio Dockerfile

- **Status:** Aceita · 2026-10-07
- **Specs afetadas:** [002-core-pack-runtime](../../specs/002-core-pack-runtime/spec.md) (US5, FR-013; supera a imagem
  base publicada do design.md, seção "Deployment")
- **Origem:** clarificação de 2026-10-07 da 002 (preparação da US5, Fase 4); ADR-009 e ADR-021

## Contexto

O ADR-009 decidiu: repositório de deployment próprio, com Dockerfile que recebe a lista de packs por build-arg e roda
`ai-core packs check` no build. O design.md da 002 ilustrou isso com `FROM ghcr.io/caio/ai-core:0.3.1` — uma imagem do
core publicada em registry. Nenhuma spec constrói nem publica essa imagem, o core ainda não tinha tag de release, e o
`agentic-app` é privado (ADR-021).

## Decisão

O Dockerfile do repositório de instalação (`agentic-deploy`) tem três estágios:

1. **`core`**: a partir de `python:3.14-slim`, instala `ai-core-contracts`, `ai-core` e `ai-generic` de uma tag de
   release do `agentic-app` (`v0.1.0` na primeira), num ambiente virtual em `/opt/ai-core`;
2. **`packs`**: sobre o `core`, instala os packs do build-arg `PACKS` no mesmo ambiente e roda `ai-core packs check`
   com o `packs.yaml` da instalação — incompatibilidade falha o build;
3. **`runtime`**: a mesma base, com o ambiente copiado do estágio `packs`, sem `uv` e sem `pip`, como usuário sem
   permissão de escrita no ambiente.

O código privado é baixado por montagens SSH do BuildKit (`RUN --mount=type=ssh`), uma identidade por origem (`core`,
`packs`): nenhuma credencial fica em camada da imagem. Imagem do core publicada em registry fica para quando houver
mais de uma instalação.

## Alternativas rejeitadas

*Imagem do core publicada no GHCR (o exemplo do design.md).* Exigiria Dockerfile e pipeline de release no
`agentic-app`, registry privado e credencial de pull em cada instalação — custo sem consumidor, com uma instalação só.

*Instalar tudo num estágio só.* O ambiente final carregaria `uv`, cliente SSH e git, que só o build usa, e o pacote de
instalação continuaria disponível em runtime (contra a FR-014).

## Consequências

- Uma instalação reproduzível a partir de duas referências: a tag do `agentic-app` e a referência de cada pack
- O primeiro build de cada versão do core é mais lento (instala o core); o cache do BuildKit cobre os seguintes
- Quem builda precisa de leitura no `agentic-app` e nos repositórios dos packs: a chave SSH do operador localmente,
  deploy keys só de leitura na CI
- Quando houver mais de uma instalação, o estágio `core` vira a imagem publicada do design.md, e este ADR é substituído
