# Research — 010 Pack genérico (`ai-generic`), Fase 1 (US1)

Insumos pré-aprovados: [design.md](design.md) (atualizado em 2026-09-17), [spec.md](spec.md) §Clarifications,
[ADR-004](../../docs/adr/ADR-004-contratos-no-repo-do-core.md),
[ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md),
[ADR-014](../../docs/adr/ADR-014-politica-versoes-0x-contratos.md), constituição (princípios I, II, VI, XII, XIII).
Código de referência já implementado: `ai-core-contracts` 0.1.0 (spec 001) e o Pack Runtime (spec 002).

## R1 — Pasta e membro do workspace

**Decision**: a distribuição mora em `ai-core/packages/generic/`, ao lado de `packages/contracts` e `packages/core`;
o `members = ["packages/*"]` da raiz já a inclui, sem mudança na declaração do workspace.

**Rationale (ADR-004, clarificação de 2026-09-17)**: o ADR-004 fixa as três distribuições do workspace sem fixar
caminho, e o glob criado na Fase 0 já previa o pack ("core e generic entram na Fase 1"). A fronteira com o core é
provada pelo `pyproject.toml` e pelo import-linter (R9), não pela posição da pasta.

**Alternatives**: `packs/generic/`, como dizia a redação original do design.md — exigiria acrescentar `packs/*` aos
membros e um gatilho de CI a mais, sem ganho de isolamento. Rejeitada na clarificação; a linha do design.md foi
atualizada com a nota de origem.

## R2 — Dependência de `ai-core-contracts`

**Decision**: `dependencies = ["ai-core-contracts>=0.1,<0.2"]` mais `[tool.uv.sources] ai-core-contracts =
{ workspace = true }`.

**Rationale (ADR-014, 001 FR-018)**: a faixa é a derivada de `contract_version = "0.1"`; a etapa de distribuição da
suíte de conformidade trata dependência sem faixa como erro (`distribution.range_too_wide`) e referência direta
também (`distribution.direct_reference`). A fonte do workspace preserva a intenção original do design ("mesmo
commit") no desenvolvimento. É exatamente o que o `contract_test_pack` da 001 já declara — e o que o `ai-scouting`
vai copiar.

**Alternatives**: sem faixa e conformidade com `check_distribution=False` (o pack de referência deixaria de exercitar
a verificação criada para packs); pin `==0.1.0` (todo patch aditivo dos contratos exigiria bump aqui).

## R3 — Piso de Python do pack

**Decision**: `requires-python = ">=3.12"`, o mesmo piso de `ai-core-contracts` — não o `>=3.14` do core. A suíte do
pack roda em 3.14 dentro do workspace e em 3.12 fora dele.

**Rationale (FR-001, 001 FR-017)**: o pack depende só dos contratos; herdar o piso do core diria que um pack precisa
da versão de Python que o core escolheu, o oposto do que este pack existe para demonstrar. O piso 3.12 também é o que
torna executável o *Independent Test* da US1 ("instalar o pack num ambiente só com contratos").

**Alternatives**: `>=3.14` (amarra o pack ao core e contradiz a FR-001); faixa fechada `>=3.12,<3.15` (nada exige
teto, e teto por precaução envelhece mal).

## R4 — Ambiente limpo (Independent Test da US1)

**Decision**: um job de CI cria um venv 3.12, instala apenas `packages/contracts`, `packages/generic` e `pytest`,
confere que a resolução tem exatamente três distribuições (`ai-core-contracts`, `typing-extensions`, `ai-generic`) e
roda a suíte do pack. Consequência: **os testes do pack não usam `pytest-asyncio`** — chamam hooks assíncronos com
`asyncio.run`, como os do `contract_test_pack`.

**Rationale (princípio XII, 001 SC-001)**: é a mesma verificação que a 001 faz com `check_clean_env.py`, aplicada ao
pack real. Fica inline no workflow porque a ferramenta da 001 tem o pack de teste fixo, e parametrizá-la seria editar
um módulo alheio por conveniência de teste deste (princípio II).

**Alternatives**: acrescentar `--pack` ao `check_clean_env.py` da 001 (mexe em outro módulo); script próprio em
`packages/generic/tools/` (duplica 40 linhas de infraestrutura de teste num pack que deve parecer um pack).

## R5 — Capacidades da v1

**Decision**: `system_prompt` de assistente geral em português; uma tool nativa `calculate` (aritmética
determinística); um validator `non_empty_answer`. Manifest apenas com `name` e `version`. Sem `prepare_context`,
retriever, reranker, `config_schema`, `depends_on`, `requires_collections` nem porta secundária.

**Rationale (clarificação de 2026-09-17, FR-006, FR-007)**: três hooks de catálogo mais o `manifest()` cobrem a
suíte de conformidade e a carga real sem inventar I/O. A aritmética é o caso de uso que o próprio roadmap descreve:
no hardware alvo o modelo local tem ~1.7B e "tool calling nesse porte é nominal" (design da 006), mas cálculo é
onde ele erra de forma verificável — e é capacidade sem domínio (princípio I). É também o que faz o pack agregar
algo além de prompts, sem antecipar a decisão da FR-005 (Fase 3).

**Alternatives**: `echo` (a fixture dos contratos já prova esse caminho; não agregaria nada ao pack de produto);
tool que devolve a data de referência do turno (útil para modelo pequeno, mas quase um echo do `reference_time`);
nenhuma tool, só prompt (responderia a FR-005 por omissão, na fase errada).

## R6 — Determinismo e segurança da tool `calculate`

**Decision**: a expressão é analisada com `ast.parse(..., mode="eval")` e avaliada por um interpretador próprio com
allowlist de nós (`Expression`, `BinOp`, `UnaryOp`, `Constant` numérico) e de operadores (`+ - * / // % **`, unários
`+ -`), com limites de tamanho da expressão e de magnitude do expoente. Nome, chamada, atributo, índice e
compreensão são recusados. Erro de sintaxe, operador não permitido, divisão por zero ou limite excedido devolvem um
resultado com campo de erro — o handler não levanta exceção.

**Rationale (princípios V e VI)**: os argumentos vêm do modelo, logo são conteúdo não-confiável; `eval`, mesmo com
`globals` vazio, dá execução arbitrária por atributos. Resultado com erro em vez de exceção mantém a tool
determinística e deixa a política de falha com o gateway (004), que ainda não existe.

**Alternatives**: `eval` com `__builtins__` vazio (contorno conhecido via dunder); biblioteca externa de expressões
(dependência nova num pack cuja razão de existir é depender só dos contratos).

## R7 — Organização interna do pack

**Decision**: `pack.py` é a composition root do pack (instancia o validator e monta os `ToolSpec`); o prompt vive em
`prompts/general.py` como constante Python, a aritmética pura em `tools/arithmetic.py` com o handler assíncrono ao
lado, o validator em `validators/answer.py`. Sem `ports.py` e sem `adapters/`.

O prompt é constante Python, e não um `.md` lido com `importlib.resources`, por causa do achado F1 do
`/speckit-analyze`: arquivo de dados dentro do pacote depende de configuração de empacotamento e falharia apenas no
ambiente instalado (quickstart §5), tarde e de forma confusa. Constante não tem esse modo de falha.

**Rationale (ADR-012, princípio XIII)**: módulo sem I/O pode omitir portas e adapters; o centro (aritmética,
validação) fica puro e testável sem o contrato, e o `pack.py` só compõe. Se uma tool passar a fazer I/O, a porta
nasce em `ports.py` e o cliente em `adapters/`, sem mudar o `pack.py` como ponto de composição.

**Alternatives**: tudo em `pack.py` (mistura política e composição num arquivo que é a fachada do pack);
`domain/` em vez de `tools/`+`validators/` (nomear de `domain/` o que os contratos já chamam de tool e validator
troca vocabulário sem ganho).

## R8 — Onde a carga real é provada

**Decision**: `ai-generic` entra no grupo `dev` da raiz do workspace (com `[tool.uv.sources] ai-generic =
{ workspace = true }`), e o teste vive em `ai-core/packages/core/tests/packs/integration/`, carregando o pack com
`EntryPointPackSource` + `InMemoryPackConfigSource` — sem nenhum caso especial no código do core. A suíte de
conformidade roda nos testes do próprio pack, sem tocar no core.

**Rationale (clarificação de 2026-09-17, SC-002)**: é a leitura literal do SC-002 e reaproveita o job `test` do
`core.yml`. Dependência de desenvolvimento não é import: nenhum módulo de `ai_core` importa `ai_generic`, e o
import-linter (R9) prova isso.

**Alternatives**: teste dentro do pack importando o `EntryPointPackSource` do core (inverte a dependência que a
constituição e o ADR-004 proíbem, e suja o ambiente limpo do R4); suíte ponta a ponta separada na raiz do workspace
(é onde a 011 US3 vai morar, mas criar essa infraestrutura agora antecipa a 011 sem necessidade).

## R9 — Fronteiras de import

**Decision**: `root_packages` da raiz passa a incluir `ai_generic`, com três contratos novos de import-linter:
`ai_generic` não importa `ai_core`; `ai_core` não importa `ai_generic`; `ai_generic` não importa frameworks de
infraestrutura (`yaml`, `jsonschema`, `fastapi`, `langgraph`, `langchain`, `qdrant_client`, `sqlalchemy`).

**Rationale (SC-001, princípios II e XIII)**: o ADR-004 aceita que, dentro do workspace, a fronteira entre pack e
core dependa de lint — então o lint precisa existir nas duas direções. A etapa de imports da suíte de conformidade
(`check_imports`, 001) cobre o mesmo do lado do pack, dentro dos testes dele.

**Alternatives**: confiar só no `check_imports` da conformidade (não pega a direção core → pack); separação física em
repositórios (é o que acontece antes da Fase 4; não muda o que a Fase 1 precisa provar).

## R10 — CI

**Decision**: workflow novo `.github/workflows/generic.yml` com os jobs `lint`, `test`, `clean-env` (R4) e
`boundaries`; e os gatilhos do `core.yml` passam a incluir `ai-core/packages/generic/**`, porque o teste de
integração do core carrega o pack.

**Rationale**: um workflow por distribuição é o padrão já estabelecido (`contracts.yml`, `core.yml`), e mantém o
sinal legível quando o pack quebra por conta própria. O gatilho cruzado no `core.yml` evita que uma mudança no pack
passe sem rodar o teste que depende dele.

**Alternatives**: um job dentro do `core.yml` (esconde o pack sob o CI do core e acopla gatilhos que deveriam ser
independentes quando o pack sair do repositório).

## R11 — Configuração do workspace na raiz

**Decision**: `testpaths` ganha `packages/generic/tests`; mypy `files` ganha `packages/generic/src`;
`known-first-party` do ruff ganha `ai_generic`; o `uv.lock` é regerado por `uv sync`.

**Rationale**: é o mesmo conjunto de ajustes que a 002 fez ao criar `packages/core` (tarefa T002 dela); sem isso o
pack ficaria fora de tipos, lint e suíte do workspace.

**Alternatives**: manter o pack fora das ferramentas do workspace e verificá-lo só no ambiente limpo (perde mypy
strict e ruff no código que serve de exemplo para todo pack futuro).

## R12 — Identidade e versão

**Decision**: distribuição `ai-generic` 0.1.0, pacote `ai_generic`, entry point
`generic = "ai_generic.pack:GenericPack"` no grupo `ai_core.packs`; `name = "generic"`, `contract_version = "0.1"`
como atributos de classe; `PackManifest(name="generic", version="0.1.0")`. Um teste do pack compara
`manifest().version` com a versão da distribuição instalada.

**Rationale (002 FR-017, R2)**: o Pack Runtime exige que o nome do entry point seja igual ao `name` da classe e lê
identidade sem instanciar; a faixa de contratos é derivada da `contract_version`, então ela precisa ser a série real.
O teste de consistência evita o manifest envelhecer em relação ao `pyproject.toml`.

**Alternatives**: derivar `version` de `importlib.metadata` dentro do `manifest()` (leitura de metadados durante a
carga, em troca de nada — o teste resolve com determinismo).
