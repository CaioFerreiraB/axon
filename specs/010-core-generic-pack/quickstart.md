# Quickstart — validar o `ai-generic` (Fase 1, US1)

Roteiro executável que prova a US1 inteira. Todos os comandos rodam a partir de `ai-core/`. Nesta máquina, use
`XDG_DATA_HOME=$HOME/.local/share` no `uv` (ver CLAUDE.md).

## 1. Workspace reconhece a distribuição nova

```bash
uv sync
uv run python -c "import ai_generic, importlib.metadata as m; print(m.version('ai-generic'))"
```

**Esperado**: `0.1.0`. O `uv sync` acrescenta `ai-generic` ao `uv.lock` como membro do workspace, sem mudança em
`members` ([research.md](research.md) R1).

## 2. O pack conforma ao contrato 001

```bash
uv run pytest packages/generic/tests -q
```

**Esperado**: tudo verde, incluindo `test_conformance.py`, que roda `assert_pack_conforms` com as nove etapas — forma,
identidade, manifest, catálogo, `prepare_context`, validators, imports e distribuição. Se a faixa de
`ai-core-contracts` no `pyproject.toml` do pack estiver errada, esta é a etapa que falha, com
`distribution.range_too_wide` ou `distribution.direct_reference`
([contracts/packaging.md](contracts/packaging.md)).

## 3. O entry point é descoberto e o pack carrega pelo Pack Runtime

```bash
uv run pytest packages/core/tests/packs/integration/test_packs_generic_entry_point.py -q
```

**Esperado**: verde. O teste usa `EntryPointPackSource` (sem distribuição falsa) e o `packs.yaml` mínimo
(`enabled: true`), e confere a entrada no registry conforme a tabela final de [data-model.md](data-model.md): status
`enabled`, `version` `0.1.0`, `contract_version` `0.1`, uma tool `calculate`, um validator `non_empty_answer`, nenhum
retriever, `preferred_flow` ausente. Nenhum caso especial no código do core (SC-002).

Inspeção manual equivalente, útil para depurar:

```bash
uv run python - <<'PY'
from importlib.metadata import entry_points
for ep in entry_points(group="ai_core.packs"):
    print(ep.name, "->", ep.value, "|", ep.dist.name, ep.dist.version)
PY
```

**Esperado**: uma linha `generic -> ai_generic.pack:GenericPack | ai-generic 0.1.0` (as distribuições falsas dos testes
da 002 não aparecem: elas só existem dentro de `tmp_path`).

## 4. A tool recusa o que não é aritmética

```bash
uv run python - <<'PY'
import asyncio
from ai_core_contracts.testing import pack_context, tool_invocation
from ai_generic.pack import GenericPack

[tool] = GenericPack().tools(pack_context("generic"))
for expression in ["2 + 3 * 4", "10 / 4", "7 // 2", "2 ** 10", "1/0", "__import__('os').system('id')",
                   "open('/etc/passwd').read()", "(1).__class__", "2 ** 10**9", "1 +", "1e308 * 10"]:
    print(repr(expression), "->", asyncio.run(tool.handler(tool_invocation({"expression": expression}))))
PY
```

**Esperado**: as quatro primeiras devolvem `result` (`14`, `2.5`, `3`, `1024`); `1/0` devolve
`{"error": "divisão por zero"}`; as três seguintes, `expressão inválida: só aritmética com números é permitida`;
`2 ** 10**9`, `expoente fora do limite`; `1 +`, `expressão inválida`; `1e308 * 10`, `resultado fora do domínio`.
Nenhuma linha levanta exceção e nenhuma executa o que foi pedido ([research.md](research.md) R6, limites em
[data-model.md](data-model.md)).

## 5. Ambiente só com os contratos (Independent Test da US1)

```bash
tmp=$(mktemp -d)
uv venv --python 3.12 "$tmp/venv"
uv pip install --python "$tmp/venv/bin/python" ./packages/contracts ./packages/generic pytest
uv pip freeze --python "$tmp/venv/bin/python"
"$tmp/venv/bin/python" -m pytest -q -p no:cacheprovider packages/generic/tests
rm -rf "$tmp"
```

**Esperado**: o `freeze` lista exatamente `ai-core-contracts`, `ai-generic` e `typing-extensions` — nada do core — e a
suíte do pack passa em Python 3.12, sem `pytest-asyncio` ([research.md](research.md) R3, R4).

## 6. Fronteiras, tipos e formatação

```bash
uv run lint-imports
uv run mypy
uv run ruff check packages/generic && uv run ruff format --check packages/generic
```

**Esperado**: `lint-imports` lista os três contratos novos como `KEPT` (pack não importa core, core não importa pack,
pack não importa frameworks — SC-001 nas duas direções); mypy strict sem erro em `packages/generic/src`; ruff limpo.

## 7. A suíte completa do workspace continua verde

```bash
uv run pytest
```

**Esperado**: contratos (001), core (002) e pack (010) verdes na mesma execução.
