# Feature Specification: Console de administração

**Feature Branch**: `013-core-admin-console`

**Created**: 2026-10-13

**Status**: Draft

**Input**: Pedido do mantenedor (2026-10-13): interface gráfica simples para aplicar configurações — login por usuário
e senha ou Google; modelos e MCPs de cada Assistant, sobrepondo o `assistants.yaml` quando a flag do YAML permite;
dashboard de requisições, tokens e custo por modelo e por dia; Langfuse; ajustes de login; instalação com ou sem a
interface. ADR-029, ADR-031, ADR-032, ADR-033, ADR-034.

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
  [ADR-034](../../docs/adr/ADR-034-trace-com-destinos-e-conteudo-opcional.md).

## Clarifications

### Session 2026-10-13

- Q: A console (e a página de login, que usa o mesmo visual) deve ter tema escuro? → A: Claro e escuro. A console abre no tema do sistema operacional e tem um botão para trocar, lembrado no navegador; a página de login da 012 segue o tema do sistema.

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
- **FR-020**: A console DEVE mostrar o nome e, se houver, o logotipo da instalação, os mesmos da página de login (012),
  lidos da API; sem eles, o nome neutro da plataforma.

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

## Assumptions

- A console é usada em navegador de desktop ou tablet; celular não é alvo.
- A console é servida na mesma origem da plataforma, pela instalação; sem chamadas entre origens.
- O formato da API de administração está no contrato `admin-api.md` da 008; a console não lê nada além dele e do
  protocolo da 012.
- Usuários comuns não usam a console; Assistants e MCPs próprios continuam pela API pública.
- O visual é desenhado antes da implementação e aprovado pelo mantenedor (design.md).
