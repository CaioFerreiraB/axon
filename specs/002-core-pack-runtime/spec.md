# Feature Specification: Descoberta, carga e composição de packs

**Feature Branch**: `002-core-pack-runtime`

**Created**: 2026-09-10

**Status**: Draft

**Input**: Tradução de arch-v1 §10 (níveis de extensão), §11 (packs declarativos, code packs, composição), §13 (registro, descoberta, fail-closed, introspecção, CLI), §14 (deployment), §6 (isolamento de fatias); ADR-003, ADR-009, ADR-011, ADR-012.

## Module Boundary *(mandatory)*

- **Módulo**: Pack Runtime — descobre, valida, habilita e compõe packs, e executa seus hooks com isolamento.
- **Repositório / distribuição**: `ai-core` → `packages/core/src/ai_core/packs/` (subcomandos `packs` em `adapters/cli.py`; a raiz do comando `ai-core` é da spec 011); template do repositório de instalação.
- **Consome (seams)**: Contrato de pack e Turn View — 001.
- **Expõe (seams)**: **Pack Registry** (packs habilitados, status, capacidades por pack) — consumido por 003, 004, 008; **Pack Hooks** (prompts, preparação de contexto, rerank, validators, rotinas, com isolamento de fatia) — consumido por 005.
- **Depende de infraestrutura (via portas)**: fonte dos packs instalados (descoberta) e configuração do operador (habilitação e configuração por pack).
- **Não conhece**: flows e nós do grafo, HTTP, Assistants (recebe apenas a lista ordenada de packs a compor), a ordem de boot da plataforma (spec 011), qualquer domínio.
- **Substituição**: preservar Pack Registry e Pack Hooks; o mecanismo de descoberta (entry points) pode mudar sem afetar consumidores.
- **Insumo técnico**: [design.md](design.md); [ADR-003](../../docs/adr/ADR-003-mcp-usuario-pack-operador.md), [ADR-009](../../docs/adr/ADR-009-deploy-docker-build-arg.md), [ADR-011](../../docs/adr/ADR-011-contratos-independentes-do-motor.md), [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Operador instala um pack e o core o descobre (Priority: P1)

O operador instala a distribuição de um pack na imagem. Na inicialização, o core descobre todos os packs instalados, verifica a compatibilidade de contrato e instancia os habilitados na configuração, passando a cada um a sua configuração.

**Why this priority**: É a Fase 1: "conversa funcionando ponta a ponta, com pack carregado por entry point". Sem descoberta não existe extensibilidade (princípio I: adicionar pack não modifica o core).

**Independent Test**: Instalar o pack de referência (010), habilitá-lo na configuração, iniciar o core e verificar que ele aparece como habilitado.

**Acceptance Scenarios**:

1. **Given** um pack instalado e habilitado, **When** o core inicia, **Then** o pack é instanciado com sua configuração e aparece como `enabled`.
2. **Given** um pack instalado e não listado ou marcado `enabled: false`, **When** o core inicia, **Then** o pack aparece como instalado e desabilitado, sem ser instanciado.
3. **Given** um pack habilitado cuja configuração viola o esquema declarado pelo pack, **When** o core inicia, **Then** o pack não carrega e o erro nomeia o campo inválido.

---

### User Story 2 - Pack quebrado não derruba o sistema (Priority: P1)

Pack com contrato incompatível, manifest inválido ou exceção na instanciação não carrega, é registrado em log e aparece com erro na introspecção. O sistema sobe sem ele. Assistants que dependem dele ficam indisponíveis com erro explícito.

**Why this priority**: Princípio VII (falha fechada e explícita). Um pack de terceiro nunca pode tirar a plataforma do ar.

**Independent Test**: Instalar três packs de teste defeituosos (contrato incompatível, manifest inválido, exceção no construtor) junto do pack de referência; o core sobe, o pack de referência funciona e os três aparecem com erro.

**Acceptance Scenarios**:

1. **Given** um pack que exige contratos `>=0.2` com 0.1 instalado, **When** o core inicia, **Then** o pack fica `error` com "requer ai-core-contracts>=0.2, instalado 0.1" e o boot conclui.
2. **Given** um pack que lança exceção ao ser instanciado, **When** o core inicia, **Then** o pack fica `error` com a causa e os demais packs carregam normalmente.
3. **Given** um Assistant que referencia um pack em erro, **When** alguém tenta usá-lo, **Then** a indisponibilidade é explícita e nomeia o pack — nunca uma resposta silenciosamente degradada.

---

### User Story 3 - Composição de packs como operação de conjunto (Priority: P1)

Dada a lista ordenada de packs de um Assistant, o runtime compõe: tools e retrievers por união com namespace; fragmentos de prompt concatenados na ordem declarada; preparação de contexto em sequência, cada pack escrevendo só na própria fatia; validators em sequência. Toda composição de packs válidos é executável por construção.

**Why this priority**: É o mecanismo que substitui o Graph Builder dinâmico (ADR-001) e o que torna o isolamento entre packs verificável.

**Independent Test**: Compor dois packs de teste que usam o mesmo nome local de tool e o mesmo nome de chave de fatia; verificar que os nomes ficam separados por namespace e que nenhuma fatia sobrescreve a outra.

**Acceptance Scenarios**:

1. **Given** packs A e B com uma tool local `search`, **When** compostos, **Then** o catálogo contém `a.search` e `b.search`.
2. **Given** A declarado antes de B no Assistant, **When** os prompts são montados, **Then** o fragmento de A precede o de B.
3. **Given** um pack que lê a fatia de outro sem declarar dependência, **When** é carregado, **Then** a carga falha (erro de carregamento, não de runtime).
4. **Given** um hook de preparação de contexto que lança exceção durante uma execução, **When** a exceção ocorre, **Then** a execução termina com erro explícito que nomeia o pack — sem resposta parcial silenciosa.

---

### User Story 4 - Operador inspeciona e valida packs sem subir o servidor (Priority: P2)

O operador lista o que está instalado e habilitado e valida compatibilidade por linha de comando, sem iniciar o servidor. A mesma informação está disponível por introspecção na superfície privada da API (exposta pela spec 008).

**Why this priority**: Diagnóstico rápido e validação no build dependem disso.

**Independent Test**: Rodar os comandos `packs list` e `packs check` com um pack incompatível instalado; `check` sai com código de erro e mensagem explícita.

**Acceptance Scenarios**:

1. **Given** packs instalados, **When** o operador roda `packs list`, **Then** vê nome, versão, versão de contrato e status de cada pack.
2. **Given** um pack incompatível, **When** o operador roda `packs check`, **Then** o comando sai com código diferente de zero e nomeia a incompatibilidade.

---

### User Story 5 - Operador compõe a instalação e o build rejeita incompatibilidade (Priority: P2)

O operador mantém um repositório de instalação que parte da imagem do core e recebe a lista de packs (de índice de pacotes ou URL de repositório) como parâmetro de build. O build roda a validação de packs; incompatibilidade falha o build, não a produção.

**Why this priority**: ADR-009 — instalação imutável e reproduzível; é o caminho pelo qual o `ai-scouting` (repositório próprio) entra na plataforma (Fase 4).

**Independent Test**: Buildar a imagem com um pack compatível (sucesso) e depois com um incompatível (falha no build).

**Acceptance Scenarios**:

1. **Given** a lista de packs com um pack compatível, **When** a imagem é buildada, **Then** o build conclui e o pack está disponível para habilitação.
2. **Given** a lista com um pack incompatível, **When** a imagem é buildada, **Then** o build falha na etapa de validação de packs.
3. **Given** uma instalação em execução, **When** alguém tenta instalar um pack sem rebuild, **Then** não há mecanismo para isso (não existe instalação de pack em runtime).

---

### User Story 6 - Administrador cria pack declarativo sem código (Priority: P3)

Quando a capacidade é "estas tools de MCP + este prompt + estes validators simples", um administrador declara o pack em configuração: fragmento de prompt, bindings de MCP com allowlist explícita de tools e namespace, flow preferido e validators declarativos (ex.: campos obrigatórios). Não há código nem rebuild.

**Why this priority**: Nível 3 de extensão (ADR-003); cobre muitos casos, mas não é necessário para as fases iniciais.

**Independent Test**: Declarar um pack com um binding de MCP expondo duas tools; verificar que só essas duas aparecem no catálogo, com o namespace declarado.

**Acceptance Scenarios**:

1. **Given** um pack declarativo que expõe `[get_transactions, get_balance]` de um MCP que oferece dez tools, **When** composto, **Then** apenas as duas aparecem, com o namespace declarado.
2. **Given** um pack declarativo que tenta declarar retriever próprio ou lógica condicional, **When** validado, **Then** é rejeitado — isso exige code pack.

---

### Edge Cases

- Dois packs instalados com o mesmo nome: nenhum dos dois carrega; erro nomeia o conflito.
- Pack habilitado na configuração mas não instalado: aparece como `error: não instalado`.
- Pack que depende da fatia de um pack desabilitado ou em erro: falha fechada também.
- Dependências de fatia circulares: erro de carregamento.
- Namespace de pack declarativo colidindo com nome de pack instalado: erro de carregamento.
- Validator que lança exceção durante a execução: a resposta não é entregue sem validação; a execução termina com erro explícito.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O sistema DEVE descobrir packs instalados por um grupo de registro padrão do empacotamento, sem lista fixa no código.
- **FR-002**: O sistema DEVE verificar a compatibilidade de contrato de cada pack antes de instanciá-lo.
- **FR-003**: Instalar e habilitar DEVEM ser etapas distintas; a habilitação e a configuração de cada pack vêm da configuração do operador.
- **FR-004**: O sistema DEVE validar a configuração de cada pack contra o esquema declarado pelo pack.
- **FR-005**: Falhas de contrato, manifest ou instanciação DEVEM impedir a carga do pack, ser registradas e expostas na introspecção, sem impedir o boot.
- **FR-006**: O Pack Registry DEVE expor, para cada pack: nome, versão, versão de contrato, status (`enabled`, `disabled`, `error`), mensagem de erro e capacidades declaradas.
- **FR-007**: A composição DEVE aplicar namespace `<pack>.<nome>` a todas as tools e retrievers.
- **FR-008**: A composição DEVE concatenar fragmentos de prompt e executar preparação de contexto e validators na ordem recebida (a ordem do Assistant).
- **FR-009**: O runtime DEVE entregar a cada hook uma Turn View contendo apenas a fatia do próprio pack e as fatias das dependências declaradas, e DEVE mesclar o retorno da preparação de contexto somente na fatia do pack.
- **FR-010**: Leitura de fatia não declarada e dependência circular DEVEM ser detectadas na carga.
- **FR-011**: Exceção em hook durante uma execução DEVE encerrar a execução com erro explícito que nomeia o pack.
- **FR-012**: A linha de comando DEVE oferecer listagem e validação de packs sem iniciar o servidor, com código de saída não zero em caso de incompatibilidade.
- **FR-013**: O template de instalação DEVE receber a lista de packs como parâmetro de build e executar a validação de packs durante o build.
- **FR-014**: NÃO DEVE existir mecanismo de instalação de pack em runtime.
- **FR-015**: O sistema DEVE aceitar packs declarativos com: fragmento de prompt, bindings de MCP (alias, allowlist explícita de tools, namespace), flow preferido e validators declarativos de um conjunto fechado.
- **FR-016**: Packs declarativos NÃO DEVEM poder declarar retriever próprio, transformação de documentos ou lógica condicional.

### Key Entities

- **Pack Registry Entry**: nome, versão, versão de contrato, origem (code/declarativo), status, erro, capacidades.
- **Pack Configuration**: habilitação e configuração por pack, fornecidas pelo operador.
- **Declarative Pack**: prompt, bindings de MCP, flow preferido, validators declarativos.
- **Composition**: resultado da composição de uma lista ordenada de packs para uma execução.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Adicionar um pack novo à instalação exige zero mudanças no código do core — apenas uma linha na lista de build e uma entrada de configuração.
- **SC-002**: Em 100% dos cenários de falha injetada (contrato incompatível, manifest inválido, exceção na instanciação), o sistema conclui o boot e os demais packs funcionam.
- **SC-003**: 100% das incompatibilidades de contrato são detectadas no build da imagem, antes da produção.
- **SC-004**: O operador identifica o estado de todos os packs e a causa de cada erro em menos de 1 minuto, usando apenas a linha de comando ou a introspecção.
- **SC-005**: Nenhuma combinação de packs válidos produz uma composição não executável (verificado por teste de composição com todos os pares de packs de teste).

## Assumptions

- Packs de código são distribuições Python com entry point no grupo `ai_core.packs` (constituição, "Stack").
- Packs declarativos vivem em arquivo de configuração ou banco e são carregados no boot e quando alterados, sem rebuild.
- A superfície HTTP de introspecção pertence à spec 008; esta spec fornece o Pack Registry que ela consulta.
- A ordem de composição é sempre a declarada pelo Assistant (spec 003); o pack não escolhe sua posição.
- A ordem de boot da plataforma (packs → registry MCP → motor → validação de Assistants → API) é da spec 011; este módulo oferece a operação de carga que ela chama.
