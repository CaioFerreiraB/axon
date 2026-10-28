# Feature Specification: Contratos públicos do núcleo (`axon-ai-contracts`)

**Feature Branch**: `001-core-contracts`

**Created**: 2026-09-10

**Status**: Draft

**Input**: Tradução de arch-v1 §5 (contratos), §6 (isolamento de estado entre packs), §7.4 (escape hatch), §30 (distribuição, versionamento, fronteiras); ADR-004, ADR-005, ADR-011, ADR-012, ADR-013. Fase 9, incremento 9.5 (2026-10-20): identidade Axon — ADR-037.

## Module Boundary *(mandatory)*

- **Módulo**: `axon-ai-contracts` (import `axon_ai_contracts`) — a única superfície que um pack enxerga do sistema.
- **Repositório / distribuição**: repositório da plataforma (`axon`, [ADR-037](../../docs/adr/ADR-037-a-plataforma-se-chama-axon.md)) → workspace do core, `packages/contracts`; distribuição com versão própria (tags `contracts-vX.Y.Z`).
- **Consome (seams)**: nenhum. Depende só da biblioteca padrão da linguagem e de `typing_extensions`.
- **Expõe (seams)**: Contrato de pack; Turn View; Contratos de serviço (`LLMProvider`, `MCPClient`) — consumidos por 002, 004, 005, 006, 007, 010 e todas as specs `1xx`. O nome da distribuição e do import é parte do seam: mudá-lo é quebra (US6). No estilo do ADR-012, estes contratos são as portas do microkernel: packs e implementações do core são os adapters.
- **Depende de infraestrutura (via portas)**: nenhuma — contratos não fazem I/O.
- **Não conhece**: runtime, motor de execução e seu estado interno, framework de grafo, HTTP, bancos, vetores, qualquer domínio.
- **Substituição**: qualquer mudança segue semver com a convenção 0.x deslocada (FR-016): enquanto o major for 0, campo, hook ou tipo opcional novo = patch e remoção, renomeação ou mudança de semântica = minor; a partir de 1.0, aditivo = minor e breaking = major. Toda remoção passa antes por uma janela de depreciação.
- **Insumo técnico**: [design.md](design.md); [ADR-004](../../docs/adr/ADR-004-contratos-no-repo-do-core.md), [ADR-005](../../docs/adr/ADR-005-execute-tool-unificado.md), [ADR-011](../../docs/adr/ADR-011-contratos-independentes-do-motor.md), [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md), [ADR-013](../../docs/adr/ADR-013-seams-transversais-trace-e-tempo.md), [ADR-014](../../docs/adr/ADR-014-politica-versoes-0x-contratos.md), [ADR-037](../../docs/adr/ADR-037-a-plataforma-se-chama-axon.md).

## Clarifications

### Session 2026-09-15

- Q: Enquanto os contratos estiverem em 0.x, que tipo de mudança sobe o minor e qual sobe o patch? → A: Convenção 0.x deslocada — enquanto o major for 0, mudança aditiva (campo, hook ou tipo opcional novo; correção) sobe o patch e mudança breaking (remoção, renomeação, mudança de semântica) sobe o minor; a faixa dos packs é `>=0.N,<0.(N+1)`; um símbolo depreciado em 0.N.x só sai a partir de 0.(N+1).0; de 1.0 em diante vale o semver padrão.
- Q: Como o pack declara a faixa de versões de contrato que aceita, para o core comparar com a versão instalada antes de carregá-lo? → A: Derivada de `contract_version` — o pack declara só a versão que implementa (ex.: "0.1" ou "0.1.3") e a faixa aceita sai da política 0.x ("0.1.3" → `>=0.1.3,<0.2`); a dependência de `axon-ai-contracts` no pacote do pack deve caber nessa faixa (verificado pela suíte de conformidade); a regra de compatibilidade também aceita faixa explícita.
- Q: O que o Pack Context carrega na 0.1, e quando os hooks de catálogo são chamados? → A: Só dados de carga — nome do pack e configuração já validada contra `config_schema`, sem serviços; os hooks de catálogo (instrução de sistema, tools, retrievers, reranker, validators, rotina) são chamados uma vez, na carga; dados por execução chegam só pela Turn View; o contexto de validators continua um tipo próprio, sem modelos; serviço novo, se surgir caso de uso, entra como campo opcional (patch).
- Q: Como um retriever do pack declara a coleção que consulta e vira tool, para o gateway aplicar a allowlist de coleções? → A: `NamedRetriever` com nome local, descrição, coleções consultadas e o retriever; o core deriva dele a tool `retrieval` (esquema padrão: consulta e quantidade opcional); `tools()` do pack declara só tools nativas (`mcp` vem da descoberta do cliente MCP); retriever com coleção fora do grant fica fora do catálogo; filtros de recuperação só vêm da preparação de contexto.
- Q: O que o CI deve detectar automaticamente como breaking change dos contratos (SC-004)? → A: Diff da superfície pública (símbolos exportados, campos, tipos e defaults dos value objects, assinaturas dos Protocols) contra a última tag `contracts-v*`, exigindo o bump correspondente, mais um pack de teste congelado na última tag rodando os próprios testes contra a versão nova; mudança só de semântica fica com revisão e changelog.

### Session 2026-10-07

- Q: Como um validator que reescreve a resposta (citação inventada removida) age quando a resposta sai em streaming? → A: Pelo protocolo opcional e aditivo `StreamingValidator` (contratos `0.1.1`): `open_stream(view, ctx)` devolve uma sessão com `feed(delta) -> str` (o texto pronto para sair) e `finish() -> ValidationResult`; o fim só acrescenta ao que saiu, e o resultado é igual ao de `validate` para qualquer partição em pedaços. O kit de conformidade verifica as duas regras (ADR-024).

### Session 2026-10-20

- Q: Qual o nome da distribuição e do import dos contratos depois do renome da plataforma? → A: `axon-ai-contracts`, import `axon_ai_contracts` (ADR-037, item 2: no código, o prefixo `ai-` vira `axon-`, e `ai-core` vira `axon-ai`; `axon` sozinho colide com um pacote do PyPI). A pasta `packages/contracts` do workspace não muda; a pasta do workspace (`ai-core/` → `axon-ai/`) é da passada da 011.
- Q: Que versão sai com o renome? → A: `0.2.0`. Renomear o import é quebra; pela política 0.x (FR-016, ADR-014), quebra sobe a minor. A faixa dos packs passa a `>=0.2,<0.3` e a `contract_version` de quem acompanha, a `"0.2"`. Tag `contracts-v0.2.0`, criada com o aval do mantenedor, depois das passadas do core (ADR-037, item 7).
- Q: Há alias, reexportação ou janela de depreciação para o nome antigo? → A: Não. Corte seco (ADR-037, item 3): não há instalação nem pack de terceiro a preservar, e os dois packs existentes (`generic`, `scouting`) mudam junto. A janela de depreciação do FR-016 vale para símbolos dentro da distribuição; o renome da distribuição inteira é decisão de ADR, não de depreciação. Um pack escrito para `0.1.x` precisa de nova versão.
- Q: Como o diff de superfície do FR-020 trata o renome, se a última tag (`contracts-v0.1.2`; a 0.1.3 não foi marcada) ainda tem o import antigo? → A: A superfície é comparada pelo nome de cada símbolo relativo à raiz do import (`TurnView`, `testing.turn_view`), não pelo nome completo; o renome da raiz e da distribuição é uma única mudança breaking ("distribuição renomeada"), que exige a minor e não conta como remoção sem depreciação. Os símbolos que existem nos dois lados são comparados normalmente. O pack congelado de `contracts-v0.1.2` não se aplica a `0.2.0` (série nova, compatibility.md §8).
- Q: O que as mensagens e as verificações nomeiam? → A: O nome novo, sempre: a mensagem de incompatibilidade ("requer axon-ai-contracts>=0.3, instalado 0.2.0"), o aviso de depreciação, a etapa de distribuição da suíte de conformidade (que procura a dependência `axon-ai-contracts` no pacote do pack; declarar só `ai-core-contracts` é "não declara dependência de axon-ai-contracts") e a varredura de imports, cujos módulos proibidos por padrão passam aos imports novos do core e do pack de referência (`axon_ai`, `axon_generic`) — `axon_ai_contracts` continua permitido, porque a comparação é por módulo, não por prefixo de texto.

### Session 2026-10-21

- Q: Como um pack que precisa de arquivos em runtime (um modelo, um índice) os obtém sem passos próprios na instalação? → A: Pelo protocolo opcional e aditivo `PreparesData` ([ADR-041](../../docs/adr/ADR-041-o-pack-prepara-os-proprios-dados-no-build.md)): `prepare(ctx: PackContext) -> None`, síncrono, chamado só no build da instalação (`axon packs prepare`, 002); `PackBase` traz o default que não faz nada. O `AgentPack` não muda — pack que não herda de `PackBase` e não define o hook continua conforme.
- Q: Onde o pack grava e lê esses arquivos? → A: No `PackContext.data_dir: Path | None` (default `None`): o diretório do pack que a plataforma entrega, o mesmo no build e em runtime. `None` quando a plataforma não tem raiz de dados configurada — o pack recorre à própria configuração (desenvolvimento e suítes). O `ValidatorContext` não muda.
- Q: Que versão sai? → A: `0.2.1` (aditivo; FR-016). Pack que implementa `prepare` ou lê `data_dir` declara `contract_version` "0.2.1" ou depende de `axon-ai-contracts>=0.2.1,<0.3` (ADR-014); pack que não usa nenhum dos dois continua com "0.2".
- Q: Como a suíte de conformidade exercita o hook? → A: Quando o pack tem `prepare` (todo pack que herda de `PackBase` tem), a suíte o chama **duas vezes** seguidas no mesmo diretório — temporário, ou o `data_dir` que o autor passar — e exige que nenhuma das duas levante e que ele seja síncrono e devolva `None` (idempotência). Os hooks seguintes recebem esse mesmo `data_dir`, como na carga com a raiz configurada.

### Session 2026-10-22

- Q: Como uma imagem atravessa os contratos ([ADR-044](../../docs/adr/ADR-044-imagens-na-conversa.md))? → A: Pelo value object `Attachment(id, mime, data, alt)`: bytes, um tipo da lista fechada `ATTACHMENT_MIME_TYPES` (`image/png`, `image/jpeg`, `image/webp`, `image/gif`; SVG fica fora, é documento ativo) e um texto alternativo opcional. `ToolResult` ganha `attachments` (tupla, default vazia) e `Message` ganha a chave opcional `attachments`. `content` continua texto nos dois.
- Q: De onde vem o `id`? → A: Do conteúdo, calculado na construção e nunca informado: `img-` seguido dos 12 primeiros hexadecimais do SHA-256 dos bytes. É o que reconhece a mesma imagem quando ela volta pelo histórico do cliente, onde o markdown não carrega id, e junta repetições.
- Q: Quem limpa o `alt`, que vem de fora (servidor MCP, pack)? → A: O próprio `Attachment`, na construção: quebras de linha viram espaço, `[`, `]`, `(` e `)` saem, espaços se juntam, o texto é cortado em 120 caracteres e o vazio vira `None`. Assim nenhum produtor entrega um `alt` que quebre o markdown em que a 008 o põe.
- Q: O `ChatMessage` dos contratos passa a aceitar partes de imagem? → A: Não. Mudar o tipo de `content` é breaking pelo diff de superfície (FR-020) e levaria a série a `0.3.0`, contra a consequência do ADR-044 ("o contrato 001 muda de forma aditiva"); nenhum pack usa `ChatMessage` nem `LLMProvider`. A mensagem com partes é tipo da 006 (decisão do mantenedor, 2026-10-22; 006 research). `ChatMessage` e `LLMProvider` não mudam.
- Q: Que versão sai? → A: `0.2.2` (aditivo; FR-016). Pack que devolve imagem pelas próprias tools ou lê os anexos das mensagens pede `axon-ai-contracts>=0.2.2,<0.3`; os demais não mudam.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Autor de pack constrói e testa um pack sem o core (Priority: P1)

Um autor de pack cria um pack novo num repositório próprio, declarando como única dependência da plataforma a distribuição de contratos. Ele implementa identidade, manifest e hooks, e roda a suíte de testes do pack sem instalar runtime, servidor HTTP, framework de grafo ou banco.

**Why this priority**: É a promessa central da arquitetura (ADR-004): packs de domínio têm ciclo de vida próprio e não arrastam o core. Sem isso, reescrever o `axon-scouting` ou o core vira coordenação entre repositórios.

**Independent Test**: Criar um pack mínimo num ambiente limpo com apenas os contratos instalados; a resolução de dependências contém somente os contratos e a biblioteca padrão, e os testes passam.

**Acceptance Scenarios**:

1. **Given** um ambiente limpo, **When** o autor instala apenas a distribuição de contratos e o pack, **Then** nenhuma dependência de runtime, HTTP, grafo, banco ou vetores é resolvida.
2. **Given** um pack que implementa o contrato, **When** o autor escreve testes dos hooks usando fixtures de Turn View, **Then** os testes rodam sem nenhum componente do core.
3. **Given** um pack que tenta importar qualquer módulo do core, **When** o CI do pack roda a verificação de fronteiras, **Then** o build falha apontando o import proibido.

---

### User Story 2 - Pack declara tools nativas, retrievers, reranker e validators (Priority: P1)

Um pack declara, de forma enumerável e sem executar lógica de domínio: fragmento de instrução para o prompt, preparação de contexto, tools nativas (com esquema de parâmetros, marca de escrita e handler), retrievers (com as coleções que consultam — o core os expõe como tools de recuperação), reranker opcional, validators de resposta e configuração aceita.

**Why this priority**: É o que permite ao core compor packs por união de conjuntos (ADR-001, ADR-005) em vez de cirurgia de grafo.

**Independent Test**: Instanciar o pack de referência e enumerar todas as capacidades; cada uma tem nome local, descrição e esquema válidos.

**Acceptance Scenarios**:

1. **Given** um pack instanciado, **When** suas tools e retrievers são enumerados, **Then** cada tool informa nome local, descrição, esquema de parâmetros, tipo e se muta estado externo, e cada retriever informa nome local, descrição e coleções consultadas.
2. **Given** um pack sem retrievers, reranker ou validators, **When** esses hooks são consultados, **Then** retornam vazio sem erro — todos os hooks, exceto identidade e manifest, são opcionais.
3. **Given** uma tool de tipo `native`, **When** ela é declarada, **Then** carrega o handler que a executa; tools de outros tipos não carregam handler.
4. **Given** um retriever declarado, **When** o core deriva a tool de recuperação dele, **Then** a tool tem tipo `retrieval`, o nome local e a descrição do retriever e o esquema padrão (consulta e quantidade opcional), sem handler.

---

### User Story 3 - Compatibilidade verificável entre pack e plataforma (Priority: P1)

Cada pack declara a versão de contrato que implementa; a faixa de contratos que aceita é derivada dela pela política de versões (FR-016, FR-018), e a dependência declarada no pacote do pack precisa caber nessa faixa. A plataforma consegue decidir, antes de executar qualquer código de domínio, se o pack é compatível.

**Why this priority**: Sem isso, incompatibilidade aparece em produção em vez de no build (princípio VII).

**Independent Test**: Declarar num pack de teste uma versão de contrato de major diferente e verificar que a regra de compatibilidade o rejeita com mensagem que nomeia versão exigida e instalada.

**Acceptance Scenarios**:

1. **Given** contratos instalados na versão 0.2.x, **When** um pack declara `contract_version` "0.2" (faixa derivada `>=0.2,<0.3`), **Then** é considerado compatível.
2. **Given** contratos instalados na versão 0.2.x, **When** um pack declara `contract_version` "0.3" (exige `>=0.3`), **Then** é considerado incompatível e a mensagem nomeia a restrição violada e a versão instalada: "requer axon-ai-contracts>=0.3, instalado 0.2.x".
3. **Given** um contrato marcado como depreciado numa versão, **When** um pack o usa, **Then** recebe aviso de depreciação que nomeia a versão da depreciação e a da remoção, e continua funcionando até a próxima série de quebra (0.(N+1).0 enquanto 0.x; o próximo major a partir de 1.0).

---

### User Story 4 - Pack enxerga uma visão estável da execução, não o estado do motor (Priority: P2)

Os hooks de pack recebem uma Turn View: uma visão somente-leitura com campos enumerados e versionados. O pack escreve apenas na própria fatia (retornando a atualização) e lê fatias de outros packs somente se declarou dependência deles.

**Why this priority**: É o que permite reescrever o motor de execução — inclusive trocar o framework de grafo — sem quebrar packs (ADR-011, princípio II).

**Independent Test**: Executar os hooks de um pack com duas implementações diferentes de produtor de Turn View (fixture e motor real); o comportamento do pack é idêntico.

**Acceptance Scenarios**:

1. **Given** um hook de preparação de contexto, **When** ele executa, **Then** recebe uma Turn View imutável e devolve apenas a atualização da própria fatia.
2. **Given** um pack que não declarou dependência do pack B, **When** seu hook executa, **Then** a fatia de B não está presente na Turn View que ele recebe.
3. **Given** um validator, **When** recebe seu contexto, **Then** esse contexto não oferece acesso a modelos de linguagem.

---

### User Story 5 - Rotina isolada de pack para o caso excepcional (Priority: P3)

Um pack que precisa de fluxo de controle próprio fornece uma rotina isolada: recebe a própria fatia e os campos que declarou, devolve a própria fatia e as saídas que declarou, e opera sob limites de iteração e orçamento herdados do Assistant. A rotina não tem referência ao fluxo que a invoca.

**Why this priority**: Cobre o nível 3 de extensão (arch-v1 §7.4), que é excepcional; sem ele, um caso raro forçaria um flow novo no core.

**Independent Test**: Implementar uma rotina de teste, invocá-la com uma fixture e verificar que lê e escreve apenas o declarado.

**Acceptance Scenarios**:

1. **Given** uma rotina que declara leitura de "pergunta" e escrita em "resultado", **When** é invocada, **Then** recebe apenas a pergunta e a própria fatia e só consegue devolver o resultado e a própria fatia.
2. **Given** uma rotina que excede o limite de iterações herdado, **When** o limite é atingido, **Then** a rotina é interrompida e o truncamento é informado.

---

### User Story 6 - Identidade Axon: os contratos com o nome da plataforma (Priority: P2)

A plataforma passa a se chamar Axon (ADR-037). Um autor de pack declara a dependência `axon-ai-contracts`, importa `axon_ai_contracts` e implementa a `contract_version` "0.2". Tudo o que os contratos dizem a ele — incompatibilidade, depreciação, conformidade — usa o nome novo, e nada do nome antigo continua aceito. Quem mantém os contratos continua com a garantia do FR-020: o CI compara a versão nova com a última tag, ainda com o nome antigo, e exige o bump certo.

**Why this priority**: Os contratos são a superfície que o pack externo consome por tag; a distribuição renomeada é o primeiro passo do renome (ADR-037, item 7) e destrava as passadas do core e dos packs. P2 porque não muda nenhum comportamento de pack, só o nome pelo qual ele é encontrado.

**Independent Test**: Num ambiente limpo, instalar `axon-ai-contracts` 0.2.0 e o pack de teste (dependência `axon-ai-contracts>=0.2,<0.3`, `contract_version` "0.2"): a resolução contém só os contratos, `typing_extensions` e o pack; a suíte de conformidade passa; o diff de superfície contra a última tag (`contracts-v0.1.2`) exige a minor e aceita o 0.2.0.

**Acceptance Scenarios**:

1. **Given** um ambiente limpo, **When** o autor instala `axon-ai-contracts` 0.2.0, **Then** o pacote importável é `axon_ai_contracts`, com a mesma superfície pública de antes, e não existe módulo `ai_core_contracts` nesse ambiente.
2. **Given** contratos 0.2.0 instalados, **When** um pack declara `contract_version` "0.1", **Then** é incompatível, com a mensagem "requer axon-ai-contracts<0.2, instalado 0.2.0".
3. **Given** um pack cujo pacote declara a dependência `ai-core-contracts>=0.1,<0.2` (o nome antigo), **When** a suíte de conformidade verifica a distribuição, **Then** aponta `distribution.missing_requirement`, pedindo `axon-ai-contracts>=0.2,<0.3`.
4. **Given** a superfície da última tag `contracts-v0.1.2` (import `ai_core_contracts`) e a do HEAD (import `axon_ai_contracts`), **When** o diff de superfície roda, **Then** relata o renome como uma única mudança breaking, sem nenhum símbolo removido sem depreciação, relata à parte só as mudanças reais de símbolo desde a tag (a chave opcional `ChatUsage.cost` da 0.1.3, que não foi marcada, e o default novo de `check_imports`), exige a minor, aceita o 0.2.0 declarado e falha se a versão declarada for 0.1.4.
5. **Given** um pack que importa `axon_ai` (o core) ou `axon_generic`, **When** a varredura de imports roda com os módulos proibidos padrão, **Then** aponta cada import com arquivo e linha; o import de `axon_ai_contracts` não é apontado.
6. **Given** um símbolo depreciado, **When** um pack o usa, **Then** o aviso diz "está depreciado desde axon-ai-contracts X e será removido em Y".

---

### Edge Cases

- Duas tools do mesmo pack com o mesmo nome local: rejeitado como manifest inválido.
- Retriever com o mesmo nome local de uma tool nativa do mesmo pack (as duas virariam a mesma tool com namespace): manifest inválido.
- Retriever sem coleção declarada: o retriever nomeado não pode ser criado (erro na construção) e o pack não carrega.
- Tool declarada pelo pack com tipo `retrieval` ou `mcp`: manifest inválido — `retrieval` é derivada dos retrievers e `mcp` vem da descoberta do cliente MCP.
- Pack que declara dependência circular de fatia com outro pack: rejeitado na carga (verificado em 002).
- Versão aditiva nova dos contratos (patch enquanto 0.x) adiciona campo à Turn View: packs antigos continuam funcionando sem mudança e sem alterar a faixa declarada.
- Pack declara versão de contrato de um major futuro: incompatível, com mensagem explícita.
- Esquema de parâmetros de tool inválido: manifest inválido, pack não carrega.
- Hook de preparação de contexto devolve chaves fora da própria fatia: impossível por construção (o retorno é a fatia).
- Pack que ainda importa `ai_core_contracts` num ambiente com 0.2.0: o import falha na carga, e o pack fica em erro (002); não há módulo de compatibilidade (corte seco, ADR-037).
- Pack que declara as duas dependências, `ai-core-contracts` e `axon-ai-contracts`: só a de `axon-ai-contracts` é verificada; a outra é dependência qualquer, fora dos contratos.
- Diff de superfície entre duas versões com o mesmo nome: nenhuma mudança de renome é relatada (o comportamento de antes).
- Pack que precisa de arquivos e recebe `data_dir` `None` (plataforma sem raiz de dados): recorre à própria configuração; se nem ela aponta para os arquivos, o pack falha na carga com mensagem própria, e fica em erro (002).
- `prepare` chamado de novo sobre um diretório já preparado: não baixa nem reescreve o que está presente e íntegro (idempotente, ADR-041).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A distribuição de contratos DEVE depender apenas da biblioteca padrão da linguagem e de `typing_extensions`.
- **FR-002**: O contrato de pack DEVE exigir identidade (nome único, versão de contrato implementada — `contract_version`, única declaração de compatibilidade no código do pack) e um manifest com: versão do pack, flow preferido (por nome), dependências de fatia de outros packs, esquema de configuração e coleções exigidas.
- **FR-003**: O contrato de pack DEVE oferecer hooks opcionais: fragmento de instrução de sistema, preparação de contexto, tools, retrievers, reranker, validators e rotina isolada.
- **FR-004**: Uma especificação de tool DEVE conter nome local, descrição, esquema de parâmetros, tipo (`retrieval`, `mcp`, `native`), marca de escrita (muta estado externo) e, apenas para `native`, o handler. O namespacing de nomes é responsabilidade do core, não do pack. As tools declaradas pelo pack no hook de tools DEVEM ser nativas; tools `retrieval` são derivadas pelo core dos retrievers (FR-006) e tools `mcp` vêm da descoberta do cliente MCP (FR-014).
- **FR-005**: O resultado de tool DEVE carregar o conteúdo, a marca de que é dado não-confiável, indicação de truncamento e erro, quando houver.
- **FR-006**: O contrato de retriever DEVE aceitar consulta, quantidade máxima e filtros opcionais, e devolver chunks com proveniência: identificador estável do chunk, documento, versão, status de vigência, seção, página, score e metadados adicionais. O pack DEVE declarar cada retriever como retriever nomeado — nome local, descrição, coleções consultadas (ao menos uma) e o retriever —, que é a informação de que o core precisa para derivar a tool `retrieval` com esquema padrão (consulta e quantidade opcional) e para deixar fora do catálogo o retriever cuja coleção não está no grant. O modelo não escolhe filtros: eles vêm só da preparação de contexto (FR-012).
- **FR-007**: O contrato de reranker DEVE receber consulta e chunks e devolver no máximo N chunks reordenados.
- **FR-008**: O contrato de validator DEVE ser determinístico: recebe Turn View e contexto sem acesso a modelos e devolve resultado com aprovação, problemas encontrados, modificações aplicadas (ex.: citações removidas) e marcações (ex.: "não fundamentada").
- **FR-009**: A Turn View DEVE ser somente-leitura e expor, no mínimo: identificador da requisição, nome do Assistant, **data de referência da execução** (a mesma para todos os hooks da execução — ADR-013), pergunta, mensagens, chunks recuperados e reranqueados, **chunks efetivamente entregues à geração**, resultados de tools, resposta, citações, a fatia do próprio pack e as fatias das dependências declaradas.
- **FR-010**: A preparação de contexto DEVE devolver a atualização da própria fatia; o contrato NÃO DEVE oferecer caminho de escrita fora dela.
- **FR-011**: A rotina isolada DEVE declarar campos de leitura e de saída, receber apenas a própria fatia mais os campos declarados, e operar sob limites herdados, sem referência ao fluxo que a invoca.
- **FR-012**: Um pack PODE publicar, na preparação de contexto, filtros de recuperação destinados aos próprios retrievers; o core os repassa de forma opaca.
- **FR-013**: O contrato de provider de LLM DEVE aceitar mensagens, modelo, tools opcionais, restrição de formato de saída e modo streaming.
- **FR-014**: O contrato de cliente MCP DEVE receber apenas aliases já autorizados (nunca endereços) para descoberta e execução.
- **FR-015**: Os contratos NÃO DEVEM expor tipos do motor de execução, do framework de grafo, de HTTP ou de armazenamento.
- **FR-016**: A distribuição DEVE seguir semver com a convenção 0.x deslocada: enquanto o major for 0, mudança aditiva (campo, hook ou tipo opcional novo; correção) sobe o patch e mudança breaking (remoção, renomeação, mudança de semântica) sobe o minor; a partir de 1.0, aditiva = minor e breaking = major. Um símbolo só pode ser removido depois de depreciado em ao menos uma versão da série compatível anterior (depreciado em 0.N.x → removível a partir de 0.(N+1).0; depreciado em X.Y → removível a partir de (X+1).0). A distribuição DEVE oferecer a regra de compatibilidade entre versão instalada e faixa declarada pelo pack.
- **FR-017**: A fronteira "contratos não importam nada do projeto" DEVE ser verificada no CI.
- **FR-018**: A faixa aceita por um pack DEVE ser derivada da `contract_version` declarada, pela política do FR-016 ("0.1" → `>=0.1,<0.2`; "0.1.3" → `>=0.1.3,<0.2`; "1.2" → `>=1.2,<2`). A regra de compatibilidade DEVE aceitar também faixas explícitas, e a mensagem de incompatibilidade DEVE nomear a restrição violada e a versão instalada. A suíte de conformidade de pack DEVE apontar a dependência de `axon-ai-contracts`, declarada no pacote do pack, que aceite versões fora da faixa derivada.
- **FR-019**: O Pack Context DEVE conter apenas o nome do pack e a configuração já validada contra o `config_schema` do manifest (e, desde 0.2.1, o diretório de dados — FR-026); ele NÃO expõe serviços. Os hooks de catálogo (instrução de sistema, tools, retrievers, reranker, validators, rotina) DEVEM ser chamados uma vez, na carga do pack, e o que devolvem vale para todas as execuções; dados por execução chegam aos hooks apenas pela Turn View (e, na rotina, pelos campos declarados). O contexto entregue a validators DEVE ser um tipo próprio, que não expõe modelos, mesmo que o Pack Context ganhe serviços numa versão futura.
- **FR-020**: O CI da distribuição DEVE, a partir da tag `contracts-v0.1.0`: (a) comparar a superfície pública — símbolos exportados, campos, tipos e defaults dos value objects, assinaturas dos Protocols — com a da última tag `contracts-v*` e falhar quando a mudança exigir um bump maior que o declarado pela política do FR-016; (b) rodar os testes de um pack de teste congelado na última tag contra a versão nova. Mudança só de semântica, sem mudança de forma, DEVE ser registrada no changelog e classificada na revisão.
- **FR-021**: Os contratos DEVEM oferecer o protocolo opcional `StreamingValidator` (com a sessão `AnswerStream`) para validators que reescrevem a resposta em streaming; a suíte de conformidade DEVE verificar, em várias partições da resposta, que o resultado da sessão é igual ao de `validate` e que o fim só acrescenta ao texto já liberado (`validator.stream.mismatch`, `validator.stream.not_append_only`). Mudança aditiva: contratos `0.1.1` (clarificação de 2026-10-07; ADR-024).

- **FR-022**: A distribuição de contratos DEVE se chamar `axon-ai-contracts`, com o pacote importável `axon_ai_contracts` (e o kit em `axon_ai_contracts.testing`), na versão `0.2.0`. NÃO DEVE existir alias, reexportação nem módulo com o nome antigo (`ai-core-contracts`, `ai_core_contracts`), nem janela de depreciação para ele: o renome é corte seco (ADR-037, clarificação de 2026-10-20).
- **FR-023**: Toda mensagem dos contratos que nomeia a distribuição DEVE usar `axon-ai-contracts`: a de incompatibilidade (FR-018), o aviso de depreciação (FR-016) e as da etapa de distribuição da suíte de conformidade, que DEVE procurar a dependência pelo nome normalizado `axon-ai-contracts`.
- **FR-024**: A varredura de imports do kit DEVE proibir por padrão os pacotes importáveis do core e do pack de referência com os nomes do ADR-037 (`axon_ai`, `axon_generic`), comparando por módulo (igual ou com prefixo seguido de ponto), de modo que `axon_ai_contracts` nunca seja apontado.
- **FR-025**: O diff de superfície do FR-020 DEVE comparar os símbolos pelo nome relativo à raiz do import e tratar a mudança de distribuição ou de raiz entre a linha de base e o HEAD como uma única mudança breaking, que exige a minor enquanto 0.x e NÃO conta como remoção sem depreciação. O CI DEVE conseguir gerar a superfície da linha de base com o import que ela tinha (`ai_core_contracts` em `contracts-v0.1.2`). Textos da linha de base que citam a raiz antiga (anotações, `repr` de aliases) DEVEM ser comparados com a raiz nova.
- **FR-026**: Os contratos DEVEM oferecer o protocolo opcional `PreparesData` — `prepare(ctx: PackContext) -> None`, síncrono — para o pack produzir, no build da instalação, os arquivos de que precisa em runtime ([ADR-041](../../docs/adr/ADR-041-o-pack-prepara-os-proprios-dados-no-build.md)); `PackBase` DEVE trazer o default que não faz nada, e o `AgentPack` NÃO DEVE mudar. O `PackContext` DEVE ganhar `data_dir: Path | None`, com default `None`. Versão `0.2.1`.
- **FR-027**: A suíte de conformidade DEVE, quando o pack tem `prepare`, chamá-lo duas vezes seguidas no mesmo diretório (temporário ou o informado pelo autor) e reportar exceção, retorno diferente de `None` e hook assíncrono; os hooks seguintes da suíte DEVEM receber o mesmo `data_dir`.
- **FR-028**: Os contratos DEVEM oferecer o value object `Attachment` — `id`, `mime`, `data: bytes`, `alt: str | None` — e a constante `ATTACHMENT_MIME_TYPES` (`image/png`, `image/jpeg`, `image/webp`, `image/gif`). O `id` DEVE ser calculado na construção, `img-` mais os 12 primeiros hexadecimais do SHA-256 de `data`; tipo fora da lista ou `data` vazio DEVE levantar `ValueError`; o `alt` DEVE sair limpo (sem quebras de linha nem `[`, `]`, `(`, `)`, no máximo 120 caracteres, vazio vira `None`) ([ADR-044](../../docs/adr/ADR-044-imagens-na-conversa.md), item 1).
- **FR-029**: `ToolResult` DEVE ganhar `attachments: tuple[Attachment, ...]`, com default vazio, e `Message` a chave opcional (`NotRequired`) `attachments`; `content` continua texto. `ChatMessage` e `LLMProvider` NÃO mudam. Versão `0.2.2`.
- **FR-030**: `Citation` DEVE ganhar a chave opcional `url` (`str | None`): o endereço do original para o usuário abrir, montado pelo pack — a página ou o trecho fazem parte dele; o core só o repassa ([ADR-051](../../docs/adr/ADR-051-link-da-citacao-e-fontes-no-open-webui.md)). Versão `0.2.3`.

### Key Entities

- **Pack**: unidade de extensão; identidade, manifest, hooks.
- **Pack Manifest**: versão, flow preferido, dependências de fatia, esquema de configuração, coleções exigidas.
- **Pack Context**: dados de carga do pack — nome, configuração validada e, desde 0.2.1, o diretório de dados (`data_dir`, FR-026); sem serviços (FR-019).
- **Validator Context**: contexto próprio dos validators; nunca expõe modelos (FR-008, FR-019).
- **Tool Spec** / **Tool Result**: capacidade invocável e seu resultado não-confiável; desde 0.2.2, o resultado carrega anexos (FR-029).
- **Attachment**: imagem com id derivado do conteúdo, tipo da lista fechada e `alt` limpo (FR-028, ADR-044).
- **Chunk**: trecho recuperado com proveniência e score.
- **Retriever** / **Reranker** / **Answer Validator** / **Validation Result**: capacidades de recuperação, ordenação e checagem.
- **Named Retriever**: retriever declarado pelo pack com nome local, descrição e coleções consultadas; origem da tool `retrieval` e da checagem de coleções do grant.
- **Turn View**: visão somente-leitura da execução (ADR-011), incluindo a data de referência (ADR-013).
- **Pack Routine**: rotina isolada do escape hatch.
- **LLM Provider** / **MCP Client**: formas que implementações do core cumprem.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Um pack de exemplo resolve dependências e roda sua suíte inteira com zero dependências além dos contratos (verificado no lockfile).
- **SC-002**: Uma reescrita completa do motor de execução (spec 005), inclusive troca do framework de grafo, é concluída com **zero** alterações nos contratos e nos packs — a suíte de conformidade de packs passa sem modificação.
- **SC-003**: 100% dos hooks de pack do `axon-generic` e do `axon-scouting` são testáveis com fixtures de Turn View, sem subir nenhum serviço.
- **SC-004**: 100% das breaking changes de forma na superfície pública (remoção ou renomeação de símbolo exportado; mudança de campo, tipo ou default de value object; mudança de assinatura de Protocol) sem o bump correspondente falham no CI antes do merge, e o pack de teste congelado na última tag passa nos próprios testes contra toda versão da mesma série compatível (FR-020).
- **SC-005**: `axon-generic` (010) e `axon-scouting` (101) implementam o contrato sem nenhum import do core, verificado pela checagem de fronteiras.
- **SC-006**: Depois da passada da US6, zero ocorrências de `ai_core_contracts` ou `ai-core-contracts` no código, nos testes e na configuração do workspace e dos packs do workspace (fora dos documentos de histórico do ADR-037, item 6, e dos testes que provam o corte seco — cenários 1 e 3 da US6), e as suítes do workspace passam com os contratos 0.2.0.

## Assumptions

- ADR-011 aceito em 2026-09-14: FR-008 a FR-011 e FR-015 valem como escritos.
- A data de referência entra na Turn View antes da tag `contracts-v0.1.0` (ADR-013), sem custo de versão.
- A política de versões 0.x foi fixada em 2026-09-15 (Clarifications, FR-016) e formalizada no ADR-014, com a constituição emendada para a 1.2.0: a faixa `>=0.1,<0.2` dos packs continua recebendo mudanças aditivas, que saem como patch.
- A rotina isolada (FR-003, FR-011, US5) não entra na 0.1: chega depois, como hook opcional com default em `PackBase` — adição compatível (patch em 0.x). Pelo roadmap, itens P3 entram quando houver caso de uso.
- `LLMProvider` e `MCPClient` ficam nos contratos para padronizar as implementações do core e permitir providers de terceiros; packs não os implementam na v1.
- A tag `contracts-v0.1.0` existe antes da Fase 4, quando o `ai-scouting` começa em repositório próprio (arch-v1 §31).
- Antes da tag `contracts-v0.1.0` não há linha de base: o diff de superfície pública e o pack congelado (FR-020) passam a valer a partir dela.
- Os contratos ainda mudam nas Fases 1–3; dentro do workspace do core, cada mudança é um PR único.
- US6 (ADR-037): a passada atualiza, de forma mecânica, os imports de quem consome os contratos no workspace (core, `ai-generic` e testes) e leva o pack de referência e os packs de teste à faixa `>=0.2,<0.3` e à `contract_version` "0.2", para a CI ficar verde. O nome da distribuição do pack de referência (`axon-generic`) é da passada da 010; o do core e a pasta do workspace, da 011; o `axon-scouting`, da 101, que passa a depender de `contracts-v0.2.0`. Até a tag, os contratos novos convivem com o core de nome antigo no mesmo workspace, e o import-linter continua guardando a fronteira de `ai_generic` contra `ai_core`.
