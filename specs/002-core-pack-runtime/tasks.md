---

description: "Tarefas da 002 — Pack Runtime: Fase 1 (US1, US2, US3 cenários 2–4) e Fase 2 (US4)"
---

# Tasks: Descoberta, carga e composição de packs

**Input**: Design documents from `/specs/002-core-pack-runtime/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (pack-runtime-api.md, ports.md,
packs-yaml.md), quickstart.md; `ai-core-contracts` 0.1.0 (spec 001) no workspace

**Tests**: incluídos — a spec pede falhas injetadas (SC-002) e composição verificável (SC-005), e a constituição exige
suíte de conformidade dos seams e das portas em todo PR. Dentro de cada user story, os testes vêm antes e falham
primeiro.

**Escopo**: **Fase 1** — US1, US2 e US3 cenários 2–4 (Pack Hooks de execução). Fora desta lista: US3 cenário 1
(catálogo com namespace, Fase 3), US4 (CLI `packs list | check`, Fase 2), US5 (template de instalação, Fase 4), US6
(pack declarativo, P3), `reranker`/`routine` no Pack Hooks (Fase 5 e 001 US5).

**Fase 2 (2026-09-30)**: US4 — `packs list` e `packs check` como funções sobre o registry carregado (Phase 7,
T034–T037; [research.md](research.md) R15–R17). O registro na raiz `ai-core` é da 011 (US4); a introspecção HTTP, da 008
(US5).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Módulo: `ai-core/packages/core/src/ai_core/packs/`; testes: `ai-core/packages/core/tests/packs/`
- Todo módulo Python começa com `from __future__ import annotations`; value objects são
  `@dataclass(frozen=True, slots=True, kw_only=True)`; mensagens em português (formato no data-model.md, "Mensagens de
  erro")
- `ai_core.packs` importa só a API pública de `ai_core_contracts` (nada com prefixo `_`)
- Nomes de arquivo de teste únicos no workspace: prefixo `test_packs_` (o pytest usa import `prepend`, sem `__init__.py`
  nos testes)

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: nascer a distribuição `ai-core` (R2) e manter o CI dos contratos funcionando com o workspace em 3.14 (R3)

- [X] T001 Criar a distribuição em `ai-core/packages/core/`: `pyproject.toml` (`name = "ai-core"`, `version = "0.1.0"`, `requires-python = ">=3.14"`, `dependencies = ["ai-core-contracts", "pyyaml>=6.0.2", "jsonschema>=4.23"]`, `[tool.uv.sources] ai-core-contracts = { workspace = true }`, `[build-system] requires = ["uv_build>=0.12,<0.13"]`, `build-backend = "uv_build"`), `README.md` (uma linha), `src/ai_core/__init__.py` (docstring), `src/ai_core/py.typed` vazio, `src/ai_core/packs/__init__.py` (docstring: consumidores importam `ai_core.packs.api`), `src/ai_core/packs/domain/__init__.py` e `src/ai_core/packs/adapters/__init__.py`
- [X] T002 Atualizar a raiz `ai-core/pyproject.toml`: `testpaths` passa a `["packages/contracts/tests", "packages/core/tests"]`; mypy `files` inclui `packages/core/src`; `known-first-party` do ruff inclui `ai_core`; rodar `uv sync` (gera o novo `ai-core/uv.lock`) e conferir `uv run python -c "import ai_core.packs"` e `uv run pytest -q` (a suíte dos contratos continua verde) (depende de T001)
- [X] T003 Ajustar os testes de piso dos contratos (R3): no job `test` de `.github/workflows/contracts.yml`, manter 3.14 pelo workspace (`uv sync --locked` + `uv run pytest packages/contracts/tests`) e rodar 3.12 e 3.13 fora dele com `uv run --no-project --python <v> --with ./packages/contracts --with pytest --with pytest-asyncio --with hypothesis --with packaging pytest packages/contracts/tests -q`; trocar o comando de 3.12 da seção 1 de `specs/001-core-contracts/quickstart.md` pelo mesmo comando; conferir localmente com Python 3.12 (depende de T002)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: seams, portas, adapters em memória e packs de teste que todas as stories usam

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T004 [P] Implementar `ai-core/packages/core/src/ai_core/packs/api.py` conforme specs/002-core-pack-runtime/contracts/pack-runtime-api.md: `PackStatus` (`StrEnum`: `enabled`, `disabled`, `error`); `RetrieverCapability` (`name`, `collections: frozenset[str]`); `PackCapabilities` (os 8 campos do data-model.md); `PackEntry` (`name`, `version: str | None`, `contract_version: str | None`, `origin: Literal["code", "declarative"]`, `status`, `error: str | None = None`, `capabilities: PackCapabilities | None = None`, com a regra "`error` obrigatório quando `status == error`" no `__post_init__`); `Composition` (`packs: tuple[str, ...]`); `CompositionError(ValueError)` com atributo `packs`; `PackHookError(RuntimeError)` com `pack` e `hook`; `PackConfigError(ValueError)`; Protocols `PackRegistry` (`entries`, `entry`, `compose`) e `PackHooks` (`system_prompts`, `async prepare`, `async validate`); `ValidatorRun`; `ValidationOutcome`; `type Slices = Mapping[str, Mapping[str, JSONValue]]`. Só importa stdlib e `ai_core_contracts`. Testes em `ai-core/packages/core/tests/packs/unit/test_packs_api.py`
- [X] T005 [P] Implementar `ai-core/packages/core/src/ai_core/packs/ports.py` conforme contracts/ports.md: `DiscoveredPack` (`name`, `distribution`, `version`, `load: Callable[[], object]`), `PackSettings` (`enabled: bool = False`; `config: Mapping[str, JSONValue]` default vazio, congelado), Protocols `PackSource.discover()` e `PackConfigSource.load()` (documentando que `load` levanta `PackConfigError`)
- [X] T006 Implementar `ai-core/packages/core/src/ai_core/packs/adapters/memory.py`: `InMemoryPackSource(entries: Sequence[DiscoveredPack])` e o construtor de conveniência `InMemoryPackSource.of(*classes, distribution="test-dist", version="0.1.0")` (usa `cls.name` como nome do entry point, ou `(nome, classe)` quando o teste quer divergência), e `InMemoryPackConfigSource(settings: Mapping[str, PackSettings] | None = None, *, error: PackConfigError | None = None)` (depende de T005)
- [X] T007 Criar `ai-core/packages/core/tests/packs/conftest.py`: fábrica `make_pack_class(name="good", contract_version="0.1", *, manifest=None, init=None, **hooks)` que devolve uma subclasse de `ai_core_contracts.PackBase` com `name`/`contract_version` como atributos de classe e contador de instâncias (`created`); packs prontos `good` (com `config_schema` exigindo `collection: string`, `system_prompt`, uma tool nativa e um validator determinístico); fixture `fake_distribution(tmp_path, monkeypatch)` que escreve `<dist>-<versão>.dist-info/METADATA` e `entry_points.txt` (grupo `ai_core.packs`) mais o módulo do pack em `tmp_path`, põe `tmp_path` no `sys.path` e limpa `sys.modules` no fim (depende de T006)

**Checkpoint**: seams tipados, portas e adapters em memória prontos

---

## Phase 3: User Story 1 — Operador instala um pack e o core o descobre (Priority: P1) 🎯 MVP

**Goal**: descoberta por entry point, identidade e contrato checados antes de instanciar, habilitação e configuração
pelo operador, catálogo coletado uma vez.

**Independent Test**: `ai-core/packages/core/tests/packs/integration/test_packs_entry_points_load.py` — distribuição falsa
com o pack `good` e `packs.yaml` real: `enabled` com capacidades; ausente ou `enabled: false` → `disabled` sem instância;
config fora do schema → `error` nomeando o campo (quickstart §3).

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T008 [P] [US1] Criar `ai-core/packages/core/tests/packs/contract/test_packs_source_port.py`: suíte de conformidade de `PackSource` parametrizada sobre `InMemoryPackSource` e `EntryPointPackSource` (este com distribuições falsas via `fake_distribution`): um `DiscoveredPack` por entrada; `load()` devolve a classe; nome, distribuição e versão corretos; módulo que levanta no import só falha ao chamar `load()`; duas distribuições com o mesmo nome aparecem as duas (contracts/ports.md)
- [X] T009 [P] [US1] Criar `ai-core/packages/core/tests/packs/contract/test_packs_config_port.py`: suíte de conformidade de `PackConfigSource` sobre `InMemoryPackConfigSource` e `YamlPackConfigSource` (arquivos em `tmp_path`): pack ausente não aparece; `enabled` default `False`; `config` default vazio; e, só no YAML, as violações de specs/002-core-pack-runtime/contracts/packs-yaml.md → `PackConfigError` nomeando `packs.<nome>.<chave>` (raiz sem `packs`, chave desconhecida, `enabled` não booleano, `config` não mapeamento, arquivo inexistente)
- [X] T010 [P] [US1] Criar `ai-core/packages/core/tests/packs/unit/test_packs_identity_config.py`: `domain/identity.py` — classe com `name`/`contract_version` como atributos de classe → identidade; `name` diferente do entry point → mensagem `entry point '<x>' aponta para classe com name '<y>'`; atributo ausente ou não `str` → `classe sem atributo de classe '<attr>'`; `domain/config.py` — config conforme → sem erro; `{"collection": 42}` contra schema que exige string → `configuração inválida em 'collection': ...`; erro aninhado → caminho `limits.top_k`; schema inválido → `config_schema inválido: ...`; pack sem schema → aceita
- [X] T011 [P] [US1] Criar `ai-core/packages/core/tests/packs/unit/test_packs_load.py` (service com adapters em memória): pack `good` habilitado com `config={"collection": "docs"}` → `enabled`, `version` da distribuição, `contract_version` `0.1`, `capabilities` com prompt, tool, validator, `preferred_flow`, `depends_on`, `requires_collections`; o `PackContext` entregue aos hooks carrega a config; cada hook de catálogo chamado exatamente uma vez; pack ausente da configuração ou `enabled: false` → `disabled` e `created == 0` (cenário 2); config violando o schema → `error` com `configuração inválida em 'collection'` (cenário 3); `entries()` ordenado por nome e `entry(nome)`
- [X] T012 [P] [US1] Criar `ai-core/packages/core/tests/packs/integration/test_packs_entry_points_load.py`: carga completa com `EntryPointPackSource` + `YamlPackConfigSource` sobre `fake_distribution` e `packs.yaml` em `tmp_path`, cobrindo as três linhas da tabela do quickstart §3

### Implementation for User Story 1

- [X] T013 [P] [US1] Implementar `ai-core/packages/core/src/ai_core/packs/domain/identity.py`: `read_identity(entry_name: str, cls: object) -> tuple[str, str] | str` — lê `name` e `contract_version` com `getattr` na **classe** (atributos de classe, FR-017), exige `str`, exige `name == entry_name`; devolve `(name, contract_version)` ou a mensagem de erro do data-model.md
- [X] T014 [P] [US1] Implementar `ai-core/packages/core/src/ai_core/packs/domain/config.py`: `config_error(config: Mapping[str, JSONValue], schema: Mapping[str, JSONValue] | None) -> str | None` com `jsonschema.validators.validator_for(schema, default=Draft202012Validator)`, `check_schema` (→ `config_schema inválido: ...`), primeiro erro por `best_match`, caminho com `.` entre segmentos (`(raiz)` quando vazio), sem resolução de `$ref` remoto; converte mapeamentos congelados em `dict`/`list` antes de validar
- [X] T015 [US1] Implementar `ai-core/packages/core/src/ai_core/packs/adapters/entry_points.py`: `EntryPointPackSource(group: str = "ai_core.packs")` com `importlib.metadata.entry_points(group=...)` → `DiscoveredPack(name=ep.name, distribution=ep.dist.name, version=ep.dist.version, load=ep.load)` (sem chamar `load`), ordenados por nome e distribuição (depende de T005)
- [X] T016 [US1] Implementar `ai-core/packages/core/src/ai_core/packs/adapters/config_yaml.py`: `YamlPackConfigSource(path: Path)` com `yaml.safe_load` e as regras de contracts/packs-yaml.md (arquivo inexistente, raiz sem `packs`, chaves desconhecidas, `enabled` booleano, `config` mapeamento JSON → `PackConfigError` com o caminho); devolve `Mapping[str, PackSettings]` (depende de T005)
- [X] T017 [US1] Implementar `ai-core/packages/core/src/ai_core/packs/service.py`: `PackRuntime(source: PackSource, config_source: PackConfigSource)` com `load() -> None` (etapas 1, 3, 4 e 5 de research R5: descobrir, importar, `read_identity`, `check_compatibility`, habilitação, instanciar sem argumentos, `manifest()`, `config_error`, hooks de catálogo uma vez com `PackContext(pack_name, config)`, `check_declaration` da 001, `PackCapabilities`) e implementação de `PackRegistry.entries()`/`entry()`; estado interno `LoadedPack` com o catálogo coletado; registry imutável depois de `load()` (segunda chamada levanta `RuntimeError`); logger `ai_core.packs` (depende de T004–T006, T013, T014)

**Checkpoint**: US1 completa — um pack instalado é descoberto, configurado e aparece como `enabled`; MVP da 002

---

## Phase 4: User Story 2 — Pack quebrado não derruba o sistema (Priority: P1)

**Goal**: toda falha de pack vira `error` com etapa e causa, o boot segue e a indisponibilidade é explícita ao compor.

**Independent Test**: `ai-core/packages/core/tests/packs/unit/test_packs_failure_matrix.py` — com `good` sempre
habilitado, cada defeito injetado deixa só o pack defeituoso em `error`, com a mensagem prevista (quickstart §4, SC-002).

### Tests for User Story 2 ⚠️

- [X] T018 [P] [US2] Criar `ai-core/packages/core/tests/packs/unit/test_packs_failure_matrix.py` com a tabela do quickstart §4: `contract_version = "0.2"` (→ `requer ai-core-contracts>=0.2, instalado 0.1.0`), manifest com nome diferente (→ `manifest inválido:`), exceção no construtor (→ `falha ao instanciar:`), exceção em `tools()` (→ `hook tools levantou`), declaração inválida (duas tools com o mesmo nome → `declaração inválida:`), falha no import (→ `falha ao importar:`), entry point com nome diferente do `name`, dois packs com o mesmo nome (os dois em erro, `nome duplicado:`), `depends_on` para pack desabilitado, ciclo `a → b → a`, pack citado na configuração e não instalado (→ `não instalado`); em todos, `good` continua `enabled` e o `load()` termina; cada erro gera um registro de log com nome e etapa (`caplog`)
- [X] T019 [P] [US2] Criar `ai-core/packages/core/tests/packs/unit/test_packs_dependencies.py`: `domain/dependencies.py` — dependência não instalada, desabilitada ou em erro → dependente em erro (`depende de '<b>', que está <estado>`); cascata até ponto fixo (A → B → C quebrado derruba B e A); ciclo → todos os packs do ciclo em erro com `dependência circular: a → b → a`; packs sem dependência não mudam
- [X] T020 [P] [US2] Criar `ai-core/packages/core/tests/packs/contract/test_packs_registry_seam.py` (seam Pack Registry, contracts/pack-runtime-api.md): `entries()` imutável e ordenado; `entry()` de nome desconhecido → `None`; `compose` recusa nome desconhecido, pack `disabled`, pack `error` (a mensagem repete o erro do pack — US2 cenário 3) e nome repetido, sempre com `CompositionError.packs` preenchido; composição válida devolve `Composition` com a ordem recebida

### Implementation for User Story 2

- [X] T021 [P] [US2] Implementar `ai-core/packages/core/src/ai_core/packs/domain/dependencies.py`: `dependency_errors(status: Mapping[str, PackStatus], depends_on: Mapping[str, Sequence[str]]) -> dict[str, str]` com a regra de cascata até ponto fixo e a detecção de ciclos (research R9), mensagens do data-model.md
- [X] T022 [P] [US2] Implementar `ai-core/packages/core/src/ai_core/packs/domain/composition.py`: `composition_error(pack_names: Sequence[str], entries: Mapping[str, PackEntry]) -> tuple[str, tuple[str, ...]] | None` para nome desconhecido, status diferente de `enabled` (mensagem inclui o `error` do pack) e nome repetido (a regra de ordem de dependência entra na US3)
- [X] T023 [US2] Completar a carga em `ai-core/packages/core/src/ai_core/packs/service.py` com falha fechada (research R5 etapas 2, 6 e 7): nomes duplicados, exceção em qualquer etapa → `error` com a etapa, `dependency_errors` depois da carga individual, pack citado e não instalado → entrada `error: não instalado`, um `logger.error` por pack em erro; e `PackRegistry.compose()` com `composition_error` → `CompositionError` (depende de T021, T022)

**Checkpoint**: US1 e US2 — o boot sempre conclui e todo pack quebrado aparece com a causa

---

## Phase 5: User Story 3 — Composição de packs: execução de hooks (Priority: P1, cenários 2–4)

**Goal**: Pack Hooks que a 005 US1 consome: prompts na ordem, `prepare` com Turn View recortada e merge raso, `validate`
encadeado, dependência antes do dependente e `PackHookError` que nomeia o pack.

**Independent Test**: `ai-core/packages/core/tests/packs/contract/test_packs_hooks_seam.py` — dois packs com a mesma chave
de fatia não se sobrescrevem; A antes de B nos prompts; B dependente de A vê a fatia que A acabou de escrever; leitura
de fatia não declarada e hook que levanta encerram com `PackHookError` (quickstart §5).

### Tests for User Story 3 ⚠️

- [X] T024 [P] [US3] Criar `ai-core/packages/core/tests/packs/unit/test_packs_hook_rules.py`: `domain/hooks.py` — `scope_view` devolve Turn View com `own_slice` = fatia do pack e `dependency_slices` só com `depends_on` (packs fora ficam ausentes); `merge_slice` faz merge raso (chaves devolvidas substituem, ausentes permanecem) e rejeita valor não-JSON; `apply_validation` atualiza `answer`/`citations` só quando o resultado os traz e acumula `flags`; `composition_error` recusa dependência ausente da lista ou depois do dependente, nomeando os dois
- [X] T025 [P] [US3] Criar `ai-core/packages/core/tests/packs/contract/test_packs_hooks_seam.py` (seam Pack Hooks, tabela de contracts/pack-runtime-api.md): `system_prompts` na ordem da composição, sem fragmentos `None` (cenário 2); `prepare` com A e B usando a mesma chave de fatia → fatias separadas; B dependente de A recebe em `dependency_slices["a"]` a fatia nova de A; retorno de `prepare` com todas as fatias da composição; `compose(["b", "a"])` e `compose(["b"])` → `CompositionError` com os dois nomes; hook que lê `dependency_slices["c"]` não declarado → `PackHookError(pack="b", hook="prepare_context")` (cenário 3); `prepare_context` que levanta ou devolve não-mapeamento/não-JSON → `PackHookError` (cenário 4); `validate` encadeia resposta e citações, devolve `ValidationOutcome` (ok, answer, citations, flags, runs na ordem); validator que levanta → `PackHookError(hook="validate:<nome>")`; `Composition` montada à mão com pack desabilitado → `CompositionError`; SC-005 — para todo par ordenado de packs de teste válidos que respeite as dependências, `compose`, `prepare` e `validate` rodam sem erro

### Implementation for User Story 3

- [X] T026 [US3] Acrescentar a `ai-core/packages/core/src/ai_core/packs/domain/composition.py` a regra de ordem (FR-008): toda dependência de um pack precisa estar na lista e antes dele; senão `CompositionError` nomeando o dependente e a dependência (depende de T022)
- [X] T027 [P] [US3] Implementar `ai-core/packages/core/src/ai_core/packs/domain/hooks.py`: `scope_view(view: TurnView, pack: str, depends_on: Sequence[str], slices: Slices) -> TurnView` (via `dataclasses.replace`), `merge_slice(current, update) -> Mapping[str, JSONValue]` (merge raso; `TypeError` se `update` não for mapeamento JSON — usa `is_json_value` equivalente, sem API privada da 001) e `apply_validation(view, result) -> TurnView`
- [X] T028 [US3] Implementar `PackHooks` em `ai-core/packages/core/src/ai_core/packs/service.py`: `system_prompts`, `prepare` e `validate` conforme contracts/pack-runtime-api.md e research R7/R8 — revalidar a composição, rodar pack a pack na ordem, recortar a view, converter exceção ou retorno inválido em `PackHookError(pack, hook)`, montar o `ValidationOutcome` (depende de T026, T027)

**Checkpoint**: escopo da Fase 1 da 002 entregue — Pack Registry e Pack Hooks prontos para a 005 e a 011

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T029 Acrescentar a `ai-core/pyproject.toml` os contratos de import-linter do research R13 — `root_packages = ["ai_core_contracts", "ai_core"]`; `ai_core_contracts` não importa `ai_core`; `ai_core.packs.api` não importa `domain`/`ports`/`service`/`adapters`; `ai_core.packs.domain` não importa `ports`/`service`/`adapters`; `ai_core.packs.service` não importa `adapters`; `ai_core.packs.api`/`domain`/`ports`/`service` não importam `yaml` — e rodar `uv run lint-imports` até passar
- [X] T030 [P] Criar `ai-core/packages/core/tests/packs/unit/test_packs_public_api.py`: os nomes públicos de `ai_core.packs.api` são exatamente os de specs/002-core-pack-runtime/contracts/pack-runtime-api.md, e `ai_core.packs.api` só importa stdlib e `ai_core_contracts` (varredura AST)
- [X] T031 [P] Criar `.github/workflows/core.yml` (raiz do repositório; `working-directory: ai-core`; gatilhos em `ai-core/packages/core/**`, `ai-core/packages/contracts/**`, `ai-core/pyproject.toml`, `ai-core/uv.lock` e no próprio workflow): jobs `lint` (`ruff check`/`ruff format --check` em `packages/core`, `mypy`), `test` (`uv sync --locked`; `uv run pytest packages/core/tests`) e `boundaries` (`uv run lint-imports`)
- [X] T032 Executar as seções 1–6 de specs/002-core-pack-runtime/quickstart.md e corrigir divergências entre o resultado e o "Esperado"
- [X] T033 [P] Atualizar a seção "Código" de `CLAUDE.md` (a distribuição `ai-core` existe, com o módulo `ai_core/packs/`; o workspace exige 3.14 e os testes de piso dos contratos rodam fora dele) e a linha da 002 em `specs/README.md` (status "Fase 1 implementada")

---

## Phase 7: User Story 4 — Operador inspeciona e valida packs sem subir o servidor (Priority: P2) — Fase 2

**Goal**: listar o que está instalado e habilitado e reprovar, com código de saída, exatamente o que o boot marcaria
como erro — inclusive pack instalado e desabilitado.

**Independent Test**: `uv run pytest packages/core/tests/packs/integration/test_packs_cli.py` — com um pack
incompatível instalado, `check` sai com código diferente de zero e nomeia a incompatibilidade.

### Tests for User Story 4 ⚠️

- [X] T034 [US4] Criar `ai-core/packages/core/tests/packs/integration/test_packs_cli.py` com os seis itens de
  [contracts/cli.md](contracts/cli.md), sobre a carga real (`EntryPointPackSource` + `YamlPackConfigSource`, com
  `FakeDistributions` e `packs.yaml` em `tmp_path`, como `test_packs_entry_points_load.py`): `list_command` imprime uma
  linha por pack com nome, versão, versão de contrato e status, `-` onde não há valor (pack citado e não instalado), e
  sai com 0 mesmo com pack em erro; `check_command` sai com 0 e `M packs ok` quando todos estão bons; sai com 1 e nomeia
  a incompatibilidade de um pack com `contract_version = "0.2"` **desabilitado** no `packs.yaml` (US4 cen. 2); sai com 1
  nomeando pack citado e não instalado e pack com `config` fora do schema; `config_error_command` sai com 2 e repete a
  mensagem de `PackConfigError`

### Implementation for User Story 4

- [X] T035 [US4] Implementar `ai-core/packages/core/src/ai_core/packs/adapters/cli.py` conforme
  [contracts/cli.md](contracts/cli.md) e research R15–R17: `list_command(registry, out) -> int`,
  `check_command(registry, out) -> int` e `config_error_command(error, err) -> int`, síncronas, só com a biblioteca
  padrão; saída em colunas na ordem de `entries()`, erro na mesma linha, `-` para campo ausente; `check` imprime só as
  entradas em erro e o resumo (`N de M packs em erro` ou `M packs ok`); códigos 0/1/2 como os do `assistants validate`
  (003). Sem parser: o registro é da 011

**Checkpoint**: a US4 da 002 está pronta para a 011 registrar

### Polish da Fase 2

- [X] T036 Rodar a seção 7 de [quickstart.md](quickstart.md) e a verificação completa (`uv run pytest`, `uv run mypy`,
  `uv run ruff check packages`, `uv run lint-imports`), corrigindo divergências
- [X] T037 [P] Atualizar a linha da 002 em `specs/README.md` (status "Fase 1 implementada (US1, US2, US3 cen. 2–4);
  Fase 2 (US4) implementada") e a seção "Código" de `CLAUDE.md` (os comandos `packs list`/`packs check` existem em
  `ai_core/packs/adapters/cli.py`, aguardando o registro pela 011)

---

## Phase 8: User Story 3, cenário 1 — Catálogo com namespace (Priority: P1) — Fase 3

**Goal**: o `PackRuntime` entrega as tools nativas e os retrievers de uma composição, com `<pack>.<nome>`, para a 004.

**Independent Test**: `uv run pytest packages/core/tests/packs/contract/test_packs_toolset_seam.py
packages/core/tests/capabilities/contract/test_pack_tool_source.py`.

### Tests for User Story 3 (cenário 1) ⚠️

- [X] T038 [P] [US3] Criar `tests/packs/contract/test_packs_toolset_seam.py`:
  packs A e B com a tool local `search` → `a.search` e `b.search` (US3 cen. 1); ordem da composição, nativas antes dos
  retrievers de cada pack; retriever como tool `retrieval` com `RETRIEVAL_TOOL_PARAMETERS`, `mutates=False` e o
  `NamedRetriever` com as coleções; `PackTool.spec.name` é o nome local; pack fora da composição não aparece; composição
  com pack em erro → `CompositionError` (revalidação, R10); composição vazia → nada
- [X] T039 [P] [US3] Toque declarado na 004 (R20): parametrizar `tests/capabilities/contract/test_pack_tool_source.py`
  para rodar contra `StaticPackTools` **e** contra um `PackRuntime` carregado com packs de teste equivalentes
  (`InMemoryPackSource`), e um teste tipado que atribui o `PackRuntime` a uma variável anotada com `PackToolSource`

### Implementation for User Story 3 (cenário 1)

- [X] T040 [US3] Em `src/ai_core/packs/api.py`, `PackTool` e `PackToolset` de
  [contracts/pack-runtime-api.md](contracts/pack-runtime-api.md); em `src/ai_core/packs/service.py`,
  `PackRuntime.toolset(composition)` (R19) sobre `_members`; atualizar os nomes públicos esperados em
  `tests/packs/unit/test_packs_public_api.py`
- [X] T041 [US3] Toque declarado na 004 (R20): `src/ai_core/capabilities/domain/records.py` reexporta `PackTool` de
  `ai_core.packs.api`

### Polish da Fase 3

- [X] T042 Verificação completa (`uv run pytest`, `uv run mypy`, `uv run ruff check packages`, `uv run lint-imports`);
  linha da 002 em `specs/README.md` (Fase 3, US3 cen. 1) e o seam **Pack Toolset** na tabela de seams; `CLAUDE.md`

---

## Phase 9: User Story 5 — Operador compõe a instalação e o build rejeita incompatibilidade (Priority: P2) — Fase 4

**Goal**: repositório de instalação `agentic-deploy` com Dockerfile em três estágios (core da tag `v0.1.0`, packs por
build-arg + `packs check`, runtime sem instalador), verificado localmente e na CI (research R21–R29).

**Independent Test**: `agentic-deploy/scripts/check-build.sh` — pack compatível builda; incompatível falha no `packs
check`; runtime sem `uv`/`pip`/`ensurepip` e sem escrita em `/opt/ai-core`.

Caminhos começam em `agentic-deploy/` (submódulo → `CaioFerreiraB/agentic-deploy`), salvo os de `specs/`, `docs/` e
`CLAUDE.md`.

- [X] T043 [US5] Criar o repositório privado `CaioFerreiraB/agentic-deploy` com `README.md` e `.gitignore` (`.env`) e
  ligá-lo no `agentic-app` como submódulo `agentic-deploy/` (R21)
- [X] T044 [P] [US5] Criar `packages/incompatible-pack/` (R26): `pyproject.toml` (`incompatible-pack` 0.1.0,
  `requires-python = ">=3.12"`, `ai-core-contracts>=0.1,<0.3`, entry point `incompatible =
  "incompatible_pack:IncompatiblePack"` em `ai_core.packs`, `uv_build`) e `src/incompatible_pack/__init__.py` com
  `IncompatiblePack(PackBase)`, `name = "incompatible"`, `contract_version = "0.2"` e `manifest()` mínimo
- [X] T045 [P] [US5] Criar `config/packs.yaml` (`generic` e `scouting` habilitados), `config/assistants.yaml` (um
  Assistant `scouting`, `flow: chat`, `packs: [scouting]`, modelo do OpenRouter, ACL pública; `api_keys.admin_group`) e
  `.env.example` (perfil `memory`, `AI_CORE_DEV_API_KEY` de exemplo no formato `aic_<16 hex>_<…>`,
  `AI_CORE_OPENROUTER_API_KEY=` vazio) (R24)
- [X] T046 [US5] Criar `Dockerfile` (R22, R23; contrato de [installation.md](contracts/installation.md)): estágios
  `core`, `packs` e `runtime` sobre `python:3.14-slim`; `uv` de `ghcr.io/astral-sh/uv:0.12.23` só nos dois primeiros;
  `known_hosts` com a chave ed25519 do GitHub fixada; `RUN --mount=type=ssh,id=core` para o core e
  `--mount=type=ssh,id=packs` + `--mount=type=bind,source=packages,target=/build/packages` para os packs;
  `ai-core packs check` com `AI_CORE_PACKS_FILE=/etc/ai-core/packs.yaml`; no runtime, remover `pip`/`ensurepip`, usuário
  `ai-core` (uid 10001), variáveis de [installation.md](contracts/installation.md) e `CMD ["ai-core", "serve"]`
- [X] T047 [US5] Criar `scripts/check-build.sh` (R27): `set -euo pipefail`; `SSH_CORE`/`SSH_PACKS` (default: agente);
  build do alvo `runtime`; na imagem, `ai-core packs list` com `generic` e `scouting` `enabled`, `ai-core assistants
  validate` com `config/assistants.yaml` montado, ausência de `uv`/`pip`/`ensurepip` e escrita recusada em
  `/opt/ai-core`; build do alvo `packs` com `PACKS=/build/packages/incompatible-pack` precisa falhar com `incompatible`
  na saída; mensagens de cada passo e saída 0 só se tudo vale
- [X] T048 [US5] Rodar `scripts/check-build.sh` localmente e corrigir até sair com 0 (US5 cen. 1–3)
- [X] T049 [P] [US5] Criar `docker-compose.yml` (R24, R25): serviço `ai-core` com `build` (target `runtime`, `ssh:
  [core, packs]`), `ports: ["8000:8000"]`, `env_file: .env`, `config/assistants.yaml` montado somente leitura em
  `/etc/ai-core/assistants.yaml`, `read_only: true` e `tmpfs: [/tmp]`; e `README.md` com o uso (build, `.env`, compose,
  trocar pack = mudar `PACKS` e `config/packs.yaml` e rebuildar)
- [X] T050 [US5] Criar `.github/workflows/build.yml` (R28): push e PR; grava `AGENTIC_APP_DEPLOY_KEY` e
  `AI_SCOUTING_DEPLOY_KEY` em arquivos `600` e roda `scripts/check-build.sh` com `SSH_CORE`/`SSH_PACKS` neles
- [X] T051 [US5] Com o aval do mantenedor: tag anotada `v0.1.0` no `agentic-app` (e push); deploy keys só de leitura
  no `agentic-app` e no `ai-scouting` e os dois segredos no `agentic-deploy`; push do `agentic-deploy` e CI verde;
  commit no `agentic-app` com o SDD, a documentação e o ponteiro do submódulo
- [X] T052 [P] Documentação no `agentic-app`: CLAUDE.md (a instalação existe — repositório, estágios, `check-build.sh`,
  ADR-022; a Fase 4 do roadmap completa), linha da 002 em `specs/README.md` (US5 implementada) e `docs/roadmap.md`
  (Fase 4 ✅ com o parágrafo "Fase 4 concluída em 2026-10-07")

**Dependências da Fase 4**: T043 primeiro; T044, T045 em paralelo; T046 → T047 → T048; T049 e T050 depois de T046;
T051 depois de T048 e T050; T052 em paralelo com T051.

---

## Passada de 2026-10-07: validators que filtram o streaming ([ADR-024](../../docs/adr/ADR-024-validators-filtram-o-streaming.md); research R30)

- [X] T053 `api.py`: `AnswerFilter`, `StreamedValidation`, `PackHooks.open_answer_stream` e `validate(..., streamed)`
- [X] T054 `domain/stream.py`: `ChainedFilter` e `StreamSession`; `service.py`: `open_answer_stream`, o `validate` com
  `streamed` e `_validators` (a sequência da composição)
- [X] T055 Testes do seam (prefixo, encadeamento, reaproveitamento, sessão que quebra a regra, filtro vazio);
  superfície pública e operações do `PackHooks` atualizadas em `test_packs_public_api.py`

---

## Passada de encaixe da Fase 5 na instalação — 2026-10-13 (research R31–R35; contracts/installation.md "Fase 5")

Caminhos em `agentic-deploy/` (o submódulo → `CaioFerreiraB/agentic-deploy`); o código é commitado lá, e aqui o SDD e o
ponteiro.

- [X] T056 `Dockerfile` (R31, R32): `CORE_REF=v0.2.0`; `PACKS` com o `ai-scouting` em
  `c60ffb460e082751e39705b539fbb82aa46eeccb`; no estágio `packs`, depois do `uv pip install` e antes do `packs check`,
  `/opt/ai-core/bin/ai-scouting-corpus model fetch /opt/ai-scouting/e5-small`; o `runtime` copia `/opt/ai-scouting`
  do estágio `packs` (dono root, somente leitura para o usuário `ai-core`)
- [X] T057 [P] `config/packs.yaml` (R32, R33): `scouting.config` com `qdrant_url: http://qdrant:6333` e
  `embedding_dir: /opt/ai-scouting/e5-small`; `config/assistants.yaml` (R35): `scouting` sem `flow` e com
  `collections: [scouting]`
- [X] T058 [P] `docker-compose.yml` (R33, R34): serviço `qdrant` (`qdrant/qdrant:v1.19.2`, volume nomeado
  `qdrant-data:/qdrant/storage`, sem `ports`); `ai-core` com `depends_on: [qdrant]` e `environment`
  `AI_SCOUTING_QDRANT_URL=http://qdrant:6333` e `AI_SCOUTING_EMBEDDING_DIR=/opt/ai-scouting/e5-small`; `qdrant` lê
  `QDRANT__SERVICE__API_KEY` do `.env` quando definida; `.env.example` com a chave opcional (o mesmo valor nas duas
  variáveis) e as `AI_CORE_RAG_*` comentadas
- [X] T059 [P] `scripts/check-build.sh` (R35): passo novo depois do 2 — `docker run … test -f
  /opt/ai-scouting/e5-small/model.onnx -a -f /opt/ai-scouting/e5-small/tokenizer.json` e `ai-scouting-corpus --help`
- [X] T060 `README.md` do `agentic-deploy`: o Qdrant, a ingestão (R34) com o clone do `ai-scouting`, a chave opcional
  e o `CORE_REF`
- [X] T061 Rodar `scripts/check-build.sh` localmente (agente SSH) até passar; depois, com o `.env` local, `docker compose
  up -d`, a ingestão do corpus real (R34) e uma pergunta ao Assistant `scouting` pela superfície privada — resposta com
  citação, página e vigência; derrubar com `docker compose down` (o volume do Qdrant fica). *Acrescido na implementação*:
  `ORT_DISABLE_TELEMETRY=1` na imagem (o onnxruntime tentava gravar um id de telemetria no sistema somente leitura e
  avisava a cada processo) e a porta do host configurável (`AI_CORE_HOST_PORT`, default 8000)
- [X] T062 Com o aval do mantenedor: commit e push do `agentic-deploy` e a CI (`build.yml`) verde; no `agentic-app`, este
  SDD, o `CLAUDE.md` (a instalação com RAG; corrigir a nota que pedia "cuidado com os submódulos" no deploy — o estágio
  `core` já clona sem submódulos) e o ponteiro do submódulo, e push

---

## Passada de encaixe da Fase 7 na instalação — 2026-10-13 (research R36–R40; contracts/installation.md "Fase 7")

Caminhos em `agentic-deploy/`; o código é commitado lá, e aqui o SDD e o ponteiro.

- [X] T063 `Dockerfile` (R36): `CORE_REF=v0.4.1` (a `v0.4.0` mais a correção do verificador OIDC da 003, achada na T069); `PACKS` com o `ai-scouting` em
  `24cb157590dbc81c9b6778de0b868fcc8064c36b`; README com o `CORE_REF` novo
- [X] T064 [P] `config/keycloak/agentic-realm.json` (R37): realm `agentic`, cliente confidencial `open-webui` (segredo
  `${OPEN_WEBUI_OIDC_SECRET}`, redirect `http://localhost:3000/*`, `standardFlowEnabled`), escopo/mappers com
  audiência `ai-core` e `groups` (sem caminho) no access token, grupo `equipe`, usuários `ana` e `bia` (`equipe`) com
  e-mail verificado e senha `${KEYCLOAK_DEV_PASSWORD}` não temporária
- [X] T065 [P] `docker-compose.yml` (R37, R38): serviços `keycloak` e `open-webui` no perfil `webui`, com a
  configuração do contrato; volume `open-webui-data`; `.env.example` com a seção do perfil `webui` (OIDC do core, segredo
  do cliente, senha de desenvolvimento, administrador do Keycloak, `WEBUI_SECRET_KEY`) e as variáveis da fila comentadas
- [X] T066 [P] `config/assistants.yaml` (R39): Assistant `interno` (privado, `group:equipe`, só `oidc`, flow `chat`,
  pack `generic`, geração no OpenRouter)
- [X] T067 [P] `scripts/check-webui.py` (R40): só biblioteca padrão; login OIDC pelo formulário do Keycloak para
  `ana` e `bia`; `/api/models` de cada um; uma mensagem pelo `/api/chat/completions` do Open WebUI; conferências do
  contrato (listas, resposta, um `POST /v1/chat/completions` no log do `ai-core`, nenhuma conversa gravada)
- [X] T068 `README.md` do `agentic-deploy`: o perfil `webui` (subir, entrar como `ana`/`bia`, o que cada um vê), o
  Keycloak só de desenvolvimento, as variáveis e o `check-webui.py`
- [ ] T069 Rodar `scripts/check-build.sh` (agente SSH) e, com o `.env` local, `docker compose --profile webui up -d` e
  `scripts/check-webui.py` até passar; anotar o resultado no quickstart da 008 (seção "Fase 7"); derrubar. *Achados na
  implementação*: o Keycloak marca os cookies de sessão como `Secure` (o script usa uma política de cookies que trata
  `http://localhost` como seguro, como os navegadores); quem entra depois do primeiro ficava `pending` no Open WebUI
  (`DEFAULT_USER_ROLE=user`); e todo access token era recusado pela 003 — a chave de cifragem do JWKS do Keycloak
  descartava todas (corrigido na 003, T066–T067, core `v0.4.1`)
- [ ] T070 Com o aval do mantenedor: commit e push do `agentic-deploy` e a CI (`build.yml`) verde; no `agentic-app`,
  este SDD, o `CLAUDE.md` e o roadmap (Fase 7 completa) e o ponteiro do submódulo, e push

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001 → T002 → T003
- **Foundational (Phase 2)**: depende do Setup; T004 e T005 em paralelo; T006 depois de T005; T007 depois de T006 —
  **bloqueia as stories**
- **US1 (Phase 3)**: depende da Foundational
- **US2 (Phase 4)**: depende da US1 (completa a carga do `service.py`)
- **US3 (Phase 5)**: depende da US2 (`compose` e o registry completo); T026 estende o arquivo de T022
- **Polish (Phase 6)**: depende de tudo
- **US4 (Phase 7, Fase 2)**: depende só da carga da Fase 1, já entregue; T034 → T035 → T036; T037 em paralelo com T036

### Within Each User Story

- Testes antes e falhando; regras de `domain/` antes do `service.py`
- `service.py` é tocado por T017, T023 e T028 — nessa ordem; `domain/composition.py` por T022 e T026 — nessa ordem

### Parallel Opportunities

- Foundational: T004 e T005
- US1: testes T008–T012 em paralelo; T013 e T014 em paralelo; T015 e T016 em paralelo
- US2: testes T018–T020 em paralelo; T021 e T022 em paralelo
- US3: testes T024 e T025 em paralelo; T027 em paralelo com T026
- Polish: T030, T031 e T033 em paralelo

---

## Parallel Example: User Story 1

```bash
Task: "T008 conformidade de PackSource em tests/packs/contract/test_packs_source_port.py"
Task: "T009 conformidade de PackConfigSource em tests/packs/contract/test_packs_config_port.py"
Task: "T010 identidade e config em tests/packs/unit/test_packs_identity_config.py"
Task: "T011 carga em tests/packs/unit/test_packs_load.py"
Task: "T012 integração em tests/packs/integration/test_packs_entry_points_load.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Setup → Foundational → US1
2. **PARAR E VALIDAR**: `uv run pytest packages/core/tests/packs` e o teste de integração com entry points reais

### Incremental Delivery

1. US1 → descoberta e carga
2. US2 → falha fechada (o boot nunca cai por causa de pack)
3. US3 (cenários 2–4) → Pack Hooks para a 005
4. Polish → fronteiras, CI e documentação

A 005 US1 pode começar quando a US3 desta lista estiver pronta; a 011 depende de US1 e US2.

---

## Notes

- [P] = arquivos diferentes, sem dependência de tarefa incompleta
- Commit após cada tarefa ou grupo lógico
- Fora de escopo: US3 cenário 1, US5, US6 e `reranker`/`routine` do Pack Hooks; da US4, o registro na raiz `ai-core`
  (011) e a introspecção HTTP (008)
