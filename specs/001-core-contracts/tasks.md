---

description: "Tarefas da Fase 0 — ai-core-contracts 0.1 (US1–US4)"
---

# Tasks: Contratos públicos do núcleo (`ai-core-contracts`)

**Input**: Design documents from `/specs/001-core-contracts/`

**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/ (python-api.md, compatibility.md,
testing-kit.md), quickstart.md

**Tests**: incluídos — a spec exige verificação automática (FR-017, FR-018, FR-020; SC-001 a SC-005) e a constituição
exige suíte de conformidade dos seams em todo PR. Dentro de cada user story, os testes vêm antes da implementação e
devem falhar primeiro.

**Escopo**: **US1–US4** (Fase 0 do roadmap). A **US5** (rotina isolada) fica fora da 0.1 (research R23): nenhuma
tarefa cria `routine()`, `PackRoutine`, `RoutineLimits` ou `RoutineResult`.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- Workspace: `ai-core/` (subpasta deste repositório — research R1); distribuição: `ai-core/packages/contracts/`
- Código: `ai-core/packages/contracts/src/ai_core_contracts/`; testes: `ai-core/packages/contracts/tests/`;
  ferramentas fora da distribuição: `ai-core/packages/contracts/tools/`
- Todo módulo Python começa com `from __future__ import annotations` (research R18)
- Value objects: `@dataclass(frozen=True, slots=True, kw_only=True)`; sequências → `tuple`, conjuntos → `frozenset`,
  mapeamentos → `MappingProxyType` sobre cópia, em profundidade, no `__post_init__` (data-model, "Convenções")
- Mensagens e docstrings em português; nomes de código em inglês, como em contracts/python-api.md

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: esqueleto do workspace `ai-core/` e da distribuição, com a guarda do FR-001 ativa desde o início

- [X] T001 Criar `ai-core/.python-version` com `3.14` e a raiz virtual do workspace em `ai-core/pyproject.toml` (sem `[project]`): `[tool.uv.workspace] members = ["packages/*"]`; `[dependency-groups] dev = ["pytest", "pytest-asyncio", "hypothesis", "packaging", "import-linter", "ruff", "mypy"]`; `[tool.pytest.ini_options]` com `testpaths = ["packages/contracts/tests"]`, `pythonpath = ["packages/contracts/tests"]` (para `import service_fakes`), `asyncio_mode = "auto"` e `norecursedirs = ["fixtures"]`; `[tool.ruff]` com `target-version = "py312"`, `line-length = 120` e `lint.select = ["E", "F", "I", "UP", "B", "SIM", "RUF"]`; `[tool.mypy]` com `strict = true`, `python_version = "3.12"` e `files = ["packages/contracts/src", "packages/contracts/tools"]`
- [X] T002 Criar a distribuição em `ai-core/packages/contracts/`: `pyproject.toml` (`name = "ai-core-contracts"`, `version = "0.1.0"`, `requires-python = ">=3.12"`, `dependencies = ["typing_extensions>=4.12"]`, `[build-system] requires = ["uv_build>=0.12,<0.13"]`, `build-backend = "uv_build"`), `README.md` (título e uma linha), `CHANGELOG.md` (seção `## 0.1.0 — não lançada`), `src/ai_core_contracts/py.typed` vazio, `src/ai_core_contracts/_version.py` com `__version__ = "0.1.0"` e `src/ai_core_contracts/__init__.py` reexportando `__version__` com `__all__ = ["__version__"]`
- [X] T003 Rodar `uv sync` em `ai-core/` para gerar `ai-core/uv.lock` e conferir que `uv run python -c "import ai_core_contracts as c; print(c.__version__)"` imprime `0.1.0` (depende de T001, T002)
- [X] T004 [P] Criar `ai-core/packages/contracts/tests/boundary/test_stdlib_only.py`: varre por AST todo `.py` de `src/ai_core_contracts/` e falha, nomeando arquivo, linha e módulo, se (a) um import absoluto tiver raiz fora de `sys.stdlib_module_names ∪ {"typing_extensions", "ai_core_contracts"}` (FR-001, FR-017) ou (b) um módulo fora de `testing/` importar `os`, `io`, `pathlib`, `socket`, `subprocess`, `shutil`, `urllib`, `http`, `time`, `random`, `secrets`, `asyncio` ou `importlib.metadata` (research R20)
- [X] T005 [P] Criar `ai-core/packages/contracts/tests/unit/test_version.py`: `ai_core_contracts.__version__ == importlib.metadata.version("ai-core-contracts")` (research R3)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: a camada de tipos (value objects e Protocols) e as primitivas de versão que todas as user stories usam.
Cada tarefa inclui os testes unitários do próprio tipo.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [X] T006 [P] Implementar `ai-core/packages/contracts/src/ai_core_contracts/_freeze.py`: `type JSONValue = str | int | float | bool | Sequence[JSONValue] | Mapping[str, JSONValue] | None`; `freeze(value: object) -> object` recursivo (`Mapping` → `MappingProxyType` sobre `dict` copiado com valores congelados; `list`/`tuple` → `tuple`; `set`/`frozenset` → `frozenset`; `str`, `bytes` e demais folhas inalteradas); `is_json_value(value: object) -> bool` recursivo (rejeita chave não-`str`, `datetime`, `set`, objetos arbitrários). Testes em `ai-core/packages/contracts/tests/unit/test_freeze.py`: alterar o original depois não muda o congelado; atribuição de item em mapeamento aninhado levanta `TypeError`; casos positivos e negativos de `is_json_value`
- [X] T007 [P] Implementar as primitivas de `ai-core/packages/contracts/src/ai_core_contracts/compat.py` conforme specs/001-core-contracts/contracts/compatibility.md §1–§4: `InvalidVersion(ValueError)`, `InvalidSpecifier(ValueError)`; `Version` (`release: tuple[int, ...]`, `pre: tuple[str, int] | None = None`, `dev: int | None = None`; `parse` pela gramática `release := N ("." N)*`, `pre := ("a" | "b" | "rc") N`, `dev := ".dev" N`; epoch, post-release, versão local e formas não normalizadas → `InvalidVersion`; ordem total do PEP 440 com "`0.1 == 0.1.0`" e "`X.devN < XaN < XbN < XrcN < X`; `XaN.devM < XaN`"; `__str__` normalizado); `parse_contract_version` (só "`X.Y` ou `X.Y.Z`"); `VersionRange` (`parse` de `==V`, `==V.*`, `!=V`, `!=V.*`, `>=`, `<=`, `>`, `<`, `~=` combinados por vírgula; "`<V` — menor que V e, se V for final, **não** pré-release de V"; `contains`; `violated_by` devolvendo a primeira cláusula violada com limite inferior antes do superior; `__str__` canônico `>=0.1,<0.2`); `derive_range` pela tabela §3; `Compatibility` (`ok`, `installed`, `required`, `violated`, `message`) e `check_compatibility(requirement: str | VersionRange, *, installed: str | None = None)` (requisito que começa com operador é faixa explícita; senão é `contract_version`; `installed` default `__version__`; `message = f"requer ai-core-contracts{violated}, instalado {installed}"`). Testes de parsing, ordem e faixas em `ai-core/packages/contracts/tests/unit/test_compat_primitives.py`
- [X] T008 [P] Implementar `ai-core/packages/contracts/src/ai_core_contracts/tools.py` conforme data-model.md "Tools": `type ToolKind = Literal["retrieval", "mcp", "native"]`; `ToolInvocation` (`arguments: Mapping[str, JSONValue]` congelado; `request_id` "não vazio"; `reference_time` "com fuso (*aware*)" — datetime ingênuo → `ValueError`); `type NativeHandler = Callable[[ToolInvocation], Awaitable[object]]`; `ToolSpec` (`name` "não vazio"; `description` "não vazio"; `parameters: Mapping[str, JSONValue]` congelado; `kind: ToolKind`; `mutates: bool = False`; `handler: NativeHandler | None = None` com a invariante de construção "não `None` ⇔ `kind == "native"`" → `ValueError`); `ToolResult` (`content: object` congelado se contêiner; `untrusted: bool = True`; `truncated: bool = False`; `error: str | None = None`). Testes em `ai-core/packages/contracts/tests/unit/test_tools.py`
- [X] T009 [P] Implementar os tipos de `ai-core/packages/contracts/src/ai_core_contracts/retrieval.py` conforme data-model.md "Recuperação" (sem `retrieval_tool_spec`, que é da US2): `Chunk` (`chunk_id` "estável e determinístico; não vazio"; `text: str`; `score: float`; `document` "não vazio"; `version`, `status`, `section: str | None = None`; `page: int | None = None` "≥ 1 se presente"; `metadata: Mapping[str, JSONValue]` default vazio, congelado); `Retriever` e `Reranker` como `Protocol` `runtime_checkable` com as assinaturas de contracts/python-api.md; `NamedRetriever` (`name` e `description` não vazios; `collections` convertido em `frozenset[str]` com a invariante "não vazio" → `ValueError`; `retriever: Retriever`). Testes em `ai-core/packages/contracts/tests/unit/test_retrieval_types.py`
- [X] T010 Implementar `ai-core/packages/contracts/src/ai_core_contracts/view.py` conforme data-model.md "Turn View": `Message` (TypedDict: `role: ReadOnly[str]`, `content: ReadOnly[str]`); `Citation` (TypedDict `total=False`: `chunk_id: Required[ReadOnly[str]]`; `document: ReadOnly[str]`; `version`, `status`, `section: ReadOnly[str | None]`; `page: ReadOnly[int | None]`), com `ReadOnly`/`Required` de `typing_extensions`; `TurnView` com os 13 campos e defaults da tabela (`request_id` e `assistant` "não vazio"; `reference_time` "**com fuso**" → `ValueError` se ingênuo; `messages`, `retrieved`, `reranked`, `generation_context`, `tool_results`, `citations` default `()`; `answer` default `None`; `own_slice` e `dependency_slices` default mapeamento vazio), congelando em profundidade todos os campos de sequência e mapeamento via `_freeze.freeze`. Testes de construção e validação em `ai-core/packages/contracts/tests/unit/test_view_types.py` (depende de T006, T008, T009)
- [X] T011 Implementar `ai-core/packages/contracts/src/ai_core_contracts/validation.py` conforme data-model.md "Validação de resposta": `ValidatorContext` (`pack_name: str`; `config: Mapping[str, JSONValue]` default vazio, congelado); `ValidationResult` (`ok: bool`; `issues` default `()`; `answer: str | None = None`; `citations: Sequence[Citation] | None = None`; `flags: frozenset[str] = frozenset()`); `AnswerValidator` (`Protocol` `runtime_checkable`: `name: str`; `async validate(view: TurnView, ctx: ValidatorContext) -> ValidationResult`). Testes em `ai-core/packages/contracts/tests/unit/test_validation_types.py` (depende de T010)
- [X] T012 Implementar `ai-core/packages/contracts/src/ai_core_contracts/pack.py` conforme data-model.md "Pack": `RETRIEVAL_FILTERS_KEY: Final = "retrieval_filters"`; `PackManifest` (`name`, `version`; `preferred_flow: str | None = None`; `depends_on` e `requires_collections` default `()` convertidos em `tuple`; `config_schema: Mapping[str, JSONValue] | None = None` congelado); `PackContext` (`pack_name: str`; `config` default vazio, congelado); `AgentPack` (`Protocol` `runtime_checkable` com `name`, `contract_version`, `manifest()`, `system_prompt(ctx)`, `async prepare_context(view, ctx)`, `tools(ctx)`, `retrievers(ctx)`, `reranker(ctx)`, `validators(ctx)` — assinaturas de contracts/python-api.md); `PackBase` com os defaults dos hooks opcionais (`system_prompt → None`, `prepare_context → {}`, `tools → ()`, `retrievers → ()`, `reranker → None`, `validators → ()`), sem `name`, `contract_version` nem `manifest`. Testes de construção em `ai-core/packages/contracts/tests/unit/test_pack_types.py` (depende de T008–T011)
- [X] T013 [P] Criar `ai-core/packages/contracts/src/ai_core_contracts/declaration.py` só com `ContractIssue` (`code: str`, `message: str`, `subject: str | None = None`, `severity: Literal["error", "warning"] = "error"`), conforme data-model.md "Issues"
- [X] T014 Reexportar em `ai-core/packages/contracts/src/ai_core_contracts/__init__.py` todos os símbolos públicos de T006–T013 (`JSONValue`, os tipos de `compat`, `tools`, `retrieval`, `view`, `validation` e `pack`, e `ContractIssue`), com `__all__` explícito; criar `ai-core/packages/contracts/tests/unit/test_public_api.py` verificando que todo nome de `__all__` é importável e que nenhum começa com `_`, exceto `__version__` (depende de T006–T013)

**Checkpoint**: camada de tipos pronta, `uv run pytest` e `uv run mypy` verdes; as user stories podem começar

---

## Phase 3: User Story 1 — Autor de pack constrói e testa um pack sem o core (Priority: P1) 🎯 MVP

**Goal**: um pack depende só de `ai-core-contracts`, testa os hooks com fixtures de Turn View e tem o build reprovado
se importar o core. Entrega o kit `ai_core_contracts.testing` (fixtures + conformidade: forma, identidade, manifest e
imports) e o pack de teste.

**Independent Test**: `uv run python packages/contracts/tools/check_clean_env.py` (em `ai-core/`) cria um ambiente limpo
com contratos + `contract_test_pack`; `uv pip freeze` lista só `ai-core-contracts`, `typing-extensions` e
`contract-test-pack`, e os testes do pack passam (SC-001; cenários 1 e 2). A conformidade reporta `imports.forbidden` num
pack que importa `ai_core` (cenário 3).

### Tests for User Story 1 ⚠️

> **NOTE: Write these tests FIRST, ensure they FAIL before implementation**

- [X] T015 [P] [US1] Criar `ai-core/packages/contracts/tests/unit/test_declaration_identity.py`: `check_declaration` devolve exatamente o código esperado para cada caso — nome de pack fora de "`^[a-z][a-z0-9_]{0,31}$`" (`pack.name.invalid`); `contract_version` fora de "`X.Y` ou `X.Y.Z`" (`pack.contract_version.invalid`); `manifest.name` ≠ nome do pack (`manifest.name_mismatch`); `manifest.version` fora do subconjunto PEP 440 (`manifest.version.invalid`); `preferred_flow=""` (`manifest.preferred_flow.invalid`); `depends_on` com o próprio nome (`manifest.self_dependency`) ou repetido (`manifest.duplicate_dependency`); `requires_collections` repetido (`manifest.duplicate_collection`); `config_schema` não serializável em JSON ou com `required` fora de `properties` (`manifest.config_schema.invalid`); manifest válido → nenhuma issue
- [X] T016 [P] [US1] Criar os packs de teste em `ai-core/packages/contracts/tests/conformance/packs.py` (um bom, herdando de `PackBase`, e um por defeito) e `ai-core/packages/contracts/tests/conformance/test_conformance_basics.py`: pack bom → `report.ok`; objeto sem a forma de `AgentPack` → `hook.missing`; `prepare_context` síncrono → `hook.not_async`; defeitos de identidade e manifest de T015 aparecem no relatório; `contract_version = "0.2"` com 0.1.0 instalado → `pack.contract_version.incompatible` com a mensagem `requer ai-core-contracts>=0.2, instalado 0.1.0`; hook que levanta exceção → `hook.raised`; uma etapa com erro encerra as seguintes; `assert_pack_conforms` levanta `AssertionError` contendo `report.render()`; `check_pack` chamado dentro de um loop em execução (teste `async`) → `RuntimeError` que sugere `acheck_pack`
- [X] T017 [P] [US1] Criar `ai-core/packages/contracts/tests/conformance/test_imports_check.py`: gera em `tmp_path` um pacote com `import ai_core.graph` e `from ai_generic import x` dentro de função nunca chamada ou sob `if TYPE_CHECKING:` (para o módulo importar sem o core instalado), coloca-o no `sys.path` (`monkeypatch.syspath_prepend`) e confirma `imports.forbidden` com `subject` `file:<caminho relativo>:<linha>` e o módulo na mensagem; pacote limpo → nenhuma issue; `acheck_pack` num pack desse pacote também reporta `imports.forbidden` (cenário 3)
- [X] T018 [P] [US1] Criar `ai-core/packages/contracts/tests/unit/test_fixtures.py`: `REFERENCE_TIME == datetime(2026, 1, 1, 12, 0, tzinfo=UTC)`; `turn_view()` usa `request_id="req-test"`, `assistant="test-assistant"`, `reference_time=REFERENCE_TIME` e coleções vazias; `chunk()` usa `chunk_id="doc#1"`, `document="doc"` e `score=1.0`; `pack_context`, `validator_context` e `tool_invocation` devolvem objetos congelados; nenhuma fixture lê o relógio

### Implementation for User Story 1

- [X] T019 [US1] Implementar `check_declaration(*, pack_name, contract_version, manifest, tools=(), retrievers=(), validators=())` em `ai-core/packages/contracts/src/ai_core_contracts/declaration.py`, com as regras de identidade e manifest de T015 (regex do pack "`^[a-z][a-z0-9_]{0,31}$`"; `parse_contract_version` e `Version.parse` de `compat.py`) e o helper privado `_schema_problems(schema, *, require_object: bool) -> list[str]` da research R14 (mapeamento; `is_json_value`; `properties` como mapeamento de mapeamentos; `required` lista de `str` contida em `properties`; `type == "object"` quando `require_object`). Mensagens em português, nomeando o elemento; reexportar `check_declaration` em `__init__.py`. Os parâmetros `tools`, `retrievers` e `validators` são aceitos e ignorados até a US2
- [X] T020 [P] [US1] Implementar `ai-core/packages/contracts/src/ai_core_contracts/testing/fixtures.py` com `REFERENCE_TIME`, `turn_view`, `chunk`, `pack_context`, `validator_context` e `tool_invocation`, nas assinaturas e defaults de specs/001-core-contracts/contracts/testing-kit.md
- [X] T021 [P] [US1] Implementar `ai-core/packages/contracts/src/ai_core_contracts/testing/imports.py`: `check_imports(package: str, *, forbidden: Sequence[str] = ("ai_core", "ai_generic")) -> tuple[ContractIssue, ...]`; localiza o alvo por `importlib.util.find_spec` — se for pacote, percorre os `.py` de `submodule_search_locations`; se for módulo solto, varre só o arquivo de `origin` —, analisa com `ast` (imports absolutos de `Import` e `ImportFrom`; relativos são ignorados), **retira de `forbidden` o nome de topo do próprio pacote varrido** (ex.: `ai_generic` importando `ai_generic.x` não é violação) e emite `imports.forbidden` por import proibido, com `subject=f"file:{caminho_relativo}:{linha}"`
- [X] T022 [US1] Implementar `ai-core/packages/contracts/src/ai_core_contracts/testing/conformance.py`: `ConformanceReport` (`pack_name`, `issues`, `ok` sem issue `error`, `render()` com uma linha por issue); `acheck_pack(pack, *, config=None, views=None, check_distribution=True)` executando as etapas 1 (forma: `isinstance(pack, AgentPack)`, `prepare_context` assíncrono), 2 (identidade + `check_compatibility(pack.contract_version)` → `pack.contract_version.incompatible` com a mensagem de `Compatibility.message`), 3 (manifest, via `check_declaration`) e 8 (`check_imports` sobre o pacote de topo do módulo da classe do pack) de testing-kit.md, na ordem, parando na primeira etapa com issue `error` e convertendo exceção de hook em `hook.raised`, com uma lista de etapas extensível para as etapas 4–7 e 9; `check_pack` (via `asyncio.run`; `RuntimeError` com sugestão de `acheck_pack` se já houver loop), `aassert_pack_conforms` e `assert_pack_conforms` (`AssertionError` com `render()`) (depende de T019–T021)
- [X] T023 [US1] Criar `ai-core/packages/contracts/src/ai_core_contracts/testing/__init__.py` reexportando a API de fixtures, conformidade e `check_imports`, com `__all__` explícito e `ISSUE_CODES: Final[frozenset[str]]` contendo **todos** os códigos de specs/001-core-contracts/contracts/testing-kit.md (inclusive os das US2–US4, `reranker.contract`, `distribution.*`, `llm.*` e `mcp.*`); criar `ai-core/packages/contracts/tests/unit/test_issue_codes.py`, que confere se todo código emitido em `declaration.py` e `testing/` está em `ISSUE_CODES` (varredura AST das strings passadas a `ContractIssue(code=...)`). Regra de código: o `code=` é sempre uma string literal na chamada de `ContractIssue`, nunca montada por função auxiliar, para que a varredura a enxergue (depende de T022)
- [X] T024 [US1] Criar o pack de teste em `ai-core/packages/contracts/tests/fixtures/contract_test_pack/`: `pyproject.toml` (`name = "contract-test-pack"`, `version = "0.1.0"`, `requires-python = ">=3.12"`, `dependencies = ["ai-core-contracts>=0.1,<0.2"]`, `[project.entry-points."ai_core.packs"] contract_test = "contract_test_pack.pack:ContractTestPack"`, backend `uv_build`), `src/contract_test_pack/__init__.py`, `src/contract_test_pack/pack.py` (`ContractTestPack(PackBase)` com `name = "contract_test"`, `contract_version = "0.1"` e `manifest()` válido) e `tests/test_pack.py`, que usa só `ai_core_contracts.testing` (`assert_pack_conforms(ContractTestPack())` e um teste de hook com `turn_view(...)`) (depende de T023)
- [X] T025 [US1] Criar `ai-core/packages/contracts/tools/check_clean_env.py` (stdlib + `subprocess` chamando `uv`): cria um venv temporário (`uv venv --python 3.14`), instala `packages/contracts` e `packages/contracts/tests/fixtures/contract_test_pack`, lê `uv pip freeze` e falha se as distribuições (nomes normalizados pelo PEP 503) não forem exatamente `{ai-core-contracts, typing-extensions, contract-test-pack}`; depois instala `pytest`, roda os testes do pack e sai com o código deles (SC-001; depende de T024)

**Checkpoint**: US1 completa — um pack é construído e testado só com os contratos; esta é a entrega mínima (MVP)

---

## Phase 4: User Story 2 — Pack declara tools nativas, retrievers, reranker e validators (Priority: P1)

**Goal**: tools nativas, retrievers nomeados (com coleções), reranker e validators enumeráveis e validados; tool
`retrieval` derivada pelo core com esquema padrão.

**Independent Test**: instanciar `ContractTestPack` e enumerar todas as capacidades — cada uma tem nome local, descrição
e esquema válidos, e `assert_pack_conforms` passa (`tests/test_pack.py` do pack de teste e
`tests/conformance/test_conformance_catalog.py`).

### Tests for User Story 2 ⚠️

- [X] T026 [P] [US2] Criar `ai-core/packages/contracts/tests/unit/test_pack_defaults.py`: uma subclasse de `PackBase` só com `name`, `contract_version` e `manifest` é `isinstance(..., AgentPack)` e seus hooks devolvem `None`, `{}`, `()`, `()`, `None` e `()` sem erro (cenário 2)
- [X] T027 [P] [US2] Criar `ai-core/packages/contracts/tests/unit/test_retrieval_tool.py`: `ToolSpec(kind="native")` sem handler e `ToolSpec(kind="retrieval")` com handler levantam `ValueError` (cenário 3); `NamedRetriever(collections=frozenset())` levanta `ValueError`; `retrieval_tool_spec(named)` tem `kind == "retrieval"`, o `name` e a `description` do retriever, `parameters == RETRIEVAL_TOOL_PARAMETERS`, `mutates is False` e `handler is None` (cenário 4); `RETRIEVAL_TOOL_PARAMETERS` é imutável
- [X] T028 [P] [US2] Criar `ai-core/packages/contracts/tests/unit/test_declaration_capabilities.py`: `check_declaration` devolve exatamente o código esperado — tool com `kind` `retrieval` ou `mcp` (`tool.not_native`); nome de tool fora de "`^[a-z][a-z0-9_]{0,47}$`" (`tool.name.invalid`); duas tools com o mesmo nome (`tool.duplicate_name`); `parameters` sem `type: "object"` no topo ou com `required` fora de `properties` (`tool.parameters.invalid`); handler síncrono (`tool.handler.not_async`); nome de retriever inválido (`retriever.name.invalid`) ou repetido (`retriever.duplicate_name`); retriever com o nome de uma tool nativa (`retriever.name_collision`); `search` síncrono (`hook.not_async`, `subject="retriever:<nome>"`); nome de validator inválido (`validator.name.invalid`) ou repetido (`validator.duplicate_name`); `validate` síncrono (`hook.not_async`, `subject="validator:<nome>"`)
- [X] T029 [P] [US2] Criar `ai-core/packages/contracts/tests/conformance/test_conformance_catalog.py`: com um pack espião, cada hook de catálogo é chamado **exatamente uma vez** (FR-019); `tools()` devolvendo `dict`s → `hook.return_type`; retriever sem coleção criado dentro de `retrievers()` → `hook.raised`; reranker com `rerank` síncrono → `hook.not_async` (`subject="reranker"`); reranker que ignora `top_k` (devolve os três chunks com `top_k=2`) ou devolve um chunk que não estava na entrada → `reranker.contract` (FR-007); issues de `check_declaration` aparecem no relatório; validator que devolve outra coisa → `validator.result_type`; validator não determinístico (ex.: contador interno) → `validator.non_deterministic`

### Implementation for User Story 2

- [X] T030 [US2] Adicionar a `ai-core/packages/contracts/src/ai_core_contracts/retrieval.py` a constante `RETRIEVAL_TOOL_PARAMETERS` congelada — `{"type": "object", "properties": {"query": {"type": "string", "minLength": 1}, "top_k": {"type": "integer", "minimum": 1}}, "required": ["query"], "additionalProperties": false}` — e `retrieval_tool_spec(named: NamedRetriever) -> ToolSpec`, conforme data-model.md; reexportar ambos em `__init__.py`
- [X] T031 [US2] Estender `check_declaration` em `ai-core/packages/contracts/src/ai_core_contracts/declaration.py` com as regras de tools, retrievers e validators de T028 (nomes locais "`^[a-z][a-z0-9_]{0,47}$`"; `_schema_problems(parameters, require_object=True)`; assíncrono verificado com `inspect.iscoroutinefunction` na função ou no `__call__`; colisão entre nome de retriever e nome de tool nativa) (depende de T030)
- [X] T032 [US2] Adicionar a `ai-core/packages/contracts/src/ai_core_contracts/testing/conformance.py` as etapas 4 (chamar cada hook de catálogo uma vez com `pack_context(pack.name, config)`, checar tipos de retorno — `str | None`, `Sequence[ToolSpec]`, `Sequence[NamedRetriever]`, `Reranker | None` com `rerank` assíncrono, `Sequence[AnswerValidator]`; se houver reranker, `await rerank("consulta", [chunk("a"), chunk("b"), chunk("c")], top_k=2)` deve devolver no máximo 2 chunks, todos com `chunk_id` da entrada, senão `reranker.contract`), 5 (`check_declaration` com o catálogo coletado) e 7 (para cada view, `validate(view, validator_context(...))` duas vezes: `ValidationResult` e resultados iguais), conforme testing-kit.md (depende de T031)
- [X] T033 [US2] Estender o pack de teste em `ai-core/packages/contracts/tests/fixtures/contract_test_pack/src/contract_test_pack/pack.py` com `system_prompt` (texto fixo), uma tool nativa `echo` (handler assíncrono que devolve `invocation.arguments` e `invocation.reference_time.isoformat()`), um `NamedRetriever` `docs` sobre a coleção `test_docs` com retriever em memória de chunks fixos, um reranker que corta em `top_k` e um validator determinístico `non_empty_answer`; estender `tests/test_pack.py` para enumerar as capacidades (independent test), checar `retrieval_tool_spec` do retriever e chamar o handler com `tool_invocation(...)`

**Checkpoint**: US1 e US2 funcionam de forma independente; o catálogo inteiro do pack é validável sem o core

---

## Phase 5: User Story 3 — Compatibilidade verificável entre pack e plataforma (Priority: P1)

**Goal**: regra de compatibilidade com faixa derivada e mensagens exatas, depreciação com versões de depreciação e de
remoção, checagem da dependência declarada (FR-018) e detecção de breaking change sem o bump correspondente (FR-020).

**Independent Test**: com 0.1.0 instalado, `check_compatibility("0.2")` é incompatível com
`requer ai-core-contracts>=0.2, instalado 0.1.0`, e `check_compatibility("0.1")` é compatível
(`tests/unit/test_compat_rules.py`); `tests/surface/` confirma que cada categoria do SC-004 sem o bump exigido falha.

### Tests for User Story 3 ⚠️

- [X] T034 [P] [US3] Criar `ai-core/packages/contracts/tests/unit/test_compat_rules.py`: tabela de faixa derivada de compatibility.md §3 (`"0.1"` → `>=0.1,<0.2`; `"0.1.3"` → `>=0.1.3,<0.2`; `"1.2"` → `>=1.2,<2`; `"1.2.3"` → `>=1.2.3,<2`); as seis linhas da tabela §4, com as mensagens exatas (cenários 1 e 2); major futuro — `check_compatibility("1.0", installed="0.1.0")` → `requer ai-core-contracts>=1.0, instalado 0.1.0` (edge case); faixa explícita aceita; requisito malformado → `InvalidVersion`/`InvalidSpecifier`
- [X] T035 [P] [US3] Criar `ai-core/packages/contracts/tests/unit/test_compat_differential.py` com `hypothesis`: versões geradas pela gramática §1 e conjuntos de especificadores com os operadores de §2; `Version` ordena como `packaging.version.Version` e `VersionRange.contains(v)` coincide com `packaging.specifiers.SpecifierSet(s).contains(v, prereleases=True)` (research R5)
- [X] T036 [P] [US3] Criar `ai-core/packages/contracts/tests/unit/test_deprecation.py`: símbolo definido no próprio teste com `@contract_deprecated(since="0.1.0")` emite `ContractDeprecationWarning` com a mensagem `"<símbolo> está depreciado desde ai-core-contracts 0.1.0 e será removido em 0.2.0"`; com `use_instead="novo"`, a mensagem termina em `"; use novo"`; `removal_version`: `"0.1.3"` → `"0.2.0"`, `"0.4"` → `"0.5.0"`, `"1.4"` → `"2.0.0"`, `"2.0.1"` → `"3.0.0"` (cenário 3)
- [X] T037 [P] [US3] Criar `ai-core/packages/contracts/tests/unit/test_distribution_check.py` com a tabela de compatibility.md §5, usando `check_contracts_requirement(requirements, "0.1")`: sem requisito → `distribution.missing_requirement`; `ai-core-contracts @ git+https://...` → `distribution.direct_reference`; `ai-core-contracts===0.1` → `distribution.unsupported_specifier`; `>=0.1` e `~=0.1` → `distribution.range_too_wide` citando `>=0.1,<0.2`; `>=0.0.5,<0.2` → `distribution.range_too_wide`; `>=0.3,<0.4` → `distribution.range_disjoint`; `>=0.1,<0.2`, `>=0.1.3,<0.2` e `ai_core_contracts[x]>=0.1,<0.2 ; python_version >= "3.12"` (nome normalizado, extras e marcador ignorados) → nenhuma issue
- [X] T038 [P] [US3] Criar `ai-core/packages/contracts/tests/surface/conftest.py` (carrega `packages/contracts/tools/api_surface.py` por `importlib.util.spec_from_file_location`) e `ai-core/packages/contracts/tests/surface/test_classification.py`, com **um teste por linha** da tabela de compatibility.md §7 (pares de snapshots sintéticos no formato §9), mais a tabela §8: `declared < required` falha; HEAD já em `0.2.0` aceita nova breaking change sobre a tag `0.1.x`; remover símbolo com `deprecated_since` nulo na tag falha mesmo com bump de minor, e remover símbolo depreciado na tag passa com o bump (janela de depreciação); mudança só em docstring → `none`; `ISSUE_CODES` com código acrescentado → aditiva, com código removido → breaking. Testes contra o pacote real: `dump` rodado em dois subprocessos com `PYTHONHASHSEED=1` e `PYTHONHASHSEED=2` produz JSON idêntico; no snapshot, `Citation` tem só `chunk_id` obrigatória e todas as chaves `ReadOnly`, `Message` tem as duas chaves obrigatórias e `ReadOnly`, e um TypedDict sintético definido no teste (módulo com `from __future__ import annotations` e uma chave `NotRequired`) sai com essa chave opcional (compatibility.md §7, nota sobre TypedDict); `dump` comparado consigo mesmo → nenhuma mudança
- [X] T039 [P] [US3] Criar `ai-core/packages/contracts/tests/conformance/test_conformance_versions.py`: hook de pack que usa um símbolo depreciado no teste → issue `deprecation.used` (*warning*) e `report.ok` continua verdadeiro; etapa 9 com o leitor de `Requires-Dist` substituído via `monkeypatch` → issues `distribution.*` correspondentes; `check_distribution=False` pula a etapa; distribuição não localizada → `distribution.not_found` (*warning*)

### Implementation for User Story 3

- [X] T040 [US3] Adicionar a `ai-core/packages/contracts/src/ai_core_contracts/compat.py` `type ChangeKind = Literal["none", "additive", "breaking"]`, `type BumpKind = Literal["none", "patch", "minor", "major"]`, `removal_version(since)` (compatibility.md §6: "`0.N.x → 0.(N+1).0`; `X.Y[.Z] → (X+1).0.0` (X ≥ 1)"), `required_bump(change, *, current)` e `declared_bump(previous, current)` (§8); reexportar em `__init__.py`
- [X] T041 [US3] Implementar `ai-core/packages/contracts/src/ai_core_contracts/deprecation.py`: `ContractDeprecationWarning(DeprecationWarning)` e `contract_deprecated(since, *, use_instead=None)` sobre `typing_extensions.deprecated`, com `category=ContractDeprecationWarning` e a mensagem de compatibility.md §6 (versão de remoção calculada por `removal_version`), gravando também `__contract_deprecated_since__ = since` no objeto decorado; reexportar em `__init__.py` (depende de T040)
- [X] T042 [P] [US3] Implementar `ai-core/packages/contracts/src/ai_core_contracts/testing/distribution.py`: `check_contracts_requirement(requirements, contract_version)`, puro (subconjunto PEP 508: nome com normalização do PEP 503, extras opcionais, especificador opcional, `@ url` opcional, marcador após `;` ignorado; inclusão por intervalos de compatibility.md §5, com `!=` ignorado na inclusão); funções finas de borda `find_distribution(pack) -> str | None` (via `importlib.metadata.packages_distributions()` e o pacote de topo do módulo do pack) e `read_requirements(distribution) -> Sequence[str]` (`importlib.metadata.requires`)
- [X] T043 [US3] Adicionar a `ai-core/packages/contracts/src/ai_core_contracts/testing/conformance.py` a etapa 9 (se `check_distribution`: `find_distribution` → `distribution.not_found` como *warning* se ausente; senão `read_requirements` + `check_contracts_requirement`) e a captura de `ContractDeprecationWarning` durante todas as etapas (`warnings.catch_warnings(record=True)` → uma issue `deprecation.used` *warning* por aviso, com a mensagem original); reexportar `check_contracts_requirement` em `testing/__init__.py` (depende de T041, T042)
- [X] T044 [US3] Implementar `ai-core/packages/contracts/tools/api_surface.py` (CLI só stdlib): `dump` gera o snapshot JSON de compatibility.md §9 por introspecção de `ai_core_contracts.__all__` e `ai_core_contracts.testing.__all__` — por símbolo, `deprecated_since` (de `__contract_deprecated_since__`, ou `null`); dataclass: campos com anotação em texto, default em `repr`, obrigatoriedade; Protocol: membros com assinatura em texto, `async`, e — para `AgentPack` — se `PackBase` define o membro; TypedDict: chaves com obrigatoriedade e `ReadOnly` **lidas do texto da anotação** (`Required[`, `NotRequired[`, `ReadOnly[`) combinado com `__total__`, nunca de `__required_keys__`/`__readonly_keys__`; funções: parâmetros e retorno; constantes: `repr`, exceto conjuntos, que entram como **listas ordenadas** (`ISSUE_CODES` inclusive); saída JSON com `sort_keys=True`. `diff OLD NEW --old-version X --new-version Y` classifica cada mudança pela tabela §7 (com `ISSUE_CODES` comparado como conjunto), calcula `required_bump` e `declared_bump` e sai com código 1, listando as mudanças, quando o declarado é menor que o exigido **ou** quando um símbolo removido tinha `deprecated_since` nulo no snapshot antigo (§8) (depende de T040, T041)

**Checkpoint**: US1–US3 funcionam; incompatibilidade, depreciação e bump insuficiente são detectados antes do merge

---

## Phase 6: User Story 4 — Pack enxerga uma visão estável da execução, não o estado do motor (Priority: P2)

**Goal**: hooks recebem uma Turn View imutável e idêntica entre produtores; `prepare_context` devolve só a atualização
da própria fatia (JSON, determinística); fatias de outros packs só aparecem se declaradas; validators não têm acesso a
modelos.

**Independent Test**: o mesmo hook do pack de teste, chamado com a view de `turn_view(...)` e com uma `TurnView(...)`
montada à mão com `list`/`dict` mutáveis e os mesmos dados, devolve o mesmo resultado, e as duas views são iguais
(`tests/unit/test_view_immutability.py` e `tests/test_pack.py` do pack de teste).

### Tests for User Story 4 ⚠️

- [X] T045 [P] [US4] Criar `ai-core/packages/contracts/tests/unit/test_view_immutability.py`: montar `TurnView` com `list`/`dict` mutáveis (`messages`, `own_slice` aninhado, `dependency_slices`, `tool_results` com `content` `dict`) e alterar os originais depois não muda a view; atribuir campo levanta `dataclasses.FrozenInstanceError`; atribuir item em `own_slice`, em mapeamentos aninhados ou em `messages[0]` levanta `TypeError` (cenário 1); view da fixture == view montada à mão com os mesmos dados (independent test)
- [X] T046 [P] [US4] Criar `ai-core/packages/contracts/tests/unit/test_contexts_no_services.py`: `dataclasses.fields(ValidatorContext)` e `dataclasses.fields(PackContext)` são exatamente `{"pack_name", "config"}`; nenhum dos dois tem atributo de modelo, provider ou serviço (cenário 3, FR-019); `TurnView` não tem campo além dos 13 do data-model.md, e nenhum campo expõe fatias fora de `dependency_slices` (cenário 2)
- [X] T047 [P] [US4] Criar `ai-core/packages/contracts/tests/conformance/test_conformance_prepare_context.py`: `prepare_context` que devolve `list` → `prepare_context.not_mapping`; `{"quando": datetime(...)}` → `prepare_context.not_json`; `retrieval_filters` não-mapeamento → `prepare_context.retrieval_filters.invalid`; saída aleatória → `prepare_context.non_deterministic`; views default: pack com `depends_on=("outro",)` recebe `dependency_slices == {"outro": {}}` e pack sem `depends_on` recebe `dependency_slices` vazio; hook que lê `view.dependency_slices["nao_declarado"]` → `hook.raised` (cenário 2)

### Implementation for User Story 4

- [X] T048 [US4] Adicionar a `ai-core/packages/contracts/src/ai_core_contracts/testing/conformance.py` a etapa 6 (para cada view, `prepare_context(view, pack_context(...))` duas vezes: resultado `Mapping`; valores aprovados em `is_json_value`; valor de `RETRIEVAL_FILTERS_KEY`, se presente, é mapeamento JSON; as duas chamadas iguais) e as views default `[turn_view(dependency_slices={dep: {} for dep in manifest.depends_on})]` quando `views` não for informado
- [X] T049 [US4] Estender o pack de teste em `ai-core/packages/contracts/tests/fixtures/contract_test_pack/src/contract_test_pack/pack.py` com `prepare_context` devolvendo `{"seen_question": view.question, "retrieval_filters": {"effective_on": view.reference_time.date().isoformat()}}` (usa `reference_time`, nunca o relógio) e estender `tests/test_pack.py` com o independent test da US4 (mesmo resultado com a view da fixture e com uma `TurnView` montada à mão)

**Checkpoint**: US1–US4 completas — o escopo da Fase 0 está entregue

---

## Phase 7: Contratos de serviço (FR-013, FR-014 — sem user story)

**Purpose**: fixar na 0.1 as formas que 006 e 007 implementam, provisórias até a tag, e as suítes mínimas que a
constituição exige para todo seam exposto (research R21, R22)

- [X] T050 [P] Implementar `ai-core/packages/contracts/src/ai_core_contracts/llm.py`: `ChatToolCall`, `ChatMessage`, `ChatTool`, `ChatUsage`, `ChatResponse` e `ChatChunk` (TypedDicts de contracts/python-api.md, com `NotRequired` onde indicado) e `LLMProvider` (`Protocol` `runtime_checkable` com os dois `@overload` de `chat` sobre `stream: Literal[False]`/`Literal[True]` e `model: str` obrigatório); a docstring do módulo marca "provisório até a tag `contracts-v0.1.0` — o plano da 006 pode refinar"
- [X] T051 [P] Implementar `ai-core/packages/contracts/src/ai_core_contracts/mcp.py`: `MCPClient` (`Protocol` `runtime_checkable`: `async discover_tools(aliases: Sequence[str]) -> Sequence[ToolSpec]`; `async execute(alias: str, tool: str, arguments: Mapping[str, JSONValue]) -> ToolResult`), com docstring sobre "só aliases já autorizados, nunca endereços" (FR-014) e o ponto em aberto da associação tool → alias (research R22)
- [X] T052 Reexportar os símbolos de T050 e T051 em `ai-core/packages/contracts/src/ai_core_contracts/__init__.py`; criar `ai-core/packages/contracts/tests/service_fakes.py` com `FakeLLMProvider` (sem stream: `{"message": {"role": "assistant", "content": "pong"}, "finish_reason": "stop"}`; com stream: `{"delta": "po"}` e `{"delta": "ng", "finish_reason": "stop"}`) e `FakeMCPClient` (`discover_tools` → uma `ToolSpec(name="echo", kind="mcp", ...)` sem handler; `execute` → `ToolResult(content=arguments)`), e `ai-core/packages/contracts/tests/unit/test_service_contracts.py`, que confere `isinstance(..., LLMProvider)`/`isinstance(..., MCPClient)` e exercita os falsos com `await`/`async for` (depende de T050, T051 e de T041 — cadeia do `__init__.py`)
- [X] T053 Criar `ai-core/packages/contracts/tests/conformance/test_service_conformance.py`: os falsos de T052 passam em `acheck_llm_provider` e `acheck_mcp_client` sem issue; variantes quebradas produzem exatamente o código de specs/001-core-contracts/contracts/testing-kit.md, "Suítes dos contratos de serviço" — resposta sem `finish_reason` ou com `message.role == "user"` → `llm.response.invalid`; `chat` que levanta exceção → `llm.response.invalid`, com a exceção na mensagem; stream com `finish_reason` num chunk intermediário ou ausente no último → `llm.stream.invalid`; descoberta com `kind="native"` → `mcp.discovery.invalid`; `execute` com `untrusted=False` → `mcp.result.invalid` (depende de T052)
- [X] T054 Implementar `ai-core/packages/contracts/src/ai_core_contracts/testing/services.py` com `acheck_llm_provider(provider, *, model="test-model")` e `acheck_mcp_client(client, *, alias, tool, arguments=None)`, conforme testing-kit.md, "Suítes dos contratos de serviço"; reexportar ambas em `testing/__init__.py` (depende de T053 e de T043 — cadeia do `testing/__init__.py`)

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: fronteiras, superfície pública final, CI e documentação

- [X] T055 Configurar o import-linter em `ai-core/pyproject.toml`: `[tool.importlinter] root_packages = ["ai_core_contracts"]` e `include_external_packages = true`; contrato *forbidden* "contratos não dependem de frameworks do runtime" (`source_modules = ["ai_core_contracts"]`, `forbidden_modules = ["langgraph", "langchain", "fastapi", "qdrant_client", "sqlalchemy"]`); contrato *forbidden* "runtime não importa o kit de testes" (cada módulo de runtime — `ai_core_contracts.pack`, `.tools`, `.retrieval`, `.view`, `.validation`, `.declaration`, `.llm`, `.mcp`, `.compat`, `.deprecation`, `._freeze`, `._version` — proibido de importar `ai_core_contracts.testing`); rodar `uv run lint-imports` até passar (research R20)
- [X] T056 Tornar exato `ai-core/packages/contracts/tests/unit/test_public_api.py`: `set(ai_core_contracts.__all__)` e `set(ai_core_contracts.testing.__all__)` iguais às listas de specs/001-core-contracts/contracts/python-api.md e contracts/testing-kit.md, para que adicionar ou remover símbolo público exija mudança consciente no teste
- [X] T057 Criar `.github/workflows/contracts.yml` (na raiz do repositório; `defaults.run.working-directory: ai-core`; gatilhos `pull_request` e `push` com filtro `ai-core/packages/contracts/**`, `ai-core/pyproject.toml`, `ai-core/uv.lock` e o próprio workflow; `astral-sh/setup-uv`) com os jobs: `lint` (`ruff check`, `ruff format --check`, `mypy`); `test` (matriz Python 3.12/3.13/3.14: `uv sync --python <v>` e `uv run pytest`); `boundaries` (`uv run lint-imports` e `pytest packages/contracts/tests/boundary`); `clean-env` (`uv run python packages/contracts/tools/check_clean_env.py`); `surface` (`fetch-depth: 0`; tag = `git describe --tags --match 'contracts-v*' --abbrev=0`; sem tag → registra "sem linha de base" e termina com sucesso; com tag → `git worktree` da tag, `api_surface.py dump` da tag e do HEAD, `api_surface.py diff` com `--old-version` da tag e `--new-version` do `pyproject.toml`); `frozen-pack` (mesma regra da tag; roda os testes de `packages/contracts/tests/fixtures/contract_test_pack` **da tag** num venv limpo com os contratos do HEAD **só se** `derive_range(<versão da tag>).contains(<versão do HEAD>)` — senão registra "série nova — pack congelado não se aplica" e termina com sucesso, conforme compatibility.md §8) — FR-020, SC-004
- [X] T058 [P] Escrever `ai-core/packages/contracts/README.md`, em português: propósito; dependência recomendada `ai-core-contracts>=0.1,<0.2`; como escrever um pack (`PackBase`, entry point `ai_core.packs`); como testar (`turn_view`, `assert_pack_conforms`); política de versões 0.x (link para specs/001-core-contracts/contracts/compatibility.md); modelo de configuração do import-linter para repositórios de pack, proibindo `ai_core` e `ai_generic` (recomendação da research R17)
- [X] T059 [P] Preencher `ai-core/packages/contracts/CHANGELOG.md` na seção `0.1.0 — não lançada`, com a superfície pública entregue e a nota de que `LLMProvider` e `MCPClient` são provisórios até a tag
- [X] T060 Executar as seções 1–7 de specs/001-core-contracts/quickstart.md em Python 3.14 e 3.12 (`uv run --python 3.12 --isolated ...`) e corrigir qualquer divergência entre o resultado e o "Esperado" de cada seção
- [X] T061 [P] Atualizar a seção "Código" de `CLAUDE.md`: o código de `ai-core-contracts` existe em `ai-core/packages/contracts/`, e os comandos de verificação são os do quickstart da 001

---

## Passada de 2026-10-07: validators que filtram o streaming ([ADR-024](../../docs/adr/ADR-024-validators-filtram-o-streaming.md); research R25)

- [X] T062 `validation.py`: `AnswerStream` e `StreamingValidator`; exportados em `ai_core_contracts`
- [X] T063 Kit: verificação de streaming na etapa de validators; códigos `validator.stream.mismatch` e
  `validator.stream.not_append_only` em `ISSUE_CODES`
- [X] T064 Versão `0.1.1` (`_version.py`, `pyproject.toml`); testes que fixavam `0.1.0` passam a ler a versão
- [X] T065 `tests/conformance/test_conformance_streaming.py` (validator correto, fim que reescreve, resultado
  divergente); `test_public_api.py` com os dois símbolos novos; diff de superfície aditivo (patch) contra a tag

---

## Passada de 2026-10-20: identidade Axon — US6 ([ADR-037](../../docs/adr/ADR-037-a-plataforma-se-chama-axon.md); research R26–R31)

**Goal**: `axon-ai-contracts` 0.2.0, import `axon_ai_contracts`, mesma superfície de 0.1.3, sem nome antigo; consumidores
do workspace atualizados de forma mecânica e CI verde.

**Independent Test**: [quickstart.md §9](quickstart.md) — versão `0.2.0`, `ai_core_contracts` não importável, pack `"0.1"`
incompatível com o nome novo, dependência antiga → `distribution.missing_requirement`, diff contra `contracts-v0.1.2`
(a última tag) com uma mudança de renome e bump `minor` aceito.

### Setup (renome mecânico — bloqueia o resto)

- [X] T066 [US6] `git mv ai-core/packages/contracts/src/ai_core_contracts ai-core/packages/contracts/src/axon_ai_contracts`;
  em `ai-core/packages/contracts/pyproject.toml`, `name = "axon-ai-contracts"`, `version = "0.2.0"` e `description`
  "Contratos públicos do núcleo da plataforma Axon: a única superfície que um pack enxerga."; `_version.py` em `0.2.0` (R26, R27)
- [X] T067 [US6] Script de substituição no scratchpad (não versionado), padrões do mais longo ao mais curto
  (`ai_core_contracts` → `axon_ai_contracts`, `ai-core-contracts` → `axon-ai-contracts`), aplicado só a
  `ai-core/packages/**` (`.py`, `.toml`, `.md`, `.txt`, `.cfg`), `ai-core/pyproject.toml`,
  `.github/workflows/contracts.yml` e `.github/workflows/generic.yml`; nada em `docs/`, `specs/`, nos submódulos nem no
  `ai-core/packages/contracts/CHANGELOG.md` (histórico; a T078 acrescenta a seção 0.2.0) (R31)
- [X] T068 [US6] Faixa e `contract_version` (R31): `ai-core/packages/generic/pyproject.toml` com
  `axon-ai-contracts>=0.2,<0.3` e a fonte do workspace; `contract_version = "0.2"` em
  `ai-core/packages/generic/src/ai_generic/pack.py`; `ai-core/packages/contracts/tests/fixtures/contract_test_pack/pyproject.toml`
  com `axon-ai-contracts>=0.2,<0.3` e o pack dele em `"0.2"`; `"0.1"` → `"0.2"` nos packs de teste e nas asserções de
  `contract_version` de `ai-core/packages/core/tests/**`, `ai-core/packages/contracts/tests/**` (exceto os testes da
  regra de versões com `installed=` explícito: `test_compat_*.py`, `test_deprecation.py`, `test_distribution_check.py`)
  e `ai-core/packages/generic/tests/test_pack.py`; `ai-core/packages/contracts/README.md` com os nomes e a faixa novos
- [X] T069 [US6] `uv lock` em `ai-core/`; `git grep -n "ai_core_contracts\|ai-core-contracts" -- ai-core .github`
  só pode sobrar o que os testes do corte seco usam (T071, T072) (SC-006)

### Tests (antes da implementação de T074–T076)

- [X] T070 [P] [US6] `ai-core/packages/contracts/tests/surface/test_rename.py`: dois snapshots sintéticos com os mesmos
  símbolos e `distribution`/`package` diferentes → exatamente uma `Change("breaking", ...)` com "distribuição
  renomeada", sem `removed_without_deprecation`; `evaluate(..., old_version="0.1.3", new_version="0.2.0")` não falha;
  com `"0.1.4"` falha; um símbolo que muda de forma junto com o renome também é relatado; mesmo nome nos dois lados →
  nenhuma mudança de renome (US6 cenário 4, FR-025)
- [X] T071 [P] [US6] `ai-core/packages/contracts/tests/boundary/test_no_old_name.py`: `importlib.util.find_spec("ai_core_contracts")`
  é `None`; `importlib.metadata.version("axon-ai-contracts") == axon_ai_contracts.__version__ == "0.2.0"` (US6 cenário 1, FR-022)
- [X] T072 [P] [US6] Nomes nas mensagens (FR-023): em `tests/unit/test_compat_rules.py`, `check_compatibility("0.1",
  installed="0.2.0").message == "requer axon-ai-contracts<0.2, instalado 0.2.0"` (cenário 2); em
  `tests/unit/test_distribution_check.py`, `["ai-core-contracts>=0.1,<0.2"]` com `"0.2"` → `distribution.missing_requirement`
  com "declare axon-ai-contracts>=0.2,<0.3" na mensagem, e as duas dependências juntas → só a nova verificada (cenário 3,
  edge case); em `tests/unit/test_deprecation.py`, a mensagem com "desde axon-ai-contracts" (cenário 6)
- [X] T073 [P] [US6] `ai-core/packages/contracts/tests/conformance/`: o pack que prova `imports.forbidden` passa a
  importar `axon_ai`; caso novo com `axon_generic`; caso com `import axon_ai_contracts` e `from axon_ai_contracts.testing
  import ...` sem issue (cenário 5, FR-024)

### Implementation

- [X] T074 [US6] `ai-core/packages/contracts/src/axon_ai_contracts/testing/imports.py`:
  `DEFAULT_FORBIDDEN = ("axon_ai", "axon_generic")`; docstring com `axon_generic` (R29)
- [X] T075 [US6] Conferir que as mensagens de `compat.py`, `deprecation.py` e `testing/distribution.py`
  (`_DISTRIBUTION = "axon-ai-contracts"`) saíram da substituição de T067 com o nome novo e as docstrings também (R28)
- [X] T076 [US6] `ai-core/packages/contracts/tools/api_surface.py` (R30): `dump(package="axon_ai_contracts")` com
  `package` e `package.testing`, snapshot com `package` e `distribution` lida de
  `importlib.metadata.packages_distributions()` ou da distribuição de nome derivado do pacote (editável; reserva: o próprio `package`); `classify` por nome relativo à raiz,
  símbolo exibido com o nome do HEAD, mais a mudança única "distribuição renomeada: <dist antiga> (<pacote antigo>) →
  <dist nova> (<pacote novo>)"; CLI `dump --package`; `evaluate` importa `axon_ai_contracts.compat`; os testes
  existentes de `tests/surface/` ajustados ao formato novo
- [X] T077 [US6] `.github/workflows/contracts.yml`: jobs `surface` e `frozen-pack` descobrem o pacote da linha de base
  em `$base/src/*/__init__.py` e o passam em `dump --package`; `same_series` com `axon_ai_contracts`; cabeçalho com
  `axon-ai-contracts`. `.github/workflows/generic.yml`: lista instalada esperada
  `["ai-generic", "axon-ai-contracts", "typing-extensions"]`
- [X] T078 [US6] `ai-core/packages/contracts/CHANGELOG.md`: título `axon-ai-contracts` e seção `0.2.0` — renome da
  distribuição e do import (breaking, ADR-037, corte seco), varredura de imports com `axon_ai`/`axon_generic`, packs
  passam a `axon-ai-contracts>=0.2,<0.3` e `contract_version = "0.2"`; `tools/check_clean_env.py` com
  `EXPECTED = {"axon-ai-contracts", "typing-extensions", "contract-test-pack"}`

### Polish

- [X] T079 [US6] Suítes (a partir de `ai-core/`): `uv sync && uv run pytest && uv run mypy && uv run ruff check packages
  && uv run ruff format --check packages/contracts && uv run lint-imports`; `check_clean_env.py`; contratos em 3.12 fora
  do workspace; `ai-generic` em ambiente limpo (CLAUDE.md); [quickstart.md §9](quickstart.md), inclusive o diff contra
  `contracts-v0.1.2` (a última tag: a 0.1.3 não foi marcada)
- [X] T080 [P] [US6] `specs/README.md`: linha da 001 (`axon-ai-contracts`, `0.2.0` com o ADR-037) e o nó do diagrama;
  `docs/roadmap.md`, incremento 9.5: 001 feita

**Dependências**: T066 → T067 → T068 → T069; T070–T073 depois de T069 e em paralelo; T074–T078 depois dos testes; T079
por último. As tarefas T001–T065 não mudam.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: sem dependências
- **Foundational (Phase 2)**: depende do Setup — **bloqueia todas as user stories**
- **US1 (Phase 3)**: depende da Foundational
- **US2 (Phase 4)**: depende da Foundational; usa o runner de conformidade e o pack de teste da US1 (T022, T024), que ela estende
- **US3 (Phase 5)**: depende da Foundational; T039 e T043 estendem o runner da US1 (T022); T044 lê `ISSUE_CODES` (T023)
- **US4 (Phase 6)**: depende da Foundational; T047–T049 estendem o runner e o pack de teste da US1
- **Contratos de serviço (Phase 7)**: T050 e T051 dependem só da Foundational e podem correr em paralelo com qualquer
  user story; T052 entra depois de T041 (cadeia do `__init__.py`) e T054 depois de T043 (cadeia do `testing/__init__.py`)
- **Polish (Phase 8)**: depende de todas as fases anteriores (T056 precisa da superfície completa; T057 roda tudo)

### User Story Dependencies

- **US1 (P1)**: independente depois da Foundational — é o MVP
- **US2 (P1)**: a parte de tipos e declaração (T026–T028, T030, T031) independe da US1; a parte de conformidade (T029, T032, T033) estende arquivos da US1
- **US3 (P1)**: regras de versão, depreciação, distribuição e superfície (T034–T038, T040–T042, T044) independem da US1; T039 e T043 estendem o runner da US1
- **US4 (P2)**: os testes de tipo (T045, T046) independem da US1; T047–T049 estendem o runner e o pack de teste da US1

### Within Each User Story

- Os testes são escritos antes e falham antes da implementação
- Tipos e regras puras antes do runner de conformidade; runner antes do pack de teste
- `testing/conformance.py` é tocado por T022, T032, T043 e T048 — **nessa ordem**, nunca em paralelo
- `declaration.py` é tocado por T013, T019 e T031, em sequência; `__init__.py` por T014, T019, T030, T040, T041 e T052, em sequência; `testing/__init__.py` por T023, T043 e T054, em sequência
- O pack de teste é tocado por T024, T033 e T049, em sequência

### Parallel Opportunities

- Setup: T004 e T005
- Foundational: T006, T007, T008, T009 e T013 em paralelo; depois T010 → T011 → T012 → T014
- US1: testes T015–T018 em paralelo; T020 e T021 em paralelo
- US2: testes T026–T029 em paralelo
- US3: testes T034–T039 em paralelo; T042 em paralelo com T040/T041
- US4: testes T045–T047 em paralelo
- Phase 7: T050 e T051 em paralelo com as user stories
- Polish: T058, T059 e T061 em paralelo

---

## Parallel Example: User Story 1

```bash
# Testes da US1 juntos:
Task: "T015 check_declaration de identidade e manifest em tests/unit/test_declaration_identity.py"
Task: "T016 runner de conformidade em tests/conformance/test_conformance_basics.py"
Task: "T017 varredura de imports em tests/conformance/test_imports_check.py"
Task: "T018 fixtures em tests/unit/test_fixtures.py"

# Depois de T019, fixtures e varredura juntas:
Task: "T020 testing/fixtures.py"
Task: "T021 testing/imports.py"
```

## Parallel Example: User Story 3

```bash
Task: "T034 tests/unit/test_compat_rules.py"
Task: "T035 tests/unit/test_compat_differential.py"
Task: "T036 tests/unit/test_deprecation.py"
Task: "T037 tests/unit/test_distribution_check.py"
Task: "T038 tests/surface/test_classification.py"
Task: "T039 tests/conformance/test_conformance_versions.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Phase 1: Setup
2. Phase 2: Foundational (bloqueia tudo)
3. Phase 3: US1
4. **PARAR E VALIDAR**: `uv run python packages/contracts/tools/check_clean_env.py` e `uv run pytest` — um pack é
   construído e testado só com os contratos (promessa do ADR-004)

### Incremental Delivery

1. Setup + Foundational → camada de tipos pronta
2. US1 → pack testável sem o core (MVP)
3. US2 → catálogo completo validável (fixture de carga da 002 e da 010)
4. US3 → compatibilidade, depreciação e detecção de breaking change
5. US4 → Turn View estável provada (base da conformidade da 005)
6. Phase 7 → formas de `LLMProvider` e `MCPClient` e suas suítes mínimas, para a Fase 1 (006) e a Fase 3 (007)
7. Polish → import-linter, superfície exata, CI e documentação

A Fase 1 do roadmap (002, 005, 006, 010...) pode começar quando US1–US4 e a Phase 7 estiverem prontas; a tag
`contracts-v0.1.0` só é criada antes da Fase 4, no repositório `ai-core` separado.

---

## Notes

- [P] = arquivos diferentes, sem dependência de tarefa incompleta
- [Story] liga a tarefa à user story para rastreabilidade
- Verificar que os testes falham antes de implementar
- Commit após cada tarefa ou grupo lógico
- Parar em qualquer checkpoint para validar a story de forma independente
- Fora de escopo nesta lista: US5 (rotina isolada), ampliação das suítes de `LLMProvider` e `MCPClient` (006 e 007),
  contratos do import-linter entre `ai_core` e `ai_generic` (entram quando esses pacotes existirem)
- Revisado em 2026-09-15 após o `/speckit-analyze`: D1 (ADR-014 + constituição 1.2.0), D2 (T052–T054), I1/I2/C1
  (T038, T041, T044), C3 (T029, T032), I3/I6 (T021), I4 (T057), I5 (dependências da Phase 7), I7 (T023), A1 (título da
  US2), C5 (T034)

---

## Passada de 2026-10-21: o pack prepara os próprios dados ([ADR-041](../../docs/adr/ADR-041-o-pack-prepara-os-proprios-dados-no-build.md); research R32–R33)

**Goal**: contratos `0.2.1` com `PreparesData`, `PackBase.prepare` e `PackContext.data_dir`; o kit chama `prepare` duas
vezes; nenhum pack existente muda.

**Independent Test**: a suíte dos contratos em 3.14 e 3.12, e o diff de superfície contra `contracts-v0.2.0` aditivo.

- [X] T081 `pack.py`: `PackContext.data_dir` (`Path` só sob `TYPE_CHECKING`; a varredura de I/O pula esses blocos),
  `PreparesData` e `PackBase.prepare`; `PreparesData` exportado na raiz (R32)
- [X] T082 Kit: `pack_context(..., data_dir=)`; etapa 3b em `conformance.py` com `data_dir` em `acheck_pack` e variantes;
  `hook.not_sync` em `ISSUE_CODES` (R33)
- [X] T083 Versão `0.2.1` (`_version.py`, `pyproject.toml`) e seção `0.2.1` no CHANGELOG
- [X] T084 [P] Testes: `tests/unit/` (`data_dir` default `None` e `Path` aceito; `PackBase.prepare`
  devolve `None`; `isinstance(PackBase(), PreparesData)`); `tests/conformance/test_conformance_prepare.py` (pack sem o
  hook fora de `PackBase` conforme; `prepare` chamado duas vezes no mesmo diretório e os hooks de catálogo o recebem;
  `prepare` que levanta na segunda chamada, que devolve valor e assíncrono); `test_public_api.py` com o símbolo novo
- [X] T085 Diff de superfície contra `contracts-v0.2.0`: aditivo, patch; quickstart da 001 com uma seção do `prepare`

### Notas da execução (ADR-041)

- O deny-list de I/O dos módulos de runtime (`tests/boundary/test_stdlib_only.py`, R20) reprovou `pathlib` em
  `pack.py`; o `Path` foi para `TYPE_CHECKING`, a varredura passou a pular esses blocos e saiu a conferência de tipo de
  `data_dir` em runtime (R32 atualizado).
- Dois testes fixavam `0.2.0` (`test_no_old_name.py`, `test_compat_rules.py`); passaram a ler a versão, como na T064.
- Suítes: contratos 320 passed em 3.14 e em 3.12; diff contra `contracts-v0.2.0` só aditivo, patch; `check_clean_env.py`
  verde; `axon-generic` em ambiente limpo 3.12, 65 passed (a conformidade já exercita o `prepare` herdado).

---

## Passada de 2026-10-22: imagens na conversa ([ADR-044](../../docs/adr/ADR-044-imagens-na-conversa.md); research R34)

**Goal**: contratos `0.2.2` com `Attachment`, `ATTACHMENT_MIME_TYPES`, `ToolResult.attachments` e
`Message.attachments`; nenhum pack existente muda.

**Independent Test**: a suíte dos contratos em 3.14 e 3.12, `check_clean_env.py` e o diff de superfície contra
`contracts-v0.2.1` aditivo.

- [X] T086 `attachments.py`: `Attachment` (id do SHA-256, tipo da lista, `alt` limpo) e `ATTACHMENT_MIME_TYPES`;
  exportados na raiz (R34)
- [X] T087 `ToolResult.attachments` (`tools.py`) e `Message.attachments` (`view.py`)
- [X] T088 Versão `0.2.2` (`_version.py`, `pyproject.toml`) e seção `0.2.2` no CHANGELOG
- [X] T089 [P] Testes: `tests/unit/test_attachments.py` (id determinístico e igual para os mesmos bytes, tipo fora da
  lista e SVG recusados, `data` vazio ou não `bytes`, limpeza do `alt`, `repr` sem os bytes, `ToolResult` com e sem
  anexos, item estranho recusado, `Message` com anexos); `test_public_api.py` com os símbolos novos
- [X] T090 Diff de superfície contra `contracts-v0.2.1`: aditivo, patch
