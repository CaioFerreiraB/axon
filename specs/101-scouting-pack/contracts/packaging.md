# Contrato — distribuição `ai-scouting`

Decisões em [research.md](../research.md) R1–R3, R9, R14. Repositório privado `CaioFerreiraB/ai-scouting`, ligado no
`agentic-app` como submódulo `ai-scouting/` (ADR-021).

## `pyproject.toml`

```toml
[project]
name = "ai-scouting"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["ai-core-contracts>=0.1,<0.2"]   # nunca ai-core em runtime (FR-001)

[project.entry-points."ai_core.packs"]
scouting = "ai_scouting.pack:ScoutingPack"

[dependency-groups]
dev = ["pytest", "mypy", "ruff", "import-linter"]
platform = ["ai-core ; python_version >= '3.14'"]   # só a integração (R9)

[tool.uv]
default-groups = ["dev"]

[tool.uv.sources]
ai-core-contracts = { git = "ssh://git@github.com/CaioFerreiraB/agentic-app.git", tag = "contracts-v0.1.0", subdirectory = "ai-core/packages/contracts" }
ai-core = { git = "ssh://git@github.com/CaioFerreiraB/agentic-app.git", tag = "contracts-v0.1.0", subdirectory = "ai-core/packages/core" }
```

Build backend `uv_build`, como o `ai-generic`; `uv.lock` versionado; `py.typed` no pacote. Ruff (`py312`, linha 120,
regras `E F I UP B SIM RUF`) e mypy strict sobre `src`, como no workspace do core; pytest sem `pytest-asyncio`
(hooks assíncronos rodam com `asyncio.run`, como no `ai-generic`).

## import-linter (no próprio `pyproject.toml`)

| Contrato | Tipo | Regra |
|---|---|---|
| o pack não importa o core | `forbidden` | `ai_scouting` ↛ `ai_core`, `ai_generic` |
| só o `pack.py` compõe | `layers` | `ai_scouting.pack` acima de `ai_scouting.context \| ai_scouting.prompts` (independentes) |
| a derivação não alcança modelo nem MCP | `forbidden` | `ai_scouting.context` ↛ `ai_core_contracts.llm`, `ai_core_contracts.mcp` — imports diretos (`allow_indirect_imports`: o `__init__` dos contratos reexporta tudo) |

## CI (`.github/workflows/ci.yml` no `ai-scouting`)

| Job | Python | O que roda |
|---|---|---|
| `lint` | 3.14 | `uv sync --locked`; `ruff check`, `ruff format --check`, `mypy` (strict, sobre `src`), `lint-imports` |
| `test` | 3.12, 3.14 | `uv sync --locked`; `pytest` (a integração é pulada sem o core) |
| `clean-env` | 3.12 | instalação normal do pack só com os contratos; `pytest tests --ignore=tests/integration` (a etapa de distribuição confere a faixa) |
| `platform` | 3.14 | `uv sync --locked --group platform`; `pytest tests/integration` |

Acesso ao `agentic-app` (privado): deploy key **só de leitura** cadastrada no `agentic-app`; a chave privada fica no
segredo `AGENTIC_APP_DEPLOY_KEY` do `ai-scouting` e é carregada por `webfactory/ssh-agent` antes do `uv sync`.

## Fluxo de commit

Código e testes do pack: commit no `ai-scouting`. No `agentic-app`: o SDD da passada e o novo ponteiro do submódulo
(`git add ai-scouting`), no mesmo commit de fechamento.

## Fase 5 (2026-10-09)

- `version = "0.2.0"`; dependências de runtime da 102 e da 103 já presentes; nenhuma nova.
- `[tool.uv.sources]`: `ai-core-contracts` e `ai-core` (grupo `platform`) pela mesma tag, `v0.2.0` (a do core com o
  `rag_first`, criada ao fim da 005 US3–US4); nela os contratos são os `0.1.1` da `contracts-v0.1.1` (R22, nota).
- O job `platform` roda também `tests/integration/test_rag.py` (US5 ponta a ponta, sem rede: Qdrant embutido e o
  embedder de teste).
- A partir da `v0.2.0` o `agentic-app` tem os submódulos `ai-scouting` e `agentic-deploy`, que o `uv` inicializa ao
  clonar a tag e que a deploy key não lê: cada job do `ci.yml` marca os dois com `git config --global
  submodule.<nome>.update none` antes de resolver as dependências (o pacote não precisa deles).
