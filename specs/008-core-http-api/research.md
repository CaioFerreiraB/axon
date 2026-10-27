# Research — 008 HTTP API (Fase 1, US1)

> Decisões pré-aprovadas vêm do [design.md](design.md) e dos ADRs da *Module Boundary*; não são re-pesquisadas.
> As quatro clarificações de 2026-09-21 estão na spec e aparecem aqui como R1, R2, R5 e R6.

## R1 — Duas superfícies desde a Fase 1, com o Principal atrás de uma porta

**Decision**: `/v1` e `/private/v1` são montadas agora, ambas com a rota de chat completions. O Principal chega pela
porta `Authenticator`, declarada por este módulo; na Fase 1 a composition root (011) injeta um adapter anônimo de
desenvolvimento, e na Fase 2 a 003 fornece o verificador real.

**Rationale** (clarificação de 2026-09-21; `design.md`, "Duas superfícies"): a US1 fala nas duas superfícies, e montar
as duas agora custa um prefixo a mais. O que não pode acontecer é a autenticação virar reescrita das rotas na Fase 2 —
com o Principal atrás de porta, ela vira troca de adapter, que é a promessa do ADR-012. O adapter anônimo é explícito
no nome e no log de boot, para que ninguém o confunda com configuração de produção.

**Alternatives considered**: só `/v1` até a Fase 2 (as rotas e a suíte ponta a ponta mudariam depois); duas superfícies
sem nenhuma noção de Principal (o caminho da requisição teria de ser reescrito quando a ACL chegasse).

## R2 — O grant vem de um resolvedor cuja forma este módulo publica

**Decision**: `ports.py` declara `GrantResolver` (`resolve(model, principal) → ExecutionGrant`) e `Principal`, ambos
`Protocol`. A 011 injeta um resolvedor montado da configuração na Fase 1; a 003 passa a fornecê-lo na Fase 2.

**Rationale** (clarificação de 2026-09-21; princípio IV): resolver Assistant é decidir *o que uma execução pode fazer* —
é a fronteira de isolamento, e não pode morar na camada HTTP. Publicar a forma exigida mantém a direção `008 → 003` do
grafo de dependências e repete a solução já usada na 005 (grant) e na 006 (política de modelos): o consumidor declara a
forma, o dono fornece o valor. O `ExecutionGrant` em si é o `Protocol` da 005, importado do `api.py` dela.

**Alternatives considered**: a API montar o grant a partir da configuração (põe a fronteira de isolamento dentro do
adapter primário); antecipar `ai_core/assistants/` (código sem spec planejada, numa fase que não é a dele).

## R3 — Formato de resposta: chunk da OpenAI, com o identificador de requisição visível

**Decision**: streaming emite `chat.completion.chunk` e o encerramento `data: [DONE]`; sem streaming, um
`chat.completion`. O identificador de requisição usado no trace vai no cabeçalho `X-Request-Id` e no campo `id` da
resposta, como `chatcmpl-<request_id>`.

**Rationale** (FR-002, FR-010, SC-004): é o formato que os clientes padrão esperam, e o cabeçalho é onde um cliente
genérico consegue lê-lo sem entender campo extra. Repetir o identificador no `id` do corpo custa nada e torna o trace
alcançável a partir de um log de cliente. Nenhum campo obrigatório do formato é omitido.

**Alternatives considered**: identificador só no corpo (invisível para quem lê cabeçalhos, como proxies e o Open
WebUI); identificador próprio, desligado do trace (quebraria FR-010, que é o que liga resposta e trace).

## R4 — A construção do chunk é pura; só a escrita na conexão é adapter

**Decision**: `domain/openai_chunks.py` converte `ExecutionEvent` (005) em dicionários de chunk; `adapters/sse.py`
apenas serializa (`data: …\n\n`) e cuida da conexão. O `design.md` previa a tradução inteira em `adapters/sse.py`.

**Rationale**: a tradução é uma regra de formato, determinística e sem I/O — é exatamente o que o princípio XIII manda
manter fora do adapter, e é onde moram os detalhes que quebram cliente (papel só no primeiro chunk, `finish_reason` só
no último, campo extra ignorável). Testá-la sem subir servidor deixa a suíte rápida e as regressões óbvias. A divisão
preserva o arquivo que o `design.md` nomeia.

**Alternatives considered**: tudo em `adapters/sse.py` (cada regra de formato exigiria um servidor de teste para ser
verificada).

## R5 — Progresso entra no stream já na Fase 1

**Decision**: `ProgressEvent` (005) vira um chunk com `delta` vazio e um campo extra com a etapa. Clientes padrão o
ignoram; a SC-003 passa a ser observável.

**Rationale** (clarificação de 2026-09-21): o motor já emite o progresso — inclusive antes da primeira chamada de
modelo (005 R2) —, então o custo é a tradução. No hardware alvo, o intervalo entre o envio e o primeiro token é de
segundos, e sem sinal nenhum a interface parece travada. O resto da US6 (progresso de tool, aviso de fila) continua nas
fases deles.

**Alternatives considered**: descartar progresso até a Fase 7 (deixaria a fase do streaming sem o sinal que a própria
spec mede em SC-003).

## R6 — Falha depois do stream aberto encerra o stream normalmente

**Decision**: quando o evento final traz erros, o chunk final sai com `finish_reason` de erro e os motivos num campo
extra, seguido de `[DONE]`. A conexão fecha limpa. Antes de o stream abrir, o erro é HTTP: requisição inválida → 400
nomeando o campo; Assistant inexistente ou não autorizado → 404 (regra 404-não-403 da 003).

**Rationale** (clarificação de 2026-09-21; 005 R6): o status 200 já foi enviado quando o primeiro chunk saiu — não há
como voltar atrás. Encerrar normalmente preserva os tokens já entregues e evita cliente pendurado; o campo extra dá o
motivo a quem sabe lê-lo. O motor já garante que nada levanta depois do primeiro evento, então o adapter traduz um
evento, não uma exceção.

**Alternatives considered**: evento SSE `error` (clientes OpenAI padrão não o entendem e podem esperar o marcador de
fim para sempre); fechar a conexão abruptamente (indistinguível de queda de rede).

## R7 — Identificador de requisição por porta

**Decision**: `ports.py` declara `RequestIds` (`next() → str`); adapters: um baseado em identificador aleatório e um
sequencial para testes.

**Rationale**: o princípio XIII manda aleatoriedade passar por porta, e aqui ela tem consequência visível — o
identificador aparece na resposta (FR-010) e é a chave do trace (009). Com a porta, a suíte verifica o valor exato em
vez de conferir formato.

**Alternatives considered**: gerar no adapter com a biblioteca padrão (testes teriam de casar por expressão regular, e
o identificador do trace deixaria de ser verificável ponta a ponta).

## R8 — Rejeições que entram já nesta fase

**Decision**: a rota de chat completions rejeita, antes de qualquer execução: campo de data de referência (FR-012),
`tools` e `functions`. Ambas com 400 que nomeia o campo.

**Rationale**: as duas são sobre a rota que está sendo entregue agora, e as duas são de segurança, não de conveniência.
FR-012 foi resolvida por clarificação própria (2026-09-14) e o ADR-013 depende dela para que a data de avaliação só
exista em processo; `tools`/`functions` é ampliação de capacidade, que o princípio IV proíbe — aceitar em silêncio
agora seria criar um buraco para fechar depois. O resto da US3 (requisição nativa) continua na Fase 2.

**Alternatives considered**: aceitar e ignorar os campos (o cliente acreditaria que suas tools seriam usadas); adiar
para a Fase 2 (deixaria a rota da Fase 1 aceitando o que a spec proíbe).

## R7b — A porta de relógio nasce nesta fase

**Decision**: `ports.py` declara `Clock` (`now()`), com `SystemClock` e `FixedClock` como adapters.

**Rationale** (apontado pelo `/speckit-analyze` de 2026-09-21): o formato da OpenAI tem um campo `created` em toda
resposta e em todo chunk — logo, **esta** fase lê o relógio, e o princípio XIII manda que tempo passe por porta. Sem
ela, o adapter chamaria o relógio do sistema direto e o teste de construção de chunk teria de ignorar o campo. A
expiração de conversas, que era o motivo original da porta no `design.md`, continua sendo Fase 2 — mas a porta já tem
consumidor agora.

**Alternatives considered**: ler o relógio no adapter e ignorar o campo nos testes (viola o princípio XIII e deixa um
campo da resposta sem verificação).

## R9 — Escopo da fase

**Decision**: a Fase 1 entrega a **US1** — chat completions com e sem streaming, nas duas superfícies — mais FR-010
(identificador de requisição) e as rejeições do R8. Ficam para depois: listagem de modelos (US2), requisição nativa
(US3), CRUD de assistants e MCPs (US4), introspecção e saúde (US5), progresso de tool e fila (US6), conversas (US7) e
Open WebUI (US8). Em consequência, **não** nascem nesta fase as portas `ConversationStore`, `HealthProvider` e `Clock`.

**Rationale**: `docs/roadmap.md` põe `008 · US1` na Fase 1; US2–US5 e US7 na Fase 2; US6 e US8 na Fase 7. Sem
armazenamento de conversa não há o que expirar, e sem saúde agregada não há o que reportar — declarar essas portas
agora seria porta sem consumidor (princípio XIII).

**Alternatives considered**: antecipar as conversas (dependem de armazenamento persistente e da noção de dono, que é o
Principal real da Fase 2).

## R10 — Testes pela própria API, sem rede

**Decision**: a suíte usa o cliente de teste do framework HTTP contra a app montada em processo, com o motor real, o
Pack Runtime real, o `ai-generic` e o provider simulado da 006. Nenhum servidor, nenhuma porta TCP, nenhum modelo de
verdade.

**Rationale**: é o que a SC-002 pede ("a suíte ponta a ponta completa roda apenas via HTTP") e o que prova a fase: a
conversa atravessa HTTP, motor, packs e router. O cliente de teste exercita rota, serialização e streaming de verdade;
só o modelo é simulado.

**Alternatives considered**: duplo do motor (testaria a tradução contra a ideia que a API faz do motor, e não contra o
motor); servidor de verdade em porta local (mais lento e mais frágil, sem cobrir nada a mais).

---

# Fase 2 (2026-09-30): US2, US3, US4 (Assistants), US5 (packs, chaves, saúde) e US7

As cinco clarificações de 2026-09-30 estão na spec e aparecem aqui em R12, R16, R19, R20 e R14. A numeração segue a
da Fase 1 (o R11 citado no plano da Fase 1 são os contratos de import-linter).

## R12 — Escopo da Fase 2

**Decision**: entram a listagem de modelos (US2), a requisição nativa (US3), o CRUD de Assistants de usuário (US4, a
metade de Assistants), a superfície privada — introspecção de packs, administração de chaves e saúde (US5) — e as
conversas no servidor (US7), com exclusão e expiração. **Não** entram: endpoints de MCP (Fase 3, com a 007 —
clarificação 1), fila, limite de concorrência e progresso de tool (US6, Fase 7) e Open WebUI (US8, Fase 7).

**Rationale** (`docs/roadmap.md`: "008 · US2, US3, US4, US5, US7"; clarificação de 2026-09-30): sem o registry da 007
os endpoints de MCP não teriam onde gravar nem o que validar.

**Alternatives considered**: endpoints de MCP respondendo 501 (rota sem dono dos dados); porta com registry vazio
(código que a 007 substituiria inteiro).

## R13 — A troca para os seams da 003 é atômica: API e composition root no mesmo passo

**Decision**: `http/ports.py` deixa de declarar `Principal`, `Authenticator`, `GrantResolver` e `AssistantNotFound`; a
API passa a importá-los, com `AssistantDirectory`, `ApiKeyAdmin` e os erros, de `ai_core.assistants.api` (a seta
`008 → 003` do grafo). Na mesma passada, a composition root (011) é ajustada no estritamente necessário para continuar
montando a plataforma: constrói `AssistantsService` e `AccessService` da 003 com os adapters em memória, entrega-os à
app, acrescenta a etapa de boot "validação de Assistants" (011 FR-002) no lugar do `validate_flows` provisório, e
remove `bootstrap/grants.py`. O autenticador dos perfis `memory` e `test` continua o anônimo de desenvolvimento, agora
produzindo um `Principal` da 003 (`user:anonymous`, esquema da superfície). O que é da 011 na Fase 2 — perfil
persistente, autenticação real nos perfis, subcomandos, saúde agregada, agendamento da expiração — fica na passada dela.

**Rationale** (003 research R2; 011 plan, "Seam Notes": "o bootstrap troca o adapter e a etapa de validação de
Assistants entra na lista"): a composition root importa hoje as portas provisórias da 008 (`AssistantNotFound`,
`Principal`, `DevelopmentPrincipal`). Trocar o tipo na 008 sem trocar o adapter no boot deixaria a plataforma sem
montar entre duas passadas; e as rotas novas (modelos, CRUD, chaves) só funcionam com os serviços reais da 003. A
exceção fica declarada no gate de fronteira, limitada aos arquivos listados no plano.

**Alternatives considered**: passar a 011 antes (a 011 dependeria de rotas e portas que só existem depois desta
passada); manter as portas provisórias com adaptadores de tradução no boot (código de transição sem dono, que teria de
traduzir exceções e tipos de Principal nos dois sentidos).

## R14 — Erros no formato da OpenAI, com um status por causa

**Decision**: todo erro sai como `{"error": {"message", "type", "param", "code"}}`, o envelope da OpenAI, com o
identificador de requisição no cabeçalho `X-Request-Id` quando houver:

| Causa | Status | `type` / `code` |
|---|---|---|
| credencial ausente ou recusada | 401 | `authentication_error` |
| inexistente **ou** não autorizado (Assistant, conversa, recurso administrativo) | 404 | `not_found_error` — mesmo corpo nos dois casos |
| campo inválido, de ampliação, de data de referência, modelo fora da allowlist, rascunho fora da política | 400 | `invalid_request_error`, `param` = o campo |
| nome de Assistant de usuário já usado pelo dono | 409 | `conflict` |
| Assistant autorizado, mas indisponível (clarificação 4) | 424 | `assistant_unavailable`, com `x_ai_core.reasons` |
| cota do par (Principal, Assistant) | 429 + `Retry-After` (segundos, arredondado para cima) | `rate_limit_exceeded` |

**Rationale** (FR-009, FR-020, SC-004): clientes da OpenAI leem esse envelope; o `{"detail": ...}` da Fase 1 era o
padrão do framework, não o formato prometido. O 424 não é repetido pelos SDKs (que repetem 409, 429 e 5xx) e não se
confunde com a sobrecarga (503, Fase 7).

**Alternatives considered**: manter `{"detail": ...}` (clientes da OpenAI perdem a mensagem estruturada); 503 para
indisponível (rejeitado na clarificação).

## R15 — A credencial é o token do cabeçalho `Authorization: Bearer`

**Decision**: o adapter extrai o token de `Authorization: Bearer <token>` e o entrega a `authenticate` (003 recebe o
token puro). Cabeçalho ausente, outro esquema ou token vazio → `credential=None` → 401. O mesmo cabeçalho nas duas
superfícies: é o que os SDKs da OpenAI enviam com `api_key`.

**Rationale** (003 contrato do `Authenticator`: "extrair o token do cabeçalho é da 008"; SC-004): um cabeçalho só
para OIDC e chave de API deixa qualquer cliente OpenAI usar as duas superfícies sem adaptação.

**Alternatives considered**: `X-API-Key` na superfície privada (cliente OpenAI não o envia).

## R16 — `/v1/models`: uma entrada por Assistant, id curto

**Decision**: `GET /v1/models` e `GET /private/v1/models` devolvem `{"object": "list", "data": [...]}` com uma entrada
por item de `AssistantDirectory.discover(principal)`: `id` = nome do Assistant (`geral`, `~meu-rag`), `object` =
`"model"`, `created` = instante da listagem (porta `Clock`), `owned_by` = `"system"` ou o subject do dono, e
`x_ai_core` = `{generation, description, origin, allow}`.

**Rationale** (clarificação 2; FR-003; 003 R12): id estável quando o operador troca o modelo, inequívoco com modelos
que contêm `/`, sem rede na listagem. Pedir outro modelo da allowlist continua possível pelo id completo (003 R5).

**Alternatives considered**: ver a clarificação 2.

## R17 — Requisição nativa: outro formato de pedido, a mesma resposta

**Decision**: `POST /v1/chat` e `POST /private/v1/chat` recebem `{"assistant", "model"?, "messages", "stream"?,
"conversation_id"?}`. `model` é só a parte que restringe (`qwen3:8b` ou `ollama/qwen3:8b`), combinada com `assistant`
no id que a 003 resolve. Campo desconhecido é recusado nomeando o campo (400); `WIDENING_FIELDS` da 003 é recusado com
a mensagem de ampliação; data de referência, com a da FR-012. A resposta é a mesma da compat (chunks SSE ou
`chat.completion`).

**Rationale** (US3; FR-004; 003 R13): a requisição nativa existe para deixar explícito na interface que ela só nomeia
e restringe — por isso é estrita, enquanto a compat tolera campos da OpenAI que ignora. Um segundo formato de
resposta seria mais uma superfície para manter, sem consumidor que precise dele.

**Alternatives considered**: formato de evento próprio na resposta (dois formatos para os mesmos eventos); rota
`/v1/assistants/{nome}/chat` (o nome do Assistant iria na URL e na conversa ao mesmo tempo).

## R18 — A compat também recusa a lista da 003

**Decision**: a lista de campos recusados na compat passa a ser `WIDENING_FIELDS` da 003 — a do Phase 1 (`tools`,
`functions`, `tool_choice`, `function_call`) está contida nela. Campos desconhecidos continuam tolerados na compat.

**Rationale** (003 R13: "a lista é da 003, a aplicação é da borda"): uma fonte só para uma regra de segurança.

**Alternatives considered**: manter a lista própria (duas fontes que divergiriam).

## R19 — Assistants de usuário: CRUD na superfície pública, sobre o `AssistantDirectory`

**Decision**: `GET /v1/assistants` (os próprios, com estado), `POST /v1/assistants`, `GET|PUT|DELETE
/v1/assistants/{nome}` (com ou sem `~`). O corpo espelha o `UserAssistantDraft` da 003, com modelos em texto
`provider/modelo`. As rotas só fazem o mapeamento JSON ⇄ rascunho (`domain/assistant_body.py`, puro) e chamam o seam.
Só na superfície pública (FR-006).

**Rationale** (US4; 003 contrato do `AssistantDirectory`): regras — política, prefixo, 404 para nome alheio — são da
003; a API não repete nenhuma.

**Alternatives considered**: CRUD também na privada (a FR-006 o põe na pública; serviços não criam Assistants de
usuário).

## R20 — Superfície privada: packs e chaves só para administradores, saúde para qualquer chave

**Decision**: `GET /private/v1/packs` (entradas do Pack Registry) e `POST|GET /private/v1/admin/keys`,
`DELETE /private/v1/admin/keys/{key_id}` (sobre o `ApiKeyAdmin`) respondem só ao grupo de administração, com 404 para
os demais; `GET /private/v1/health` responde a qualquer chave válida, com 200 quando tudo está saudável e 503 quando
algum item não está. A checagem de administrador para os packs entra por uma porta que esta spec declara —
`AdminGate.is_admin(principal)` —, satisfeita pelo `AccessService` da 003, que já tem a regra.

**Rationale** (clarificação 5; 003 FR-015): a regra "chave de API **e** grupo de administração" é da 003; declarar a
forma exigida e deixar a 003 cumpri-la repete o arranjo da Fase 1 (a 008 declara, a 003 cumpre) sem duplicar a regra
nem mudar o seam `ApiKeyAdmin`. 503 na saúde é o que balanceadores e monitores esperam.

**Alternatives considered**: repetir a regra do grupo aqui (duas fontes para uma regra de acesso); acrescentar o método
ao seam `ApiKeyAdmin` (mudaria um seam da 003).

## R21 — Conversas no servidor: porta `ConversationStore`, dono = subject

**Decision**: a porta guarda conversas por (subject do dono, id). Id `conv_<hex>` gerado por uma instância própria da
porta `RequestIds`. Fluxo por requisição de chat:

1. **com `conversation_id`**: a conversa precisa ser do subject (senão 404) e do mesmo Assistant (senão 400 com
   `param = conversation_id`); o histórico armazenado mais a **última** mensagem de usuário do pedido formam as
   mensagens da execução — mensagens de assistente ou de tool vindas do cliente são descartadas (SC-005);
2. **sem `conversation_id`**: a execução usa as mensagens do pedido (padrão da OpenAI) e uma conversa nova é criada
   antes da execução, para que o id saia no primeiro chunk;
3. **no evento final sem erro**: grava-se a troca — a última mensagem de usuário e a resposta, com `request_id`,
   citações e marcações — e atualiza-se a última atividade. Se a conversa foi apagada no meio, a gravação não
   acontece (FR-018). Execução que falhou não grava a troca.

Compat: `conversation_id` como campo extra do corpo; a resposta devolve o id no cabeçalho `X-Conversation-Id` e em
`x_ai_core.conversation_id` (no primeiro chunk, em streaming). Rotas `GET /v1/conversations` (paginada por cursor),
`GET|DELETE /v1/conversations/{id}`, e as mesmas em `/private/v1` — o mesmo subject as alcança pelas duas superfícies
(clarificação 3). Expiração: `ConversationService.expire()` apaga as inativas há mais que o prazo (180 dias por
padrão), a partir do relógio da porta; quem agenda é a 011.

**Rationale** (US7; FR-008, FR-013–FR-015, FR-018, FR-019; `design.md`, "Conversas no servidor"): na criação só a
troca é gravada, e não o histórico que o cliente mandou — senão uma mensagem de assistente forjada no primeiro pedido
entraria nas execuções seguintes pelo id. Criar antes de executar é o que permite devolver o id já no primeiro chunk.

**Alternatives considered**: criar a conversa só depois do sucesso (o id não sairia no primeiro chunk); gravar todo o
histórico enviado na criação (quebraria a SC-005).

## R22 — Postgres das conversas: schema `http`, mesmo padrão da 003

**Decision**: `adapters/conversations_postgres.py` com as tabelas `http.conversations` e `http.messages` (mensagens com
`seq` por conversa e `ON DELETE CASCADE`), migrações em `adapters/sql/` aplicadas por `migrate(pool, now=…)` sob trava
consultiva — o mesmo desenho do adapter da 003 (ADR-015). Conformidade memória × Postgres com
`AI_CORE_TEST_POSTGRES_DSN`.

**Rationale** (ADR-015; design.md, "Persistência"): a convenção já está fixada; repeti-la aqui é seguir o ADR, não
decidir de novo.

**Alternatives considered**: nenhuma além do ADR-015.

## R23 — Portas novas e retiradas

**Decision**: `ports.py` fica com `RequestIds`, `Clock`, `ConversationStore`, `HealthProvider` e `AdminGate`. Saem
`Principal`, `Authenticator`, `GrantResolver` e `AssistantNotFound`, que agora são da 003 (R13). `HealthProvider.health()`
devolve um `HealthReport` (itens com nome, estado e detalhe) que a 011 monta (US5 dela); até lá, a composition root
entrega um provedor mínimo a partir do relatório de boot.

**Rationale** (princípio XIII; design.md, "Portas e adapters"): cada porta tem I/O, não-determinismo ou troca prevista
— armazenamento, saúde agregada montada fora do módulo, regra de acesso de outro módulo.

**Alternatives considered**: a 008 calcular a saúde (conheceria os demais módulos, o que o design proíbe).

## R24 — Testes

**Decision**: `domain/` puro (corpos da requisição nativa e do rascunho, envelope de erro, entrada de modelo);
`contract/` por grupo de rotas, com os serviços **reais** da 003 sobre adapters em memória (principals de teste com
`StaticOidcVerifier` e chaves semeadas), e a conformidade da `ConversationStore` em memória × Postgres; `integration/`
com a conversa atravessando um "reinício" — um serviço novo sobre o mesmo armazenamento — e a suíte ponta a ponta da
011 no perfil `test`.

**Rationale** (R10 da Fase 1; SC-002, SC-005, SC-007): as regras de acesso são da 003, e testá-las contra dublês
testaria a ideia que a API faz delas.

**Alternatives considered**: dublês da 003 (não pegariam divergência de tipo nem de exceção).

---

# Fase 3 (2026-10-02): passada de encaixe

Insumos: a clarificação de 2026-10-02 (FR-022); a nota para a 008 no plano da
[007](../007-core-mcp-integration/plan.md) ("Seam Notes": CRUD de usuário em `/v1`, globais em `/private/v1` com
`AdminGate`, saúde com `check`, erros que herdam da 003); [ADR-018](../../docs/adr/ADR-018-seam-execution-engine-fase-3.md)
(gravidade dos registros); a 011, que já expõe o registry em `Platform.mcp`.

## R25 — Escopo da passada

**Decision**: rotas de MCP do usuário (`/v1/mcp`) e globais (`/private/v1/mcp`, grupo de administração) sobre o seam
`McpRegistry` da 007, com saúde por servidor; desfecho da execução por gravidade (FR-022) e o cabeçalho
`x-should-retry: false` nas falhas de execução; a US6 cen. 1 (progresso de tool) e a US4 cen. 1 (MCP próprio + Assistant
que o usa nos modelos) cobertas por teste. Toque declarado na 011: passar o registry a `create_app`. **Fora**: fila e
limite de execuções simultâneas (FR-016/FR-017, Fase 7), Open WebUI (US8).

**Rationale**: é o que a 007 e o ADR-018 deixaram para a 008 na Fase 3.

**Alternatives considered**: deixar o CRUD de MCP para a Fase 7 (os MCPs de usuário são a extensão do usuário prevista
pelo ADR-003, e a 007 já os oferece).

## R26 — Rotas de MCP do usuário, só na superfície pública

**Decision**:

| Rota | Seam (007) | Sucesso |
|---|---|---|
| `GET /v1/mcp` | `mine(principal)` | 200, lista |
| `POST /v1/mcp` | `create_mine` | 201 |
| `GET /v1/mcp/available` | `available(principal)` | 200, o que o Principal pode referenciar (próprios e globais liberados), sem endpoint nem política de global |
| `GET /v1/mcp/{alias}` | `get_mine` | 200 |
| `PUT /v1/mcp/{alias}` | `update_mine` | 200 |
| `DELETE /v1/mcp/{alias}` | `delete_mine` | 204 |
| `GET /v1/mcp/{alias}/health` | `check(alias, owner=subject)` | 200, saúde do servidor do próprio usuário |

`{alias}` aceita com ou sem `~` (como os Assistants de usuário); `available` é rota literal, antes de `{alias}`. O corpo
segue a forma do `mcp.yaml` (007), para que o operador e o usuário escrevam o mesmo formato: `alias`, `transport`,
`endpoint`, `description`, `auth: {type, credential}`, `enabled`, `user_access`, `policy: {allowed_tools, write_tools,
timeout_ms, max_response_bytes}`. Campo desconhecido → 400. As regras de escopo (sempre `https`, sem autenticação, sem
`user_access`, `~` obrigatório) são da 007, que recusa com `McpRejected`.

**Rationale**: nota da 007; FR-006; o molde das rotas de Assistants de usuário (R19).

**Alternatives considered**: corpo plano com os campos do `McpServerDraft` (dois formatos para o mesmo dado, arquivo e
API).

## R27 — Rotas de MCP globais, só para o grupo de administração

**Decision**: `GET/POST /private/v1/mcp`, `GET/PUT/DELETE /private/v1/mcp/{alias}` e `GET /private/v1/mcp/{alias}/health`
sobre `globals`, `create_global`, `get_global`, `update_global`, `delete_global` e `check(alias)`. Antes de tudo,
`AdminGate.is_admin(principal)`; quem não administra recebe o mesmo 404 de recurso inexistente (como `/packs` e
`/admin/keys`, R20). A saúde por servidor global é de administração; a agregada (`/private/v1/health`) já traz um item
não crítico por servidor global para qualquer chave (011).

**Rationale**: nota da 007; FR-007; a regra de quem administra é da 003 (R20).

**Alternatives considered**: saúde por servidor para qualquer chave (expõe as tools anunciadas por um servidor do
operador a quem não administra).

## R28 — Erros de MCP

**Decision**: `McpNotFound` → 404 (herda de `NotFound`, mensagem fixa), `McpRejected` → 400 com `param` = campo (herda
de `RequestRejected`), `McpConflict` → 409 com `param: "alias"` (herda de `Conflict`; o caso genérico continua com
`param: "name"`), `UnknownServer` → 404. Entrada do arquivo do operador alterada pela API → 409 (somente leitura, 007).

**Rationale**: a tabela de erros da 008 já traduz a hierarquia da 003 (R12); só o `param` do conflito muda de nome.

**Alternatives considered**: tradução própria para cada erro da 007 (duplicaria a tabela).

## R29 — O registry chega a `create_app` como seam opcional

**Decision**: `create_app(..., mcp: McpRegistry | None = None)`; sem registry, as rotas de MCP não são montadas (404).
A 011 passa `parts["mcp"]` (toque declarado). As rotas importam só `ai_core.mcp.api`.

**Rationale**: o padrão dos seams da 003 na Fase 2 (R23); a API não instancia nada (princípio XIII).

**Alternatives considered**: registry obrigatório (quebraria as suítes da 008 que não precisam de MCP).

## R30 — Desfecho pela gravidade (FR-022, ADR-018)

**Decision**: `finish_reason(event)` = `"error"` se algum registro tem `severity == "error"`, senão `"stop"`; `failed`
(sem streaming → 502) segue o mesmo critério. A constante `VALIDATOR_ISSUE` da 008 sai: a API não conhece mais nenhum
`kind` da 005.

**Rationale**: ADR-018; FR-022. Antes, uma execução `agentic` truncada (só `notice`) saía com `finish_reason: "error"` e
502.

**Alternatives considered**: ver ADR-018.

## R31 — `x-should-retry: false` nas falhas de execução

**Decision**: a resposta 502 de falha de execução sem streaming leva `x-should-retry: false`. Em streaming o status já é
200 (nenhum cliente repete), e erros **anteriores** à execução — 4xx, 503 de armazenamento — não levam o cabeçalho: ali
nada rodou, e repetir é seguro.

**Rationale** (clarificação de 2026-10-02): o SDK oficial da OpenAI repete 5xx automaticamente e obedece a esse
cabeçalho; cada repetição rodaria o loop `agentic` de novo, inclusive tools de escrita (auditadas, mas executadas de
novo).

**Alternatives considered**: ver a clarificação.

## R32 — Testes

**Decision**: `tests/http/contract/test_mcp_routes.py` (usuário: ciclo criar → ler → atualizar → listar → saúde →
remover, isolamento entre donos, `available`, recusas da 007 com o campo; globais: 404 para não administrador, ciclo
para administrador, entrada do arquivo → 409, saúde), com o `McpService` da 007 em memória (transporte programado) e a
003 real; US4 cen. 1: MCP próprio criado pela API + Assistant de usuário que o usa → aparece em `/v1/models` do dono;
desfecho: execução só com `notice` → 200 e `finish_reason: "stop"` (com e sem streaming), com `error` → 502 e
`x-should-retry: false`; US6 cen. 1: execução `agentic` com tool emite chunk de progresso com `stage: "execute_tool"` e o
nome. Marcas `us4`, `us5`, `us6`.

**Rationale**: o padrão da R24 (a 003 real, nada de dublê do que se integra).

**Alternatives considered**: dublê do registry (não pegaria divergência de tipo nem de exceção da 007).

---

# Fase 7 (2026-10-13): progresso, fila e Open WebUI (US6, US8)

Insumos: as quatro clarificações de 2026-10-13; o `design.md` ("Admissão e fila", pré-aprovado; "Compatibilidade OpenAI
e Open WebUI"); os contratos da 005 que publicam os estágios de progresso (`execution-engine.md`, `agentic-flow.md`,
`rag-first-flow.md`); e o código do Open WebUI v0.12.0 (`utils/headers.py`, `routers/openai.py`, `utils/middleware.py`,
`utils/misc.py`, `utils/oauth.py`, `config.py`, `env.py`). Nenhum ADR novo.

## R33 — Escopo da passada

**Decision**: da 008, a US6 (cenários 2–4: fila, recusa por sobrecarga e progresso como raciocínio; o cenário 1 — tool
nomeada no progresso — já vale desde a Fase 3, R32) e a US8 no lado da API (compatibilidade com o que o Open WebUI v0.12
envia, lista de modelos por token, pedido efêmero). Toque declarado na 011: a configuração da fila e
`create_app(admission=…)`. A instalação com Open WebUI e um provedor OIDC de desenvolvimento — onde a US8 é provada com a
interface de verdade — é uma passada de encaixe da 002 no `agentic-deploy`, depois desta, como na Fase 5.

**Rationale**: a API não depende da interface (FR-011, princípio XI); a 002 é dona da instalação.

**Alternatives considered**: subir o Open WebUI nos testes do core (traria uma interface e um provedor de identidade
para a suíte de uma API).

## R34 — Progresso como raciocínio (clarificação 2)

**Decision**: o chunk de progresso passa a levar `delta: {"reasoning_content": "<linha>\n"}` além do
`x_ai_core.progress` de antes, **só até o primeiro token**: depois do primeiro `TokenEvent`, o progresso (o de
`validate_answer`, por exemplo) vai só no campo extra. A linha é uma frase curta em português, de uma tabela pura em
`domain/progress_text.py`, indexada pelos estágios que os contratos da 005 publicam:

| Estágio (005) | Linha |
|---|---|
| `prepare_context` | `Preparando o contexto da pergunta…` |
| `load_capabilities` | `Carregando as ferramentas…` |
| `controller` | `Decidindo o próximo passo ({detail})…` |
| `execute_tool` | `Usando a ferramenta {detail}…` |
| `retrieve` | `Consultando os documentos…` |
| `rerank` | `Ordenando os trechos encontrados…` |
| `gate` | `Conferindo se os trechos cobrem a pergunta…` |
| `generate` | `Escrevendo a resposta…` |
| `validate_answer` | `Conferindo a resposta…` (na prática, só no extra: vem depois dos tokens) |
| outro | `Etapa {stage}…` |
| (fila, da própria 008) | `Aguardando uma vaga (posição {n} na fila)…` |

**Rationale**: o Open WebUI v0.12 junta os `reasoning_content` num bloco recolhível de "pensamento" e, ao reenviar o
histórico, descarta o raciocínio por padrão (`reasoning_format=None` em `convert_output_to_messages`) — a linha não volta
ao modelo. Raciocínio depois da resposta abriria um segundo bloco abaixo do texto; por isso para no primeiro token. Os
estágios são valores publicados nos contratos da 005 (não nomes internos lidos do grafo); estágio novo cai na linha
genérica e nada quebra.

**Alternatives considered**: campo `message` no `ProgressEvent` da 005 (mudança de seam e ADR, sem necessidade enquanto a
tabela cobre os estágios publicados); progresso em `delta.content` (suja a resposta).

## R35 — Admissão e fila (design.md, pré-aprovado; FR-016, FR-017)

**Decision**: `domain/admission.py` puro — `AdmissionLimits(max_executions, queue_size, max_wait)`,
`decide(running, queued, limits) -> "run" | "queue" | "reject"` e `retry_after(limits) -> int` (segundos, teto da espera
máxima, mínimo 1). Em `service.py`, `ExecutionSlots`: vagas e fila FIFO em memória (`asyncio`), a vaga ocupada do
início da execução até o evento final — ou até o iterador ser fechado (cliente que desconecta, cancelamento) —; quem
desconecta na fila sai dela sem ocupar vaga. A admissão roda **depois** da resolução do grant (404, 400, 424 e 429
primeiro) e **antes** de `engine.run`:

| Situação | Sem streaming | Com streaming |
|---|---|---|
| vaga livre | executa | executa |
| vagas cheias, fila livre | espera; esgotou a espera → 503 + `Retry-After` | abre o stream com o primeiro chunk e a linha de fila (no mesmo instante — bem antes dos 2 s); esgotou → chunk final com `finish_reason: "error"` e o registro `QueueTimeout` no extra, depois `[DONE]` |
| vagas e fila cheias | 503 + `Retry-After` | 503 + `Retry-After` (antes de abrir o stream) |

503 de sobrecarga: `type` `server_error`, `code` `overloaded`, sem `x-should-retry` (nada rodou; repetir respeitando o
`Retry-After` é seguro).

**Rationale**: é o desenho pré-aprovado (decisão pura em `domain/`, semáforo e fila no serviço, sem porta — não há I/O).
O stream já aberto não pode virar 503: segue a clarificação de 2026-09-21 (falha depois de o SSE abrir encerra o stream
normalmente); nenhuma chamada de modelo aconteceu, então a SC-006 continua valendo.

**Alternatives considered**: abrir o stream só depois de ganhar a vaga (o cliente na fila ficaria sem sinal — contraria
a FR-017); porta de admissão (seria uma porta para regra pura e estado em memória — princípio XII).

## R36 — Configuração e valores iniciais

**Decision**: a 011 lê `AI_CORE_MAX_EXECUTIONS` (1–64), `AI_CORE_QUEUE_SIZE` (0–1000; 0 = sem fila) e
`AI_CORE_QUEUE_WAIT_MS` (1–600 000; sem fila é `AI_CORE_QUEUE_SIZE=0`) e passa `AdmissionLimits` a `create_app(admission=…)`. Valores provisórios: **2**
execuções, fila de **8**, espera de **60 000 ms**; a implementação os mede no hardware alvo (Ollama local,
`qwen3:1.7b`: 1, 2 e 4 conversas simultâneas, latência até o primeiro token e total) e fixa os defaults com os números
no quickstart. Sem `admission` em `create_app`, não há limite (suítes e o harness, que não passa pela API).

*Medição de 2026-10-13*: por decisão do mantenedor, com OpenRouter (o suporte ao Ollama local fica para depois). Com o
modelo remoto, 1, 2 e 4 conversas simultâneas têm o mesmo primeiro texto (~2 s) e o mesmo total (~3 s) — a plataforma
não é o gargalo. Os defaults continuam 2 / 8 / 60 s, provisórios até a medição com o Ollama no hardware alvo (números no
quickstart).

**Rationale**: a spec manda medir os valores no hardware alvo; o nome em milissegundos segue `AI_CORE_TOOL_TIMEOUT_MS`.

**Alternatives considered**: fixar sem medir (princípio X).

## R37 — Pedido efêmero (clarificação 4, FR-023)

**Decision**: o adapter lê o cabeçalho `x-ai-core-store` e o domínio o valida (`domain/chat_request.py`,
`parse_store(value, conversation_id) -> bool`): ausente ou `true` → grava (FR-013); `false` (sem diferenciar
maiúsculas) e sem id de conversa → efêmero; `false` com id de conversa → 400 `store_conflict`; outro valor → 400
`invalid_header`; os dois com `param: "x-ai-core-store"`. `ChatRequest.store`; o serviço não cria nem grava conversa no
pedido efêmero, o primeiro chunk e a resposta sem streaming saem sem `conversation_id`, e não há `X-Conversation-Id`.
Vale nas duas superfícies, na compat e na requisição nativa.

**Rationale**: a clarificação; o Open WebUI envia cabeçalhos próprios por conexão (`headers` em `OPENAI_API_CONFIGS`,
aplicados em `get_headers_and_cookies`).

**Alternatives considered**: campo `store` no corpo (o Open WebUI só o mandaria configurado modelo a modelo).

## R38 — O que o Open WebUI v0.12 envia (compatibilidade)

**Decision**: nenhuma mudança na leitura do corpo, só a prova. O Open WebUI manda `model`, `messages` com conteúdo em
texto, `stream: true` e os parâmetros do modelo (`temperature`, `top_p`, `max_tokens`, `seed`, `stop`…), às vezes
`stream_options` — todos tolerados pela compat (ignorados ou dentro dos limites). `tools` só no modo de chamada de
função "nativo", que a instalação de referência não usa; se vier, 400 `widening_field` (princípio IV). Conteúdo
multimodal (lista de partes, ao anexar imagem) continua 400 em `messages`. Uma suíte de contrato reproduz o pedido do
Open WebUI (corpo e cabeçalhos tirados do código da v0.12, como fixture) e confere a resposta: streaming com
`reasoning_content` antes do texto, `[DONE]` e nada que o parser dele recuse.

**Rationale**: SC-001 (zero código de interface) e SC-004.

**Alternatives considered**: aceitar `tools` em silêncio (contraria o princípio IV e a borda de `chat_request.py`).

## R39 — Identidade do Open WebUI (clarificação 1)

**Decision**: nenhuma mudança na autenticação. A conexão `system_oauth` repassa o **access token** do provedor
(`get_headers_and_cookies` → `oauth_manager.get_oauth_token`, que renova o token a menos de 5 minutos de expirar); a 003
o verifica como hoje (`AI_CORE_OIDC_ISSUER`, `AI_CORE_OIDC_AUDIENCE`, `AI_CORE_OIDC_JWKS_URL` — a URL das chaves pode
ser a interna da rede, diferente do emissor que o navegador vê —, `AI_CORE_OIDC_SUBJECT_CLAIM`,
`AI_CORE_OIDC_GROUPS_CLAIM`). O provedor precisa emitir access token **JWT** com a audiência da plataforma e as claims
de subject e grupos. A lista de modelos do Open WebUI fica em cache **por usuário** (`openai_all_models_{user.id}`), e
com `BYPASS_MODEL_ACCESS_CONTROL=true` ele mostra o que o `/v1/models` devolve para aquele token, sem filtro próprio.

**Nota para a 002** (passada de encaixe): provedor de desenvolvimento **Keycloak** (access token JWT por padrão, mapper
de audiência e de grupos, realm importado com dois usuários de grupos diferentes); Authelia emite access token opaco por
padrão e o Dex não dá grupos a usuários estáticos.

**Rationale**: a clarificação; a autenticação real da 003 já é a de produção.

**Alternatives considered**: os da clarificação 1.

## R40 — Configuração do Open WebUI na instalação (nota para a 002)

**Decision**: o que a passada de encaixe da 002 configura, só por ambiente: `OPENAI_API_BASE_URLS` com o `/v1` da
plataforma e `OPENAI_API_CONFIGS` com `auth_type: system_oauth` e `headers: {"x-ai-core-store": "false"}`;
`ENABLE_OLLAMA_API=false`; `BYPASS_MODEL_ACCESS_CONTROL=true`; `ENABLE_TITLE_GENERATION`, `ENABLE_TAGS_GENERATION`,
`ENABLE_FOLLOW_UP_GENERATION`, `ENABLE_AUTOCOMPLETE_GENERATION`, `ENABLE_SEARCH_QUERY_GENERATION` e
`ENABLE_RETRIEVAL_QUERY_GENERATION` em `false` (clarificação 3); OIDC (`OPENID_PROVIDER_URL`, `OAUTH_CLIENT_ID`,
`OAUTH_CLIENT_SECRET`, `ENABLE_OAUTH_SIGNUP=true`, `ENABLE_LOGIN_FORM=false`); `ENABLE_PERSISTENT_CONFIG=false`, para que
o ambiente prevaleça sobre o que ficou gravado; imagem fixada na `v0.12.0`. *Acrescido depois da prova no navegador
(2026-10-13)*: `DEFAULT_MODEL_PARAMS={"function_calling": "legacy"}` e `DEFAULT_MODEL_METADATA={"capabilities":
{"builtin_tools": false}}` — no v0.12 a chamada de função nativa é o padrão, e toda conversa do navegador (com
`session_id`) levava as ferramentas embutidas do Open WebUI (38: memória, notas, hora, calendário, automações…) no campo
`tools`, recusado com 400 `widening_field`. Só o metadado não bastou: o cadastro de modelo que a tela cria (ao mexer no
modelo pelo painel) vem com todas as capacidades ligadas e vence o metadado padrão; os parâmetros desse cadastro ficam
vazios, então o modo legado — que nunca manda `tools` à conexão — continua valendo. A prova automatizada não pegou na
primeira versão porque montava o pedido direto pela API, sem o `session_id`; agora monta como a tela de chat. O teste da US8 com a interface conta as
execuções no trace: uma por mensagem.

**Rationale**: SC-001 (nenhum código de interface); as consultas de busca e de recuperação do próprio Open WebUI também
seriam execuções extras.

**Alternatives considered**: configurar pela tela de administração (não reproduzível).

## R41 — Testes

**Decision**: unitários puros — `tests/http/unit/test_progress_text.py` (a tabela, a linha genérica, o `{detail}`),
`test_admission_decision.py` (decisão e `Retry-After`), `test_chat_request.py` (o cabeçalho), `test_openai_chunks.py` (chunk de
progresso com `reasoning_content` e sem ele depois do primeiro token); contrato — `tests/http/contract/test_admission.py`
(motor programado que segura a execução: limite respeitado, fila FIFO, linha de fila no primeiro segundo, 503 com
`Retry-After` antes de qualquer chamada de modelo, espera esgotada nos dois modos, desconexão na fila libera o lugar —
SC-006 com 10 pedidos para 2 vagas e fila de 3), `test_ephemeral.py` (nada gravado, nenhum id, 400 nos conflitos,
duas superfícies), `test_open_webui.py` (o pedido do Open WebUI v0.12 como fixture; dois tokens de grupos diferentes →
duas listas em `/v1/models`); bootstrap — a 011 lê as três variáveis e, com `AI_CORE_MAX_EXECUTIONS=1` e
`AI_CORE_QUEUE_SIZE=0`, o segundo pedido simultâneo recebe 503 `overloaded`. Marcas `us6`, `us8`.

**Rationale**: o padrão da R24 (a 003 real, o motor real ou programado na porta de execução).

**Alternatives considered**: teste de carga com modelo real na suíte (fica no quickstart, para medir os valores).

## R42 — Timeline de status no Open WebUI (FR-005a; clarificação de 2026-10-13; ADR-028)

**Decision**: o cabeçalho `x-ai-core-progress` escolhe o modo de progresso em streaming, nas duas entradas
(`domain/chat_request.py`, `parse_progress`): `reasoning` (padrão, a R34) ou `status`. Outro valor é 400
`invalid_header`. No modo `status`:

- cada evento vira um chunk com `delta: {}` e a chave `event` = `{"type": "status", "data": {"description", "done"}}`;
- o início de etapa (`ProgressEvent`) vai com `done: false` e o mesmo `x_ai_core.progress` de sempre;
- o desfecho (`StepFinished`, 005 ADR-028) vai com `done: true`: uma linha por desfecho (no `retrieve`, uma por chamada),
  com o tempo da etapa medido pelo `Clock` da API entre o início e o fim;
- a fila vira status com `done: false`;
- no `FinalEvent`, uma linha por registro (`Aviso: <mensagem>` para `notice`; `Erro em <etapa>: <tipo>` para `error`) e a
  de conclusão (`Concluído em <tempo>[ · N citações]` ou `Terminou com erro em <tempo>`), antes do chunk final;
- nenhum `reasoning_content`, e a timeline segue depois do primeiro texto.

As linhas saem de `domain/timeline.py` (puro, tempo dado por quem chama): o início reaproveita a tabela da R34. O
desfecho segue esta tabela:

| Desfecho | Linha |
|---|---|
| `None` | `Contexto preparado` (`prepare_context`), `Resposta conferida` (`validate_answer`), `Etapa {stage} concluída` |
| `CatalogOutcome` | `7 ferramentas disponíveis; indisponível: crm` |
| `ControllerOutcome` | `Decisão (iteração 1, openai/gpt-4.1-nano): chamar scouting.search_docs(query="…")`, `responder`, `ação inválida (motivo)`, `o controller falhou; segue para a resposta` |
| `ToolCallsOutcome` | `scouting.search_docs(query="…", top_k=20) → ok: 20 trechos de 4 documentos: POR 2025, Estatuto 2024, … e mais 1`; status `erro`, `tempo esgotado`, `ferramenta inexistente`, `argumentos inválidos`; `, cortado` |
| `RerankOutcome` | `5 de 20 trechos: POR 2025 — Regra 12, p. 34; …` e o reranker que falhou |
| `GateOutcome` | `Coberto: melhor score 0,89, sem limiar → resposta com 5 trechos`; `Não coberto: … → busca com ferramentas` ou `→ resposta sem trechos` |
| `GenerationOutcome` | `Resposta de openrouter/openai/gpt-4.1-nano · 1.840 tokens de entrada, 312 de saída` |

Argumentos em JSON compacto, cortados em 120 caracteres com "…"; até 3 documentos ou fontes nomeados, depois "e mais
N"; números em pt-BR (`0,89`, `1.840`, `12 ms`, `1,2 s`, `1 min 3 s`). Texto de trecho, conteúdo de resultado e texto de
erro de tool nunca aparecem: o desfecho do motor não os traz, e um registro `error` aparece pelo tipo, porque a mensagem
dele pode trazer o texto de erro de uma tool ou de um servidor. A conexão da instalação manda o cabeçalho junto do
`x-ai-core-store: false`.

**Rationale**: o Open WebUI v0.12.0, no código da versão:

- `utils/middleware.py`, no laço do streaming: repassa a chave `event` de cada chunk ao emissor de eventos
  (`if 'event' in data and not request.state.direct`) e continua processando o `choices` do mesmo chunk;
- `socket/main.py`: grava cada `status` na mensagem (`add_message_status_to_chat_by_id_and_message_id`), e a timeline
  volta quando a conversa é reaberta;
- `StatusHistory.svelte`: mostra o último status, animado só com `done: false`, e o histórico expansível com um ponto
  por item;
- `StatusItem.svelte`: renderiza a `description` como texto puro, sem markdown.

Esse é o lugar do "o que está acontecendo": o bloco de raciocínio diz "Pensou por N segundos", não aceita nada depois do
primeiro texto (abriria um segundo bloco, R34) e não mostra a conferência nem a conclusão. O cabeçalho mantém o padrão
inalterado para qualquer outro cliente; a chave `event` é ignorada como campo extra pelos SDKs.

**Alternatives considered**:

- Raciocínio mais rico, em markdown dentro do bloco: pararia no primeiro texto e continuaria dizendo "pensou".
- Os dois canais juntos: a mesma informação duas vezes na tela.
- A chave `event` sempre, sem cabeçalho: dialeto do Open WebUI imposto a todo cliente.
- Status com `action` de busca na web (`web_search`, `sources_retrieved`): os rótulos são de busca na web, em inglês, e
  a lista leva links.

# Fase 9 (2026-10-14): superfície de administração (US9)

## R43 — Uma superfície nova, montada à parte

**Decision**: `adapters/admin.py` com um `APIRouter` em `ADMIN_PREFIX = "/admin/v1"`, incluído por `create_app` quando
os seams de administração são passados (`admin_seams: AdminSeams | None`, um `dataclass` com `assistants`
(`SystemAssistantAdmin`), `models` (o `check` do Model Router), `usage`, `prices`, `destinations`, `accounts`,
`login`, `keys`, `mcp`, `instance`). A autenticação usa `authenticated(request, surface="admin")` (003 R25) e o
`AdminGate`; não admin → `NotFound` → 404 pela tabela de erros existente. O router de MCP global da superfície privada é
reaproveitado com outro prefixo.

**Rationale**: ADR-031; a superfície privada não muda; sem os seams (perfil antigo ou teste), a superfície não existe.

**Alternatives considered**: rotas de administração na superfície privada com OIDC (ADR-031 rejeitou).

## R44 — Formatos puros em `domain/admin_*.py`

**Decision**: a tradução corpo ↔ value object fica em funções puras: `domain/admin_assistants.py`,
`domain/admin_usage.py`, `domain/admin_accounts.py`, `domain/admin_observability.py` — leem o JSON cru (como
`assistant_body.py` e `mcp_body.py` já fazem), recusam campos desconhecidos com `422 invalid_field` e montam as
respostas de [contracts/admin-api.md](contracts/admin-api.md). Valores monetários saem como string decimal.

**Rationale**: o padrão do módulo (corpo cru, regra pura, testável sem HTTP).

**Alternatives considered**: modelos Pydantic (o módulo não os usa; o OpenAPI sem corpo já é a decisão anterior).

## R45 — Versão no corpo, não em `If-Match`

**Decision**: escritas versionadas levam `version` no corpo (no `DELETE`, na query); conflito → `409
version_conflict` com `current_version`. As respostas de leitura trazem `version` por recurso.

**Rationale**: as sobreposições têm uma versão por seção, não por recurso inteiro; um campo explícito é mais simples
para a console que um `ETag` composto. Refina o "`ETag`/`If-Match`" do `design.md` e da FR-026 sem mudar a regra
(versão lida obrigatória, conflito sem sobrescrever).

**Alternatives considered**: `ETag` por seção em rotas separadas (mais chamadas na console).

## R46 — Erros novos na tabela

**Decision**: `domain/errors.py` ganha os mapeamentos: `Conflict` (003, 012, 009) → 409 `version_conflict` ou, com
causa, `installation_defined` / `master_key_missing` / `protected_group` / `google_not_configured`;
`RequestRejected(field)`, `InvalidField`, `InvalidPrice`, `InvalidQuery` → 422 `invalid_field` com `param`. Mensagem do
módulo dono, sem detalhe de infraestrutura.

**Rationale**: FR-026; a console mostra o motivo junto ao campo (013 FR-001).

**Alternatives considered**: —

## R47 — "Testar modelo" pelo Model Router

**Decision**: `POST /assistants/{name}/models/check` lê a visão do Assistant (003), recusa modelo fora de `allow`
(422) e chama `ModelRouting.check(ModelPolicy(roles={role: ref}, allow=view.allow))` (006); devolve disponibilidade,
detalhe e o tempo medido pelo `Clock`. A 008 passa a consumir o `api.py` da 006 só para isso (Module Boundary
atualizado).

**Rationale**: a verificação já existe no seam da 006; nenhuma regra nova.

**Alternatives considered**: a 003 testar o modelo (a 003 não conhece providers).

## R48 — Marca da instalação no `/me`

**Decision**: `create_app` recebe `instance: InstanceBranding(name, logo_url)` (011, de `AI_CORE_DISPLAY_NAME` e da
existência de `AI_CORE_LOGO_FILE`; o arquivo é servido pela 012 em `/oauth2/assets/logo`); `GET /admin/v1/me` o devolve.

**Rationale**: resolve o achado X1 do analyze da 012 — a console precisa do nome e do logotipo "lidos da API" (013
FR-020) — sem a 008 conhecer a 012.

**Alternatives considered**: rota pública de marca (só serve antes do login, e a console já passa pela página da 012).

## R49 — Testes

**Decision**: `tests/http/unit/test_admin_*.py` (formatos puros), `tests/http/contract/test_admin_api.py` (rota a rota
com os seams em memória: token da console e chave de admin, não admin 404, token do chat 401, varredura de segredo,
`no-store`, `409`/`422` com `param`). Marca `us9`.

**Rationale**: SC-008 e SC-009.

**Alternatives considered**: —

---

# Passada de 2026-10-20: identidade Axon ([ADR-037](../../docs/adr/ADR-037-a-plataforma-se-chama-axon.md), [ADR-038](../../docs/adr/ADR-038-marca-da-plataforma-e-marca-da-instalacao.md); US10)

Decisões pré-aprovadas pelos ADRs (nomes, corte seco, `instance.custom`) e a do mantenedor de 2026-10-20 (recusar o
cabeçalho antigo); o que segue é como elas chegam à API, sem re-pesquisa. Os R anteriores ficam como foram executados
(ADR-037, item 6); os nomes antigos neles se leem pela tabela do ADR-037.

## R50 — Cabeçalhos e chave de extensão

**Decision**: em `axon_ai/http/domain/chat_request.py`, `STORE_HEADER = "x-axon-store"` e `PROGRESS_HEADER =
"x-axon-progress"` (as docstrings das funções que os leem citam o nome novo); em `domain/errors.py` e
`domain/openai_chunks.py`, `EXTRA = "x_axon"`. Valores aceitos, códigos de erro e comportamento não mudam.

**Rationale** (ADR-037, item 2: `x-ai-core-*` → `x-axon-*`): na operação, o nome fica curto; a chave de extensão segue o
mesmo radical, para quem lê o chunk ou o erro reconhecer a plataforma.

**Alternatives considered**: `x-axon-ai-*` (o ADR rejeita o sufixo na operação); manter `x_ai_core` no corpo (dois
vocabulários na mesma resposta).

## R51 — Recusa dos cabeçalhos antigos

**Decision**: em `chat_request.py`, `LEGACY_HEADERS: Final = {"x-ai-core-store": STORE_HEADER, "x-ai-core-progress":
PROGRESS_HEADER}` e a função pura `reject_legacy_headers(names: Iterable[str]) -> None`, que, para o primeiro nome antigo
presente (na ordem do mapa, comparando sem caixa), levanta `ChatRequestInvalid(f"cabeçalho '{antigo}' foi renomeado: use
'{novo}'", field=antigo, code="invalid_header")`. O adapter de chat (`adapters/chat.py`) a chama nas duas entradas
(`/chat/completions` e `/chat`), depois da autenticação e antes do parse do corpo — um pedido não autenticado continua
401, e nenhum pedido com o nome antigo chega a executar. A presença basta: valor vazio ou com o novo junto também é
recusado.

**Rationale** (decisão do mantenedor de 2026-10-20; princípio VII; ADR-037, item 3): ignorar `x-ai-core-store: false`
gravaria a conversa de um cliente que pediu o contrário; aceitar o antigo seria janela de compatibilidade. O 400 explica e
não aceita — a mesma forma da recusa de `AI_CORE_*` no boot. O código `invalid_header` é o que o cliente já recebe por
valor errado no cabeçalho.

**Alternatives considered**: ignorar como desconhecido (rejeitado pelo mantenedor); aceitar os dois nomes; recusar só
quando o novo falta (deixa a dúvida de qual vale); um código novo `legacy_header` (o cliente já trata `invalid_header`, e
`param` diz qual).

## R52 — Título do OpenAPI

**Decision**: `FastAPI(title="Axon", …)` em `adapters/app.py`; o `version` do documento fica como está.

**Rationale** (ADR-037, item 2: "`title` do OpenAPI … → `axon`", em texto corrido "Axon", item 1).

**Alternatives considered**: `axon` minúsculo (o título é texto corrido; o wordmark é que é minúsculo).

## R53 — `instance.custom` e o nome padrão

**Decision**: `InstanceBranding` (`http/ports.py`) ganha `custom: bool = False`, e o `name` padrão passa a `"Axon"`;
`GET /admin/v1/me` publica `{"name", "logo_url", "custom"}`. A composição (011, `bootstrap/wiring.py::_instance`) calcula
`custom = settings.display_name != DEFAULT_DISPLAY_NAME or logo_url is not None` — sobre o logotipo que de fato é servido
(com a identidade ligada), para a console nunca receber `custom: true` sem nada próprio para mostrar.

**Rationale** (ADR-038, item 2): a console precisa saber se o lugar principal é da instalação. `AXON_DISPLAY_NAME=Axon`
sem logotipo dá `false`: o lugar principal já é o Axon, e a atribuição "com Axon" não aparece.

**Alternatives considered**: `custom` pela presença da variável no ambiente (o `Settings` não guarda se o valor veio do
padrão, e o resultado visível seria o mesmo lockup duas vezes); a console comparar o nome com "Axon" (regra de marca
espalhada no cliente).

## R54 — Consumidores e documentos vivos

**Decision**: a fixture `tests/http/open_webui_v0_12.py` (cabeçalhos da conexão) e os testes que citam os cabeçalhos ou a
chave de extensão, por troca de texto em lista fechada (`x-ai-core-store` → `x-axon-store`, `x-ai-core-progress` →
`x-axon-progress`, `x_ai_core` → `x_axon`), menos os testes novos da recusa; `test_admin_api.py` com `InstanceBranding(name=
"Axon", …, custom=True)` e o `me` com `custom`; `tests/bootstrap/integration/test_platform_identity_admin.py` com
`custom: false`. Documentos vivos: `spec.md` (já trocado no specify), `data-model.md`, `quickstart.md`, `contracts/`
(`chat-completions.md`, `conversations.md`, `errors.md`, `models.md`, `open-webui.md`, `sse-format.md`, `admin-api.md`) e
a linha da 008 em `specs/README.md`. A validação do `me` na console (`zod`, que descarta chave desconhecida) não muda
aqui; a 013 passa a ler `custom`. Ficam: `specs/002-core-pack-runtime/contracts/installation.md` e o deploy (passada da
instalação), o histórico.

**Rationale** (ADR-037, item 7).

**Alternatives considered**: nenhuma.

## R55 — Testes

**Decision**: em `tests/http/unit/test_chat_request.py`, `reject_legacy_headers` recusa cada nome antigo (com o novo na
mensagem e o antigo em `field`), sem caixa, e aceita a lista sem nenhum antigo. Em `tests/http/contract/test_ephemeral.py`
ou num arquivo novo `tests/http/contract/test_legacy_headers.py` (marca `us10`): `/v1/chat/completions` e `/v1/chat` com
`x-ai-core-store: false` e com `x-ai-core-progress: status` → 400 `invalid_header`, `param` igual ao antigo e a mensagem
citando o novo, sem chamada de modelo; com o novo e o antigo juntos → 400; com só o novo → como antes (cen. 1–3). O
título do OpenAPI em `/openapi.json` é "Axon" (cen. 5). O `me` com e sem marca própria (cen. 6), na suíte da superfície de
administração e na integração da 011. A chave `x_axon` nos chunks e no erro é coberta pelos testes de `openai_chunks` e
`errors` depois da troca (cen. 4).

**Rationale**: o cenário 3 é o único comportamento novo e precisa de verificador nas duas entradas.

**Alternatives considered**: testar a recusa só no domínio (não prova que o adapter a chama antes de executar).

---

# Passada de 2026-10-21: chaves rotacionáveis e `auth` na administração (US11; [ADR-040](../../docs/adr/ADR-040-rotacao-de-chaves-e-acesso-sobreponivel.md))

Decisões pré-aprovadas: ADR-031 (superfície e erros), ADR-032 (sobreposições), ADR-040 e a passada da 003 (research R38
a R44 dela, seams `ApiKeyAdmin.rotate` e `SystemAssistantAdmin.override_auth`). O que segue é como chegam à API.

## R56 — Rota de rotação e o 409 próprio

**Decision**: `POST /admin/v1/keys/{key_id}/rotate` → `200` com `key_json(info) | {"key": plaintext}` (a mesma forma da
emissão, sem `201`: nada é criado). Corpo opcional: vazio é aceito; objeto com qualquer campo → 422 nomeando-o (nenhum
campo é aceito). `NotFound` → 404 da tabela; `Conflict` da 003 **nesta rota** → 409 `key_revoked` com `param: "key_id"`,
traduzido pela função pura `key_revoked(message)` em `http/domain/errors.py` — a tabela geral continua mapeando
`Conflict` para `version_conflict`, que é o caso de toda outra rota. Só em `/admin/v1` (clarificação de 2026-10-21).

**Rationale**: FR-034; um `version_conflict` com `param: "version"` numa rota sem versão mandaria a console recarregar e
tentar de novo, sem efeito.

**Alternatives considered**: mudar o `Conflict` da 003 para um erro próprio (mudaria o seam por um detalhe de borda);
422 (o pedido está certo; é o estado que impede — research R39 da 003).

## R57 — `rotated_at` na representação da chave

**Decision**: `key_json` (`http/domain/private.py`, usado pelas duas superfícies) ganha `rotated_at` (ISO 8601 ou
`null`). As recusas novas da emissão chegam como `RequestRejected` e já saem como 422 `invalid_field` com `param` pela
tabela (FR-036): nada novo na borda.

**Rationale**: FR-035; campo aditivo, a forma da privada não muda (ADR-031, item 5).

**Alternatives considered**: `rotated_at` só na administração (duas representações da mesma chave).

## R58 — Sobreposição de `auth` na borda

**Decision**: `PUT /admin/v1/assistants/{name}/auth` com `{"schemes": [...], "allow": [...], "version": n|null}` →
`auth_body` puro em `http/domain/admin_assistants.py` (só esses campos; listas de textos, senão 422 com o campo; o
conteúdo — vazio, esquema desconhecido, seletor inválido, `*` em privado — é validado pela 003 e volta como 422 com
`param` `auth.schemes`/`auth.allow`/`auth`). `_SECTIONS` ganha `auth` (descarte por `DELETE …/overrides/auth`).
`auth_json(AuthOverride)` = `{"schemes": sorted, "allow": [...] na ordem}`; `view_json` traz `yaml.auth` e
`effective.auth`; `payload_json` aceita `AuthOverride` (sobreposições e histórico).

**Rationale**: FR-037; mesma forma das seções `models` e `mcp` (uma rota por seção, R46 da Fase 9).

**Alternatives considered**: `PUT /assistants/{name}/overrides/{section}` genérico (quebraria as rotas existentes).

## R59 — Nenhuma rota para o seletor; testes

**Decision**: a console monta o seletor de `allow` com `GET /keys` (subjects `svc:` das chaves ativas) e `GET /groups`
(FR-038). Testes: as três rotas novas na tabela da conformidade (`test_admin_api.py`: 404 para não admin, 401 para o
token do chat, `no-store`, varredura de segredo); casos da US11 (cen. 1–7) em `tests/http/contract/test_admin_keys_auth.py`
(marca `us11`, cuja descrição passa a citar também a 008 US11); unidade de `auth_body`/`auth_json`/`view_json` em
`tests/http/unit/test_admin_assistants.py` e de `key_revoked` em `test_errors.py`.

**Rationale**: SC-011; mesma régua da US9.

**Alternatives considered**: `GET /admin/v1/subjects` (rota nova sem regra própria; ADR-040, item 3).

## R60 — Imagens na borda (ADR-044, itens 5 a 10; FR-040 a FR-044)

**Decision**: `domain/images.py` (puro): `ImageLimits` (32 MiB, 5 MiB, 4), `decode`/`attachment_of` de data URI,
`read_messages` — a pergunta validada (`_question`, códigos `image_url_not_allowed`, `unsupported_image_type`,
`invalid_image`, `image_too_large`, `too_many_images`, `param` `messages[i].content[j].image_url.url`), o histórico com
marcas (`_history`, `_assistant`, que troca o markdown `![…](data:…)` e as partes `image_url` e guarda os bytes só da
última resposta) —, `with_markers`, `images_markdown`, `summary` e `VisionUnsupported`. `parse_messages` passa a aceitar
partes e converte as recusas em `ChatRequestInvalid`; `RequestTooLarge` (413) mora em `errors.py`; o `json_body` lê o
corpo com o teto de `app.state.image_limits` (o `create_app` recebe `image_limits`; a 011 os monta). O `ChatService`
recusa `vision_unsupported` logo depois do grant, retém as imagens e as emite num token antes do chunk final, e lê do
banco as imagens da última resposta (`_candidates`). `exchange` devolve as mensagens (texto com marcas e
`StoredAttachment`) e os bytes; a porta `ConversationStore` ganha `append(..., files=)` e `attachment(owner, id,
attachment_id)`, com memória e Postgres (`002_attachments.sql`: chave (conversa, seq, posição), FK para a mensagem com
`ON DELETE CASCADE`). A rota de bytes responde com o `mime`, `Cache-Control: private, no-store` e `nosniff`.
`models_json`/`models_body` e o corpo do Assistant de usuário leem e escrevem `{model, vision}`; a visão da 003 ganhou
`yaml_vision`/`effective_vision`. A timeline mostra o desfecho de `image_gate` e o `view_image` do controller (feito
na passada da 005, R51). A verificação do Open WebUI está na clarificação de 2026-10-22.

**Rationale** ([ADR-044](../../docs/adr/ADR-044-imagens-na-conversa.md)): validar só a pergunta é o que mantém viva a conversa em que o usuário trocou de Assistant; o
teto do corpo vem antes do JSON porque, com a conversa no cliente, o histórico inteiro com imagens volta a cada turno. O
markdown com data URI é o que o Open WebUI renderiza e devolve intacto (verificado), e serve a qualquer cliente que
renderize markdown. Os metadados na leitura e os bytes numa rota própria evitam carregar imagens a cada listagem.

**Alternatives considered**: teto só nas rotas de chat (as outras rotas com corpo ficariam sem limite nenhum);
guardar o data URI no texto da mensagem (o ADR proíbe; a leitura da conversa viraria megabytes); responder a imagem por
URL própria (alternativa rejeitada no ADR); recusar parte desconhecida também no histórico (um cliente que mandou
áudio uma vez travaria a conversa).
