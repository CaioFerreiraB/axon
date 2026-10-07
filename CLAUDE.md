# agentic-app — Plataforma Agentic AI (SDD com spec-kit)

Este repositório é o **Spec-Driven Development** da plataforma: `ai-core` (runtime genérico), `ai-generic` (pack de referência)
e `ai-scouting` (pack de domínio escoteiro). Spec-kit 1.0.6, integração Claude em modo skills (`/speckit-*`).

## Onde está cada coisa

| O quê | Onde |
|---|---|
| Princípios (lidos por toda skill do spec-kit) | `.specify/memory/constitution.md` |
| Mapa de módulos, seams e dependências | `specs/README.md` |
| Uma spec por módulo + insumo técnico | `specs/NNN-nome/spec.md` e `specs/NNN-nome/design.md` |
| Decisões arquiteturais | `docs/adr/` |
| Estilo arquitetural (microkernel · monolito modular · hexagonal) e seus motivos | ADR-012 e `docs/relatorio-estilo-arquitetural.md` |
| Fases → specs/user stories | `docs/roadmap.md` |
| Arquitetura original (histórico, "arch-v1") | `docs/archive/architecture-v1.md` |
| Overrides de template do projeto | `.specify/templates/overrides/` |

## Regras para trabalhar neste repositório

1. **Modularidade é inegociável (princípio II).** Antes de mexer numa spec ou em código, leia a seção *Module Boundary* dela e a
   tabela de seams em `specs/README.md`. Nunca referencie internals de outro módulo (nomes de nós, campos de estado interno,
   tabelas, classes privadas) — só seams. Se uma mudança exige editar outra spec, pare: ou um seam está mudando (precisa de ADR)
   ou a fronteira está sendo violada.
2. **`/speckit-plan`**: leia obrigatoriamente o `design.md` da pasta da spec e os ADRs citados. Essas decisões são pré-aprovadas —
   leve-as para `research.md` como "Decision / Rationale (ADR) / Alternatives", sem re-pesquisar. Divergência = ADR novo.
3. **`/speckit-specify` (spec nova)**: escolha o número no bloco do módulo — `0xx` core, `1xx` scouting, `2xx`+ packs futuros — e
   passe `SPECIFY_FEATURE_DIRECTORY=specs/NNN-nome` explicitamente (a numeração automática do spec-kit só faz "maior + 1").
   A seção *Module Boundary* é obrigatória (vem no template do projeto). Registre a spec em `specs/README.md`.
4. **Core agnóstico de domínio (princípio I)**: nada de escotismo em specs, código ou prompts do `0xx`.
5. **Idioma**: conteúdo em português; títulos de seção dos templates em inglês (compatibilidade com as skills).
6. **ADR aceito não se edita**: cria-se outro que o substitui (`docs/adr/README.md`).
7. **Portas e adapters (princípio XIII, ADR-012).** Dentro de cada módulo: `api.py` (seams), `domain/` (políticas puras),
   `ports.py` (portas secundárias), `service.py` e `adapters/` (infraestrutura). I/O, tempo, segredos e trace ficam atrás
   de portas; um módulo só importa o `api.py` de outro; só a composition root (spec 011) — ou o `pack.py`, num pack —
   instancia serviços e adapters. Todo `design.md` tem a seção "Portas e adapters". Porta nova só onde há I/O,
   não-determinismo ou troca prevista.

## Fluxo por spec

```text
/speckit-clarify   → resolve ambiguidades (máx. 5 perguntas) e grava na spec
/speckit-plan      → plan.md, research.md, data-model.md, contracts/, quickstart.md
/speckit-tasks     → tasks.md (limite às user stories da fase, ver docs/roadmap.md)
/speckit-analyze   → consistência entre spec, plano e tarefas
/speckit-implement → executa tasks.md
```

**Spec ativa**: as skills usam `.specify/feature.json` (`{"feature_directory": "specs/NNN-nome"}`), que é local e fica fora do git.
Para trocar de spec: edite esse arquivo ou exporte `SPECIFY_FEATURE_DIRECTORY=specs/NNN-nome`.

## Reescrever um módulo

Ver "Como reescrever um módulo" em `specs/README.md`. Resumo:
- **Grafo do core** → só `specs/005-core-execution-engine/` muda; nomes de nós, estado interno e framework são livres (ADR-011).
  Na prática, troca-se `ai_core/graph/adapters/langgraph/` e preservam-se `api.py` e `domain/` (ADR-012).
- **ai-scouting** → só `specs/1xx-*` mudam; o core enxerga o pack apenas pelo contrato 001 e pelo nome do flow preferido.

## Código

Implementado até agora: `ai-core-contracts` (spec 001, Fase 0) em `ai-core/packages/contracts/`; a distribuição
`ai-core` em `ai-core/packages/core/`, com o Pack Runtime (`ai_core/packs/`, spec 002, Fase 1: US1, US2, US3 cenários
2–4), o trace por requisição (`ai_core/observability/`, spec 009, Fase 1: US1) — seam Trace Sink com eventos tipados,
consulta por requisição, redação de credenciais e backends de memória e JSONL (`ai_core/eval/`, o harness, é Fase 6) —
o Model Router (`ai_core/llm/`, spec 006, Fase 1: US1) — resolução de papel a partir de uma Model Policy, allowlist,
saúde sob demanda, trace por chamada e o provider local do Ollama pela camada compatível com OpenAI (SDK `openai`,
confinado a `adapters/` por import-linter), mais o provider simulado do perfil de teste; OpenAI e OpenRouter chegaram na Fase 3 (abaixo)
— e o motor de execução (`ai_core/graph/`, spec 005, Fase 1: US1) — seam Execution Engine (`run(grant, request)` →
token, progresso e evento final), o flow `chat` em LangGraph (framework preso a `adapters/langgraph/` por
import-linter) e o grant chegando como `Protocol` estrutural até a 003 existir (substituído pelo grant da 003 na Fase 3,
ADR-018); `agentic` é Fase 3 (abaixo) e `rag_first`, Fase 5
— e a API HTTP (`ai_core/http/`, spec 008, Fase 1: US1) — chat completions compatível com OpenAI, com e sem streaming
SSE, nas superfícies `/v1` e `/private/v1`, com autenticação e resolução de Assistant atrás de portas até a 003
existir; listagem de modelos, conversas e fila são Fases 2 e 7 — e a composition root (`ai_core/bootstrap/`, spec 011,
Fase 1: US1, US2 em memória, US3) — boot por etapas declaradas com falha fechada, perfis `memory` e `test`, resolvedor
de grant a partir de `assistants.yaml` e o comando `ai-core serve`; saúde agregada e subcomandos de módulo são Fase 2.
**A Fase 1 do roadmap está completa**: `ai-core serve` sobe a plataforma e uma conversa atravessa HTTP, motor, packs e
modelo local;
e o pack de referência `ai-generic` em `ai-core/packages/generic/` (spec 010, Fase 1: US1) — prompt de uso geral,
tool nativa `calculate` e validator `non_empty_answer`, descoberto pelo entry point `ai_core.packs` como qualquer pack
externo (a Fase 3 da 010 está abaixo). O resto dos caminhos-alvo está nos `design.md`, no layout hexagonal do ADR-012.
Decidido em 2026-09-15 (plano da 001): `ai-core/` é subpasta deste repositório nas Fases 0–3 e se separa antes da Fase 4;
Python 3.14 no workspace, piso 3.12 em `ai-core-contracts`; CI em `.github/workflows/` da raiz. O `ai-scouting` segue a
mesma regra: subpasta até existir repositório próprio, dependendo só de `ai-core-contracts`.

**A Fase 2 do roadmap está completa.** O módulo Assistants & Access (`ai_core/assistants/`, spec 003, US1–US7):
autenticação OIDC (JWT verificado localmente contra o JWKS) e por chave de API (só o hash; emissão e revogação pela CLI
e pela superfície privada, restritas ao grupo de administração), resolução de grant com 404-não-403, allowlist aplicada
na resolução, orçamento em janela deslizante, Assistants de usuário `~nome` sob políticas por grupo e validação de
referências. É o primeiro módulo com Postgres — psycopg 3, schema `assistants`, migrações SQL no próprio adapter
(ADR-015) —, e o grant carrega a `ModelPolicy` da 006 (seta 003 → 006, ADR-016). Da 002, a US4: `packs list` e `packs
check` em `ai_core/packs/adapters/cli.py`. Da 008, a Fase 2 (US2, US3, US4 de Assistants, US5, US7): a API consome os
seams da 003 direto (`Authorization: Bearer`, erros no envelope da OpenAI, 424 para Assistant indisponível), com
`/models`, a requisição nativa `POST /chat`, o CRUD de Assistants de usuário em `/v1/assistants`, a superfície privada
(`/packs` e `/admin/keys` só para o grupo de administração, `/health` para qualquer chave) e as conversas no servidor,
em memória e em Postgres (schema `http`). Os endpoints de MCP chegaram na Fase 3 (abaixo).
Da 011, a Fase 2 (US2 persistente, US4, US5) liga tudo isso: três perfis — `memory`, `persistent` (Postgres em
`AI_CORE_DATABASE_URL`, migrações de `assistants` e `http` na etapa `adapters`) e `test` —, todos com a autenticação
real da 003 (o anônimo saiu; o `memory` aceita a chave de `AI_CORE_DEV_API_KEY`, e o `test` exporta `TEST_OIDC_TOKEN`
e `TEST_API_KEY` em `ai_core.bootstrap.profiles`); a raiz `ai-core` com `serve`, `packs list|check`, `assistants
validate`, `keys create|list|revoke` e `health`, registrados numa lista em `bootstrap/cli.py`; a saúde agregada
(`bootstrap/health.py`, 503 só quando o banco ou uma etapa crítica falha); e a expiração periódica das conversas no
ciclo de vida da app. O pool do psycopg pertence ao laço em que abre: o de serviço abre no ciclo de vida da app, e o
boot e a CLI usam uma sessão de armazenamento própria (`wiring.storage`).

**A Fase 3 do roadmap está completa.** O registry e o cliente MCP (`ai_core/mcp/`, spec 007, US1–US6) existem como módulo: servidores
por alias — globais pela API (`http`/`sse`) ou pelo arquivo do operador `mcp.yaml` (único lugar de `stdio` e dos hosts
internos e da allowlist de hosts de destino), e de usuário com prefixo `~`, sempre `https` e sem credencial —, política por
servidor com allowlist de tools obrigatória, credencial só por referência (`AI_CORE_MCP_SECRET_<REF>`), descoberta com
cache por TTL e o cliente restrito ao grant (`client_for(grant)`, com `discover` que devolve também os servidores com
falha). O SDK oficial `mcp` (2.x, com `httpx2`) fica em `adapters/`; o transporte HTTP aplica a política de rede a cada
conexão, conectando no IP validado (fecha DNS rebinding). Postgres no schema `mcp` (ADR-015). A 008 o expõe na
Fase 3: `/v1/mcp` (servidores do próprio usuário, `available` e saúde do próprio servidor) e `/private/v1/mcp` (globais,
só para o grupo de administração, 404 para os demais; entradas do `mcp.yaml` somente leitura), com o corpo no formato do
`mcp.yaml` e nenhuma resposta com valor de credencial.
O catálogo de capacidades e o gateway de tools (`ai_core/capabilities/`, spec 004, US1–US5) também existem como módulo:
uma sessão por execução (`Capabilities.open(grant, ToolContext)`) monta o catálogo — tools de pack, retrievers com todas
as coleções no grant e tools de MCP pelo cliente restrito da 007, com namespace, `allowed_tools`/`write_tools` exatos — e
executa chamadas (fora do catálogo é "tool inexistente"; argumentos validados com `jsonschema`, sem regex de terceiro
em esquema de MCP; prazo e tamanho do gateway; resultado cercado em `<tool_result>` com o conteúdo neutralizado). Tool
de escrita é auditada **antes** de executar (sem auditoria, não executa), em memória ou Postgres (schema
`capabilities`); `audit_command` em `adapters/cli.py`. Cada chamada vira o evento `tool_call` da 009 (acrescentado
nesta passada). A 002 já expõe o seam **Pack Toolset** (`PackRuntime.toolset(composition)`, US3 cen. 1), que cumpre
a porta `PackToolSource` da 004. A 003 (passada de encaixe da Fase 3) valida as referências que o loop usa: papéis de
modelo exigidos pelo flow — o motor os publica em `ExecutionEngine.flow_roles()` (ADR-019) e a 011 os injeta, então um
Assistant `agentic` sem `controller` fica indisponível (424 pela API) —, entradas de `allowed_tools`/`write_tools`
sempre com namespace, de um pack ou MCP do próprio Assistant e, para pack, de tool que ele oferece, e a colisão de alias
MCP com pack; Assistant de usuário que viole uma delas é recusado na criação e na atualização, nomeando o campo.
O motor tem o flow `agentic` (spec 005, US2): a sessão de tools da 004 abre depois da preparação; a cada iteração o
papel `controller` devolve uma ação por `response_format` (um ramo `anyOf` por tool do catálogo, parâmetros sem regex),
o gateway executa e o resultado cercado volta pelo formato nativo de tool (`assistant` com `tool_calls` + `tool`), com
a `FENCE_INSTRUCTION` no sistema. Limite do grant ou 3; teto de contexto do grant aplicado ao loop e à geração
(estimativa por caracteres, resultados mais antigos omitidos com marca); falha do controller segue para a geração.
As políticas são puras em `ai_core/graph/domain/` (`actions`, `limits`, `budget`, `transcript`). Mudanças de seam no
ADR-018: o motor recebe o `ExecutionGrant` da 003 (reexportado pelo `api.py` da 005) e `ExecutionIssue` tem `severity`
(`error`/`notice`; `ExecutionFinished.ok` ignora `notice`). A decisão do controller é o evento `controller_decision` da
009 (ADR-017). O `ExecutionService` aceita `capabilities` (seam da 004): sem ele, `agentic` não está em `flows()`.
A 008 decide o desfecho por `severity` (FR-022): só `notice` → 200 e `finish_reason: "stop"`; algum `error` → 502 sem
streaming, com `x-should-retry: false` para o SDK oficial não reexecutar o loop (nem tools de escrita). Checkpoint
adiado até haver retomada (FR-014).
A composition root (011, passada de encaixe da Fase 3) liga tudo isso nos três perfis: portas `mcp_store`, `mcp_dns`,
`mcp_transports`, `mcp_secrets`, `mcp_cache` e `audit` (memória; Postgres no `persistent`, com as migrações de `mcp` e
`capabilities`; no `test`, um transporte MCP programado sem servidores); o `mcp.yaml` (`AI_CORE_MCP_FILE`) lido na etapa
`configuration`; a etapa nova `mcp_registry` (sem rede; entrada com problema ou credencial sem
`AI_CORE_MCP_SECRET_<REF>` degrada; logger `mcp` fixo em `INFO`); o gateway no motor (`agentic` em `flows()`); a 003
validando contra o registry real; um item de saúde não crítico `mcp:<alias>` por servidor global; `ai-core audit`; e
`AI_CORE_TOOL_TIMEOUT_MS`/`AI_CORE_TOOL_MAX_RESPONSE_BYTES`/`AI_CORE_MCP_DISCOVERY_TTL`. O `McpService` da plataforma
fica em `Platform.mcp` para as rotas da 008. As suítes trocam portas na montagem —
`platform(profile="test", overrides={"providers": …, "mcp_transports": …})` — para programar controller e servidores
MCP (portas de armazenamento não se trocam); sem trocas, o modelo simulado do `test` responde `{"action": "answer"}`
como controller. Uma conversa `agentic` + MCP atravessa a API sem rede
(`tests/bootstrap/integration/test_platform_agentic_mcp.py`).
Os providers remotos da 006 (US2–US5) também: `OpenAIProvider` e `OpenRouterProvider` são arquivos finos sobre a
camada compatível (`adapters/remote.py`), com a credencial lida uma vez, na construção, pela porta `SecretResolver`
(`AI_CORE_OPENAI_API_KEY`/`AI_CORE_OPENROUTER_API_KEY`; ADR-020) — sem ela, o remoto fica registrado e explica a falta
na saúde e na chamada, sem tocar a rede, e o valor da chave nunca entra em mensagem. O `ModelRef` recusa roteamento
automático (`openrouter/auto` e o namespace `openrouter/…`) na construção, antes da allowlist. Nenhuma chamada do papel
`controller` sai sem `response_format` de esquema (guarda pura em `llm/domain/output.py`, aplicada no cliente
instrumentado, com `ModelCall` de erro); o adapter envia `strict: true` e, no OpenRouter, `require_parameters`; recusa
do provider é `ModelCallFailed`, sem reenvio. A 011 monta `llm_secrets` (ambiente no `memory`/`persistent`, memória
vazia no `test`) antes de `providers`, que nos dois primeiros perfis tem `ollama`, `openai` e `openrouter`.
Pendência da 005: o esquema de ação tem `anyOf` na raiz, que o modo estrito da OpenAI recusa — OpenAI como controller
do `agentic` falha explicitamente até a 005 publicar um esquema de raiz objeto (006 R19). A integração paga
(`tests/llm/integration/test_remote_real.py`) só roda com as credenciais no ambiente.
A 010 fechou a fase (US2): o `ai-generic` **continua pack** — a FR-005 é regra permanente, e ele agrega `calculate` e
`non_empty_answer` além do prompt — e **sem flow preferido** (FR-007): o Assistant genérico com MCP declara `flow:
agentic`, `controller` e `mcp`; `packs: [generic]` sem `flow` segue no `chat`. O prompt é neutro quanto ao flow
(FR-008): orienta a usar os resultados de ferramentas que a conversa trouxer e nunca manda chamar ferramenta — no
`agentic` ele só chega à geração. A US2 é provada no core sem importar `ai_generic` (o prompt vem pelo seam `PackHooks`)
em `tests/bootstrap/integration/test_generic_agentic_mcp.py`; `test_generic_agentic_real.py` repete com um Ollama de
verdade, só com `OLLAMA_BASE_URL`.

O `ai-generic` é o exemplo a copiar num pack novo: piso de Python dos contratos (`>=3.12`, não o 3.14 do core),
dependência pela faixa derivada da `contract_version` (`>=0.1,<0.2`, ADR-014) com `[tool.uv.sources] ... { workspace =
true }`, suíte de conformidade nos próprios testes e zero import do core (import-linter, nas duas direções). Ele é
dependência de desenvolvimento do workspace porque o teste de carga real por entry point roda na suíte do core
(`packages/core/tests/packs/integration/test_packs_generic_entry_point.py`). A etapa de distribuição da conformidade só
verifica a faixa numa instalação normal — no workspace tudo é editável —, então ela vale no ambiente limpo:

```bash
tmp=$(mktemp -d) && uv venv --python 3.12 "$tmp/venv"
uv pip install --python "$tmp/venv/bin/python" ./packages/contracts ./packages/generic pytest
(cd packages/generic && "$tmp/venv/bin/python" -m pytest -q tests) ; rm -rf "$tmp"
```

Verificação dos contratos (a partir de `ai-core/`; roteiro completo no quickstart da 001):

```bash
uv sync
uv run pytest && uv run mypy && uv run ruff check packages && uv run lint-imports
uv run python packages/contracts/tools/check_clean_env.py      # SC-001: pack só com os contratos
```

O workspace exige Python 3.14 (por causa do core); o piso 3.12 dos contratos roda fora dele:
`uv run --no-project --python 3.12 --with ./packages/contracts --with pytest --with pytest-asyncio --with hypothesis
--with packaging pytest packages/contracts/tests`.

Conformidade contra o Postgres real (ADR-015; a CI do core tem o serviço): sem `AI_CORE_TEST_POSTGRES_DSN`, esses casos
são pulados.

```bash
docker run -d --rm --name ai-core-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:17
AI_CORE_TEST_POSTGRES_DSN=postgresql://postgres:pg@localhost:55432/postgres uv run pytest
```

Nesta máquina, rode o `uv` com `XDG_DATA_HOME=$HOME/.local/share` (o VSCode snap aponta o XDG para uma pasta que some).
