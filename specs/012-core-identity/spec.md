# Feature Specification: Provedor de identidade da plataforma

**Feature Branch**: `012-core-identity`

**Created**: 2026-10-13

**Status**: Draft

**Input**: Pedido do mantenedor (2026-10-13): login por usuário e senha, com login Google opcional, sem Keycloak; a
plataforma emite os tokens que o Open WebUI repassa e que a console usa; ADR-030, ADR-031, ADR-033. Fase 9, incremento
9.5 (2026-10-20): identidade Axon — ADR-037, ADR-038. Fase 9, incremento 9.7 (2026-11-04): apagar conta em cascata,
um grupo de cada vez e gestão de contas por quem não administra — ADR-057, ADR-058.

## Module Boundary *(mandatory)*

- **Módulo**: Identity — mantém as contas e os grupos da instalação, autentica pessoas (senha ou Google) e emite os
  tokens OIDC da plataforma.
- **Repositório / distribuição**: `axon-ai` → `axon_ai/identity/`. Os endpoints do protocolo e a página de login são o
  adapter primário HTTP do módulo (`adapters/`), montado pela composition root (011) no mesmo app da 008; os
  subcomandos `users` e `identity` ficam em `adapters/cli.py`, registrados pela 011.
- **Consome (seams)**: nenhum. O nome do grupo de administração chega como configuração, pela composition root (011),
  que o lê de onde o operador o declara.
- **Expõe (seams)**: **Account Admin** (usuários, grupos, associação, vínculo Google; desde 2026-11-04, também apagar
  conta, um grupo de cada vez e a indicação de que o ator não administra) — consumido pela 008 (superfície
  de administração) e pela linha de comando; **Login Settings** (login Google ligado ou desligado e de onde vem o
  ajuste) — consumido pela 008; **Public Key Set** (as chaves públicas vigentes do emissor) — consumido pela 011, que o
  injeta no verificador OIDC da 003. Fora do processo, expõe o **protocolo OIDC** a clientes declarados pelo operador
  (Open WebUI, console 013).
- **Depende de infraestrutura (via portas)**: armazenamento (contas, grupos, sessões, códigos, tokens de renovação,
  chaves de assinatura, ajustes), relógio, aleatoriedade, segredos de instalação (cliente Google, segredos dos clientes
  OIDC), cifra com a chave mestra da instalação, rede (provedor Google), contadores de tentativas de login; desde
  2026-11-04, o **apagamento dos dados de um subject nos outros módulos**, por uma porta própria que a composition root
  (011) monta a partir dos seams deles (ADR-058).
- **Não conhece**: Assistants, ACL, Execution Grant, chaves de API, a API HTTP da 008, o motor, qualquer domínio. Não
  decide o que um grupo pode fazer: só diz a que grupos uma pessoa pertence. *(Acréscimo de 2026-11-04.)* Não conhece
  escopos nem chaves: sabe só se o ator administra, como um sim ou não dado por quem chama (ADR-057, item 4); e não sabe
  o que cada apagador dos outros módulos apaga — só o nome dele, as contagens e os avisos que ele devolve.
- **Substituição**: preservar os seams acima e o que os tokens carregam (emissor, audiência por cliente, nome de
  usuário e grupos); armazenamento, biblioteca de protocolo e forma da página de login são livres.
- **Insumo técnico**: [design.md](design.md); [ADR-030](../../docs/adr/ADR-030-a-plataforma-e-o-provedor-de-identidade.md),
  [ADR-031](../../docs/adr/ADR-031-superficie-de-administracao.md),
  [ADR-033](../../docs/adr/ADR-033-segredos-de-runtime-cifrados-com-a-chave-mestra.md),
  [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md),
  [ADR-015](../../docs/adr/ADR-015-persistencia-postgres-por-modulo.md),
  [ADR-020](../../docs/adr/ADR-020-segredos-uma-fonte-por-perfil-uma-porta-por-modulo.md);
  [ADR-057](../../docs/adr/ADR-057-escopos-da-chave-de-api.md),
  [ADR-058](../../docs/adr/ADR-058-apagar-conta-em-cascata.md) (substitui o item 7 do ADR-030),
  [ADR-059](../../docs/adr/ADR-059-o-que-fica-do-apagamento-e-pseudonimizado.md) (pseudônimo; refina o item 6 do ADR-058).

## Clarifications

### Session 2026-10-13

- Q: Uma pessoa comum (não admin) pode trocar a própria senha sozinha? → A: Sim, numa página "Minha conta" servida pela própria identidade (como a de login), informando a senha atual; usuários comuns não usam a console.
- Q: Quanto tempo uma pessoa fica logada antes de precisar entrar de novo? → A: 30 dias de sessão absoluta no provedor; o token de acesso continua de 10 minutos e se renova dentro da sessão.
- Q: Ao cadastrar uma pessoa ou redefinir a senha dela, quem define a senha temporária? → A: A plataforma gera uma senha aleatória forte, devolvida uma única vez na resposta da operação, para o admin repassar; o admin não digita senha.
- Q: Na página de login, a pessoa entra com o nome de usuário, com o e-mail ou com qualquer um dos dois? → A: Com qualquer um dos dois; ambos são únicos, e o e-mail é comparado sem diferenciar maiúsculas.
- Q: Que nome aparece na página de login, vista também por quem usa o chat? → A: O nome da instalação, definido pelo operador, com logotipo opcional; sem ele, um nome neutro da plataforma. Nada de domínio no core (princípio I). As páginas são desenhadas primeiro para celular.

### Session 2026-10-20

- Q: Que marca as páginas do provedor mostram depois do renome (ADR-038)? → A: Sem nome nem logotipo próprios da instalação, o lockup Axon (símbolo e wordmark `axon`) ocupa o lugar principal do cartão. Com um nome diferente de "Axon" ou um logotipo, eles ocupam o lugar principal, e o rodapé do cartão leva o símbolo pequeno e "com Axon". O favicon é sempre o símbolo Axon. O nome padrão da instalação passa de "Agentic" a "Axon". Vale para login, troca de senha, "Minha conta", erro e saída. A FR-023 é reescrita com isso.
- Q: As cores das páginas mudam? → A: Sim. Os tokens passam aos do `DESIGN.md` (ADR-038, item 4): neutros frios da marca no claro e `axon-night` (`#0B0F19`) com superfícies derivadas no escuro, com o mesmo azul de ação (`#2563EB`), os mesmos estados e o contraste AA de antes. Os valores são iguais aos da console (013), que muda na passada dela.
- Q: Quais identificadores do provedor mudam de nome? → A: O cookie da sessão (`axon_session`; `__Host-axon_session` quando seguro), o realm do `WWW-Authenticate: Basic` (`axon`), o rótulo da subchave que sela as chaves de assinatura (`axon-ai/identity/v1`) e o contexto do CSRF de "Minha conta" (`axon-ai/identity/csrf:`) (ADR-037, item 2).
- Q: O que acontece com o que foi criado com os nomes antigos? → A: Corte seco, sem migração (ADR-037, item 3). O cookie antigo não é lido, então todo mundo entra de novo; "Minha conta" aberta antes da troca leva ao login (o CSRF dela deriva da sessão, que já não é lida). Uma chave de assinatura selada com o rótulo antigo não abre: a identidade não sobe, e a mensagem do boot aponta `axon identity keys rotate --force` (o caminho que já existe para chave mestra perdida, que encerra as sessões), dizendo também que a chave pode ter sido selada antes do renome. Contas, grupos e senhas não dependem de nenhum desses nomes e continuam.

### Session 2026-11-04

- Q: Depois que uma conta é apagada, o que fica guardado sobre o que ela fez? → A: Ficam os registros da plataforma — a auditoria de tools de escrita (004), o uso, o custo e o impacto (009), os históricos de mudança —, mas **nenhum dado que identifique a conta**: onde eles citam a pessoa apagada (o subject, o nome de usuário como autor de uma mudança), a citação é trocada por um pseudônimo opaco e aleatório, o mesmo em todos os módulos para aquela conta, que não é um nome de usuário possível. A trilha continua ligando as ações entre si, sem dizer de quem eram. Revê o item 6 do ADR-058, como ele mesmo previa ([ADR-059](../../docs/adr/ADR-059-o-que-fica-do-apagamento-e-pseudonimizado.md): pseudônimo `deleted:<16 hex>`).
- Q: Quando um dos módulos falha no meio do apagamento, a operação termina com erro ou devolve um relatório do que faltou? → A: Erro, levando o relatório parcial (o que saiu e qual apagador falhou): a API responde com uma falha que pede nova tentativa, e a linha de comando sai com código 1.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Pessoa entra no chat com usuário e senha (Priority: P1)

Uma pessoa cadastrada abre o Open WebUI, é levada à página de login da plataforma, informa usuário e senha e volta ao
chat já identificada. O Open WebUI repassa à plataforma o token que recebeu, e a pessoa vê exatamente os Assistants que
os grupos dela permitem.

**Why this priority**: É o que substitui o Keycloak. Sem isso, a instalação com interface perde a identidade de quem
conversa e a ACL por grupo da Fase 7.

**Independent Test**: Com dois usuários cadastrados em grupos diferentes, fazer o fluxo de login de um cliente
confidencial contra a plataforma e chamar a listagem de Assistants com cada token; as listas diferem pelo Assistant
restrito ao grupo.

**Acceptance Scenarios**:

1. **Given** um usuário ativo com senha definida, **When** ele entra pela página de login a partir do Open WebUI, com o
   nome de usuário ou com o e-mail, **Then** volta ao Open WebUI com um token cujo nome de usuário é o dele e cujos grupos
   são os da conta.
2. **Given** o token recebido pelo Open WebUI, **When** é repassado à superfície pública da API, **Then** a 003 o
   aceita sem consultar nenhum serviço externo à plataforma.
3. **Given** usuário inexistente, senha errada ou conta desativada, **When** a pessoa tenta entrar, **Then** vê a mesma
   mensagem genérica, e as três respostas são indistinguíveis em status, corpo e ordem de grandeza de tempo.
4. **Given** uma instalação sem a console, **When** o Open WebUI inicia o login, **Then** a página de login existe e
   funciona igual.

---

### User Story 2 - Operador cria o primeiro admin, e admins gerem contas e grupos (Priority: P1)

Numa instalação nova, o operador cria o primeiro administrador pela linha de comando ou por variáveis da instalação.
Depois, administradores cadastram pessoas (usuário, e-mail, nome, grupos e senha temporária), alteram grupos, redefinem
senhas, desativam e reativam contas, criam e apagam grupos.

**Why this priority**: Sem cadastro não há quem entre: o login Google só aceita contas cadastradas, e não há
autocadastro.

**Independent Test**: Numa instalação sem usuários, criar o admin pela linha de comando, entrar com ele e cadastrar uma
segunda pessoa num grupo; a segunda pessoa entra, é obrigada a trocar a senha temporária e recebe um token com o grupo.

**Acceptance Scenarios**:

1. **Given** uma instalação sem nenhum usuário e as variáveis de admin inicial definidas, **When** a plataforma sobe,
   **Then** o admin é criado no grupo de administração; **Given** já existe algum usuário, **Then** as variáveis são
   ignoradas, com aviso no boot.
2. **Given** um admin, **When** cadastra uma pessoa, **Then** recebe uma senha temporária gerada pela plataforma, uma
   única vez; no primeiro login, a pessoa precisa definir uma senha nova antes de receber qualquer token.
3. **Given** uma pessoa num grupo, **When** um admin a tira do grupo, **Then** o próximo token emitido para ela (login
   ou renovação) já não traz o grupo.
4. **Given** uma conta desativada, **When** alguém tenta cadastrar outra conta com o mesmo nome de usuário, **Then** o
   cadastro é recusado: o nome de uma conta desativada não é reaproveitado (só o de uma conta apagada, US9).
5. **Given** o último membro ativo do grupo de administração, **When** um admin tenta desativá-lo ou tirá-lo do grupo,
   **Then** a operação é recusada com o motivo; e o grupo de administração não pode ser apagado.
6. **Given** uma pessoa com senha, **When** abre a página "Minha conta", informa a senha atual e uma nova válida,
   **Then** a senha muda, as outras sessões dela terminam e a atual continua; senha atual errada é recusada e conta para
   o bloqueio da FR-013.

---

### User Story 3 - A console entra com audiência própria (Priority: P1)

A console de administração é um cliente público: inicia o login com prova de posse do código (PKCE), recebe um token
cuja audiência é só a da administração e o usa na superfície de administração. O token que o Open WebUI guarda tem
outra audiência e não serve para administrar.

**Why this priority**: É o que permite à console existir sem segredo no navegador e sem que um token do chat vire acesso
administrativo (ADR-031).

**Independent Test**: Fazer o fluxo de cliente público com e sem PKCE; sem PKCE é recusado. Com PKCE, comparar a
audiência do token da console com a do token do Open WebUI para o mesmo usuário.

**Acceptance Scenarios**:

1. **Given** o cliente público da console, **When** o pedido de autorização chega sem desafio PKCE, **Then** é recusado.
2. **Given** um admin que entra pela console, **When** recebe o token, **Then** a audiência é a da administração e não
   a do chat.
3. **Given** um endereço de retorno que não está registrado para o cliente, **When** o pedido chega, **Then** a
   plataforma mostra uma página de erro e não redireciona para lugar nenhum.
4. **Given** a console, **When** a pessoa sai, **Then** a sessão no provedor termina e os tokens de renovação dessa
   sessão deixam de valer.

---

### User Story 4 - Login com Google só para quem está cadastrado (Priority: P2)

Se a instalação tem um cliente Google configurado e um admin liga o login Google, a página de login mostra "Entrar com
Google". Uma conta Google só entra se o e-mail dela, verificado pelo Google, for o de uma conta ativa da plataforma; no
primeiro sucesso, a conta Google fica vinculada a essa pessoa.

**Why this priority**: Reduz senhas para quem já tem conta Google, sem abrir a instalação para qualquer pessoa.

**Independent Test**: Com um provedor Google simulado, entrar com três identidades: e-mail cadastrado e verificado,
e-mail cadastrado mas não verificado, e e-mail desconhecido. Só a primeira recebe token; nenhuma conta nova é criada.

**Acceptance Scenarios**:

1. **Given** login Google ligado e uma conta ativa com o e-mail `ana@exemplo.org`, **When** essa pessoa entra pelo
   Google com o mesmo e-mail verificado, **Then** recebe um token da plataforma como `ana`, e a conta Google fica
   vinculada.
2. **Given** um e-mail que não pertence a nenhuma conta ativa, **When** a pessoa entra pelo Google, **Then** vê "conta
   Google não cadastrada" e nenhuma conta é criada.
3. **Given** uma conta já vinculada a uma conta Google, **When** outra conta Google com o mesmo e-mail tenta entrar,
   **Then** é recusada.
4. **Given** login Google desligado, ou a instalação sem cliente Google, **When** a página de login abre, **Then** o
   botão não aparece, e o início do fluxo Google é recusado.
5. **Given** a instalação sem cliente Google, **When** um admin tenta ligar o login Google, **Then** a operação é
   recusada explicando que falta a configuração da instalação.

---

### User Story 5 - Tentativas repetidas são contidas (Priority: P2)

Falhas seguidas de login para o mesmo usuário ou da mesma origem bloqueiam novas tentativas por um tempo, sem revelar se
o usuário existe.

**Why this priority**: A página de login fica exposta na internet; sem isso, a senha é adivinhável.

**Independent Test**: Errar a senha cinco vezes seguidas e confirmar que a sexta tentativa, mesmo com a senha certa, é
recusada com a mensagem genérica até o bloqueio passar; repetir com um usuário inexistente e obter as mesmas respostas.

**Acceptance Scenarios**:

1. **Given** cinco falhas em quinze minutos para um usuário, **When** chega a sexta tentativa, **Then** é recusada por
   quinze minutos com a mesma mensagem genérica, mesmo com a senha certa.
2. **Given** um usuário inexistente, **When** chegam as mesmas tentativas, **Then** as respostas são as mesmas que as de
   um usuário existente.

---

### User Story 6 - Desativar alguém corta o acesso (Priority: P2)

Um admin desativa uma conta. A pessoa não entra mais, nenhuma sessão dela renova token, e o acesso termina no máximo
quando o último token de acesso expira.

**Why this priority**: É o controle de saída de quem deixa a organização.

**Independent Test**: Com um usuário logado, desativá-lo; a renovação seguinte é recusada, e um login novo também.

**Acceptance Scenarios**:

1. **Given** um usuário com sessão aberta, **When** é desativado, **Then** a renovação de token seguinte é recusada e as
   sessões dele terminam — com sessões de 30 dias, a desativação é o que corta o acesso antes do fim da sessão.
2. **Given** o mesmo usuário reativado, **When** entra de novo, **Then** recebe token normalmente, com os grupos atuais.

---

### User Story 7 - Chave de assinatura trocada sem derrubar ninguém (Priority: P3)

O operador troca a chave que assina os tokens. Tokens emitidos com a chave anterior continuam aceitos até expirar, e os
novos saem com a nova.

**Why this priority**: Higiene de segurança e caminho de recuperação; pouco frequente.

**Independent Test**: Emitir um token, rotacionar a chave, verificar que o token antigo ainda é aceito e que um novo
token sai com outro identificador de chave.

**Acceptance Scenarios**:

1. **Given** um token vigente, **When** a chave é rotacionada, **Then** o token continua aceito até expirar.
2. **Given** a rotação forçada (chave mestra perdida), **When** executada, **Then** todas as sessões terminam e as
   pessoas precisam entrar de novo.

---

### User Story 8 - Identidade Axon: as páginas de login com a marca da plataforma (Priority: P2)

A plataforma passa a se chamar Axon (ADR-037, ADR-038). Numa instalação sem marca própria, quem entra vê o lockup Axon no cartão de login. Numa instalação com nome ou logotipo, vê a marca da organização no lugar principal e, discreto no rodapé, "com Axon". A aba do navegador mostra sempre o símbolo Axon. As cores seguem a marca nos dois temas, sem perder contraste.

**Why this priority**: É o único lugar em que a marca da plataforma aparece para quem não abre a console; e os identificadores do provedor (cookie, rótulos) precisam do nome novo antes da instalação passar à tag nova. P2 porque nenhum fluxo de login muda.

**Independent Test**: Abrir o login sem nome nem logotipo da instalação e ver o lockup Axon e o favicon; definir um nome próprio e ver o nome no lugar principal e "com Axon" no rodapé; entrar e ver o cookie `axon_session`; subir com uma chave de assinatura selada com o rótulo antigo e ver a identidade recusar o boot com a orientação de rotação forçada.

**Acceptance Scenarios**:

1. **Given** uma instalação sem nome nem logotipo próprios, **When** alguém abre o login, a troca de senha, "Minha conta", a página de erro ou a de saída, **Then** o lockup Axon ocupa o lugar principal do cartão, nenhuma atribuição aparece no rodapé, e o título da aba termina em "Axon".
2. **Given** uma instalação com um nome próprio (diferente de "Axon") ou um logotipo, **When** alguém abre essas páginas, **Then** o nome e o logotipo da instalação ocupam o lugar principal, e o rodapé do cartão mostra o símbolo Axon pequeno e "com Axon".
3. **Given** qualquer uma das páginas, **When** o navegador pede o ícone, **Then** recebe o símbolo Axon, com ou sem marca da instalação.
4. **Given** as páginas nos temas claro e escuro, **When** se mede o contraste de texto, campos e botões, **Then** todo par atende WCAG 2.2 AA, com os tokens da marca.
5. **Given** um login bem-sucedido, **When** a resposta chega, **Then** o cookie de sessão se chama `__Host-axon_session` (ou `axon_session` em desenvolvimento sem HTTPS), e um cookie `aic_session` que o navegador ainda mande é ignorado.
6. **Given** uma troca de código no endpoint de token com credencial de cliente errada, **When** a resposta é 401, **Then** o desafio é `Basic realm="axon"`.
7. **Given** uma instalação persistente cuja chave de assinatura foi selada com o rótulo antigo, **When** a plataforma sobe, **Then** a identidade não sobe e a mensagem aponta `axon identity keys rotate --force`; **When** o operador roda o comando, **Then** a plataforma sobe com uma chave nova, e todas as sessões terminam.

---

### User Story 9 - Apagar uma conta, em cascata (Priority: P1)

Um admin apaga a conta de quem deixou a organização ou pediu para sair. A plataforma apaga o que guarda daquela pessoa
em cada módulo — na identidade, a conta, as sessões, os códigos, os tokens de renovação, o vínculo Google e as
associações a grupos; nos outros, pelos apagadores que a composição liga (Assistants e chaves dela, servidores MCP,
conversas e anexos) — e devolve um relatório do que saiu. Ao fim, o nome de usuário fica livre: uma conta nova com o
mesmo nome não herda nada. Desativar continua existindo para "tirar o acesso e guardar" ([ADR-058](../../docs/adr/ADR-058-apagar-conta-em-cascata.md)).

**Why this priority**: É o pedido do incremento. Hoje a conta só se desativa, e o e-mail, o nome, as conversas e os
anexos ficam guardados para sempre, com o nome preso.

**Independent Test**: Com dois apagadores de teste ligados à porta, uma conta com sessão aberta e num grupo: apagar. O
relatório lista cada apagador com as contagens; a renovação seguinte da sessão é recusada; a conta não aparece mais; uma
conta nova com o mesmo nome e outro e-mail é cadastrada. Com um apagador que falha, a conta fica "em apagamento" (não
entra, não aparece como ativa, nome preso), o relatório diz o que faltou, e repetir o apagamento conclui.

**Acceptance Scenarios**:

1. **Given** uma conta com sessões abertas, tokens de renovação e um grupo, **When** um admin a apaga, **Then** a
   próxima renovação é recusada, nenhum login novo dela é aceito, e a conta, as sessões, os tokens, os códigos, as
   associações e o vínculo Google deixam de existir.
2. **Given** os apagadores dos outros módulos ligados, **When** a conta é apagada, **Then** cada um roda uma vez, na
   ordem em que a composição os declara, e o relatório traz, por apagador, as contagens e os avisos que ele devolveu.
3. **Given** uma conta apagada, **When** um admin cadastra outra com o mesmo nome de usuário, **Then** o cadastro é
   aceito, e a conta nova não tem grupos, sessões nem vínculo da anterior.
4. **Given** um apagador que falha, **When** a conta é apagada, **Then** a conta fica "em apagamento": não entra, não
   renova token, não aparece entre as ativas, não pode ser reativada nem alterada, e o nome continua preso; a operação
   termina com erro, que leva o relatório do que foi apagado e de qual apagador falhou, sem texto de segredo.
5. **Given** uma conta "em apagamento", **When** o apagamento é pedido de novo, **Then** os apagadores rodam outra vez
   (cada um é idempotente) e, sem falha, a conta some e o nome fica livre.
6. **Given** o ator e a própria conta, **When** ele tenta apagá-la, **Then** é recusado com o motivo; **Given** o último
   membro ativo do grupo de administração, **Then** também é recusado (FR-011).
7. **Given** uma conta inexistente, **When** alguém pede para apagá-la, **Then** recebe conta inexistente.
8. **Given** a linha de comando, **When** o operador apaga uma conta, **Then** vale a mesma regra e o mesmo relatório
   (o comando é registrado pela 011).

---

### User Story 10 - Um grupo de cada vez (Priority: P2)

Um sistema de provisionamento põe uma pessoa num grupo ou a tira dele sem reescrever a lista inteira de grupos da conta
nem a de membros do grupo. Duas chamadas ao mesmo tempo, para grupos diferentes da mesma pessoa, não se sobrescrevem.

**Why this priority**: Hoje atribuir um grupo exige mandar a lista inteira (com versão) ou os membros inteiros do
grupo; dois provisionamentos concorrentes perdem um ao outro.

**Independent Test**: Pôr `ana` em `equipe` e, em paralelo, em `vendas`; ela fica nos dois. Pôr de novo em `equipe`:
nada muda, sem erro. Tirar de `vendas`: o próximo token dela não traz `vendas`.

**Acceptance Scenarios**:

1. **Given** uma conta e um grupo existentes, **When** alguém a põe no grupo, **Then** a conta passa a ter o grupo, sem
   versão no pedido, e o próximo token emitido para ela o traz.
2. **Given** a conta já no grupo, **When** a põe de novo, **Then** nada muda e não é erro; o mesmo para tirar de um
   grupo em que ela não está.
3. **Given** duas operações simultâneas em grupos diferentes da mesma conta, **When** as duas concluem, **Then** a conta
   tem o resultado das duas.
4. **Given** um grupo ou uma conta inexistente, **When** alguém tenta a operação, **Then** recebe o inexistente
   correspondente, nomeando qual.
5. **Given** o último membro ativo do grupo de administração, **When** alguém o tira desse grupo, **Then** é recusado
   (FR-011).
6. **Given** uma conta "em apagamento", **When** alguém tenta pôr ou tirar grupo, **Then** é recusado.

---

### User Story 11 - Gestão de contas por quem não administra (Priority: P1)

Um sistema de provisionamento, com a chave de escopo `users` (ADR-057), cria, altera, desativa, reativa e apaga contas
e mexe em grupos — mas nunca nas contas do grupo de administração nem no próprio grupo. Quem chama (a 008) diz à
identidade se o ator administra; a identidade aplica a regra no próprio domínio, sem conhecer escopos nem chaves.

**Why this priority**: Sem essa regra, a chave `users` poderia pôr a si mesma — ou a qualquer conta — no grupo de
administração, ou redefinir a senha de um admin e entrar como ele: o escopo seria administração com outro nome.

**Independent Test**: Com o ator marcado como não administrador: cadastrar e apagar uma conta comum e pô-la num grupo
comum funcionam; cadastrar no grupo de administração, pôr alguém nele, tirar alguém dele, redefinir a senha, desativar,
alterar ou apagar uma conta do grupo de administração, apagar o grupo de administração e definir os membros dele são
recusados, cada um nomeando o motivo.

**Acceptance Scenarios**:

1. **Given** um ator que não administra, **When** cadastra uma conta sem o grupo de administração ou a põe num grupo
   comum, **Then** a operação vale como para um admin.
2. **Given** um ator que não administra, **When** cadastra uma conta com o grupo de administração, põe ou tira alguém
   desse grupo, ou define os membros dele, **Then** é recusado com um erro próprio, que nomeia o campo (`groups`).
3. **Given** um ator que não administra e uma conta que está no grupo de administração, **When** tenta alterá-la,
   redefinir a senha, desativá-la, reativá-la, desfazer o vínculo Google, pô-la ou tirá-la de qualquer grupo ou apagá-la,
   **Then** é recusado com o mesmo erro próprio.
4. **Given** um ator que não administra, **When** define os membros de um grupo comum de modo a pôr ou tirar uma conta
   do grupo de administração, **Then** é recusado; sem tocar essas contas, vale.
5. **Given** um ator que não administra, **When** lista e lê contas e grupos, **Then** vê o mesmo que um admin, inclusive
   as contas e os membros do grupo de administração (só leitura).
6. **Given** um ator que administra, ou a linha de comando, **When** faz qualquer uma dessas operações, **Then** valem as
   regras de hoje, sem a restrição.

---

### Edge Cases

- E-mail igual a outro com maiúsculas diferentes: tratado como o mesmo e-mail; o cadastro é recusado.
- Nome de usuário que é igual ao e-mail de outra conta: impossível por construção — nome de usuário não aceita `@`; o
  campo de login decide entre os dois pela presença de `@`.
- Conta Google vinculada a uma conta que depois é desativada: o login Google é recusado como o de senha.
- Admin troca o e-mail de uma conta vinculada ao Google: o vínculo continua pelo identificador do Google; o admin pode
  desfazê-lo explicitamente.
- Grupo citado no `assistants.yaml` que não existe na identidade: ninguém pertence a ele; nada quebra.
- Grupo apagado: as associações somem e o próximo token das pessoas já não o traz.
- Código de autorização usado duas vezes: a segunda troca é recusada e os tokens emitidos a partir dele são revogados.
- Token de renovação de cliente público usado de novo depois de trocado: toda a família de tokens daquela sessão é
  revogada.
- Duas renovações simultâneas do Open WebUI (cliente confidencial): ambas funcionam, porque o token de renovação do
  cliente confidencial não roda a cada uso.
- A instalação tem identidade ligada e também um emissor externo configurado: erro de configuração no boot (um único
  emissor confiável, ADR-030).
- Perfil persistente com identidade ligada e sem chave mestra: a identidade não sobe, com erro que nomeia a variável.
- Pessoa com senha temporária fecha a página antes de trocá-la: na próxima entrada, a troca continua obrigatória.
- Navegador acessa a plataforma pelo endereço público, e os contêineres pelo endereço interno: o emissor é sempre o
- Instalação com `AXON_DISPLAY_NAME=Axon` e sem logotipo: igual a sem marca própria — o lockup no lugar principal e nenhuma atribuição (o lugar principal já é o Axon).
- Instalação com logotipo e sem nome próprio: o logotipo e o nome padrão "Axon" no lugar principal, e "com Axon" no rodapé (há marca da instalação).
- Apagamento pedido enquanto a pessoa está numa conversa: a execução em curso termina; o token de acesso já emitido
  vale até expirar (10 minutos, como na desativação; ADR-058, item 8), e a renovação já é recusada.
- Dois apagamentos simultâneos da mesma conta: um passa a conta a "em apagamento" primeiro; o outro roda os mesmos
  apagadores idempotentes ou recebe conta inexistente, sem erro de integridade.
- Conta "em apagamento" e o último admin: a conta saiu dos grupos ao entrar em apagamento; a regra do último membro
  ativo é conferida antes, nunca depois.
- Cadastro, durante o apagamento, de outra conta com o mesmo nome: recusado (o nome ainda está preso) até o apagamento
  concluir.
- Ator que não administra e se põe em um grupo comum: vale — a regra protege só o grupo de administração e os membros
  dele.
- Ator que não administra cuja própria conta está no grupo de administração: não acontece pela chave `users` (ela não
  é de pessoa da console), mas, se acontecer, a recusa de tocar contas do grupo de administração vale também para a dele.
- "Minha conta" aberta antes da troca e enviada depois: a sessão do cookie antigo não é lida, e a página leva ao login. O login aberto antes continua valendo: a proteção dele é do pedido pendente, não do nome do provedor.
  endereço público; os endpoints usados servidor a servidor respondem também pelo interno.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O módulo DEVE manter contas com nome de usuário (imutável, minúsculas, letras, dígitos, `.`, `_` e `-`,
  até 64 caracteres), e-mail (obrigatório, único sem diferenciar maiúsculas), nome de exibição, estado (ativa,
  desativada ou em apagamento) e grupos. Uma conta desativada guarda o nome; uma conta só é apagada pela operação da
  FR-028, e só depois do apagamento concluído o nome fica livre. *(Revista em 2026-11-04: o ADR-058 substitui o item 7
  do ADR-030 — antes, contas nunca eram apagadas e nomes nunca eram reaproveitados.)*
- **FR-002**: Senhas DEVEM ter de 12 a 128 caracteres, sem regras de composição, e DEVEM ser guardadas só como hash
  resistente a força bruta. No cadastro e na redefinição por um admin, a plataforma DEVE gerar uma senha temporária
  aleatória forte, devolvida uma única vez na resposta da operação; o admin não escolhe a senha. A pessoa DEVE trocá-la
  no primeiro login, antes de receber qualquer token.
- **FR-003**: O módulo DEVE servir a própria página de login (usuário ou e-mail e senha e, quando ligado, "Entrar com
  Google"), independente da console. O campo de identificação DEVE aceitar o nome de usuário ou o e-mail da conta. Usuário inexistente, senha errada e conta desativada DEVEM receber a mesma resposta, em
  status, corpo e ordem de grandeza de tempo.
- **FR-004**: O módulo DEVE implementar o subconjunto do OIDC: documento de descoberta, autorização só por código,
  troca de código e renovação de token, informações do usuário, chaves públicas, revogação de token e logout. PKCE
  (S256) DEVE ser obrigatório para cliente público. NÃO DEVE haver fluxo implícito, registro dinâmico de cliente nem
  tela de consentimento.
- **FR-005**: Os clientes DEVEM ser declarados pelo operador em configuração versionada, somente leitura para a
  plataforma: identificador, tipo (confidencial ou público), endereços de retorno exatos, endereços pós-logout exatos e
  audiência. O segredo de um cliente confidencial DEVE vir por referência a uma variável da instalação. Endereço de
  retorno não registrado DEVE resultar numa página de erro, sem redirecionar.
- **FR-006**: O token de acesso DEVE ser assinado, durar 10 minutos e trazer emissor, audiência do cliente, nome de
  usuário, grupos e validade; o token de identidade traz também o `nonce` do pedido e o e-mail. O token de renovação
  DEVE ser opaco, guardado só como hash e preso a uma sessão de no máximo 30 dias (absoluta, contada do login). Para cliente público, o token de
  renovação DEVE ser trocado a cada uso, e o reuso de um token já trocado DEVE revogar a família inteira; para cliente
  confidencial, não é trocado.
- **FR-007**: O código de autorização DEVE ser de uso único e valer 60 segundos; uma segunda troca DEVE ser recusada e
  revogar os tokens emitidos a partir dele.
- **FR-008**: O login Google DEVE valer só se a instalação configurar o cliente Google e o login Google estiver ligado.
  Ele DEVE exigir e-mail verificado pelo Google e casar com uma conta ativa; no primeiro sucesso, DEVE vincular o
  identificador da conta Google à conta da plataforma. Conta Google com e-mail desconhecido DEVE ser recusada sem criar
  conta; conta Google diferente da já vinculada DEVE ser recusada. A instalação PODE restringir o domínio aceito.
- **FR-009**: Ligar e desligar o login Google DEVE ser um ajuste de runtime feito pela administração (seam Login
  Settings). Se a instalação define o ajuste por variável, ela prevalece e a administração o vê somente leitura
  (ADR-033). Sem cliente Google configurado, o ajuste NÃO DEVE poder ser ligado.
- **FR-010**: Administradores DEVEM poder, pelo seam Account Admin: listar e buscar contas; cadastrar conta com senha
  temporária ou só para Google; alterar e-mail, nome e grupos; redefinir senha (temporária); desativar e reativar;
  desfazer o vínculo Google; criar, listar e apagar grupos e definir seus membros. Toda operação DEVE registrar quem a
  fez.
- **FR-011**: O grupo de administração, cujo nome o operador declara, DEVE ser protegido: não pode ser apagado, e o
  último membro ativo não pode ser desativado nem retirado dele.
- **FR-012**: Grupos DEVEM ter nomes no mesmo padrão dos nomes de usuário; apagar um grupo DEVE remover as associações.
  Mudança de grupos ou de estado DEVE valer no próximo token emitido para a pessoa.
- **FR-013**: Depois de 5 falhas de login em 15 minutos para um mesmo usuário ou uma mesma origem, novas tentativas DEVEM
  ser recusadas por 15 minutos com a mesma mensagem genérica, sem revelar se o usuário existe. A origem só é lida de
  cabeçalho de proxy quando a instalação declara proxies confiáveis.
- **FR-014**: A sessão no provedor DEVE usar cookie inacessível a scripts, e todo formulário DEVE ter proteção contra
  falsificação de requisição. Logout DEVE encerrar a sessão e revogar os tokens de renovação dela.
- **FR-015**: Desativar uma conta DEVE impedir novos logins e renovações e encerrar as sessões dela; tokens de acesso já
  emitidos continuam válidos até expirar.
- **FR-016**: A chave de assinatura DEVE ser gerada no primeiro boot com identidade ligada, quando não houver nenhuma, e
  guardada cifrada com a chave mestra da instalação (ADR-033). A rotação DEVE manter a chave anterior publicada até que
  todo token emitido com ela tenha expirado; a rotação forçada DEVE encerrar todas as sessões.
- **FR-017**: O seam Public Key Set DEVE devolver, em processo, as chaves públicas vigentes, para a composição injetar
  no verificador da 003 sem chamada de rede da plataforma para si mesma; o endpoint público de chaves DEVE publicar o
  mesmo conjunto.
- **FR-018**: A linha de comando DEVE criar contas em qualquer grupo, inclusive o de administração, lendo a senha sem
  ecoá-la. A instalação DEVE poder declarar um admin inicial por variáveis, aplicado só quando não existe nenhuma conta;
  havendo contas, as variáveis são ignoradas com aviso.
- **FR-019**: O emissor DEVE ser o endereço público da instalação. Os endpoints usados servidor a servidor (troca de
  código, informações do usuário, chaves) DEVEM ser anunciados a partir do endereço pelo qual o pedido de descoberta
  chegou, para que contêineres os alcancem pelo endereço interno.
- **FR-020**: Senhas, códigos, tokens de renovação, segredos de cliente e chaves privadas NÃO DEVEM aparecer em log,
  trace, mensagem de erro nem resposta.
- **FR-021**: Logins aceitos e recusados, bloqueios, recusas do Google e mudanças de conta DEVEM ser registrados em log
  com o nome de usuário (quando existe) e o motivo, sem nenhum segredo.
- **FR-022**: O módulo DEVE servir uma página "Minha conta", acessível a quem tem sessão no provedor, em que a pessoa troca a própria senha informando a atual; a troca DEVE encerrar as outras sessões dela e revogar os tokens de renovação dessas sessões. Conta só para Google não tem senha a trocar. Falha na senha atual conta para o bloqueio da FR-013.
- **FR-023**: A página de login, a troca de senha, "Minha conta", a de erro e a de saída DEVEM mostrar, no lugar principal do cartão, o nome e o logotipo da instalação quando ela definiu um nome diferente de "Axon" ou um logotipo — e então o rodapé do cartão DEVE levar o símbolo Axon pequeno e "com Axon" —; sem isso, o lockup Axon no lugar principal e nenhuma atribuição. O ícone da aba DEVE ser sempre o símbolo Axon, e o nome padrão da instalação, "Axon" (ADR-038; reescrita em 2026-10-20). Essas páginas DEVEM funcionar primeiro em tela de celular e também no computador, e atender WCAG 2.2 AA nos dois temas, com os tokens de cor do `DESIGN.md`, iguais aos da console.

- **FR-024**: O cookie de sessão do provedor DEVE se chamar `axon_session`, com o prefixo `__Host-` quando seguro (ADR-037); o cookie com o nome antigo NÃO DEVE ser lido.
- **FR-025**: O desafio `WWW-Authenticate: Basic` do endpoint de token DEVE usar o realm `axon`.
- **FR-026**: As chaves de assinatura DEVEM ser seladas com a subchave de rótulo `axon-ai/identity/v1`, e o CSRF de "Minha conta" DEVE ser derivado com o contexto `axon-ai/identity/csrf:` (ADR-033, ADR-037). Uma chave selada com outro rótulo NÃO DEVE abrir: a identidade não sobe, e a mensagem DEVE apontar a rotação forçada e citar a chave mestra trocada ou o selo anterior ao renome. Sem migração.
- **FR-027**: Os consumidores no workspace que citam esses nomes — os testes, o e2e da console que entra pelas páginas e os documentos vivos — DEVEM usar os nomes novos na mesma passada (ADR-037, item 7).

- **FR-028**: O seam Account Admin DEVE apagar uma conta ([ADR-058](../../docs/adr/ADR-058-apagar-conta-em-cascata.md)):
  primeiro a conta passa a "em apagamento" — login e renovação recusados, sessões encerradas, tokens de renovação e
  códigos revogados, fora de todos os grupos —; depois rodam, na ordem declarada pela composição, os apagadores dos
  dados do subject nos outros módulos; por fim, a identidade apaga a conta e tudo o que guarda dela (sessões, códigos,
  tokens de renovação, vínculo Google, associações, contadores de tentativas), e o nome fica livre.
- **FR-029**: Se um apagador falhar, a conta DEVE ficar "em apagamento", e a operação DEVE terminar com **erro** — não
  com resultado —, levando o relatório parcial do que foi apagado e do apagador que falhou, sem segredo nem texto interno
  do erro (a 008 o traduz numa falha que pede nova tentativa; a linha de comando sai com código 1); pedir o apagamento de novo DEVE retomar,
  rodando os apagadores outra vez. Não há transação entre os módulos: cada apagador é idempotente.
- **FR-030**: Conta "em apagamento" NÃO DEVE entrar, renovar token, ser reativada, alterada, ter a senha redefinida nem
  ganhar ou perder grupo; NÃO DEVE aparecer entre as contas ativas; e o nome dela NÃO DEVE ser aceito num cadastro novo
  até o apagamento concluir.
- **FR-031**: O apagamento DEVE ser recusado para a própria conta do ator e para o último membro ativo do grupo de
  administração (FR-011), antes de qualquer mudança.
- **FR-032**: O relatório DEVE trazer, por apagador, o nome dele, as contagens e os avisos que ele devolveu, e as
  contagens da própria identidade. A identidade NÃO DEVE interpretar as contagens nem os avisos dos outros módulos.
- **FR-033**: O seam Account Admin DEVE pôr e tirar um grupo de uma conta, um por vez, sem versão, com resultado
  idempotente (pôr de novo ou tirar o que não está não muda nada e não é erro) e sem perder uma mudança concorrente em
  outro grupo da mesma conta; conta ou grupo inexistente DEVE ser recusado nomeando qual. A regra do último membro
  ativo (FR-011) vale.
- **FR-034**: As operações de escrita do seam Account Admin DEVEM receber de quem chama se o ator administra. Quando
  ele **não** administra ([ADR-057](../../docs/adr/ADR-057-escopos-da-chave-de-api.md), item 4), DEVEM ser recusadas,
  com um erro próprio que nomeia o campo: cadastrar conta com o grupo de administração; pôr ou tirar alguém desse grupo
  (por qualquer operação: alterar grupos, um grupo por vez ou definir membros); definir os membros do grupo de
  administração; apagar o grupo de administração; e qualquer escrita sobre conta que está no grupo de administração
  (alterar, redefinir senha, desativar, reativar, desfazer o vínculo Google, mudar grupos, apagar). As leituras NÃO
  DEVEM ser restringidas.
- **FR-035**: Sem a indicação do ator, as operações DEVEM se comportar como hoje (ator que administra): a linha de
  comando e os chamadores atuais não mudam. A identidade NÃO DEVE conhecer escopos, chaves de API nem a superfície por
  onde a operação chegou.
- **FR-036**: Apagar conta e mudar um grupo DEVEM registrar quem fez e o resultado, como as outras mudanças de conta
  (FR-010, FR-021); a falha de um apagador DEVE ser registrada com o nome dele, sem segredo.
- **FR-038**: Depois do apagamento concluído, nenhum dado que identifique a conta DEVE restar na plataforma. Os
  registros que ficam — auditoria de tools de escrita, uso, custo e impacto, históricos de mudança e autores de
  mudanças em contas, grupos e ajustes — DEVEM ter cada citação da conta (subject ou nome de usuário) trocada por um
  **pseudônimo**: opaco, aleatório, gerado uma vez por apagamento, o mesmo em todos os módulos para aquela conta e de uma
  forma que nenhum nome de usuário ou subject pode ter. A identidade DEVE gerar o pseudônimo, guardá-lo na conta "em
  apagamento" (a retomada usa o mesmo) e passá-lo a cada apagador; na própria identidade, DEVE trocar o nome de usuário
  apagado pelo pseudônimo nos autores de mudanças de outras contas, dos grupos e dos ajustes de login. Fora do alcance
  da plataforma, e por isso fora desta regra: o log de processo (FR-021) e o que já saiu para destinos externos de
  observabilidade, ambos sob a retenção do operador.
- **FR-037**: O armazenamento persistente DEVE ganhar o estado "em apagamento" por migração nova do próprio módulo,
  aplicável sobre uma instalação com dados, sem mudar contas existentes.

### Key Entities

- **Conta**: nome de usuário, e-mail, nome de exibição, estado (ativa, desativada ou em apagamento), grupos, senha (hash, ou ausente para conta só Google),
  indicação de senha temporária, vínculo Google opcional, instantes de criação e de alteração, autor da última alteração.
- **Grupo**: nome; o grupo de administração é protegido.
- **Cliente**: identificador, tipo, endereços de retorno e pós-logout, audiência, referência do segredo (confidencial).
- **Sessão**: pessoa, cliente, início, expiração absoluta, método de autenticação (senha ou Google).
- **Código de autorização**: cliente, sessão, desafio PKCE, `nonce`, validade, uso.
- **Token de renovação**: hash, sessão, família, estado (ativo, trocado, revogado).
- **Chave de assinatura**: identificador, chave pública, chave privada cifrada, estado (ativa, em retirada, retirada).
- **Ajustes de login**: login Google ligado ou desligado, e de onde vem (instalação ou runtime).
- **Apagador de dados do subject** (2026-11-04): um nome e a operação que apaga, noutro módulo, o que é do subject;
  devolve contagens e avisos. A composição declara a lista, em ordem.
- **Pseudônimo** (2026-11-04): identificador opaco e aleatório de uma conta apagada, que substitui a citação dela nos
  registros que ficam; nunca casa com um nome de usuário nem com um subject.
- **Relatório de apagamento** (2026-11-04): a conta, se concluiu, as contagens da identidade, e por apagador o nome, as
  contagens e os avisos — ou que ele falhou.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Numa instalação sem Keycloak, uma pessoa cadastrada entra no Open WebUI com usuário e senha e vê
  exatamente os Assistants que os grupos dela permitem.
- **SC-002**: 100% dos casos adversariais da suíte de protocolo são recusados: endereço de retorno divergente, cliente
  público sem PKCE, código reusado, formulário sem proteção, usuário bloqueado, e-mail Google não verificado, conta
  desconhecida ou desativada, conta Google diferente da vinculada, token de renovação reusado.
- **SC-003**: Nenhuma conta é criada por login Google em nenhum cenário de teste.
- **SC-004**: Depois de desativada, uma conta não obtém nenhum token novo, e todo acesso dela termina em até 10 minutos.
- **SC-005**: Em teste automatizado, as respostas de login para usuário inexistente, senha errada e conta desativada são
  indistinguíveis em status, corpo e ordem de grandeza de tempo.
- **SC-006**: Numa instalação nova, o operador cria o primeiro admin e entra na console em menos de 5 minutos, seguindo
  só a documentação da instalação.
- **SC-007**: Rotacionar a chave de assinatura não invalida nenhum token vigente nem encerra nenhuma sessão.
- **SC-008**: Depois da passada da US8, em 100% das páginas do provedor, nos dois temas e nas larguras de celular e de computador, a marca segue a FR-023 e o contraste atende AA; e há zero ocorrências de `aic_session`, `realm="ai-core"`, `ai-core/identity/` e do nome padrão "Agentic" no código, nos testes e nos documentos vivos do workspace e das specs do core (fora do histórico do ADR-037, item 6, e dos testes e textos que nomeiam o antigo de propósito).

- **SC-009**: Depois de um apagamento concluído, zero sessões, tokens de renovação, códigos, associações e vínculos da
  conta restam, em memória e no Postgres; uma conta nova com o mesmo nome é cadastrada e não recebe nenhum grupo nem
  sessão da anterior; com um apagador que falha na primeira vez, a segunda tentativa conclui.
- **SC-010**: Em suíte adversarial, nenhuma operação com o ator marcado como não administrador põe ou tira alguém do
  grupo de administração, nem altera, desativa, reativa, redefine a senha, desfaz o vínculo ou apaga uma conta desse
  grupo — 100% recusadas, nomeando o campo.
- **SC-011**: Duas mudanças de grupo simultâneas em grupos diferentes da mesma conta preservam as duas em 100% das
  repetições do teste, em memória e no Postgres.
- **SC-012**: Depois de um apagamento concluído, uma busca pelo nome de usuário e pelo subject apagados em todo o
  armazenamento da plataforma (todos os schemas) não encontra nenhuma ocorrência; a mesma busca pelo pseudônimo
  encontra os registros que ficaram.

## Assumptions

- Um emissor por instalação. O caminho de IdP externo da 003 continua existindo como alternativa, mas não junto com
  este módulo.
- Sem autocadastro, sem verificação em duas etapas e sem recuperação de senha por e-mail nesta fase: a plataforma não
  envia e-mail, e a senha é redefinida por um admin.
- Os clientes são da própria instalação (Open WebUI e console); por isso não há tela de consentimento.
- Processo único: os contadores de tentativas ficam em memória, como os de rate limit da 003.
- Contas, sessões e chaves exigem o perfil `persistent` (Postgres). No `memory`, tudo é efêmero e a chave de assinatura
- US8: o AA da FR-023 vale para os pares de texto e controles nos dois temas, inclusive o hover do botão primário: no escuro ele passou a `#1D4ED8` (texto branco a 6,7:1) pela decisão do mantenedor de 2026-10-20, no ADR-039, aplicada na passada da 013 aos dois CSS.
- US8 (ADR-037, ADR-038): o símbolo, o lockup e o favicon vêm de `brand-kit/svg/` (aprovados pelo mantenedor) e entram nos assets das páginas; a console (013) os usa na passada dela. A instalação continua presa a uma tag antiga até a passada dela.
  muda a cada processo; serve só para desenvolvimento.
- O Open WebUI v0.12 é cliente confidencial e guarda os tokens dele; a instalação configura a sessão dele um pouco
  menor que a sessão de 30 dias do provedor, para que ele nunca fique com um token de renovação já vencido (com o
  Keycloak, era 8 h contra 10 h).
- Nomes de usuário continuam sendo o subject (`user:<nome>`), como na Fase 7, para que ACLs e donos já gravados sigam
  valendo.
- US9 (ADR-058, item 6 revisto na clarificação de 2026-11-04): a auditoria de tools de escrita (004), o uso, o custo e
  o impacto (009) e os históricos ficam, pseudonimizados (FR-038); o trace em arquivo não cita o subject. O que cada
  módulo apaga ou pseudonimiza é dele (003, 004, 007, 008, 009); a identidade só os chama, pela porta, na ordem que a
  composição dá, e lhes passa o pseudônimo.
- US9: o apagamento é síncrono e o relatório vem na resposta; o volume de conversas de uma pessoa é o de uma instalação
  pequena (centenas), e cada apagador é um `DELETE` por tabela.
- US11 (ADR-057): quem marca o ator como não administrador é a 008, a partir dos escopos da chave; a linha de comando é
  o operador e não tem a restrição.

