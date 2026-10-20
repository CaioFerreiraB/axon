# Quickstart — 003 Assistants & Access (Fase 2, US1–US7)

Guia de validação. Comandos a partir de `axon-ai/`, com `XDG_DATA_HOME=$HOME/.local/share` nesta máquina. Esta passada
entrega o módulo e seus adapters; a conversa por HTTP com autenticação real depende das passadas da 008 e da 011
([research.md](research.md) R2), e o roteiro dela fica nos quickstarts dessas specs.

## Pré-requisitos

```bash
uv sync                      # traz pyjwt[crypto], httpx, psycopg[binary] e psycopg-pool
```

Para a conformidade contra o Postgres real (opcional localmente, obrigatória na CI):

```bash
docker run -d --rm --name axon-ai-pg -e POSTGRES_PASSWORD=pg -p 5432:5432 postgres:17
export AXON_TEST_POSTGRES_DSN=postgresql://postgres:pg@localhost:5432/postgres
```

## Verificação completa

```bash
uv run pytest packages/core/tests/assistants
uv run mypy
uv run ruff check packages
uv run lint-imports          # jwt, httpx, psycopg e yaml só em assistants/adapters; 003 só vê api.py dos outros
```

Sem `AXON_TEST_POSTGRES_DSN`, os casos do adapter Postgres aparecem como *skipped* com o motivo.

## Cenários

### 1. Assistants de sistema e o grant (US1)

```bash
uv run pytest packages/core/tests/assistants/unit/test_assistants_yaml.py \
              packages/core/tests/assistants/contract/test_grant_resolver.py -v -k "us1"
```

Esperado: `mcp: []` produz grant sem alias MCP; dois packs aparecem na ordem declarada; um pack sem flow herda o
`preferred_flow` (ou `chat`); dois packs sem flow deixam o Assistant indisponível; o arquivo da Fase 1 recebe motivos
que dizem o que mudar ([contracts/assistants-yaml.md](contracts/assistants-yaml.md)).

### 2. Duas superfícies de autenticação (US2)

```bash
uv run pytest packages/core/tests/assistants/contract/test_authenticator.py \
              packages/core/tests/assistants/contract/test_oidc_verifier.py -v
```

Esperado: token OIDC assinado por chave local → `user:<sub>` com grupos; chave de API → subject e grupos da chave;
credencial ausente, adulterada, expirada (relógio fixo), `alg: none` ou revogada → `None`; token na superfície privada
e chave na pública → `None`.

### 3. 404, nunca 403 (US3, SC-001)

```bash
uv run pytest packages/core/tests/assistants/contract/test_adversarial.py -v -k "not_found"
```

Esperado: Assistant privado existente pedido por quem não pode e Assistant inexistente levantam o mesmo erro, com a
mesma mensagem; `~x` de outro usuário é indistinguível de `~x` inexistente; a razão entre as medianas de tempo dos dois
casos fica abaixo do limite da suíte.

### 4. A requisição só restringe (US4, SC-002, SC-005)

```bash
uv run pytest packages/core/tests/assistants/contract/test_adversarial.py \
              packages/core/tests/assistants/contract/test_allowlist_parity.py -v
```

Esperado: `geral/openai/gpt-x` com allowlist `ollama/*` → `RequestRejected(field="model")`; `geral/ollama/qwen3:8b` →
grant com esse modelo em `generation` e os demais papéis intactos; hypothesis não encontra pedido cujo grant exceda o
declarado; a regra de allowlist concorda com a da 006 em todos os casos da tabela.

### 5. Descoberta filtrada (US5)

```bash
uv run pytest packages/core/tests/assistants/contract/test_directory.py -v -k "discover"
```

Esperado: para cada Principal da suíte, `discover` devolve exatamente os nomes que `resolve` aceita; um privado com
`group:chefia` aparece para um membro do grupo e para mais ninguém.

### 6. Assistants de usuário (US6)

```bash
uv run pytest packages/core/tests/assistants/contract/test_directory.py \
              packages/core/tests/assistants/contract/test_user_assistant_store.py -v
```

Esperado: criação dentro da política resolve como `~nome` só para o dono, sem restart; modelo ou `rpm` fora do teto →
`PolicyViolation` nomeando o campo; MCP de outro usuário → mesma mensagem de inexistente; Principal sem política →
`NoApplicablePolicy`; dono que sai do grupo vê o Assistant indisponível em `mine` e recebe `AssistantUnavailable` ao
resolver; com Postgres, o Assistant sobrevive a um novo serviço construído sobre o mesmo banco.

### 7. Orçamento (US7)

```bash
uv run pytest packages/core/tests/assistants/contract/test_rate_counter_store.py \
              packages/core/tests/assistants/contract/test_grant_resolver.py -v -k "rate"
```

Esperado: com `rpm: 20` e relógio fixo, a 21ª resolução do par na janela levanta `RateLimited` com `retry_after`
exato; outro Principal no mesmo Assistant resolve; avançado o relógio, o par volta a resolver.

### 8. Chaves e CLI (FR-015, R14)

```bash
uv run pytest packages/core/tests/assistants/contract/test_key_admin.py \
              packages/core/tests/assistants/integration/test_cli.py -v
```

Esperado: `keys create` imprime a chave uma vez e ela autentica; `keys list` não a mostra; `keys revoke` faz a chamada
seguinte ser recusada; ator fora do `admin_group` recebe `NotFound`; `assistants validate` sai com 0, 1 ou 2 conforme
[contracts/cli.md](contracts/cli.md).

## Critérios de sucesso

| Critério | Onde se verifica |
|---|---|
| SC-001 — não autorizado não distingue privado de inexistente | cenário 3 |
| SC-002 — nada fora do grant é alcançável | cenário 4 (hypothesis) |
| SC-003 — zero código para mudar Assistant; de usuário sem restart | cenários 1 e 6 |
| SC-004 — 100% das referências pendentes detectadas antes de servir | cenários 1 e 8 (`validate`) |
| SC-005 — campos de ampliação recusados antes de qualquer modelo | cenário 4 (id de modelo); o corpo da requisição, na 008 com `WIDENING_FIELDS` |

## Fase 3 (2026-10-02): regras de referência novas

### Cenários US8 2–4 e Assistants de usuário

```bash
uv run pytest packages/core/tests/assistants -m "us8 or us6" -v
```

Esperado: Assistant `agentic` sem `controller` indisponível nomeando o papel; entradas mortas de `allowed_tools` e
`write_tools` (sem namespace, namespace fora do Assistant, tool que o pack não oferece) indisponíveis nomeando a
entrada; alias MCP igual a pack indisponível nomeando a colisão; criação e atualização de Assistant de usuário com
qualquer uma delas → `RequestRejected` com o campo ([contracts/assistants-yaml.md](contracts/assistants-yaml.md),
"Fase 3").

### Pela plataforma de verdade

```bash
cat > /tmp/assistants.yaml <<'YAML'
assistants:
  sem-controller:
    visibility: public
    auth: { schemes: [oidc, api_key], allow: ["*"] }
    flow: agentic
    packs: [generic]
    models: { generation: ollama/qwen3:1.7b, allow: ["ollama/*"] }
YAML
printf 'packs:\n  generic:\n    enabled: true\n' > /tmp/packs.yaml
AXON_PROFILE=test AXON_PACKS_FILE=/tmp/packs.yaml AXON_ASSISTANTS_FILE=/tmp/assistants.yaml \
  uv run axon assistants validate; echo $?
```

Esperado: código 1 e a linha de `sem-controller` dizendo `models: o flow 'agentic' exige o papel 'controller', que o
Assistant não declara`.

---

## Fase 9, incremento 9.5 (2026-10-20): US11 — credenciais com o nome Axon

A partir de `axon-ai/`, com `XDG_DATA_HOME=$HOME/.local/share` nesta máquina. Decisões em [research.md](research.md)
R33–R37.

```bash
uv run pytest packages/core/tests -m us11 -v
uv run pytest packages/core/tests/assistants packages/core/tests/bootstrap/integration/test_boot_phase9.py -q
```

**Esperado**: verde — a chave emitida tem o formato `axn_<16 hex>_<segredo>`; `aic_…` e os tokens com `ai-core` ou
`ai-core-admin` são não autenticados nas três superfícies; o token `axon` não entra na administração; o `axon-admin` de
admin entra; o `TEST_API_KEY` do perfil `test` começa com `axn_`.

À mão, no perfil `memory`:

```bash
AXON_PROFILE=memory AXON_DEV_API_KEY=aic_0123456789abcdef_dev uv run axon health   # recusada: formato axn_<16 hex>_<…>
AXON_PROFILE=memory AXON_DEV_API_KEY=axn_0123456789abcdef_dev uv run axon serve &
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer axn_0123456789abcdef_dev" localhost:8000/private/v1/health
curl -s -o /dev/null -w '%{http_code}\n' -H "Authorization: Bearer aic_0123456789abcdef_dev" localhost:8000/private/v1/health
```

**Esperado**: o primeiro comando sai com erro de configuração que cita `axn_<16 hex>_<…>`; depois, `200` com a chave
nova e `401` com a antiga.
