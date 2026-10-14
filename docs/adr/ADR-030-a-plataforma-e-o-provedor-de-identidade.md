# ADR-030 — A plataforma é o provedor de identidade

- **Status:** Aceita · 2026-10-13
- **Specs afetadas:** [012-core-identity](../../specs/012-core-identity/spec.md) (nova),
  [003-core-assistants-access](../../specs/003-core-assistants-access/spec.md) (premissa "provedor OIDC externo; a
  plataforma não gerencia senhas"; origem das chaves do verificador OIDC),
  [011-core-bootstrap](../../specs/011-core-bootstrap/spec.md) (etapa e configuração da identidade),
  [002-core-pack-runtime](../../specs/002-core-pack-runtime/spec.md) (research R37–R40: o Keycloak sai da instalação);
  constituição (linha "Identidade" na tabela de stack)
- **Origem:** pedido do mantenedor (2026-10-13): login por usuário e senha, com login Google opcional, sem Keycloak; e a
  decisão, no mesmo dia, de que a plataforma emite os tokens que o Open WebUI repassa

## Contexto

Na Fase 7, a identidade de quem conversa vem de um Keycloak de desenvolvimento: o Open WebUI faz login nele e repassa o
access token do usuário (`system_oauth`), e a 003 verifica o JWT localmente pelo JWKS do emissor, com `sub` e `groups`.
A ACL dos Assistants (`group:equipe`) e a lista de modelos por usuário dependem desses grupos.

Tirar o Keycloak deixa três opções: outro provedor externo, o login nativo do Open WebUI repassando o usuário por
cabeçalho, ou a própria plataforma emitindo os tokens. O login com Google sozinho não basta: o access token do Google é
opaco (não é JWT), não traz grupos e só serve à API do Google.

## Decisão

1. Um módulo novo do core, **identidade** (spec **012**, `ai_core/identity/`), é o provedor OIDC da plataforma:
   - contas locais (usuário, e-mail, senha com hash argon2id), grupos e vínculo com o Google;
   - login com Google **só para usuários cadastrados**: o e-mail verificado tem de bater com uma conta ativa, e conta
     desconhecida é recusada. O cliente Google (id e segredo) vem da instalação; liga e desliga é ajuste de runtime;
   - um subconjunto mínimo do OIDC: discovery, `authorize` só com `code` (PKCE obrigatório para cliente público),
     `token`, `userinfo`, `jwks`, `revoke` e `logout`. Sem registro dinâmico de cliente, sem tela de consentimento, sem
     fluxo implícito;
   - a página de login é servida pelo próprio módulo, porque o Open WebUI precisa dela mesmo numa instalação sem
     console (ADR-029).
2. Os endpoints do protocolo são o **adapter primário HTTP da 012**, montado pela composition root (011) no mesmo app da
   008. A 008 não aprende OIDC; a 012 não conhece Assistants, ACL nem as rotas da 008. O framework HTTP fica em
   `identity/adapters/`, como nas demais.
3. Os clientes OIDC são do operador (`identity.yaml`): o Open WebUI, confidencial, com segredo por referência; e a
   console, pública. URIs de redirecionamento exatas.
4. O access token é um JWT RS256 com `kid`, curto (10 min), com `preferred_username` (o subject continua `user:<nome>`,
   como na Fase 7) e `groups`. A chave de assinatura é gerada no primeiro boot e guardada cifrada (ADR-033).
5. A **003 continua verificando o JWT localmente** pela porta `OidcVerifier`. Só muda a origem das chaves: com a
   identidade ligada, a 011 injeta o JWKS do provedor em processo, sem chamada HTTP da plataforma para si mesma. A
   plataforma confia num **único emissor**: identidade ligada junto com `AI_CORE_OIDC_ISSUER` é erro de configuração.
   O caminho de IdP externo continua existindo, como alternativa de instalação.
6. O grupo de administração continua sendo o de `assistants.yaml` (`api_keys.admin_group`). A 012 o recebe da 011 como
   grupo protegido: não se apaga, e o último membro ativo não sai.
7. Usuário nunca é apagado, só desativado: ACL, Assistants de usuário e conversas usam o subject, e um nome reaproveitado
   herdaria tudo isso.

## Alternativas rejeitadas

*Outro IdP externo leve (Dex, Authentik, Zitadel).* Troca um serviço por outro: continua um contêiner a mais no hardware
alvo (12 GB, ARM64), e o cadastro de usuários e grupos ficaria fora da console ou exigiria integrar a API administrativa
de cada produto.

*Login nativo do Open WebUI repassando o usuário por cabeçalho, com uma chave de serviço.* Dois cadastros de usuários
(Open WebUI e plataforma), grupos mapeados à parte, e quem tiver a chave de serviço se passa por qualquer usuário.

*Login novo só na console, com o Open WebUI numa chave de serviço única.* A plataforma deixaria de saber quem conversa:
perde a lista de Assistants por usuário e a ACL por grupo da Fase 7.

*Servidor OAuth de uma biblioteca (authlib).* Fica para o research do plano da 012. O servidor do authlib é desenhado em
torno de Flask e Django, e para este subconjunto a cola pode pesar mais que o protocolo. A decisão aqui é o papel da
plataforma, não a biblioteca.

## Consequências

- A premissa da 003 "provedor OIDC externo; a plataforma não gerencia senhas" é substituída por esta decisão.
- A plataforma passa a guardar senhas e chaves de assinatura: a 012 tem suíte adversarial do protocolo e de força
  bruta, e a release que a introduz passa por ela.
- Usuário desativado mantém o access token até ele expirar (no máximo 10 min); mudança de grupo vale no próximo refresh.
- Contas, sessões e chaves exigem o perfil `persistent`: uma instalação com interface (Open WebUI ou console) passa a ter
  Postgres.
- Usuários do Open WebUI já criados estavam ligados ao `sub` do Keycloak; a migração da instalação documenta como
  religá-los (volume novo ou junção por e-mail).
