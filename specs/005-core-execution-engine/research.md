# Research — 005 Execution Engine (Fase 1, US1)

> Decisões pré-aprovadas vêm do [design.md](design.md) e dos ADRs da *Module Boundary*; não são re-pesquisadas.
> As quatro clarificações de 2026-09-21 estão na spec e aparecem aqui como R1, R3, R5 e R7.

## R1 — LangGraph entra já na Fase 1

**Decision**: `adapters/langgraph/` nasce agora, com o grafo do `chat`, o estado com reducers e a tradução do streaming
do framework em `ExecutionEvent`. Dependência `langgraph>=1.2,<2` na distribuição `ai-core`.

**Rationale** (clarificação de 2026-09-21; constituição, "Stack e restrições técnicas"; `design.md`): é a decisão
pré-aprovada, e a Fase 1 existe justamente para provar a conversa ponta a ponta **em streaming** (princípio XI, SC-004).
A parte delicada do desenho é traduzir o streaming do framework nos eventos do seam; adiá-la significaria escrever um
adapter sequencial para jogar fora e descobrir só na Fase 3 se a tradução funciona. Com o grafo montado agora, a Fase 3
acrescenta nós e arestas de loop a uma topologia que já roda.

**Alternatives considered**: adapter sequencial na Fase 1 e LangGraph na Fase 3 (exigiria ADR por divergir da
constituição, e o adapter seria escrito duas vezes); motor próprio em todas as fases (ADR que substituiria a escolha
original de orquestração).

## R2 — O streaming sai por `astream(stream_mode=["custom", "values"])`, não por `astream_events`

**Decision**: os nós escrevem tokens e progresso no canal `custom` (via o escritor de stream do próprio framework) e o
runtime do adapter consome `["custom", "values"]`: `custom` vira `TokenEvent`/`ProgressEvent` ao vivo e o último
`values` vira o `FinalEvent`.

**Rationale**: o `design.md` escreve "`astream_events` → filtrar tokens do `agent_generate`", que pressupõe que a
geração passe por um modelo do próprio framework. Não é o caso: pelo princípio XIII e pelo ADR-008, o modelo vem do
**Model Router** (006), que não é um modelo do LangChain — logo não há evento de LLM para filtrar. O canal `custom` é a
forma suportada de emitir de dentro de um nó, e dá o progresso de graça. Verificado na versão instalada: os pedaços
`custom` chegam intercalados, **antes** de o nó terminar (é o que sustenta SC-004), o último `values` traz o estado
completo, fechar o iterador no meio não levanta, e exceção dentro de nó propaga para quem consome. Isso é interior do
adapter, que o `design.md` declara livre ("tudo abaixo da seção Seams é interno"), então não há divergência a registrar
em ADR.

**Alternatives considered**: embrulhar o `BoundModel` (006) num modelo do LangChain só para `astream_events` enxergá-lo
(poria o framework no caminho do seam de outro módulo, contra o princípio XIII, e acrescentaria uma tradução a mais por
token); acumular tudo e emitir no fim (mata o streaming, que é requisito de fase).

## R3 — O grant chega como `Protocol` publicado por este módulo

**Decision**: `api.py` publica `ExecutionGrant` como `Protocol` com o que o motor lê: `assistant`, `flow`,
`composition` e `models`. A 003 produzirá, na Fase 2, um valor que o satisfaz **estruturalmente** — sem import, sem
registro e sem mudar o seam.

**Rationale** (clarificação de 2026-09-21): o grafo de dependências tem a seta `005 → 003`; definir o value object aqui
inverteria a posse do seam e exigiria ADR. Um `Protocol` expressa exatamente a relação certa: a 005 declara a *forma
exigida*, a 003 fornece o *valor*. Na Fase 1 quem monta o objeto é a composition root (011), e o seam `run(grant,
request)` fica idêntico nas duas fases. O `Protocol` cresce de forma aditiva: `limits` entra na Fase 3 (loop) e o teto
de contexto na Fase 5, quando houver o que limitar.

**Alternatives considered**: dataclass própria da 005 (inverte a posse do seam); antecipar `ai_core/assistants/` só com
o value object (código sem spec planejada, numa fase que não é a dele).

## R4 — O grant carrega a `Composition`, não a lista de nomes de pack

**Decision**: `ExecutionGrant.composition` é a `Composition` da 002, já validada. O motor **não** consome o Pack
Registry.

**Rationale**: a tabela de seams de `specs/README.md` dá o Pack Registry a 003, 004 e 008 — não a 005; a 005 só
consome Pack Hooks. Compor exige validar dependências e disponibilidade, que é resolução de Assistant (003). Receber a
composição pronta mantém a fronteira, evita que o motor conheça o estado de carga dos packs e deixa `run` sem nenhuma
chamada de registro. Na Fase 1, quem compõe é a 011, que consome todos os módulos por definição.

**Alternatives considered**: receber `Sequence[str]` e compor no motor (acrescentaria um seam não declarado à
*Module Boundary*, o que o princípio II proíbe sem ADR).

## R5 — A validação da requisição acontece fora do grafo, em `service.run()`

**Decision**: `run()` é função comum (não geradora): valida requisição, flow e grant de forma síncrona, levanta
`ExecutionRequestInvalid`/`UnknownFlow` se algo estiver errado e só então devolve o iterador de eventos.

**Rationale** (clarificação de 2026-09-21): para a 008 responder 4xx **antes** de abrir o SSE, o erro precisa aparecer
na chamada, não na primeira iteração — se `run` fosse geradora, o corpo só rodaria no primeiro `__anext__` e a 008
teria de espiar o iterador para decidir o código de resposta. Isso tira `validate_request` da lista de nós do
`design.md`, que é interior do adapter e declaradamente livre; a política em si continua pura, em `domain/request.py`,
e sobrevive a qualquer reescrita do grafo (é o que o SC-001 pede).

**Alternatives considered**: nó `validate_request` dentro do grafo (o erro chegaria depois do iterador começar);
validar em duas etapas (duplica a regra e cria o risco de as duas discordarem).

## R6 — Depois do primeiro evento, falha é evento; nunca exceção

**Decision**: o runtime do adapter envolve o consumo do grafo: qualquer exceção vira `FinalEvent` com a resposta
parcial e um erro que nomeia a etapa e a causa. `PackHookError` (002) nomeia o pack; `ModelCallFailed` (006) nomeia
provider e modelo.

**Rationale** (clarificação de 2026-09-21): quem consome já está lendo um stream e, em SSE, uma exceção não tem para
onde ir sem descartar o que já foi entregue. O princípio VII exige falha explícita, não falha silenciosa — e um evento
final com erro nomeado é explícito. Também é o que o edge case da spec já mandava para falha de provider no meio da
geração.

**Alternatives considered**: propagar a exceção (o consumidor perde tokens já emitidos e a 008 teria de fechar o SSE
sem explicação); engolir e devolver resposta vazia (falha silenciosa).

## R7 — Porta `Clock` com data e cronômetro; checkpoint só na Fase 3

**Decision**: `ports.py` declara `Clock` com `now()` (data de referência, ADR-013) e `monotonic()` (duração da
execução no trace). A porta `CheckpointStore` **não** nasce nesta fase.

**Rationale** (clarificação de 2026-09-21): a Fase 1 não retoma execução — o `chat` roda do começo ao fim dentro de uma
requisição —, então a porta de checkpoint não teria consumidor, o que o princípio XIII proíbe. As duas leituras de
tempo, ao contrário, têm uso imediato: `reference_time` vai em toda Turn View e a duração vai no trace. Os outros
módulos declaram portas de tempo próprias (009 com `now()`, 006 com `monotonic()`); um único adapter as satisfaz
estruturalmente, e é a 011 que injeta o mesmo objeto nos três (011 FR-008).

**Alternatives considered**: porta de checkpoint com adapter em memória agora (porta sem consumidor); reusar a porta de
outro módulo (um módulo não importa `ports.py` de outro — são internos).

## R8 — Eventos como dataclasses congeladas no `api.py`

**Decision**: `TokenEvent`, `ProgressEvent` e `FinalEvent`, união em `type ExecutionEvent`. Nenhum tipo do LangGraph,
do LangChain ou de HTTP aparece no `api.py`; `Citation` vem do contrato 001.

**Rationale**: é o que torna o SC-001 verificável — trocar o framework não pode mudar o que a 008 e o harness leem. O
padrão é o mesmo do `api.py` da 009 (dataclasses congeladas que validam na construção), e um contrato de import-linter
impede o framework de vazar.

**Alternatives considered**: dicionários (perde validação e deixa o formato implícito em quem consome).

## R9 — A Turn View é projeção do estado interno

**Decision**: `adapters/langgraph/view.py` projeta `AgentState` → `TurnView` (001). `question` é o conteúdo da última
mensagem de papel `user` da requisição; `reference_time` é fixada uma vez, no início, e repetida em toda Turn View da
execução.

**Rationale**: ADR-011 — o estado interno é privado e o pack só enxerga a Turn View; manter a projeção num arquivo só
é o que permite reescrever o estado sem tocar em pack nenhum. A pergunta ser a última mensagem de usuário é a regra
mínima que serve a `chat`; se algum flow futuro precisar de outra, a regra muda aqui.

**Alternatives considered**: passar o estado ao pack (proibido pelo ADR-011); pedir a pergunta na requisição além das
mensagens (dado duplicado que pode divergir).

## R10 — Quem emite cada dado de trace

**Decision**: o `service.py` emite `ExecutionStarted` (com `reference_time`) antes do primeiro evento e
`ExecutionFinished` ao encerrar, com a duração; o nó de validação emite um `ValidationRun` por validator; falhas emitem
`ExecutionError`. As chamadas de modelo já são emitidas pela 006, e o motor não as duplica.

**Rationale**: FR-016 e o "Seam Notes for Consumers" do plano da 009 descrevem exatamente esta divisão. Emitir do
serviço garante que começo e fim existam mesmo quando o grafo falha no meio; emitir o validator do nó é o único lugar
que conhece o resultado de cada um.

**Alternatives considered**: emitir tudo do serviço (o serviço não vê o resultado de cada validator, só o agregado);
emitir tudo dos nós (execução que falha antes do grafo ficaria sem começo nem fim no trace).

## R11 — Escopo da fase

**Decision**: a Fase 1 entrega a **US1** inteira mais o registro de flows da US5, porque `flows()` faz parte do seam e
a 011 precisa dele no boot. `agentic` (US2), `rag_first` (US3), rotina de pack (US6), checkpoint e corte de contexto
por orçamento ficam para as fases deles. De `domain/`, nascem `request.py` (validação) e `outcome.py` (montagem do
evento final); `gate.py`, `limits.py`, `actions.py` e `budget.py` chegam com `rag_first` e `agentic`.

**Rationale**: `docs/roadmap.md` lista `005 · US1 (chat)` na Fase 1, `005 · US2` na Fase 3 e `005 · US3, US4` na Fase 5.
A US4 (validators com a Turn View correta) é exercida já aqui na sua parte que o `chat` alcança — validators rodam e
recebem `generation_context` —, mas o cenário de truncamento por orçamento é Fase 5, porque depende de chunks.

**Alternatives considered**: entregar também o `agentic` (antecipa 004 e 007, que não existem); entregar o `chat` sem
validators (deixaria a US1 cenário 3 sem cobertura).

## R12 — Contratos de import-linter novos

**Decision**: camadas do módulo (`api.py` não importa o resto; `domain/` não importa portas, service nem adapters;
`service.py` não importa adapters) e, sobretudo, `langgraph`/`langchain_core` proibidos em `api.py`, `domain/`,
`ports.py` e `service.py` — e proibidos em qualquer módulo que não seja `ai_core.graph.adapters`.

**Rationale**: é o que torna executável a promessa do ADR-011 e do SC-001: o framework de grafo não é contrato. Segue o
padrão já aplicado ao SDK de modelo na 006 (R13 daquela spec).

**Alternatives considered**: confiar em revisão (a regra mais importante do módulo seria a única não verificada).

## R13 — Os testes montam o caminho real

**Decision**: a suíte de conformidade do seam roda o grafo de verdade, com o Pack Runtime real (002) carregando o
`ai-generic` (010) e o provider simulado da 006. Só o modelo é simulado.

**Rationale**: é o "Independent Test" que a própria US1 descreve ("com o pack de referência"), e é o primeiro ponto do
projeto em que quatro módulos se encontram — o valor do teste está exatamente aí. Simular o modelo é o que mantém a
suíte sem rede e determinística; simular o resto esconderia justamente o que esta fase precisa provar.

**Alternatives considered**: duplos para packs e hooks (testaria o motor contra a ideia que ele faz dos outros módulos,
não contra eles).
