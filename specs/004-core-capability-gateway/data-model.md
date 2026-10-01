# Data Model — 004 Capability Gateway (Fase 3)

Entidades da spec (Capability Catalog, Tool Call, Fenced Tool Result, Audit Record) e os value objects dos seams, todos
dataclasses congeladas em `api.py`, exceto os registros internos marcados como tal.

## ToolContext — o que só o motor sabe

| Campo | Tipo | Regra |
|---|---|---|
| `request_id` | str | não vazio; liga trace e auditoria |
| `reference_time` | datetime | com fuso; a mesma da Turn View (ADR-013), repassada ao handler nativo |
| `retrieval_filters` | Mapping[str, Mapping[str, JSONValue]] | pack → `retrieval_filters` da fatia dele (contrato 001); nunca do modelo |

## CatalogTool — o que o controller vê

`name` (com namespace), `description`, `parameters` (o esquema), `kind` (`native`, `retrieval`, `mcp`), `mutates`. Sem
handler nem retriever: o motor não tem como executar nada por fora do gateway.

## ToolSession — o catálogo e o gateway de uma execução

| Membro | O que é |
|---|---|
| `tools` | Mapping nome com namespace → `CatalogTool`, na ordem de montagem (packs na ordem do grant, depois MCPs) |
| `unavailable` | Mapping alias → motivo, dos MCPs que falharam na descoberta |
| `execute(call)` | `ToolCall` → `FencedToolResult` |

## ToolCall

`name` (texto como o controller pediu) e `arguments` (Mapping[str, JSONValue]). Nome fora de `tools` não é erro de
programação: é o caso "tool inexistente".

## FencedToolResult

| Campo | Regra |
|---|---|
| `name` | o nome pedido |
| `kind` | o tipo da tool, ou `None` se ela não existe |
| `status` | `ok`, `error`, `timeout`, `unknown` (fora do catálogo), `invalid_arguments` |
| `text` | o conteúdo cercado e neutralizado ([contracts/fencing.md](contracts/fencing.md)); sempre presente |
| `truncated` | o conteúdo passou do limite e foi cortado com marca |
| `error` | o motivo, quando `status` não é `ok` |
| `chunks` | só em recuperação: os `Chunk` devolvidos, com proveniência (princípio IX) |

## GatewayLimits — configuração do operador (clarificação 3)

| Campo | Faixa | Default |
|---|---|---|
| `timeout_ms` | 1 000–300 000 | 30 000 |
| `max_response_bytes` | 1 024–1 048 576 | 16 384 |

Valem para tools nativas e de recuperação; em MCP vale o mais restritivo entre isto e a política do servidor (007).

## PackTool — o que a 002 entrega (porta `PackToolSource`, interno)

`name` (`<pack>.<tool>`), `pack`, `spec` (`ToolSpec` do contrato 001 — com handler se nativa; o de recuperação via
`retrieval_tool_spec`), `retriever` (`NamedRetriever`, só em recuperação; carrega as coleções).

## Entrada do catálogo (interno, `domain/catalog.py`)

`CatalogTool` + a origem: `pack` (nome do pack e o handler ou retriever) ou `mcp` (alias e nome local da tool), e o
esquema já conferido. É o que a sessão usa para despachar; nunca sai do módulo.

## AuditRecord (clarificação 4)

| Campo | Regra |
|---|---|
| `id` | gerado pelo armazenamento |
| `request_id`, `principal`, `assistant` | da execução |
| `tool`, `kind` | nome com namespace e tipo |
| `arguments` | inteiros, JSON |
| `status` | `started` (aberto; continua assim se o fechamento falhar), `ok`, `error`, `timeout` |
| `result` | o texto **como o modelo recebeu** — cercado e cortado no limite; `None` enquanto `started` |
| `started_at`, `finished_at` | relógio da porta; `finished_at` `None` enquanto `started` |

## AuditFilter

`principal`, `assistant`, `tool` (cada um opcional, comparação exata), `since`, `until` (opcionais, com fuso), `limit`
(1–1 000, default 100). Resultado do mais recente para o mais antigo.

## ToolCall (evento de trace, 009)

`request_id`, `tool`, `kind` (`None` se `unknown`), `status`, `duration_ms`, `size_bytes` (do conteúdo entregue),
`truncated`. Sem argumentos nem conteúdo.

## Erros

| Situação | Resultado |
|---|---|
| Nome fora do catálogo | `FencedToolResult(status="unknown")`, "tool inexistente: <nome>" |
| Argumentos fora do esquema | `status="invalid_arguments"`, nomeando o caminho; nada despachado |
| Handler ou retriever levanta | `status="error"`, tipo e primeira linha da mensagem |
| Prazo vencido | `status="timeout"` |
| Auditoria não abre | `status="error"`, "auditoria indisponível"; a tool **não** é executada |
| Dois itens com o mesmo nome no catálogo | `CatalogConflict` na montagem, nomeando o nome |
| MCP falha na descoberta | alias em `unavailable`; `ExecutionError(stage="catalog")` no trace |
| Esquema de tool inválido | a tool sai do catálogo; motivo no trace |
