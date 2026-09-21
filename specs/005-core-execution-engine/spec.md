# Feature Specification: Motor de execução (flows)

**Feature Branch**: `005-core-execution-engine`

**Created**: 2026-09-10

**Status**: Draft

**Input**: Tradução de arch-v1 §6 (estado e contexto), §7 (topologias fixas), §8 (nós do core), §9 (custo do controller), §25 (streaming), §28 (checkpoint); ADR-001, ADR-005, ADR-006, ADR-007, ADR-010, ADR-011, ADR-012, ADR-013.

## Module Boundary *(mandatory)*

- **Módulo**: Execution Engine — orquestra uma execução: ordena as chamadas aos serviços do core e aos hooks de pack segundo um flow nomeado, e emite um fluxo de eventos. **Esta spec é desenhada para ser reescrita.**
- **Repositório / distribuição**: `ai-core` → `ai_core/graph/` (seam em `api.py`, políticas em `domain/`, framework de grafo e estado interno em `adapters/`).
- **Consome (seams)**: Turn View e PackRoutine — 001; Pack Hooks — 002; Execution Grant — 003, pela forma que este módulo publica como `Protocol` (satisfeita estruturalmente pelo grant da 003 a partir da Fase 2); Capability Catalog e Tool Gateway — 004; Model Router — 006; Trace Sink — 009.
- **Expõe (seams)**: **Execution Engine** — `run(grant, requisição) → fluxo de eventos` — consumido por 008 e 009; **nomes de flow** (`chat`, `agentic`, `rag_first`) — consumidos como dado por 003 (validação) e por manifests de pack.
- **Depende de infraestrutura (via portas)**: relógio (data de referência) e, a partir da Fase 3, armazenamento de checkpoint de execução. O framework de grafo é adapter interno.
- **Não conhece**: HTTP, autenticação, quais packs existem ou seu domínio, como tools são executadas ou protegidas, quais providers existem.
- **Substituição**: qualquer implementação que honre os dois seams expostos e consuma apenas os seams listados é válida. **Nomes de nós, forma do estado interno e o framework de grafo não são contrato** (ADR-011). Reescrever o grafo troca o adapter de fluxo e preserva as políticas de `domain/` com seus testes (ADR-012). Renomear ou remover um flow é permitido; `assistants validate` (003) aponta as referências pendentes.
- **Insumo técnico**: [design.md](design.md); [ADR-001](../../docs/adr/ADR-001-topologia-fixa.md), [ADR-005](../../docs/adr/ADR-005-execute-tool-unificado.md), [ADR-006](../../docs/adr/ADR-006-rag-first-default-scouting.md), [ADR-007](../../docs/adr/ADR-007-citacao-mecanica.md), [ADR-010](../../docs/adr/ADR-010-temporal-fora.md), [ADR-011](../../docs/adr/ADR-011-contratos-independentes-do-motor.md), [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md), [ADR-013](../../docs/adr/ADR-013-seams-transversais-trace-e-tempo.md).

## Clarifications

### Session 2026-09-21

- Q: O flow `chat` da Fase 1 é linear. O framework de grafo entra já nesta fase ou só quando houver loop? → A: Já nesta fase, como o `design.md` e a tabela de stack da constituição determinam. A parte mais delicada do desenho é traduzir o streaming do framework nos eventos do seam, e é isso que a Fase 1 — cuja razão de ser é a conversa ponta a ponta em streaming (princípio XI) — precisa pôr à prova. A Fase 3 acrescenta o loop ao grafo existente, sem reescrever o adapter nem escrevê-lo duas vezes.
- Q: O seam é `run(grant, requisição)`, mas o Execution Grant pertence à 003, que é Fase 2. Como o motor recebe o grant na Fase 1? → A: O `api.py` deste módulo publica um `Protocol` que descreve apenas o que o motor lê do grant (assistant, flow, packs, política de modelos, limites). Na Fase 2 o Execution Grant concreto da 003 o satisfaz estruturalmente, sem import e sem inverter a direção `005 → 003` do grafo de dependências; o seam é o mesmo nas duas fases. Na Fase 1, quem constrói um objeto que cumpre o Protocol é a composition root (011).
- Q: Uma falha chega ao consumidor como evento ou como exceção? → A: Depende de quando acontece. A validação da requisição — parâmetros, flow inexistente, orçamento — levanta exceção tipada **antes** do primeiro evento, para que a 008 responda 4xx sem abrir o stream e sem custo (princípio VII: 4xx antes de qualquer custo). Depois que o fluxo começou, toda falha vira evento final com erros, porque o consumidor já está lendo um stream e os tokens já emitidos não podem ser perdidos.
- Q: A porta de checkpoint (FR-014) entra na Fase 1? → A: Não. Nesta fase nada retoma execução: o `chat` roda do começo ao fim dentro de uma requisição. Declarar a porta agora seria porta sem consumidor, contra o princípio XIII. Ela entra na Fase 3, junto com o loop, que é quando reter estado entre passos passa a significar alguma coisa.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Conversa direta com resposta em streaming (Priority: P1)

Um usuário envia uma mensagem a um Assistant de flow `chat`. O motor valida a requisição, executa a preparação de contexto dos packs, gera a resposta com o modelo do papel `generation` emitindo tokens à medida que são produzidos, valida a resposta com os validators dos packs e encerra com um evento final.

**Why this priority**: É a Fase 1 — conversa ponta a ponta, em streaming. Streaming não é retrofit (princípio XI).

**Independent Test**: Executar um grant de flow `chat` com o pack de referência; o consumidor recebe eventos de token antes do fim da geração e um evento final com a resposta validada.

**Acceptance Scenarios**:

1. **Given** um grant de flow `chat`, **When** a execução roda com streaming, **Then** o consumidor recebe eventos de token incrementais e, ao final, um evento com resposta, citações e erros.
2. **Given** parâmetros inválidos ou orçamento esgotado, **When** a execução começa, **Then** falha na validação da requisição, antes de qualquer chamada de modelo.
3. **Given** um validator que remove uma citação, **When** a resposta é validada, **Then** o evento final reflete a resposta modificada e registra a remoção.

---

### User Story 2 - Loop agêntico com ação estruturada e limite (Priority: P1)

Num Assistant de flow `agentic`, o motor monta o catálogo e entra num loop: a cada iteração o modelo do papel `controller` emite **uma** ação estruturada — chamar uma tool (nome + argumentos) ou responder. Tools são executadas pelo gateway; resultados acumulam. Ao atingir o limite de iterações do grant, o motor segue para a geração com o que tem e registra o truncamento.

**Why this priority**: Fase 3. É o que habilita MCP e capacidades compostas; o limite é o que impede loop infinito (princípio V).

**Independent Test**: Um controller simulado que sempre pede tool; com limite 3, a execução faz exatamente 3 chamadas, gera a resposta e registra o truncamento.

**Acceptance Scenarios**:

1. **Given** um controller que pede `x.tool` e depois responde, **When** a execução roda, **Then** a tool é executada uma vez, o resultado é acumulado e a resposta é gerada.
2. **Given** limite de 3 iterações e um controller que nunca responde, **When** a execução roda, **Then** há exatamente 3 iterações, a geração acontece e o truncamento é registrado em erros.
3. **Given** um controller que emite ação malformada, **When** isso ocorre, **Then** conta como iteração, é registrado como erro e não interrompe a execução.
4. **Given** um controller que pede tool fora do catálogo, **When** isso ocorre, **Then** o resultado "tool inexistente" volta ao controller e conta como iteração.

---

### User Story 3 - Recuperação determinística antes de qualquer decisão de modelo (Priority: P2)

Num Assistant de flow `rag_first`, o motor recupera e reordena documentos deterministicamente e aplica um **portão de cobertura** determinístico. Com cobertura suficiente, gera a resposta direto (uma única chamada de modelo). Sem cobertura, escala para o loop agêntico.

**Why this priority**: Fase 5. ADR-006: no hardware alvo, o caminho determinístico é mais barato e mais confiável que o loop.

**Independent Test**: Com um retriever de teste, uma consulta com score alto gera resposta com uma única chamada de modelo; uma consulta sem resultados escala para o loop.

**Acceptance Scenarios**:

1. **Given** resultados cujo melhor score está acima do limiar, **When** o portão avalia, **Then** a execução vai direto à geração, sem chamada de controller.
2. **Given** zero resultados após filtros ou melhor score abaixo do limiar, **When** o portão avalia, **Then** a execução escala para o loop agêntico.
3. **Given** um pack que publicou filtros de recuperação na preparação de contexto, **When** a recuperação roda, **Then** os filtros são repassados aos retrievers desse pack sem interpretação pelo motor.

---

### User Story 4 - Resposta validada deterministicamente (Priority: P2)

Antes de encerrar, o motor executa os validators dos packs ativos em sequência, entregando a eles a Turn View que inclui os chunks efetivamente entregues à geração. Validators não chamam modelos.

**Why this priority**: ADR-007 — a verificação de citação precisa saber exatamente o que esteve no contexto da geração.

**Independent Test**: Um validator de teste recebe a Turn View e confirma que `generation_context` contém exatamente os chunks enviados ao modelo.

**Acceptance Scenarios**:

1. **Given** dois packs com validators, **When** a resposta é validada, **Then** os validators rodam na ordem do Assistant e seus resultados se acumulam.
2. **Given** um contexto de geração truncado por limite de tokens, **When** os validators rodam, **Then** `generation_context` contém só os chunks que de fato couberam.

---

### User Story 5 - Seleção de flow por nome (Priority: P2)

O motor executa o flow nomeado no grant. Flows ficam num registro nomeado; um flow desconhecido é erro explícito (e a validação de Assistants o detecta antes).

**Why this priority**: É o que permite reescrever, renomear ou acrescentar flows sem tocar em outros módulos.

**Independent Test**: Registrar um flow de teste novo e executá-lo por nome sem alterar nenhum outro módulo.

**Acceptance Scenarios**:

1. **Given** o registro de flows, **When** consultado, **Then** lista os nomes disponíveis (usados pela validação de Assistants).
2. **Given** um grant com flow inexistente, **When** a execução começa, **Then** falha com erro explícito que nomeia o flow.

---

### User Story 6 - Rotina isolada de pack (Priority: P3)

Quando o catálogo inclui a rotina de um pack, o controller pode invocá-la como uma ação. O motor a executa como passo único, entregando apenas a fatia do pack e os campos declarados, sob limites herdados, e incorpora apenas as saídas declaradas.

**Why this priority**: Escape hatch excepcional (nível 3).

**Independent Test**: Uma rotina de teste que tenta devolver campo não declarado tem essa saída descartada e registrada como erro.

**Acceptance Scenarios**:

1. **Given** uma rotina que declara saída `resultado`, **When** devolve também `outro`, **Then** só `resultado` é incorporado e o excesso é registrado.

---

### Edge Cases

- Cliente desconecta no meio do streaming: a execução é cancelada e os recursos liberados.
- Falha do provider no meio da geração: o fluxo termina com evento de erro explícito.
- Contexto excede o teto de tokens do grant: é reduzido por prioridade (chunks de menor rank primeiro) e a redução é registrada.
- Todas as citações removidas pelos validators: a marcação "não fundamentada" do validator chega ao evento final.
- Execução concorrente de ramos (se um flow futuro paralelizar): dados acumulados não se perdem.
- Hook de pack lança exceção: a execução termina com erro explícito que nomeia o pack (spec 002, FR-011).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O motor DEVE expor uma única operação de execução: recebe Execution Grant e requisição e devolve um fluxo de eventos (token, progresso, final com resposta, citações e erros). Falha anterior ao primeiro evento DEVE ser exceção tipada; falha posterior DEVE ser evento final com erros, preservando o que já foi emitido.
- **FR-002**: O motor DEVE interagir com packs somente via Pack Hooks (002), com tools somente via Capability Catalog e Tool Gateway (004) e com modelos somente via Model Router (006).
- **FR-003**: O motor DEVE oferecer os flows `chat`, `agentic` e `rag_first` num registro nomeado; flows novos são decisão arquitetural registrada em ADR.
- **FR-004**: Packs NÃO DEVEM poder criar, alterar ou inspecionar flows.
- **FR-005**: No flow `agentic`, o controller DEVE emitir exatamente uma ação estruturada por iteração, sob restrição de formato de saída.
- **FR-006**: Toda execução DEVE ter contador de iterações e respeitar o limite do grant; ao atingi-lo, DEVE seguir para a geração e registrar o truncamento.
- **FR-007**: No flow `rag_first`, o portão de cobertura DEVE ser determinístico: melhor score abaixo de limiar configurável ou nenhum resultado após filtros → escalar; caso contrário → gerar.
- **FR-008**: O motor DEVE repassar de forma opaca aos retrievers de um pack os filtros de recuperação que esse pack publicou.
- **FR-009**: Mensagens, chamadas de tool, resultados de tool e erros DEVEM acumular sem perda entre iterações e ramos.
- **FR-010**: O motor DEVE produzir, para os hooks de pack, a Turn View definida em 001, incluindo o conjunto exato de chunks entregues à geração.
- **FR-011**: O contexto enviado a modelos DEVE respeitar o teto de tokens do grant.
- **FR-012**: O motor DEVE emitir eventos de progresso (tool chamada, recuperação em curso) e de token durante a geração.
- **FR-013**: A validação da requisição (parâmetros, modelo, orçamento) DEVE ocorrer antes de qualquer chamada de modelo e antes do primeiro evento, levantando exceção tipada que nomeia o que está errado.
- **FR-014**: O estado de execução DEVE poder ser registrado por checkpoint, separado do histórico de conversa. A porta entra na Fase 3, com o loop: antes disso nenhuma execução é retomada (clarificação de 2026-09-21).
- **FR-015**: A rotina isolada de pack DEVE ser executada como passo único, com entradas e saídas restritas ao declarado e limites herdados.
- **FR-016**: Cada iteração, decisão do controller, chamada de tool e validação DEVE emitir dados de trace pelo Trace Sink (009).
- **FR-017**: O motor DEVE fixar, no início de cada execução, a data de referência — pelo relógio ou, numa execução de avaliação, pelo valor fixado (ADR-013) — e entregá-la em toda Turn View daquela execução.

### Key Entities

- **Execution Request**: mensagens, streaming sim/não, restrições válidas e, só em execução de avaliação, data de referência fixa (ADR-013) — preenchida apenas pelo harness em processo, nunca pela API HTTP (008 FR-012).
- **Execution Event**: token, progresso ou final (resposta, citações, erros, marcações).
- **Execution Grant (forma exigida)**: o que o motor lê do grant — assistant, flow, packs, política de modelos e limites. Publicado por este módulo como `Protocol`; a 003 produz o valor que o satisfaz.
- **Flow**: topologia nomeada.
- **Controller Action**: `{action: tool, name, arguments}` ou `{action: answer}`.
- **Internal State**: privado do motor; não é seam.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Uma reescrita completa da orquestração (topologias novas ou troca do framework de grafo) é concluída alterando apenas esta spec e `ai_core/graph/`; as suítes de conformidade de 002, 004, 006, 008 e dos packs passam sem modificação.
- **SC-002**: 0 execuções ultrapassam o limite de iterações do grant (teste de propriedade com controllers adversariais).
- **SC-003**: No caminho coberto do `rag_first`, 100% das respostas usam exatamente uma chamada de modelo.
- **SC-004**: Em requisições com streaming, o usuário recebe o primeiro sinal (progresso ou token) em até 2 segundos após o envio, no hardware alvo.
- **SC-005**: 0 perdas de dados acumulados em testes de loop com o número máximo de iterações.

## Assumptions

- ADR-011 aceito: o estado interno é privado e os packs recebem a Turn View.
- O contexto de cada execução é montado pelo próprio motor, a partir do grant, com os seams que a composition root (011) injeta no boot.
- Na composição de vários packs em `rag_first`, a recuperação consulta os retrievers de todos os packs do grant e une os resultados por score; se isso se mostrar inadequado, a regra muda aqui sem afetar packs.
- Defaults do hardware alvo: limite de iterações baixo (3–4) e catálogo mínimo em contexto.
- O limiar do portão de cobertura é calibrado na Fase 6 (spec 105), não aqui.
