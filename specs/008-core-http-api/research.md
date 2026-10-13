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
o ambiente prevaleça sobre o que ficou gravado; imagem fixada na `v0.12.0`. O teste da US8 com a interface conta as
execuções no trace: uma por mensagem.

**Rationale**: SC-001 (nenhum código de interface); as consultas de busca e de recuperação do próprio Open WebUI também
seriam execuções extras.

**Alternatives considered**: configurar pela tela de administração (não reproduzível).

## R41 — Testes

**Decision**: unitários puros — `tests/http/unit/test_progress_text.py` (a tabela, a linha genérica, o `{detail}`),
`test_admission.py` (decisão e `Retry-After`), `test_chat_request.py` (o cabeçalho), `test_openai_chunks.py` (chunk de
progresso com `reasoning_content` e sem ele depois do primeiro token); contrato — `tests/http/contract/test_admission.py`
(motor programado que segura a execução: limite respeitado, fila FIFO, linha de fila no primeiro segundo, 503 com
`Retry-After` antes de qualquer chamada de modelo, espera esgotada nos dois modos, desconexão na fila libera o lugar —
SC-006 com 10 pedidos para 2 vagas e fila de 3), `test_ephemeral.py` (nada gravado, nenhum id, 400 nos conflitos,
duas superfícies), `test_open_webui.py` (o pedido do Open WebUI v0.12 como fixture; dois tokens de grupos diferentes →
duas listas em `/v1/models`); bootstrap — a 011 lê as três variáveis e, com `AI_CORE_MAX_EXECUTIONS=1` e
`AI_CORE_QUEUE_SIZE=0`, o segundo pedido simultâneo recebe 503 `overloaded`. Marcas `us6`, `us8`.

**Rationale**: o padrão da R24 (a 003 real, o motor real ou programado na porta de execução).

**Alternatives considered**: teste de carga com modelo real na suíte (fica no quickstart, para medir os valores).
