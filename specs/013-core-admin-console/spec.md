# Feature Specification: Console de administração

**Feature Branch**: `013-core-admin-console`

**Created**: 2026-10-13

**Status**: Draft

**Input**: Pedido do mantenedor (2026-10-13): interface gráfica simples para aplicar configurações — login por usuário
e senha ou Google; modelos e MCPs de cada Assistant, sobrepondo o `assistants.yaml` quando a flag do YAML permite;
dashboard de requisições, tokens e custo por modelo e por dia; Langfuse; ajustes de login; instalação com ou sem a
interface. ADR-029, ADR-031, ADR-032, ADR-033, ADR-034. Fase 9, incremento 9.5 (2026-10-20): identidade Axon —
ADR-037, ADR-038, ADR-039. Fase 9 (2026-10-21): chaves de API e acesso dos Assistants de sistema pela console — ADR-040.

## Module Boundary *(mandatory)*

- **Módulo**: Admin Console — interface gráfica de administração da plataforma, opcional na instalação e restrita ao
  grupo de administração.
- **Repositório / distribuição**: `axon-ai` → `axon-ai/console/` (aplicação web com toolchain próprio, fora do
  workspace Python); a imagem é montada pela instalação (002).
- **Consome (seams)**: API HTTP — 008 (superfície de administração `/admin/v1`, contrato `admin-api.md`); protocolo
  OIDC — 012 (cliente público `console`).
- **Expõe (seams)**: nenhum.
- **Depende de infraestrutura (via portas)**: nenhuma porta do core. Roda no navegador e é servida por um servidor
  estático da instalação, na mesma origem da plataforma.
- **Não conhece**: módulos internos do core, banco, arquivos do operador (`assistants.yaml`, `mcp.yaml`), regras de
  validação, de autorização e de precedência entre instalação e runtime — tudo isso vem pronto da API.
- **Substituição**: qualquer interface que use só a API de administração e o protocolo da 012 substitui esta sem tocar
  em nenhuma outra spec.
- **Insumo técnico**: [design.md](design.md); [ADR-029](../../docs/adr/ADR-029-console-de-administracao-propria.md),
  [ADR-031](../../docs/adr/ADR-031-superficie-de-administracao.md),
  [ADR-032](../../docs/adr/ADR-032-assistants-de-sistema-sobrepostos-em-runtime.md),
  [ADR-033](../../docs/adr/ADR-033-segredos-de-runtime-cifrados-com-a-chave-mestra.md),
  [ADR-034](../../docs/adr/ADR-034-trace-com-destinos-e-conteudo-opcional.md),
  [ADR-037](../../docs/adr/ADR-037-a-plataforma-se-chama-axon.md), [ADR-038](../../docs/adr/ADR-038-marca-da-plataforma-e-marca-da-instalacao.md),
  [ADR-039](../../docs/adr/ADR-039-hover-do-botao-primario-no-escuro.md),
  [ADR-040](../../docs/adr/ADR-040-rotacao-de-chaves-e-acesso-sobreponivel.md).

## Clarifications

### Session 2026-10-13

- Q: A console (e a página de login, que usa o mesmo visual) deve ter tema escuro? → A: Claro e escuro. A console abre no tema do sistema operacional e tem um botão para trocar, lembrado no navegador; a página de login da 012 segue o tema do sistema.

### Session 2026-10-20

- Q: Que marca a console mostra depois do renome (ADR-038)? → A: Sem marca da instalação — o `instance.custom` do `me` é falso —, a barra lateral mostra o símbolo Axon de 32px, o wordmark `axon` e a legenda "Console". Com marca da instalação, o nome e o logotipo dela ocupam esse lugar, e o rodapé da barra leva o símbolo de 16px e "com Axon". No trilho de ícones (abaixo de 1100px), só o símbolo, ou só o logotipo ou a inicial da instalação. A tela de acesso negado mostra sempre o lockup Axon: quem não administra não lê o `me`, e a console não sabe a marca da instalação.
- Q: O que a aba do navegador mostra? → A: O favicon é sempre o símbolo Axon (ADR-038, item 3). O título é "<tela> · <nome da instalação>" ("Axon" por padrão), como nas páginas de login da 012; a barra do navegador no celular usa `#0B0F19` no tema escuro.
- Q: As cores da console mudam? → A: Sim. Os tokens passam aos do `DESIGN.md` (ADR-038, item 4), iguais aos das páginas da 012. No tema escuro, o hover do botão primário escurece para `#1D4ED8`, como no claro, em vez do `axon-blue`, que dava 3,69:1 com o texto branco — decisão do mantenedor de 2026-10-20 (ADR-039), que vale também para as páginas da 012.
- Q: De onde vêm o símbolo e o wordmark? → A: Do `brand-kit/svg/` aprovado (ADR-038, item 6). O wordmark sozinho, que a barra lateral usa ao lado do símbolo, é um recorte do lockup aprovado: o mesmo traço, só com o enquadramento do wordmark; ele entra no `brand-kit` ao lado dos outros arquivos.
- Q: O pacote da console muda de nome? → A: Sim: `@axon/console` (era `@agentic/console`; ADR-037, item 2). Nenhum outro identificador da console muda: a chave `console.theme` do armazenamento do navegador e o cliente OIDC `console` ficam (ADR-037, item 5).

### Session 2026-10-21

- Q: Como se chama a aba nova do detalhe do Assistant, ao lado de Modelos, MCP e Histórico? → A: "Permissões" (rota `permissoes`), com o título interno "Quem pode usar este Assistant"; o nome evita repetir "Acesso", que é a tela da barra lateral.
- Q: Onde fica a tela de chaves de API? → A: Quarta aba da tela Acesso, "Chaves de API" (`/acesso/chaves`), depois de Usuários, Grupos e Login, com "Criar chave" no cabeçalho, como "Cadastrar pessoa".
- Q: O formulário de criação concede grupos à chave? → A: Não. O sistema ganha acesso pela entrada `svc:` na aba "Permissões" de cada Assistant, o que deixa explícito o que cada sistema alcança; os grupos de chaves existentes aparecem na lista, e a API e a CLI continuam podendo concedê-los.
- Q: Além de sistemas e grupos, o que "Adicionar" oferece na aba "Permissões"? → A: Um campo de texto com sugestões (como o de modelo): sistemas com chave ativa e grupos como sugestões, e `user:<nome>` digitado; num Assistant público, "Qualquer pessoa autenticada (`*`)" é uma opção à parte, com nota; num privado, ela não aparece, com o motivo.

### Session 2026-10-22

- Q: Como a console mostra e muda o `vision` de um papel ([ADR-044](../../docs/adr/ADR-044-imagens-na-conversa.md), item 10)? → A: Na aba Modelos, cada papel ganha a caixa "Enxerga imagens" na coluna da sobreposição (desligada sem modelo), com a dica de que a pergunta com imagem a um Assistant sem visão é recusada; o efetivo mostra o selo "Visão". A sobreposição de `models` é a seção inteira, então o `vision` vai junto: papel marcado sai como `{model, vision: true}`, o resto como o texto de sempre. O resumo da sobreposição e o histórico mostram "(visão)" no papel.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Admin entra na console (Priority: P1)

Um administrador abre a console, é levado à página de login da plataforma, entra com usuário e senha ou Google e volta
à console. Quem entra sem pertencer ao grupo de administração vê "Sua conta não tem acesso à console" e um botão para
sair.

**Why this priority**: Toda outra tela depende disso.

**Independent Test**: Entrar com um admin e com um usuário comum; o primeiro chega à tela inicial, o segundo à página de
acesso negado, sem nenhum dado administrativo carregado.

**Acceptance Scenarios**:

1. **Given** um admin sem sessão, **When** abre a console, **Then** é levado ao login da plataforma e, depois de
   entrar, volta à página que tinha pedido.
2. **Given** um usuário fora do grupo de administração, **When** entra, **Then** vê a página de acesso negado e nenhuma
   informação administrativa.
3. **Given** um admin na console, **When** o token expira durante o uso, **Then** a console renova o acesso sem perder o
   que estava sendo editado; se a sessão no provedor acabou, pede login de novo e volta ao mesmo lugar.
4. **Given** um admin, **When** sai, **Then** a sessão termina também no provedor, e voltar à console exige login.

---

### User Story 2 - Trocar os modelos de um Assistant (Priority: P1)

O admin abre um Assistant de sistema e vê, para cada papel de modelo, o que o YAML define, a sobreposição (se houver) e o
valor efetivo. Se o YAML permite sobrepor modelos, ele escolhe outro modelo dentro da allowlist, testa e salva; a
próxima conversa já usa o modelo novo. Se não permite, a seção aparece travada com "Só muda por novo deploy".

**Why this priority**: É o primeiro pedido do mantenedor e o motivo principal da console.

**Independent Test**: Com um Assistant que permite `models`, trocar o modelo de geração, salvar e conferir na API que a
configuração efetiva mudou; com outro que não permite, conferir que a seção não é editável.

**Acceptance Scenarios**:

1. **Given** um Assistant com `overrides: [models]`, **When** o admin escolhe outro modelo de geração permitido e salva,
   **Then** a tela mostra a sobreposição como ativa e o valor efetivo novo.
2. **Given** um modelo fora da allowlist, **When** o admin tenta salvar, **Then** a recusa da API aparece junto ao campo,
   com o motivo que ela devolveu.
3. **Given** um Assistant sem `models` em `overrides`, **When** o admin abre a seção, **Then** ela está travada e mostra
   o que o YAML define.
4. **Given** uma sobreposição que um deploy desativou, **When** o admin abre o Assistant, **Then** vê a sobreposição
   como inativa, com o motivo, e o valor do YAML como efetivo.
5. **Given** um modelo escolhido, **When** o admin pede "Testar modelo", **Then** vê se o modelo está disponível e, se
   não, o motivo.
6. **Given** uma sobreposição ativa, **When** o admin a descarta e confirma na própria tela, **Then** o Assistant volta
   ao que o YAML define.

---

### User Story 3 - Gerenciar os MCPs de um Assistant (Priority: P1)

O admin escolhe quais servidores MCP globais um Assistant usa e, de cada um, quais tools ficam permitidas e quais podem
escrever. As tools vêm da descoberta do servidor. Num Assistant público, tools de escrita não podem ser marcadas, e a
tela explica por quê.

**Why this priority**: Segundo pedido do mantenedor; hoje só muda por deploy.

**Independent Test**: Com um Assistant que permite `mcp` e um servidor MCP de teste com duas tools, ligar o servidor,
permitir uma tool e salvar; a configuração efetiva traz só aquela tool desse servidor.

**Acceptance Scenarios**:

1. **Given** um Assistant com `overrides: [mcp]`, **When** o admin liga um servidor e marca uma tool, **Then** depois de
   salvar a tool aparece entre as permitidas, com o namespace do servidor.
2. **Given** um servidor indisponível, **When** o admin abre a lista de tools dele, **Then** vê o motivo da falha e as
   tools já selecionadas continuam visíveis.
3. **Given** um Assistant público, **When** o admin tenta marcar uma tool como de escrita, **Then** a opção está
   bloqueada com a explicação.
4. **Given** um Assistant sem `mcp` em `overrides`, **When** o admin abre a seção, **Then** ela está travada.

---

### User Story 4 - Ver uso e custo (Priority: P2)

O admin abre o dashboard e vê, num período de 7, 30 ou 90 dias, requisições, chamadas de modelo, tokens de entrada e de
saída e custo, por dia e por modelo ou por Assistant, com totais e uma tabela. Modelos sem preço aparecem com "sem
preço". Ele mantém a tabela de preços (USD por milhão de tokens de entrada e de saída, com data de início).

**Why this priority**: É o terceiro pedido, mas não bloqueia a configuração.

**Independent Test**: Com conversas registradas em dois modelos, um com preço e outro sem, abrir o dashboard de 7 dias;
os totais batem com a API e o modelo sem preço aparece marcado.

**Acceptance Scenarios**:

1. **Given** uso em vários dias, **When** o admin escolhe 30 dias e agrupa por modelo, **Then** vê uma série por dia,
   totais do período e a tabela por modelo, no fuso que a API informa.
2. **Given** um modelo sem preço, **When** o dashboard abre, **Then** o custo dele aparece como "sem preço" e o total
   avisa que está incompleto.
3. **Given** a tabela de preços, **When** o admin cadastra um preço com data de início no passado, **Then** o custo do
   período passa a refletir esse preço.
4. **Given** nenhum uso no período, **When** o dashboard abre, **Then** mostra um estado vazio que explica de onde vêm os
   dados.

---

### User Story 5 - Configurar o Langfuse (Priority: P2)

O admin informa o endereço do Langfuse e as chaves, liga o envio e testa a conexão. Pode ligar a captura do texto de
prompt e resposta, depois de ler e confirmar um aviso de privacidade. Campos definidos pela instalação aparecem somente
leitura, com "Definido na instalação".

**Why this priority**: Pedido do mantenedor; útil, mas opcional para operar.

**Independent Test**: Contra um Langfuse simulado, salvar endereço e chaves, testar a conexão e ver o sucesso; recarregar
a tela e conferir que a chave secreta não volta, só a indicação de que existe.

**Acceptance Scenarios**:

1. **Given** chaves válidas, **When** o admin salva e testa, **Then** vê a conexão bem-sucedida e o estado do envio.
2. **Given** chaves salvas, **When** o admin reabre a tela, **Then** a chave secreta aparece só como "definida", nunca
   o valor.
3. **Given** a instalação define o endereço e as chaves, **When** o admin abre a tela, **Then** esses campos estão
   somente leitura com "Definido na instalação".
4. **Given** a captura de conteúdo desligada, **When** o admin a liga, **Then** precisa confirmar o aviso de privacidade
   na própria tela antes de salvar.

---

### User Story 6 - Login e contas (Priority: P2)

O admin liga ou desliga o login Google e vê o endereço de retorno que deve ser registrado no Google. Cadastra pessoas
(usuário, e-mail, nome, grupos, senha temporária), muda grupos, redefine senhas, desativa e reativa contas, desfaz
vínculos com o Google, e cria e apaga grupos.

**Why this priority**: Com a plataforma como provedor de identidade, o cadastro é obrigatório para alguém entrar.

**Independent Test**: Cadastrar uma pessoa num grupo e entrar com ela no Open WebUI; desativá-la e ver o login recusado.

**Acceptance Scenarios**:

1. **Given** a instalação sem cliente Google, **When** o admin abre os ajustes de login, **Then** a opção do Google está
   desabilitada, com a explicação de que falta configuração da instalação.
2. **Given** uma pessoa cadastrada com senha temporária, **When** o admin conclui o cadastro, **Then** a senha temporária
   é mostrada uma única vez, com a opção de copiá-la.
3. **Given** o último admin ativo, **When** alguém tenta desativá-lo ou tirá-lo do grupo de administração, **Then** a
   recusa da API aparece com o motivo.
4. **Given** o grupo de administração, **When** o admin vê a lista de grupos, **Then** ele aparece como protegido, sem
   opção de apagar.

---

### User Story 7 - Servidores MCP globais (Priority: P3)

Regressão ADR-055: a lista aceita `auth.type: delegated` junto aos modos existentes. A console indica
"Por execução" para a conectividade delegada, sem sondagem administrativa sem credencial; a configuração
inválida continua visível como indisponível. Os detalhes explicam a autorização temporária, e editar um
registro delegado preserva esse modo sem solicitar nem enviar credencial estática. A aba MCP do Assistant
mostra as tools configuradas na política, deixando claro que a descoberta ocorre na execução.

O admin lista os servidores MCP globais com estado e tools, cadastra, edita e remove os registrados pela API. Os que
vêm do arquivo do operador aparecem somente leitura.

**Why this priority**: Já existe pela API privada; a tela fecha o ciclo da US3 sem obrigar o uso de linha de comando.

**Independent Test**: Cadastrar um servidor, ver a saúde dele e as tools; um servidor do arquivo aparece sem ações de
edição.

**Acceptance Scenarios**:

1. **Given** um servidor do arquivo do operador, **When** aparece na lista, **Then** não tem ações de edição e indica a
   origem.
2. **Given** um servidor cadastrado com referência de credencial sem valor na instalação, **When** aparece na lista,
   **Then** mostra o estado de falha com o motivo, sem nenhum valor de credencial.

---

### User Story 8 - Identidade Axon: a console com a marca da plataforma (Priority: P2)

A plataforma passa a se chamar Axon (ADR-037, ADR-038). O admin de uma instalação sem marca própria vê o símbolo e o wordmark Axon na barra lateral; o de uma instalação com marca vê a marca da organização e, discreto no rodapé, "com Axon". A aba mostra o símbolo Axon e o nome da tela. As cores seguem a marca nos dois temas, sem perder contraste, inclusive ao passar o mouse no botão primário.

**Why this priority**: É a tela que o operador mais vê; sem a passada, a console continuaria dizendo "Agentic". P2 porque nenhuma função muda.

**Independent Test**: Abrir a console com o `me` sem marca própria e ver o símbolo, o wordmark e "Console"; com nome próprio, ver o nome e "com Axon" no rodapé; conferir o favicon, o título e o contraste AA nas telas, nos dois temas.

**Acceptance Scenarios**:

1. **Given** uma instalação sem marca própria, **When** o admin abre a console, **Then** a barra lateral mostra o símbolo Axon, o wordmark `axon` e "Console", e nenhuma atribuição no rodapé.
2. **Given** uma instalação com nome próprio ou logotipo, **When** o admin abre a console, **Then** a barra lateral mostra o nome e o logotipo (ou a inicial) da instalação e, no rodapé, o símbolo Axon pequeno e "com Axon".
3. **Given** a janela abaixo de 1100px, **When** a barra vira trilho de ícones, **Then** a marca aparece só como símbolo (ou logotipo/inicial), e o nome continua disponível para leitor de tela.
4. **Given** uma pessoa sem o grupo de administração, **When** entra, **Then** a tela de acesso negado mostra o lockup Axon.
5. **Given** qualquer tela, **When** o navegador mostra a aba, **Then** o ícone é o símbolo Axon e o título é "<tela> · <nome da instalação>".
6. **Given** as telas nos temas claro e escuro, **When** a verificação automática de acessibilidade roda, **Then** não há violação de WCAG 2.2 AA, e o texto do botão primário atende AA também no hover, nos dois temas.

---

### User Story 9 - Chaves de API dos sistemas (Priority: P2)

O admin cria uma chave para um sistema informando o nome dele (a chave sai com o subject `svc:<nome>`) e, se quiser, um
rótulo que distingue chaves do mesmo sistema (por exemplo, por ambiente). A chave em claro aparece uma única vez, num
diálogo com "Copiar" e o aviso de que não será mostrada de novo; depois de fechado, nada a mostra — nem a lista, nem a
memória da tela, nem o registro do navegador. A lista traz todas as chaves: sistema, identificador, grupos, rótulo,
criação, última rotação e estado (ativa, ou revogada com a data). O admin revoga uma chave confirmando na própria tela e
rotaciona o segredo de uma chave ativa, vendo a chave nova uma vez, como na criação
([ADR-040](../../docs/adr/ADR-040-rotacao-de-chaves-e-acesso-sobreponivel.md); 008 US11).

**Why this priority**: Hoje chave só se cria e revoga pela linha de comando ou por chamada direta à API; a rotação nem
existe. Com a aba de acesso (US10), é o que permite dar a um sistema novo acesso a um Assistant sem deploy.

**Independent Test**: Na aba "Chaves de API" da tela Acesso, criar uma chave para `relatorios` com rótulo `prod`, copiar a chave do diálogo, fechar e conferir
que a lista não a mostra; rotacioná-la e ver a chave nova uma vez; revogá-la confirmando na tela e ver o estado
"Revogada" com a data.

**Acceptance Scenarios**:

1. **Given** o admin na tela de chaves, **When** cria uma chave com o nome `relatorios` e o rótulo `prod`, **Then** um
   diálogo mostra a chave em claro, com "Copiar" e o aviso de que ela não aparece de novo, e a lista passa a ter a chave
   `svc:relatorios`, sem a chave em claro.
2. **Given** o diálogo fechado, **When** o admin volta à lista ou reabre a tela, **Then** a chave em claro não aparece em
   lugar nenhum da console.
3. **Given** um nome fora do padrão (`Relatórios`), **When** o admin tenta criar, **Then** o campo do nome mostra o
   motivo da plataforma, e nada é criado.
4. **Given** uma chave ativa, **When** o admin pede a revogação, **Then** a tela pede confirmação na própria linha; ao
   confirmar, a chave aparece revogada com a data, e as ações dela somem.
5. **Given** uma chave ativa, **When** o admin rotaciona o segredo, **Then** confirma na tela, vê a chave nova uma única
   vez no mesmo diálogo da criação, com o aviso de que a anterior já não vale, e a lista mostra a data da rotação.
6. **Given** uma chave revogada por outra pessoa enquanto a tela estava aberta, **When** o admin tenta rotacioná-la,
   **Then** vê o motivo ("chave revogada") e a lista se atualiza.
7. **Given** duas chaves do mesmo sistema com rótulos diferentes, **When** o admin olha a lista, **Then** distingue uma
   da outra pelo rótulo e pelo identificador.

---

### User Story 10 - Quem pode usar um Assistant de sistema (Priority: P2)

No detalhe de um Assistant de sistema, a aba "Permissões" mostra e, se o YAML liberar `auth` em `overrides`, edita quem pode
usá-lo: um interruptor por forma de entrada ("Login" para quem entra pelo chat, "Chave de API" para sistemas) e a lista
de quem é permitido — sistemas, grupos e, onde a plataforma admite, pessoas e "qualquer autenticado" —, cada entrada
removível. "Adicionar" abre uma escolha entre os sistemas com chave ativa e os grupos da plataforma. A seção segue as
sobreposições das outras abas: travada com "Só muda por novo deploy" quando o YAML não a libera, inativa com o motivo
quando o deploy a mudou, conflito de versão com o rascunho preservado, descarte confirmado na tela e histórico
([ADR-040](../../docs/adr/ADR-040-rotacao-de-chaves-e-acesso-sobreponivel.md)).

**Why this priority**: Dar acesso a um sistema ou a um grupo hoje exige editar o `assistants.yaml` e reimplantar.

**Independent Test**: Num Assistant com `overrides: [auth]`, ligar "Chave de API", adicionar o sistema `relatorios` e
salvar; a visão efetiva traz o esquema e a entrada; o histórico registra a gravação.

**Acceptance Scenarios**:

1. **Given** um Assistant com `auth` liberado, **When** o admin liga "Chave de API", adiciona `svc:relatorios` e salva,
   **Then** a aba mostra o valor efetivo novo, com autor e versão, e o YAML como referência.
2. **Given** um Assistant sem `auth` em `overrides`, **When** o admin abre a aba, **Then** vê os esquemas e a lista do
   YAML só para leitura, com "Só muda por novo deploy".
3. **Given** um Assistant privado, **When** o admin procura "qualquer autenticado", **Then** a opção não é oferecida, com
   a explicação; num público, é.
4. **Given** o admin desligando os dois esquemas ou removendo todas as entradas, **When** tenta salvar, **Then** a tela
   explica por que não pode e não envia; se a plataforma recusar algo mesmo assim, o motivo aparece no campo.
5. **Given** uma entrada que não corresponde a nenhum sistema com chave ativa nem a nenhum grupo, **When** o admin olha a
   lista, **Then** ela aparece marcada como "sem correspondência", com a explicação de que não dá acesso a ninguém, e
   pode ser removida.
6. **Given** um sistema adicionado com "Chave de API" desligada, **When** o admin olha a lista, **Then** a entrada é
   marcada: sistemas só entram por chave.
7. **Given** outro admin salvou antes, **When** o admin salva, **Then** vê o aviso de conflito com "Recarregar e manter
   meu rascunho".
8. **Given** uma sobreposição de acesso, **When** o admin a descarta, **Then** confirma na tela e o Assistant volta ao
   YAML; o histórico mostra a gravação e o descarte com os esquemas e as entradas.

---

### Edge Cases

- Dois admins editam o mesmo Assistant: quem salva por último recebe aviso de que houve mudança, pode recarregar e não
  perde o próprio rascunho.
- A API fica indisponível: cada tela mostra erro com opção de tentar de novo; nada salvo localmente é dado como
  aplicado.
- A conta do admin é desativada ou sai do grupo durante o uso: a próxima chamada leva à página de acesso negado.
- Assistant indisponível (por exemplo, sobreposição que ficou inválida porque um MCP foi apagado): aparece na lista com
  o estado e os motivos que a API devolve.
- Lista longa de usuários ou de preços: busca e paginação.
- Dados de uso com fuso diferente do navegador: a console mostra o fuso da API, não o do navegador.
- Tela estreita (tablet): todas as funções continuam acessíveis; o layout se reorganiza.
- `me` ainda carregando: a barra lateral mostra o símbolo Axon (sem atribuição) até a resposta chegar, e o título usa "Axon".
- Instalação com logotipo e sem nome próprio: o logotipo com o nome padrão no lugar principal, e "com Axon" no rodapé (há marca da instalação).
- Troca de tema pela console (claro/escuro/sistema): o símbolo e o wordmark trocam de versão na hora, sem recarregar.
- Fechar o diálogo da chave em claro sem copiar: a chave se perde; a tela avisa antes de fechar que ela não volta e
  sugere rotacionar se não tiver sido guardada.
- Admin que rotaciona a chave com que a própria automação dele entra: a console não usa chave de API (entra pelo login),
  então a sessão não cai.
- Sistema cuja única chave foi revogada: some das opções de "Adicionar"; as entradas que já o citam ficam marcadas como
  sem correspondência.
- Muitas chaves (centenas): a lista continua legível, com o sistema e o rótulo como primeiras colunas e as revogadas
  depois das ativas.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A console NÃO DEVE decidir regra de negócio: validação, autorização e precedência entre instalação e
  runtime vêm da API. Toda recusa da API DEVE aparecer junto ao campo que ela nomeia, com o motivo devolvido.
- **FR-002**: A console DEVE entrar pelo provedor de identidade da plataforma como cliente público com PKCE, manter os
  tokens só em memória (nenhum token nem dado administrativo no armazenamento persistente do navegador), renovar o acesso sem interromper o uso e, ao
  sair, encerrar a sessão no provedor.
- **FR-003**: Pessoa autenticada fora do grupo de administração DEVE ver só a página de acesso negado, com a opção de
  sair.
- **FR-004**: A lista de Assistants de sistema DEVE mostrar nome, descrição, flow, modelos efetivos por papel, MCPs,
  estado (disponível ou indisponível com os motivos) e as marcas "sobreposto", "sobreposição inativa" e "travado".
- **FR-005**: O detalhe de um Assistant DEVE mostrar, para cada seção sobreponível, o valor do YAML, a sobreposição (com
  autor e data) e o valor efetivo, e DEVE permitir editar só as seções que o YAML declara em `overrides`; as demais
  aparecem travadas com "Só muda por novo deploy". Uma aba "Histórico" DEVE listar as sobreposições gravadas e
  descartadas, com autor, data e versão (003 FR-021).
- **FR-006**: A edição de modelos DEVE cobrir os papéis que o Assistant declara ou que o flow exige, mostrar a allowlist
  do YAML como referência, oferecer "Testar modelo" e mostrar o resultado.
- **FR-007**: A edição de MCPs DEVE permitir ligar servidores globais disponíveis ao Assistant e, para cada um, marcar
  tools permitidas e de escrita a partir da descoberta do servidor; a marcação de escrita DEVE estar bloqueada em
  Assistant público.
- **FR-008**: Salvar DEVE usar a versão que a tela leu; se outro admin salvou antes, a console DEVE avisar e oferecer
  recarregar, preservando o rascunho.
- **FR-009**: Descartar uma sobreposição DEVE pedir confirmação na própria tela e voltar ao YAML.
- **FR-010**: O dashboard DEVE mostrar, para 7, 30 ou 90 dias (padrão 30), agrupado por modelo ou por Assistant, com
  filtro de origem (só produção por padrão; avaliação ou as duas — 009):
  requisições, chamadas de modelo, tokens de entrada e de saída e custo, em série diária, totais e tabela; DEVE mostrar
  o fuso dos dados e marcar "sem preço" e total incompleto quando faltar preço.
- **FR-011**: A tabela de preços DEVE listar provider, modelo, USD por milhão de tokens de entrada e de saída e data de
  início, permitir cadastrar um preço novo (vigência) e destacar modelos usados que não têm preço.
- **FR-012**: A tela do Langfuse DEVE permitir endereço, chave pública, chave secreta (só de escrita: mostra se existe,
  nunca o valor), ligar o envio, ligar a captura de conteúdo (com confirmação de um aviso de privacidade), testar a
  conexão e ver o estado (último erro, descartes). Campo definido pela instalação DEVE aparecer somente leitura com
  "Definido na instalação".
- **FR-013**: A tela de acesso DEVE permitir ligar e desligar o login Google (desabilitado, com explicação, sem cliente
  Google na instalação), mostrar o endereço de retorno a registrar no Google, e gerir contas (listar com busca,
  cadastrar com senha temporária mostrada uma única vez, editar e-mail, nome e grupos, redefinir senha, desativar e
  reativar, desfazer vínculo Google) e grupos (criar, apagar, membros; o grupo de administração aparece protegido).
- **FR-014**: A tela de servidores MCP globais DEVE listar origem, estado, motivo e tools, e permitir cadastrar, editar e
  remover os registrados pela API; os do arquivo do operador aparecem somente leitura. Nenhum valor de credencial
  aparece.
- **FR-015**: Toda tela DEVE ter estados de carregamento, vazio, erro com nova tentativa e acesso negado.
- **FR-016**: A console DEVE estar em português do Brasil, com números e datas no formato brasileiro e valores
  monetários em USD.
- **FR-017**: A console DEVE atender WCAG 2.2 nível AA e ser operável só pelo teclado.
- **FR-018**: Toda ação da console DEVE ter equivalente na API de administração, para que a instalação sem console
  administre o mesmo (ADR-029).
- **FR-019**: A console DEVE ter tema claro e tema escuro: abre no tema do sistema operacional e oferece a troca manual,
  lembrada no navegador (a única preferência guardada nele). Os dois temas DEVEM atender à FR-017.
- **FR-020**: A console DEVE mostrar a marca pela regra do ADR-038, lida da API (`me.instance`, com `custom`): sem marca da
  instalação, o símbolo Axon, o wordmark `axon` e a legenda "Console" na barra lateral; com nome próprio ou logotipo, eles
  no lugar principal e o símbolo Axon pequeno com "com Axon" no rodapé da barra. A tela de acesso negado DEVE mostrar o
  lockup Axon. O favicon DEVE ser sempre o símbolo Axon, e o título da aba, "<tela> · <nome da instalação>" (reescrita em
  2026-10-20).
- **FR-021**: Os tokens de cor da console DEVEM ser os do `DESIGN.md`, iguais aos das páginas da 012, e o hover do botão
  primário no tema escuro DEVE usar `#1D4ED8` (ADR-039); o texto do botão primário DEVE atender AA em repouso e no hover,
  nos dois temas.
- **FR-022**: O pacote da console DEVE se chamar `@axon/console` (ADR-037). A chave de tema do navegador (`console.theme`)
  e o cliente OIDC (`console`) NÃO DEVEM mudar.
- **FR-023**: Os arquivos do símbolo, do lockup, do wordmark e do favicon DEVEM ser os do `brand-kit/svg/`, sem
  redesenho; o wordmark sozinho é um recorte do lockup aprovado, com o mesmo traço.
- **FR-024**: A console DEVE ter a aba "Chaves de API" na tela Acesso (`/acesso/chaves`) e, nela, criar chaves de API para sistemas: o admin informa o nome do sistema (a chave sai com o
  subject `svc:<nome>`) e um rótulo opcional, sem grupos (o acesso do sistema vem da aba "Permissões" de cada
  Assistant). Erro de campo da plataforma aparece no campo.
- **FR-025**: A chave em claro (na criação e na rotação) DEVE aparecer uma única vez, num diálogo com "Copiar" e o aviso de
  que não será mostrada de novo; ao fechar, ela NÃO DEVE permanecer em lugar nenhum da console — tela, memória de dados
  da API, histórico de navegação ou registro do navegador.
- **FR-026**: A lista de chaves DEVE mostrar sistema (subject), identificador, grupos, rótulo, criação, última rotação e
  estado (ativa, ou revogada com a data), e nunca a chave nem o hash; ativas antes das revogadas.
- **FR-027**: Revogar e rotacionar DEVEM pedir confirmação na própria tela (sem diálogo do navegador); rotação de chave
  revogada mostra o motivo da plataforma e atualiza a lista.
- **FR-028**: O detalhe de um Assistant de sistema DEVE ter a aba "Permissões" (título "Quem pode usar este Assistant") com um interruptor por esquema ("Login" e
  "Chave de API") e a lista de entradas de `allow`, cada uma removível; editável só se o YAML libera `auth`, com o mesmo
  tratamento das outras seções sobreponíveis (FR-005, FR-008, FR-009): valor do YAML e efetivo, autor e versão,
  sobreposição inativa com o motivo, conflito de versão com o rascunho preservado e descarte confirmado na tela.
- **FR-029**: "Adicionar" DEVE ser um campo de texto com sugestões: os sistemas com chave ativa (dos subjects `svc:` da
  lista de chaves) e os grupos da plataforma, vindos só do que a administração já lista (008 FR-038), e `user:<nome>`
  digitado. "Qualquer pessoa autenticada (`*`)" DEVE ser uma opção à parte, só em Assistant público, com nota; num
  privado, não aparece, com o motivo. Entrada fora dos formatos aceitos é apontada antes de entrar na lista.
- **FR-030**: A aba DEVE marcar, sem bloquear, as entradas sem correspondência (sistema sem chave ativa, grupo
  inexistente) e as que nunca casam com os esquemas ligados (sistema com "Chave de API" desligada); e DEVE impedir salvar
  com os dois esquemas desligados ou sem entradas, explicando o porquê, como a plataforma também recusa (003 FR-031).
- **FR-031**: O histórico do Assistant DEVE mostrar as gravações e os descartes de acesso com os esquemas e as entradas, e
- **FR-032**: A aba Modelos DEVE ler as duas formas de papel da API (`provider/modelo` e `{model, vision}`), permitir marcar `vision` por papel na sobreposição e mostrar o `vision` efetivo ([ADR-044](../../docs/adr/ADR-044-imagens-na-conversa.md), item 10).
  a lista de Assistants DEVE contar `auth` nas marcas de "sobreposto", "sobreposição inativa" e "travado" (FR-004).

### Key Entities

- **Visão de Assistant**: seções do YAML, sobreposições (ativa ou inativa, motivo, autor, data, versão), configuração
  efetiva, estado e motivos, seções permitidas.
- **Relatório de uso**: período, fuso, agrupamento, séries diárias, totais, linhas por modelo ou Assistant, marcas de
  "sem preço".
- **Preço**: provider, modelo, USD por milhão de tokens de entrada e de saída, data de início.
- **Ajustes do Langfuse**: endereço, chave pública, existência da chave secreta, envio ligado, captura de conteúdo, e a
  origem de cada campo (instalação, runtime ou padrão); estado do envio.
- **Conta** e **Grupo**: como na 012.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Um admin troca o modelo de geração de um Assistant permitido e a conversa seguinte usa o modelo novo, sem
  deploy, em menos de 1 minuto de trabalho na tela.
- **SC-002**: 100% das ações da console têm equivalente na API de administração, verificado pelo contrato da API e pelos
  testes de ponta a ponta.
- **SC-003**: Em teste, toda recusa da API aparece junto ao campo nomeado, com o motivo devolvido.
- **SC-004**: O dashboard de 90 dias abre em menos de 2 segundos com até 100 mil chamadas de modelo no período.
- **SC-005**: Zero violações automáticas de WCAG 2.2 AA nas telas, nos estados com dados, vazio e de erro, nos dois temas.
- **SC-006**: Nenhum segredo (chave do Langfuse, senha) aparece na tela depois de salvo, e nenhum token nem dado
  administrativo fica no armazenamento persistente do navegador — só a preferência de tema.
- **SC-007**: Uma pessoa sem o grupo de administração não recebe nenhum dado administrativo em nenhuma tela.
- **SC-008**: Em 100% das telas, nos dois temas, a marca segue a FR-020 e o contraste atende AA (inclusive o hover do botão primário); zero ocorrências de "Agentic" e de `@agentic/console` no código, nos testes e nos documentos vivos da console (fora do histórico do ADR-037, item 6).
- **SC-009**: Em teste, a chave em claro aparece só no diálogo da criação ou da rotação: depois de fechado, ela não está em nenhum texto da tela, na memória de dados da API nem no registro do navegador; criar uma chave e dar acesso a um sistema leva menos de 2 minutos sem tocar no `assistants.yaml`.
- **SC-010**: Zero violações automáticas de WCAG 2.2 AA na tela de chaves, no diálogo da chave e na aba de acesso, nos dois temas, operáveis só pelo teclado.

## Assumptions

- A console é usada em navegador de desktop ou tablet; celular não é alvo.
- A console é servida na mesma origem da plataforma, pela instalação; sem chamadas entre origens.
- O formato da API de administração está no contrato `admin-api.md` da 008; a console não lê nada além dele e do
  protocolo da 012.
- Usuários comuns não usam a console; Assistants e MCPs próprios continuam pela API pública.
- O visual é desenhado antes da implementação e aprovado pelo mantenedor (design.md).
- US8 (ADR-037, ADR-038, ADR-039): a mudança do hover escuro vale também para as páginas da 012, que usam os mesmos tokens; a passada da 013 muda os dois CSS e os dois testes de contraste. O Penpot não estava conectado em 2026-10-20; a verificação visual segue o `DESIGN.md`.
