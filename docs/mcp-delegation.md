# MCP com autorização delegada por execução

Protocolo 1 ([ADR-055](adr/ADR-055-autenticacao-mcp-delegada.md)). Destinado a serviços que precisam
usar o mesmo Assistant com identidades externas diferentes. O Axon não interpreta essas identidades:
o servidor MCP autentica a credencial que recebe e aplica seu próprio isolamento.

O operador registra um MCP global com transporte `http`, endpoint HTTPS, `auth: {type: delegated}`,
sem `credential`, `user_access: false` e política explícita de ferramentas. Pelo CRUD privado, os
campos são os do [contrato MCP](../specs/008-core-http-api/contracts/mcp-routes.md). O Assistant
privado autoriza esse alias e concede acesso ao serviço que usa a integração. Instalações distintas
devem usar serviços, Assistants e registros MCP distintos.

O protocolo aceita um único alias delegado por Assistant. Zero aliases não anuncia delegação;
mais de um é erro de configuração na descoberta e admissão. O modo delegado é mutuamente exclusivo
com credencial estática. A verificação de saúde sem credencial de execução não acessa o MCP.

`GET /private/v1/models`, autenticado pela chave do serviço, anuncia:

```json
{"id":"assistant","x_axon":{"mcp_delegation":{"version":1,"alias":"dados","endpoint":"https://dados.exemplo/mcp"}}}
```

O cliente verifica versão e destino antes de mandar a autorização. Não selecione o primeiro
Assistant quando a descoberta for ambígua. Para cada Chat Completion privado:

```text
Authorization: Bearer <chave do serviço Axon>
X-Axon-MCP-Authorization: Bearer <credencial temporária do MCP>
x-axon-store: false
```

Sem `conversation_id`. A credencial MCP não vai no JSON, nas mensagens ou nos argumentos de tools.
A superfície pública e o chat nativo recusam esse header. O segredo é vinculado ao alias e endpoint
autorizados no momento da admissão; alteração do destino ou do modo invalida o uso. Não há cache de
descoberta compartilhado nem fallback estático. Cada operação abre sua própria conexão, conserva a
política de rede por IP e não segue redirecionamentos.

Pedidos efêmeros não gravam conversas, mas não desligam observabilidade. Desative captura de conteúdo
na console/instalação para dados confidenciais (`AXON_LANGFUSE_CAPTURE_CONTENT=false` quando a
configuração vem do ambiente; confira também os destinos configurados na console). Não habilite
logs de depuração HTTP com credenciais reais. Limites do Assistant continuam autoritativos; não
presuma que parâmetros de geração do cliente os substituem.

Testes: `tests/mcp/contract/test_delegation.py`, `tests/http/contract/test_mcp_delegation.py` e
`tests/graph/contract/test_graph_mcp_delegation.py`, em `axon-ai/packages/core`. Cobrem concorrência,
falha fechada, persistência do modo em Postgres, superfície HTTP, propagação até o gateway e
segredo ausente das mensagens/eventos. A homologação de uma integração externa deve usar um MCP
HTTPS de teste e pelo menos duas identidades.
