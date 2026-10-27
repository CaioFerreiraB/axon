# Feature Specification: Bootstrap e composition root do núcleo

**Feature Branch**: `011-core-bootstrap`

**Created**: 2026-09-14

**Status**: Draft

**Input**: ADR-012 (composition root), ADR-013 (relógio único, Trace Sink); [relatório de estilo arquitetural](../../docs/relatorio-estilo-arquitetural.md), lacuna G6; arch-v1 §13 (boot, CLI) e §14 (deployment). Fase 9 (2026-10-13): identidade da plataforma, superfície de administração, sobreposições, destinos do trace e chave mestra — ADR-030 a ADR-034. Fase 9, incremento 9.5 (2026-10-20): identidade Axon — ADR-037, ADR-038.

## Module Boundary *(mandatory)*

- **Módulo**: Bootstrap — composition root do `axon-ai`: carrega a configuração do operador, escolhe e instancia o adapter de cada porta, injeta seams e adapters nos módulos, conduz a ordem de boot e oferece os pontos de entrada do processo.
- **Repositório / distribuição**: distribuição `axon-ai` (workspace `axon-ai/` do repositório da plataforma, [ADR-037](../../docs/adr/ADR-037-a-plataforma-se-chama-axon.md)) → `packages/core/src/axon_ai/bootstrap/`; comando `axon` (raiz). A 011 é dona do nome da distribuição, do import `axon_ai`, do comando e do prefixo `AXON_` do ambiente (US7).
- **Consome (seams)**: o `api.py` de todos os módulos do core (002–009 e 012) e os `adapters/` deles. É o único módulo autorizado a importar adapters de outros módulos (princípio XIII).
- **Expõe (seams)**: nenhum seam Python. Expõe os pontos de entrada do processo — servidor e raiz da linha de comando `axon`, onde cada módulo contribui seus subcomandos —, consumidos pelo operador, pelo template de instalação (002) e pela CI.
- **Depende de infraestrutura (via portas)**: configuração do operador (arquivos e ambiente). Indiretamente, toda a infraestrutura dos módulos, cujos adapters instancia.
- **Não conhece**: regras de negócio de qualquer módulo (grant, catálogo, flows, políticas de tool), o estado interno do motor e o contexto de execução (005), qualquer domínio.
- **Substituição**: preservar a ordem de boot com falha fechada, os perfis de adapters e os comandos da linha de comando; a técnica de injeção é livre.
- **Insumo técnico**: [design.md](design.md); [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md), [ADR-013](../../docs/adr/ADR-013-seams-transversais-trace-e-tempo.md), [ADR-009](../../docs/adr/ADR-009-deploy-docker-build-arg.md), [ADR-020](../../docs/adr/ADR-020-segredos-uma-fonte-por-perfil-uma-porta-por-modulo.md), [ADR-030](../../docs/adr/ADR-030-a-plataforma-e-o-provedor-de-identidade.md), [ADR-033](../../docs/adr/ADR-033-segredos-de-runtime-cifrados-com-a-chave-mestra.md), [ADR-034](../../docs/adr/ADR-034-trace-com-destinos-e-conteudo-opcional.md), [ADR-037](../../docs/adr/ADR-037-a-plataforma-se-chama-axon.md), [ADR-038](../../docs/adr/ADR-038-marca-da-plataforma-e-marca-da-instalacao.md).

## Clarifications

### Session 2026-09-21

- Q: A ordem de boot tem sete etapas, mas duas pertencem a módulos que ainda não existem. Como o boot lida com isso? → A: Cada etapa é declarada — nome, ação e política de falha (interrompe o boot ou degrada e segue) — e a sequência executa a lista registrada na fase. Na Fase 1 registram-se configuração, adapters, packs, motor e API; registry MCP e validação de Assistants entram quando seus módulos existirem, sem tocar no código da sequência. É o que torna FR-002 e FR-003 verificáveis com etapas de teste, sem subir a plataforma inteira.
- Q: A linha de comando completa é a US4 (Fase 2); o que a Fase 1 entrega como ponto de entrada? → A: Um `serve` mínimo (hoje `axon serve`), que conduz o boot e serve a aplicação com um servidor ASGI. É o que faz a US1 existir de fato — sem ele, "o operador inicia o serviço" não teria como acontecer — e o que permite conversar com a plataforma por HTTP fora da suíte. Os subcomandos contribuídos por cada módulo continuam na Fase 2.
- Q: A API resolve `<assistant>/<modelo>` num grant, e até a 003 existir quem monta isso é esta spec. De onde vem a configuração? → A: De um `assistants.yaml` mínimo — nome do Assistant → packs, flow e modelo por papel —, como o `design.md` já previa ao dar YAML ao armazenamento de Assistants de sistema. A composition root o lê e monta o resolvedor de grant; quando a 003 chegar, ela assume o arquivo e esta spec passa a consumir o seam dela. O formato nasce aqui e é herdado, em vez de inventado duas vezes.
- Q: O perfil de teste que sobe a plataforma inteira em memória é código distribuído ou das suítes? → A: Da distribuição. O perfil vive no próprio módulo, e qualquer suíte monta a plataforma com uma chamada — inclusive a de um pack externo, que passa a poder testar seu pack contra a plataforma de verdade. É o que a SC-003 mede, e evita que cada spec remonte tudo à mão.

### Session 2026-09-30

- Q: Como cada perfil autentica, agora que a 003 existe? → A: Com a verificação real nos três, e o autenticador anônimo sai. `persistent`: OIDC por JWKS e chaves de API no Postgres. `memory`: OIDC quando configurado e uma chave de desenvolvimento lida do ambiente, no grupo de administração. `test`: verificador OIDC estático e chave semeada, com credenciais conhecidas exportadas para as suítes.
- Q: O que faz a saúde agregada responder 503 (fora do ar), e o que só a marca como degradada, com 200? → A: Só item **crítico** leva a 503 — armazenamento persistente inacessível ou etapa crítica do boot que falhou. Pack em erro, Assistant indisponível e modelo fora do ar são itens não saudáveis de um resultado `degraded`, com 200 e o item nomeado: a instância continua atendendo o resto.

### Session 2026-10-02

- Q: Quando a plataforma verifica se os servidores MCP globais estão no ar — só na saúde agregada, também no boot, ou em nenhum? → A: Só na saúde agregada. O boot não sai para a rede: a etapa do registry MCP carrega o arquivo do operador e o armazenamento, e um MCP fora do ar nunca atrasa nem impede a subida (SC-004). A saúde traz um item **não crítico** por servidor global, consultado em paralelo sob o prazo e o cache que ela já tem; servidor fora do ar deixa o resultado `degraded` (200), nunca `down`. Servidores de usuário (`~alias`) ficam fora — a 008 os verifica um a um.
- Q: Como uma suíte ponta a ponta, subindo a plataforma pelo perfil `test`, faz o controller pedir uma tool e um servidor MCP responder, sem rede? → A: A chamada que monta a plataforma aceita **trocas de porta**: a suíte passa o adapter de qualquer porta (o provider do controller com um roteiro, o transporte MCP com servidores programados) sem montar o resto. Sem troca, o perfil `test` continua autossuficiente — o modelo simulado responde `{"action": "answer"}` quando chamado como controller e o transporte MCP simulado não tem servidores. A troca existe só na chamada Python que as suítes usam; nenhum arquivo de configuração nem variável de ambiente a expõe.
- Q: Com o registry MCP no mesmo Postgres dos outros módulos, o caso de borda "armazenamento do registry MCP indisponível" deve ser reescrito? → A: Sim. Com um banco só (ADR-015), registry inacessível é banco inacessível: a saúde agregada responde `down` (503, item crítico) e as requisições recebem 503 `storage_unavailable` (008 FR-021). O que continua não crítico é o servidor MCP **remoto** fora do ar: fica fora do catálogo da execução com registro `error`, e a execução segue (004, 005).

### Session 2026-10-20

- Q: Quais são o nome da distribuição, o import, a pasta e a versão do core depois do renome? → A: Distribuição `axon-ai`, import `axon_ai`, workspace na pasta `axon-ai/` (as pastas `packages/core`, `packages/contracts` e `packages/generic` não mudam), versão `0.7.0rc1`: a linha 0.6.0 termina no rc6 com o nome antigo (ADR-037, itens 2 e 4). O import muda em todos os módulos do core de uma vez, nesta passada, porque é um pacote só; a mudança nos outros módulos é mecânica, sem comportamento novo. Tag `v0.7.0-rc1` depois da passada da 013, com o aval do mantenedor.
- Q: Como o operador chama a plataforma e vê a versão? → A: Pelo comando `axon` (o que se digita fica curto; `axon-ai` é o nome da distribuição Python). `axon --version` imprime `axon-ai <versão>`, lida dos metadados da distribuição instalada, e sai com 0 sem carregar configuração. Os subcomandos são os mesmos de antes.
- Q: O que acontece com as variáveis `AI_CORE_*` depois do renome? → A: Todas as variáveis do core passam ao prefixo `AXON_` com o mesmo sufixo — inclusive as que outros módulos leem pela porta de segredos (`AXON_MCP_SECRET_<REF>`, `AXON_OPENAI_API_KEY`, `AXON_OPENROUTER_API_KEY`, `AXON_IDENTITY_SECRET_<REF>`, `AXON_GOOGLE_*`, `AXON_BOOTSTRAP_ADMIN_*`) e a das suítes (`AXON_TEST_POSTGRES_DSN`). Corte seco com diagnóstico (ADR-037, item 3): qualquer variável cujo nome comece com `AI_CORE_` presente no ambiente, conhecida ou não, com valor ou vazia, faz a configuração ser recusada antes da primeira etapa, com uma linha por variável que nomeia a antiga e a nova (`AI_CORE_PROFILE → AXON_PROFILE`), nunca o valor. A recusa vale também quando a nova já está definida, e para os subcomandos que carregam a configuração. Nenhum período em que os dois prefixos valem.
- Q: Qual o nome exibido quando a instalação não define o seu? → A: "Axon" (era "Agentic"), o default de `AXON_DISPLAY_NAME` (ADR-038, item 1). O lockup, a atribuição "com Axon", o favicon e o `instance.custom` do `me` são da 012, da 013 e da 008, nas passadas delas; a 011 só entrega o nome padrão e a configuração de nome e logotipo que já entregava.
- Q: A substituição mecânica desta passada renomeia também os identificadores com comportamento de outros módulos? → A: Não. Cada um muda na passada do módulo dono, com testes (ADR-037, item 7): o grupo de entry point `ai_core.packs` (002), as audiências `ai-core`/`ai-core-admin` e o prefixo `aic_` da chave de API (003), o `service.name` do OTel e o rótulo HKDF da observabilidade (009), os cabeçalhos `x-ai-core-*`, a chave de extensão `x_ai_core` e o título do OpenAPI (008), o cookie, o realm Basic e os rótulos HKDF e CSRF da identidade (012), o pacote npm da console (013) e a distribuição do pack de referência (010). Os da 011 mudam aqui: o comando, o prefixo, o nome do pool de conexões (`axon`) e o nome padrão. As specs 004–007, sem passada própria, mudam só nos nomes nesta passada, inclusive o marcador interno `x-ai-core-optional` da 006, que nunca vai ao provider (passa a `x-axon-optional`).
- Q: Onde as suítes de pack encontram as credenciais do perfil `test` depois do renome? → A: Em `axon_ai.bootstrap.profiles` (e `axon_ai.bootstrap.identity`), com os mesmos nomes (`TEST_OIDC_TOKEN`, `TEST_API_KEY`, `TEST_ADMIN_USERNAME`, `TEST_ADMIN_PASSWORD`). O valor de `TEST_API_KEY` muda na passada da 003 (prefixo `axn_`).

### Session 2026-10-21

- Q: Como o operador configura a raiz dos dados dos packs ([ADR-041](../../docs/adr/ADR-041-o-pack-prepara-os-proprios-dados-no-build.md))? → A: Por `AXON_PACKS_DATA_DIR`, um caminho; sem ela, não há raiz, e cada pack recebe `data_dir=None`. A raiz vale nos três perfis e é a mesma no build (`axon packs prepare`) e em runtime (a carga dos packs no boot e em `packs list|check`). A composition root não cria nem confere o diretório: quem cria cada `<raiz>/<pack>` é o `packs prepare` da 002.
- Q: Como o `packs prepare` entra na raiz `axon`? → A: Como `packs list|check`: uma entrada na lista de registro de `bootstrap/cli.py`, que monta só configuração e adapters (sem os hooks de catálogo nem a carga do registry) e repassa os códigos da 002 (0, 1, 2).

### Session 2026-10-22

- Q: Que configuração as imagens na conversa trazem ([ADR-044](../../docs/adr/ADR-044-imagens-na-conversa.md), item 12)? → A: Quatro variáveis, com os valores propostos no ADR: `AXON_TOOL_MAX_ATTACHMENT_BYTES` (2 MiB; vai ao `McpService` da 007), `AXON_MAX_REQUEST_BYTES` (32 MiB), `AXON_MAX_INPUT_IMAGE_BYTES` (5 MiB) e `AXON_MAX_INPUT_IMAGES` (4; 0 desliga a imagem do usuário) — as três últimas vão ao `create_app` da 008 como `ImageLimits`. Fora da faixa, o boot para nomeando a variável.
- Q: Como se prova sem rede? → A: No perfil `test`, com o controller e o servidor MCP programados pelas trocas de porta de sempre: a tool devolve PNG, a resposta leva a imagem em markdown, e no turno seguinte (histórico do cliente) o `view_image` leva a imagem ao provider simulado da geração, que a registra.

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

Um único comando `axon` reúne os subcomandos dos módulos — `serve`, `packs list`, `packs check` (002), `assistants validate` (003) — com a mesma configuração e os mesmos adapters do servidor. Os subcomandos de validação rodam sem abrir a API.

**Why this priority**: Fase 2. Diagnóstico e validação no build da imagem (ADR-009) dependem disso; sem uma raiz, os comandos ficariam espalhados entre módulos.

**Independent Test**: Rodar `packs check` e `assistants validate` numa instalação com um pack incompatível e um Assistant inválido; os dois saem com código não zero e mensagem explícita, sem subir o servidor.

**Acceptance Scenarios**:

1. **Given** uma instalação, **When** o operador pede a ajuda do comando `axon`, **Then** vê os subcomandos de todos os módulos.
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

1. **Given** o perfil `persistent` com a identidade ligada e sem `AXON_MASTER_KEY`, **When** a plataforma sobe,
   **Then** o boot falha na etapa `configuration` com erro que nomeia a variável.
2. **Given** a identidade ligada e `AXON_OIDC_ISSUER` também configurado, **When** a plataforma sobe, **Then** o boot
   falha nomeando o conflito: a plataforma confia num único emissor.
3. **Given** uma instalação sem contas e as variáveis de admin inicial, **When** a plataforma sobe, **Then** o admin
   existe no grupo de administração; numa segunda subida, as variáveis são ignoradas com aviso.
4. **Given** o Langfuse configurado e fora do ar, **When** a plataforma sobe, **Then** o boot conclui; a saúde mostra
   `trace:langfuse` como não crítico e indisponível.
5. **Given** o perfil `test`, **When** uma suíte de pack o monta, **Then** encontra o admin semeado e as credenciais dele
   exportadas pela distribuição, como já encontra a chave de teste.

---

### User Story 7 - Identidade Axon: a plataforma com o nome da marca (Priority: P2)

A plataforma passa a se chamar Axon (ADR-037). O operador instala a distribuição `axon-ai`, configura a instalação pelas
variáveis `AXON_*` e opera pelo comando `axon`; sem nome próprio, a instalação se apresenta como "Axon" (ADR-038). Um
`.env` antigo, com variáveis `AI_CORE_*`, não sobe a plataforma: o boot o recusa dizendo o nome novo de cada variável,
em vez de ignorá-lo em silêncio e subir com os defaults. Quem escreve a suíte de um pack monta a plataforma pelo
`axon_ai`, como montava pelo nome antigo.

**Why this priority**: A 011 é dona da distribuição, do comando e do ambiente; sem esta passada, as passadas dos outros
módulos do core e a do pack (101) não têm o nome novo a que se ligar. P2 porque nenhum comportamento da plataforma muda,
só o nome pelo qual ela é instalada, configurada e chamada.

**Independent Test**: Com o workspace renomeado, `axon --version` mostra `axon-ai 0.7.0rc1`; `axon serve` com
`AXON_PROFILE=memory` sobe e responde à saúde; o mesmo comando com `AI_CORE_PROFILE=memory` no ambiente falha na
configuração nomeando `AXON_PROFILE`; a suíte inteira do workspace passa com o import `axon_ai`.

**Acceptance Scenarios**:

1. **Given** a distribuição instalada, **When** o operador roda `axon --version`, **Then** vê `axon-ai` e a versão
   instalada (`0.7.0rc1`), com código 0 e sem carregar configuração.
2. **Given** um ambiente com `AXON_PROFILE=persistent` e `AXON_DATABASE_URL` definidos, **When** o operador sobe a
   plataforma, **Then** ela sobe no perfil `persistent`, como subia com os nomes antigos.
3. **Given** um ambiente com `AI_CORE_PROFILE` e `AI_CORE_MCP_SECRET_FINANCEIRO_TOKEN`, **When** o operador sobe a
   plataforma ou roda um subcomando que carrega a configuração, **Then** a configuração é recusada antes da primeira
   etapa, com código não zero e uma linha por variável — `AI_CORE_PROFILE → AXON_PROFILE` e
   `AI_CORE_MCP_SECRET_FINANCEIRO_TOKEN → AXON_MCP_SECRET_FINANCEIRO_TOKEN` —, sem nenhum valor na saída.
4. **Given** `AXON_PROFILE` e `AI_CORE_PROFILE` definidas juntas, **When** a plataforma sobe, **Then** a configuração é
   recusada do mesmo jeito: o nome antigo nunca é ignorado.
5. **Given** uma instalação sem `AXON_DISPLAY_NAME`, **When** as páginas do provedor e a console pedem o nome da
   instalação, **Then** recebem "Axon".
6. **Given** a suíte de um pack, **When** ela monta a plataforma pelo perfil `test` com as credenciais de
   `axon_ai.bootstrap.profiles`, **Then** a conversa atravessa a plataforma, como no cenário 5 da US2.
7. **Given** a ajuda do comando `axon`, **When** o operador a pede, **Then** vê os subcomandos de todos os módulos,
   como na US4, sob o nome `axon`.

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
- Variável `AI_CORE_*` que nunca existiu (por exemplo, `AI_CORE_FOO`): recusada do mesmo jeito, com `AXON_FOO` na mensagem — a regra é pelo prefixo, não por uma lista.
- Variável `AI_CORE_*` vazia: recusada; a presença do nome antigo já indica um `.env` a migrar.
- Variáveis de outros prefixos parecidos (`AI_COREX`, `MY_AI_CORE_URL`, `AI_SCOUTING_*`): não são do core e não são recusadas pelo boot; `AI_SCOUTING_*` é recusada pelo pack, na passada da 101.
- Distribuição instalada sem metadados (execução direto da árvore, sem instalar): `axon --version` mostra `axon-ai desconhecida` e sai com 0.

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
- **FR-022**: A distribuição do core DEVE se chamar `axon-ai`, na versão `0.7.0rc1`, com o pacote importável `axon_ai` em todos os módulos e o workspace na pasta `axon-ai/`. NÃO DEVE existir alias, reexportação nem módulo com o nome antigo (`ai-core`, `ai_core`): corte seco (ADR-037, item 3). *(Fase 9, incremento 9.5.)*
- **FR-023**: O comando único do FR-010 DEVE se chamar `axon`, com os mesmos subcomandos, e DEVE oferecer `axon --version`, que imprime `axon-ai <versão>` a partir dos metadados da distribuição instalada (ou `desconhecida`, sem eles) e sai com 0 sem carregar configuração.
- **FR-024**: Toda variável de ambiente do core DEVE usar o prefixo `AXON_`, com o sufixo de antes — as que este módulo lê e as que outros módulos leem pelas portas de segredo que ele monta (FR-009). As mensagens de erro de configuração DEVEM nomear a variável com o prefixo novo.
- **FR-025**: A carga da configuração DEVE recusar o ambiente em que exista qualquer variável cujo nome comece com `AI_CORE_`, conhecida ou não, vazia ou não, mesmo com a equivalente `AXON_` definida: erro de configuração antes da primeira etapa do boot (e nos subcomandos que carregam a configuração), com uma linha por variável no formato `AI_CORE_<X> → AXON_<X>` e nunca o valor (FR-009).
- **FR-026**: O nome exibido padrão da instalação (FR-016, 012 FR-023) DEVE ser "Axon" (ADR-038).
- **FR-027**: As credenciais do perfil `test` exportadas para as suítes (FR-014, FR-015, FR-021) DEVEM estar em `axon_ai.bootstrap.profiles`, com os mesmos nomes. O nome do pool de conexões do perfil `persistent` DEVE ser `axon`.
- **FR-028**: A configuração DEVE aceitar `AXON_PACKS_DATA_DIR`, a raiz dos diretórios de dados dos packs, e entregá-la à 002 nos três perfis; ausente, nenhum pack recebe diretório. A raiz de comandos DEVE registrar `packs prepare` (002 FR-030), e só ele chama o hook `prepare` (002 FR-031).
- **FR-029**: A configuração DEVE ler `AXON_TOOL_MAX_ATTACHMENT_BYTES`, `AXON_MAX_REQUEST_BYTES`, `AXON_MAX_INPUT_IMAGE_BYTES` e `AXON_MAX_INPUT_IMAGES`, com faixas que nomeiam a variável, e ligá-las à 007 e à 008 nos três perfis ([ADR-044](../../docs/adr/ADR-044-imagens-na-conversa.md), item 12).

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
- **SC-008**: Depois da passada da US7, zero ocorrências de `ai_core`, `ai-core` ou `AI_CORE` no código, nos testes, na configuração e nos documentos vivos do workspace e das specs do core (fora do histórico do ADR-037, item 6, do código, dos testes e dos documentos da recusa dos nomes antigos (FR-025) e dos identificadores que pertencem às passadas de outros módulos — clarificação de 2026-10-20), e as suítes do workspace e da console passam.

## Assumptions

- A configuração vem de arquivos montados na imagem (`packs.yaml`, `assistants.yaml`) e de variáveis de ambiente, como no template de instalação (002, ADR-009).
- Processo único na v1; múltiplas réplicas ficam fora de escopo, como os contadores de taxa da 003.
- A técnica de injeção (construtores explícitos ou container) é decidida no plano; a constituição exige apenas que ela fique neste módulo.
- O perfil de teste usa um provider de modelo simulado, fornecido como adapter do contrato `LLMProvider`.
- O perfil persistente cresce por fase: Assistants de usuário e histórico na Fase 2; registry MCP e auditoria na Fase 3; contas, sessões e chaves (012), sobreposições (003), uso, preços e ajustes dos destinos (009) na Fase 9; checkpoint quando houver retomada (ver `docs/roadmap.md`).
- US7 (ADR-037): a passada renomeia de forma mecânica o import em todos os módulos do core, o workspace, os workflows da CI e os documentos vivos das specs 001–013 (`spec.md`, `design.md`, `contracts/`, `data-model.md`, `quickstart.md`) onde citam o core, o comando ou o prefixo — os de 004–007 sem ciclo próprio. Os `research.md`, `plan.md`, `tasks.md` e `checklists/` já executados ficam como estão. As specs `1xx` mudam na passada da 101: até lá, o pack depende do core pela tag `v0.3.0`, ainda com o nome antigo.
- US7: `CLAUDE.md`, `.specify/templates/overrides/` e o `README.md` da raiz mudam no fechamento do renome (ADR-037, depois da passada da instalação); a instalação (`agentic-deploy`) continua presa à tag antiga até a passada dela.
- US7: se a instalação definiu o próprio nome ou logotipo (`instance.custom` da 008, ADR-038) é decisão da passada da 008 sobre a configuração que a 011 já entrega.
