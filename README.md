<p>
  <picture>
    <source media="(prefers-color-scheme: dark)" srcset="brand-kit/svg/axon-lockup-dark.svg">
    <img src="brand-kit/svg/axon-lockup-light.svg" alt="Axon" height="56">
  </picture>
</p>

**Design. Connect. Build.**

[![core](https://github.com/CaioFerreiraB/axon/actions/workflows/core.yml/badge.svg?branch=main)](https://github.com/CaioFerreiraB/axon/actions/workflows/core.yml) [![contracts](https://github.com/CaioFerreiraB/axon/actions/workflows/contracts.yml/badge.svg?branch=main)](https://github.com/CaioFerreiraB/axon/actions/workflows/contracts.yml) [![generic](https://github.com/CaioFerreiraB/axon/actions/workflows/generic.yml/badge.svg?branch=main)](https://github.com/CaioFerreiraB/axon/actions/workflows/generic.yml) [![console](https://github.com/CaioFerreiraB/axon/actions/workflows/console.yml/badge.svg?branch=main)](https://github.com/CaioFerreiraB/axon/actions/workflows/console.yml)

![axon-ai](https://img.shields.io/badge/axon--ai-0.7.0rc3-2563EB?style=flat) ![axon-ai-contracts](https://img.shields.io/badge/axon--ai--contracts-0.2.0-2563EB?style=flat) ![axon-generic](https://img.shields.io/badge/axon--generic-0.2.0-2563EB?style=flat) ![Python](https://img.shields.io/badge/Python-3.14_·_contratos_3.12%2B-3776AB?style=flat&logo=python&logoColor=white) ![Node](https://img.shields.io/badge/Node-24-5FA04E?style=flat&logo=nodedotjs&logoColor=white) ![spec-kit](https://img.shields.io/badge/spec--kit-1.0.6-475569?style=flat)

Axon é um ambiente open source para projetar, conectar e executar sistemas agênticos.

*Axon is an open-source workspace to design, connect, and run agentic systems.*

## Repositórios

| Repositório | O que tem | Aqui |
|---|---|---|
| `axon` (este) | O SDD da plataforma (constituição, specs, ADRs, roadmap) e o código do core: contratos `axon-ai-contracts`, runtime `axon-ai` (comando `axon`), pack de referência `axon-generic` e a console de administração | `axon-ai/`, `specs/`, `docs/` |
| `axon-scouting` [![ci](https://github.com/CaioFerreiraB/axon-scouting/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/CaioFerreiraB/axon-scouting/actions/workflows/ci.yml) [![eval](https://github.com/CaioFerreiraB/axon-scouting/actions/workflows/eval.yml/badge.svg?branch=main)](https://github.com/CaioFerreiraB/axon-scouting/actions/workflows/eval.yml) | O pack de domínio escoteiro: contexto, recuperação com vigência e citação verificada, avaliação | submódulo `axon-scouting/` |
| `axon-deploy` [![build](https://github.com/CaioFerreiraB/axon-deploy/actions/workflows/build.yml/badge.svg?branch=main)](https://github.com/CaioFerreiraB/axon-deploy/actions/workflows/build.yml) | A instalação de referência: imagem com o core de uma tag e os packs, compose com Postgres, Qdrant, Open WebUI e a console | submódulo `axon-deploy/` |

O core não conhece domínio nenhum: um pack se anuncia no grupo de entry point `axon.packs` e depende só dos contratos.

## Por onde começar

- [`CLAUDE.md`](CLAUDE.md): as regras de trabalho no repositório, o estado de cada fase e os comandos de verificação.
- [`specs/README.md`](specs/README.md): o mapa de módulos, seams e dependências.
- [`docs/roadmap.md`](docs/roadmap.md): as fases e o andamento.
- [`docs/adr/`](docs/adr/): as decisões de arquitetura; os nomes da plataforma estão no
  [ADR-037](docs/adr/ADR-037-a-plataforma-se-chama-axon.md) e a marca no
  [ADR-038](docs/adr/ADR-038-marca-da-plataforma-e-marca-da-instalacao.md).
- [`brand-kit/`](brand-kit/BRAND.md): símbolo, lockups, tokens e voz da marca.

```bash
git clone --recurse-submodules git@github.com:CaioFerreiraB/axon.git
cd axon/axon-ai && uv sync && uv run pytest
```
