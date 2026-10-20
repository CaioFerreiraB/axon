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
