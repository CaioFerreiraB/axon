---

description: "Task list for 010 — pack genérico de referência (ai-generic), Fase 1"
---

# Tasks: Pack genérico de referência (`ai-generic`)

**Input**: Design documents from `/specs/010-core-generic-pack/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: incluídos. A FR-003 exige a suíte de conformidade publicada pelos contratos, e a constituição exige
verificação de fronteiras de import — os dois são tarefas de teste, e a US1 é inteiramente sobre ser carregável e
conforme.

**Organization**: só a **User Story 1** (Fase 1 do roadmap). A US2 (Assistant genérico com MCP no flow `agentic`) é
Fase 3 e entra junto da 007 e da decisão da FR-005.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: user story da tarefa (US1)
- Todo caminho é relativo à raiz do repositório

## Path Conventions

- Distribuição do pack: `ai-core/packages/generic/` ([research.md](research.md) R1)
- Código do pack: `ai-core/packages/generic/src/ai_generic/`; testes do pack: `ai-core/packages/generic/tests/`
- Teste de carga real: `ai-core/packages/core/tests/packs/integration/` (R8)
- Configuração do workspace: `ai-core/pyproject.toml`; CI: `.github/workflows/`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: a distribuição existe, o workspace a reconhece e as ferramentas a cobrem

- [X] T001 Criar a distribuição em `ai-core/packages/generic/` com os valores exatos de
  [contracts/packaging.md](contracts/packaging.md): `pyproject.toml` (`name = "ai-generic"`, `version = "0.1.0"`,
  `requires-python = ">=3.12"`, `dependencies = ["ai-core-contracts>=0.1,<0.2"]`, `[tool.uv.sources]
  ai-core-contracts = { workspace = true }`, `[project.entry-points."ai_core.packs"] generic =
  "ai_generic.pack:GenericPack"`, `[build-system] requires = ["uv_build>=0.12,<0.13"]`, `build-backend = "uv_build"`),
  `README.md` (uma linha), `src/ai_generic/__init__.py` (docstring: consumidores usam o entry point, não importam o
  módulo), `src/ai_generic/py.typed` vazio, e `__init__.py` em `prompts/`, `tools/` e `validators/`
- [X] T002 Atualizar `ai-core/pyproject.toml` conforme a tabela "Mudanças na raiz do workspace" de
  [contracts/packaging.md](contracts/packaging.md): `[dependency-groups] dev` ganha `"ai-generic"`;
  `[tool.uv.sources]` ganha `ai-generic = { workspace = true }`; `testpaths` ganha `"packages/generic/tests"`; mypy
  `files` ganha `"packages/generic/src"`; `known-first-party` do ruff ganha `"ai_generic"`; `root_packages` do
  import-linter ganha `"ai_generic"`. Rodar `uv sync` (regenera `ai-core/uv.lock`) e conferir a seção 1 do
  [quickstart.md](quickstart.md) (depende de T001)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: o núcleo puro do pack — o que não depende dos contratos e é consumido por todo o resto

**⚠️ CRITICAL**: T003 e T004 precedem a implementação dos hooks (T010, T012)

- [X] T003 [P] Implementar a aritmética pura em `ai-core/packages/generic/src/ai_generic/tools/arithmetic.py`:
  `evaluate(expression: str) -> int | float` com `ast.parse(expression, mode="eval")` e allowlist de nós
  (`Expression`, `BinOp`, `UnaryOp`, `Constant` numérico) e de operadores (`+ - * / // % **`, unários `+ -`),
  conforme [research.md](research.md) R6; recusa nome, chamada, atributo, índice, comparação, operador booleano,
  f-string, comprehension e walrus; limites como constantes do módulo, com os valores de
  [data-model.md](data-model.md): `MAX_LENGTH = 200` caracteres (após `strip()`) e `MAX_EXPONENT = 1000` (magnitude do
  expoente, verificada antes de avaliar a potência); erros sinalizados por exceção própria do módulo
  (`ExpressionError`) com as mensagens da
  tabela de [data-model.md](data-model.md) — `"expressão inválida"`, `"expressão inválida: só aritmética com números
  é permitida"`, `"divisão por zero"`, `"expressão longa demais"`, `"expoente fora do limite"`, `"resultado fora do
  domínio"` (`inf`/`nan`); nunca usa `eval`; sem I/O, sem relógio, sem aleatoriedade. A normalização da entrada
  (`strip()`) acontece aqui, e é essa string que o handler ecoa em `expression` (achado A1 do `/speckit-analyze`)
- [X] T004 [P] Criar o prompt em `ai-core/packages/generic/src/ai_generic/prompts/general.py` como
  `SYSTEM_PROMPT: Final = """..."""` (texto de assistente de uso geral, em português, sem nenhum termo de domínio, de
  organização ou de produto — princípio I; não pede ao modelo confiar em saída de tool — princípio VI) e reexportar
  em `ai-core/packages/generic/src/ai_generic/prompts/__init__.py`. Constante Python, não arquivo de dados: nada a
  declarar no empacotamento e nada que possa faltar no wheel (achado F1 do `/speckit-analyze`)

**Checkpoint**: aritmética e prompt existem e são testáveis sem os contratos

---

## Phase 3: User Story 1 — Pack de referência e fixture de carga (Priority: P1) 🎯 MVP

**Goal**: o pack tem o formato exato de um pack externo, passa na suíte de conformidade dos contratos e é descoberto e
carregado pelo Pack Runtime por entry point, sem nenhum tratamento especial no core.

**Independent Test**: instalar o pack num ambiente só com os contratos e rodar a suíte de conformidade
([quickstart.md](quickstart.md) §5); e carregar o pack pelo `EntryPointPackSource` real (§3).

### Tests for User Story 1 ⚠️

> Escreva estes testes primeiro e confirme que falham antes de implementar. Os testes do pack rodam **sem
> `pytest-asyncio`** (hooks assíncronos com `asyncio.run`), porque no ambiente limpo só existe `pytest`
> ([research.md](research.md) R4).

- [X] T005 [P] [US1] Criar `ai-core/packages/generic/tests/test_arithmetic.py`: casos válidos (`"2 + 3 * 4"` → `14`,
  `"10 / 4"` → `2.5`, `"7 // 2"` → `3`, `"-3 ** 2"`, parênteses, float, módulo); recusas com a mensagem exata da
  tabela de [data-model.md](data-model.md) para nome, chamada (`"__import__('os').system('id')"`,
  `"open('/etc/passwd').read()"`), atributo (`"(1).__class__"`), índice, comparação, booleano, f-string e walrus;
  `"1/0"` e `"5 % 0"` → `"divisão por zero"`; `"1 +"` → `"expressão inválida"`; expressão com 201 caracteres →
  `"expressão longa demais"` (e 200 ainda aceita); `"2 ** 10**9"` → `"expoente fora do limite"` (e `"2 ** 1000"`
  ainda aceita); resultado `inf` (`"1e308 * 10"`) → `"resultado fora do domínio"`; espaços nas extremidades são
  ignorados e o `expression` devolvido vem com `strip()`; determinismo (mesma expressão duas vezes, mesmo valor)
- [X] T006 [P] [US1] Criar `ai-core/packages/generic/tests/test_validator.py` com as três linhas da tabela do
  validator em [data-model.md](data-model.md): resposta com conteúdo → `ok=True`, `issues=()`, `flags=frozenset()`;
  `None` e `"   "`/`"\n"` → `ok=False`, `issues=("resposta vazia",)`, `flags={"empty_answer"}`; em todos,
  `answer is None` e `citations is None` no resultado; determinismo com a mesma Turn View
- [X] T007 [P] [US1] Criar `ai-core/packages/generic/tests/test_pack.py`: `name` e `contract_version` são atributos de
  **classe** (`GenericPack.name == "generic"`, `GenericPack.contract_version == "0.1"`, lidos sem instanciar);
  `manifest()` devolve `PackManifest(name="generic", version="0.1.0")` com `preferred_flow is None`, `depends_on ==
  ()`, `requires_collections == ()` e `config_schema is None` (FR-007); `system_prompt(ctx)` devolve string não vazia
  e o mesmo valor para dois `PackContext` diferentes; `tools(ctx)` devolve exatamente uma `ToolSpec` com
  `name="calculate"`, `kind="native"`, `mutates=False`, `handler` não nulo e `parameters` iguais aos de
  [contracts/generic-pack.md](contracts/generic-pack.md); `retrievers(ctx) == ()` e `reranker(ctx) is None`;
  `validators(ctx)` devolve um validator chamado `non_empty_answer`; o handler chamado com
  `tool_invocation({"expression": "2+2"})` devolve `{"expression": ..., "result": 4}`; `manifest().version` é igual a
  `importlib.metadata.version("ai-generic")` (R12)
- [X] T008 [P] [US1] Criar `ai-core/packages/generic/tests/test_conformance.py`: `assert_pack_conforms(GenericPack(),
  views=[...])` com uma Turn View de resposta preenchida e outra de resposta vazia — todas as nove etapas, incluindo
  imports (`check_imports`) e distribuição (faixa derivada de `ai-core-contracts`), sem `check_distribution=False`
- [X] T009 [P] [US1] Criar
  `ai-core/packages/core/tests/packs/integration/test_packs_generic_entry_point.py`: `PackRuntime` com
  `EntryPointPackSource()` real (nenhuma distribuição falsa) e a configuração do operador com `generic` habilitado;
  conferir a entrada do registry conforme a tabela final de [data-model.md](data-model.md) — `status` `enabled`,
  `version` `"0.1.0"`, `contract_version` `"0.1"`, prompt presente, uma tool `calculate`, um validator
  `non_empty_answer`, nenhum retriever, reranker ausente, `preferred_flow` `None`, `depends_on` e
  `requires_collections` vazios; e o pack ausente da configuração → `disabled`; nenhum caso especial para o nome
  `generic` no código do core (SC-002)

### Implementation for User Story 1

- [X] T010 [US1] Acrescentar a `ai-core/packages/generic/src/ai_generic/tools/arithmetic.py` o handler e a
  especificação: `async def calculate(invocation: ToolInvocation) -> Mapping[str, JSONValue]`, que lê
  `invocation.arguments["expression"]` (ausente ou não `str` → `{"error": "expression precisa ser uma string"}`),
  chama `evaluate` e devolve `{"expression": <normalizada>, "result": <número>}` ou `{"error": <mensagem>}` —
  **nunca levanta exceção** — e `calculate_spec() -> ToolSpec` com `name="calculate"`, `kind="native"`,
  `mutates=False`, `description` e `parameters` de [contracts/generic-pack.md](contracts/generic-pack.md)
  (`additionalProperties: False`, `required: ["expression"]`); não usa `reference_time` nem `request_id` (depende de
  T003)
- [X] T011 [P] [US1] Implementar `ai-core/packages/generic/src/ai_generic/validators/answer.py`: `NonEmptyAnswer` com
  `name = "non_empty_answer"` e `async def validate(view, ctx) -> ValidationResult` conforme a tabela de
  [data-model.md](data-model.md); não altera `answer` nem `citations`; sem acesso a modelo
- [X] T012 [US1] Implementar `ai-core/packages/generic/src/ai_generic/pack.py`: `GenericPack(PackBase)` com `name` e
  `contract_version` como atributos de classe, `manifest()`, `system_prompt()` (devolve `SYSTEM_PROMPT`), `tools()`
  (devolve `(calculate_spec(),)`) e `validators()` (devolve `(NonEmptyAnswer(),)`); é a composition root do pack
  (ADR-012) — só compõe, nenhuma política aqui; sem `prepare_context`, `retrievers` e `reranker` (defaults de
  `PackBase`) (depende de T004, T010, T011)

**Checkpoint**: US1 completa — `uv run pytest packages/generic/tests` e o teste de integração do core passam

---

## Phase 4: Polish & Cross-Cutting Concerns

- [X] T013 Acrescentar a `ai-core/pyproject.toml` os três contratos de import-linter de
  [contracts/packaging.md](contracts/packaging.md) — `ai_generic` não importa `ai_core`; `ai_core` não importa
  `ai_generic`; `ai_generic` não importa `yaml`, `jsonschema`, `fastapi`, `langgraph`, `langchain`, `qdrant_client`
  nem `sqlalchemy` — e rodar `uv run lint-imports` até os três aparecerem como `KEPT` (SC-001)
- [X] T014 [P] Criar `.github/workflows/generic.yml` (raiz do repositório; `working-directory: ai-core`; gatilhos em
  `ai-core/packages/generic/**`, `ai-core/packages/contracts/**`, `ai-core/pyproject.toml`, `ai-core/uv.lock` e no
  próprio workflow, mais `workflow_dispatch`) com os quatro jobs da tabela de
  [contracts/packaging.md](contracts/packaging.md) — `lint`, `test`, `clean-env` (venv 3.12 com apenas
  `packages/contracts`, `packages/generic` e `pytest`; confere que a resolução tem exatamente `ai-core-contracts`,
  `typing-extensions` e `ai-generic`; roda a suíte do pack) e `boundaries` — e acrescentar
  `ai-core/packages/generic/**` aos gatilhos de `pull_request` e `push` de `.github/workflows/core.yml`
- [X] T015 Executar as seções 1–7 de [quickstart.md](quickstart.md) e corrigir divergências entre o resultado e o
  "Esperado"
- [X] T016 [P] Atualizar a seção "Código" de `CLAUDE.md` (a distribuição `ai-generic` existe em
  `ai-core/packages/generic/`, é o pack de referência carregado por entry point e roda também num ambiente só com os
  contratos em 3.12) e a linha da 010 em `specs/README.md` (caminho `packages/generic` e status "Fase 1 implementada
  (US1)")

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup (Phase 1)**: T001 → T002
- **Foundational (Phase 2)**: depende de T001 (os pacotes existem); T003 e T004 são independentes entre si
- **User Story 1 (Phase 3)**: depende de Setup + Foundational
- **Polish (Phase 4)**: T013 depende de T012; T014 e T016 só de a distribuição existir; T015 depende de tudo

### Within User Story 1

- Testes (T005–T009) antes da implementação e falhando
- T010 depende de T003; T012 depende de T004, T010 e T011
- T009 (teste no core) só passa depois de T002 (dev-dependency) e T012

### Parallel Opportunities

- T003 e T004 em paralelo
- T005, T006, T007, T008 e T009 em paralelo (arquivos distintos)
- T011 em paralelo com T010
- T014 e T016 em paralelo com qualquer coisa da Phase 3 já concluída

---

## Parallel Example: User Story 1

```bash
# Testes da US1, juntos:
Task: "Criar tests/test_arithmetic.py (T005)"
Task: "Criar tests/test_validator.py (T006)"
Task: "Criar tests/test_pack.py (T007)"
Task: "Criar tests/test_conformance.py (T008)"
Task: "Criar tests de integração do core (T009)"
```

---

## Implementation Strategy

### MVP (US1, o escopo desta fase)

1. Phase 1: a distribuição existe e o workspace a reconhece
2. Phase 2: aritmética e prompt, puros
3. Phase 3: testes primeiro, depois handler, validator e `pack.py`
4. **PARE e VALIDE**: quickstart §2, §3 e §5 — conformidade, carga real e ambiente limpo
5. Phase 4: fronteiras, CI, quickstart completo e documentação

### Depois desta fase

- Fase 3: US2 (Assistant genérico com MCP no flow `agentic`) e a decisão da FR-005 — se o pack continuar sendo pack,
  ganha `preferred_flow`; se não, `packages/generic` sai do workspace e a fixture de carga do core passa a ser um pack
  mínimo de teste

---

## Notes

- Tarefas `[P]` = arquivos diferentes, sem dependência pendente
- O pack só importa stdlib e `ai_core_contracts` — qualquer outro import quebra T013 e a etapa de imports da
  conformidade
- Nenhuma tarefa cria porta secundária: o pack não faz I/O (princípio XIII, plano §Ports & adapters gate)
- Commit por tarefa ou grupo lógico
