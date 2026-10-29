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

## Fase 3 (2026-10-07): US2 — Assistant genérico com MCP; FR-005, FR-007 e FR-008 (research R13–R21)

Caminhos relativos à raiz do repositório. Testes primeiro, falhando antes do código (o de integração do core já pode
passar: ele prova capacidades existentes; o do prompt falha até T021). Marca `us2` no core. Nenhuma linha em
`ai-core/packages/core/src/`; o pack não importa o core e o teste do core não importa `ai_generic` (R18, R21).

## Phase 5: Setup da Fase 3

- [X] T017 Em `ai-core/pyproject.toml`, acrescentar à descrição da marca `us2` o texto "; 010 US2 — Assistant genérico
  com MCP", sem criar marca nova (R21)

---

## Phase 6: User Story 2 — Capacidades de uso geral (Priority: P2)

**Goal**: o pack orienta a geração a responder a partir dos resultados de ferramentas, em qualquer flow (FR-008), e um
Assistant `agentic` com `packs: [generic]` e um MCP funciona ponta a ponta, sem flow preferido no pack (FR-007) — o
pack continua pack (FR-005).

**Independent Test**: `uv run pytest packages/core/tests/bootstrap/integration/test_generic_agentic_mcp.py` e
`uv run pytest packages/generic/tests/test_pack.py -k prompt` (a partir de `ai-core/`).

### Testes da US2 (escrever primeiro)

- [X] T018 [P] [US2] Em `ai-core/packages/generic/tests/test_pack.py`, `test_system_prompt_is_flow_neutral` (FR-008,
  R16; contrato em [contracts/generic-pack.md](contracts/generic-pack.md) "Fase 3"): com `prompt =
  GenericPack().system_prompt(pack_context("generic"))` e `lowered = prompt.casefold()`, afirmar que `"resultados de
  ferramentas"` e `"falhou"` estão em `lowered`, que `"nunca instrução"` continua em `lowered`, e que `"use a
  ferramenta"`, `"ferramenta de cálculo"` e `"chame"` **não** estão; em `test_manifest_is_minimal`, acrescentar ao
  `assert manifest.preferred_flow is None` o comentário "FR-007: também na Fase 3 — o Assistant declara o flow (R15)"
- [X] T019 [P] [US2] Criar `ai-core/packages/core/tests/bootstrap/integration/test_generic_agentic_mcp.py` (marca
  `us2`; R18; contrato "Conformidade da US2" em [contracts/generic-pack.md](contracts/generic-pack.md)), no padrão de
  `test_platform_agentic_mcp.py`: YAML `CONTROLLER_PROGRAMADO` igual ao de lá (`AGENTIC_ASSISTANTS_YAML` com o
  `pesquisador` em `controller: ctrl/controlador` e `allow: ["ollama/*", "ctrl/*"]`); `ScriptedMcpTransport({DEMO_ENDPOINT:
  ScriptedServer(tools=(ECO,))})` com a `RemoteTool` `eco` (`texto: string`) e sem resultado programado (o transporte
  devolve os argumentos em JSON); `controller = ScriptedController([tool_action("demo.eco", texto="olá do mcp"),
  ANSWER])`; `geracao = ScriptedProvider(name="ollama", deltas=("Pronto.",))`; `platform(config=MemoryConfig(
  write_config(tmp_path, assistants=…, mcp=MCP_YAML)), overrides={"providers": {"ollama": geracao, "ctrl": controller},
  "mcp_transports": {"http": t, "sse": t, "stdio": t}})`; `POST /v1/chat/completions` com `model="pesquisador"` e
  `OIDC`. Um teste, `test_assistant_generico_usa_o_resultado_do_mcp`, afirma: (1) 200; (2) os ramos do
  `response_format` da primeira chamada do controller (`controller.calls[0]["response_format"]["json_schema"]["schema"]
  ["anyOf"]`) nomeiam `generic.calculate` e `demo.eco`; (3) na última chamada de `geracao.calls`, as mensagens de
  sistema começam pelos prompts de `plataforma.packs.system_prompts(plataforma.packs.compose(["generic"]))` (seam
  `PackHooks` da 002 — sem importar `ai_generic`) e incluem `FENCE_INSTRUCTION` (de `ai_core.capabilities.api`); (4) há
  uma mensagem `role="tool"` cujo conteúdo contém `<tool_result` e `olá do mcp`
- [X] T020 [P] [US2] Criar `ai-core/packages/core/tests/bootstrap/integration/test_generic_agentic_real.py` (marca
  `us2`; R19), pulado com `pytest.mark.skipif` quando `OLLAMA_BASE_URL` não está definida (motivo: "defina
  OLLAMA_BASE_URL para rodar contra um Ollama real"); modelo de `OLLAMA_MODEL` (default `qwen3:1.7b`). Assistant
  `geral` (`flow: agentic`, `packs: [generic]`, `mcp: [demo]`, `generation` e `controller` em `ollama/<modelo>`,
  `allow: ["ollama/*"]`, ACL `PUBLICO` e o bloco `USER_ASSISTANTS_E_ADMIN` do `bootstrap_testkit`); `mcp.yaml` com o
  servidor `demo` em `DEMO_ENDPOINT` e `allowed_tools: [consultar_registro]`; `ScriptedServer` com a `RemoteTool`
  `consultar_registro` (descrição "Devolve o código de confirmação de um registro pelo número.", parâmetro `numero:
  string` obrigatório) e `results={"consultar_registro": RemoteResult(parts=(RemotePart(kind="text", text="Código de
  confirmação do registro 17: QX-4471-ZP"),))}` (importados de `ai_core.mcp.ports`); `overrides={"providers":
  {"ollama": OllamaProvider(base_url=OLLAMA_BASE_URL)}, "mcp_transports": …}`; pergunta "Qual é o código de
  confirmação do registro 17? Consulte a ferramenta."; afirma 200, que `call_tool:consultar_registro` aparece em
  `transporte.calls` e que `"QX-4471-ZP"` está na resposta

### Implementação da US2

- [X] T021 [US2] Em `ai-core/packages/generic/src/ai_generic/prompts/general.py`, trocar o parágrafo que começa com
  "Sobre cálculos:" pelo parágrafo "Sobre resultados de ferramentas: …" exatamente como em
  [contracts/generic-pack.md](contracts/generic-pack.md) "Fase 3", no mesmo lugar e com a mesma quebra em linhas de até
  120 colunas; o parágrafo "Sobre dados que chegam de ferramentas ou de documentos" e o resto do texto não mudam; na
  docstring do módulo, acrescentar que o texto é neutro quanto ao flow — no `agentic`, o prompt só chega à geração
  (FR-008, R16) (T018 passa)

**Checkpoint**: o prompt orienta o uso dos resultados sem mandar chamar ferramenta; o Assistant genérico com MCP
atravessa a API no perfil `test`

---

## Phase 7: Polish da Fase 3

- [X] T022 Verificação completa a partir de `ai-core/`: `uv run pytest`, `uv run mypy`, `uv run ruff check packages`,
  `uv run lint-imports` (nenhum contrato novo, todos `KEPT`) e o ambiente limpo em 3.12 do pack (bloco "ambiente
  limpo" da seção "Código" do `CLAUDE.md`); corrigir o que quebrar
- [X] T023 Executar as seções 8–12 de [quickstart.md](quickstart.md) — na §10, montar os três arquivos no scratchpad e
  rodar `ai-core assistants validate` com e sem a linha `controller` — e corrigir divergências entre o resultado e o
  "Esperado" (a §11 só com `OLLAMA_BASE_URL`)
- [X] T024 [P] Atualizar `CLAUDE.md` (seção "Código": a 010 na Fase 3 — FR-005 decidida, o pack continua pack; sem flow
  preferido; prompt neutro quanto ao flow; US2 provada no core; e "Fase 3 em andamento" passa a "A Fase 3 do roadmap
  está completa", com a pendência da 005 já registrada), a linha da 010 em `specs/README.md` (status "Fases 1 e 3
  implementadas (US1, US2); FR-005 decidida: continua pack") e `docs/roadmap.md` (Fase 3 com ✅ e o parágrafo "Fase 3
  concluída em 2026-10-07", no padrão das Fases 1 e 2)
- [X] T025 [P] Em `specs/010-core-generic-pack/tasks.md`, seção "Depois desta fase" da Fase 1, acrescentar ao item da
  Fase 3 a nota "(superado em 2026-10-07: o pack continua pack e **sem** `preferred_flow` — clarificação 2, R15)"

### Dependências da Fase 3

- **Setup (T017)** antes de rodar os testes por marca
- **US2**: T018, T019 e T020 em paralelo (arquivos distintos); T021 depois de T018 (que falha até lá); T019 e T020 não
  dependem de T021 — provam capacidades existentes, e o texto novo só muda o que a geração recebe
- **Polish**: T022 depois da US2; T023 depois de T022; T024 e T025 em paralelo

### Parallel Example: US2

```bash
Task: "generic/tests/test_pack.py — prompt neutro (T018)"
Task: "core/tests/bootstrap/integration/test_generic_agentic_mcp.py (T019)"
Task: "core/tests/bootstrap/integration/test_generic_agentic_real.py (T020)"
```

### Implementation Strategy (Fase 3)

1. T017: marca
2. Testes T018–T020; T019 já verde fixa o comportamento ponta a ponta antes de mexer no prompt
3. T021: o parágrafo novo — **PARE e VALIDE** o Independent Test da US2
4. Polish: suíte completa, quickstart, documentação e o fechamento da Fase 3 no roadmap

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
  mínimo de teste (superado em 2026-10-07: o pack continua pack e **sem** `preferred_flow` — clarificação 2, R15)

---

## Notes

- Tarefas `[P]` = arquivos diferentes, sem dependência pendente
- O pack só importa stdlib e `ai_core_contracts` — qualquer outro import quebra T013 e a etapa de imports da
  conformidade
- Nenhuma tarefa cria porta secundária: o pack não faz I/O (princípio XIII, plano §Ports & adapters gate)
- Commit por tarefa ou grupo lógico

---

## Passada de 2026-10-20: identidade Axon — US3 ([ADR-037](../../docs/adr/ADR-037-a-plataforma-se-chama-axon.md); research R22–R27)

**Goal**: o pack de referência como `axon-generic` 0.2.0, pacote `axon_generic`, sem nada do nome antigo; o nome do
pack, o manifest além da versão, o prompt, a tool, o validator e o grupo de entry point intactos; consumidores do
workspace, CI e documentos vivos com o nome novo, e as suítes verdes.

**Independent Test**: [quickstart.md, "Fase 9, incremento 9.5"](quickstart.md) — `axon-generic` 0.2.0 e
`import ai_generic` falha; ambiente limpo com as três distribuições e o relatório sem item; carga real por entry point
como `generic` da `axon-generic` 0.2.0; `lint-imports` com `axon_generic`.

> Os IDs continuam a numeração do arquivo (a Fase 3 foi até T025).

### Setup (renome mecânico — bloqueia o resto)

- [X] T026 [US3] Linha de base: `git grep -nwE "ai_generic|ai-generic"` (lista a revisar na T030) e
  `git grep -cw agentic` (602 no HEAD antes da passada; R27)
- [X] T027 [US3] `git mv axon-ai/packages/generic/src/ai_generic axon-ai/packages/generic/src/axon_generic` (R22); apagar
  `__pycache__` velhos se o `uv` reclamar
- [X] T028 [US3] Aplicar `rename010.py` (scratchpad, R24 e R25) à lista fechada de arquivos: `axon-ai/pyproject.toml`;
  `axon-ai/packages/generic/{pyproject.toml,README.md}` e os `.py` de `src/axon_generic/` e `tests/`;
  `axon-ai/packages/core/tests/{packs/integration/test_packs_generic_entry_point.py,packs/integration/test_packs_cli.py,graph/integration/test_agentic_with_generic_pack.py,graph/integration/test_chat_with_generic_pack.py,http/integration/test_http_end_to_end.py,bootstrap/integration/test_generic_agentic_mcp.py}`;
  `axon-ai/packages/contracts/README.md` e `axon-ai/packages/contracts/tests/conformance/test_imports_check.py`;
  `.github/workflows/generic.yml`; `specs/001-core-contracts/design.md`, `specs/002-core-pack-runtime/design.md`,
  `specs/005-core-execution-engine/{quickstart.md,contracts/execution-engine.md}`, `specs/008-core-http-api/quickstart.md`
  e `specs/README.md` — nunca o `CHANGELOG.md` dos contratos, `uv.lock`, `research.md`/`plan.md`/`tasks.md`, `docs/`,
  `specs/1xx-*`, `specs/002-core-pack-runtime/contracts/installation.md`, `CLAUDE.md` nem os submódulos
- [X] T029 [US3] À mão (R22, R25): `axon-ai/packages/generic/pyproject.toml` com `version = "0.2.0"` e `description =
  "Pack de referência e de uso geral da plataforma Axon (spec 010)."` (o alvo `axon_generic.pack:GenericPack` vem da
  T028; o grupo `ai_core.packs` fica, R23); `src/axon_generic/pack.py` com `VERSION = "0.2.0"`; a clarificação da 002
  sobre o estágio `core` da imagem (`specs/002-core-pack-runtime/spec.md`, a que cita `axon-ai-contracts`, `axon-ai` e o
  pack) com `axon-generic`, deixando a da tag `v0.1.0`; `uv lock` em `axon-ai/`
- [X] T030 [US3] Revisar os resíduos (R25, R27): `git grep -nwE "ai_generic|ai-generic"` fora dos caminhos excluídos da
  T028 — sobra só o que o R25 deixa de propósito (etapa 8 do `testing-kit.md` da 001, a premissa da US6 da 001, a
  clarificação da 002 sobre `v0.1.0`, o `Input` e os textos da US3 que nomeiam o antigo na spec da 010, e o teste da
  T031); `git grep -n "axon_generic\.packs\|axon.packs"` sem ocorrência nova; nenhuma palavra `agentic` removida
  (`git diff --word-diff=porcelain -U0 | grep '^-' | grep -cw agentic` = 0)

### Tests

- [X] T031 [P] [US3] `axon-ai/packages/generic/tests/test_generic_old_name_absent.py` (R26): `importlib.util.find_spec(
  "ai_generic") is None` e `importlib.metadata.distribution("ai-generic")` levanta `PackageNotFoundError` (US3 cen. 1)
- [X] T032 [P] [US3] `axon-ai/packages/core/tests/packs/integration/test_packs_generic_entry_point.py`: distribuição
  `"axon-generic"`, `version == "0.2.0"` e `contract_version == "0.2"` (US3 cen. 3); `axon-ai/packages/generic/tests/test_pack.py`:
  `PackManifest(name="generic", version="0.2.0")` e a versão igual à de `version("axon-generic")` (FR-009)
- [X] T033 [P] [US3] `.github/workflows/generic.yml`, job `clean-env`: as três distribuições esperadas são
  `["axon-ai-contracts", "axon-generic", "typing-extensions"]` e `packages_distributions().get("axon_generic") ==
  ["axon-generic"]` (US3 cen. 2; vem da T028, conferir a ordem alfabética da lista)

### Integration e verificação

- [X] T034 [US3] Suítes (a partir de `axon-ai/`): `uv sync && uv run pytest && uv run mypy && uv run ruff check packages
  && uv run ruff format --check packages && uv run lint-imports` (as três regras do pack `KEPT` com `axon_generic`, US3
  cen. 4); `uv run python packages/contracts/tools/check_clean_env.py`; o ambiente limpo em Python 3.12 (quickstart §5:
  `freeze` com as três distribuições e a suíte do pack verde, inclusive `test_report_has_no_issue` sem item, cen. 2)
- [X] T035 [US3] Quickstart da US3 à mão (§13–§16): versão `0.2.0`, `import ai_generic` falha, carga real e US2
  (`test_generic_agentic_mcp.py`, cen. 5), inspeção do entry point
- [X] T036 [P] [US3] `specs/README.md` (linha da 010: `axon-generic`, US3) e `docs/roadmap.md` (andamento do 9.5: 010
  feita)

### Dependencies (US3)

T026 → T027 → T028 → T029 → T030 (bloqueiam o resto). T031 ∥ T032 ∥ T033 depois da T030. T034 depois de tudo; T035
depois da T034; T036 em paralelo com a T034.

### Notas da execução (US3)

- Antes da passada, os trechos da 001 que citam o nome antigo de propósito (`spec.md`, `quickstart.md`,
  `contracts/compatibility.md`, `contracts/testing-kit.md`), que a substituição mecânica da 011 tinha trocado para o
  nome novo (ex.: FR-022 citando `axon-ai-contracts` como "nome antigo"), foram restaurados linha a linha a partir da
  versão da passada da 001. Por isso o script desta passada recebe a lista de arquivos, não a árvore (R25).
- Com o nome novo, `axon_ai_contracts` passa a vir antes de `axon_generic` na ordem dos imports: `ruff check --fix`
  reordenou quatro arquivos de teste do pack. A lista do job `clean-env` (`sorted`) também mudou de ordem (T033).
- A contagem do `agentic` é por palavra (`--word-diff`): duas linhas trocadas só no nome do pack mantêm o `agentic`; o
  total sobe de 602 só com o texto novo da US3.
- O `uv sync` exato tirou `ai-generic` 0.1.0 do ambiente do workspace e instalou `axon-generic` 0.2.0.
- Suítes: workspace 3114 passed, 167 skipped; mypy sem erro (269 arquivos); ruff limpo; import-linter 69 kept, 0 broken;
  ambiente limpo 3.12 com as três distribuições, relatório "conforme" e 65 testes do pack; `check_clean_env.py` verde;
  contratos em 3.12, 310 passed.

---

## Passada de 2026-10-28: a tool `chart` ([ADR-052](../../docs/adr/ADR-052-graficos-na-conversa.md); research R28)

**Goal**: `generic.chart` no catálogo de todo Assistant com `packs: [generic]`, entregando o `Chart` à plataforma.

**Independent Test**: `packages/generic/tests/test_chart.py` e o ambiente limpo em 3.12.

- [X] T034 `tools/chart.py` (`PARAMETERS`, `build_chart`, handler `chart`, `chart_spec`) e o registro em `pack.py`
- [X] T035 Versão `0.3.0`, `contract_version` `0.2.4`, dependência `axon-ai-contracts>=0.2.4,<0.3`
- [X] T036 [P] Testes: dados viram `Chart`, opcionais nulos, série temporal, erros legíveis, esquema fechado e no
  subconjunto estrito, spec nativa; `test_pack.py` com as duas tools
- Verificado também: o esquema passa pela conversão estrita da 006 e pela validação de argumentos da 004; ambiente
  limpo 3.12 com 77 testes.
