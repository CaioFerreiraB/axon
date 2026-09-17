# Quickstart — validar o Pack Runtime (Fase 1: US1, US2, US3 cenários 2–4)

Referências: [pack-runtime-api.md](contracts/pack-runtime-api.md), [ports.md](contracts/ports.md),
[packs-yaml.md](contracts/packs-yaml.md), [data-model.md](data-model.md).

## Pré-requisitos

- Workspace `ai-core/` sincronizado (`uv sync`), com `ai-core-contracts` 0.1.0 (spec 001)
- Nesta máquina: `export XDG_DATA_HOME=$HOME/.local/share`

```bash
cd ai-core
uv sync
```

## 1. Suíte do módulo

```bash
uv run pytest packages/core/tests/packs -q
uv run mypy
uv run ruff check packages/core && uv run lint-imports
```

**Esperado**: tudo verde; `lint-imports` mantém os contratos novos (camadas de `ai_core.packs`, contratos sem `ai_core`).

## 2. Portas (conformidade)

```bash
uv run pytest packages/core/tests/packs/contract/test_packs_source_port.py packages/core/tests/packs/contract/test_packs_config_port.py -v
```

**Esperado**: a mesma suíte passa contra o adapter em memória e contra o real — entry points de distribuições falsas
criadas em `tmp_path` e arquivos `packs.yaml` temporários.

## 3. Descoberta e carga (US1)

`packages/core/tests/packs/integration/test_packs_entry_points_load.py` cria distribuições falsas com o pack de teste
`good` e roda a carga completa com `EntryPointPackSource` e `YamlPackConfigSource`:

| Configuração | Esperado em `entries()` |
|---|---|
| `good: {enabled: true}` | `good` `enabled`, versão da distribuição, `contract_version` `0.1`, capacidades preenchidas (cenário 1) |
| `good` ausente ou `enabled: false` | `good` `disabled`, sem ser instanciado — construtor com contador continua em zero (cenário 2) |
| `config` fora do `config_schema` | `good` `error` com `configuração inválida em '<campo>'` (cenário 3) |

## 4. Falha fechada (US2, SC-002)

```bash
uv run pytest packages/core/tests/packs/unit/test_packs_failure_matrix.py -v
```

**Esperado** — com o pack `good` sempre presente e `enabled`, cada defeito injetado deixa só o pack defeituoso em
`error`, com a mensagem da tabela do data-model:

| Defeito | Mensagem começa com |
|---|---|
| `contract_version = "0.2"` | `requer ai-core-contracts>=0.2, instalado 0.1.0` |
| manifest com nome diferente | `manifest inválido:` |
| exceção no construtor | `falha ao instanciar:` |
| exceção em `tools()` | `hook tools levantou` |
| entry point com nome diferente do `name` | `entry point '...' aponta para classe com name` |
| dois packs com o mesmo nome | `nome duplicado:` (os dois em erro) |
| `depends_on` para pack desabilitado | `depende de '...', que está desabilitado` |
| ciclo `a → b → a` | `dependência circular:` |
| habilitado na configuração e não instalado | `não instalado` |

`compose(["good", "quebrado"])` levanta `CompositionError` que nomeia `quebrado` e repete seu erro (US2 cenário 3).

## 5. Pack Hooks (US3 cenários 2–4)

```bash
uv run pytest packages/core/tests/packs/contract/test_packs_hooks_seam.py -v
```

**Esperado**:

- `system_prompts(compose(["a", "b"]))` devolve o fragmento de A antes do de B (cenário 2);
- `prepare` com B dependente de A: B recebe em `dependency_slices["a"]` o que A acabou de escrever; nenhum pack vê fatia
  fora do `depends_on`; o retorno entra por merge raso;
- `compose(["b", "a"])` (dependente antes) e `compose(["b"])` (dependência ausente) levantam `CompositionError`
  nomeando A e B;
- hook que lê `view.dependency_slices["c"]` sem declarar → `PackHookError(pack="b", hook="prepare_context")`
  (cenário 3); `prepare_context` que levanta ou devolve valor não-JSON → `PackHookError` (cenário 4);
- `validate`: o segundo validator recebe a resposta alterada pelo primeiro; o `ValidationOutcome` traz resposta final,
  citações, união das flags e uma `ValidatorRun` por validator; validator que levanta → `PackHookError`.

## 6. Contratos dos testes de piso (consequência de R3)

```bash
uv run --no-project --python 3.12 --with ./packages/contracts --with pytest --with pytest-asyncio \
  --with hypothesis --with packaging pytest packages/contracts/tests -q
```

**Esperado**: a suíte dos contratos continua passando em 3.12, fora do workspace (que agora exige 3.14).
