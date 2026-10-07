# Contrato — repositório de instalação `agentic-deploy` (Fase 4, US5)

Decisões em [research.md](../research.md) R21–R29; [ADR-009](../../../docs/adr/ADR-009-deploy-docker-build-arg.md) e
[ADR-022](../../../docs/adr/ADR-022-instalacao-constroi-o-core-num-estagio-proprio.md). Repositório privado
`CaioFerreiraB/agentic-deploy`, submódulo `agentic-deploy/` do `agentic-app`.

## Build-args

| Arg | Default | Significado |
|---|---|---|
| `CORE_REF` | `v0.1.0` | tag (ou branch) do `agentic-app` de onde vêm `ai-core-contracts`, `ai-core` e `ai-generic` — clone raso, sem submódulos |
| `CORE_REPO` | `ssh://git@github.com/CaioFerreiraB/agentic-app.git` | repositório do core |
| `PACKS` | `ai-scouting @ git+ssh://git@github.com/CaioFerreiraB/ai-scouting.git@329d592010a74eaaa0cc113ef2f717905455be8f` | requisitos dos packs, separados por espaço (PyPI, URL de git ou caminho em `/build/packages`) |

Identidades SSH do BuildKit: `core` (lê `CORE_REPO`) e `packs` (lê os repositórios dos packs).

## Estágios

| Estágio | Conteúdo | Falha quando |
|---|---|---|
| `core` | `/opt/ai-core` com os contratos, o core e o `ai-generic` da tag | a tag ou o acesso ao `agentic-app` faltam |
| `packs` | `core` + packs + `/etc/ai-core/packs.yaml`; `ai-core packs check` | um pack não instala, ou `packs check` sai ≠ 0 (pack em erro → 1; `packs.yaml` inválido → 2) |
| `runtime` | o ambiente e o `packs.yaml` do `packs`, sem `uv`, `pip` nem `ensurepip`; usuário `ai-core` (uid 10001) sem escrita em `/opt/ai-core`; `CMD ["ai-core", "serve"]` | — |

## Ambiente do runtime

| Variável | Valor | Origem |
|---|---|---|
| `AI_CORE_HOST` | `0.0.0.0` | imagem |
| `AI_CORE_PACKS_FILE` | `/etc/ai-core/packs.yaml` (na imagem) | imagem |
| `AI_CORE_ASSISTANTS_FILE` | `/etc/ai-core/assistants.yaml` (montado, somente leitura) | imagem |
| perfil, chaves, OIDC, provedores | — | `.env` (fora do git; modelo em `.env.example`) |

## `scripts/check-build.sh` (o *Independent Test*)

| Passo | Esperado |
|---|---|
| build do `runtime` com o `PACKS` default | sucesso (US5 cen. 1) |
| `ai-core packs list` na imagem | `generic` e `scouting` `enabled` |
| `ai-core assistants validate` com `config/assistants.yaml` | sai com 0 |
| `uv`, `pip`, `python -m ensurepip` na imagem; escrita em `/opt/ai-core` como o usuário do processo | ausentes / recusada (US5 cen. 3) |
| build do `packs` com `PACKS=/build/packages/incompatible-pack` | falha no `packs check`, saída nomeando `incompatible` (US5 cen. 2) |

Sai com 0 só se todos valem. `SSH_CORE` e `SSH_PACKS` escolhem a origem de cada identidade (default: o agente SSH).

## CI (`.github/workflows/build.yml`)

Push e PR: deploy keys só de leitura nos segredos `AGENTIC_APP_DEPLOY_KEY` (cadastrada no `agentic-app`) e
`AI_SCOUTING_DEPLOY_KEY` (no `ai-scouting`), gravadas em arquivo e passadas por `SSH_CORE`/`SSH_PACKS`;
`scripts/check-build.sh` em `linux/amd64`.
