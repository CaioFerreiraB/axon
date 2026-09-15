# ADR-003 — MCP é extensão do usuário, Python pack é extensão do operador

- **Status:** Aceita · 2026-09-10
- **Specs afetadas:** [002-core-pack-runtime](../../specs/002-core-pack-runtime/spec.md), [007-core-mcp-integration](../../specs/007-core-mcp-integration/spec.md), [003-core-assistants-access](../../specs/003-core-assistants-access/spec.md)
- **Origem:** arch-v1 Parte VIII

## Contexto

Desejava-se adicionar packs sem hardcode no core, configurável a nível de usuário, possivelmente a partir de um repositório git.

## Decisão

Quatro níveis de extensão, com fronteira clara: Assistant e MCP server são dado, nível de usuário, ao vivo; pack declarativo é dado, nível admin; code pack é código Python via entry point, nível operador, exige rebuild.

| Nível | Mecanismo | Quem | Código? | Restart? | Onde vive |
|---|---|---|---|---|---|
| 1 | Assistant | usuário | não | não | banco |
| 2 | MCP server | usuário | não | não | banco |
| 3 | Pack declarativo | admin | não | não | banco/YAML |
| 4 | Code pack | operador | sim | sim | imagem |

## Alternativas rejeitadas

*Endpoint de admin que instala pack de git em runtime.* É execução remota de código por construção. Exigiria venv gravável, mecanismo de restart, e uma allowlist de origens cuja falha é comprometimento total. Além disso, produz estado divergente do manifesto de deployment — a instalação deixa de ser reproduzível.

## Consequências

- A pergunta "como adiciono capacidade?" tem resposta determinada pelo papel de quem pergunta
- Usuário final nunca executa código arbitrário no processo do core
- Quem precisa de código próprio escreve um MCP server e ganha fronteira de processo de brinde
- Custo: capacidade que exige lógica Python depende do operador — aceitável, e é a fronteira certa de confiança
- Corolário registrado na tradução para SDD (2026-09-10): MCP de escopo de usuário não pode usar transporte `stdio`, porque isso executaria um comando arbitrário no host do core — ver spec 007, FR-012.
