# ADR-002 — Assistant como fronteira de isolamento

- **Status:** Aceita · 2026-09-10
- **Specs afetadas:** [003-core-assistants-access](../../specs/003-core-assistants-access/spec.md), [004-core-capability-gateway](../../specs/004-core-capability-gateway/spec.md), [008-core-http-api](../../specs/008-core-http-api/spec.md)
- **Origem:** arch-v1 Parte VIII

## Contexto

Era preciso usar o pack de scouting sem que a execução conhecesse os MCPs configurados no generic, com possibilidade de compor os dois quando explícito. Cogitou-se uma rota por plugin mais uma rota de composição.

## Decisão

Separar **Capability Pack** de **Assistant**. O Assistant é configuração server-side nomeada que amarra topologia, packs, MCPs, coleções, política de modelos e ACL. A requisição nomeia um Assistant e nunca amplia capacidades. Endpoint único; duas superfícies de auth (`/v1` OIDC, `/private/v1` API key). Cada Assistant é exposto como um "model" na compat OpenAI.

## Alternativas rejeitadas

*Rota por plugin.* Duplica middleware, auth, streaming e tratamento de erro; adicionar um pack passaria a exigir mudança no core, violando o princípio 18; e complica a integração com Open WebUI. A variável que de fato precisa de rota separada é a **superfície de autenticação** — que é pequena e estável — não o pack.

*Endpoint único com packs e MCPs na requisição.* Foi o desenho original. O cliente decide o que o agente enxerga, podendo ampliar o conjunto de capacidades. Sem fronteira server-side, não há isolamento — apenas convenção.

## Consequências

- Isolamento é estrutural: `scouting` declara `mcp: []` e não há caminho para um MCP entrar naquele catálogo
- Composição é um terceiro Assistant, explícito e auditável
- Autorização diferenciada por Assistant (público com OIDC, privado com API key) sai de graça
- 404 em vez de 403 evita vazar existência de assistant privado
- Custo: mais um conceito no vocabulário — mitigado pelo vocabulário normativo da constituição
