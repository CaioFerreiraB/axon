# Feature Specification: Bootstrap e composition root do núcleo

**Feature Branch**: `011-core-bootstrap`

**Created**: 2026-09-14

**Status**: Draft

**Input**: ADR-012 (composition root), ADR-013 (relógio único, Trace Sink); [relatório de estilo arquitetural](../../docs/relatorio-estilo-arquitetural.md), lacuna G6; arch-v1 §13 (boot, CLI) e §14 (deployment).

## Module Boundary *(mandatory)*

- **Módulo**: Bootstrap — composition root do `ai-core`: carrega a configuração do operador, escolhe e instancia o adapter de cada porta, injeta seams e adapters nos módulos, conduz a ordem de boot e oferece os pontos de entrada do processo.
- **Repositório / distribuição**: `ai-core` → `packages/core/src/ai_core/bootstrap/`; comando `ai-core` (raiz).
- **Consome (seams)**: o `api.py` de todos os módulos do core (002–009) e os `adapters/` deles. É o único módulo autorizado a importar adapters de outros módulos (princípio XIII).
- **Expõe (seams)**: nenhum seam Python. Expõe os pontos de entrada do processo — servidor e raiz da linha de comando `ai-core`, onde cada módulo contribui seus subcomandos —, consumidos pelo operador, pelo template de instalação (002) e pela CI.
- **Depende de infraestrutura (via portas)**: configuração do operador (arquivos e ambiente). Indiretamente, toda a infraestrutura dos módulos, cujos adapters instancia.
- **Não conhece**: regras de negócio de qualquer módulo (grant, catálogo, flows, políticas de tool), o estado interno do motor e o contexto de execução (005), qualquer domínio.
- **Substituição**: preservar a ordem de boot com falha fechada, os perfis de adapters e os comandos da linha de comando; a técnica de injeção é livre.
- **Insumo técnico**: [design.md](design.md); [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md), [ADR-013](../../docs/adr/ADR-013-seams-transversais-trace-e-tempo.md), [ADR-009](../../docs/adr/ADR-009-deploy-docker-build-arg.md).

## Clarifications

### Session 2026-09-21

- Q: A ordem de boot tem sete etapas, mas duas pertencem a módulos que ainda não existem. Como o boot lida com isso? → A: Cada etapa é declarada — nome, ação e política de falha (interrompe o boot ou degrada e segue) — e a sequência executa a lista registrada na fase. Na Fase 1 registram-se configuração, adapters, packs, motor e API; registry MCP e validação de Assistants entram quando seus módulos existirem, sem tocar no código da sequência. É o que torna FR-002 e FR-003 verificáveis com etapas de teste, sem subir a plataforma inteira.
- Q: A linha de comando completa é a US4 (Fase 2); o que a Fase 1 entrega como ponto de entrada? → A: Um `ai-core serve` mínimo, que conduz o boot e serve a aplicação com um servidor ASGI. É o que faz a US1 existir de fato — sem ele, "o operador inicia o serviço" não teria como acontecer — e o que permite conversar com a plataforma por HTTP fora da suíte. Os subcomandos contribuídos por cada módulo continuam na Fase 2.
- Q: A API resolve `<assistant>/<modelo>` num grant, e até a 003 existir quem monta isso é esta spec. De onde vem a configuração? → A: De um `assistants.yaml` mínimo — nome do Assistant → packs, flow e modelo por papel —, como o `design.md` já previa ao dar YAML ao armazenamento de Assistants de sistema. A composition root o lê e monta o resolvedor de grant; quando a 003 chegar, ela assume o arquivo e esta spec passa a consumir o seam dela. O formato nasce aqui e é herdado, em vez de inventado duas vezes.
- Q: O perfil de teste que sobe a plataforma inteira em memória é código distribuído ou das suítes? → A: Da distribuição. O perfil vive no próprio módulo, e qualquer suíte monta a plataforma com uma chamada — inclusive a de um pack externo, que passa a poder testar seu pack contra a plataforma de verdade. É o que a SC-003 mede, e evita que cada spec remonte tudo à mão.

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

O operador escolhe, por configuração, qual adapter atende cada porta. Na Fase 1, tudo roda em memória; da Fase 2 em diante, Assistants de usuário e histórico passam a armazenamento persistente; na Fase 3, registry MCP, auditoria e checkpoint também. Trocar de perfil não altera nenhum módulo.

**Why this priority**: ADR-012 — as trocas previstas no roadmap são trocas de adapter.

**Independent Test**: Rodar a mesma suíte ponta a ponta com o perfil em memória e com o perfil persistente; os resultados são os mesmos e nenhum módulo muda.

**Acceptance Scenarios**:

1. **Given** o perfil em memória, **When** o serviço sobe, **Then** nenhum armazenamento externo é exigido.
2. **Given** o perfil persistente com o armazenamento indisponível, **When** o serviço sobe, **Then** o boot falha com erro que nomeia a porta e o adapter.
3. **Given** um perfil em que uma porta declarada por algum módulo não tem adapter, **When** a configuração é validada, **Then** o perfil é rejeitado antes do boot, com erro que nomeia a porta.
4. **Given** a checagem de fronteiras de import do CI, **When** ela roda, **Then** nenhum módulo além deste importa adapters de outro módulo.

---

### User Story 3 - Plataforma inteira em memória para testes ponta a ponta (Priority: P1)

A suíte ponta a ponta sobe a plataforma inteira com adapters em memória e um provider de modelo simulado: sem banco, sem vetores, sem rede.

**Why this priority**: Princípio XIII (toda porta tem adapter em memória) e 008 SC-002 (suíte ponta a ponta via HTTP). É o que permite testar a plataforma desde a Fase 1.

**Independent Test**: Num ambiente sem rede nem serviços externos, a suíte ponta a ponta do core passa.

**Acceptance Scenarios**:

1. **Given** um ambiente sem serviços externos, **When** a suíte sobe a plataforma no perfil de teste, **Then** uma conversa ponta a ponta com o pack de referência funciona pela API.
2. **Given** o perfil de teste com o relógio fixado, **When** várias execuções rodam, **Then** todas recebem a mesma data de referência (ADR-013).

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

1. **Given** o provider local fora do ar, **When** a saúde é consultada, **Then** o resultado nomeia o provider e o modelo indisponíveis, e os demais itens aparecem saudáveis.
2. **Given** todos os itens disponíveis, **When** a saúde é consultada, **Then** o resultado é saudável.

---

### Edge Cases

- Configuração de pack que referencia pack não instalado: tratada pela 002 (`error: não instalado`); o boot continua.
- Dois adapters para a mesma porta no mesmo perfil: configuração inválida; o boot não começa.
- Armazenamento do registry MCP indisponível (a partir da Fase 3): Assistants que usam MCP ficam indisponíveis com erro explícito; os demais atendem.
- Sinal de parada durante o boot: as etapas já concluídas são desfeitas na ordem inversa.
- Referência de segredo ausente no ambiente: o adapter que precisa dela falha na inicialização com erro que nomeia a referência, nunca o valor.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE carregar a configuração do operador (packs, Assistants de sistema, perfil de adapters, parâmetros de ambiente, referências de segredo) e validá-la antes de qualquer outra etapa, rejeitando-a com erro que nomeia o campo.
- **FR-002**: O sistema DEVE conduzir o boot na ordem configuração → adapters → packs (002) → registry MCP (007) → motor (005) → validação de Assistants (003, que usa os nomes de flow do motor) → API (008); a API só aceita requisições depois da última etapa. As etapas são declaradas, e cada fase registra as que seus módulos já oferecem — acrescentar uma etapa NÃO DEVE exigir mudança na sequência.
- **FR-003**: Cada etapa DEVE falhar fechada: erro de configuração ou de adapter obrigatório impede o boot; pack, MCP ou Assistant inválido fica indisponível com erro explícito, sem impedir os demais.
- **FR-004**: Cada perfil DEVE definir um adapter para cada porta secundária declarada pelos módulos; porta sem adapter DEVE invalidar o perfil antes do boot.
- **FR-005**: O sistema DEVE oferecer pelo menos os perfis "em memória" (Fase 1), "persistente" (Fase 2 em diante) e "teste"; trocar de perfil NÃO DEVE exigir mudança em nenhum módulo.
- **FR-006**: Este módulo DEVE ser o único a instanciar adapters de outros módulos e a injetá-los; os demais módulos recebem seams e adapters prontos.
- **FR-007**: O sistema DEVE injetar no motor (005) os seams já construídos (Pack Hooks, Capability Catalog e Tool Gateway, Model Router, Trace Sink) e os adapters das portas do motor (checkpoint, relógio); a montagem do contexto de cada execução continua sendo do motor.
- **FR-008**: Um único adapter de relógio DEVE atender todos os módulos que declaram porta de tempo, e o perfil de teste DEVE permitir fixar o relógio.
- **FR-009**: Um único adapter de segredos DEVE atender todos os módulos que declaram porta de segredos; valores de segredo NÃO DEVEM aparecer em configuração versionada, logs ou mensagens de erro.
- **FR-010**: O sistema DEVE oferecer um único comando de linha de comando com os subcomandos contribuídos por cada módulo — no mínimo `serve`, `packs list`, `packs check` e `assistants validate` —, usando a mesma configuração e os mesmos adapters do servidor.
- **FR-011**: Subcomandos de validação DEVEM rodar sem abrir a API e sair com código não zero em caso de erro.
- **FR-012**: O sistema DEVE agregar a saúde de todos os módulos num único resultado, com o estado e o motivo de cada item, consumido pela superfície privada (008) e pela linha de comando.
- **FR-013**: No encerramento, o sistema DEVE parar de aceitar requisições, aguardar as execuções em andamento até um prazo configurável e liberar os recursos na ordem inversa do boot.
- **FR-014**: O perfil de teste DEVE subir a plataforma inteira sem nenhum serviço externo (armazenamento, vetores, rede, provider de modelo real), e DEVE fazer parte da distribuição, para que a suíte de qualquer pack possa montar a plataforma de verdade.

### Key Entities

- **Operator Configuration**: packs e sua configuração, Assistants de sistema, perfil de adapters, parâmetros de ambiente e referências de segredo.
- **Adapter Profile**: mapeamento porta → adapter para uma fase ou um ambiente (em memória, persistente, teste).
- **Boot Stage**: etapa da inicialização, com estado (concluída, degradada, falhou) e motivo.
- **Health Report**: estado agregado por módulo e por item, com motivo.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Trocar o perfil de adapters (em memória ↔ persistente) exige zero mudanças em módulos, e a suíte de conformidade de cada módulo passa nos dois perfis.
- **SC-002**: 100% das falhas de configuração são detectadas antes de a API aceitar a primeira requisição.
- **SC-003**: A suíte ponta a ponta do core roda inteira num ambiente sem rede e sem serviços externos.
- **SC-004**: Em 100% dos cenários de falha injetada (pack defeituoso, Assistant inválido, MCP indisponível), o boot conclui e os itens que não dependem da falha atendem.
- **SC-005**: O operador identifica, só pela saída do boot ou pela saúde agregada, qual etapa ou item falhou e por quê, em menos de 1 minuto.
- **SC-006**: Adicionar um adapter novo a uma porta existente exige mudança apenas no módulo dono do adapter e neste módulo.

## Assumptions

- A configuração vem de arquivos montados na imagem (`packs.yaml`, `assistants.yaml`) e de variáveis de ambiente, como no template de instalação (002, ADR-009).
- Processo único na v1; múltiplas réplicas ficam fora de escopo, como os contadores de taxa da 003.
- A técnica de injeção (construtores explícitos ou container) é decidida no plano; a constituição exige apenas que ela fique neste módulo.
- O perfil de teste usa um provider de modelo simulado, fornecido como adapter do contrato `LLMProvider`.
- O perfil persistente cresce por fase: Assistants de usuário e histórico na Fase 2; registry MCP, auditoria e checkpoint na Fase 3 (ver `docs/roadmap.md`).
