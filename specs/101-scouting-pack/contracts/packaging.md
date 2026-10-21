# Contrato — distribuição `axon-scouting`

Decisões em [research.md](../research.md) R1–R3, R9, R14. Repositório privado `CaioFerreiraB/axon-scouting`, ligado no
`axon` como submódulo `axon-scouting/` (ADR-021).

## `pyproject.toml`

```toml
[project]
name = "axon-scouting"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["axon-ai-contracts>=0.1,<0.2"]   # nunca axon-ai em runtime (FR-001)

[project.entry-points."axon.packs"]
scouting = "axon_scouting.pack:ScoutingPack"

[dependency-groups]
dev = ["pytest", "mypy", "ruff", "import-linter"]
platform = ["axon-ai ; python_version >= '3.14'"]   # só a integração (R9)

[tool.uv]
default-groups = ["dev"]

[tool.uv.sources]
axon-ai-contracts = { git = "ssh://git@github.com/CaioFerreiraB/axon.git", tag = "contracts-v0.1.0", subdirectory = "axon-ai/packages/contracts" }
axon-ai = { git = "ssh://git@github.com/CaioFerreiraB/axon.git", tag = "contracts-v0.1.0", subdirectory = "axon-ai/packages/core" }
```

Build backend `uv_build`, como o `axon-generic`; `uv.lock` versionado; `py.typed` no pacote. Ruff (`py312`, linha 120,
regras `E F I UP B SIM RUF`) e mypy strict sobre `src`, como no workspace do core; pytest sem `pytest-asyncio`
(hooks assíncronos rodam com `asyncio.run`, como no `axon-generic`).

## import-linter (no próprio `pyproject.toml`)

| Contrato | Tipo | Regra |
|---|---|---|
| o pack não importa o core | `forbidden` | `axon_scouting` ↛ `axon_ai`, `axon_generic` |
| só o `pack.py` compõe | `layers` | `axon_scouting.pack` acima de `axon_scouting.context \| axon_scouting.prompts` (independentes) |
| a derivação não alcança modelo nem MCP | `forbidden` | `axon_scouting.context` ↛ `axon_ai_contracts.llm`, `axon_ai_contracts.mcp` — imports diretos (`allow_indirect_imports`: o `__init__` dos contratos reexporta tudo) |

## CI (`.github/workflows/ci.yml` no `axon-scouting`)

| Job | Python | O que roda |
|---|---|---|
| `lint` | 3.14 | `uv sync --locked`; `ruff check`, `ruff format --check`, `mypy` (strict, sobre `src`), `lint-imports` |
| `test` | 3.12, 3.14 | `uv sync --locked`; `pytest` (a integração é pulada sem o core) |
| `clean-env` | 3.12 | instalação normal do pack só com os contratos; `pytest tests --ignore=tests/integration` (a etapa de distribuição confere a faixa) |
| `platform` | 3.14 | `uv sync --locked --group platform`; `pytest tests/integration` |

Acesso ao `axon` (privado): deploy key **só de leitura** cadastrada no `axon`; a chave privada fica no
segredo `AGENTIC_APP_DEPLOY_KEY` do `axon-scouting` e é carregada por `webfactory/ssh-agent` antes do `uv sync`.

## Fluxo de commit

Código e testes do pack: commit no `axon-scouting`. No `axon`: o SDD da passada e o novo ponteiro do submódulo
(`git add axon-scouting`), no mesmo commit de fechamento.

## Fase 5 (2026-10-09)

- `version = "0.2.0"`; dependências de runtime da 102 e da 103 já presentes; nenhuma nova.
- `[tool.uv.sources]`: `axon-ai-contracts` e `axon-ai` (grupo `platform`) pela mesma tag, `v0.2.0` (a do core com o
  `rag_first`, criada ao fim da 005 US3–US4); nela os contratos são os `0.1.1` da `contracts-v0.1.1` (R22, nota).
- O job `platform` roda também `tests/integration/test_rag.py` (US5 ponta a ponta, sem rede: Qdrant embutido e o
  embedder de teste).
- A partir da `v0.2.0` o `axon` tem os submódulos `ai-scouting` e `agentic-deploy` (nomes do `.gitmodules`), que o
  `uv` inicializa ao clonar a tag e que a deploy key não lê: cada job do `ci.yml` marca os dois com `git config --global
  submodule.<nome>.update none` antes de resolver as dependências (o pacote não precisa deles).

## Fase 9 (2026-10-20)

Identidade Axon (US6, research R25–R28; ADR-037):

- `name = "axon-scouting"`, `version = "0.4.0"`; `dependencies` com `axon-ai-contracts>=0.2,<0.3`; `contract_version`
  "0.2" no pack.
- `[project.entry-points."axon.packs"]` com `scouting = "axon_scouting.pack:ScoutingPack"` (o nome do pack não muda);
  `[project.scripts]` com `axon-scouting-corpus = "axon_scouting.pack:corpus_cli"`.
- `[tool.uv.sources]`: `axon-ai-contracts` e `axon-ai` (grupo `platform`) de `ssh://git@github.com/CaioFerreiraB/axon.git`,
  tag `v0.7.0-rc1`, subdiretórios `axon-ai/packages/contracts` e `axon-ai/packages/core`.
- import-linter com `axon_scouting` ↛ `axon_ai`, `axon_generic`, e as demais regras sobre `axon_scouting.*` e
  `axon_ai_contracts.*`.
- A CI e o `eval.yml` usam `AXON_SCOUTING_*`, `AXON_PROFILE`, `AXON_PACKS_FILE`, `AXON_ASSISTANTS_FILE`, `axon eval run`
  e `axon-scouting-corpus`. O segredo continua `AGENTIC_APP_DEPLOY_KEY`, e os submódulos da tag `v0.7.0-rc1` ainda se
  chamam `ai-scouting` e `agentic-deploy`, então o `update = none` segue com esses nomes até a tag seguinte.
