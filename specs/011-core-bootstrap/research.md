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
