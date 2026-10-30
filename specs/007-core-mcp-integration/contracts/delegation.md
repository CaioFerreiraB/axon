# Delegação MCP, protocolo 1

`auth.type = delegated`, `credential_ref = null`, escopo global, transporte http HTTPS, `user_access = false`. `none`/`bearer` preservados.

`McpRegistry.delegation_for(grant) -> McpDelegation | None`: aliases do grant explicitamente autorizados; zero retorna None, um retorna versão 1/alias/endpoint, vários levantam McpRejected. Nunca contém segredo.

`DelegatedAuthorization(alias, endpoint, authorization)` é imutável e confidencial, sem serialização implícita nem repr revelador. `McpClients.client_for(grant, *, delegation=None)` vincula esse objeto a uma única execução. Cada chamada revalida grant/visibilidade/alias/endpoint/modo. Não usa cache de descoberta. `ExecutionRequest.mcp_delegation` e `ToolContext.mcp_delegation` são canais internos opcionais; não entram no prompt nem nos eventos.

Somente Chat Completions privado aceita `X-Axon-MCP-Authorization`, com Bearer opaco não vazio até 4096 caracteres sem espaços/controles. Header ausente para Assistant delegado, header para Assistant estático ou na superfície pública: erro explicativo sem repetir valor. Credencial nunca escolhe destino nem ferramentas. GET models privado publica `x_axon.mcp_delegation` para Assistants compatíveis acessíveis. Destino alterado após admissão é recusado antes de enviar credencial.

Sem redirecionamentos. Duas execuções simultâneas usam clientes e conexões independentes. Falhas não revelam segredo nem fazem fallback estático. Testes D01–D05 acompanham os seams.
