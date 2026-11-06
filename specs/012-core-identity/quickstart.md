# Quickstart — validação da 012 Identity

Roteiro de validação; o código e as tarefas ficam em `tasks.md`. Comandos a partir de `axon-ai/`, com
`XDG_DATA_HOME=$HOME/.local/share`.

## 1. Suítes do módulo

```bash
uv run pytest packages/core/tests/identity
uv run mypy && uv run ruff check packages && uv run lint-imports
```

Esperado: unidades do domínio, conformidade dos três seams e das portas em memória, e a suíte de protocolo com o
authlib como RP ([contracts/oidc.md](contracts/oidc.md)) passam; os contratos de import novos estão verdes.

## 2. Portas contra o Postgres real

```bash
docker run -d --rm --name axon-ai-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:17
AXON_TEST_POSTGRES_DSN=postgresql://postgres:pg@localhost:55432/postgres uv run pytest packages/core/tests/identity
```

Esperado: as suítes de `AccountStore`, `GrantStore`, `SigningKeyStore` e `IdentitySettingsStore` passam contra o
schema `identity`; o código é de uso único mesmo com duas trocas concorrentes.

## 3. Cenários da spec cobertos pela suíte

| Cenário | Onde |
|---|---|
| US1: login por senha a partir de um cliente confidencial; token com `preferred_username` e `groups` | `integration/test_protocol.py` |
| US1: respostas indistinguíveis (inexistente, senha errada, desativada) — SC-005 | `integration/test_login_uniform.py` |
| US2: admin inicial só com zero contas; senha temporária obrigatória | `contract/test_account_admin.py`, `integration/test_bootstrap.py` |
| US3: cliente público sem PKCE recusado; audiência da console | `integration/test_protocol.py` |
| US4: Google só para cadastrados (simulado) — SC-003 | `integration/test_google.py` |
| US5: bloqueio depois de 5 falhas | `unit/test_attempts.py`, `integration/test_login_uniform.py` |
| US6: desativar revoga a renovação | `integration/test_protocol.py` |
| US7: rotação normal e forçada — SC-007 | `contract/test_public_key_set.py` |
| FR-020: nenhum segredo nos logs | `integration/test_no_secrets_in_logs.py` |

## 4. Prova manual com o Open WebUI

Fica para a passada da 002 (instalação sem Keycloak), depois do encaixe na 011 e na 003: entrar pelo formulário da
plataforma como `ana` e `bia` e comparar as listas de modelos (o `check-webui.py` reescrito).

---

## Fase 9, incremento 9.5 (2026-10-20): US8 — as páginas com a marca Axon

A partir de `axon-ai/`, com `XDG_DATA_HOME=$HOME/.local/share` nesta máquina. Decisões em [research.md](research.md)
R20–R26.

```bash
uv run pytest packages/core/tests/identity -m us8 -v
uv run pytest packages/core/tests/identity packages/core/tests/bootstrap/integration/test_platform_identity.py -q
```

**Esperado**: verde — sem marca própria, o lockup e nenhuma atribuição; com nome ou logotipo, a marca da instalação e
"com Axon"; o favicon em toda página; os SVG servidos iguais aos do `brand-kit`; os pares de texto em AA nos dois temas;
cookie `axon_session`, realm `axon`, rótulos `axon-ai/identity/…`; chave selada com o rótulo antigo para o boot com a
orientação de `rotate --force`.

À mão, com a identidade ligada no `memory` (ver o quickstart da 011, "identidade"):

```bash
AXON_PROFILE=memory AXON_IDENTITY_ENABLED=true AXON_PUBLIC_URL=http://localhost:8000 AXON_COOKIE_SECURE=false \
  AXON_MASTER_KEY=… AXON_IDENTITY_CLIENTS_FILE=… uv run axon serve &
```

Abrir `/oauth2/authorize?…` de um cliente (por exemplo, pela console) e conferir o lockup Axon e o favicon na aba; com
`AXON_DISPLAY_NAME="Instituto Exemplo"`, o nome no lugar principal e "com Axon" no rodapé. Capturas em 390 e 1440 px, claro
e escuro (R26).

## Fase 9, incremento 9.7 (2026-11-04): US9–US11 — apagar conta, um grupo de cada vez, o ator que não administra

A partir de `axon-ai/`, com `XDG_DATA_HOME=$HOME/.local/share`. Decisões em [research.md](research.md) R28–R34; formas em
[data-model.md](data-model.md) e [contracts/identity-api.md](contracts/identity-api.md).

```bash
uv run pytest packages/core/tests/identity -q
AXON_TEST_POSTGRES_DSN=postgresql://postgres:pg@localhost:55432/postgres \
  uv run pytest packages/core/tests/identity -q       # conformidade das portas e a migração 005 sobre dados
uv run pytest && uv run mypy && uv run ruff check packages && uv run lint-imports
```

**Esperado**: verde.
- **US9.**
  - Com dois apagadores de teste, apagar `ana` devolve o relatório com as contagens dos dois e da identidade, sem o
    pseudônimo.
  - A renovação dela é recusada, e `ana` pode ser cadastrada de novo, sem nada da anterior.
  - Os autores de mudanças feitas por `user:ana` passam a `deleted:<16 hex>`, o mesmo valor que os apagadores receberam.
  - Com um apagador que falha uma vez: `DeletionIncomplete`, a conta em apagamento e o nome preso. A segunda tentativa
    conclui com o mesmo pseudônimo.
- **US10.** Pôr `ana` em `equipe` e em `vendas` ao mesmo tempo deixa os dois; repetir não muda a versão.
- **US11.** Com `actor_can_admin=False`, toda recusa da R31 sai com `ActorNotAllowed` e o campo.

O comando `axon users delete` e os `axon groups add|remove` ficam disponíveis na passada da 011, que os registra e liga
os apagadores. A prova ponta a ponta (008 + 011) busca o nome apagado em todos os schemas.
