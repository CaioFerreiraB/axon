# Contrato — páginas do provedor

Desenho aprovado no Penpot, página "Login e conta" (celular primeiro; desktop; tema escuro por `prefers-color-scheme`).
HTML servido pelo módulo, sem script, CSS próprio (`/oauth2/assets/identity.<hash>.css`), nome e logotipo da instalação
(`AXON_DISPLAY_NAME`, `AXON_LOGO_FILE` servido em `/oauth2/assets/logo`; FR-023). Toda página tem `lang="pt-BR"`, rótulos ligados aos campos,
foco visível e atende WCAG 2.2 AA.

## Login — `GET /oauth2/authorize` (sem sessão) e `POST /oauth2/login`

| Elemento | Conteúdo |
|---|---|
| Título | "Entrar" · "Use a conta que a sua equipe criou para você." |
| Campos | `identifier` ("Usuário ou e-mail", `autocomplete="username"`), `password` (`autocomplete="current-password"`) |
| Ocultos | `request` (id do pedido pendente), `csrf` |
| Ações | "Entrar" (primária); "Entrar com Google" (link para `/oauth2/google/start?request=…`) só com o Google ligado e configurado |
| Rodapé | "Esqueceu a senha? Peça a um administrador para redefinir." |
| Erro genérico | "Não foi possível entrar com esses dados" + "Confira o usuário e a senha e tente de novo. Depois de 5 tentativas, o login fica bloqueado por 15 minutos." — o mesmo para usuário inexistente, senha errada, conta desativada e bloqueio (FR-003, FR-013); status `401`, mesma ordem de tempo |
| Google recusado | "Conta Google não cadastrada" + o e-mail e a orientação; para e-mail não verificado ou vínculo divergente, "Não foi possível entrar com essa conta Google" (sem detalhar) |
| Pedido vencido (10 min) | "O link de login expirou" + "Volte ao aplicativo e entre de novo." Sem redirecionar: o pedido vencido não autoriza mais nenhum `redirect_uri` |

## Troca de senha obrigatória — `POST /oauth2/password`

Mostrada depois de um login com senha temporária, antes de qualquer código. Campos `new_password`, `confirm`
(`autocomplete="new-password"`), `request`, `csrf`. Erros junto ao campo: tamanho fora de 12–128, confirmação diferente,
igual à temporária. Sucesso: grava, cria a sessão e segue o pedido.

## Minha conta — `GET /oauth2/account` e `POST /oauth2/account`

Exige sessão (sem ela, mostra o login com retorno para a própria página). Mostra nome, usuário, e-mail, grupos e o
vínculo Google (somente leitura, "mantidos pelos administradores"). Formulário "Trocar senha": `current_password`,
`new_password`, `confirm`, `csrf`. Senha atual errada conta para o bloqueio. Sucesso: "Senha trocada. As suas outras
sessões foram encerradas." Link "Sair" (`/oauth2/logout`). Conta só Google: sem o formulário, com a explicação.

## Erro do protocolo

Cliente ou `redirect_uri` inválidos: "Este link de login não é válido" e o motivo curto; nunca redireciona.

## Saída

"Você saiu" quando o logout não tem `post_logout_redirect_uri` válido.
