# Contrato — arquivo do operador `mcp.yaml` (clarificações 1 e 2; research R3, R10)

Montado na imagem e lido uma vez no boot; o caminho vem de `AI_CORE_MCP_FILE` (escolhido pela 011). É a **única**
origem de servidores `stdio` e da allowlist de hosts internos. Mudar o arquivo exige restart.

```yaml
servers:
  financeiro:                                   # alias global (sem ~)
    transport: http                             # http | sse | stdio
    endpoint: http://mcp-financeiro:8080/mcp
    description: Saldos e extratos
    auth: { type: bearer, credential: financeiro_token }   # → AI_CORE_MCP_SECRET_FINANCEIRO_TOKEN
    user_access: false                          # liberado para Assistants de usuário? padrão false
    enabled: true
    policy:
      timeout_ms: 10000
      max_response_bytes: 65536
      allowed_tools: [saldo, extrato]           # obrigatória
      write_tools: []

  arquivos:
    transport: stdio
    command: /usr/local/bin/mcp-arquivos        # executado sem shell
    args: ["--raiz", "/dados"]
    env: { LOG_LEVEL: info }                    # valores literais — não são segredo
    secrets: { TOKEN: arquivos_token }          # variável do filho → AI_CORE_MCP_SECRET_ARQUIVOS_TOKEN
    policy:
      allowed_tools: [ler, listar]

network:
  internal_hosts:                               # alcançáveis só por MCPs globais, mesmo em faixa privada
    - mcp-financeiro
    - 10.0.5.20
  allowed_hosts:                                # opcional: allowlist de hosts de destino (princípio VI)
    - "*.empresa.example"                       # os subdomínios, não o próprio domínio
    - mcp.parceiro.example
```

## Topo do arquivo

| Chave | Obrigatória | Regra |
|---|---|---|
| `servers` | não | mapeamento alias → servidor; ausente = nenhum global no arquivo |
| `network.internal_hosts` | não | lista de nomes de host (comparação exata, sem diferença de maiúsculas) e IPs literais; ausente = nenhuma exceção. A comparação é com o **host do endpoint**, não com o IP resolvido: listar `10.0.5.20` libera endpoints escritos com esse IP, não um nome que resolva para ele |
| `network.allowed_hosts` | não | allowlist de hosts de destino: nomes exatos, `*.domínio` (só subdomínios) e IPs literais. Definida, todo destino fora de `internal_hosts` — de MCP global ou de usuário — precisa casar com ela; ausente, vale qualquer host público. Lista vazia é erro de arquivo (bloquearia tudo sem dizer) |

## Servidor

As regras de [research.md](../research.md) R11, com escopo sempre global, mais:

| Campo | Regra |
|---|---|
| `transport: stdio` | exige `command`; proíbe `endpoint` e `auth` |
| `transport: http`/`sse` | exige `endpoint`; proíbe `command`, `args`, `env` e `secrets` |
| `auth` | `{type: none}` (padrão) ou `{type: bearer, credential: <ref>}` |
| `env` | nome de variável → texto |
| `secrets` | nome de variável → referência de credencial (R7) |

## Erros

**Erro de arquivo → o boot para** (`McpConfigError`, nomeando o caminho do campo): YAML inválido; raiz que não é
mapeamento; chave de topo desconhecida; `servers` ou `network` que não é mapeamento; `internal_hosts` ou
`allowed_hosts` que não é lista de textos; `allowed_hosts` vazia; padrão de `allowed_hosts` fora de nome, `*.domínio` ou
IP literal.

**Erro de um servidor → só ele fica indisponível**, com o motivo na listagem, na saúde e na validação de Assistants da
003: alias fora da gramática, transporte desconhecido, campo proibido para o transporte, política inválida, chave
desconhecida no servidor. Os demais servidores atendem (princípio VII).

Conformidade: `contract/test_mcp_config_source.py` e `unit/test_servers.py`.
