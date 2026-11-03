# ADR-055 — Autenticação MCP delegada por execução

- Status: aceito para implementação solicitada
- Data: 2026-10-29
- Complementa ADR-003, ADR-012, ADR-013 e ADR-015; substitui apenas a exigência de resolução exclusivamente no servidor para MCPs explicitamente delegados.

## Contexto

Um serviço pode compartilhar um Assistant entre identidades externas sem compartilhar a identidade do MCP. Credenciais estáticas continuam sendo o padrão. A delegação deve ser genérica, sem qualquer conhecimento do domínio do cliente.

## Decisão

`auth.type: delegated` é um modo explícito de MCP global HTTP HTTPS, sem `credential_ref` e sem `user_access`. O Assistant autoriza o alias pelo seu `mcp_aliases` existente; no protocolo 1, pode autorizar exatamente um alias delegado. O registry publica `delegation_for(grant)` e valida essa cardinalidade. ACL, ferramentas e política de rede continuam determinadas pelo servidor.

Somente `/private/v1/chat/completions` aceita `X-Axon-MCP-Authorization: Bearer <credencial>`. A autorização normal identifica o serviço. A entrada resolve o grant e vincula o segredo ao alias e endpoint do registry antes da execução. `/private/v1/models` publica `x_axon.mcp_delegation: {version: 1, alias, endpoint}`. Não se aceita destino informado pelo cliente.

O segredo viaja exclusivamente nos seams `ExecutionRequest` (005), `ToolContext` (004) e `McpClients.client_for` (007), em um objeto confidencial sem serialização de dataclass, sem repr de conteúdo, e com escopo imutável. Não entra em mensagens, argumentos, eventos, banco ou traces. O cliente restrito é exclusivo da execução. Descoberta delegada nunca usa cache compartilhado, nem positivo nem negativo. Revalidação de alias, modo e endpoint precede cada operação. Ausência, formato inválido ou configuração incompatível falha sem recorrer à credencial estática.

O transporte conserva admissão por IP e não segue redirecionamentos. MCPs existentes mantêm seus contratos e credenciais. A integração deve usar pedidos efêmeros (`x-axon-store:false`) e o operador deve desativar captura de conteúdo nos traces quando esse conteúdo for confidencial.

## Consequências e seams

007 adiciona modo delegado, objeto `DelegatedAuthorization`, descritor e método do registry; 004 e 005 transportam o objeto fora do estado conversacional; 008 valida a superfície e publica descoberta. Sem novos schemas de armazenamento: o modo usa o discriminante de autenticação já armazenado. Uma configuração com mais de um alias delegado é recusada na descoberta e na admissão, antes de executar ferramentas.

Aceite: duas execuções concorrentes com segredos distintos; descoberta e execução corretas sem cache; ausência/invalidade/alteração do destino falham; segredo ausente de repr/trace/erro; estáticos preservados.

As duas arestas públicas de tipos `graph.api → capabilities.api → mcp.api` recebem exceções pontuais nos contratos de dependências transitivas de 005/010. Importações diretas do motor ou harness ao MCP continuam proibidas; acesso a implementações privadas permanece proibido.
