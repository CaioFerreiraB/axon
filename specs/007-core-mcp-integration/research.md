# Research — 007 MCP Integration (Fase 3: US1–US6)

Insumos: [spec.md](spec.md) (com as cinco clarificações de 2026-10-01), [design.md](design.md), ADR-003, ADR-012,
ADR-013 e ADR-015; os seams e portas já publicados ao redor deste módulo — o contrato `MCPClient`, `ToolSpec` e
`ToolResult` da 001, a porta `McpDirectory` e o `ExecutionGrant` da 003, o que a 004 espera do cliente restrito (design
dela: `discover_tools` com cache por TTL do lado da 007; MCP indisponível sinalizado, não silencioso) e a sessão de
armazenamento da 011 (research R13 dela). As decisões do `design.md` e dos ADRs aparecem como pré-aprovadas; as
clarificações aparecem em R3, R4, R5, R7 e R10. **Nenhum ADR novo**: as escolhas abaixo são internas ao módulo ou
seguem uma convenção já aceita (ADR-015).

## R1 — Esta passada entrega o módulo; o encaixe em 003, 008 e 011 é das passadas delas

**Decision**: as mudanças de código ficam em `ai_core/mcp/**` e `tests/mcp/**` (mais `pyproject.toml`, import-linter e
CI). O encaixe na plataforma em execução acontece nas passadas da Fase 3 dos módulos donos: a **011** constrói o
serviço e os adapters nos perfis, lê o arquivo do operador, migra o schema `mcp` e acrescenta a etapa `mcp_registry`
antes da validação de Assistants — e troca o `McpDirectory` vazio da 003 por este serviço; a **008** expõe o CRUD de
MCPs de usuário em `/v1` e de globais em `/private/v1` (com a regra do grupo de administração) e a saúde por servidor;
a **004** consome o cliente restrito.

**Rationale** (princípio II; mesma divisão da Fase 2, 003 R2): cada módulo entra com suíte de conformidade própria, e a
troca na plataforma é uma mudança de adapter na composition root. A 003 já declarou a forma que exige
(`McpDirectory.aliases`) e a 011 já previu a etapa (`boot-sequence.md`: "Etapas de outras fases — `mcp_registry` (007)
— entram na lista sem tocar no código que a executa").

**Alternatives considered**: fazer as rotas da 008 e o boot nesta passada (tocaria três módulos de uma vez e misturaria
as suítes; a Fase 2 mostrou que a divisão por passada mantém cada diff revisável).

## R2 — Os seams: registry, catálogo de aliases e cliente restrito ao grant

**Decision**: `api.py` publica três seams como `Protocol`:

- **`McpRegistry`** — CRUD por escopo. Globais: `globals`, `get_global`, `create_global`, `update_global`,
  `delete_global`, com **autoridade do operador** — quem confere o grupo de administração é a borda (008), como em
  `issue_as_operator` da 003. De usuário: `mine`, `get_mine`, `create_mine`, `update_mine`, `delete_mine`, sempre no
  escopo do `Principal`. E `available(principal)` (o que o Principal pode referenciar num Assistant próprio: os seus e
  os globais liberados, só alias e descrição) e `check(alias, owner=None)` (saúde por servidor, FR-011).
- **`McpCatalog`** — `aliases(*, owner)`, exatamente a forma da porta `McpDirectory` da 003, que este serviço satisfaz
  estruturalmente (R13).
- **`McpClients`** — `client_for(grant) -> RestrictedMcpClient`. O cliente cumpre o `MCPClient` da 001
  (`discover_tools`, `execute`) e acrescenta `discover(aliases) -> Discovery`, que devolve as tools **e** os servidores
  que falharam, com o motivo — é o que a 004 precisa para registrar e sinalizar MCP fora do ar (004 Edge Cases).

Os erros especializam os da 003 — `McpNotFound(NotFound)`, `McpRejected(RequestRejected)` (com `field`),
`McpConflict(Conflict)` —, e o cliente levanta `UnknownServer` para alias fora do grant. Value objects: `McpServerDraft`,
`McpServer`, `SecurityPolicy`, `McpSummary`, `ServerHealth`, `Discovery`.

**Rationale** (design.md: "MCP Registry" e "cliente MCP restrito" como seams; 003 R11; 004 design §4 e Edge Cases;
ADR-012): os erros herdados fazem a tabela de erros da 008 traduzir 404, 400 e 409 sem regra nova, e com a mensagem fixa
do 404 — MCP alheio e inexistente ficam indistinguíveis (SC-004). A 007 já depende do `api.py` da 003 (`Principal`,
`ExecutionGrant`), então reaproveitar a hierarquia não cria seta nova. `discover` existe porque `discover_tools` do
contrato devolve só tools: sem ele, a 004 não teria como saber que um servidor caiu.

**Alternatives considered**: um registry com `scope` em cada método e a checagem de administrador dentro dele (a regra
de quem administra é da 003 e é aplicada na borda pela porta `AdminGate` da 008; duplicá-la aqui criaria duas fontes);
erros próprios sem herança (a 008 ganharia uma linha de tabela por erro sem nenhum ganho).

## R3 — `stdio` só no arquivo do operador; `http`/`sse` também pela API (clarificação 1)

**Decision**: o registry tem duas origens de MCPs globais. O **arquivo do operador** (`mcp.yaml`, R10), lido uma vez no
boot, declara globais de qualquer transporte — é a única origem de `stdio` — e eles aparecem como `origin: "file"`,
somente leitura. O **armazenamento** (`McpServerStore`) guarda os globais `http`/`sse` criados pela API e todos os de
usuário. Criar ou alterar pela API um servidor `stdio`, em qualquer escopo, é recusado com `field="transport"`
(FR-013); alterar ou apagar um global do arquivo é `McpConflict` ("declarado no arquivo do operador"). Criar pela API um
global com alias que o arquivo já declara é `McpConflict`. Se o arquivo passa a declarar um alias que o armazenamento
já tem (o operador mudou o arquivo), **o arquivo prevalece**: o registro do armazenamento fica indisponível, com o
motivo, na listagem e na saúde.

**Rationale** (clarificação 1; ADR-003: "comando no host é nível de operador" e a alternativa rejeitada "endpoint de
admin que instala pack em runtime é execução remota por construção"): uma chave de administração vazada não vira
comando no host. O arquivo prevalecer é falha fechada e explícita sem parar o boot por um conflito que o operador
resolve apagando um dos dois.

**Alternatives considered**: o boot falhar no conflito (um alias criado por um administrador derrubaria a instância
quando o operador atualizasse o arquivo); o armazenamento prevalecer (a configuração da imagem perderia para a API,
o inverso da fronteira de confiança).

## R4 — Alias: `~` reservado ao usuário (clarificação 5)

**Decision**: alias global casa `[a-z0-9][a-z0-9_-]{0,31}` e é único entre os globais (arquivo + armazenamento); alias
de usuário é `~` seguido da mesma gramática, único por dono. Sem ponto: o ponto é o separador do namespace das tools na
004 (`<alias>.<tool>`). A recusa nomeia `alias`.

**Rationale** (clarificação 5; 003 FR-017, `NAME_PATTERN`): dois espaços que nunca se cruzam, nada sombreia nada, e a
tool de um MCP de usuário fica visivelmente distinta no catálogo (`~drive.buscar` × `drive.buscar`).

**Alternatives considered**: ver a clarificação.

## R5 — Rede: política pura sobre o IP resolvido, conexão fixada no IP validado (FR-009, clarificação 2)

**Decision**: a decisão "este destino pode ser alcançado?" é uma função pura em `domain/network.py`, que recebe o host,
os IPs resolvidos, o escopo do servidor e as duas listas do operador — hosts internos e, opcional, a allowlist de hosts
de destino:

1. host normalizado (minúsculas, sem ponto final);
2. **global** e host (ou IP literal) na allowlist de hosts internos → permitido;
3. `localhost` ou `*.localhost` → bloqueado antes de resolver;
4. allowlist de hosts de destino definida e host que não casa com ela (nome exato, `*.domínio` para os subdomínios,
   ou IP literal exato) → bloqueado, para global e para usuário;
5. nenhum IP → bloqueado;
6. cada IP é normalizado (IPv4 mapeado em IPv6, 6to4, Teredo) e precisa ser `is_global` — o que exclui loopback,
   privadas, link-local (metadados da nuvem em `169.254.169.254`), CGNAT, ULA, multicast, reservadas e não
   especificadas; **qualquer** IP bloqueado bloqueia o destino (resposta mista de DNS não passa).

O adapter de transporte HTTP aplica a política **a cada conexão**, num backend de rede próprio do `httpcore2` (o pool
aceita `network_backend`): resolve pelo `DnsResolver`, decide, e abre o TCP **no IP validado** — o TLS continua
verificando o certificado contra o nome do host. Como toda conexão passa pelo backend, redirecionamento e nova
resolução são conferidos do mesmo jeito; e o SDK só segue redirecionamento dentro da mesma origem. Proxies do ambiente
ficam desligados (`trust_env=False`): um proxy faria a conexão real sair de outro lugar.

A allowlist de hosts de destino é o controle de saída que o princípio VI exige ("o cliente MCP aplica allowlist de
hosts"); é opcional para que uma instalação aberta a MCPs de usuário na internet funcione sem listar cada host, e quem
quer restringir a saída a domínios conhecidos a define (alinhamento registrado na spec, achado C1 do `/speckit-analyze`).

**Rationale** (design.md: "checado no IP resolvido, a cada conexão e a cada redirecionamento"; princípio VI; SC-002):
conferir o IP e depois deixar a biblioteca resolver de novo abre a janela de DNS rebinding; fixar a conexão no IP
conferido fecha. `is_global` é a definição da IANA de "alcançável na internet", mais completa que uma lista de faixas
mantida à mão.

**Alternatives considered**: lista explícita de faixas (fácil esquecer CGNAT, 6to4 e IPv4 mapeado); conferir só no
registro (o DNS muda depois); proxy de saída dedicado (infraestrutura a mais para um processo único — princípio XII; vale
reavaliar se a instalação já tiver um).

## R6 — Transporte: SDK oficial de MCP, só em `adapters/`; uma sessão por operação

**Decision**: dependência nova `mcp>=2.2,<3` (o SDK oficial; traz `httpx2`/`httpcore2`, a camada HTTP que ele usa),
confinada a `adapters/` por import-linter. `http` é o Streamable HTTP do protocolo atual; `sse` é o transporte HTTP+SSE
legado; `stdio` usa `stdio_client` com comando, argumentos e ambiente fixados no arquivo do operador, sem shell. Cada
operação — descoberta, chamada, saúde — abre a sua sessão (`initialize`, a operação, encerramento). O **prazo** da
política é regra da porta: todo `McpTransport` o aplica à operação inteira e devolve `TransportFailure` quando ele
vence — o serviço só repassa `OperationLimits`, sem uma segunda camada de prazo. **Teto de bytes lidos por sessão**, só
em `http`/`sse`: `max_response_bytes` mais 1 MiB de folga para o protocolo (inicialização e lista de tools); passou, a
operação falha com o motivo. No `stdio` não há teto no transporte: o servidor é do operador, e o corte do conteúdo
(R9) e o prazo bastam — limitar a leitura do processo filho exigiria mexer nos internals do SDK.

Dois adapters, como no `design.md`: `transport_http.py` (`http` e `sse`, com o backend de rede de R5) e
`transport_stdio.py`. O serviço recebe um transporte por tipo. Para testes e para o perfil `test` da 011, um transporte
em memória com servidores programados (`adapters/memory.py`), na distribuição — como o provider simulado da 006.

**Rationale** (design.md, "Portas e adapters": `McpTransport` http/sse e stdio): o protocolo tem negociação de versão,
sessão e dois formatos de resposta HTTP; reimplementá-lo é risco sem ganho. A versão 2 do SDK aceita um cliente HTTP
pronto (`streamable_http_client(url, http_client=...)` e `sse_client(..., httpx_client_factory=...)`), que é onde entra
o backend de R5. Sessão por operação isola falhas e torna o teto de bytes por sessão um teto por chamada.

**Alternatives considered**: implementar o protocolo à mão sobre o `httpx` do workspace (JSON-RPC, sessão, SSE —
centenas de linhas para manter); manter sessões abertas entre operações (ganha a latência do `initialize`, mas precisa
de pool, renovação e reconexão — fica para quando houver medição que peça); SDK 1.x (`httpx` em vez de `httpx2`, mas a
série corrente é a 2).

## R7 — Credenciais: referência resolvida na hora, só para globais (FR-003, FR-004, clarificação 3)

**Decision**: porta `SecretResolver.resolve(ref) -> str | None`. Uma referência casa `[a-z0-9][a-z0-9_]{0,63}`; o
adapter de ambiente lê `AI_CORE_MCP_SECRET_<REF EM MAIÚSCULAS>` e nada mais — um global não aponta para
`AI_CORE_DATABASE_URL` nem para outra variável do processo. Tipos de autenticação: `none` e `bearer` (cabeçalho
`Authorization`) para `http`/`sse`; para `stdio`, `secrets` mapeia variáveis de ambiente do processo filho para
referências. O segredo é resolvido no momento da operação, vive só na memória dela e nunca entra em `McpServer`,
`ServerHealth`, `Discovery`, `ToolResult`, exceção nem log. Referência sem valor: a operação falha com
"credencial '<ref>' não configurada" (nomeia a referência, nunca um valor), e a saúde do servidor diz o mesmo. MCP de
usuário: `auth_type` só `none`, `credential_ref` proibida, endpoint sem usuário e senha (FR-014).

**Rationale** (FR-003, FR-004; design.md: `SecretResolver` de ambiente injetado pela 011; 011 FR-009: segredo nunca
em mensagem): o prefixo fixo é o que impede um administrador — ou uma chave de administração vazada — de mandar um
segredo do core para um endpoint externo.

**Alternatives considered**: qualquer variável de ambiente (a exfiltração acima); cofre externo já nesta fase (porta
pronta para isso; o adapter muda, o domínio não).

## R8 — Descoberta: cache por servidor com TTL, filtro aplicado na leitura (FR-007, FR-010, SC-003)

**Decision**: porta `DiscoveryCache` com adapter em memória e relógio da porta `Clock`. A chave é a identidade do
servidor (escopo, dono, alias) **mais a versão do registro** (`updated_at`; `"file"` para os do arquivo): alterar ou
desabilitar um servidor invalida a entrada sem lógica extra. O cache guarda a lista **bruta** de tools do servidor; a
allowlist e a marca de escrita são aplicadas a cada leitura, então mudar a política vale na execução seguinte. TTL
padrão de 300 s, configurável pela composition root. Falha de descoberta fica em cache negativo por 30 s — o mínimo para
que um servidor fora do ar não custe o prazo inteiro a cada execução. Servidor recém-registrado não tem entrada: aparece
na primeira execução seguinte (SC-003).

**Rationale** (FR-010; 004 FR-004: o cache é deste módulo; princípio XIII: tempo por porta): filtrar na leitura mantém
uma só regra para descoberta e para chamada (R9) e evita servir a política antiga até o TTL vencer.

**Alternatives considered**: guardar a lista já filtrada (política nova só depois do TTL); sem cache negativo (cada
execução esperaria o prazo de um servidor caído); deduplicar descobertas simultâneas do mesmo servidor (ganho pequeno
para um processo com poucas execuções paralelas — princípio XII).

## R9 — O cliente restrito (FR-005, FR-007, FR-008, US3)

**Decision**: `client_for(grant)` congela o conjunto de aliases do grant e o dono. Para Assistant de usuário (nome com
`~`), o dono é o `subject` do Principal do grant — Assistants de usuário só resolvem para o próprio dono (003) — e os
aliases válidos são os `~` do dono e os globais liberados a usuários; para Assistant de sistema, só globais. Alias fora
do grant, ou que deixou de ser visível desde a resolução, é `UnknownServer("servidor desconhecido: <alias>")` — mesma
mensagem para inexistente e não autorizado.

- `discover(aliases)` → `Discovery(tools, unavailable)`: para cada alias, a lista do cache ou do servidor, filtrada pela
  allowlist, em `ToolSpec(kind="mcp", mutates=<em write_tools>)`, com o nome local da tool (o namespace é da 004). Tool
  anunciada fora da allowlist não aparece; tool da allowlist que o servidor não anuncia também não. Servidor com falha
  entra em `unavailable` com o motivo. `discover_tools` (contrato 001) devolve só as tools.
- `execute(alias, tool, arguments)` → `ToolResult(untrusted=True)`: tool fora da allowlist é recusada sem tocar no
  servidor; prazo e teto de bytes da política; resultado de erro do servidor, prazo esgotado ou destino bloqueado viram
  `ToolResult(error=...)` — a 004 captura e registra. Conteúdo: os textos concatenados, com marcador para partes não
  textuais; o `structured_content` só quando não há texto — o protocolo pede que o servidor repita em texto o que
  devolve estruturado, e o SDK embrulha o retorno de uma tool simples em `{"result": ...}` (visto no protótipo da
  implementação). Acima de `max_response_bytes`, o texto é cortado com marca visível e `truncated=True` (princípio VI).

**Rationale** (US3; elo 4 da cadeia de enforcement; contrato 001: tools de MCP têm `kind="mcp"` e nenhum handler;
004 FR-007): o cliente não aceita endereço — só alias — e não confia que o grant continue válido: conferir de novo a
visibilidade custa uma leitura e fecha a janela entre resolução e execução.

**Alternatives considered**: devolver `ToolResult(error=...)` também para alias fora do grant (esconderia uma violação
de fronteira como falha comum de tool); levantar em falha de servidor (a 004 trataria exceção e resultado de erro por
caminhos diferentes).

## R10 — O arquivo do operador `mcp.yaml` (clarificações 1 e 2)

**Decision**: porta `McpConfigSource` com adapter YAML; formato em [contracts/mcp-yaml.md](contracts/mcp-yaml.md):
`servers` (alias → transporte, endpoint ou comando, autenticação, `user_access`, `enabled`, `description`, `policy`),
`network.internal_hosts` (nomes de host e IPs literais que **só MCPs globais** podem alcançar mesmo em faixa privada,
comparados com o host do endpoint) e `network.allowed_hosts` (opcional: a allowlist de hosts de destino de R5).
Erro de arquivo — YAML inválido, chave desconhecida, raiz que não é mapeamento — para o boot; erro de um servidor deixa
só ele indisponível, com o motivo (a mesma separação do `assistants.yaml`, 003 FR-011). Quem escolhe o caminho
(`AI_CORE_MCP_FILE`) é a 011.

**Rationale** (clarificação 1: `stdio` só por arquivo; clarificação 2: hosts internos por configuração da imagem, nunca
pela API): um arquivo só para os dois porque ambos são decisões do operador sobre a mesma coisa — com quem o core fala.

**Alternatives considered**: hosts internos numa variável de ambiente (lista longa em variável é frágil, e o arquivo já
existe); `stdio` no `assistants.yaml` (misturaria o formato de outro módulo).

## R11 — Validação do registro (FR-001, FR-012–FR-015)

**Decision**: regras puras em `domain/servers.py`, aplicadas igualmente ao rascunho da API e à entrada do arquivo, cada
recusa nomeando o campo:

| Campo | Regra |
|---|---|
| `alias` | R4 |
| `transport` | `http`, `sse` ou `stdio`; `stdio` só no arquivo (FR-012, FR-013) |
| `endpoint` | `http`/`sse`: URL absoluta com host, sem usuário/senha, sem fragmento; `https` obrigatório para usuário, `http` ou `https` para global |
| `command`, `args`, `env`, `secrets` | só `stdio`; `command` não vazio |
| `auth_type`, `credential_ref` | R7; usuário: só `none` e sem referência |
| `user_access` | só global; padrão `false` |
| `description` | opcional, até 500 caracteres |
| `policy.timeout_ms` | 1 000–120 000; padrão 30 000 |
| `policy.max_response_bytes` | 1 024–1 048 576; padrão 65 536 |
| `policy.allowed_tools` | **obrigatória e não vazia**, nomes exatos, sem curinga |
| `policy.write_tools` | subconjunto de `allowed_tools`; padrão vazio |

**Rationale** (FR-007; princípio IV: capacidade não declarada não existe; FR-008): allowlist obrigatória é a mesma
falha fechada do `models.allow` da 003 — um servidor que anuncia 50 tools não expõe nenhuma até alguém escolher. A saúde
do servidor lista o que ele anuncia, para que escrever a allowlist não exija outra ferramenta. Os limites de prazo e
tamanho são controles de segurança, não calibração de qualidade (princípio X).

**Alternatives considered**: allowlist ausente = todas (um servidor que ganha uma tool de escrita amanhã a exporia sem
ninguém decidir); curinga (o mesmo problema, um caractere mais curto); `http` permitido a usuário (dado de conversa em
texto claro pela internet).

## R12 — Armazenamento: memória e Postgres no schema `mcp` (ADR-015)

**Decision**: porta `McpServerStore` com `get(owner, alias)`, `list(owner)` (`owner=None` = globais), `all()`,
`insert` (falso se já existe), `replace` (falso se não existe) e `delete`. Adapter em memória e adapter Postgres no
schema `mcp`, tabela `servers` com a política em JSON, unicidade por `(owner, alias)` com índices parciais para globais
e de usuário, migrações em `adapters/sql/` e `migrate(pool)` como na 003 e na 008. A tabela só tem a **referência** da
credencial; a suíte de varredura de segredos (SC-001) confere o conteúdo inteiro do banco depois de operações
autenticadas.

**Rationale** (ADR-015; roadmap: `McpServerStore` memória → Postgres na Fase 3; design.md): mesma convenção dos módulos
que já persistem; quem chama `migrate` é a 011.

**Alternatives considered**: uma tabela por escopo (as regras são as mesmas; só o dono muda).

## R13 — `aliases(owner)` para a validação da 003 (US1 cen. 2; FR-006)

**Decision**: `aliases(owner=None)` devolve os globais **habilitados e disponíveis** (arquivo e armazenamento, sem os
sombreados de R3); `aliases(owner=X)` devolve os `~` habilitados de X mais os globais habilitados com `user_access`.
Servidor desabilitado some do catálogo: os Assistants que o referenciam ficam indisponíveis com o motivo da 003
("MCP desconhecido"), sem regra nova lá.

**Rationale** (003 FR-016 e a porta que ela declarou; clarificação 4): a 003 não precisa saber de escopo, arquivo nem
habilitação; a troca do catálogo vazio por este serviço é só de adapter.

**Alternatives considered**: devolver também os desabilitados com uma marca (a porta da 003 é um conjunto de nomes; mudar
a forma mudaria a 003).

## R14 — Saúde por servidor (FR-011)

**Decision**: `check(alias, owner=None)` ignora o cache e faz uma sessão completa: resolve a credencial, conecta (com a
política de rede), inicializa e lista as tools, dentro do prazo do servidor. Devolve `ServerHealth(ok, detail, tools,
missing)` — o que o servidor anuncia e o que a allowlist pede e ele não anuncia. Servidor desabilitado ou sombreado
responde `ok=False` com o motivo, sem conectar. A 008 expõe por servidor; a 011 pode agregar os globais como itens não
críticos (011 FR-012) — decisões das passadas delas.

**Rationale** (FR-011; Edge Cases: "referência de credencial inválida: erro explícito na chamada e no health check"):
uma operação que exercita o caminho real inteiro, e a lista de tools é o que o operador precisa para escrever a
allowlist (R11).

**Alternatives considered**: saúde só por TCP (passaria com credencial errada); saúde a partir do cache (diria "ok" por
até 300 s depois de o servidor cair).

## R15 — Trace

**Decision**: este módulo não emite no Trace Sink nesta fase. A descoberta devolve as falhas em `Discovery.unavailable`
e as chamadas devolvem `ToolResult`; quem registra tool, latência e falha de MCP no trace é a 004 (FR-014 dela).

**Rationale** (ADR-013: o emissor é quem tem o contexto da execução; 004 Edge Cases): um evento só, emitido por quem
sabe a qual execução e a qual Assistant ele pertence; e nada aqui pode vazar credencial para o trace.

**Alternatives considered**: emitir também aqui (eventos duplicados por chamada, e a 007 precisaria do id de requisição).

## R16 — Testes

**Decision**:

- `unit/` — domínio puro: validação do rascunho e da entrada do arquivo (tabela de R11), gramática do alias, política de
  rede com a tabela de vetores de SSRF e propriedades com hypothesis (nenhum IP fora de `is_global` passa para usuário),
  visibilidade (dono, `user_access`, sombreamento), mapeamento e corte do resultado.
- `contract/` — os três seams com adapters em memória: CRUD e isolamento entre usuários (SC-004), somente leitura do
  arquivo, `aliases`, cliente restrito (alias fora do grant, allowlist, marca de escrita, falha em `unavailable`, cache
  com relógio fixo e invalidação por versão); cada porta contra o adapter em memória e o real — `McpServerStore` contra
  Postgres (`AI_CORE_TEST_POSTGRES_DSN`), `SecretResolver` contra o ambiente, `DnsResolver` contra o do sistema,
  `McpTransport` contra um servidor MCP de verdade (o servidor do próprio SDK, servido por uvicorn em `127.0.0.1`,
  alcançado como global pela exceção de hosts internos) e contra um servidor `stdio` em script Python.
- `integration/` — suíte de SSRF de ponta a ponta pelo transporte real com DNS fixo (nomes que resolvem para privadas,
  IPv4 mapeado, decimal, `localhost`, redirecionamento e nova resolução) — 100% bloqueados (SC-002); varredura de
  segredos no banco e nos logs capturados depois de chamadas autenticadas (SC-001).

**Rationale** (princípio XIII: toda porta com conformidade contra o adapter real; SC-001–SC-004 mensuráveis): o servidor
do SDK testa o protocolo de verdade sem serviço externo, e a exceção de hosts internos é exercitada no mesmo teste.

**Alternatives considered**: só servidores falsos em memória (não pegaria incompatibilidade de protocolo nem a política
aplicada na conexão real).

## R17 — Imagens no resultado (ADR-044, itens 2 e 3; FR-016, FR-017)

**Decision**: `RemotePart` ganha `mime: str | None` e `data: bytes | None`. O adapter do SDK (`sdk_session._part`)
decodifica `ImageContent` (`type: "image"`, `mimeType`, `data` em base64): base64 inválido vira `RemotePart(kind="image",
mime=…)` sem bytes. Em `domain/results.py`, `to_tool_result(remote, max_bytes=…, max_attachment_bytes=…)` leva cada parte
de imagem com bytes, tipo em `ATTACHMENT_MIME_TYPES` e tamanho no teto para `ToolResult.attachments`, na ordem, sem
repetir `id`, e não escreve nada no texto por ela; a parte recusada vira `[conteúdo image omitido: <motivo>]` —
`tipo <mime> não aceito`, `<n> bytes acima do teto de <teto>` ou `imagem inválida`. O corte de `max_response_bytes`
continua só no texto. `McpService` recebe `max_attachment_bytes` (default `DEFAULT_MAX_ATTACHMENT_BYTES` = 2 MiB, em
`api.py`) e o teto do transporte passa a `max_response_bytes + TRANSPORT_SLACK_BYTES + 4 × base64(max_attachment_bytes)`.
O transporte em memória aceita resultados programados com partes de imagem.

**Rationale** (ADR-044: "a 007 preserva a parte de imagem"; "o teto de texto do gateway não conta os anexos"): a marca
no texto é da 004, que conhece o `id` e o `alt` e cerca o texto; a 007 só separa bytes de texto e recusa o que não pode
sair. O teto do transporte continua sendo o limite de memória de uma chamada — sem a folga, um PNG de 2 MiB (2,7 MiB em
base64) derrubaria a chamada inteira.

**Alternatives considered**: a 007 escrever a marca `[imagem <id> …]` no texto (duas specs escreveriam a mesma marca, e
tool nativa de pack, que não passa pela 007, ficaria sem ela); limitar a quantidade de imagens por resultado (o ADR não
pede; o teto do transporte já limita o total); contar as imagens em `max_response_bytes` (o ADR o recusa: o teto é do
texto que o modelo lê).


## Incremento: delegação MCP por execução (2026-10-29)

Regido por [ADR-055](../../docs/adr/ADR-055-autenticacao-mcp-delegada.md). Protocolo 1: um MCP delegado por grant, identidade confidencial por execução, sem cache compartilhado e sem alteração da ACL. Contrato: [delegação](../007-core-mcp-integration/contracts/delegation.md). Casos D01 isolamento concorrente; D02 falha fechada; D03 metadados e superfície privada; D04 segredo ausente de persistência/trace; D05 regressão estática.
