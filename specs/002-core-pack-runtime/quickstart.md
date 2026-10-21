# Quickstart — validar o Pack Runtime (Fase 1: US1, US2, US3 cenários 2–4)

Referências: [pack-runtime-api.md](contracts/pack-runtime-api.md), [ports.md](contracts/ports.md),
[packs-yaml.md](contracts/packs-yaml.md), [data-model.md](data-model.md).

## Pré-requisitos

- Workspace `axon-ai/` sincronizado (`uv sync`), com `axon-ai-contracts` 0.1.0 (spec 001)
- Nesta máquina: `export XDG_DATA_HOME=$HOME/.local/share`

```bash
cd axon-ai
uv sync
```

## 1. Suíte do módulo

```bash
uv run pytest packages/core/tests/packs -q
uv run mypy
uv run ruff check packages/core && uv run lint-imports
```

**Esperado**: tudo verde; `lint-imports` mantém os contratos novos (camadas de `axon_ai.packs`, contratos sem `axon_ai`).

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
| `contract_version = "0.2"` | `requer axon-ai-contracts>=0.2, instalado 0.1.0` |
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

## 7. CLI de packs (US4, Fase 2)

```bash
uv run pytest packages/core/tests/packs/integration/test_packs_cli.py -v
```

Esperado: `list` mostra nome, versão, versão de contrato e status de cada pack e sai com 0; `check` sai com 1 e nomeia a
incompatibilidade quando há um pack incompatível instalado, mesmo desabilitado, e com 0 quando todos estão bons;
`packs.yaml` malformado sai com 2 ([contracts/cli.md](contracts/cli.md)). Rodar os comandos pela raiz `axon` depende
do registro pela 011 (US4).

## 8. Build da instalação (US5, Fase 4)

Dentro de `agentic-deploy/` (submódulo, que passa a `axon-deploy/` no fechamento do renome; `git submodule update
--init agentic-deploy`), com o agente SSH carregando uma chave que lê o `axon` e o `axon-scouting`. Contrato em [contracts/installation.md](contracts/installation.md).

```bash
scripts/check-build.sh
```

**Esperado**: o build com o `axon-scouting` conclui; na imagem, `generic` e `scouting` aparecem `enabled`, o
`assistants validate` passa, não há `uv`, `pip` nem `ensurepip`, e o usuário do processo não escreve em `/opt/axon`;
o build com o pack incompatível falha no `packs check`, nomeando `incompatible`. O script sai com 0.

```bash
docker compose up --build        # com .env copiado de .env.example
```

**Esperado**: o serviço sobe com `read_only`, ouvindo em `:8000`; `GET /private/v1/health` com a chave de
desenvolvimento do `.env` responde.


---

## Fase 9, incremento 9.5 (2026-10-20): US8 — grupo `axon.packs`

A partir de `axon-ai/`, com `XDG_DATA_HOME=$HOME/.local/share` nesta máquina. Decisões em [research.md](research.md)
R51–R55.

### Descoberta pelo grupo novo e corte seco (cenários 1 a 4)

```bash
uv run pytest packages/core/tests/packs/integration/test_packs_entry_point_group.py -v
```

**Esperado**: verde — o pack anunciado em `axon.packs` carrega; anunciado só em `ai_core.packs` e habilitado, fica
`error: não instalado` e `packs check` sai com 1 nomeando-o; não habilitado, não aparece.

### O pack de referência no grupo novo (cenário 5)

```bash
uv run python - <<'PY'
from importlib.metadata import entry_points
print([(ep.name, ep.value, ep.dist.name) for ep in entry_points(group="axon.packs")])
print([ep.name for ep in entry_points(group="ai_core.packs")])
PY
AXON_PROFILE=memory AXON_PACKS_FILE=<packs.yaml com generic habilitado> uv run axon packs list
```

**Esperado**: `[('generic', 'axon_generic.pack:GenericPack', 'axon-generic')]` e `[]` (nenhum pack do workspace no
grupo antigo); a lista mostra `generic  0.2.0  0.2  enabled`.

### Resíduos (SC-008)

```bash
cd .. && git grep -nw "ai_core\.packs" -- . ':!ai-scouting' ':!agentic-deploy' ':!specs/1*' ':!**/research.md' \
  ':!**/plan.md' ':!**/tasks.md' ':!docs' ':!CLAUDE.md' ':!specs/002-core-pack-runtime/contracts/installation.md'
```

**Esperado**: só o teste do corte seco e os textos que nomeiam o grupo antigo de propósito (a US8, as clarificações de
2026-10-20 e os FR-024 e SC-008 da 002, as notas da 010); nenhum `pyproject.toml` nem código de produção.

## Fase 9, incremento 9.5 (2026-10-20): a instalação com os nomes da Axon (US7 cen. 6)

Dentro do submódulo da instalação (o repositório `axon-deploy`; a pasta `agentic-deploy/` até o fechamento do renome),
com o agente SSH lendo o `axon` e o `axon-scouting`. Decisões em [research.md](research.md) R56–R61.

```bash
scripts/check-build.sh                                    # build da v0.7.0-rc1 + axon-scouting 0.4.0, incompatível, recusa
docker compose -p agentic-deploy --profile webui --profile console down
sed -i 's/^AI_SCOUTING_/AXON_SCOUTING_/; s/^AI_CORE_/AXON_/' .env
COMPOSE_PROFILES=webui,console docker compose up -d --build
docker compose ls                                         # o projeto axon
scripts/dev-users.sh
docker compose run --rm -v ../ai-scouting/corpus:/corpus:ro axon axon-scouting-corpus ingest /corpus/corpus.yaml
python3 scripts/check-webui.py
```

**Esperado**: o `check-build.sh` termina em OK, com o passo 3b recusando `AI_CORE_PROFILE → AXON_PROFILE`; o compose
mostra o projeto `axon`; o login do Open WebUI diz "Continuar com Axon"; o `check-webui.py` passa (as listas de `ana` e
`bia`, uma mensagem com 200 e a timeline); a console responde na porta dela.
