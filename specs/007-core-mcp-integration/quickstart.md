# Quickstart — 007 MCP Integration (Fase 3)

Roteiro de validação do módulo. Comandos a partir de `axon-ai/`, com `XDG_DATA_HOME=$HOME/.local/share` nesta máquina.
O encaixe na plataforma em execução (rotas da 008, boot da 011, catálogo da 003) é das passadas delas; aqui o módulo é
validado pelos próprios seams.

## Pré-requisitos

```bash
uv sync                                                       # traz o SDK de MCP (mcp>=2.2,<3)
docker run -d --rm --name axon-ai-pg -e POSTGRES_PASSWORD=pg -p 55432:5432 postgres:17   # para o adapter Postgres
```

## Suítes

```bash
uv run pytest packages/core/tests/mcp -v                                         # memória, SDK local, stdio
AXON_TEST_POSTGRES_DSN=postgresql://postgres:pg@localhost:55432/postgres \
  uv run pytest packages/core/tests/mcp -v                                       # + Postgres
uv run mypy && uv run ruff check packages && uv run lint-imports
```

## O que cada parte prova

| Cenário | Onde | Esperado |
|---|---|---|
| US1 — MCP registrado aparece sem restart | `contract/test_discovery.py`, `contract/test_catalog.py` | servidor criado depois do cliente aparece na descoberta seguinte; desabilitado some de `aliases` |
| US1 cen. 3 — `stdio` pela API | `contract/test_registry.py` | recusado com `field="transport"`; o do arquivo aparece global e somente leitura |
| US2 — credencial por referência | `contract/test_credentials.py`, `contract/test_transport.py`, `integration/test_secret_scan.py` | o servidor de teste recebe `Authorization`; nem o banco, nem os logs, nem os valores devolvidos contêm o segredo |
| US3 — cliente restrito | `contract/test_restricted_client.py` | alias fora do grant → `UnknownServer`, sem I/O |
| US4 — MCP de usuário | `contract/test_isolation.py`, `contract/test_registry.py` | B não vê nem alcança o MCP de A; `stdio`, credencial, `http` e alias sem `~` recusados; global não liberado recusado |
| US5 — política por servidor | `contract/test_policy.py` | de 50 tools anunciadas, só as 3 da allowlist, com a marca de escrita; resultado grande cortado com marca |
| US6 — SSRF | `unit/test_network.py`, `contract/test_guarded_backend.py`, `integration/test_ssrf.py` | 100% dos vetores de [contracts/network-policy.md](contracts/network-policy.md) bloqueados, inclusive rebinding; host interno só para global; com `allowed_hosts`, host fora dela bloqueado para global e usuário |
| FR-010 — cache | `contract/test_discovery.py` | segunda descoberta no TTL não toca o servidor; mudar o registro invalida |
| FR-011 — saúde | `contract/test_registry.py` | lista as tools anunciadas e as que faltam; credencial ausente aparece nomeando a referência |

## Manual: um servidor MCP de verdade

Com um servidor MCP qualquer escutando em `http://127.0.0.1:9000/mcp` (por exemplo, o servidor de exemplo do SDK):

```python
# num REPL com `uv run python`, montando o serviço com os adapters reais e a exceção de host interno
from axon_ai.mcp import api
# 1. create_global(alias="local", endpoint="http://127.0.0.1:9000/mcp", policy.allowed_tools=[...])
# 2. check("local") → ServerHealth com as tools anunciadas
# 3. client_for(grant com mcp_aliases={"local"}).discover(["local"]) → as tools da allowlist
# 4. sem "127.0.0.1" nos hosts internos, o mesmo check → bloqueado pela política de rede
```

A montagem completa — arquivo do operador, perfis e rotas — entra no quickstart da passada da 011 e da 008.
