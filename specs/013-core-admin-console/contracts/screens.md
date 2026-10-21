# Contrato — telas, chamadas e estados

Cada tela usa só as rotas de [admin-api.md](../../008-core-http-api/contracts/admin-api.md) (e o protocolo da 012 para
entrar e sair). Toda tela tem os estados: **carregando** (esqueleto com a forma final), **vazio** (explica de onde vêm
os dados), **erro** (mensagem da API + "Tentar de novo"), **acesso negado** (404 do `/me`). Recusas aparecem junto ao
campo do `param` (FR-001). Referência visual: Penpot, "Console — claro" e "Console — escuro".

| Rota | Chamadas | Ações | Estados específicos |
|---|---|---|---|
| `/callback` | protocolo da 012 | — | erro de login → volta ao início do login |
| (shell) | `GET /me` | sair (`end_session`); trocar tema | 404 → página "Sua conta não tem acesso à console" (sem barra lateral, sem dado administrativo — SC-007) |
| `/uso` | `GET /usage` (período, `by`, `origin`, `tz` da API) | trocar período 7/30/90, agrupamento, origem | "Incompleto: N modelo sem preço" + link para `/uso/precos`; marcos de mudança no gráfico (preço novo; sobreposição gravada — do histórico); vazio "Nenhuma chamada de modelo neste período" |
| `/uso/precos` | `GET /prices`, `GET /prices/unpriced`, `POST /prices` | novo preço (modelo, entrada, saída, vigente desde) | aviso "data no passado recalcula o custo"; modelos usados sem preço destacados |
| `/assistentes` | `GET /assistants` | buscar; filtrar (todos, sobrepostos, com problema) | selos: Sobreposto (autor e data), Sobreposição inativa, Travado, Indisponível + motivo |
| `/assistentes/:nome/modelos` | `GET /assistants/{nome}`, `PUT …/models`, `DELETE …/overrides/models`, `POST …/models/check` | trocar modelo por papel; testar; salvar; descartar (confirmação na própria tela) | travado ("Só muda por novo deploy" + o que o YAML define); sobreposição inativa com motivo; conflito de versão (rascunho preservado) |
| `/assistentes/:nome/mcp` | `GET /assistants/{nome}`, `GET /mcp`, `GET /mcp/{alias}/health`, `PUT …/mcp`, `DELETE …/overrides/mcp` | ligar servidor; marcar tools permitidas e de escrita | escrita bloqueada em Assistant público (aviso); servidor indisponível com motivo, tools já marcadas visíveis |
| `/assistentes/:nome/permissoes` | `GET /assistants/{nome}`, `GET /keys`, `GET /groups`, `PUT …/auth`, `DELETE …/overrides/auth` | ligar e desligar "Login" e "Chave de API"; adicionar entrada (sugestões de sistemas e grupos, `user:` digitado; `*` à parte só em público); remover; salvar; descartar (confirmação na própria tela) | travada; inativa com motivo; conflito de versão; entradas "sem correspondência" e "não entra com os esquemas ligados"; salvar desabilitado sem esquema ou sem entrada (US10, ADR-040) |
| `/assistentes/:nome/historico` | `GET /assistants/{nome}/history` | — | vazio "Nenhuma sobreposição gravada" |
| `/servidores-mcp` | `GET /mcp`, `GET /mcp/{alias}/health`, `POST`, `PUT`, `DELETE /mcp/{alias}` | novo servidor; editar; remover | do arquivo do operador: somente leitura; credencial ausente: motivo, sem valor |
| `/observabilidade` | `GET /observability`, `PUT /observability/langfuse`, `PUT /observability/capture`, `POST /observability/langfuse/test` | editar endereço e chaves; ligar envio; testar conexão; ligar captura (aviso + "Li e quero capturar o texto") | campo "Definido na instalação" somente leitura; segredo só "definido"; `master_key_missing` explicado |
| `/acesso/usuarios` | `GET /users`, `POST /users`, `PATCH /users/{u}`, `POST …/password`, `…/disable`, `…/enable`, `DELETE …/google` | cadastrar; editar; redefinir senha; desativar e reativar; desfazer vínculo Google | diálogo de pessoa cadastrada com a senha temporária uma vez; último admin protegido (`protected_group`) |
| `/acesso/grupos` | `GET /groups`, `POST /groups`, `DELETE /groups/{g}`, `PUT /groups/{g}/members` | criar; apagar; membros | grupo de administração com "Protegido", sem apagar |
| `/acesso/login` | `GET /login-settings`, `PUT /login-settings` | ligar e desligar o Google; copiar o endereço de retorno | sem cliente Google: opção desabilitada com a explicação; "Definido na instalação" |
| `/acesso/chaves` | `GET /keys`, `POST /keys`, `POST /keys/{id}/rotate`, `DELETE /keys/{id}` | criar chave (nome do sistema, rótulo); rotacionar e revogar (confirmação na linha) | diálogo com a chave em claro uma vez ("Copiar", aviso, "Concluir"); ativas antes das revogadas; `409 key_revoked` com o motivo; vazio "Nenhuma chave" (US9, ADR-040) |

Formatos: números `pt-BR`; dinheiro "US$ 41,87"; tokens compactos ("21,1 M"); datas no fuso da API.


## Marca (US8, FR-020 reescrita; ADR-038, ADR-039; research R15–R18)

| Lugar | Sem marca da instalação (`instance.custom` falso) | Com marca da instalação |
|---|---|---|
| Barra lateral, topo | símbolo Axon de 32px + wordmark `axon` (altura de x de 12px) + "Console" | logotipo ou inicial de 24px + nome + "Console" |
| Barra lateral, rodapé | nada | símbolo de 16px + "com Axon" (caption terciário) |
| Trilho (< 1100px) | só o símbolo | só o logotipo ou a inicial; a atribuição só com o símbolo |
| Acesso negado | lockup Axon (32px de altura) | lockup Axon (a console não lê o `me` sem permissão) |
| Aba | favicon do símbolo; "<tela> · Axon" | favicon do símbolo; "<tela> · <nome da instalação>" |

Cada imagem existe nas duas versões (para fundo claro e escuro), e o CSS mostra a do tema em vigor, inclusive com o tema
escolhido na console. Tokens do `DESIGN.md`, os mesmos das páginas da 012; o hover do botão primário no escuro é
`#1D4ED8` (ADR-039).
