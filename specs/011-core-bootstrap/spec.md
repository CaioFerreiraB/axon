# Feature Specification: Bootstrap e composition root do núcleo

**Feature Branch**: `011-core-bootstrap`

**Created**: 2026-09-14

**Status**: Draft

**Input**: ADR-012 (composition root), ADR-013 (relógio único, Trace Sink); [relatório de estilo arquitetural](../../docs/relatorio-estilo-arquitetural.md), lacuna G6; arch-v1 §13 (boot, CLI) e §14 (deployment). Fase 9 (2026-10-13): identidade da plataforma, superfície de administração, sobreposições, destinos do trace e chave mestra — ADR-030 a ADR-034.

## Module Boundary *(mandatory)*

- **Módulo**: Bootstrap — composition root do `ai-core`: carrega a configuração do operador, escolhe e instancia o adapter de cada porta, injeta seams e adapters nos módulos, conduz a ordem de boot e oferece os pontos de entrada do processo.
- **Repositório / distribuição**: `ai-core` → `packages/core/src/ai_core/bootstrap/`; comando `ai-core` (raiz).
- **Consome (seams)**: o `api.py` de todos os módulos do core (002–009 e 012) e os `adapters/` deles. É o único módulo autorizado a importar adapters de outros módulos (princípio XIII).
- **Expõe (seams)**: nenhum seam Python. Expõe os pontos de entrada do processo — servidor e raiz da linha de comando `ai-core`, onde cada módulo contribui seus subcomandos —, consumidos pelo operador, pelo template de instalação (002) e pela CI.
- **Depende de infraestrutura (via portas)**: configuração do operador (arquivos e ambiente). Indiretamente, toda a infraestrutura dos módulos, cujos adapters instancia.
- **Não conhece**: regras de negócio de qualquer módulo (grant, catálogo, flows, políticas de tool), o estado interno do motor e o contexto de execução (005), qualquer domínio.
- **Substituição**: preservar a ordem de boot com falha fechada, os perfis de adapters e os comandos da linha de comando; a técnica de injeção é livre.
- **Insumo técnico**: [design.md](design.md); [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md), [ADR-013](../../docs/adr/ADR-013-seams-transversais-trace-e-tempo.md), [ADR-009](../../docs/adr/ADR-009-deploy-docker-build-arg.md), [ADR-020](../../docs/adr/ADR-020-segredos-uma-fonte-por-perfil-uma-porta-por-modulo.md), [ADR-030](../../docs/adr/ADR-030-a-plataforma-e-o-provedor-de-identidade.md), [ADR-033](../../docs/adr/ADR-033-segredos-de-runtime-cifrados-com-a-chave-mestra.md), [ADR-034](../../docs/adr/ADR-034-trace-com-destinos-e-conteudo-opcional.md).

## Clarifications

### Session 2026-09-21

- Q: A ordem de boot tem sete etapas, mas duas pertencem a módulos que ainda não existem. Como o boot lida com isso? → A: Cada etapa é declarada — nome, ação e política de falha (interrompe o boot ou degrada e segue) — e a sequência executa a lista registrada na fase. Na Fase 1 registram-se configuração, adapters, packs, motor e API; registry MCP e validação de Assistants entram quando seus módulos existirem, sem tocar no código da sequência. É o que torna FR-002 e FR-003 verificáveis com etapas de teste, sem subir a plataforma inteira.
- Q: A linha de comando completa é a US4 (Fase 2); o que a Fase 1 entrega como ponto de entrada? → A: Um `ai-core serve` mínimo, que conduz o boot e serve a aplicação com um servidor ASGI. É o que faz a US1 existir de fato — sem ele, "o operador inicia o serviço" não teria como acontecer — e o que permite conversar com a plataforma por HTTP fora da suíte. Os subcomandos contribuídos por cada módulo continuam na Fase 2.
- Q: A API resolve `<assistant>/<modelo>` num grant, e até a 003 existir quem monta isso é esta spec. De onde vem a configuração? → A: De um `assistants.yaml` mínimo — nome do Assistant → packs, flow e modelo por papel —, como o `design.md` já previa ao dar YAML ao armazenamento de Assistants de sistema. A composition root o lê e monta o resolvedor de grant; quando a 003 chegar, ela assume o arquivo e esta spec passa a consumir o seam dela. O formato nasce aqui e é herdado, em vez de inventado duas vezes.
- Q: O perfil de teste que sobe a plataforma inteira em memória é código distribuído ou das suítes? → A: Da distribuição. O perfil vive no próprio módulo, e qualquer suíte monta a plataforma com uma chamada — inclusive a de um pack externo, que passa a poder testar seu pack contra a plataforma de verdade. É o que a SC-003 mede, e evita que cada spec remonte tudo à mão.

### Session 2026-09-30

- Q: Como cada perfil autentica, agora que a 003 existe? → A: Com a verificação real nos três, e o autenticador anônimo sai. `persistent`: OIDC por JWKS e chaves de API no Postgres. `memory`: OIDC quando configurado e uma chave de desenvolvimento lida do ambiente, no grupo de administração. `test`: verificador OIDC estático e chave semeada, com credenciais conhecidas exportadas para as suítes.
- Q: O que faz a saúde agregada responder 503 (fora do ar), e o que só a marca como degradada, com 200? → A: Só item **crítico** leva a 503 — armazenamento persistente inacessível ou etapa crítica do boot que falhou. Pack em erro, Assistant indisponível e modelo fora do ar são itens não saudáveis de um resultado `degraded`, com 200 e o item nomeado: a instância continua atendendo o resto.

### Session 2026-10-02

- Q: Quando a plataforma verifica se os servidores MCP globais estão no ar — só na saúde agregada, também no boot, ou em nenhum? → A: Só na saúde agregada. O boot não sai para a rede: a etapa do registry MCP carrega o arquivo do operador e o armazenamento, e um MCP fora do ar nunca atrasa nem impede a subida (SC-004). A saúde traz um item **não crítico** por servidor global, consultado em paralelo sob o prazo e o cache que ela já tem; servidor fora do ar deixa o resultado `degraded` (200), nunca `down`. Servidores de usuário (`~alias`) ficam fora — a 008 os verifica um a um.
- Q: Como uma suíte ponta a ponta, subindo a plataforma pelo perfil `test`, faz o controller pedir uma tool e um servidor MCP responder, sem rede? → A: A chamada que monta a plataforma aceita **trocas de porta**: a suíte passa o adapter de qualquer porta (o provider do controller com um roteiro, o transporte MCP com servidores programados) sem montar o resto. Sem troca, o perfil `test` continua autossuficiente — o modelo simulado responde `{"action": "answer"}` quando chamado como controller e o transporte MCP simulado não tem servidores. A troca existe só na chamada Python que as suítes usam; nenhum arquivo de configuração nem variável de ambiente a expõe.
- Q: Com o registry MCP no mesmo Postgres dos outros módulos, o caso de borda "armazenamento do registry MCP indisponível" deve ser reescrito? → A: Sim. Com um banco só (ADR-015), registry inacessível é banco inacessível: a saúde agregada responde `down` (503, item crítico) e as requisições recebem 503 `storage_unavailable` (008 FR-021). O que continua não crítico é o servidor MCP **remoto** fora do ar: fica fora do catálogo da execução com registro `error`, e a execução segue (004, 005).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Operador sobe a plataforma e o boot segue uma ordem fixa (Priority: P1)

O operador inicia o serviço. O bootstrap carrega e valida a configuração, instancia os adapters do perfil escolhido, carrega os packs (002), prepara o registry MCP (007), monta o motor (005), valida os Assistants contra packs, MCPs, coleções e os flows que o motor oferece (003) e só então abre a API (008). Cada etapa falha fechada: erro de configuração impede o boot com mensagem explícita; pack ou Assistant inválido fica indisponível com erro, e o resto sobe.

**Why this priority**: Fase 1 — a conversa ponta a ponta exige que alguém monte as peças. Princípio VII: falha fechada e explícita.

**Independent Test**: Iniciar com o pack de referência habilitado, um pack defeituoso e um Assistant que referencia o defeituoso; o serviço sobe, o pack de referência atende, e o pack defeituoso e o Assistant aparecem com erro.

**Acceptance Scenarios**:

1. **Given** uma configuração válida, **When** o operador inicia o serviço, **Then** as etapas ocorrem na ordem configuração → adapters → packs → registry MCP → motor → Assistants → API, e nenhuma requisição é aceita antes da última.
2. **Given** uma configuração com campo obrigatório ausente ou inválido, **When** o operador inicia o serviço, **Then** o boot para antes de carregar packs, com erro que nomeia o campo.
3. **Given** um Assistant que referencia um pack em erro, **When** o boot conclui, **Then** o Assistant fica indisponível com o motivo e os demais atendem.
4. **Given** um sinal de parada, **When** recebido, **Then** o serviço deixa de aceitar requisições, aguarda as execuções em andamento até o prazo configurado e libera os recursos na ordem inversa do boot.
5. **Given** o boot concluído, **When** uma execução começa, **Then** o motor usa os seams injetados no boot e nenhum adapter é instanciado durante a execução.

---

### User Story 2 - Perfil de adapters por fase, sem mudar módulos (Priority: P1)

O operador escolhe, por configuração, qual adapter atende cada porta. Na Fase 1, tudo roda em memória; da Fase 2 em diante, Assistants de usuário e histórico passam a armazenamento persistente; na Fase 3, registry MCP e auditoria também (o checkpoint de execução ficou adiado até haver retomada — 005, clarificação de 2026-10-01). Trocar de perfil não altera nenhum módulo.

**Why this priority**: ADR-012 — as trocas previstas no roadmap são trocas de adapter.

**Independent Test**: Rodar a mesma suíte ponta a ponta com o perfil em memória e com o perfil persistente; os resultados são os mesmos e nenhum módulo muda.

**Acceptance Scenarios**:

1. **Given** o perfil em memória, **When** o serviço sobe, **Then** nenhum armazenamento externo é exigido.
2. **Given** o perfil persistente com o armazenamento indisponível, **When** o serviço sobe, **Then** o boot falha com erro que nomeia a porta e o adapter.
3. **Given** um perfil em que uma porta declarada por algum módulo não tem adapter, **When** a configuração é validada, **Then** o perfil é rejeitado antes do boot, com erro que nomeia a porta.
4. **Given** a checagem de fronteiras de import do CI, **When** ela roda, **Then** nenhum módulo além deste importa adapters de outro módulo.
5. **Given** qualquer perfil, **When** uma requisição chega sem credencial, **Then** é recusada (401); **Given** o perfil `test`, **When** a suíte usa as credenciais exportadas pela distribuição, **Then** a conversa atravessa a plataforma (FR-015).

---

### User Story 3 - Plataforma inteira em memória para testes ponta a ponta (Priority: P1)

A suíte ponta a ponta sobe a plataforma inteira com adapters em memória e um provider de modelo simulado: sem banco, sem vetores, sem rede.

**Why this priority**: Princípio XIII (toda porta tem adapter em memória) e 008 SC-002 (suíte ponta a ponta via HTTP). É o que permite testar a plataforma desde a Fase 1.

**Independent Test**: Num ambiente sem rede nem serviços externos, a suíte ponta a ponta do core passa.

**Acceptance Scenarios**:

1. **Given** um ambiente sem serviços externos, **When** a suíte sobe a plataforma no perfil de teste, **Then** uma conversa ponta a ponta com o pack de referência funciona pela API.
2. **Given** o perfil de teste com o relógio fixado, **When** várias execuções rodam, **Then** todas recebem a mesma data de referência (ADR-013).
3. **Given** o perfil de teste com um controller programado e um servidor MCP programado trocados na montagem, **When** uma conversa com um Assistant `agentic` chega pela API, **Then** a tool do servidor é chamada pelo gateway e o resultado chega à resposta — sem rede.

---

### User Story 4 - Linha de comando única do operador (Priority: P2)

Um único comando `ai-core` reúne os subcomandos dos módulos — `serve`, `packs list`, `packs check` (002), `assistants validate` (003) — com a mesma configuração e os mesmos adapters do servidor. Os subcomandos de validação rodam sem abrir a API.

**Why this priority**: Fase 2. Diagnóstico e validação no build da imagem (ADR-009) dependem disso; sem uma raiz, os comandos ficariam espalhados entre módulos.

**Independent Test**: Rodar `packs check` e `assistants validate` numa instalação com um pack incompatível e um Assistant inválido; os dois saem com código não zero e mensagem explícita, sem subir o servidor.

**Acceptance Scenarios**:

1. **Given** uma instalação, **When** o operador pede a ajuda do comando `ai-core`, **Then** vê os subcomandos de todos os módulos.
2. **Given** o subcomando `assistants validate`, **When** executado, **Then** usa a mesma configuração e os mesmos adapters do servidor, sem abrir a API.
3. **Given** um módulo novo que contribui subcomandos, **When** incluído, **Then** seus subcomandos aparecem sem alterar os de outros módulos.

---

### User Story 5 - Saúde agregada (Priority: P2)

A verificação de saúde reúne o estado de cada módulo — packs carregados e em erro, providers de modelo, registry MCP, armazenamento — num único resultado, exposto pela superfície privada (008) e pela linha de comando.

**Why this priority**: Diagnóstico sem acesso ao host (008 US5). Cada módulo sabe verificar a si mesmo, mas alguém precisa agregar.

**Independent Test**: Com o provider local fora do ar, a saúde aponta exatamente esse item como degradado e os demais como saudáveis.

**Acceptance Scenarios**:

1. **Given** o provider local fora do ar, **When** a saúde é consultada, **Then** o resultado é `degraded` (200), nomeia o provider e o modelo indisponíveis, e os demais itens aparecem saudáveis.
4. **Given** um servidor MCP global fora do ar, **When** a saúde é consultada, **Then** o resultado é `degraded` (200) e nomeia o alias e o motivo; o boot que precedeu a consulta concluiu sem sair para a rede.
3. **Given** o perfil persistente com o banco inacessível depois do boot, **When** a saúde é consultada, **Then** o resultado é `down` (503) e nomeia o armazenamento.
2. **Given** todos os itens disponíveis, **When** a saúde é consultada, **Then** o resultado é saudável.

---

### User Story 6 - A plataforma sobe com identidade, administração e destinos do trace (Priority: P2)

O operador liga o provedor de identidade da plataforma (012) e a composição o monta antes da API, gera a chave de
assinatura na primeira vez, cria o admin inicial quando a instalação o declara e não há contas, injeta as chaves
públicas no verificador da 003 e monta o adapter primário do protocolo no mesmo app da 008. Também monta as
sobreposições da 003, os destinos do trace da 009 (uso e Langfuse) e a superfície de administração, e lê a chave mestra
da instalação, recusando o boot quando ela falta e há o que cifrar.

**Why this priority**: Sem a composição, nenhum dos módulos da Fase 9 existe no processo; é a passada de encaixe.

**Independent Test**: Subir o perfil `test` com a identidade ligada; entrar pelo protocolo com o admin semeado, chamar
`/v1/models` com o token do chat e `/admin/v1/me` com o token da console; sobrepor o modelo de um Assistant, conversar e
ler o uso.

**Acceptance Scenarios**:

1. **Given** o perfil `persistent` com a identidade ligada e sem `AI_CORE_MASTER_KEY`, **When** a plataforma sobe,
   **Then** o boot falha na etapa `configuration` com erro que nomeia a variável.
2. **Given** a identidade ligada e `AI_CORE_OIDC_ISSUER` também configurado, **When** a plataforma sobe, **Then** o boot
   falha nomeando o conflito: a plataforma confia num único emissor.
3. **Given** uma instalação sem contas e as variáveis de admin inicial, **When** a plataforma sobe, **Then** o admin
   existe no grupo de administração; numa segunda subida, as variáveis são ignoradas com aviso.
4. **Given** o Langfuse configurado e fora do ar, **When** a plataforma sobe, **Then** o boot conclui; a saúde mostra
   `trace:langfuse` como não crítico e indisponível.
5. **Given** o perfil `test`, **When** uma suíte de pack o monta, **Then** encontra o admin semeado e as credenciais dele
   exportadas pela distribuição, como já encontra a chave de teste.

---

### Edge Cases

- Configuração de pack que referencia pack não instalado: tratada pela 002 (`error: não instalado`); o boot continua.
- Dois adapters para a mesma porta no mesmo perfil: configuração inválida; o boot não começa.
- Armazenamento do registry MCP indisponível (perfil `persistent`): é o banco único fora do ar (ADR-015) — saúde `down` (503) e requisições com 503 `storage_unavailable` (008 FR-021). Servidor MCP **remoto** fora do ar não é isso: fica fora do catálogo da execução, com registro `error`, e a execução segue; na saúde, é item não crítico.
- Sinal de parada durante o boot: as etapas já concluídas são desfeitas na ordem inversa.
- Referência de segredo ausente no ambiente: o adapter que precisa dela falha na inicialização com erro que nomeia a referência, nunca o valor. *(Refinado pelo [ADR-020](../../docs/adr/ADR-020-segredos-uma-fonte-por-perfil-uma-porta-por-modulo.md): a peça que depende da credencial é montada em estado de falha e o boot continua — etapa `mcp_registry` degradada para servidor MCP; item `model:<provider/modelo>` indisponível na saúde e erro explícito na chamada para provider de modelo.)*
- Perfil `memory` sem chave de desenvolvimento nem OIDC configurados: o boot conclui, toda credencial é recusada (401), e o relatório de boot diz isso em destaque — nunca uma plataforma aberta por falta de configuração.
- Perfil `memory` com a identidade ligada e sem chave mestra: o boot gera uma chave efêmera, e o relatório avisa que contas, sessões e chaves somem no restart.
- Variáveis do Langfuse definidas pela metade: erro de configuração que nomeia a variável que falta.
- Banco de uso fora do ar com o resto do Postgres de pé: impossível por construção (um banco único, ADR-015); com o banco fora, a saúde já é `down`.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE carregar a configuração do operador (packs, Assistants de sistema, perfil de adapters, parâmetros de ambiente, referências de segredo) e validá-la antes de qualquer outra etapa, rejeitando-a com erro que nomeia o campo.
- **FR-002**: O sistema DEVE conduzir o boot na ordem configuração → adapters → packs (002) → registry MCP (007) → motor (005) → validação de Assistants (003, que usa os nomes de flow do motor) → API (008); a API só aceita requisições depois da última etapa. As etapas são declaradas, e cada fase registra as que seus módulos já oferecem — acrescentar uma etapa NÃO DEVE exigir mudança na sequência.
- **FR-003**: Cada etapa DEVE falhar fechada: erro de configuração ou de adapter obrigatório impede o boot; pack, MCP ou Assistant inválido fica indisponível com erro explícito, sem impedir os demais.
- **FR-004**: Cada perfil DEVE definir um adapter para cada porta secundária declarada pelos módulos; porta sem adapter DEVE invalidar o perfil antes do boot.
- **FR-005**: O sistema DEVE oferecer pelo menos os perfis "em memória" (Fase 1), "persistente" (Fase 2 em diante) e "teste"; trocar de perfil NÃO DEVE exigir mudança em nenhum módulo.
- **FR-006**: Este módulo DEVE ser o único a instanciar adapters de outros módulos e a injetá-los; os demais módulos recebem seams e adapters prontos.
- **FR-007**: O sistema DEVE injetar no motor (005) os seams já construídos (Pack Hooks, Capability Catalog e Tool Gateway, Model Router, Trace Sink) e os adapters das portas do motor (relógio; checkpoint quando houver retomada — 005 FR-014); a montagem do contexto de cada execução continua sendo do motor.
- **FR-008**: Um único adapter de relógio DEVE atender todos os módulos que declaram porta de tempo, e o perfil de teste DEVE permitir fixar o relógio.
- **FR-009**: Um único adapter de segredos DEVE atender todos os módulos que declaram porta de segredos; valores de segredo NÃO DEVEM aparecer em configuração versionada, logs ou mensagens de erro. *(Refinado pelo [ADR-020](../../docs/adr/ADR-020-segredos-uma-fonte-por-perfil-uma-porta-por-modulo.md): uma **fonte** de segredos por perfil — o ambiente em `memory` e `persistent`, memória em `test` —, com uma porta por módulo e a regra de nomes do módulo — `mcp_secrets` da 007, `llm_secrets` da 006.)*
- **FR-010**: O sistema DEVE oferecer um único comando de linha de comando com os subcomandos contribuídos por cada módulo — no mínimo `serve`, `packs list`, `packs check` e `assistants validate` —, usando a mesma configuração e os mesmos adapters do servidor.
- **FR-011**: Subcomandos de validação DEVEM rodar sem abrir a API e sair com código não zero em caso de erro.
- **FR-012**: O sistema DEVE agregar a saúde de todos os módulos num único resultado, com o estado e o motivo de cada item, consumido pela superfície privada (008) e pela linha de comando. Cada item é crítico ou não: o resultado é `down` se algum item crítico falha (armazenamento persistente inacessível, etapa crítica do boot), `degraded` se só itens não críticos falham (pack em erro, Assistant indisponível, modelo fora do ar, servidor MCP global fora do ar) e `ok` se nenhum falha; só `down` é 503 na superfície privada. A disponibilidade de servidores MCP é verificada só aqui, nunca no boot.
- **FR-013**: No encerramento, o sistema DEVE parar de aceitar requisições, aguardar as execuções em andamento até um prazo configurável e liberar os recursos na ordem inversa do boot.
- **FR-014**: O perfil de teste DEVE subir a plataforma inteira sem nenhum serviço externo (armazenamento, vetores, rede, provider de modelo real), e DEVE fazer parte da distribuição, para que a suíte de qualquer pack possa montar a plataforma de verdade. A montagem DEVE aceitar a troca do adapter de qualquer porta, para que a suíte programe o controller e os servidores MCP; sem troca, o controller simulado responde direto e não há servidor MCP.
- **FR-015**: Todo perfil DEVE autenticar com o verificador real da 003 — nenhum perfil aceita requisição sem credencial. O `persistent` verifica OIDC pelo JWKS do emissor configurado e chaves de API no armazenamento persistente; o `memory`, OIDC quando configurado e uma chave de desenvolvimento lida do ambiente, no grupo de administração; o `test`, um verificador OIDC estático e uma chave semeada, cujas credenciais a distribuição exporta para as suítes.
- **FR-016**: Com a identidade ligada, a composição DEVE montar a 012 numa etapa própria, depois de `adapters` e antes de `assistants` — chave de assinatura, admin inicial, grupo de administração protegido (lido de onde o operador o declara) —, injetar o seam Public Key Set no verificador OIDC da 003 (sem chamada de rede para si mesma), configurar as audiências por superfície a partir dos clientes da 012 e montar o adapter primário do protocolo no mesmo app da API. Identidade ligada com um emissor externo configurado DEVE ser erro de configuração. *(Fase 9, [ADR-030](../../docs/adr/ADR-030-a-plataforma-e-o-provedor-de-identidade.md).)*
- **FR-017**: A configuração DEVE incluir a chave mestra da instalação (ADR-033): obrigatória no perfil `persistent` quando há o que cifrar (identidade ligada ou segredo gravado em runtime); efêmera, com aviso, no `memory`; fixa no `test`. Ela NÃO DEVE aparecer em log, relatório nem erro.
- **FR-018**: A composição DEVE montar as portas novas da Fase 9 em cada perfil — sobreposições da 003; uso, preços e ajustes dos destinos da 009; contas, sessões, chaves e ajustes da 012 — em memória no `memory` e no `test`, em Postgres no `persistent`, com as migrações dos schemas `identity` e `observability` na etapa `adapters`.
- **FR-019**: A composição DEVE montar os destinos do trace (009): o backend principal, o destino de uso e, quando configurado, o Langfuse, e as tarefas do ciclo de vida que os esvaziam; no encerramento e no fim de cada comando da linha de comando, os destinos DEVEM ser esvaziados.
- **FR-020**: A saúde agregada DEVE ganhar os itens não críticos `trace:usage` e `trace:langfuse` (descartes e último erro) e passar a ler os modelos efetivos dos Assistants (com sobreposições), não só os declarados no YAML.
- **FR-021**: A linha de comando DEVE ganhar os subcomandos contribuídos pela 012 (`users`, `identity keys rotate`), e o perfil `test` DEVE semear um admin cujas credenciais a distribuição exporta, ao lado das que já exporta.

### Key Entities

- **Operator Configuration**: packs e sua configuração, Assistants de sistema, perfil de adapters, parâmetros de ambiente e referências de segredo.
- **Adapter Profile**: mapeamento porta → adapter para uma fase ou um ambiente (em memória, persistente, teste).
- **Boot Stage**: etapa da inicialização, com estado (concluída, degradada, falhou) e motivo.
- **Health Report**: estado agregado por módulo e por item, com motivo.
- **Master Key**: chave da instalação da qual cada módulo deriva a subchave com que cifra os próprios segredos de runtime (ADR-033).

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Trocar o perfil de adapters (em memória ↔ persistente) exige zero mudanças em módulos, e a suíte de conformidade de cada módulo passa nos dois perfis.
- **SC-002**: 100% das falhas de configuração são detectadas antes de a API aceitar a primeira requisição.
- **SC-003**: A suíte ponta a ponta do core roda inteira num ambiente sem rede e sem serviços externos.
- **SC-004**: Em 100% dos cenários de falha injetada (pack defeituoso, Assistant inválido, MCP indisponível), o boot conclui e os itens que não dependem da falha atendem.
- **SC-005**: O operador identifica, só pela saída do boot ou pela saúde agregada, qual etapa ou item falhou e por quê, em menos de 1 minuto.
- **SC-006**: Adicionar um adapter novo a uma porta existente exige mudança apenas no módulo dono do adapter e neste módulo.
- **SC-007**: Com a identidade ligada, a suíte ponta a ponta — login, conversa pelo token do chat, administração pelo token da console, sobreposição e relatório de uso — roda inteira sem rede e sem serviços externos.

## Assumptions

- A configuração vem de arquivos montados na imagem (`packs.yaml`, `assistants.yaml`) e de variáveis de ambiente, como no template de instalação (002, ADR-009).
- Processo único na v1; múltiplas réplicas ficam fora de escopo, como os contadores de taxa da 003.
- A técnica de injeção (construtores explícitos ou container) é decidida no plano; a constituição exige apenas que ela fique neste módulo.
- O perfil de teste usa um provider de modelo simulado, fornecido como adapter do contrato `LLMProvider`.
- O perfil persistente cresce por fase: Assistants de usuário e histórico na Fase 2; registry MCP e auditoria na Fase 3; contas, sessões e chaves (012), sobreposições (003), uso, preços e ajustes dos destinos (009) na Fase 9; checkpoint quando houver retomada (ver `docs/roadmap.md`).
