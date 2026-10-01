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
