# Research — 011 Bootstrap (Fase 1, US1–US3)

> Decisões pré-aprovadas vêm do [design.md](design.md) e dos ADRs da *Module Boundary*; não são re-pesquisadas.
> As quatro clarificações de 2026-09-21 estão na spec e aparecem aqui como R1, R4, R5 e R7.

## R1 — Etapas de boot declaradas, registradas por fase

**Decision**: cada etapa é um valor — nome, ação e política de falha (`critical`, que interrompe o boot, ou
degradável, que registra o motivo e segue) — e a sequência executa a lista registrada. A Fase 1 registra
configuração, adapters, packs, motor e API; registry MCP (007) e validação de Assistants (003) entram nas fases
deles.

**Rationale** (clarificação de 2026-09-21; FR-002, FR-003): a ordem é requisito, e uma lista de valores torna-a um
dado verificável — a suíte confere a sequência e as políticas com etapas de teste, sem subir a plataforma. Também é o
que faz "acrescentar etapa não muda a sequência" ser verdade em vez de intenção: o código que executa o boot não
menciona nenhum módulo.

**Alternatives considered**: função linear editada a cada fase (a política de falha ficaria espalhada por dentro das
chamadas, e cada fase reescreveria a função que o SC-002 depende de manter correta).

## R2 — Um único objeto montado, entregue pronto

**Decision**: o `wiring.py` constrói tudo e devolve uma `Platform` congelada — registro de packs, trace, roteador de
modelos, motor e aplicação HTTP. Ninguém mais instancia `service.py` ou `adapters/` de outro módulo.

**Rationale** (princípio XIII, FR-006; ADR-012 decisão 7): é a definição de composition root. Um objeto só, com tudo
já ligado, deixa o encerramento (FR-013) e a saúde (Fase 2) terem onde olhar, e o contrato de import-linter torna a
exclusividade verificável — nenhum outro módulo importa `ai_core.bootstrap`, e nenhum módulo importa `service.py` ou
`adapters/` de outro.

**Alternatives considered**: container de injeção (resolve por tipo, esconde a ordem de construção — e a ordem aqui é
requisito); fábricas espalhadas por módulo (é exatamente o que o princípio XIII proíbe).

## R3 — `packs.yaml` é da 002; a 011 só aponta o caminho

**Decision**: a configuração de packs usa o adapter de YAML que a 002 já publica; o bootstrap decide **qual arquivo**,
não **qual formato**.

**Rationale**: o formato é contrato da 002 (`contracts/packs-yaml.md`) e já tem suíte própria. Reimplementar a leitura
aqui duplicaria regra de validação e faria a mensagem de erro divergir entre o boot e o `packs check` do módulo.

**Alternatives considered**: um arquivo único de configuração para tudo (juntaria o formato de dois donos num arquivo
só e obrigaria a 002 a conhecer o resto).

## R4 — `assistants.yaml` nasce aqui e é herdado pela 003

**Decision**: um arquivo com nome do Assistant → `flow`, `packs`, `models` (por papel) e `allow`. O bootstrap o lê e
monta o resolvedor de grant que a 008 exige. Quando a 003 chegar, ela assume o arquivo e o bootstrap passa a consumir
o seam dela.

**Rationale** (clarificação de 2026-09-21; `design.md`: "AssistantStore de sistema (003): YAML"): a API precisa
resolver `<assistant>/<modelo>` desde a Fase 1, e alguém tem de montar o grant. O arquivo é a forma que o design já
previa para Assistants de sistema, então nasce uma vez e é herdado, em vez de ser inventado agora e de novo na Fase 2.
E mantém o princípio IV honesto: a fronteira de isolamento é configuração, não código.

**Alternatives considered**: um Assistant default por variáveis de ambiente (não exercita composição de packs nem
modelo por papel, e o formato teria de ser reinventado); Assistant fixo em código (a fronteira deixaria de ser
configurável, contra o princípio IV, e a SC-001 ficaria sem como ser demonstrada).

## R5 — `ai-core serve`, com servidor ASGI

**Decision**: um ponto de entrada `ai-core`, com o subcomando `serve`, que conduz o boot e serve a aplicação;
`uvicorn>=0.53,<1` entra como dependência. A raiz de linha de comando usa a biblioteca padrão — os subcomandos
contribuídos por módulo (US4) chegam na Fase 2.

**Rationale** (clarificação de 2026-09-21; `design.md`, "Linha de comando"): sem um ponto de entrada, o ator da US1 —
o operador que inicia o serviço — não existiria, e a conversa por HTTP só aconteceria dentro da suíte. Um servidor
ASGI é o que falta entre a aplicação (008) e uma porta aberta. Usar a biblioteca padrão para o parser evita escolher
agora um framework de linha de comando que a US4 pode querer diferente.

**Alternatives considered**: só função de biblioteca (deixaria a US1 sem ator); antecipar a US4 inteira (exigiria
`assistants validate`, e a 003 não existe).

## R6 — Perfil como conjunto de fábricas, validado antes do boot

**Decision**: um perfil oferece uma fábrica por porta secundária do core. A lista de portas exigidas é dado; validar o
perfil é conferir que nenhuma ficou sem fábrica, e isso acontece **antes** da primeira etapa.

**Rationale** (FR-004, FR-005, SC-006): é o que torna "porta sem adapter invalida o perfil" verificável sem subir
nada. Como a lista é dado, acrescentar uma porta numa fase futura é acrescentar uma linha, e o perfil que não a
atender falha com mensagem que a nomeia — em vez de quebrar no meio do boot com erro de atributo.

**Alternatives considered**: descobrir as portas por introspecção dos módulos (mágica frágil, e `Protocol` não é
enumerável); confiar no erro em tempo de construção (a falha apareceria tarde e sem nomear a porta).

## R7 — O perfil de teste é parte da distribuição

**Decision**: o perfil `test` vive no módulo, não na suíte, e monta a plataforma inteira — packs, motor, roteador de
modelos com provider simulado, trace em memória, relógio fixo e aplicação HTTP — com uma chamada.

**Rationale** (clarificação de 2026-09-21; FR-014, SC-003, US3): é o que permite à suíte de um pack externo testar o
pack contra a plataforma de verdade, sem copiar montagem. Dentro do repositório, é o que substitui as montagens
manuais que hoje existem em duplicata nas suítes de 005 e 008.

**Alternatives considered**: perfil de teste em `tests/` (packs externos ficariam sem como subir a plataforma, e a
duplicação permaneceria).

**O que o perfil NÃO faz** (apontado pelo `/speckit-analyze`): as suítes de 005 e 008 **não** passam a usar o perfil.
Fariam os testes desses módulos dependerem da composition root — a inversão que o próprio `design.md` da 008 evita ao
dizer que ela não importa a 011 —, e enfraqueceriam o isolamento que o SC-001 da 005 protege. A montagem manual lá é
deliberada: cada módulo se testa sozinho. O perfil serve a esta spec e às suítes de packs externos.

## R8 — Relógio e segredos únicos, por tipagem estrutural

**Decision**: um único adapter de relógio atende as portas de tempo de 005, 008 e 009; no perfil de teste, o relógio
fixo atende as três.

**Rationale** (FR-008, ADR-013): as portas são `Protocol` estruturais e têm a mesma forma, então uma implementação as
satisfaz sem que os módulos se conheçam. É o que garante que duas Turn Views da mesma execução tragam a mesma data —
e o que torna o conjunto dourado da 105 reproduzível. O adapter de segredos entra com os providers remotos (Fase 3).

**Alternatives considered**: um relógio por módulo (a data de referência poderia divergir na virada do dia, que é o
problema que o ADR-013 resolve).

## R9 — Escopo da fase

**Decision**: a Fase 1 entrega **US1** (ordem de boot com falha fechada e encerramento em ordem inversa), **US2** no
perfil em memória e **US3** (plataforma inteira em memória), mais o `serve` do R5. Ficam para depois: a linha de
comando com subcomandos de módulo (US4, Fase 2), a saúde agregada (US5, Fase 2) e o perfil persistente.

**Rationale**: `docs/roadmap.md` lista `011 · US1, US2 (perfil em memória), US3` na Fase 1 e `US2 (perfil
persistente), US4, US5` na Fase 2. A saúde agregada depende de a 008 declarar a porta `HealthProvider`, que é da fase
dela; os subcomandos dependem de a 002 e a 003 contribuírem os seus.

**Alternatives considered**: antecipar a saúde agregada (a 006 já oferece verificação de saúde, mas não há superfície
que a exponha nesta fase, e seria porta sem consumidor).

## R10 — O que a suíte prova

**Decision**: a suíte cobre a sequência e as políticas de falha com etapas de teste (sem plataforma), a validação de
perfil, o resolvedor de grant a partir do YAML, e uma conversa ponta a ponta pela aplicação montada no perfil `test`.
A 005 e a 008 passam a montar suas plataformas por esse perfil onde hoje montam à mão.

**Rationale** (SC-002, SC-003, SC-004): são os quatro critérios mensuráveis da fase. A conversa ponta a ponta no
perfil de teste é, ao mesmo tempo, o teste da US3 e a demonstração de que a montagem manual das outras suítes pode
morrer.

**Alternatives considered**: testar só pela plataforma montada (a ordem e as políticas de falha ficariam dependentes
de injetar defeito em módulos reais, o que é caro e frágil).

---

# Fase 2 (2026-09-30): US2 (perfil persistente), US4 (CLI), US5 (saúde agregada) e autenticação real

As duas clarificações de 2026-09-30 estão em R15 e R16. Herdados das passadas da 003 e da 008: autenticação real nos
perfis, migrações no boot (ADR-015), agendamento da expiração de conversas e o id de conversa do perfil de teste.

## R11 — Escopo da Fase 2

**Decision**: perfil `persistent` (US2), a raiz `ai-core` com os subcomandos dos módulos (US4), a saúde agregada (US5),
a autenticação real nos três perfis (FR-015), as migrações de `assistants` e `http` no boot e a expiração periódica das
conversas. Registry MCP, auditoria e checkpoint continuam na Fase 3.

**Rationale** (`docs/roadmap.md`: "011 · US2 (perfil persistente), US4, US5"; 003 e 008 R13: o que ficou para a
011): é a passada que liga, na plataforma em execução, o que as passadas anteriores entregaram como módulo.

**Alternatives considered**: deixar a autenticação real para depois (o `memory` continuaria aberto — rejeitado na
clarificação 1).

## R12 — Perfil como fábricas que veem o que já foi construído

**Decision**: a lista de portas exigidas passa a ser `clock`, `trace`, `providers`, `pack_source`, `request_ids`,
`conversation_ids`, `database`, `api_keys`, `oidc`, `user_assistants` e `conversations`. Cada fábrica recebe a
configuração **e as partes já construídas**, porque as de armazenamento do perfil `persistent` precisam do pool
(`database`). `memory` e `test` têm `database = None` e armazenamentos em memória; `persistent` tem o pool e os
adapters Postgres de 003 e 008. A validação de perfil incompleto continua a mesma (FR-004).

**Rationale** (R6 da Fase 1; FR-004, FR-005, SC-001): o perfil continua sendo dado — trocar de perfil não toca módulo
nenhum —, e a ordem das portas na lista é a ordem de construção.

**Alternatives considered**: um campo `storage: memory | postgres` decidido no `wiring.py` (a escolha de adapter sairia
do perfil e voltaria a ser código).

## R13 — Postgres no perfil persistente: conferido no boot, aberto no ciclo de vida da app

**Decision**: `AI_CORE_DATABASE_URL` é obrigatória no `persistent` e tratada como segredo — nunca aparece em log, em
relatório nem em mensagem de erro. Na etapa de adapters (crítica), um pool temporário, no laço do próprio boot, confere
a conexão e roda `migrate` de `assistants` e de `http` (ADR-015); falha para o boot nomeando a porta (`database`), o
adapter (Postgres) e, numa migração, o módulo e o arquivo. O pool de serviço é criado fechado e aberto no início do
ciclo de vida da app, no laço do servidor; fecha no fim dele. A linha de comando abre e fecha o seu no próprio laço.

**Rationale** (US2 cen. 2; FR-009; ADR-015): o pool do psycopg pertence ao laço de eventos em que é aberto, e o boot
roda antes do servidor, noutro laço. Conferir e migrar no boot mantém a falha fechada antes de a API existir (SC-002);
abrir o pool de serviço no laço do servidor é o que funciona.

*Na implementação*: a etapa `assistants` do boot também lê o banco (a validação percorre os Assistants de usuário), e a
linha de comando precisa de chaves, Assistants e saúde. Os três usam a mesma **sessão de armazenamento**
(`wiring.storage`): pool temporário no laço corrente e as portas de `STORAGE_PORTS` refeitas sobre ele pelas fábricas
do perfil. Sem banco, a sessão devolve as portas da plataforma. Um pool não reabre depois de fechado: a app de uma
plataforma persistente serve uma vez.

**Alternatives considered**: abrir o pool no boot e reaproveitá-lo no servidor (quebra ao trocar de laço); migrar só
por comando (o boot subiria sobre um schema desatualizado).

## R14 — Ciclo de vida da app: pool e tarefas periódicas

**Decision**: `create_app` (008) ganha um parâmetro opcional `lifespan`, aditivo. A composition root entrega um ciclo de
vida que, no início, abre o pool de serviço e agenda as tarefas periódicas declaradas — hoje, `ConversationService.expire`
a cada `AI_CORE_CONVERSATION_EXPIRY_INTERVAL` segundos (default 3600) — e, no fim, cancela as tarefas e fecha o pool. O
prazo de retenção vem de `AI_CORE_CONVERSATION_RETENTION_DAYS` (default 180) e chega à app como
`conversation_retention`.

**Rationale** (design.md: "tarefas periódicas declaradas pelos módulos são agendadas ao fim do boot e canceladas no
encerramento"; 008 FR-019): o ciclo de vida da app é o único lugar com o laço do servidor em execução.

**Alternatives considered**: expiração por comando externo (cron) — dependeria de algo fora da imagem para cumprir um
requisito da plataforma.

## R15 — Autenticação real em todos os perfis (clarificação 1, FR-015)

**Decision**:

| Perfil | Chaves de API | OIDC | Credencial pronta |
|---|---|---|---|
| `persistent` | Postgres (emitidas pela CLI) | JWKS do emissor, se `AI_CORE_OIDC_ISSUER` estiver definida; senão recusa | — |
| `memory` | memória, semeada com `AI_CORE_DEV_API_KEY` | idem | a chave de desenvolvimento: `user:dev`, no grupo de administração do `assistants.yaml` |
| `test` | memória, semeada | verificador estático | `TEST_API_KEY` e `TEST_OIDC_TOKEN`, de `user:test`, exportadas por `ai_core.bootstrap.profiles` |

`AI_CORE_DEV_API_KEY` precisa ter o formato de chave (`aic_<16 hex>_<segredo>`) e é recusada no `persistent`, onde
chaves saem da CLI. Sem chave de desenvolvimento nem OIDC, o `memory` sobe, mas recusa toda credencial, e o relatório
de boot diz isso. O autenticador anônimo sai dos perfis (continua só nas suítes da 008).

**Rationale** (clarificação 1; princípio VII): o perfil que mais parece produção deixa de aceitar qualquer requisição;
o de teste passa a exercitar a autenticação real. A chave de desenvolvimento é segredo de ambiente, como o
`design.md` prevê para o perfil `memory`.

**Alternatives considered**: ver a clarificação.

## R16 — Saúde agregada: itens críticos e não críticos (clarificação 2, FR-012)

**Decision**: `bootstrap/health.py` implementa a porta `HealthProvider` da 008 com os itens:

| Item | Crítico | Fonte |
|---|---|---|
| `database` | sim | `SELECT 1` no pool (só no `persistent`) |
| `boot:<etapa>` degradada | não | relatório de boot |
| `pack:<nome>` em erro | não | Pack Registry (002) |
| `assistant:<nome>` indisponível | não | `AssistantsService.validate()` (003) |
| `model:<provider/modelo>` | não | `ModelRouting.check` (006) sobre os modelos declarados pelos Assistants de sistema |

O resultado é `down` se algum crítico falha, `degraded` se só não críticos falham, `ok` se nenhum. Cada consulta tem
timeout de 3 s por item e o resultado fica em cache por 15 s. Na 008, `HealthItem` ganha `critical` e
`HealthReport.status`, e a rota responde 503 só em `down` — ajuste declarado nesta passada.

**Rationale** (clarificação 2; US5): o monitor não tira do ar uma instância que atende o resto; o cache e o timeout
impedem que a consulta frequente de saúde vire carga sobre o provider local ou pendure quando ele cai.

**Alternatives considered**: saúde sem cache (o monitor de 10 em 10 s faria o provider responder a cada vez); checar
todos os modelos da allowlist (padrões, não modelos — não há o que enumerar).

## R17 — Raiz `ai-core`: argparse, com os comandos dos módulos registrados como dado

**Decision**: a raiz continua na biblioteca padrão. Subcomandos: `serve`, `packs list|check` (002), `assistants
validate` (003), `keys create|list|revoke` (003) e `health` (011). Cada um chama as funções que o módulo dono oferece
no próprio `adapters/cli.py`; a 011 só monta o parser, a configuração e os adapters. Nenhum abre a porta HTTP:
`packs` roda só configuração, adapters e carga de packs (é o que distingue `packs.yaml` malformado, código 2);
`assistants validate` e `health` montam a plataforma; `keys` abre o armazenamento de chaves no próprio laço e avisa
quando o perfil não é persistente.

**Rationale** (FR-010, FR-011; 002 R15 e 003 R14: o framework de linha de comando é decisão da 011): os módulos já
entregaram as funções; acrescentar um módulo é acrescentar uma entrada à lista de registro.

**Alternatives considered**: click/typer (uma dependência para seis comandos); cada módulo registrando o próprio
parser (a 011 deixaria de saber o que a raiz oferece).

## R18 — Configuração nova

**Decision**: variáveis `AI_CORE_DATABASE_URL` (segredo), `AI_CORE_DEV_API_KEY` (segredo), `AI_CORE_OIDC_ISSUER`,
`AI_CORE_OIDC_AUDIENCE`, `AI_CORE_OIDC_JWKS_URL`, `AI_CORE_OIDC_SUBJECT_CLAIM` (`sub`), `AI_CORE_OIDC_GROUPS_CLAIM`
(`groups`), `AI_CORE_CONVERSATION_RETENTION_DAYS` (180), `AI_CORE_CONVERSATION_EXPIRY_INTERVAL` (3600). Validadas antes
de qualquer etapa, com erro que nomeia a variável e nunca o valor de um segredo; `AI_CORE_OIDC_ISSUER` sem
`AI_CORE_OIDC_AUDIENCE` é recusada.

**Rationale** (FR-001, FR-009): mesmas regras da configuração da Fase 1.

**Alternatives considered**: arquivo de configuração próprio (as variáveis já são o canal do template de instalação).

## R19 — Id de conversa no perfil de teste

**Decision**: a porta `conversation_ids` ganha fábrica própria em cada perfil — aleatória em `memory` e `persistent`,
sequencial com prefixo `t` no `test` (`conv_t-1`).

**Rationale**: o perfil de teste reaproveitava a fábrica de requisição (`conv_req-1`), o que confundia os dois ids.

**Alternatives considered**: nenhuma relevante.

## R20 — Testes

**Decision**: `unit/` — configuração (variáveis novas, segredo nunca na mensagem), perfis (portas exigidas, fábricas
do `persistent` construídas sem conectar), saúde (crítico × não crítico, cache, timeout) com checagens falsas;
`contract/` — cada subcomando por `main(argv)` com servidor e saída injetados, códigos de saída e mensagens;
`integration/` — perfil `test` com as credenciais exportadas (401 sem credencial) e perfil `persistent` contra
Postgres real (`AI_CORE_TEST_POSTGRES_DSN`): o boot migra, uma chave emitida pela CLI autentica pela API, uma conversa
sobrevive a uma plataforma nova sobre o mesmo banco, e o boot falha sem expor a URL quando o banco não responde.

**Rationale** (SC-001, SC-002, SC-003, SC-005): é o que prova que trocar de perfil não muda módulo e que a falha
fechada vale para o armazenamento.

**Alternatives considered**: nenhuma relevante.

---

# Fase 3 (2026-10-02): encaixe da 007, da 004 e do `agentic`

Insumos: as três clarificações de 2026-10-02; as notas para a 011 nos planos da
[007](../007-core-mcp-integration/plan.md) ("Seam Notes", linha da 011) e da [004](../004-core-capability-gateway/plan.md)
(idem); o `design.md` (tabela de portas por perfil: `McpServerStore`, `McpTransport`, `AuditLog`); ADR-012, ADR-013,
ADR-015, [ADR-017](../../docs/adr/ADR-017-trace-sink-cresce-por-eventos-aditivos.md) e
[ADR-018](../../docs/adr/ADR-018-seam-execution-engine-fase-3.md). Módulos ligados, já implementados: 007 (`McpService`,
adapters de armazenamento, transporte, segredos, cache e arquivo), 004 (`CapabilityService`, auditoria em memória e
Postgres, `audit_command`), 005 (`ExecutionService(capabilities=…)`).

## R21 — Escopo da passada

**Decision**: ligar nos três perfis o registry MCP (007) e o gateway de tools (004); passar o gateway ao motor (o
`agentic` passa a existir em `flows()`); a etapa `mcp_registry` entre `packs` e `engine`; o serviço da 007 no lugar do
`McpDirectory` vazio da 003; `ai-core audit`; um item de saúde por servidor MCP global; o SDK de MCP com log em `INFO`;
trocas de porta para as suítes; e o teste ponta a ponta `agentic` + MCP pelo perfil `test`. **Fora**: rotas HTTP de
MCP, saúde por servidor na API e `finish_reason` por gravidade (passada da 008); acusar Assistant `agentic` sem
`controller` (passada da 003); checkpoint (adiado pela 005).

**Rationale**: é a linha da 011 que as notas da 007 e da 004 deixaram, mais as clarificações de 2026-10-02.

**Alternatives considered**: ligar também as rotas da 008 (é outra spec).

## R22 — Portas novas no perfil

**Decision**: `REQUIRED_PORTS` ganha, depois das de armazenamento já existentes: `mcp_store`, `mcp_dns`,
`mcp_transports`, `mcp_secrets`, `mcp_cache` e `audit`. `STORAGE_PORTS` ganha `mcp_store` e `audit` (reconstruídas sobre o pool
temporário nas sessões, R13).

| Porta | `memory` | `persistent` | `test` |
|---|---|---|---|
| `mcp_store` (007) | `InMemoryServerStore` | `PostgresServerStore(pool)` | `InMemoryServerStore` |
| `mcp_dns` (007) | `SystemDnsResolver` | `SystemDnsResolver` | `FixedDnsResolver` vazio |
| `mcp_transports` (007) | `http`/`sse`: `HttpMcpTransport` com a porta `mcp_dns` | `http`/`sse`: idem; `stdio`: `StdioMcpTransport` | os três: um `ScriptedMcpTransport` sem servidores |
| `mcp_secrets` (007) | `EnvSecretResolver` (`AI_CORE_MCP_SECRET_<REF>`) | idem | `InMemorySecretResolver` vazio |
| `mcp_cache` (007) | `InMemoryDiscoveryCache(clock)` | idem | idem |
| `audit` (004) | `InMemoryAuditLog` | `PostgresAuditLog(pool)` | `InMemoryAuditLog` |

O transporte HTTP recebe os hosts internos e a allowlist de hosts do arquivo do operador — por isso o arquivo é lido
na etapa de configuração (R23), antes de os adapters existirem. Os provedores do perfil `test` passam a responder
`{"action": "answer"}` em chamada sem streaming — é o controller simulado (clarificação 2).

**Rationale** (`design.md`, tabela por perfil; FR-004): toda porta declarada por um módulo tem adapter em cada perfil,
e a escolha é dado. `stdio` só no `persistent`, como o `design.md` determina: no `memory`, uma entrada `stdio` do
arquivo fica indisponível com o motivo (transporte não oferecido pelo perfil), em vez de executar comando local num
perfil de desenvolvimento. O cache é sempre em memória (processo único, como os contadores de taxa da 003).

A porta `DnsResolver` da 007 entra no perfil como `mcp_dns` (FR-004: toda porta declarada tem adapter no perfil); o
transporte HTTP a recebe das partes. A porta `McpConfigSource` segue o padrão do `assistants.yaml` (R4): a escolha entre
o arquivo e a configuração vazia é da etapa `configuration`, pela variável, não do perfil.

**Alternatives considered**: montar cache, DNS e segredos direto na etapa, sem porta (o FR-004 pede que toda porta tenha
adapter declarado no perfil); um transporte por servidor (o transporte é por tipo — `http`, `sse`, `stdio` —, e a
política de rede é aplicada a cada conexão dentro dele, 007).

## R23 — O arquivo do operador na configuração; a etapa `mcp_registry` monta o serviço

**Decision**: a etapa `configuration` lê também o `mcp.yaml` (`AI_CORE_MCP_FILE`, pelo `YamlMcpConfigSource` da 007;
ausente = nenhum servidor do operador). Arquivo ilegível ou malformado (`McpConfigError`) para o boot ali, nomeando o
arquivo. A etapa nova `mcp_registry` — **crítica**, entre `packs` e `engine` — monta o `McpService` com as portas do
perfil, o arquivo já lido, o relógio único e o TTL de descoberta; entrada do arquivo com problema (`ConfigEntry.problem`)
**degrada** a etapa, nomeando o alias e o motivo, e o resto sobe. A etapa não sai para a rede (clarificação 1).

A etapa também confere, sem rede e sem ler valor, que toda referência de credencial dos servidores globais resolve —
`credential_ref` dos globais (`globals()`, na sessão de armazenamento) e os `secrets` das entradas `stdio` do arquivo:
referência ausente degrada a etapa com `mcp '<alias>': credencial '<ref>' ausente (AI_CORE_MCP_SECRET_<REF>)`. É o
caso de borda "referência de segredo ausente" da spec: a 007 só resolve o valor por operação (007 FR-004), então sem
esta conferência o operador só descobriria na primeira chamada (SC-005). O relatório nomeia a referência, nunca o
valor (FR-009).

**Rationale**: FR-001 ("validada antes de qualquer outra etapa") e SC-002; é o mesmo tratamento do `assistants.yaml`
(R4). A nota da 007 ("erro de arquivo é crítico") vale: erro de arquivo para o boot, só que uma etapa antes. Entrada
com problema não para o boot (FR-003, SC-004).

**Alternatives considered**: ler o arquivo dentro de `mcp_registry` (o transporte HTTP precisa dos hosts antes, na
etapa de adapters); sondar os servidores no boot (clarificação 1).

## R24 — Gateway de tools no motor; o `agentic` em todos os perfis

**Decision**: a etapa `engine` monta o `CapabilityService` — `pack_tools` = o `PackRuntime` (seam Pack Toolset da 002),
`mcp` = o `McpService`, `audit` = a porta, o Trace Sink, o relógio e `GatewayLimits(timeout_ms, max_response_bytes)` da
configuração — e o passa ao `ExecutionService(capabilities=…)`. Com isso `flows()` oferece `chat` e `agentic` nos três
perfis, e `assistants validate` aceita Assistants `agentic`.

**Rationale**: FR-007 (o motor recebe os seams prontos); ADR-018 (sem `capabilities`, não há `agentic`); notas da 004.

**Alternatives considered**: `agentic` só no `persistent` (nada no flow depende de armazenamento persistente).

## R25 — O `McpDirectory` da 003 passa a ser o `McpService`

**Decision**: `assistants_service(parts, users=…, mcp=…)` recebe o diretório de MCP como os outros armazenamentos: no
servidor, o `McpService` da plataforma; no boot e na linha de comando, um `McpService` montado sobre o `mcp_store` da
sessão de armazenamento (R13), pela mesma fábrica (`mcp_service(parts, store=…)`). O `EmptyMcpDirectory` sai da
montagem.

**Rationale**: a 007 cumpre a porta `McpDirectory` estruturalmente (`aliases(owner=…)`); no `persistent`, o
armazenamento só pode ser usado no laço em que o pool abriu (R13).

**Alternatives considered**: um `McpService` só, compartilhado entre laços (quebra no `persistent`, pelo mesmo motivo do
R13).

## R26 — Migrações `mcp` e `capabilities` na etapa de adapters

**Decision**: `_migrate` roda, na sessão de armazenamento do boot, as migrações de `assistants`, `http`, `mcp` e
`capabilities`, nessa ordem — cada uma sob a trava consultiva do seu schema (ADR-015).

**Rationale**: ADR-015 e as notas da 007 e da 004.

**Alternatives considered**: migrar na primeira escrita (erro de banco apareceria depois de a API existir).

## R27 — Configuração nova

**Decision**:

| Variável | Default | Regra |
|---|---|---|
| `AI_CORE_MCP_FILE` | — | caminho do arquivo do operador (formato da 007); ausente = nenhum servidor do operador |
| `AI_CORE_MCP_DISCOVERY_TTL` | `300` | segundos, `> 0` — validade do catálogo descoberto de um servidor (007) |
| `AI_CORE_TOOL_TIMEOUT_MS` | `30000` | inteiro entre 1 000 e 300 000 — prazo do gateway (004) |
| `AI_CORE_TOOL_MAX_RESPONSE_BYTES` | `16384` | inteiro entre 1 024 e 1 048 576 — corte do gateway (004) |

Valor fora da regra é recusado na construção de `Settings`, nomeando a variável. Credenciais de MCP **não** passam por
`Settings`: o `EnvSecretResolver` da 007 lê `AI_CORE_MCP_SECRET_<REF>` só ao montar a operação, e o valor nunca sai em
log, relatório ou erro (FR-009, 007 FR-004).

**Rationale**: notas da 007 e da 004; as faixas são as de `GatewayLimits`, repetidas aqui para que o erro saia na
configuração (FR-001), não na montagem do serviço.

**Alternatives considered**: deixar o `GatewayLimits` recusar (o erro nomearia o campo do value object, não a variável).

## R28 — Saúde: um item não crítico por servidor MCP global

**Decision** (clarificação 1): `PlatformHealth` recebe o registry da 007 e acrescenta, a cada consulta não coberta pelo
cache, um item `mcp:<alias>` por servidor de `globals()` — `ok` e `detail` do `ServerHealth` de `check(alias)`,
inclusive as tools que a allowlist pede e o servidor não anuncia —, todos em paralelo, cada um sob o prazo de 3 s. Itens
**não críticos**: servidor fora do ar deixa a saúde `degraded`. Falha ao listar os globais vira um item `mcp` não
crítico com o motivo (banco fora do ar já aparece como `database`, crítico). Servidores de usuário não entram.

**Rationale**: US5 cen. 4, FR-012, SC-005; o cache de 15 s e o prazo de 3 s já existentes limitam a ida à rede.

**Alternatives considered**: ver a clarificação 1.

## R29 — `ai-core audit`

**Decision**: `Command(path=("audit",))`, com os argumentos do contrato da 004 (`--principal`, `--assistant`, `--tool`,
`--since`, `--until`, `--limit`, `--results`). Sobe até `engine` (configuração, adapters, packs, registry e motor — sem
rede; o gateway precisa do Trace Sink, que nasce na etapa `engine`) e, na sessão de armazenamento, monta o `CapabilityService` pela mesma fábrica da etapa `engine`, com a
auditoria e o registry da sessão, e chama `audit_command` da 004. Códigos: os do contrato da 004 (0; 2 para filtro
inválido); boot que falha, 1.

**Rationale**: a consulta é seam da 004 (`AuditQuery`); montá-la pela mesma fábrica do servidor é o que o FR-010
pede ("a mesma configuração e os mesmos adapters do servidor"). No `memory` e no `test`, a auditoria é do próprio
processo — a listagem sai vazia, como `keys list` no `memory`.

**Alternatives considered**: ler o `AuditLog` direto (contornaria o seam da 004 e repetiria a regra de filtro).

## R30 — O SDK de MCP nunca registra em `DEBUG`

**Decision**: a etapa `mcp_registry` fixa o nível do logger `mcp` (raiz dos loggers do SDK) em `INFO`. Os loggers filhos
do SDK não têm nível próprio, então herdam `INFO` mesmo com a raiz do processo em `DEBUG`.

**Rationale**: em `DEBUG`, o SDK registra mensagens JSON-RPC inteiras — argumentos de tool e conteúdo de resposta, que
podem trazer dado de usuário ou credencial de terceiro (princípio VI, FR-009). A composition root é quem configura o
processo; a 007 não configura logging.

**Alternatives considered**: um filtro de redação no log (frágil diante de formatos que mudam com o SDK); confiar no
nível padrão (um operador que liga `DEBUG` para depurar outra coisa vazaria conteúdo).

## R31 — Trocas de porta na montagem

**Decision** (clarificação 2): `platform(…, overrides: Mapping[str, Any] | None = None)`. Na etapa de adapters, cada
porta com troca usa o valor dado em vez da fábrica do perfil; as fábricas seguintes já o enxergam. Nome fora de
`REQUIRED_PORTS`, ou porta de armazenamento (`database` e `STORAGE_PORTS`), é recusado com `ConfigurationError`
nomeando a porta — as sessões de armazenamento reconstroem essas portas pelas fábricas, e uma troca nelas seria
ignorada em silêncio no `persistent`. A troca existe só na chamada Python; nenhuma variável de ambiente a expõe.

**Rationale**: FR-014 — a suíte programa o controller (porta `providers`) e os servidores MCP (porta `mcp_transports`)
sem montar o resto. O perfil continua dado; a troca é por porta, no mesmo ponto em que o perfil é aplicado.

**Alternatives considered**: fakes fixos no perfil `test` (clarificação 2, opção B); perfil `test` com servidores
programados por arquivo (programar resultado de tool não é configuração).

## R32 — Testes

**Decision**:

- unidade: `Settings` com as variáveis novas (defaults e recusas); perfis com as portas novas (inclusive a recusa de
  troca de porta de armazenamento e de nome desconhecido); `PlatformHealth` com o registry falso (item por global,
  não crítico, prazo, falha de listagem);
- contrato: a ordem das etapas com `mcp_registry`; arquivo malformado para na configuração; entrada com problema
  degrada `mcp_registry`; `agentic` em `flows()` nos três perfis; o SDK em `INFO` com a raiz em `DEBUG`;
- CLI: `ai-core audit` registrado, filtro inválido → 2, listagem vazia no `test`;
- integração: o `persistent` contra Postgres real (migrações `mcp` e `capabilities`; um servidor criado pelo registry
  sobrevive à reabertura; `audit` lista o que uma tool de escrita gravou) com `AI_CORE_TEST_POSTGRES_DSN`; e a
  conversa `agentic` + MCP ponta a ponta pela API no perfil `test`, com controller e servidor MCP trocados na montagem
  (US3 cen. 3) — sem rede.
- marca `us3` na ponta a ponta, `us2` nos perfis, `us5` na saúde, `us4` na CLI.

**Rationale**: o que as clarificações e a US3 cen. 3 pedem, no padrão das suítes da Fase 2 (R20).

**Alternatives considered**: testar a ponta a ponta com o servidor de demonstração real da 007 por HTTP (exige rede de
loopback; a clarificação 2 pede sem rede).

## R33 — Pendências para outros planos

| Spec | O quê |
|---|---|
| 008 | rotas de MCP em `/v1/mcp` e `/private/v1/mcp` (o `McpService` da plataforma já existe em `Platform.mcp`); saúde por servidor na API; `finish_reason` por `severity` (ADR-018) |
| 003 | acusar Assistant `agentic` sem papel `controller`; exemplo de `allowed_tools` com namespace; regra de colisão alias × pack |
| 006 | US4: `strict` e recusa de provider sem saída estruturada no `controller` |

## Passada de encaixe da Fase 5 (005 US3, US4) — 2026-10-09

### R34 — `AI_CORE_RAG_*` e o `rag_first` em `flows()`

**Decision**: `Settings` ganha `rag_candidates`, `rag_passages` e `rag_min_score` (as regras de `RagSettings` da 005,
repetidas para que o erro nomeie a variável, como as faixas do gateway no R27); a etapa `engine` passa
`RagSettings` ao `ExecutionService`. Com o gateway, o motor oferece `rag_first` nos três perfis.

**Rationale**: a clarificação 1 de 2026-10-09 da 005 (configuração do operador, sem limiar por default).

**Alternatives considered**: no grant (por Assistant) — quando houver o segundo Assistant `rag_first`.

### R35 — Catálogo de coleções a partir do Pack Registry

**Decision**: a porta `CollectionCatalog` da 003 passa a ser atendida por `PackCollectionCatalog` (em
`ai_core/assistants/adapters/catalogs.py`): existem as coleções que os retrievers dos packs **habilitados** declaram
(`NamedRetriever.collections`, contrato 001, visto pelo Pack Registry). Pack desligado ou em erro não oferece coleção.

**Rationale**: o R11 da 003 previa que "o índice (Fase 5)" atenderia a porta por troca de adapter. O índice, porém, mora
no pack que o declara (102, no `ai-scouting`); o core só conhece as coleções pelos retrievers. Sem a troca, todo
Assistant que declara `collections` ficava indisponível (424), e o catálogo da 004 já exige todas as coleções do
retriever no grant — as duas regras se fecham. Nenhum seam muda: é a troca de adapter que o R11 anunciou.

**Alternatives considered**: coleções declaradas pelo operador num arquivo (mais uma fonte para desalinhar do pack);
aceitar qualquer nome (referência fantasma no grant, contra o R11).

# Fase 9 (2026-10-14): identidade, administração, sobreposições e destinos do trace

### R36 — Variáveis novas e validação na etapa `configuration`

**Decision**: `Settings` ganha (contrato em [contracts/configuration.md](contracts/configuration.md), Fase 9):
`identity_enabled` (`AI_CORE_IDENTITY_ENABLED`, padrão falso), `public_url` (`AI_CORE_PUBLIC_URL`, obrigatório com a
identidade ligada), `identity_clients_file`, `master_key` (`AI_CORE_MASTER_KEY`, 32 bytes em base64; nunca em log nem
relatório), `display_name` (`AI_CORE_DISPLAY_NAME`, padrão "Agentic"), `logo_file`, `trusted_proxies`,
`cookie_secure`, `usage_timezone` (padrão `UTC`), `usage_retention_days` (400). Validações que **param o boot** com
erro que nomeia a variável: identidade ligada com `AI_CORE_OIDC_ISSUER` (emissor único, ADR-030); identidade ligada sem
`AI_CORE_PUBLIC_URL` ou sem o arquivo de clientes; `persistent` com identidade ligada sem chave mestra (ADR-033); chave
mestra malformada; grupo `AI_CORE_LANGFUSE_HOST|PUBLIC_KEY|SECRET_KEY` incompleto; fuso desconhecido. As variáveis do
Google, do admin inicial e dos segredos de cliente são lidas pelas portas de segredo da 012 (ADR-020), não pelo
`Settings`.

**Rationale**: falha cedo (princípio VII) e uma fonte de configuração.

**Alternatives considered**: degradar a identidade em vez de parar (a instalação ficaria sem login nenhum — pior que
não subir).

### R37 — Etapa `identity` e ordem do boot

**Decision**: `configuration` → `adapters` (migrações de `assistants`, `http`, `mcp`, `capabilities`, **`identity`**,
**`observability`**) → **`identity`** (só com a identidade ligada; crítica: monta o `IdentityService`, `start()` — chave
de assinatura —, admin inicial, grupo de administração protegido vindo de `api_keys.admin_group`) → `packs` →
`mcp_registry` → `engine` → `assistants` → `api`. A etapa `assistants` monta o `AccessService` com
`OidcAudiences(public=<audience do cliente open-webui>, admin=<audience do cliente console>)` e, com a identidade, o
`JwksOidcVerifier(issuer=public_url, source=CallableJwksSource(identity.jwks))`; e o `AssistantsService` com o
`SystemOverrideStore`. A etapa `api` passa `admin_seams` e `instance` ao `create_app` e inclui o router da 012.

**Rationale**: a 003 precisa das chaves antes de servir; a identidade não depende de packs nem de MCP.

**Alternatives considered**: identidade depois de `assistants` (o verificador nasceria sem chaves).

### R38 — Portas novas por perfil

**Decision**: `REQUIRED_PORTS` ganha `identity_accounts`, `identity_grants`, `identity_keys`, `identity_settings`,
`identity_attempts`, `identity_upstream`, `identity_secrets`, `system_overrides`, `usage_store`, `price_store`,
`destination_settings`, `langfuse_transport`; `STORAGE_PORTS` ganha os de banco. `memory`: tudo em memória, chave mestra
aleatória por processo (com aviso no relatório de boot), Google real se configurado. `persistent`: Postgres e Google
real. `test`: memória, Google simulado, Langfuse simulado, chave mestra fixa. Trocáveis por `overrides` como os demais
(exceto armazenamento).

**Rationale**: o padrão dos perfis (FR-018).

**Alternatives considered**: —

### R39 — Perfil `test` compatível com as suítes de pack

**Decision**: o `test` mantém, por padrão, o verificador estático de `TEST_OIDC_TOKEN` (as suítes do `ai-scouting`
dependem dele). Com `AI_CORE_IDENTITY_ENABLED=true` no ambiente ou `platform(profile="test", config={...})`, monta a
identidade em memória, semeia o admin `TEST_ADMIN_USERNAME = "admin-teste"` com `TEST_ADMIN_PASSWORD` (exportados por
`ai_core.bootstrap.profiles`) e usa o JWKS em processo; `TEST_API_KEY` continua valendo nas superfícies privada e de
administração.

**Rationale**: nenhuma suíte existente quebra; a nova suíte de plataforma liga a identidade explicitamente.

**Alternatives considered**: ligar a identidade sempre no `test` (quebraria o `TEST_OIDC_TOKEN` das suítes de pack).

### R40 — Destinos do trace e origem do processo

**Decision**: a etapa `adapters` monta o `TraceService(primary=<memória|JSONL>, destinations=[UsageDestination(origin),
LangfuseDestination(...)], content=ContentPolicy(...))`; `origin = "evaluation"` no `ai-core eval run` e `"production"`
no resto (clarificação de 2026-10-13 da 009). Tarefas do ciclo de vida (`PeriodicTask`): flush do uso a cada 2 s,
expurgo da identidade a cada hora, retenção do uso a cada dia; `Platform.aclose()` esvazia os destinos (CLI e harness
também).

**Rationale**: ADR-034; o harness não vira produção no dashboard.

**Alternatives considered**: —

### R41 — Saúde

**Decision**: itens não críticos `trace:usage` e `trace:langfuse` a partir de `TraceDestinations.health()`; o item de
modelos passa a usar `assistants.declared_models()` (efetivos) por consulta, não a tupla do boot; item crítico
`identity` (chaves carregadas) com a identidade ligada.

**Rationale**: 011 FR-020.

**Alternatives considered**: —

### R42 — CLI

**Decision**: `COMMANDS`/`GROUPS` em `bootstrap/cli.py` ganham `users create|list|disable|enable|password|groups` e
`identity keys rotate [--force]` (comandos da 012), rodando na sessão de armazenamento (`wiring.storage`); sem a
identidade ligada, saem com código não zero e a mensagem "identidade desligada".

**Rationale**: o operador cria o primeiro admin antes de existir console (012 FR-018).

**Alternatives considered**: —

### R43 — Prova ponta a ponta sem rede

**Decision**: `tests/bootstrap/integration/test_platform_identity_admin.py`: `platform(profile="test")` com a
identidade ligada; o authlib como RP faz login como o admin semeado pelo cliente `open-webui` (audiência do chat) e pelo
cliente `console` (PKCE); `GET /v1/models` com o token do chat; `GET /admin/v1/me` com o da console (e 401 com o do
chat); sobreposição de `generation` num Assistant com `overrides: [models]`; uma conversa; `GET /admin/v1/usage` com a
chamada (SC-007 da 011).

**Rationale**: a prova da fase sem rede nem serviço externo (SC-003 da 011).

**Alternatives considered**: —

### R44 — Release

**Decision**: depois desta passada, o core vai para `0.6.0` (tag `v0.6.0`) **com aprovação do mantenedor**, antes da
passada da 002 (instalação), que fixa `CORE_REF`.

**Rationale**: o padrão das fases anteriores.

**Alternatives considered**: —

### R45 — Notas da implementação (incremento 9.2, 2026-10-14)

**Decision**:

- **Montagem dos destinos** em `bootstrap/observability.py` (como `bootstrap/identity.py` para a 012): as portas por
  perfil, a `InstallationDestinations` a partir do `Settings` e o `trace_parts(parts)`, que monta o `UsageDestination`,
  o `LangfuseDestination`, o `DestinationService` e o `UsageService`. A etapa `engine` monta o `TraceService` com os dois
  destinos e `capture=destinations.capture_enabled`.
- **Ajustes gravados**: sem banco, lidos no boot (`DestinationService.start()`); com banco, quando o pool de serviço abre
  (`startups` do ciclo de vida, R13). Consequência: no `persistent`, a linha de comando (`ai-core eval run`) só conhece o
  Langfuse da instalação — o da console vale no servidor.
- **Encerramento**: o ciclo de vida grava o último lote antes de fechar o pool (`shutdowns`), e `Platform.aclose()`
  esvazia os destinos e desliga o exportador do Langfuse. O `eval run` grava o lote da rodada na própria sessão de
  armazenamento (009 R38).
- **Chave mestra única por processo** (`identity.shared_master_key`): no `memory` sem a variável, a aleatória é sorteada
  uma vez para a 012 e a 009; no `persistent` sem ela, a 009 fica sem cifra e gravar o segredo do Langfuse responde
  `master_key_missing` (o resto funciona).
- **Origem**: `platform(origin="evaluation")` no `ai-core eval run`; `production` no resto.
- **Credenciais de teste**: `TEST_ADMIN_USERNAME`/`TEST_ADMIN_PASSWORD` reexportados por `ai_core.bootstrap.profiles`,
  ao lado de `TEST_API_KEY` (R39).

**Rationale**: o padrão já usado pela identidade (R13, R37), sem chamada de rede nem armazenamento novo.

**Alternatives considered**: abrir o pool de serviço na linha de comando (contra o R13).

---

## Passada de 2026-10-20: identidade Axon ([ADR-037](../../docs/adr/ADR-037-a-plataforma-se-chama-axon.md), [ADR-038](../../docs/adr/ADR-038-marca-da-plataforma-e-marca-da-instalacao.md); US7)

Decisões pré-aprovadas pelos ADRs (nomes, corte seco, versão, ordem das passadas, nome padrão); o que segue é como elas
chegam à composição e ao workspace, sem re-pesquisa. Os R anteriores ficam como foram executados (ADR-037, item 6); os
nomes antigos neles se leem pela tabela do ADR-037.

### R46 — Distribuição, pasta, import e versão

- **Decision**: `git mv ai-core axon-ai` (o workspace inteiro: contratos, core, generic, console) e `git mv
  packages/core/src/ai_core packages/core/src/axon_ai`. `packages/core/pyproject.toml`: `name = "axon-ai"`,
  `version = "0.7.0rc1"`, `description = "Runtime genérico da plataforma Axon (monolito modular; specs 002–009, 011,
  012)."`, script `axon = "axon_ai.bootstrap.cli:main"`, pacote `axon_ai` no build. O `__init__.py` diz `axon-ai:
  runtime genérico da plataforma Axon`. As pastas `packages/core`, `packages/contracts` e `packages/generic` ficam. O
  `uv.lock` é regenerado (`uv lock`), não editado.
- **Rationale** (ADR-037, itens 2 e 4): no código, `ai-core` vira `axon-ai`; a linha 0.6.0 termina no rc6 com o nome
  antigo, então o primeiro release com o nome novo é `0.7.0rc1`. Um pacote só: o import muda em todos os módulos de uma
  vez, e a 011, dona da distribuição, é quem muda.
- **Alternatives**: uma passada por módulo para o import (impossível: um pacote Python não tem duas raízes);
  `0.6.0rc7` (misturaria os dois nomes na mesma linha de versões).

### R47 — Substituição mecânica e o que ela protege

- **Decision**: um script no scratchpad (não versionado) aplica, do padrão mais específico ao mais geral:
  1. `x-ai-core-optional` → `x-axon-optional` (marcador interno da 006, que nunca vai ao provider; a 006 não tem passada
     própria);
  2. **comando**: `ai-core` seguido de um subcomando (`serve`, `packs`, `assistants`, `keys`, `health`, `eval`, `audit`,
     `users`, `groups`, `identity`, `--version`, `--help`, `--profile`), o `[project.scripts]` e as frases "comando/raiz
     `ai-core`" → `axon`;
  3. `ai_core` → `axon_ai`; `AI_CORE` → `AXON`; o restante de `ai-core` → `axon-ai`.

  Antes, troca por marcadores (e devolve depois) o que é das passadas de outros módulos: `x-ai-core-*` e `x_ai_core`
  (008); os rótulos `ai-core/identity/…` e `ai-core/observability/v1` (012, 009); as audiências — `ai-core-admin` em
  qualquer lugar, `"ai-core"`/`'ai-core'` entre aspas em `.py` e `.md`, e `ai-core` depois de `audience`, `aud` ou
  "audiência(s)" (003); o grupo de entry point `ai_core.packs` (`entry-points."ai_core.packs"`, `PACKS_GROUP` e as
  frases "grupo/entry point `ai_core.packs`") (002); `http://ai-core:` e `/etc/ai-core`/`/run/secrets/ai-core`, que são
  da instalação (002); e todo `AI_CORE_…` seguido de `→` (o texto que documenta a recusa). Os literais entre aspas que
  são da 011 — `prog`, a versão lida dos metadados, o nome do pool — são trocados à mão (R49, R50), assim como o título
  do OpenAPI (008), o realm (012) e o `service.name` (009) ficam com as passadas deles.

  Escopo: `axon-ai/**` (código, testes, configuração, console, menos `uv.lock`, `node_modules`, `CHANGELOG.md` e
  binários), `.github/workflows/*.yml`, os documentos vivos das specs 001–013 (`spec.md`, `design.md`,
  `data-model.md`, `quickstart.md`, `contracts/**`), `specs/README.md`, `PRODUCT.md` e
  `.impeccable/surfaces/ai-core-console.md` (caminhos). Fora: `research.md`, `plan.md`, `tasks.md`, `checklists/`,
  `docs/adr/`, `docs/archive/`, `docs/relatorio-estilo-arquitetural.md` (relatório datado), `.impeccable/mocks/`,
  as specs `1xx` (passada da 101), `CLAUDE.md`, `.specify/templates/overrides/` e o `README.md` da raiz (fechamento),
  os submódulos. A spec da 011 e os documentos dela já são escritos com os nomes novos nesta passada.
  Depois: `git grep` dos resíduos, revisão de cada um (o que sobra é protegido ou histórico) e `git grep -w agentic`
  com a contagem de antes (o flow intacto).
- **Rationale** (ADR-037, itens 6 e 7): a passada que renomeia uma distribuição atualiza mecanicamente quem a consome;
  os identificadores com comportamento (credencial, dado selado, protocolo) mudam com testes na passada do dono. O
  plano do renome (Etapa 2, "Mecânica") já previa script, ordem dos padrões e a regra de contexto do comando.
- **Alternatives**: `sed` global sem proteção (trocaria audiências e rótulos HKDF para `axon-ai`, que nem é o nome
  final deles); renomear também os identificadores dos outros módulos aqui (atropela as passadas e os testes deles).

### R48 — Prefixo `AXON_` e recusa de `AI_CORE_*`

- **Decision**: `settings.PREFIX = "AXON_"`; os adapters de segredo leem `AXON_MCP_SECRET_<REF>` (007),
  `AXON_OPENAI_API_KEY`/`AXON_OPENROUTER_API_KEY` (006) e `AXON_IDENTITY_SECRET_<REF>`, `AXON_GOOGLE_*`,
  `AXON_BOOTSTRAP_ADMIN_*` (012) — a troca é a substituição mecânica (R47). A recusa fica em
  `EnvConfigSource.load()`, antes de ler qualquer valor: `LEGACY_PREFIX = "AI_CORE_"`; os nomes do ambiente com esse
  prefixo, ordenados, viram um `ConfigurationError`:

  ```text
  variáveis com o nome antigo da plataforma (ADR-037); renomeie:
    AI_CORE_MCP_SECRET_FINANCEIRO_TOKEN → AXON_MCP_SECRET_FINANCEIRO_TOKEN
    AI_CORE_PROFILE → AXON_PROFILE
  ```

  Sem valor, nem o tamanho. A etapa `configuration` falha com essa mensagem (boot e `serve`), e a CLI sai com 1, como
  em qualquer erro de configuração (contracts/cli.md). As suítes leem `AXON_TEST_POSTGRES_DSN`.
- **Rationale** (ADR-037, item 3): corte seco com diagnóstico; um `.env` antigo ignorado em silêncio subiria um
  `persistent` como `memory`, sem banco e sem identidade. A regra pelo prefixo (não por lista) pega também os nomes de
  outros módulos e os que nunca existiram. A carga da configuração é o único ponto por onde todo boot e todo comando
  passam, e vem antes de qualquer adapter de segredo.
- **Alternatives**: aceitar os dois prefixos por um tempo (rejeitado no ADR-037); só avisar (o boot seguiria com a
  configuração errada); recusar só as variáveis conhecidas (o `AI_CORE_MCP_SECRET_<REF>` antigo escaparia, e o servidor
  MCP ficaria sem credencial com um erro que não diz por quê).

### R49 — Comando `axon` e `--version`

- **Decision**: `argparse.ArgumentParser(prog="axon", description="Axon — linha de comando do operador")`, com
  `--version` (`action="version"`, `version=f"axon-ai {_core_version()}"`); `_core_version()` lê
  `importlib.metadata.version("axon-ai")` e devolve `desconhecida` sem metadados. A ação de versão do `argparse` sai com
  0 antes de qualquer subcomando, então nada de configuração é carregado. A ajuda de `--profile` cita `AXON_PROFILE`.
- **Rationale** (ADR-037, item 2): o que o operador digita fica curto; a versão é da distribuição, então leva o nome
  dela. `_core_version()` já existia (o relatório do `eval run` a usa) e só muda de nome lido.
- **Alternatives**: subcomando `axon version` (mais um comando a registrar, sem ganho); `axon <versão>` sem o nome da
  distribuição (esconde qual pacote está instalado).

### R50 — Nome padrão e pool

- **Decision**: `DEFAULT_DISPLAY_NAME = "Axon"` em `bootstrap/settings.py`; `AsyncConnectionPool(..., name="axon")` em
  `bootstrap/profiles.py`. Os defaults próprios da 008 (`InstanceBranding.name`) e da 012 (`pages.DEFAULT_NAME`), que só
  valem quando montados sem a 011, mudam nas passadas deles, com o lockup e o `instance.custom`.
- **Rationale** (ADR-038, item 1; ADR-037, item 2): o nome padrão é configuração da 011; o pool é infraestrutura que a
  011 monta. O que se desenha com o nome (lockup, atribuição) é da 012 e da 013.
- **Alternatives**: trocar aqui também os defaults da 008 e da 012 (internals de outros módulos, contra o princípio II).

### R51 — Documentos vivos, specs 004–007 e o que fica para depois

- **Decision**: a substituição do R47 alcança os documentos vivos de 001–013 onde citam o core, o comando, o prefixo ou
  os caminhos (`axon-ai/packages/core/src/axon_ai/...`). As specs 004–007 não ganham US: só os nomes. `specs/README.md`:
  a coluna de caminhos (`axon_ai/...`), o diagrama (`axon-ai`, workspace `axon-ai`) e a linha da 011.
  `docs/roadmap.md`: a linha de andamento do incremento 9.5. `CLAUDE.md`, os overrides de template e o `README.md` da
  raiz ficam para o fechamento do renome (plano, "Fechamento"); até lá, os caminhos do `CLAUDE.md` se leem pela tabela
  do ADR-037.
- **Rationale** (ADR-037, item 6): documentos vivos passam aos nomes novos na passada que torna o antigo errado; o
  histórico fica. As specs `1xx` citam o core pela tag `v0.3.0`, ainda com o nome antigo, até a passada da 101.
- **Alternatives**: deixar os caminhos antigos nas specs até cada passada (as specs de 004–007 ficariam erradas para
  sempre, porque não têm passada própria).

### R52 — CI e console

- **Decision**: `.github/workflows/*.yml`: filtros de caminho `axon-ai/**`, `working-directory: axon-ai` e
  `axon-ai/console`, `AXON_TEST_POSTGRES_DSN`, `uv run axon …`. A console muda só pelo que a 011 renomeia: a pasta
  (`axon-ai/console/`), os imports `axon_ai` do `e2e/serve_platform.py`, a variável `AXON_UPSTREAM` do proxy de
  desenvolvimento, do Playwright e do `nginx.conf.template` (prefixo do ADR-037; a instalação a passa na passada dela)
  e os textos que nomeiam variáveis `AXON_*` ao operador. O pacote npm, o "Agentic" da barra lateral e do acesso negado
  e os tokens ficam com a passada da 013.
- **Rationale** (ADR-037, item 7): a CI fica verde a cada passada; a console é consumidora do nome do workspace e das
  variáveis, não dona deles.
- **Alternatives**: deixar `AI_CORE_UPSTREAM` até a 013 (o prefixo antigo sobreviveria num lugar que o operador
  configura, sem a recusa do boot para apontá-lo).

### R53 — Testes da US7

- **Decision**:
  - `tests/bootstrap/unit/test_settings_legacy.py`: um `AI_CORE_*` (conhecido, desconhecido, vazio, com a nova também
    definida) → `ConfigurationError` com `AI_CORE_X → AXON_X` por linha, ordenado, sem o valor; `AI_COREX`,
    `MY_AI_CORE_URL` e `AI_SCOUTING_INDEX` não são recusados (US7 cen. 3, 4; casos de borda).
  - `tests/bootstrap/contract/test_cli_commands.py`: `--version` imprime `axon-ai ` + a versão de
    `importlib.metadata` e sai com 0 sem configuração (cen. 1); um subcomando com `AI_CORE_PROFILE` no ambiente sai com
    1 e a linha da recusa (cen. 3); `prog` `axon` na ajuda (cen. 7).
  - O nome padrão "Axon" nos testes de settings e no `me` da prova ponta a ponta (cen. 5); as suítes existentes com o
    prefixo novo cobrem o cen. 2 e o cen. 6.
  - `tests/bootstrap/unit/test_core_old_name_absent.py`: `importlib.util.find_spec("ai_core")` é `None` (FR-022), como a 001 fez
    para os contratos.
- **Rationale**: cada cenário da US7 com um teste; o resto é a suíte existente com os nomes novos.
- **Alternatives**: —

---

# Correção de 2026-10-21: a saúde da linha de comando e a identidade (FR-012)

## R34 — A saúde de `axon health` confere a identidade sobre a própria sessão

**Decision**: `platform_health(parts, *, session, identity=None)` aceita a identidade a conferir, e `session_identity(parts,
session)` (`wiring.py`) a monta: sem banco, a da plataforma; com banco, um serviço da 012 sobre a sessão do comando,
iniciado com `start()`, como o boot (`_start_identity`) e o servidor (`app_lifespan`) o iniciam. `axon health` usa os
dois; a superfície privada continua com a da plataforma, já iniciada pelo ciclo de vida.

**Rationale**: com o perfil `persistent` e a identidade ligada, as chaves de assinatura só chegam ao serviço da
plataforma quando o ciclo de vida da app abre o pool de serviço; a linha de comando não o abre, então `axon health`
dava o item crítico `identity` como falha ("nenhuma chave de assinatura carregada") e `status: down`, com o servidor
saudável — contra a FR-012 (o mesmo resultado na API e na linha de comando). Achado na atualização da instalação para a
`v0.7.0-rc2`. `start()` não acrescenta efeito ao que o boot do mesmo comando já fez sobre a mesma base.

**Alternatives considered**: um método público só de leitura das chaves na 012 (mudaria o módulo dono por uma
necessidade da composition root); omitir o item `identity` na linha de comando (esconderia uma chave que não abre com
a chave mestra, que é exatamente o que o item existe para mostrar).

---

# Passada de 2026-10-21: o pack prepara os próprios dados ([ADR-041](../../docs/adr/ADR-041-o-pack-prepara-os-proprios-dados-no-build.md); FR-028)

## R54 — `AXON_PACKS_DATA_DIR` e o registro de `packs prepare`

**Decision**: `Settings.packs_data_dir: Path | None` lido de `AXON_PACKS_DATA_DIR` por `_path` (vazio = ausente, como
`AXON_PACKS_FILE`); sem validação de existência nem de caminho absoluto. `pack_runtime(parts)` (`wiring.py`) passa
`LocalPackDataDirs(settings.packs_data_dir)` ao `PackRuntime` — o mesmo nos três perfis, porque o diretório é do
operador, não um armazenamento que o perfil troca. Em `bootstrap/cli.py`, `packs prepare` entra na lista de registro
com o mesmo boot dos `packs list|check` (`until=STAGE_ADAPTERS`) e chama `packs_cli.prepare_command` sobre o runtime
**não carregado**; a mensagem de `PackConfigError` sai pelo mesmo `config_error_command` (2). `axon serve` não muda.

**Rationale** (ADR-041, itens 2–4): a raiz é configuração de instalação, como o caminho do `packs.yaml`; o build e o
runtime a leem da mesma variável, então o caminho que o pack recebe é o mesmo. A existência do diretório não é
conferida no boot porque `data_dir` sem conteúdo é assunto do pack (ele falha na carga com mensagem própria, e o boot
segue, princípio VII). Um caminho relativo é aceito (útil no desenvolvimento) e resolvido pelo processo, como os outros
caminhos da configuração.

**Alternatives considered**: um default (`/opt/axon-data`; amarraria a plataforma ao layout de uma imagem, e o
desenvolvimento passaria a escrever fora do repositório); exigir caminho absoluto (diferente de todos os outros caminhos
da configuração, sem ganho); criar o diretório no boot (contraria o somente leitura em runtime).

## R55 — Configuração na imagem e nenhum arquivo de segredo obrigatório ([ADR-042](../../docs/adr/ADR-042-instalacao-por-camadas.md))

**Decision**: nada muda no código da 011. Os caminhos de configuração (`AXON_PACKS_FILE`, `AXON_ASSISTANTS_FILE`,
`AXON_IDENTITY_CLIENTS_FILE`, `AXON_LOGO_FILE`) apontam, no modelo de instalação, para `/etc/axon` na própria imagem, e
as imagens base fixam `AXON_PACKS_FILE` e `AXON_PACKS_DATA_DIR` (002 R66). O único arquivo de segredo que a
plataforma lê, `AXON_BOOTSTRAP_ADMIN_PASSWORD_FILE`, continua opcional; o primeiro administrador sai de `axon users
create` no console do contêiner.

**Rationale** (ADR-042, itens 4 e 5): a 011 já lê cada arquivo por variável e já aceita a ausência do admin inicial;
o que muda é a instalação.

**Alternatives considered**: —

## R56 — Os tetos das imagens ([ADR-044](../../docs/adr/ADR-044-imagens-na-conversa.md), item 12; FR-029)

**Decision**: quatro campos no `Settings`, com os padrões do ADR e faixas (`TOOL_MAX_ATTACHMENT_RANGE` e
`MAX_INPUT_IMAGE_RANGE` 1 KiB–20 MiB, `MAX_REQUEST_RANGE` 64 KiB–256 MiB, `MAX_INPUT_IMAGES_RANGE` 0–16); o
`mcp_service` passa `max_attachment_bytes`, e o `create_app` recebe `ImageLimits` da 008. Nenhuma porta nova: o provider
simulado do perfil `test` já registra as imagens (`ScriptedProvider.images`, 006). A prova é
`tests/bootstrap/integration/test_platform_images.py`.

**Rationale**: os números são do operador, como os da fila e do `rag_first` (princípio X); os tetos mínimos impedem uma
configuração que recusaria toda requisição. As faixas moram aqui, como as do gateway (R27), para o erro nomear a
variável.

**Alternatives considered**: um teto único para imagem de tool e do usuário (o ADR os separa: a da tool vem de um
servidor que o operador escolheu; a do usuário, de qualquer cliente).

## R57 — O endereço dos scripts dos gráficos ([ADR-052](../../docs/adr/ADR-052-graficos-na-conversa.md), item 6; FR-030)

**Decision**:
- `Settings.charts_script_base_url`, lido de `AXON_CHARTS_SCRIPT_BASE_URL` e conferido pela mesma regra do
  `AXON_PUBLIC_URL` (`_check_public_url`, agora com o nome da variável na mensagem).
- A propriedade `charts_base_url` devolve o próprio endereço ou, na falta dele, o `public_url`.
- O `create_app` recebe `charts_base_url=settings.charts_base_url`.
- A `PlatformHealth` ganha `charts: bool | None`, e o item `charts` é sempre `ok`, com o detalhe
  `CHARTS_WITHOUT_URL` quando falta o endereço.
- Prova ponta a ponta sem rede em `tests/bootstrap/integration/test_platform_charts.py`:
  1. uma tool MCP programada devolve a série em JSON;
  2. o controller programado chama `demo.serie` e depois `generic.chart`, do `axon-generic` carregado pelo entry point;
  3. a resposta em streaming traz a tabela, um `embeds` cujas páginas carregam os scripts que a própria app serve, e
     `x_axon.charts`;
  4. a geração recebe o aviso dos gráficos, e o resultado da tool que volta ao controller leva só a marca.

**Rationale**:
- **O endereço público basta na instalação comum.** Com a console, o `AXON_PUBLIC_URL` é o domínio dela, e o nginx
  repassa `/static/` ao core (013). A variável própria cobre o caso em que os scripts são servidos de outro host.
- **O aviso não degrada a saúde.** O ADR pede um aviso não crítico, mas a 008 trata como `degraded` qualquer item com
  `ok: false`, inclusive os não críticos, e o `axon health` sai com 1. Uma instalação sem Open WebUI não deve ficar
  degradada por isso. O teste da CLI pegou o problema na primeira versão.

**Alternatives considered**:
- Exigir o endereço sempre: quebraria as instalações só de API.
- O item `charts` com `ok: false` não crítico: degrada a saúde, como visto acima.
- Montar o endereço a partir do `Host` do pedido: atrás do proxy, o core vê o endereço interno.
