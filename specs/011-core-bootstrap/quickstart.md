# Quickstart — 011 Bootstrap (Fase 1, US1–US3)

Guia de validação. Comandos a partir de `axon-ai/`, com `XDG_DATA_HOME=$HOME/.local/share` nesta máquina.

## Pré-requisitos

```bash
uv sync                      # traz uvicorn e instala o comando `axon`
```

## Verificação completa

```bash
uv run pytest
uv run mypy
uv run ruff check packages
uv run lint-imports          # ninguém importa o bootstrap; ninguém importa internals de outro módulo
```

## Cenários

### 1. Ordem de boot e falha fechada (US1)

```bash
uv run pytest packages/core/tests/bootstrap/contract -v
```

Esperado: as etapas rodam na ordem declarada; falha crítica interrompe e as seguintes não rodam; falha degradável
segue com o motivo registrado; o encerramento libera recursos na ordem inversa.

### 2. Perfis (US2)

```bash
uv run pytest packages/core/tests/bootstrap/unit/test_profiles.py -v
```

Esperado: os dois perfis atendem todas as portas exigidas; perfil incompleto é recusado nomeando a porta; o relógio
entregue ao motor, à API e ao trace é o mesmo objeto.

### 3. Plataforma inteira em memória (US3, SC-003)

```bash
uv run pytest packages/core/tests/bootstrap/integration -v
```

Esperado: `platform(profile="test")` devolve a plataforma montada e uma conversa completa acontece por HTTP, sem rede
e sem serviço externo.

### 4. Pack defeituoso não derruba o boot (SC-004)

```bash
uv run pytest packages/core/tests/bootstrap/integration -k degradado -v
```

Esperado: com um pack em erro na configuração, o boot conclui, a etapa `packs` aparece como degradada com o pack
nomeado, e um Assistant que não depende dele atende normalmente.

## Subindo a plataforma de verdade

```bash
cat > /tmp/packs.yaml <<'YAML'
packs:
  generic:
    enabled: true
YAML

cat > /tmp/assistants.yaml <<'YAML'
assistants:
  geral:
    flow: chat
    packs: [generic]
    models:
      generation: ollama/qwen3:1.7b
    allow: ["ollama/*"]
YAML

ollama serve &
ollama pull qwen3:1.7b

AXON_PACKS_FILE=/tmp/packs.yaml \
AXON_ASSISTANTS_FILE=/tmp/assistants.yaml \
uv run axon serve
```

Em outro terminal:

```bash
curl -N http://127.0.0.1:8000/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{"model": "geral", "messages": [{"role": "user", "content": "oi"}], "stream": true}'
```

Esperado: o relatório de boot no terminal do servidor, com as cinco etapas; e os pedaços da resposta chegando um a
um, com `data: [DONE]` no fim. **É a conversa ponta a ponta da Fase 1** — HTTP, motor, pack de referência e modelo
local.

Com `AXON_TRACE_DIR=/tmp/trace`, cada requisição vira registros no arquivo do dia: execução iniciada, chamada de
modelo com tokens e duração, validação e fim.

## Montando a plataforma numa suíte

```python
from axon_ai.bootstrap.wiring import platform

plataforma = platform(profile="test")
cliente = TestClient(plataforma.app)
```

É assim que a suíte de um pack externo testa o pack contra a plataforma de verdade, sem copiar montagem.

---

## Fase 2 (US2, US4, US5, autenticação real)

```bash
uv run pytest packages/core/tests/bootstrap -v                     # perfis, saúde, CLI, plataforma no test
AXON_TEST_POSTGRES_DSN=postgresql://postgres:pg@localhost:55432/postgres \
  uv run pytest packages/core/tests/bootstrap -k persistent -v     # perfil persistente contra Postgres
```

Esperado: os três perfis atendem todas as portas; sem credencial, 401 em qualquer perfil; no `test`, as credenciais
exportadas conversam; no `persistent`, o boot migra `assistants` e `http`, uma chave emitida por `axon keys create`
autentica na API e uma conversa sobrevive a uma plataforma nova sobre o mesmo banco; banco inacessível para o boot
nomeando `database` sem imprimir a URL; a saúde é `degraded` (200) com um modelo fora do ar e `down` (503) com o banco
fora; `axon --help` lista todos os subcomandos ([contracts/cli.md](contracts/cli.md)).

Manual, com Postgres local e Ollama:

```bash
export AXON_PROFILE=persistent AXON_DATABASE_URL=postgresql://postgres:pg@localhost:55432/postgres
export AXON_PACKS_FILE=packs.yaml AXON_ASSISTANTS_FILE=assistants.yaml
uv run axon keys create --subject user:caio --group operadores   # a chave sai na última linha
uv run axon serve
```

## Fase 3 (registry MCP, gateway de tools e `agentic`)

Sem dependência nova. A partir de `axon-ai/`, com `XDG_DATA_HOME=$HOME/.local/share`.

### Ordem de boot, arquivo do operador e `agentic` nos perfis

```bash
uv run pytest packages/core/tests/bootstrap -k "mcp or agentic or audit or override" -v
```

Esperado ([contracts/boot-sequence.md](contracts/boot-sequence.md), itens 13–18): `mcp_registry` entre `packs` e
`engine`; `mcp.yaml` malformado para o boot em `configuration`; entrada com problema degrada a etapa; `agentic` em
`flows()` nos três perfis; loggers `mcp.*` em `INFO` com a raiz em `DEBUG`.

### Conversa `agentic` + MCP ponta a ponta, sem rede (US3 cen. 3)

```bash
uv run pytest packages/core/tests/bootstrap/integration/test_platform_agentic_mcp.py -v
```

Esperado: a plataforma sobe pelo perfil `test` com um controller programado e um servidor MCP programado (trocas de
porta); `POST /v1/chat/completions` com `Bearer <TEST_OIDC_TOKEN>` para um Assistant `agentic` que declara o alias;
o transporte programado recebe `call_tool` da tool do servidor, a resposta chega com `finish_reason: "stop"` e o trace
da requisição tem `controller_decision` e `tool_call`.

### Perfil persistente com Postgres

```bash
docker run -d --rm --name axon-ai-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:17
AXON_TEST_POSTGRES_DSN=postgresql://postgres:pg@localhost:55432/postgres \
  uv run pytest packages/core/tests/bootstrap -k "persistent" -v
```

Esperado: as migrações de `mcp` e `capabilities` rodam no boot; um servidor criado pelo registry sobrevive a um novo
boot; `axon audit` lista o registro de uma tool de escrita.

### Subindo com um servidor MCP de verdade (manual)

```bash
cat > /tmp/mcp.yaml <<'YAML'
# formato: specs/007-core-mcp-integration/contracts/mcp-yaml.md
servers:
  local:
    transport: http
    endpoint: http://localhost:9000/mcp
    policy:
      allowed_tools: [eco]
network:
  internal_hosts: [localhost]
YAML
AXON_MCP_FILE=/tmp/mcp.yaml AXON_DEV_API_KEY=axn_0123456789abcdef_dev uv run axon serve
curl -s -H "Authorization: Bearer axn_0123456789abcdef_dev" localhost:8000/private/v1/health | jq .
```

Esperado: um item `mcp:<alias>` por servidor do arquivo; servidor fora do ar deixa a saúde `degraded` (200).

---

## Fase 9, incremento 9.5 (2026-10-20): identidade Axon (US7)

A partir de `axon-ai/`, com o `XDG_DATA_HOME=$HOME/.local/share` desta máquina:

```bash
uv sync
uv run axon --version                                     # axon-ai 0.7.0rc1
AXON_PROFILE=memory AXON_DEV_API_KEY=axn_0123456789abcdef_dev uv run axon serve &
curl -s -H "Authorization: Bearer axn_0123456789abcdef_dev" localhost:8000/private/v1/health | jq .status
kill %1
AI_CORE_PROFILE=memory uv run axon health; echo "código $?"  # recusa: AI_CORE_PROFILE → AXON_PROFILE; código 1
uv run python -c "import ai_core" 2>&1 | tail -1          # ModuleNotFoundError: corte seco
```

Esperado: a versão nova; a saúde `ok` com o prefixo novo; a recusa com a linha da variável e o código 1; o módulo antigo
ausente. A suíte inteira (`uv run pytest && uv run mypy && uv run ruff check packages && uv run lint-imports`), a
conformidade Postgres com `AXON_TEST_POSTGRES_DSN` e a console (`npm run typecheck && npm run lint && npm test`, a partir
de `axon-ai/console/`) passam com os nomes novos. A chave tem o prefixo `axn_` desde a passada da 003.
