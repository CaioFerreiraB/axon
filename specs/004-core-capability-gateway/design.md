# Design — 004 Capability Gateway

> Insumo técnico pré-aprovado para `/speckit-plan`. Origem: arch-v1 §8 (`load_capabilities`, `execute_tool`), §16, §18, §28; ADR-005, ADR-012, ADR-013.

## Localização

```text
axon-ai/packages/core/src/axon_ai/capabilities/
├── api.py        # seams Capability Catalog e Tool Gateway; ToolCall, FencedToolResult
├── domain/       # puro
│   ├── catalog.py       # união, namespacing, filtros do grant (ex-lógica do nó load_capabilities)
│   ├── fencing.py       # delimitação de conteúdo não-confiável, truncamento com marca
│   └── write_policy.py  # tools mutantes conforme a visibilidade do Assistant
├── ports.py      # AuditLog
├── service.py    # gateway: despacho por kind, validação de argumentos, timeout, limite, auditoria, emissão ao
│                 # Trace Sink (ex-lógica do nó execute_tool)
└── adapters/
    ├── audit_memory.py     # AuditLog — Fases 1–2 e testes
    └── audit_postgres.py   # AuditLog — Fase 3
```

O antigo `axon_ai/security/` vira `domain/` deste módulo (ADR-012). O motor (spec 005) mantém os passos
`load_capabilities` e `execute_tool` apenas como chamadas finas a este módulo.

## Montagem do catálogo (arch-v1 §8 `load_capabilities`)

1. União das tools dos packs ativos (Pack Registry, spec 002)
2. Mais as tools dos MCPs permitidos pelo grant (via `discover_tools`, com cache por TTL — spec 007)
3. Mais os retrievers, expostos **como tools**
4. Namespacing de todos os nomes: `scouting.search_docs`, `finance.get_transactions`
5. Filtro final pelo `allowed_tools` do grant
6. Remoção de tools `mutates: true` que não estejam em `write_tools` (e de todas, se o Assistant é público)

O resultado é o único universo que o controller conhece.

```python
class CapabilityCatalog(Protocol):
    tools: Mapping[str, ToolSpec]          # nome com namespace → spec
    def for_controller(self, limit: int) -> list[ToolSpec]: ...   # catálogo mínimo em contexto

class ToolGateway(Protocol):
    async def execute(self, call: ToolCall, grant: ExecutionGrant) -> FencedToolResult: ...
```

## Despacho (arch-v1 §8 `execute_tool`)

```text
retrieval → Retriever do pack            → resultado vai para "retrieved" no estado do motor
mcp       → MCPClient.execute(alias...)  → "tool_results"
native    → handler do pack              → "tool_results"
```

Aplica timeout, limite de tamanho de resposta e, para `mutates: true`, a política de autorização de escrita. Resultado entra **fenced** como conteúdo não-confiável.

## Superfície de ataque (arch-v1 §18)

### Conteúdo não-confiável no contexto

1. Todo resultado de tool entra fenced e rotulado como dado.
2. **Saída de tool nunca é instrução.** O system prompt afirma isso explicitamente, e o controller ignora diretivas vindas de resultados.
3. Resultado excedendo `max_response_bytes` é truncado com marca, não silenciosamente cortado.

### Tools de escrita

| Contexto | Comportamento |
|---|---|
| Assistant público | tools mutantes indisponíveis por default |
| Assistant privado | permitidas se declaradas em `write_tools` |
| Qualquer | efeito registrado em auditoria com Principal e argumentos |

### Orçamento como controle de segurança

Rate limit, limite de iteração e teto de tokens não são só custo — impedem que um prompt malicioso transforme uma requisição num loop caro (aplicados por 003 e 005).

## Elos da cadeia de enforcement neste módulo

| # | Camada | O que filtra | Efeito se violado |
|---|---|---|---|
| 3 | Capability | catálogo = união só dos packs do assistant | tool inexistente |
| 4 | MCP | só aliases do assistant (cliente da spec 007) | server desconhecido |
| 5 | Retrieval | allowlist de coleções | query rejeitada |

## Persistência

| Dado | Porta | Adapter | Quando |
|---|---|---|---|
| Auditoria de tool mutante | `AuditLog` | memória → Postgres | Fase 3 |

O cache de descoberta MCP (memória, TTL) é do cliente MCP (spec 007, FR-010); este módulo não mantém cache próprio.

## Portas e adapters **[ADR-012]**

| Porta | Tipo | Adapters por fase | Teste |
|---|---|---|---|
| Capability Catalog | primária (seam) | `service.py` + `domain/catalog.py` | suíte adversarial: 0 tools fora do catálogo |
| Tool Gateway | primária (seam) | `service.py` | timeout, truncamento, fencing, prompt injection |
| `AuditLog` | secundária | memória (Fases 1–2) → Postgres (Fase 3) | em memória + conformidade contra Postgres |

Consome por seam: Pack Registry (002), Execution Grant (003), cliente MCP restrito (007), Trace Sink (009). Retrievers e
handlers nativos chegam dos packs pelo contrato 001.
