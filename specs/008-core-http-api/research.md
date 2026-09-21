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
