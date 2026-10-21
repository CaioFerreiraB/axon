# axon — Plataforma Axon (SDD com spec-kit)

Este repositório é o **Spec-Driven Development** da plataforma: `axon-ai` (runtime genérico), `axon-generic` (pack de referência)
e `axon-scouting` (pack de domínio escoteiro). Spec-kit 1.0.6, integração Claude em modo skills (`/speckit-*`).

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
| Marca (símbolo, lockups, tokens, voz) e regras visuais | `brand-kit/`, `DESIGN.md`, `PRODUCT.md`; ADR-037 a ADR-039 |

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
  Na prática, troca-se `axon_ai/graph/adapters/langgraph/` e preservam-se `api.py` e `domain/` (ADR-012).
- **axon-scouting** → só `specs/1xx-*` mudam; o core enxerga o pack apenas pelo contrato 001 e pelo nome do flow preferido.

## Código

Implementado até agora: `axon-ai-contracts` (spec 001, Fase 0) em `axon-ai/packages/contracts/`; a distribuição
`axon-ai` em `axon-ai/packages/core/`, com o Pack Runtime (`axon_ai/packs/`, spec 002, Fase 1: US1, US2, US3 cenários
2–4), o trace por requisição (`axon_ai/observability/`, spec 009, Fase 1: US1) — seam Trace Sink com eventos tipados,
consulta por requisição, redação de credenciais e backends de memória e JSONL (`axon_ai/eval/`, o harness, é Fase 6) —
o Model Router (`axon_ai/llm/`, spec 006, Fase 1: US1) — resolução de papel a partir de uma Model Policy, allowlist,
saúde sob demanda, trace por chamada e o provider local do Ollama pela camada compatível com OpenAI (SDK `openai`,
confinado a `adapters/` por import-linter), mais o provider simulado do perfil de teste; OpenAI e OpenRouter chegaram na Fase 3 (abaixo)
— e o motor de execução (`axon_ai/graph/`, spec 005, Fase 1: US1) — seam Execution Engine (`run(grant, request)` →
token, progresso e evento final), o flow `chat` em LangGraph (framework preso a `adapters/langgraph/` por
import-linter) e o grant chegando como `Protocol` estrutural até a 003 existir (substituído pelo grant da 003 na Fase 3,
ADR-018); `agentic` é Fase 3 (abaixo) e `rag_first`, Fase 5
— e a API HTTP (`axon_ai/http/`, spec 008, Fase 1: US1) — chat completions compatível com OpenAI, com e sem streaming
SSE, nas superfícies `/v1` e `/private/v1`, com autenticação e resolução de Assistant atrás de portas até a 003
existir; listagem de modelos, conversas e fila são Fases 2 e 7 — e a composition root (`axon_ai/bootstrap/`, spec 011,
Fase 1: US1, US2 em memória, US3) — boot por etapas declaradas com falha fechada, perfis `memory` e `test`, resolvedor
de grant a partir de `assistants.yaml` e o comando `axon serve`; saúde agregada e subcomandos de módulo são Fase 2.
**A Fase 1 do roadmap está completa**: `axon serve` sobe a plataforma e uma conversa atravessa HTTP, motor, packs e
modelo local;
e o pack de referência `axon-generic` em `axon-ai/packages/generic/` (spec 010, Fase 1: US1) — prompt de uso geral,
tool nativa `calculate` e validator `non_empty_answer`, descoberto pelo entry point `axon.packs` como qualquer pack
externo (a Fase 3 da 010 está abaixo). O resto dos caminhos-alvo está nos `design.md`, no layout hexagonal do ADR-012.
Decidido em 2026-09-15 (plano da 001) e revisto em 2026-10-07 (ADR-021): `axon-ai/` **permanece** neste repositório
— as tags `contracts-v*` são criadas aqui, e packs de domínio vivem em repositórios próprios, ligados como submódulos na
raiz (`axon-scouting/`);
Python 3.14 no workspace, piso 3.12 em `axon-ai-contracts`; CI em `.github/workflows/` da raiz. O `axon-scouting` mora
no repositório privado `CaioFerreiraB/axon-scouting` (submódulo `axon-scouting/`): o código dele é commitado lá, e aqui só
muda o ponteiro; ele depende só de `axon-ai-contracts`, resolvido pela tag `contracts-v*` deste repositório.

**A Fase 2 do roadmap está completa.** O módulo Assistants & Access (`axon_ai/assistants/`, spec 003, US1–US7):
autenticação OIDC (JWT verificado localmente contra o JWKS) e por chave de API (só o hash; emissão e revogação pela CLI
e pela superfície privada, restritas ao grupo de administração), resolução de grant com 404-não-403, allowlist aplicada
na resolução, orçamento em janela deslizante, Assistants de usuário `~nome` sob políticas por grupo e validação de
referências. É o primeiro módulo com Postgres — psycopg 3, schema `assistants`, migrações SQL no próprio adapter
(ADR-015) —, e o grant carrega a `ModelPolicy` da 006 (seta 003 → 006, ADR-016). Da 002, a US4: `packs list` e `packs
check` em `axon_ai/packs/adapters/cli.py`. Da 008, a Fase 2 (US2, US3, US4 de Assistants, US5, US7): a API consome os
seams da 003 direto (`Authorization: Bearer`, erros no envelope da OpenAI, 424 para Assistant indisponível), com
`/models`, a requisição nativa `POST /chat`, o CRUD de Assistants de usuário em `/v1/assistants`, a superfície privada
(`/packs` e `/admin/keys` só para o grupo de administração, `/health` para qualquer chave) e as conversas no servidor,
em memória e em Postgres (schema `http`). Os endpoints de MCP chegaram na Fase 3 (abaixo).
Da 011, a Fase 2 (US2 persistente, US4, US5) liga tudo isso: três perfis — `memory`, `persistent` (Postgres em
`AXON_DATABASE_URL`, migrações de `assistants` e `http` na etapa `adapters`) e `test` —, todos com a autenticação
real da 003 (o anônimo saiu; o `memory` aceita a chave de `AXON_DEV_API_KEY`, e o `test` exporta `TEST_OIDC_TOKEN`
e `TEST_API_KEY` em `axon_ai.bootstrap.profiles`); a raiz `axon` com `serve`, `packs list|check`, `assistants
validate`, `keys create|list|revoke` e `health`, registrados numa lista em `bootstrap/cli.py`; a saúde agregada
(`bootstrap/health.py`, 503 só quando o banco ou uma etapa crítica falha); e a expiração periódica das conversas no
ciclo de vida da app. O pool do psycopg pertence ao laço em que abre: o de serviço abre no ciclo de vida da app, e o
boot e a CLI usam uma sessão de armazenamento própria (`wiring.storage`).

**A Fase 3 do roadmap está completa.** O registry e o cliente MCP (`axon_ai/mcp/`, spec 007, US1–US6) existem como módulo: servidores
por alias — globais pela API (`http`/`sse`) ou pelo arquivo do operador `mcp.yaml` (único lugar de `stdio` e dos hosts
internos e da allowlist de hosts de destino), e de usuário com prefixo `~`, sempre `https` e sem credencial —, política por
servidor com allowlist de tools obrigatória, credencial só por referência (`AXON_MCP_SECRET_<REF>`), descoberta com
cache por TTL e o cliente restrito ao grant (`client_for(grant)`, com `discover` que devolve também os servidores com
falha). O SDK oficial `mcp` (2.x, com `httpx2`) fica em `adapters/`; o transporte HTTP aplica a política de rede a cada
conexão, conectando no IP validado (fecha DNS rebinding). Postgres no schema `mcp` (ADR-015). A 008 o expõe na
Fase 3: `/v1/mcp` (servidores do próprio usuário, `available` e saúde do próprio servidor) e `/private/v1/mcp` (globais,
só para o grupo de administração, 404 para os demais; entradas do `mcp.yaml` somente leitura), com o corpo no formato do
`mcp.yaml` e nenhuma resposta com valor de credencial.
O catálogo de capacidades e o gateway de tools (`axon_ai/capabilities/`, spec 004, US1–US5) também existem como módulo:
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
As políticas são puras em `axon_ai/graph/domain/` (`actions`, `limits`, `budget`, `transcript`). Mudanças de seam no
ADR-018: o motor recebe o `ExecutionGrant` da 003 (reexportado pelo `api.py` da 005) e `ExecutionIssue` tem `severity`
(`error`/`notice`; `ExecutionFinished.ok` ignora `notice`). A decisão do controller é o evento `controller_decision` da
009 (ADR-017). O `ExecutionService` aceita `capabilities` (seam da 004): sem ele, `agentic` não está em `flows()`.
A 008 decide o desfecho por `severity` (FR-022): só `notice` → 200 e `finish_reason: "stop"`; algum `error` → 502 sem
streaming, com `x-should-retry: false` para o SDK oficial não reexecutar o loop (nem tools de escrita). Checkpoint
adiado até haver retomada (FR-014).
A composition root (011, passada de encaixe da Fase 3) liga tudo isso nos três perfis: portas `mcp_store`, `mcp_dns`,
`mcp_transports`, `mcp_secrets`, `mcp_cache` e `audit` (memória; Postgres no `persistent`, com as migrações de `mcp` e
`capabilities`; no `test`, um transporte MCP programado sem servidores); o `mcp.yaml` (`AXON_MCP_FILE`) lido na etapa
`configuration`; a etapa nova `mcp_registry` (sem rede; entrada com problema ou credencial sem
`AXON_MCP_SECRET_<REF>` degrada; logger `mcp` fixo em `INFO`); o gateway no motor (`agentic` em `flows()`); a 003
validando contra o registry real; um item de saúde não crítico `mcp:<alias>` por servidor global; `axon audit`; e
`AXON_TOOL_TIMEOUT_MS`/`AXON_TOOL_MAX_RESPONSE_BYTES`/`AXON_MCP_DISCOVERY_TTL`. O `McpService` da plataforma
fica em `Platform.mcp` para as rotas da 008. As suítes trocam portas na montagem —
`platform(profile="test", overrides={"providers": …, "mcp_transports": …})` — para programar controller e servidores
MCP (portas de armazenamento não se trocam); sem trocas, o modelo simulado do `test` responde `{"action": "answer"}`
como controller. Uma conversa `agentic` + MCP atravessa a API sem rede
(`tests/bootstrap/integration/test_platform_agentic_mcp.py`).
Os providers remotos da 006 (US2–US5) também: `OpenAIProvider` e `OpenRouterProvider` são arquivos finos sobre a
camada compatível (`adapters/remote.py`), com a credencial lida uma vez, na construção, pela porta `SecretResolver`
(`AXON_OPENAI_API_KEY`/`AXON_OPENROUTER_API_KEY`; ADR-020) — sem ela, o remoto fica registrado e explica a falta
na saúde e na chamada, sem tocar a rede, e o valor da chave nunca entra em mensagem. O `ModelRef` recusa roteamento
automático (`openrouter/auto` e o namespace `openrouter/…`) na construção, antes da allowlist. Nenhuma chamada do papel
`controller` sai sem `response_format` de esquema (guarda pura em `llm/domain/output.py`, aplicada no cliente
instrumentado, com `ModelCall` de erro); o adapter envia `strict: true` e, no OpenRouter, `require_parameters`; recusa
do provider é `ModelCallFailed`, sem reenvio. A 011 monta `llm_secrets` (ambiente no `memory`/`persistent`, memória
vazia no `test`) antes de `providers`, que nos dois primeiros perfis tem `ollama`, `openai` e `openrouter`.
Onde o provider segue as regras da API da OpenAI (`OpenAIProvider` e modelos `openai/…` do OpenRouter —
`_follows_openai_rules`), o adapter as cumpre por quem chama (ADR-023): o esquema de saída vai no subconjunto estrito
(`llm/domain/strict.py`: raiz embrulhada em `value`, opcional obrigatório e anulável, `additionalProperties: false`,
`type` inferido em `const`/`enum`; o que não tem equivalente falha antes da rede) e a conversão é desfeita no conteúdo
da volta; nomes de função com namespace viram apelidos na ida (`llm/domain/names.py`) e voltam nas `tool_calls`. Com
isso a OpenAI serve de controller do `agentic` sem mudança na 005 (verificado com `openai/gpt-4.1-nano`). A integração
paga (`tests/llm/integration/test_remote_real.py`) só roda com as credenciais no ambiente.
A 010 fechou a fase (US2): o `axon-generic` **continua pack** — a FR-005 é regra permanente, e ele agrega `calculate` e
`non_empty_answer` além do prompt — e **sem flow preferido** (FR-007): o Assistant genérico com MCP declara `flow:
agentic`, `controller` e `mcp`; `packs: [generic]` sem `flow` segue no `chat`. O prompt é neutro quanto ao flow
(FR-008): orienta a usar os resultados de ferramentas que a conversa trouxer e nunca manda chamar ferramenta — no
`agentic` ele só chega à geração. A US2 é provada no core sem importar `axon_generic` (o prompt vem pelo seam `PackHooks`)
em `tests/bootstrap/integration/test_generic_agentic_mcp.py`; `test_generic_agentic_real.py` repete com um Ollama de
verdade, só com `OLLAMA_BASE_URL`.

**A Fase 4 do roadmap está completa.** As tags `contracts-v0.1.0` e `v0.1.0` (core e `axon-generic`) existem (ADR-021), e o pack de domínio `axon-scouting` (spec 101,
Fase 4: US1–US3) mora no submódulo `axon-scouting/` (repositório privado `CaioFerreiraB/axon-scouting`): pack `scouting`
0.1.0, dependendo só de `axon-ai-contracts>=0.1,<0.2`, resolvido pela tag por SSH. Na Fase 4 o manifest declara só nome
e versão (o `rag_first`, a coleção e o esquema de configuração chegam na Fase 5, com a US5); o prompt manda declarar
que nenhum documento foi consultado e nunca citar documento (FR-011); e `prepare_context` é uma derivação pura de
(pergunta, dia de referência, léxico) — ramo, temas, tipos de documento e vigência como **intervalo**, com consulta
histórica (`include_superseded`, `previous_version`) —, publicada em `context` e `retrieval_filters`. O dia de
referência é o de Brasília (UTC−03:00 fixo; o core entrega UTC). O léxico (`context/lexicon.py`) é dado em código; a
semente foi aprovada como primeira versão. A suíte padrão roda só com os contratos (SC-003); a integração com a
plataforma fica no grupo opcional `platform` (o `axon-ai` pela mesma tag, Python 3.14) e usa só a superfície da 011
para packs externos (variáveis `AXON_*` e `platform(profile="test")`). Rode dentro de `axon-scouting/`:
`uv run pytest && uv run mypy && uv run ruff check && uv run lint-imports`, e a integração com
`uv run --python 3.14 --group platform pytest tests/integration`. Código do pack é commitado no `axon-scouting`; aqui, o
SDD e o ponteiro do submódulo. O esqueleto da 104 também está lá (`axon_scouting/validators/`): `citation_integrity`
(só fica citação `[[chunk_id]]` que esteve no `generation_context`; as válidas viram `[n]` com a proveniência; sem
nenhuma, aviso de "não fundamentada") e `validity_notice` (aviso para citação não `vigente`, inclusive vigência não
confirmada, sem duplicar o que o modelo já disse) — testados com Turn Views sintéticas e **não publicados** pelo pack
até a Fase 5. A instalação (002 US5) mora no submódulo `axon-deploy/` (repositório privado
`CaioFerreiraB/axon-deploy`, ADR-009 e ADR-022): Dockerfile em três estágios — `core` (contratos, core e
`axon-generic` da tag `CORE_REF`, hoje `v0.2.0`), `packs` (o build-arg `PACKS` + `axon packs check`, que falha o
build com pack incompatível) e `runtime` (sem `uv`, `pip` nem `ensurepip`; usuário sem escrita no ambiente) —, código
privado por montagem SSH do BuildKit (identidades `core` e `packs`, `--no-sources`), `config/packs.yaml` na imagem e
`config/assistants.yaml` montado. `scripts/check-build.sh` é o teste da US5 (local, com o agente SSH; na CI, com deploy
keys só de leitura do `axon` e do `axon-scouting`). Os contratos estão em `0.1.1`
(ADR-024): um validator pode implementar `StreamingValidator` (`open_stream` → sessão com `feed`/`finish`, igual ao
`validate` e só acrescentando no fim); o Pack Hooks abre o filtro com o prefixo desses validators
(`open_answer_stream`) e o motor passa cada pedaço da geração por ele, emitindo depois, como token, o que os validators
em lote só acrescentam. O `citation_integrity` da 104 já filtra (nenhuma citação inventada sai, nem em streaming).

**A Fase 5 do roadmap está completa.** A 102 (US1–US5) existe no `axon-scouting`: `rag/index/` é o seam *Índice do
scouting* — `api.py` com `IndexedChunk`, `IndexFilters` (vigência como intervalo, `include_superseded`,
`previous_version`, ramo ou geral, tipos), `IndexVersion` e `ChunkIndex` (`search`/`get`/`version`, erros
`IndexUnavailable` e `IndexMismatch`) —, com o `QdrantIndex` (um build por coleção atrás de um alias trocado numa
operação, RRF nativo sobre `dense` + `sparse` com IDF, versão do índice na `metadata` da coleção, texto original em
pontos sem vetor) e o `MemoryIndex` (as mesmas fórmulas), numa suíte de conformidade contra memória, Qdrant local e
servidor (`AXON_SCOUTING_TEST_QDRANT_URL`, job `qdrant` da CI). O denso é o `multilingual-e5-small` em ONNX no processo,
fixado por revisão e sha256 (`axon-scouting-corpus model fetch`, nunca baixa em runtime); o esparso, BM25 com stemmer
português. `rag/ingestion/` é o pipeline offline: catálogo `corpus.yaml` validado por inteiro, linhagem sem relógio
(status pela posição; vigência numa data pelas datas), PDFium, limpeza (índice, cabeçalho corrido, hifenização,
crédito de foto), unidade normativa pelo tipo (regra no POR, artigo no estatuto e na resolução), janelas que não
cortam frase, ids determinísticos e execução tudo ou nada que reaproveita os vetores do que não mudou. A CLI
`axon-scouting-corpus` (`ingest`, `reindex`, `status`, `original`, `model fetch`) é composta no `pack.py`. O corpus
inicial — POR 2025 v2.1, Estatuto 2024, Resolução CAN 08/2021 e "Escotistas em Ação — Ramo Lobinho", catálogo revisado
pelo curador, `source_url` em cada entrada — mora em `axon-scouting/corpus/`, no git normal; ingerido, dá 413 chunks
(197 regras, 74 artigos). Configuração por `AXON_SCOUTING_QDRANT_URL`, `AXON_SCOUTING_QDRANT_API_KEY`, `AXON_SCOUTING_INDEX` e
`AXON_SCOUTING_EMBEDDING_DIR`. A 103 (US1–US5) também existe: `rag/retrieval/` tem o `ScoutingRetriever` (o `Retriever`
da 001 sobre `rag.index.api`), que traduz os `retrieval_filters` da 101 sem ler relógio (temas ignorados; filtros
ausentes ou com chave desconhecida → `InvalidFilters`), devolve `score` = similaridade densa — a 102 passou a devolver
`IndexedChunk.similarity` (ADR-025) — e ordena pela fusão com empates desfeitos por metadados (vigente, ramo, tipo),
sem pesos, gravando as marcas nos metadados; o `MetadataReranker` reconstrói essa ordem sem depender da entrada; a
tool `search_docs` devolve 5 trechos por padrão (teto 30). No corpus real a similaridade do e5 é comprimida (coberto
0,85–0,92; fora do corpus até 0,84): o limiar do portão precisa da 105.
O motor tem o flow `rag_first` (spec 005, US3–US4): depois da preparação, abre a sessão de tools e executa cada tool de
recuperação do catálogo com a pergunta e `top_k = candidates` (os filtros do pack vão opacos pelo gateway); recuperação
com status diferente de `ok` é `RetrievalFailed` (`error`) e encerra **sem gerar**. Cada pack reordena os próprios
chunks com o reranker dele (`PackHooks.reranker(composition, pack)`, toque na 002; trecho estranho, repetido, além de
`top_k` ou exceção → `RerankFailed` `notice` e a ordem do retriever), e a junção vai pelas cabeças dos grupos, sem
desfazer a ordem de cada reranker. O portão (`graph/domain/gate.py`, puro) cobre quando há trechos e, havendo limiar,
o melhor score o alcança — **sem limiar por default**; sem cobertura, escala para o loop do `agentic` só se o Assistant
declara `controller` (e há tool), senão gera sem trechos com `CoverageInsufficient` (`notice`). A decisão é o evento
`coverage_gate` da 009 (ADR-017). No caminho coberto, uma chamada de modelo (SC-003): os trechos entram como passo de
tool sintético (`ToolStep.synthetic`, resultado de `ToolSession.fence_chunks`, toque na 004), cortados por posição no
teto (`fit_chunks`), e o `generation_context` é exatamente o que entrou. Todo trecho que o core mostra ao modelo traz
`[documento — seção, p. N · id: <chunk_id>]` (ADR-026), e a recuperação acima do limite do gateway é cortada por trecho
inteiro (`render_within`). `flow_roles()["rag_first"] == ("generation",)`; `RagSettings` vem de `AXON_RAG_CANDIDATES`
(20), `AXON_RAG_PASSAGES` (5) e `AXON_RAG_MIN_SCORE` (sem valor = sem limiar), pela 011, que também passou a
atender o `CollectionCatalog` da 003 pelo Pack Registry (`PackCollectionCatalog`: existem as coleções dos retrievers de
packs habilitados). Prova ponta a ponta sem rede em `tests/bootstrap/integration/test_platform_rag_first.py`. O core está na tag `v0.2.0`
(contratos `0.1.1`, `axon-generic` 0.1.0).
O pack `scouting` está em 0.2.0 (101 US4–US5, com a 104 publicada): o manifest declara `rag_first`, a coleção lógica
fixa `scouting` (o que se configura é o **índice**, o alias no Qdrant) e o `config_schema` — `qdrant_url` (default
`http://localhost:6333`) ou `qdrant_path` (embutido), `index` (`scouting`), `embedder` (`e5`, que exige `embedding_dir`
com `model.onnx` e `tokenizer.json`, ou `hashing`, só para suítes), `default_limit`/`max_limit` (5/30) —, com os
defaults e as combinações conferidos por `read_config` no `pack.py` (configuração inválida deixa o pack em erro, na
introspecção; `packs.yaml` sem `config` falha, porque o default é o e5). A chave do Qdrant vem só de
`AXON_SCOUTING_QDRANT_API_KEY`. O `pack.py` compõe, dentro dos hooks, o `QdrantIndex` (cliente sem checagem de versão na
carga), o `ScoutingRetriever` (tool `scouting.search_docs`), o `MetadataReranker` e os validators `citation_integrity`
e `validity_notice`, nessa ordem. O prompt da Fase 5 traz as cinco prioridades de fonte (US4), a citação `[[id]]` pelo
identificador depois de `id:` (ADR-026), o caminho sem trechos ("nenhum documento oficial foi encontrado") e a
vigência. Contratos e core vêm da **mesma** tag `v0.2.0` (o `uv` não aceita duas fontes para os contratos). A US5 é
provada ponta a ponta no grupo `platform` (`tests/integration/test_rag.py`: Qdrant embutido, embedder de teste, uma
chamada de modelo, citação `[1]`), e uma conversa real com o índice e o e5 cita POR e manual com página e vigência.
A CI do `axon-scouting` marca os submódulos do `axon` com `update = none` antes do `uv sync` (o `uv` os
inicializaria ao clonar a tag, e a deploy key não os lê). A instalação (`axon-deploy`, passada de encaixe da Fase 5
na 002, research R31–R35) traz o RAG: `CORE_REF` `v0.2.0` e o `axon-scouting` fixado no commit da Fase 5; o estágio
`packs` baixa o e5 (`axon-scouting-corpus model fetch /opt/axon-scouting/e5-small`, verificado por sha256) antes do `packs
check`, e o `runtime` o copia; `ORT_DISABLE_TELEMETRY=1`. O `config/packs.yaml` dá ao `scouting` `qdrant_url:
http://qdrant:6333` e o `embedding_dir`; o Assistant `scouting` não declara `flow` (logo `rag_first`) e concede a
coleção. O `docker-compose.yml` sobe o Qdrant (`v1.19.2`, volume `qdrant-data`, sem porta publicada; chave opcional, o
mesmo valor em `QDRANT_API_KEY` e `AXON_SCOUTING_QDRANT_API_KEY`) e a porta do host vem de `AXON_HOST_PORT`. A
ingestão usa a CLI da própria imagem com o `corpus/` de um clone do `axon-scouting` montado (`docker compose run --rm -v
../axon-scouting/corpus:/corpus:ro axon axon-scouting-corpus ingest /corpus/corpus.yaml`). O estágio `core` já clona o
`axon` sem submódulos, então o deploy não precisa do ajuste da CI do pack. Segue a 105 (limiar do portão — sem
ele, pergunta fora do corpus ainda chega à geração com trechos); a curadoria do catálogo fica para depois do
desenvolvimento.

**A Fase 6 do roadmap está em andamento.** A 009 (US2–US4) tem o harness de avaliação em `axon_ai/eval/`, adapter
primário sobre seams: `axon eval run --golden <yaml> [--assistant] [--judge provider/modelo] [--baseline]
[--update-baseline] [--force] [--report] [--principal svc:eval] [--annotate]` roda cada item do conjunto dourado pelo
Execution Engine com a data do item (o único caminho que fixa `reference_time`), sob o grant que a 003 resolve para o
`Principal` da rodada (a ACL do Assistant precisa admiti-lo), e lê o trace da requisição. O conjunto dourado é YAML
(`version: 1`), com evidência por **documento** (seção ou `chunk_id` opcionais, casamento normalizado — sobrevive a
mudança de chunking); item malformado vira `invalid` e o resto roda; evidência que nenhum candidato da rodada casa sai
como aviso "evidência não vista". Para medir, a 005 passou a emitir o evento `retrieval` da 009 (ADR-017) na validação:
os trechos candidatos, reordenados e entregues (id, score, proveniência; o **texto só dos entregues**, cortado em 2.000
caracteres e redigido — é o que o juiz lê). Métricas: recall@k, MRR, recall dos entregues e ganho do rerank (as
**determinísticas**, as únicas que barram o CI), citação resolvível/inventada/esperada, fidelidade e cobertura pelo
juiz offline (Model Router da 006, três julgamentos, média e variância; sem `--judge`, ausentes), latência e tempo até
o primeiro token p50/p95, tokens, chamadas, tokens/s, ações inválidas do controller, erros, e frações de flags e de rotas
do portão (informativas). Métricas de domínio vêm do pack pelo contrato 001 `0.1.2` (`axon_ai_contracts.eval`:
`EvalItem`, `EvalObservation`, `EvalMetric`, hook opcional `eval_metrics` — ADR-027), coletadas pela 002 (seam
`PackEvalMetrics`) e reportadas como `<pack>:<nome>`. Linha de base = um relatório JSON; tolerância absoluta por métrica
(default 0,02); saída 0, 1 (regressão determinística) ou 2 (entrada inválida). `axon eval compare` põe relatórios
lado a lado (benchmark: Assistants que diferem no modelo; RAM e CPU por `--annotate`). O core está na tag `v0.3.0`
(contratos `0.1.2`).
Da 105 (US1, US2), a infraestrutura de avaliação do scouting, sobre um conjunto **semente provisório** — a curadoria das
perguntas reais e a calibração (US3–US5) ficam para depois do desenvolvimento, por decisão do mantenedor: o pack
`scouting` 0.3.0 (contratos `>=0.1.2`, contratos e core da tag `v0.3.0`) publica em `eval_metrics` as métricas puras de
`axon_scouting/eval/` — `context_accuracy` (refaz a derivação da 101 para a pergunta e o dia do item e compara com
`extra.context`), `current_document_rate` (trechos entregues `vigente`, fora de item histórico) e
`validity_notice_rate` (flag `non_current_source` quando a resposta cita fonte não vigente; não determinística). Em
`axon-scouting/eval/`: `golden.yaml` (10 perguntas tiradas do corpus, `extra.provisional`, datas entre aspas),
validado sem o core contra `corpus/corpus.yaml` e o léxico (`tests/eval/test_golden.py`); `packs.yaml` (`embedding_dir:
.cache/e5`, relativo à raiz) e `assistants.yaml` (ACL `svc:eval`); e `baseline.json`, gerado com o corpus real, o e5 e
o gerador simulado do perfil `test`. O workflow `eval.yml` (filtro de caminhos: corpus, `rag/`, `prompts/`,
`context/`, `eval/`, `pack.py`, dependências) ingere o corpus num Qdrant de serviço com o e5 em cache e roda `axon-ai
eval run` contra a base; a integração (`tests/integration/test_eval.py`) chama o comando `axon` em subprocesso. 
**A Fase 7 do roadmap está completa.** Da 008 (US6, US8), a API pronta para o Open WebUI: admissão
(`domain/admission.py`, puro; `ExecutionSlots` no `service.py`, vagas e fila FIFO em memória, por processo) entre a
resolução do grant e o motor — vaga livre executa, vagas cheias com fila livre esperam (em streaming, o aviso de fila sai
na hora como raciocínio), fila cheia é 503 `overloaded` com `Retry-After` antes de qualquer chamada de modelo, espera
esgotada é 503 sem streaming e chunk final de erro (`QueueTimeout`) em streaming; a conversa nova só nasce depois da
admissão. Configuração na 011: `AXON_MAX_EXECUTIONS` (2), `AXON_QUEUE_SIZE` (8; 0 = sem fila) e
`AXON_QUEUE_WAIT_MS` (60 000), provisórios até a medição no hardware alvo. O progresso sai também em
`delta.reasoning_content` — uma linha em português por etapa (`domain/progress_text.py`, indexada pelos estágios que a
005 publica, inclusive `retrieve`/`rerank`/`gate` do `rag_first`; estágio novo cai em "Etapa …") — só até o primeiro
texto. O cabeçalho `x-axon-store: false` torna efêmero o pedido sem id de conversa (nada gravado, sem id); com id, 400
`store_conflict`. A autenticação não mudou: o Open WebUI repassa o access token de cada usuário (`system_oauth`) e a 003
o verifica. A compatibilidade com o Open WebUI v0.12 é provada com o pedido dele como fixture
(`tests/http/open_webui_v0_12.py`). A passada de encaixe da 002 levou isso à instalação (`axon-deploy`, research R36–R40 da 002):
`CORE_REF=v0.4.1`, o pack `scouting` 0.3.0 (com ele, `axon eval run` na imagem) e o perfil `webui` do compose —
Keycloak 26.7.5 de desenvolvimento (`start-dev --import-realm`, dados no volume `keycloak-data` para o `sub` dos
usuários não mudar, realm `config/keycloak/agentic-realm.json`: cliente
`open-webui`, audiência `axon` e `groups` no access token, usuários `ana` e `bia` do grupo `equipe`; o navegador usa
`localhost:8180`, o emissor, e os contêineres `keycloak:8080`, por `KC_HOSTNAME_BACKCHANNEL_DYNAMIC`) e Open WebUI
v0.12.0 configurado só por ambiente (`OPENAI_API_CONFIGS` com `system_oauth` e o cabeçalho, `BYPASS_MODEL_ACCESS_CONTROL`,
tarefas auxiliares desligadas, `DEFAULT_USER_ROLE=user` e chamada de função legada (`DEFAULT_MODEL_PARAMS`) sem as
ferramentas embutidas (`DEFAULT_MODEL_METADATA`) — no v0.12 a nativa é o padrão, e as embutidas iriam em `tools`,
recusado pela plataforma; o cadastro de modelo feito pela tela vence o metadado, mas não os parâmetros; e a sessão de 8 h,
menor que a de 10 h do realm — se a do provedor cai antes, o Open WebUI fica sem token e mostra "Model '' was not
found"); o core lê `AXON_OIDC_*` do `.env` (subject por
`preferred_username`), e o Assistant `interno` (só `group:equipe`) prova a lista por usuário. `scripts/check-webui.py`
(só biblioteca padrão, manual) entra pelo formulário do Keycloak como `ana` e `bia`, compara as listas, manda uma
mensagem montada como a tela de chat do v0.12 (conversa salva, `session_id`) e confere um `POST /v1/chat/completions`
com 200 no log do core. A prova
achou um defeito na 003: o JWKS do Keycloak traz uma chave de cifragem (`use: enc`, `RSA-OAEP`) que derrubava a
atualização inteira e recusava todo token; o `JwksOidcVerifier` agora guarda só chaves de assinatura e ignora, uma a
uma, as que não carregam (003 research R24). O core está na tag `v0.4.1` (contratos `0.1.2`, `axon-generic` 0.1.0).
Depois da Fase 7, a **timeline de status** no Open WebUI (ADR-028; 005 FR-012a, R49; 008 FR-005a, R42): o motor fecha
cada etapa com `StepFinished(stage, outcome)` — desfechos tipados em `graph/api.py` (`ToolCallsOutcome` com
`ToolCallSummary` e `SourceRef`, `RerankOutcome`, `GateOutcome`, `ControllerOutcome`, `GenerationOutcome`,
`CatalogOutcome`), montados por `graph/domain/steps.py`, com argumentos de tool e fontes, sem texto de trecho, de
resultado ou de erro de tool; o motor não mede tempo. Com o cabeçalho `x-axon-progress: status` (padrão `reasoning`;
outro valor → 400), a 008 manda cada início, desfecho, aviso e a conclusão como evento `status` do Open WebUI (chave
`event` do chunk, `delta: {}`), também depois do primeiro texto e sem `reasoning_content`; as linhas pt-BR e os tempos
(pelo `Clock`) saem de `http/domain/timeline.py`. A conexão da instalação manda o cabeçalho, e o `check-webui.py` lê o
`statusHistory` gravado. Core `0.5.0` (tag `v0.5.0`, com o aval do mantenedor).

**A Fase 9 do roadmap está em andamento** (console de administração e identidade própria, ADR-029 a ADR-034). O
provedor de identidade (`axon_ai/identity/`, spec 012, US1–US7) existe como módulo: a plataforma é o próprio emissor OIDC
(ADR-030) — descoberta com backchannel dinâmico, autorização só por código (PKCE S256 obrigatório para cliente público),
troca de código e renovação (rotação com detecção de reuso para cliente público; o confidencial não rotaciona),
`userinfo`, JWKS, revogação e logout —, com as páginas próprias (login por usuário ou e-mail, troca obrigatória da senha
temporária, "Minha conta"; HTML sem script, escape por padrão, CSS do desenho aprovado no Penpot), contas e grupos com o
grupo de administração protegido, senha temporária gerada (só a operação que a define a devolve), argon2id
(`argon2-cffi`, confinado a `adapters/`), bloqueio de 5 falhas em 15 min por usuário e por origem, Google só para contas
cadastradas (vínculo pelo `sub` no primeiro sucesso), chaves RS256 com a privada selada por AES-GCM com subchave HKDF da
chave mestra (ADR-033) e rotação normal ou forçada. Seams em `identity/api.py`: `AccountAdmin` e `LoginSettings` (para a
008) e `PublicKeySet` (a 011 o injeta no verificador da 003); o protocolo é o adapter primário `router(service,
settings)` de `adapters/http.py`. Postgres no schema `identity` (ADR-015); clientes no `identity.yaml` do operador; CLI
`users …` e `identity keys rotate` em `adapters/cli.py` (a 011 registra). A suíte de protocolo usa o authlib como RP
(grupo de desenvolvimento; o authlib 1.9 fala `httpx2`). O encaixe — verificador e superfície `/admin/v1` na 003, rotas
na 008, etapa `identity` e configuração na 011, instalação sem Keycloak na 002 — vem nas passadas delas.
Já encaixados (incremento 9.1): a 003 tem três superfícies (`SCHEMES_OF_SURFACE`; `admin` aceita chave ou OIDC com a
audiência `axon-admin`; `SCHEME_OF_SURFACE` ficou depreciado), admin pelo grupo em qualquer esquema (ADR-031) e o
`JwksOidcVerifier(issuer, source)` com `HttpJwksSource` (provedor externo, com cache) ou `CallableJwksSource` (o
`jwks()` da 012, sem rede); a 011 liga a identidade com `AXON_IDENTITY_ENABLED` (+ `AXON_PUBLIC_URL`,
`AXON_IDENTITY_CLIENTS_FILE`, `AXON_MASTER_KEY`, `AXON_DISPLAY_NAME`, `AXON_LOGO_FILE`,
`AXON_TRUSTED_PROXIES`, `AXON_COOKIE_SECURE`) — etapa crítica `identity` depois de `adapters`, portas
`identity_*` nos três perfis (`bootstrap/identity.py`), router da 012 no app, item crítico `identity` na saúde, chaves
carregadas no início do ciclo de vida no `persistent` e `axon users create|list|disable|enable|password|groups` e
`axon identity keys rotate`. No `test` com identidade, o admin `TEST_ADMIN_USERNAME`/`TEST_ADMIN_PASSWORD` e os
clientes de exemplo vêm de `axon_ai.bootstrap.identity`, e o `TEST_OIDC_TOKEN` deixa de valer (sem identidade, segue
valendo). Com a identidade ligada, o subject é o `preferred_username` (o nome de usuário, como na Fase 7) e a CLI tem
também `axon groups create|list`. A instalação (`axon-deploy`, 002 US7 parcial) já usa isso, com
`CORE_REF=v0.6.0-rc2`: o `axon-ai` roda sempre no `persistent` com o Postgres do compose (`POSTGRES_PASSWORD`,
`AXON_MASTER_KEY`), o Keycloak saiu e o Open WebUI entra pelo login da plataforma (`config/identity.yaml`, cliente
`open-webui` com PKCE S256, contas da Fase 7 religadas pelo e-mail); `scripts/dev-users.sh` cria `equipe`, `ana` e
`bia`, e o `check-webui.py` entra pelo formulário da plataforma.
Incremento 9.2 (a API de administração, sem tela): a 003 tem as **sobreposições** de Assistants de sistema (US10,
ADR-032) — `overrides: [models, mcp]` no YAML libera a seção; a sobreposição guarda a impressão digital da seção do YAML
e fica inativa, com o motivo, se a seção mudar no deploy ou sair de `overrides`; a efetiva vale na resolução seguinte
(cache de 5 s), com histórico e versão por seção, pelo seam `SystemAssistantAdmin`; Postgres na migração
`003_system_overrides.sql`. A 009 tem o **uso e custo** (US5: `UsageDestination` com buffer e lote, relatório por dia
local, modelo ou Assistant, preços com vigência, custo calculado na consulta, origem `production`/`evaluation`), o
**Langfuse** (US6: OpenTelemetry por OTLP/HTTP, confinado a `adapters/langfuse.py`; o exportador observado leva a
falha à saúde) e a **captura opcional** de prompt e resposta (US7: o evento `model_exchange`, que a 006 emite e que só
chega a destinos com `accepts_content`, nunca ao JSONL nem à memória), com ajustes em precedência instalação > console
> padrão e o segredo selado pela chave mestra (ADR-033, ADR-034); schema `observability`. A 008 tem a superfície
**`/admin/v1`** (US9, ADR-031; `http/adapters/admin.py`, formatos puros em `http/domain/admin_*.py`): `me` com a marca
da instalação, Assistants de sistema e sobreposições, "testar modelo" pela 006, MCP globais, uso e preços, Langfuse e
captura, contas, grupos e login da 012, chaves e saúde; token da console (audiência `axon-admin`) ou chave; quem não
administra recebe em toda rota o 404 de rota inexistente; `no-store` e `X-Request-Id` em toda resposta (middleware do
prefixo); versão no corpo e 409/422 com `param`. A 011 liga tudo (`bootstrap/observability.py`): portas
`system_overrides`, `usage_store`, `price_store`, `destination_settings` e `langfuse_transport` (simulado no `test`),
`AXON_LANGFUSE_*` (tudo ou nada) e `AXON_USAGE_TIMEZONE`/`AXON_USAGE_RETENTION_DAYS`, tarefas `usage.flush`
(2 s) e `usage.purge`, ajustes lidos quando o pool abre, itens `trace:usage`/`trace:langfuse` e os modelos efetivos na
saúde; `TEST_ADMIN_USERNAME`/`TEST_ADMIN_PASSWORD` também em `axon_ai.bootstrap.profiles`. A prova sem rede é
`tests/bootstrap/integration/test_platform_identity_admin.py`.
Incremento 9.3: a **console de administração** (spec 013, US1–US7) em `axon-ai/console/` — SPA React 19 + TypeScript
(Vite 8, React Router 8, TanStack Query, `zod`, Radix, gráficos em SVG próprio com `d3-scale`, CSS Modules sobre os
tokens do desenho aprovado no Penpot, Mona Sans e JetBrains Mono servidas pela própria console). Entra pela 012 como
cliente público `console` (PKCE, `nonce`, tokens só em memória; renovação pelo token de renovação) e fala só com
`/admin/v1`; telas de uso e custo (página inicial), preços, Assistants (Modelos — a sobreposição de `models` é a seção
inteira —, MCP e Histórico), servidores MCP, observabilidade e acesso (usuários, grupos e login), temas claro e escuro.
Fronteira por ESLint: `fetch` só em `src/api/` e `oidc-client-ts` só em `src/auth/`. Rode a partir de `axon-ai/console/`
com `source ~/.nvm/nvm.sh && nvm use` (Node 24): `npm ci && npm run typecheck && npm run lint && npm test` (Vitest + MSW)
e `npx playwright install chromium && npm run e2e` (Playwright + axe; o `webServer` sobe a plataforma em memória com
`uv run python console/e2e/serve_platform.py` na porta 8765 e o `vite preview` na 4173). O nginx da instalação está em
`deploy/nginx.conf.template` (teste de fumaça: `e2e/serve_nginx.sh` e `CONSOLE_NGINX_URL=http://127.0.0.1:8080 npx
playwright test e2e/serving.spec.ts`); a CI é `.github/workflows/console.yml`. O e2e achou dois defeitos da 012,
corrigidos: `Referrer-Policy: same-origin` (com `no-referrer`, o Chromium mandava `Origin: null` no formulário de login;
R18) e a Mona Sans servida pelas páginas (R19). A instalação com a console (002 US7) é o incremento 9.4.
Custo informado e providers prontos (ADR-035, core `0.6.0rc5`, contratos `0.1.3`): o OpenRouter informa o custo de cada
chamada em `usage.cost` (`ChatUsage.cost`), o adapter o lê e o pede (`usage.include`), e o `ModelCall` o leva em
`cost_usd`; no relatório da 009 o informado vence a tabela, que só cobre os tokens das chamadas sem custo informado
(coluna `reported_cost_usd`, migração `004`). O Model Router lista os providers com a prontidão de cada um
(`providers()`; o remoto pela chave, o local se responde), exposto em `GET /admin/v1/providers`, e a console escolhe o
provedor numa lista — no modelo por papel e no novo preço — com o modelo digitado sem o prefixo.
Provider que informa o custo não tem preço de tabela (ADR-036, core `0.6.0rc6`): `ModelProvider.reports_cost` (o
OpenRouter declara `True`) chega ao `ProviderStatus` e a `GET /admin/v1/providers`, e `POST /admin/v1/prices` recusa o
preço dele com 422. A console mostra o custo parcial (selo "Parcial") na tabela e no gráfico, "Não informado" sem custo
nenhum, e nunca "Cadastrar" para esse provider; a tabela de preços o tira do formulário. O `UsageDay` da 009 traz as
requisições distintas do dia (`requests`), e o gráfico da tela de uso alterna entre custo, requisições e tokens (total,
entrada, saída) — `metrica` e `tokens` na URL; por modelo, requisições numa barra só (`DailyChart`, `series.ts`).

Incremento 9.5, **identidade Axon** (ADR-037, ADR-038, ADR-039): a plataforma se chama Axon, em corte seco. Os
nomes antigos (`ai-core`, `ai_core`, `AI_CORE_*`, `ai-scouting`, `agentic-app`…) só aparecem no histórico — ADRs
aceitos, `docs/archive/`, os `research.md`/`plan.md`/`tasks.md` já executados — e se leem pela tabela do ADR-037. A
distribuição do core é `axon-ai` (import `axon_ai`, pasta `axon-ai/`, comando `axon`, prefixo `AXON_`); o boot recusa
qualquer `AI_CORE_*` e o pack, qualquer `AI_SCOUTING_*`, nomeando a variável nova. Contratos `axon-ai-contracts` 0.2.0
(tag `contracts-v0.2.0`), core `0.7.0rc1` (tag `v0.7.0-rc1`), `axon-generic` 0.2.0, `axon-scouting` 0.4.0; grupo de
entry point `axon.packs`; audiências `axon`/`axon-admin`; chave de API `axn_<id>_<segredo>`; cookie `axon_session`;
rótulos HKDF `axon-ai/identity/v1` e `axon-ai/observability/v1`; cabeçalhos `x-axon-store`/`x-axon-progress` (os antigos
recebem 400); extensão `x_axon`; `me.instance.custom` na 008. A marca (ADR-038): sem nome nem logotipo da instalação,
as páginas da 012 e a console mostram o lockup Axon; com eles, a marca da instalação e "com Axon"; o favicon é sempre o
símbolo; os tokens da marca têm contraste AA nos dois temas, com o hover do botão primário no escuro em `#1D4ED8`
(ADR-039). Os arquivos da marca estão em `brand-kit/` (`svg/`, tokens, `BRAND.md`). Os repositórios são `axon`,
`axon-scouting` e `axon-deploy`, e os submódulos ficam em `axon-scouting/` e `axon-deploy/`; a instalação usa o projeto
`axon` fixo no compose (serviço `axon`, Postgres `axon`, `/etc/axon`). Os segredos de CI `AGENTIC_APP_DEPLOY_KEY` e
`AI_SCOUTING_DEPLOY_KEY` mantêm o nome. O flow `agentic` não muda de nome.

O `axon-generic` é o exemplo a copiar num pack novo: piso de Python dos contratos (`>=3.12`, não o 3.14 do core),
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

Verificação dos contratos (a partir de `axon-ai/`; roteiro completo no quickstart da 001):

```bash
uv sync
uv run pytest && uv run mypy && uv run ruff check packages && uv run lint-imports
uv run python packages/contracts/tools/check_clean_env.py      # SC-001: pack só com os contratos
```

O workspace exige Python 3.14 (por causa do core); o piso 3.12 dos contratos roda fora dele:
`uv run --no-project --python 3.12 --with ./packages/contracts --with pytest --with pytest-asyncio --with hypothesis
--with packaging pytest packages/contracts/tests`.

Conformidade contra o Postgres real (ADR-015; a CI do core tem o serviço): sem `AXON_TEST_POSTGRES_DSN`, esses casos
são pulados.

```bash
docker run -d --rm --name axon-ai-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:17
AXON_TEST_POSTGRES_DSN=postgresql://postgres:pg@localhost:55432/postgres uv run pytest
```

Nesta máquina, rode o `uv` com `XDG_DATA_HOME=$HOME/.local/share` (o VSCode snap aponta o XDG para uma pasta que some).
