# Data Model — 007 MCP Integration (Fase 3)

Entidades da spec (MCP Server, Security Policy, Credential Reference) mais os value objects que os seams publicam.
Todos são dataclasses congeladas em `api.py`, exceto os registros internos marcados como tal. Regras de validação em
[research.md](research.md) R4, R7 e R11.

## Vocabulário

| Termo | Valores |
|---|---|
| `Scope` | `global`, `user` |
| `Transport` | `http` (Streamable HTTP), `sse` (HTTP+SSE legado), `stdio` (só no arquivo do operador) |
| `AuthType` | `none`, `bearer` (só globais `http`/`sse`) |
| `Origin` | `file` (arquivo do operador, somente leitura), `registry` (armazenamento, criado pela API) |

## SecurityPolicy

| Campo | Tipo | Regra |
|---|---|---|
| `timeout_ms` | int | 1 000–120 000; padrão 30 000 — prazo de **uma operação inteira** (sessão + operação) |
| `max_response_bytes` | int | 1 024–1 048 576; padrão 65 536 — corte do conteúdo do resultado; o teto do transporte `http`/`sse` é este valor + 1 MiB |
| `allowed_tools` | tuple[str, ...] | obrigatória, não vazia, nomes exatos, sem repetição |
| `write_tools` | tuple[str, ...] | ⊆ `allowed_tools`; padrão vazio |

## McpServerDraft — o que a API envia

| Campo | Tipo | Global | Usuário |
|---|---|---|---|
| `alias` | str | `[a-z0-9][a-z0-9_-]{0,31}` | `~` + a mesma gramática |
| `transport` | `http` \| `sse` | sim | sim (`stdio` recusado nos dois — FR-013) |
| `endpoint` | str | URL `http`/`https` com host, sem usuário/senha nem fragmento | só `https` |
| `description` | str \| None | até 500 caracteres | idem |
| `auth_type` | AuthType | `none` ou `bearer` | só `none` |
| `credential_ref` | str \| None | exigida com `bearer`, proibida com `none`; `[a-z0-9][a-z0-9_]{0,63}` | proibida |
| `enabled` | bool | padrão `true` | idem |
| `user_access` | bool | padrão `false` | proibido |
| `policy` | SecurityPolicy | obrigatória | obrigatória |

## Entrada do arquivo do operador

A mesma estrutura, sempre global, mais os campos de `stdio` ([contracts/mcp-yaml.md](contracts/mcp-yaml.md)):
`command` (não vazio), `args` (lista de textos), `env` (nome → valor literal) e `secrets` (nome de variável → referência
de credencial). Entrada com erro vira servidor **indisponível** com o motivo, não erro de arquivo.

## McpServer — a visão publicada

| Campo | Observação |
|---|---|
| `alias`, `scope`, `owner` | `owner` é o `subject` do dono para `user`; `None` para global |
| `transport`, `endpoint` | para `stdio`, `endpoint` é `None` e `command` traz o comando (sem os valores de `secrets`) |
| `description`, `auth_type`, `credential_ref` | `credential_ref` é o **nome** da referência, nunca o valor |
| `enabled`, `user_access`, `policy` | — |
| `origin`, `read_only` | `read_only` é verdadeiro para `origin == "file"` |
| `available`, `reason` | indisponível: entrada de arquivo com erro ou registro sombreado pelo arquivo (R3) |
| `created_at`, `updated_at` | do relógio da porta; `None` para entradas do arquivo |

Invariante de segurança: nenhum campo de `McpServer`, `McpSummary`, `ServerHealth`, `Discovery` ou `ToolResult` contém o
valor de um segredo.

## McpSummary — o que um usuário pode referenciar

`alias`, `scope`, `description`. Devolvido por `available(principal)`: os `~` do Principal e os globais habilitados com
`user_access`. Endpoint, credencial e política de globais **não** aparecem para usuários — a topologia interna não vaza.

## Registro armazenado (interno, `ports.py`)

`StoredServer(owner: str | None, draft: McpServerDraft, created_at, updated_at)`. Unicidade por `(owner, alias)`. No
Postgres, tabela `mcp.servers` com a política em JSON e só a referência da credencial (ADR-015).

## Visibilidade

| Quem | Enxerga em `mine`/`get_mine` | Pode referenciar (`aliases`, `available`) |
|---|---|---|
| Assistant de sistema (`owner=None`) | — | globais habilitados e disponíveis |
| Usuário X | os `~` de X | os `~` habilitados de X + globais habilitados com `user_access` |
| Usuário Y sobre MCP de X | nada — `McpNotFound`, mesma mensagem de inexistente | — |

Sombreamento (R3): registro global do armazenamento com alias também declarado no arquivo fica `available=False`, com o
motivo, e fora de `aliases`.

## Descoberta e execução

| Tipo | Campos |
|---|---|
| `RemoteTool` (interno, `ports.py`) | `name`, `description`, `input_schema` — como o servidor anuncia |
| `RemoteResult` (interno, `ports.py`) | `parts` (texto ou marcador de parte não textual), `structured`, `is_error` |
| `Discovery` | `tools: tuple[ToolSpec, ...]` (nome local, `kind="mcp"`, `mutates` por `write_tools`, sem handler); `unavailable: Mapping[str, str]` (alias → motivo) |
| `ToolResult` (001) | `content` (textos concatenados; `structured` só quando não há texto), `untrusted=True`, `truncated`, `error` (resultado de erro, prazo, destino bloqueado, credencial ausente) |
| `ServerHealth` | `alias`, `ok`, `detail`, `tools` (o que o servidor anuncia), `missing` (da allowlist, não anunciadas) |

## Cache de descoberta

Chave: `(scope, owner, alias, versão)` — versão é `updated_at` do registro ou `"file"`. Valor: a lista bruta de
`RemoteTool` ou a falha. Validade: TTL configurável (padrão 300 s) para sucesso, 30 s para falha. Alterar ou desabilitar
um servidor muda a versão e invalida a entrada.

## Estados

```text
registro ── create ──▶ habilitado ── update(enabled=false) ──▶ desabilitado ── update(enabled=true) ──▶ habilitado
                           │                                         │
                           └────────────── delete ──────────────────┴──▶ (removido)
arquivo ── boot ──▶ disponível | indisponível (erro na entrada)        somente leitura; muda só com restart
registro global + mesmo alias no arquivo ──▶ sombreado (indisponível, com motivo)
```

## Falhas

| Situação | Resultado |
|---|---|
| Rascunho inválido | `McpRejected` nomeando o campo (400 na 008) |
| `stdio` pela API | `McpRejected(field="transport")` |
| Alias já usado pelo dono, ou global já declarado no arquivo | `McpConflict` |
| Alterar ou apagar entrada do arquivo | `McpConflict` ("declarado no arquivo do operador") |
| MCP de outro usuário ou inexistente | `McpNotFound`, mensagem fixa |
| Alias fora do grant na execução | `UnknownServer("servidor desconhecido: <alias>")` |
| Servidor fora do ar na descoberta | alias em `Discovery.unavailable`; demais servidores atendem |
| Destino bloqueado pela política de rede | descoberta: `unavailable`; chamada: `ToolResult(error=...)`; saúde: `ok=False` |
| Credencial não configurada | idem, nomeando a referência, nunca um valor |
| Erro no arquivo (YAML, chave desconhecida, raiz) | `McpConfigError` — o boot para (011) |
