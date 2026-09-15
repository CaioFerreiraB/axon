# Design — 007 MCP Integration

> Insumo técnico pré-aprovado para `/speckit-plan`. Origem: arch-v1 §5, §17, §18, §28; ADR-003, ADR-012.

## Localização

```text
ai-core/packages/core/src/ai_core/mcp/
├── api.py        # seams MCP Registry e cliente restrito ao grant; McpServer, SecurityPolicy
├── domain/       # regras de escopo e dono, stdio só global, filtro por allowlist, marca de escrita,
│                 # política SSRF (IP resolvido permitido?) — puro
├── ports.py      # McpServerStore, SecretResolver, McpTransport, DnsResolver, DiscoveryCache
├── service.py    # registry + cliente restrito (implementa MCPClient do contrato 001) + descoberta com cache
└── adapters/
    ├── registry_memory.py     # McpServerStore — Fases 1–2 e testes
    ├── registry_postgres.py   # McpServerStore — Fase 3
    ├── transport_http.py      # McpTransport (http/sse)
    ├── transport_stdio.py     # McpTransport (stdio, só escopo global)
    ├── dns_system.py          # DnsResolver
    └── cache_memory.py        # DiscoveryCache (TTL)
```

## Registry (arch-v1 §17)

MCP é protocolo: tools são descobertas em runtime via `tools/list`. Portanto **adicionar um MCP é dado puro** — sem código, sem restart.

```text
mcp_servers
├── id
├── alias                        # "finance" — o que a config referencia
├── transport                    # stdio | http | sse   (stdio: apenas scope global)
├── endpoint                     # url ou comando
├── auth_type
├── credential_ref               # ponteiro pro secret store, NUNCA o segredo
├── owner_principal              # dono
├── scope                        # global | user   ← nível de usuário
├── enabled
└── security_policy
    ├── timeout_ms
    ├── max_response_bytes
    ├── allowed_tools[]          # allowlist: server expõe 50, assistant vê 3
    └── write_tools[]            # quais mutam estado
```

`owner_principal` + `scope: user` permite cada usuário registrar os MCPs dele, visíveis só para ele. `credential_ref` em vez do segredo evita credencial em texto plano no banco.

## Cliente

```python
class MCPClient(Protocol):          # contrato 001
    async def discover_tools(self, aliases: list[str]) -> list[ToolSpec]: ...
    async def execute(self, alias: str, tool: str, arguments: dict) -> ToolResult: ...
```

`discover_tools` recebe **aliases já autorizados**, nunca URLs. A resolução alias → endpoint + credencial acontece server-side.

## Rede

Como qualquer pessoa poderá instalar a plataforma, o cliente MCP aplica:

- allowlist de hosts
- bloqueio de `localhost` e faixas de IP privadas (defesa contra SSRF) — checado no IP resolvido, a cada conexão e a cada redirecionamento
- timeout e limite de tamanho de resposta
- credenciais nunca trafegam na requisição do usuário

A decisão "este IP pode ser alcançado?" é função pura em `domain/`, testável com uma tabela de vetores de SSRF. Resolver
o nome (`DnsResolver`) e abrir a conexão (`McpTransport`) são adapters; o transporte consulta a política a cada conexão
e a cada redirecionamento.

## Transporte `stdio` — restrição adicionada na tradução

arch-v1 lista `stdio` como transporte e permite `scope: user`. Combinados, isso deixaria um usuário final registrar um **comando** a ser executado no host do core — contradizendo ADR-003 ("usuário final nunca executa código arbitrário no processo do core"). Regra: `stdio` só para `scope: global` (registrado pelo operador). MCP de usuário é sempre `http`/`sse`.

## Persistência

| Dado | Porta | Adapter | Quando |
|---|---|---|---|
| MCP registry | `McpServerStore` | memória → Postgres | Fase 3 |
| Cache de descoberta | `DiscoveryCache` | memória, TTL | Fase 3 |

## Portas e adapters **[ADR-012]**

| Porta | Tipo | Adapters por fase | Teste |
|---|---|---|---|
| MCP Registry | primária (seam) | `service.py` | CRUD por escopo, isolamento entre usuários |
| Cliente MCP restrito (`MCPClient`, contrato 001) | primária (seam) | `service.py` | alias fora do grant → "servidor desconhecido" |
| `McpServerStore` | secundária | memória → Postgres (Fase 3) | em memória + conformidade contra Postgres; varredura de segredos |
| `SecretResolver` | secundária | variáveis de ambiente (adapter único, injetado pela 011) | dicionário em memória |
| `McpTransport` | secundária | http/sse; stdio só global | MCP de teste em processo |
| `DnsResolver` | secundária | resolvedor do sistema | resolvedor fixo com vetores de SSRF |
| `DiscoveryCache` | secundária | memória, TTL | relógio fixo |

Consome por seam: Principal e Execution Grant (003), via `ai_core.assistants.api`.
