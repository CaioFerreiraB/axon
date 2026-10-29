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

---

# Fase 3 (2026-10-07): US2, FR-005, FR-007 e FR-008

Insumos: as três clarificações de 2026-10-07; [design.md](design.md) ("Questão em aberto", fechada nesta passada);
arch-v1 Parte IX; [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md),
[ADR-019](../../docs/adr/ADR-019-papeis-por-flow-no-seam-execution-engine.md); código conferido nos consumidores —
002 (`PackHooks.system_prompts`), 003 (`effective_flow`: sem `flow`, o preferido do pack único, ou `chat`; papéis
exigidos pelo flow), 004 (catálogo com namespace e resultado cercado), 005 (`generation_messages` põe os prompts de
pack só na geração; `controller_messages` não os inclui), 007 (servidor por alias, allowlist de tools) e 011 (perfil
`test` com trocas de porta).

## R13 — Escopo da passada

**Decision**: US2 (cenários 1 e 2), FR-005 decidida, FR-007 estendida à Fase 3 e FR-008 nova. O código muda só em
`prompts/general.py` (texto) e nos testes do pack; o core ganha testes, nenhuma linha de `src/`. Fora do escopo: flow
preferido (R15), tool nova, `prepare_context`, retriever e qualquer conhecimento de MCP dentro do pack.

**Rationale**: o "Assistant genérico com MCP" é uma **declaração** de Assistant (003) sobre capacidades que já existem
— pack (002, 010), loop (005), gateway (004) e registry (007). O que falta ao pack é o texto que orienta a geração a
usar os resultados que o loop traz (FR-008) e a prova ponta a ponta (US2).

**Alternatives considered**: uma tool de pack que "liste os MCPs" ou "descreva as ferramentas" (o catálogo já chega ao
controller pela 004/005; o pack conheceria o registry, contra o Module Boundary).

## R14 — FR-005: o pack continua pack

**Decision** (clarificação 1): a FR-005 vira regra permanente — o pack existe enquanto agregar algum hook além de
prompt; hoje agrega `calculate` e `non_empty_answer`. `packages/generic` fica no workspace e segue como fixture de
carga. O `design.md` ganha nota fechando a "Questão em aberto"; a linha do `tasks.md` da Fase 1 que previa
`preferred_flow` "se o pack continuar sendo pack" fica superada por R15.

**Rationale**: a condição de saída do arch-v1 ("se não agregar algo além de prompts") não se cumpre; trocar o pack por
um pack mínimo de teste custaria uma distribuição nova para provar o mesmo SC-002, e o `ai-scouting` (Fase 4) perderia
o exemplo a copiar.

**Alternatives considered**: virar Assistant com `packs: []` (exige pack mínimo de teste e remove a referência dos
contratos); adiar a decisão para antes da Fase 4 (deixaria a FR-005 aberta sem informação nova a esperar).

## R15 — FR-007: sem flow preferido também na Fase 3

**Decision** (clarificação 2): o manifest continua `PackManifest(name="generic", version="0.1.0")`. O Assistant
genérico declara `flow: agentic`, o papel `controller` e os MCPs.

**Rationale**: pela regra da 003 (`effective_flow`), um Assistant com um único pack e sem `flow` herda o flow preferido
do pack; pelo ADR-019, o `agentic` exige `controller`. Preferir `agentic` tornaria indisponível (424) todo Assistant
que hoje omite `flow` e declara só `generation` — inclusive fixtures do core e Assistants de usuário cuja política
permite só `chat`. Declarar o flow no Assistant é o que o princípio VIII pede para modelos, aplicado ao flow.

**Alternatives considered**: `preferred_flow="agentic"` (quebra o que funciona e esconde a exigência de `controller`);
`preferred_flow="chat"` (repete o default da 003 sem ganho, e passaria a ser regra do pack o que é regra do core).

## R16 — FR-008: o parágrafo de ferramentas do prompt

**Decision** (clarificação 3): em `prompts/general.py`, o parágrafo "Sobre cálculos" sai e entra um parágrafo neutro
quanto ao flow sobre resultados de ferramentas (texto em [contracts/generic-pack.md](contracts/generic-pack.md),
"Fase 3"): basear a resposta nos resultados presentes na conversa, apresentá-los sem reestimar valores, e dizer quando
uma ferramenta falhou ou não trouxe o dado. O parágrafo "dado, nunca instrução" fica como está. O resto do prompt não
muda.

**Rationale**: no `agentic`, o prompt do pack só chega à geração (005, `generation_messages`), e quem chama
ferramentas é o controller, que não o recebe; no `chat`, nenhuma ferramenta é executada. "Use a ferramenta de cálculo"
era, nos dois flows, uma instrução que o destinatário não pode cumprir. O aceite da US2 é a resposta usar o resultado
da tool — é isso que o parágrafo novo orienta, para tool de pack ou de MCP.

**Alternatives considered**: manter o texto da Fase 1 (a cerca da 005 fala de segurança, não de usar o resultado);
prompt por flow (exige o flow no `PackContext`, mudança no contrato 001 e ADR).

## R17 — Versão do pack

**Decision**: a distribuição e o manifest continuam `0.1.0`.

**Rationale**: nada foi publicado — `ai-core` e `ai-generic` saem juntos, com versão única, no primeiro release
(arch-v1, tabela de versões); o texto do prompt não é contrato. O teste de consistência da R12 e o de carga por entry
point do core seguem valendo sem edição.

**Alternatives considered**: `0.2.0` agora (mudaria dois testes para registrar um release que não existe).

## R18 — Onde a US2 é provada

**Decision**: no core, em `tests/bootstrap/integration/test_generic_agentic_mcp.py` (marca `us2`), no perfil `test`,
sem rede: um Assistant `agentic` com `packs: [generic]`, o MCP `demo` do `mcp.yaml` e `controller` num provider
trocado na montagem (`ScriptedController`: pede `demo.eco`, depois responde); a geração num `ScriptedProvider`
(`ollama`); o MCP num `ScriptedMcpTransport`. Verifica: 200 pela API; o catálogo que o controller recebeu tem
`generic.calculate` **e** `demo.eco` (pack e MCP juntos); a chamada de geração recebeu o prompt do pack — obtido pelo
seam `PackHooks.system_prompts` da plataforma, sem importar `ai_generic` —, a `FENCE_INSTRUCTION` e o resultado do MCP
cercado em `<tool_result>`. As propriedades textuais da FR-008 (inclusive "não manda chamar ferramenta") são do
prompt do pack e ficam em `tests/test_pack.py`: no core, a `FENCE_INSTRUCTION` da 004 também fala de ferramentas, e o
teste não deve depender do texto dela.

**Rationale**: o pack não importa o core (SC-001), então a prova ponta a ponta vive no core, como a carga real da
Fase 1 (R8). Com modelos simulados, "a resposta usa o resultado" se prova pelo que a geração recebe; o uso pelo modelo
de verdade é a integração opcional (R19). Obter o prompt pelo seam evita acoplar o teste do core ao texto do pack.

**Alternatives considered**: um provider de eco que responda com o resultado da tool (prova encanamento, não modelo, e
acrescenta um dublê só para isso); importar `SYSTEM_PROMPT` de `ai_generic` no teste do core (permitido, mas acopla a
suíte ao módulo do pack sem necessidade).

## R19 — Integração opcional com modelo real

**Decision**: `tests/bootstrap/integration/test_generic_agentic_real.py`, pulado sem `OLLAMA_BASE_URL` (o mesmo
gatilho da integração da 006): perfil `test` com `providers={"ollama": OllamaProvider(base_url=…)}` e o MCP programado
com uma tool `consultar_registro` que devolve um código que o modelo não tem como adivinhar; Assistant com
`controller` e `generation` em `ollama/<OLLAMA_MODEL>` (default `qwen3:1.7b`). Aceite: 200 e o código aparece na
resposta (cenário 1 literal).

**Rationale**: é o *Independent Test* da US2 com um modelo de verdade decidindo e respondendo; sem rede para o MCP e
sem custo, mas lento e dependente de modelo local — por isso opcional.

**Alternatives considered**: rodar sempre (exige Ollama na CI); MCP real (rede e servidor externo, sem ganho para o
que o teste prova).

> Estendido em 2026-10-07: o mesmo teste roda também contra o OpenRouter, com `AI_CORE_OPENROUTER_API_KEY` (pago;
> modelo em `OPENROUTER_MODEL`, default `~z-ai/glm-flash-latest`, o da 006), parametrizado por backend — cada um
> pulado sem a própria variável. Primeira execução real: o controller recebeu o esquema de ação da 005 (`anyOf` na
> raiz) com `strict` e `require_parameters`, chamou `demo.consultar_registro`, e a resposta trouxe o código — o cenário
> 1 literal. Modelos sem `structured_outputs` no OpenRouter (os `:free` do Gemma 4) são recusados no controller com 404,
> como a 006 FR-005 manda.

## R20 — O exemplo do Assistant genérico

**Decision**: o [quickstart.md](quickstart.md), seção "Fase 3", traz o bloco de `assistants.yaml` (`flow: agentic`,
`packs: [generic]`, `mcp: [<alias>]`, `generation` e `controller`) e o de `mcp.yaml` (servidor com
`policy.allowed_tools`). Nenhum arquivo de exemplo novo no repositório.

**Rationale** (princípio XII): os formatos são da 003 e da 007; um arquivo de exemplo duplicaria esses contratos e
envelheceria sem teste. O teste da R18 é o exemplo executável.

**Alternatives considered**: `examples/assistants.yaml` distribuído (sem consumidor e sem teste).

## R21 — Toques fora do módulo e fronteiras

**Decision**: fora de `ai-core/packages/generic/**`, só testes do core (`tests/bootstrap/integration/`, R18 e R19) e a
descrição da marca `us2` em `ai-core/pyproject.toml` (+= "; 010 US2 — Assistant genérico com MCP"). Nenhuma linha de
`ai-core/packages/core/src/`. import-linter sem contrato novo.

**Rationale**: SC-002 e a clarificação de 2026-09-17 — o core prova o pack sem caso especial no código.

**Alternatives considered**: nenhum.

---

# Passada de 2026-10-20: identidade Axon ([ADR-037](../../docs/adr/ADR-037-a-plataforma-se-chama-axon.md); US3)

Decisões pré-aprovadas pelo ADR-037 (nomes, corte seco, versão, ordem das passadas); o que segue é como elas chegam ao
pack e aos consumidores dele no workspace, sem re-pesquisa. Os R anteriores ficam como foram executados (ADR-037, item
6); os nomes antigos neles se leem pela tabela do ADR-037.

## R22 — Distribuição, pacote e versão

**Decision**: `git mv packages/generic/src/ai_generic packages/generic/src/axon_generic`. Em
`packages/generic/pyproject.toml`: `name = "axon-generic"`, `version = "0.2.0"`, `description = "Pack de referência e
de uso geral da plataforma Axon (spec 010)."` e o alvo do entry point `generic = "axon_generic.pack:GenericPack"`. Em
`pack.py`, `VERSION = "0.2.0"` (a docstring cita `axon-generic`); o `__init__.py` e o `README.md` do pack com os nomes
novos. A pasta `packages/generic` fica. A faixa `axon-ai-contracts>=0.2,<0.3` e a `contract_version = "0.2"` já estão
no lugar (passada da 001) e não mudam. O `uv.lock` é regenerado (`uv lock`), não editado.

**Rationale** (ADR-037, itens 2 e 4): no código, o prefixo `ai-` vira `axon-`; a versão `0.2.0` é a do ADR, e a
política 0.x (ADR-014) sobe a minor numa quebra — renomear a distribuição e o import é quebra para quem instala ou
importa o pack pelo nome. A versão do manifest continua igual à da distribuição (R12, verificada em `tests/test_pack.py`).

**Alternatives considered**: manter `0.1.0` (o nome muda sem a versão dizer); `0.1.1` (patch é para mudança aditiva,
ADR-014); alias `ai_generic` reexportando `axon_generic` (o ADR-037 decide corte seco, e o pack não tem consumidor que o
importe).

## R23 — O que fica

**Decision**: não mudam o nome do pack (`GenericPack.name = "generic"`, o nome do entry point, o namespace
`generic.calculate`, `packs: [generic]`), o manifest além da versão, o prompt, a tool, o validator, os limites da tool,
a fronteira (só os nomes nas regras) e o **grupo** do entry point, que continua `ai_core.packs` até a passada da 002
(grupo `axon.packs`), porque é o grupo que o Pack Runtime procura hoje.

**Rationale** (ADR-037, itens 5 e 7): os nomes de pack não mudam; o grupo de entry point é identificador com
comportamento da 002 e muda na passada dela, com testes. Mudar o grupo só no pack faria o core deixar de encontrá-lo.

**Alternatives considered**: trocar o grupo aqui junto com o Pack Runtime (atropela a passada da 002); anunciar o pack
nos dois grupos (compatibilidade sem usuário, contra o corte seco).

## R24 — Consumidores no workspace (mecânico)

**Decision**: um script no scratchpad (não versionado) troca `ai_generic` → `axon_generic` e `ai-generic` →
`axon-generic` (do padrão com sublinhado ao com hífen, por palavra; `ai_generic_fake` do teste da 001 vira
`axon_generic_fake`). Escopo:

- `axon-ai/pyproject.toml`: `[tool.uv.sources]`, grupo `dev`, `known-first-party`, `root_packages` e as três regras
  do pack no import-linter;
- `axon-ai/packages/generic/**` (código, testes, `pyproject.toml`, `README.md`);
- a suíte do core que cita o pack: `tests/packs/integration/test_packs_generic_entry_point.py` (que passa a esperar a
  distribuição `axon-generic` e a versão `0.2.0`, à mão) e as docstrings de `tests/graph/integration/`,
  `tests/http/integration/`, `tests/bootstrap/integration/` e `tests/packs/integration/test_packs_cli.py`;
- `axon-ai/packages/contracts/README.md` (exemplo de import-linter) e
  `packages/contracts/tests/conformance/test_imports_check.py` (nome do pacote falso);
- `.github/workflows/generic.yml` (cabeçalho e o job `clean-env`: as três distribuições esperadas e o mapeamento
  `axon_generic` → `axon-generic`). O `core.yml` filtra por caminho (`axon-ai/packages/generic/**`), que não muda.

Fora do script: `packages/contracts/CHANGELOG.md` (histórico), `uv.lock` (regenerado).

**Rationale** (ADR-037, item 7): a passada que renomeia uma distribuição atualiza de forma mecânica quem a consome, para
a CI ficar verde. O core não importa o pack (SC-001), então o único código do core que muda são testes.

**Alternatives considered**: `sed` global sem escopo (alcançaria o histórico e os submódulos); deixar a suíte do core
para a passada da 002 (a CI ficaria vermelha entre as passadas).

## R25 — Documentos vivos

**Decision**: o mesmo script, nos documentos vivos (ADR-037, item 6) que citam o pack: os da 010 (`design.md`,
`data-model.md`, `quickstart.md`, `contracts/**`), `specs/001-core-contracts/design.md` (tabela de distribuições e o
exemplo do import-linter), `specs/002-core-pack-runtime/design.md`, `specs/005-core-execution-engine/{quickstart.md,contracts/execution-engine.md}`,
`specs/008-core-http-api/quickstart.md` e `specs/README.md`. À mão: a clarificação de `specs/002-core-pack-runtime/spec.md` sobre de onde vem o core na imagem (a
vizinha, sobre a tag `v0.1.0`, fica); e, na 010, `contracts/generic-pack.md` e
`data-model.md` passam a `contract_version = "0.2"` (faixa `>=0.2,<0.3`) e à versão `0.2.0`, que a passada da 001
deixou com os valores antigos; `contracts/packaging.md` e o `quickstart.md` com a distribuição, a versão e a resolução
esperada no ambiente limpo.

Ficam como estão: `research.md`, `plan.md` e `tasks.md` executados; os textos que nomeiam o antigo de propósito
(`specs/001-core-contracts/contracts/testing-kit.md`, "na série 0.1"; a premissa da US6 da 001, que descreve o estado
daquela passada; a clarificação da 002 sobre a tag `v0.1.0`); as specs `1xx` (passada da 101);
`specs/002-core-pack-runtime/contracts/installation.md` (passada da instalação); `CLAUDE.md` (fechamento); `docs/`
(ADRs, roadmap narrativo — só a linha de andamento do 9.5 muda —, constituição e o Sync Impact Report dela).

**Rationale** (ADR-037, item 6): `spec.md`, `design.md`, `contracts/`, `data-model.md` e `quickstart.md` são vivos e
passam aos nomes novos; o histórico não se reescreve. A lição da 011: a substituição mecânica corrompeu textos da 001 que
citavam o nome antigo de propósito (restaurados antes desta passada); aqui o script recebe a lista de arquivos, não a
árvore.

**Alternatives considered**: deixar os documentos das outras specs para as passadas delas (o nome antigo ficaria errado
entre as passadas, e a 005 e a 008 nem têm passada de nome própria).

## R26 — Teste do corte seco

**Decision**: `packages/generic/tests/test_generic_old_name_absent.py` (nome único: o pytest do workspace coleta os
testes por nome de arquivo, e `test_no_old_name.py` já existe na 001): `importlib.util.find_spec("ai_generic") is None`
e `importlib.metadata.distribution("ai-generic")` levanta `PackageNotFoundError` (US3 cenário 1). Roda no workspace e no
ambiente limpo. A distribuição e a versão novas já são verificadas por `tests/test_pack.py` (versão do manifest igual à
de `axon-generic`), `tests/test_conformance.py` (etapa de distribuição no ambiente limpo, cenário 2) e pela carga real
na suíte do core (cenário 3).

**Rationale**: o corte seco é requisito (FR-009) e precisa de um verificador, como na 001 e na 011. Um `uv sync` exato
tira a distribuição antiga do ambiente do workspace.

**Alternatives considered**: só o `git grep` de resíduos (não pega uma instalação antiga no ambiente).

## R27 — Verificação

**Decision**: a partir de `axon-ai/`: `uv sync && uv run pytest && uv run mypy && uv run ruff check packages && uv run
ruff format --check packages && uv run lint-imports`; o ambiente limpo em 3.12 (quickstart §5, com a resolução das três
distribuições e a etapa de distribuição sem item); `check_clean_env.py` dos contratos. Na raiz: `git grep -nwE
"ai_generic|ai-generic"` fora dos caminhos do R25 dá zero, e nenhuma ocorrência da palavra `agentic` sai no diff da passada
(`git diff --word-diff=porcelain -U0 | grep '^-' | grep -cw agentic` = 0, por palavra: uma linha trocada
que mantém o `agentic` não conta; a contagem total só cresce com o texto novo da US3 — eram 602 no
HEAD antes da passada): o flow fica intacto.

**Rationale**: SC-003 e a lição da 011 (contar o `agentic`).

**Alternatives considered**: nenhuma.

## R28 — A tool `chart` (ADR-052, item 7; FR-013)

**Decision**: `tools/chart.py`, módulo puro:
- `PARAMETERS`, com `kind`, `title` e `series` obrigatórios e os demais opcionais; `x` é `anyOf` texto ou número;
  todo objeto é fechado; `series` tem `minItems` 1 e `maxItems` 8.
- `build_chart`: os opcionais ausentes ou nulos viram o padrão do contrato, porque o adapter da OpenAI os torna
  obrigatórios e anuláveis (ADR-023).
- O handler `chart` devolve `ToolResult(content="gráfico <id> criado (<tipo>, N série(s), M ponto(s))",
  charts=(chart,))` ou `ToolResult(error="gráfico inválido: <motivo>")` para `TypeError`, `ValueError` e `KeyError`
  do `Chart`.

A descrição da tool diz quando usar e como passar os dados: pedido do usuário; números já agregados; o teto; data ISO
com `x_type` temporal; uma série na pizza. Ela diz também que o gráfico aparece com a tabela. `GenericPack.tools`
devolve `(calculate_spec(), chart_spec())`. Versão `0.3.0`, `contract_version = "0.2.4"`, dependência
`>=0.2.4,<0.3`.

**Rationale** (ADR-052: "A tool é do `axon-generic`"): o pack de uso geral é o lugar das capacidades sem domínio
(FR-005). O `Chart` já valida tudo na construção, então a tool não repete regra; ela só traduz argumentos e transforma
a exceção em erro que o controller lê e corrige. O esquema foi conferido contra a conversão estrita da 006 e a
validação de argumentos da 004. O prompt não muda: a frase do controller sobre gráficos é do core (005 R53).

**Alternatives considered**: a tool no core (o core não tem tools próprias; elas vêm de packs, MCP e retrievers);
pontos como pares `[x, y]` (o subconjunto estrito recusa `items` em tupla); devolver o erro como exceção (o gateway o
transformaria em `error` genérico, sem o motivo).
