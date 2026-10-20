# Contrato — empacotamento do pack de referência

É este arquivo que o `ai-scouting` (Fase 4) e qualquer pack futuro copiam. Cada linha tem um verificador automático.

## `axon-ai/packages/generic/pyproject.toml`

```toml
[project]
name = "axon-generic"
version = "0.2.0"
description = "Pack de referência e de uso geral da plataforma Axon (spec 010)."
readme = "README.md"
requires-python = ">=3.12"                        # piso dos contratos, não o do core (research R3)
dependencies = ["axon-ai-contracts>=0.2,<0.3"]    # faixa derivada da contract_version (ADR-014)

[project.entry-points."ai_core.packs"]
generic = "axon_generic.pack:GenericPack"

[tool.uv.sources]
axon-ai-contracts = { workspace = true }          # commit local enquanto mora no workspace (research R2)

[build-system]
requires = ["uv_build>=0.12,<0.13"]
build-backend = "uv_build"
```

> Passada de 2026-10-20 (US3, ADR-037; research R22, R23): distribuição `axon-generic` 0.2.0, pacote `axon_generic`.
> O grupo `ai_core.packs` é o que o Pack Runtime (002) procura e passa a `axon.packs` na passada dela, junto com o do
> Pack Runtime; o nome do entry point (`generic`) não muda.

| Linha | Verificador |
|---|---|
| `dependencies` com a faixa derivada | etapa de distribuição de `assert_pack_conforms` (001 FR-018): sem faixa → `distribution.range_too_wide`; `@ referência` → `distribution.direct_reference`; ausente → `distribution.missing_requirement` |
| nome do entry point igual a `GenericPack.name` | carga do Pack Runtime (002 FR-017): divergência → `error` com `entry point '<x>' aponta para classe com name '<y>'` |
| dependência só dos contratos | job de ambiente limpo: a resolução tem exatamente `axon-ai-contracts`, `typing-extensions`, `axon-generic` |
| `requires-python = ">=3.12"` | a suíte do pack roda no ambiente limpo em 3.12 |
| `py.typed` no pacote | `mypy --strict` da raiz, com `packages/generic/src` em `files` |

## Mudanças na raiz do workspace (`axon-ai/pyproject.toml`)

| Chave | Mudança | Por quê |
|---|---|---|
| `[tool.uv.workspace] members` | nenhuma | `packages/*` já inclui `packages/generic` (research R1) |
| `[dependency-groups] dev` | `+ "axon-generic"` | o teste de carga real roda na suíte do core (research R8) |
| `[tool.uv.sources]` | `+ axon-generic = { workspace = true }` | resolver a dev-dependency no workspace |
| `[tool.pytest.ini_options] testpaths` | `+ "packages/generic/tests"` | a suíte do pack roda também no workspace (3.14) |
| `[tool.mypy] files` | `+ "packages/generic/src"` | mypy strict no código que serve de exemplo |
| `[tool.ruff.lint.isort] known-first-party` | `+ "axon_generic"` | ordenação de imports consistente |
| `[tool.importlinter] root_packages` | `+ "axon_generic"` | habilita os contratos abaixo |

## Contratos de import-linter (research R9)

```toml
[[tool.importlinter.contracts]]
name = "o pack genérico não importa o core"
type = "forbidden"
source_modules = ["axon_generic"]
forbidden_modules = ["axon_ai"]

[[tool.importlinter.contracts]]
name = "o core não importa o pack genérico"
type = "forbidden"
source_modules = ["axon_ai"]
forbidden_modules = ["axon_generic"]

[[tool.importlinter.contracts]]
name = "o pack genérico não importa frameworks de infraestrutura"
type = "forbidden"
source_modules = ["axon_generic"]
forbidden_modules = ["yaml", "jsonschema", "fastapi", "langgraph", "langchain", "qdrant_client", "sqlalchemy"]
```

As duas primeiras cobrem SC-001 nas duas direções; a terceira mantém o pack dentro de stdlib + contratos. A etapa de
imports da suíte de conformidade (`check_imports`) verifica o mesmo do lado do pack, dentro dos testes dele.

## CI (research R10)

`.github/workflows/generic.yml`, `working-directory: axon-ai`, gatilhos em `axon-ai/packages/generic/**`,
`axon-ai/packages/contracts/**`, `axon-ai/pyproject.toml`, `axon-ai/uv.lock` e no próprio workflow, mais
`workflow_dispatch`:

| Job | Comandos |
|---|---|
| `lint` | `uv sync --locked`; `uv run ruff check packages/generic`; `uv run ruff format --check packages/generic`; `uv run mypy` |
| `test` | `uv sync --locked`; `uv run pytest packages/generic/tests` |
| `clean-env` | venv 3.12 com apenas `packages/contracts`, `packages/generic` e `pytest`; conferir a resolução (três distribuições) e rodar `pytest packages/generic/tests` |
| `boundaries` | `uv sync --locked`; `uv run lint-imports` |

`core.yml` ganha `axon-ai/packages/generic/**` nos gatilhos de `pull_request` e `push`, porque o job `test` dele passa
a carregar o pack.
