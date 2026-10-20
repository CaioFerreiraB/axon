# Feature Specification: Trace por requisição e harness de avaliação

**Feature Branch**: `009-core-observability-evaluation`

**Created**: 2026-09-10

**Status**: Draft

**Input**: Tradução de arch-v1 §29 (trace, harness, métricas), §27 (benchmark de modelos), §31 Fase 6; ADR-007. Fase 9 (2026-10-13): uso e custo por modelo e por dia, Langfuse e captura opcional de conteúdo — ADR-033, ADR-034.

## Module Boundary *(mandatory)*

- **Módulo**: Observability & Evaluation — trace estruturado de cada execução e harness genérico que roda conjuntos dourados fornecidos por packs.
- **Repositório / distribuição**: `axon-ai` → `axon_ai/observability/` (Trace Sink e consulta de trace) e `axon_ai/eval/` (harness).
- **Consome (seams)**: Execution Engine (eventos) — 005, pelo harness; `Chunk` — 001.
- **Expõe (seams)**: **Trace Sink** (porta de emissão de dados de trace por requisição) — consumido por 004, 005 e 006; **Trace** (consulta por identificador de requisição) — consumido por 008 e pelo operador; **Eval Harness** com o **formato de conjunto dourado** — consumidos pelo CI e por packs (ex.: 105); **Usage Report** (uso e custo por dia, modelo e Assistant), **Price Book** (preços com vigência) e **Trace Destinations** (Langfuse, captura de conteúdo, estado dos destinos) — consumidos pela 008, superfície de administração (Fase 9).
- **Depende de infraestrutura (via portas)**: backend de trace (exporter), destinos adicionais do trace (projeção de uso, Langfuse — rede), armazenamento de uso, preços e ajustes dos destinos, cifra com a chave mestra da instalação, segredos de instalação, relógio, armazenamento de linhas de base, juiz LLM (só offline).
- **Não conhece**: domínio (métricas específicas de domínio são fornecidas pelo pack), flows internos (lê apenas eventos e dados de trace), quem emite dados de trace além do que chega pelo Trace Sink.
- **Substituição**: preservar o Trace Sink, o formato do conjunto dourado, o formato de relatório e os seams de uso, preços e destinos; o backend de trace e os destinos podem ser trocados (são adapters).
- **Insumo técnico**: [design.md](design.md); [ADR-007](../../docs/adr/ADR-007-citacao-mecanica.md), [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md), [ADR-013](../../docs/adr/ADR-013-seams-transversais-trace-e-tempo.md), [ADR-017](../../docs/adr/ADR-017-trace-sink-cresce-por-eventos-aditivos.md), [ADR-033](../../docs/adr/ADR-033-segredos-de-runtime-cifrados-com-a-chave-mestra.md), [ADR-034](../../docs/adr/ADR-034-trace-com-destinos-e-conteudo-opcional.md).

## Clarifications

### Session 2026-09-17

- Q: O seam Trace Sink é um contrato próprio do projeto ou a API do OpenTelemetry usada diretamente como porta? → A: Contrato próprio, com value objects do projeto — quem emite (004, 005, 006) importa apenas o seam deste módulo e nenhuma biblioteca de observabilidade. OpenTelemetry, se for adotado, entra como adapter do exporter, que é onde o backend pode ser trocado. Resolve a candidata em aberto do `design.md` e do ADR-013, preservando a semântica do seam.
- Q: Como os dados chegam ao Trace Sink? → A: Um único método de emissão que recebe um evento tipado; cada tipo de dado de trace é um value object publicado pelo módulo. Instrumentar um módulo novo é acrescentar um tipo de evento, sem alterar o seam — o que evita um ADR por fase, já que os emissores chegam em fases diferentes.
- Q: Quais tipos de evento existem na Fase 1, se tools, iterações do controller e recuperação só chegam nas Fases 3 e 5? → A: Apenas os dos módulos que existem na fase: execução iniciada e concluída (assistant, packs ativos, flow, desfecho), chamada de modelo (provider, modelo, papel, tokens, latência), execução de validator e erro. Os demais campos da US1 entram como tipos novos nas fases dos módulos que os produzem. Emitir é responsabilidade de quem produz o dado (005, 006 e, depois, 004); esta spec entrega o seam, os tipos, o exporter e a consulta.
- Q: Como o módulo garante que credencial nunca aparece no trace? → A: Em duas camadas — os tipos de evento não têm campo onde um segredo caiba, e o que é texto livre (hoje, a mensagem de erro) passa por redação antes de sair do processo: nomes de chave conhecidos em qualquer mapeamento e padrões de credencial no texto, substituídos por marcador. A regra é pura e testável sem backend.
- Q: Os eventos vão para o backend um a um, na hora, ou acumulados por requisição e gravados no fim? → A: Um a um, na hora, um evento por registro — o trace sobrevive a queda, travamento ou encerramento forçado no meio da execução, que é quando ele mais importa, e uma execução longa é observável enquanto corre. A consulta por identificador de requisição agrega os registros na leitura.

### Session 2026-10-13

- Q: Como o harness, que executa cada item pelo Execution Engine e só recebe tokens, progresso e a resposta final, sabe quais trechos foram recuperados, reordenados e entregues à geração, para calcular recall@k, MRR e o ganho do rerank? → A: Pelo trace da própria requisição: a 005 emite um evento novo e aditivo (ADR-017) com os identificadores e scores dos trechos candidatos, reordenados e entregues à geração — sem texto —, e o harness o lê pela consulta de trace deste módulo. Nenhum seam muda.
- Q: Em que nível o conjunto dourado declara a evidência esperada (documentos a recuperar e citações esperadas)? → A: Por documento — o `document` do trecho (001) —, com seção opcional (a `section` do trecho), casados por igualdade normalizada (caixa, espaços e acentos); o identificador de trecho é aceito como alternativa opcional, para evidência estável. Assim o conjunto sobrevive a mudanças de chunking, que é o que ele precisa medir.
- Q: Como um pack entrega ao harness as métricas de domínio dele (ex.: taxa de documento vigente, da 105) sem importar o core? → A: Por um protocolo novo e aditivo no contrato 001 — uma métrica com nome que calcula, por item, um valor sobre uma observação (o item esperado, a resposta, as citações e os trechos com proveniência) — e um hook opcional do pack que as declara; o harness as calcula e as põe no mesmo relatório, sob a mesma linha de base e tolerância das métricas do core. Contratos `0.1.2`, com ADR; nenhum pack existente precisa implementar.
- Q: As métricas de geração julgadas por modelo (fidelidade ao trecho e cobertura da resposta de referência) entram já nesta fase? → A: Sim. O operador escolhe o modelo juiz na configuração da rodada — fora de qualquer Assistant, roteado pelo Model Router —; cada julgamento é repetido 3 vezes e reportado com média e variância; nunca barra o CI sozinho; sem juiz configurado, essas métricas aparecem como ausentes.
- Q: No benchmark de modelos, como entram RAM e CPU, que são do servidor do modelo e não do processo do harness? → A: O harness mede o que observa — tempo até o primeiro token, tokens/s, latência, confiabilidade de tool calling (ações válidas do controller) e fidelidade —; RAM e CPU entram como anotação do operador no relatório (campo livre por modelo), sem medição automática.
- Q: De onde o juiz tira o texto dos trechos entregues à geração, que precisa ler para julgar a fidelidade, se o evento de recuperação foi decidido sem texto? → A: O evento de recuperação passa a levar o texto **só dos trechos entregues** à geração — o que o modelo viu —, cortado em 2.000 caracteres e redigido como todo texto livre do trace; candidatos e reordenados continuam sem texto. Revê em parte a resposta da primeira pergunta desta sessão (decidido durante a implementação).
- Q: As rodadas de avaliação (`axon eval run`, inclusive o modelo juiz) entram no uso e custo? → A: Entram, marcadas com a origem "avaliação"; o relatório mostra só a produção por padrão e permite incluir a avaliação ou ver só ela.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Entender por que uma execução se comportou assim (Priority: P1)

Cada requisição produz um trace com: Assistant resolvido, packs ativos, tools em catálogo, cada iteração do controller e sua ação, cada tool executada com latência e status, chunks recuperados com score, tokens por papel, validators e seus resultados, erros. Cada campo aparece a partir da fase do módulo que o produz; na Fase 1, o trace cobre execução iniciada e concluída, chamada de modelo, execução de validator e erro (FR-001).

**Why this priority**: Sem trace, depurar por que o controller escolheu determinada tool é adivinhação. Útil desde a Fase 1.

**Independent Test**: Na Fase 1, executar uma conversa e responder, só pelo trace, qual modelo atendeu cada papel, quantos tokens custou, quais packs estavam ativos e como a execução terminou. A partir da Fase 3, a mesma pergunta sobre uma requisição agêntica: qual tool foi chamada em cada iteração e por que o loop terminou.

**Acceptance Scenarios**:

1. **Given** uma execução concluída, **When** o operador consulta o trace pelo identificador da requisição, **Then** vê os campos produzidos pelos módulos existentes, na ordem em que aconteceram.
2. **Given** um dado de trace que carrega credencial — mensagem de erro de provider na Fase 1, argumentos de tool a partir da Fase 3 —, **When** registrado, **Then** a credencial não aparece no trace, e sim um marcador de redação.
3. **Given** uma execução interrompida no meio (queda ou encerramento forçado), **When** o trace é consultado, **Then** os eventos já emitidos estão lá.

---

### User Story 2 - Medir a qualidade com um conjunto dourado (Priority: P1)

O harness roda um conjunto dourado fornecido por um pack — perguntas, documentos que devem ser recuperados, resposta de referência e citações esperadas — contra um Assistant, e calcula métricas de recuperação, rerank, geração, citação e operação.

**Why this priority**: Fase 6, e pré-requisito de qualquer calibração (princípio X). Sem harness não há empiria.

**Independent Test**: Rodar um conjunto dourado mínimo de teste contra o pack de referência e obter um relatório com todas as métricas.

**Acceptance Scenarios**:

1. **Given** um conjunto dourado, **When** o harness roda, **Then** produz recall@k, MRR, ganho de rerank, fidelidade, cobertura, taxa de citação resolvível, taxa de citação inventada, latência p50/p95 e tokens por resposta.
2. **Given** um pack que fornece métricas de domínio adicionais, **When** o harness roda, **Then** elas aparecem no mesmo relatório.

---

### User Story 3 - Barrar regressões no CI (Priority: P2)

O harness roda em CI a cada mudança de chunking, prompt, retriever ou modelo, compara com a linha de base registrada e falha quando uma métrica determinística regride além da tolerância.

**Why this priority**: É o que responde se uma mudança melhorou ou piorou — de outro modo impossível num sistema RAG.

**Independent Test**: Introduzir uma regressão proposital no retriever de teste; o CI falha apontando a métrica.

**Acceptance Scenarios**:

1. **Given** uma linha de base, **When** uma mudança derruba o recall@k além da tolerância, **Then** o CI falha e mostra o delta.
2. **Given** métricas avaliadas por LLM (fidelidade, cobertura), **When** variam, **Then** são reportadas com média e variância de 3 julgamentos e não bloqueiam sozinhas.

---

### User Story 4 - Comparar modelos com as métricas que importam (Priority: P3)

O mesmo harness compara modelos candidatos em tokens/s, tempo até o primeiro token, latência, qualidade em português (a cobertura da resposta de referência, julgada, num conjunto dourado em português), confiabilidade de tool calling e fidelidade em RAG — o que ele observa da própria execução. RAM e CPU, que são do servidor do modelo, entram como anotação do operador no relatório.

**Why this priority**: As duas últimas métricas são as decisivas e não aparecem em benchmarks padrão.

**Independent Test**: Rodar o benchmark com dois modelos locais e obter relatório comparativo.

**Acceptance Scenarios**:

1. **Given** dois modelos, **When** o benchmark roda, **Then** o relatório compara lado a lado as métricas medidas e as anotações de recursos que o operador forneceu.

---

### User Story 5 - Ver uso e custo por modelo e por dia (Priority: P2)

O operador consulta, para um período, quantas requisições a plataforma atendeu, quantas chamadas de modelo fez, quantos
tokens de entrada e de saída consumiu e quanto isso custou, por dia e por modelo ou por Assistant. O custo vem de uma
tabela de preços que ele mantém (USD por milhão de tokens de entrada e de saída, com data de início) e é calculado na
consulta: um preço lançado depois corrige o histórico ([ADR-034](../../docs/adr/ADR-034-trace-com-destinos-e-conteudo-opcional.md)).

**Why this priority**: É o dashboard que o mantenedor pediu para a console (013); a consulta é deste módulo porque o dado
nasce do trace.

**Independent Test**: Emitir, pelo Trace Sink, execuções com chamadas em dois modelos em dois dias, um deles com preço;
consultar o relatório e conferir totais, séries diárias, custo e a marca "sem preço".

**Acceptance Scenarios**:

1. **Given** chamadas de modelo em dois dias, **When** o operador consulta por dia e por modelo, **Then** recebe, por dia
   e por modelo, requisições, chamadas, tokens de entrada e de saída e custo.
2. **Given** um modelo sem preço, **When** o relatório é consultado, **Then** o custo dele é ausente, marcado "sem
   preço", e o total do período avisa que está incompleto.
3. **Given** um preço cadastrado com data de início no passado, **When** o relatório é consultado de novo, **Then** o
   custo do período passa a usar esse preço desde aquela data.
4. **Given** uma chamada às 23h30 em Brasília, **When** o relatório usa o fuso de Brasília, **Then** ela conta no dia
   local, não no dia UTC.
5. **Given** o destino de uso indisponível, **When** execuções acontecem, **Then** nenhuma é atrasada nem falha; os
   registros perdidos são contados e aparecem na saúde.
6. **Given** uma rodada de avaliação no período, **When** o operador consulta sem filtro, **Then** o relatório mostra só
   a produção; com o filtro de avaliação, mostra as chamadas da rodada e do juiz.

---

### User Story 6 - Enviar traces ao Langfuse (Priority: P2)

O operador liga o envio ao Langfuse com endereço e chaves — pela administração, quando a instalação não os define, ou
pela instalação, que então prevalece ([ADR-033](../../docs/adr/ADR-033-segredos-de-runtime-cifrados-com-a-chave-mestra.md)). Cada execução vira um trace no
Langfuse, com as chamadas de modelo (modelo, tokens, tempos), as chamadas de tool, as decisões do controller e do portão
e os erros.

**Why this priority**: Pedido do mantenedor; o trace atual só se lê por arquivo ou pela consulta por requisição.

**Independent Test**: Contra um Langfuse simulado, ligar o envio e executar uma conversa `agentic` com uma tool; o
simulado recebe um trace com a geração, a tool e a decisão, sem nenhum texto de prompt ou resposta.

**Acceptance Scenarios**:

1. **Given** o envio ligado, **When** uma execução termina, **Then** o Langfuse recebe um trace com as gerações e spans
   correspondentes, em até alguns segundos.
2. **Given** o Langfuse fora do ar ou lento, **When** execuções acontecem, **Then** nenhuma é atrasada nem falha; os
   envios perdidos são contados e o estado do destino mostra o último erro.
3. **Given** a instalação define endereço e chaves, **When** a administração tenta alterá-los, **Then** é recusado, e a
   consulta dos ajustes mostra a origem "instalação".
4. **Given** chaves gravadas pela administração, **When** os ajustes são consultados, **Then** a chave secreta aparece
   só como existente, nunca o valor.
5. **Given** um pedido de "testar conexão", **When** o Langfuse responde, **Then** o resultado diz se as credenciais
   foram aceitas.

---

### User Story 7 - Captura opcional de prompt e resposta (Priority: P3)

O operador pode ligar a captura do texto de prompt e resposta das chamadas de modelo. Desligada por padrão. Ligada, o
texto vai só para destinos que aceitam conteúdo — hoje, o Langfuse —, redigido e cortado; o trace consultável por
requisição e o arquivo do operador nunca o recebem.

**Why this priority**: Dá ao Langfuse o valor pleno de depuração, com risco de privacidade que exige opção explícita.

**Independent Test**: Com a captura desligada, nenhum destino recebe texto; ligada, só o Langfuse simulado recebe, e o
backend principal continua sem texto.

**Acceptance Scenarios**:

1. **Given** a captura desligada, **When** uma execução acontece, **Then** nenhum destino recebe o texto de prompt ou de
   resposta.
2. **Given** a captura ligada, **When** uma execução acontece, **Then** o Langfuse recebe as mensagens e a saída de cada
   chamada, redigidas e cortadas; o backend principal não recebe nada disso.

---

### Edge Cases

- Item do conjunto dourado que referencia documento fora do corpus: não é falha do sistema. O core não conhece o corpus — conferir o conjunto contra o catálogo é do pack (105) —, e o harness aponta, como aviso no item, a evidência esperada que não aparece entre os candidatos de nenhum item da rodada ("evidência não vista"); item com formato inválido é sinalizado como inválido e não roda.
- Juiz LLM indisponível: métricas determinísticas continuam; as de juiz ficam marcadas como ausentes.
- Trace de execução com conteúdo sensível do usuário: retenção limitada e configurável; credenciais nunca registradas.
- Chamada de modelo sem tokens informados pelo provider: entra no uso como chamada, com tokens ausentes ("sem tokens"), e não soma custo.
- Chamada de modelo fora de uma execução (por exemplo, o juiz do harness): entra no uso sem Assistant, com a origem do processo (`avaliação`, no caso do juiz); o relatório a mostra como "fora de Assistant".
- Dois preços para o mesmo modelo: vale, em cada dia, o de data de início mais recente que não seja posterior ao dia.
- Langfuse reconfigurado no meio de execuções: os registros já enfileirados vão ao destino antigo; os seguintes, ao novo.
- Chave mestra ausente no perfil persistente: gravar a chave secreta do Langfuse é recusado com a explicação; o resto dos ajustes grava.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Cada requisição DEVE gerar um trace acessível pelo identificador da requisição, com os campos da US1 que os módulos existentes na fase produzem — na Fase 1: execução iniciada e concluída (assistant, packs ativos, flow, desfecho), chamada de modelo (provider, modelo, papel, tokens, latência), execução de validator e erro.
- **FR-002**: O trace NÃO DEVE conter credenciais: nenhum tipo de evento DEVE ter campo destinado a segredo, e todo texto livre e todo mapeamento de atributos DEVEM passar por redação de nomes de chave conhecidos e de padrões de credencial antes de sair do processo.
- **FR-003**: O harness DEVE definir um formato de conjunto dourado com: pergunta, documentos esperados, resposta de referência, citações esperadas e data de referência do item (ADR-013), para que itens datados sejam reproduzíveis. Documentos e citações esperados são evidências declaradas **por documento** (o `document` do trecho, contrato 001), com **seção** opcional (a `section` do trecho) e, como alternativa opcional, o identificador do trecho; o casamento é por igualdade normalizada (caixa, espaços e acentos), para o conjunto sobreviver a mudanças de chunking.
- **FR-004**: O harness DEVE calcular as métricas das camadas recuperação, rerank, geração, citação e operação (tabela no design). As de recuperação e rerank saem do trace da própria requisição — o evento de recuperação que a 005 emite (por trecho candidato, reordenado e entregue: identificador, score e a proveniência do contrato 001 — documento, versão, status, seção e página —; o texto só dos entregues, cortado e redigido, para o juiz julgar a fidelidade; aditivo pelo ADR-017) —, e as de operação, dos eventos de chamada de modelo e de execução; o harness não depende de nenhum internal do motor.
- **FR-005**: O harness DEVE aceitar métricas de domínio fornecidas por packs pelo contrato 001: um protocolo aditivo de métrica (nome e valor por item, calculado sobre uma observação — item esperado, resposta, citações e trechos com proveniência) e um hook opcional do pack que as declara (contratos `0.1.2`, ADR). Elas entram no mesmo relatório e sob a mesma linha de base e tolerância das métricas do core (FR-007); um pack sem o hook não muda.
- **FR-006**: Julgamento por LLM PODE ser usado aqui (offline) e NÃO DEVE ser usado no caminho da requisição. Fidelidade ao trecho e cobertura da resposta de referência são julgadas por um modelo juiz escolhido pelo operador na configuração da rodada (fora de qualquer Assistant, roteado pelo Model Router da 006); cada julgamento é repetido 3 vezes e reportado com média e variância; sem juiz configurado, essas métricas aparecem como ausentes, e as determinísticas seguem.
- **FR-007**: O harness DEVE registrar linhas de base e comparar execuções, com tolerância configurável por métrica.
- **FR-008**: O harness DEVE poder rodar em CI com saída que falha o pipeline em regressão de métrica determinística.
- **FR-009**: O harness DEVE suportar benchmark comparativo de modelos, medindo o que observa da execução — tempo até o primeiro token, tokens/s, latência, confiabilidade de tool calling (ações válidas do controller) e fidelidade —; RAM e CPU do servidor do modelo NÃO são medidas, e entram como anotação do operador por modelo no relatório.
- **FR-010**: O módulo DEVE oferecer o Trace Sink: uma porta de emissão pela qual 004, 005 e 006 registram dados de trace com o identificador da requisição, sem conhecer o backend (ADR-013).
- **FR-011**: A falha do backend de trace NÃO DEVE interromper nem atrasar perceptivelmente a execução; dados perdidos são sinalizados.
- **FR-012**: Cada dado de trace DEVE ser entregue ao **backend principal** (o consultável por requisição) no momento da emissão, um registro por evento, de modo que o trace de uma execução interrompida permaneça consultável e uma execução em andamento seja observável. Os demais destinos (FR-014) entregam em lote, com atraso de segundos. *(Refinada em 2026-10-13 pelo [ADR-034](../../docs/adr/ADR-034-trace-com-destinos-e-conteudo-opcional.md).)*
- **FR-013**: O seam de emissão DEVE receber eventos tipados publicados por este módulo e NÃO DEVE expor tipos de biblioteca de observabilidade; acrescentar um tipo de evento NÃO DEVE alterar o seam.
- **FR-014**: Cada evento DEVE ser entregue a todos os destinos configurados: o backend principal, o destino de uso e o Langfuse, quando ligado. A falha de um destino NÃO DEVE afetar os outros nem quem emite; destinos de banco ou de rede DEVEM enfileirar num buffer limitado, esvaziado fora do caminho da requisição, e contar o que descartam; os contadores aparecem na saúde.
- **FR-015**: O destino de uso DEVE guardar, por chamada de modelo, instante, requisição, origem (`produção` ou `avaliação`), Assistant (quando há execução), provider, modelo, papel, tokens de entrada e de saída, duração e falha; e, por execução, início, fim, origem, Assistant, flow e desfecho. A origem é a do processo: as rodadas do harness, juiz incluído, gravam `avaliação`.
- **FR-016**: O seam Usage Report DEVE devolver, para um período, um fuso, um agrupamento (modelo ou Assistant) e um filtro de origem (padrão: só `produção`; ou `avaliação`, ou as duas): séries diárias e totais de requisições, chamadas de modelo, tokens de entrada e de saída e custo, com "sem preço" por linha e total incompleto quando faltar preço. O dia é o do fuso pedido; o padrão é o da instalação.
- **FR-017**: O seam Price Book DEVE manter preços por provider e modelo — USD por milhão de tokens de entrada e de saída, com data de início — e o custo DEVE ser calculado na consulta, pelo preço vigente em cada dia. Modelo sem preço não tem custo.
- **FR-018**: O seam Trace Destinations DEVE expor e gravar os ajustes do Langfuse (endereço, chave pública, chave secreta só de escrita, ligado) e da captura de conteúdo, com a origem de cada campo (instalação, runtime ou padrão); a instalação prevalece. A chave secreta gravada em runtime DEVE ficar cifrada com a chave mestra da instalação ([ADR-033](../../docs/adr/ADR-033-segredos-de-runtime-cifrados-com-a-chave-mestra.md)) e nunca DEVE ser devolvida. Gravar DEVE reconfigurar o destino sem restart. Uma operação de teste DEVE dizer se o Langfuse aceita as credenciais.
- **FR-019**: O texto de prompt e de resposta DEVE existir só num evento dedicado (emitido pela 006 junto com a chamada de modelo), que só é entregue com a captura de conteúdo ligada (desligada por padrão) e só a destinos que declaram aceitar conteúdo; o backend principal NÃO DEVE recebê-lo. O texto passa pela redação de credenciais e é cortado por mensagem. Nenhum outro evento carrega texto de prompt, resposta, argumento ou resultado de tool, exceto os trechos entregues já previstos na FR-004 ([ADR-017](../../docs/adr/ADR-017-trace-sink-cresce-por-eventos-aditivos.md), ADR-034).
- **FR-020**: O uso DEVE ser expurgado depois de um período de retenção configurável pela instalação.

### Key Entities

- **Trace Sink**: porta de emissão de dados de trace, consumida pelos módulos que produzem esses dados.
- **Trace Event**: um dado de trace tipado, publicado por este módulo; um tipo por espécie de acontecimento (execução, chamada de modelo, validação, erro, tool, decisão do controller, portão de cobertura e, na Fase 6, recuperação — identificador, score e proveniência dos trechos, e o texto só dos entregues à geração).
- **Trace**: registro estruturado de uma execução — os eventos de um identificador de requisição, agregados na consulta.
- **Golden Set / Golden Item**: conjunto dourado e seus itens; cada evidência esperada é um documento, com seção ou identificador de trecho opcionais.
- **Eval Run / Baseline**: execução do harness e linha de base de comparação.
- **Domain Metric** (contrato 001): métrica fornecida por um pack — nome e valor por item sobre uma **Eval Observation** (item esperado, resposta, citações e trechos com proveniência), sem acesso ao core.
- **Trace Destination**: para onde os eventos vão — backend principal, uso, Langfuse —, cada um dizendo se aceita conteúdo.
- **Usage Record**: uma chamada de modelo ou uma execução, como o destino de uso as guarda (FR-015).
- **Price**: provider, modelo, USD por milhão de tokens de entrada e de saída, data de início.
- **Destination Settings**: ajustes do Langfuse e da captura de conteúdo, com a origem de cada campo; a chave secreta cifrada.
- **Model Exchange**: o evento com as mensagens e a saída de uma chamada de modelo, só para destinos que aceitam conteúdo.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Qualquer pergunta do tipo "por que o controller escolheu X" é respondida só com o trace, em menos de 5 minutos.
- **SC-002**: Uma rodada de 50 perguntas conclui em tempo compatível com rodar a cada PR relevante (meta: até 30 minutos).
- **SC-003**: 100% das regressões determinísticas acima da tolerância são barradas no CI.
- **SC-004**: Toda mudança de calibração tem relatório antes/depois.
- **SC-005**: Os totais de tokens do relatório de uso batem 100% com a soma das chamadas de modelo emitidas no período, em teste.
- **SC-006**: Com o Langfuse ou o banco de uso indisponíveis, nenhuma execução fica mais lenta de forma perceptível nem falha.
- **SC-007**: Em nenhum cenário de teste o texto de prompt ou de resposta chega ao backend principal, e com a captura desligada não chega a nenhum destino.
- **SC-008**: O relatório de 90 dias com até 100 mil chamadas de modelo responde em menos de 1 segundo.

## Assumptions

- O conteúdo dos conjuntos dourados é responsabilidade do pack de domínio (ex.: spec 105); o core fornece só formato e runner.
- Instrumentação de trace é incremental desde a Fase 1; o harness completo entra na Fase 6.
- Backend de trace (arquivo, Postgres ou ferramenta de observabilidade) é decidido no plano; é adapter do exporter. A candidata "API do OpenTelemetry como porta" foi resolvida na clarificação de 2026-09-17: o seam é contrato próprio, e OpenTelemetry, se entrar, é adapter — candidato a transporte do destino Langfuse (Fase 9, research do plano).
- Uso, preços e ajustes dos destinos exigem o perfil `persistent` para sobreviver a um restart; no `memory`, ficam em memória.
- O custo é estimativa: preços manuais, sem separar tokens de cache ou de raciocínio, e com os tokens que o provider informa.
- Trace e harness estão em lados opostos do hexágono (porta secundária × adapter primário); dividi-los em duas specs é opcional e, se feito, segue "Como reescrever um módulo" em `specs/README.md`.
