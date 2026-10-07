# Decisões arquiteturais (ADR)

Um ADR aceito não é editado: é **substituído** por outro ADR, que o referencia. Specs e planos citam ADRs pelo número.
Divergir de um ADR aceito num `plan.md` exige um ADR novo (ver constituição, "Organização do SDD").

| ADR | Título | Status | Specs afetadas |
|---|---|---|---|
| [001](ADR-001-topologia-fixa.md) | Topologia fixa em vez de Graph Builder dinâmico | Aceita | 005, 001, 002 |
| [002](ADR-002-assistant-fronteira-isolamento.md) | Assistant como fronteira de isolamento | Aceita | 003, 004, 008 |
| [003](ADR-003-mcp-usuario-pack-operador.md) | MCP é extensão do usuário, Python pack é do operador | Aceita | 002, 007, 003 |
| [004](ADR-004-contratos-no-repo-do-core.md) | Contratos no repositório do core, packs de domínio separados | Aceita | 001, 010, 1xx |
| [005](ADR-005-execute-tool-unificado.md) | `execute_tool` unificado — retrieval é tool | Aceita | 004, 005, 001 |
| [006](ADR-006-rag-first-default-scouting.md) | `rag_first` determinístico como default do scouting | Aceita | 101, 005 |
| [007](ADR-007-citacao-mecanica.md) | Verificação mecânica de citação em vez de LLM judge online | Aceita | 104, 005, 009 |
| [008](ADR-008-modelo-por-papel.md) | Modelo por papel | Aceita | 006, 003 |
| [009](ADR-009-deploy-docker-build-arg.md) | Deploy por imagem Docker com build-arg | Aceita | 002 |
| [010](ADR-010-temporal-fora.md) | Temporal fora da arquitetura | Aceita | 005 |
| [011](ADR-011-contratos-independentes-do-motor.md) | Contratos independentes do motor de execução | Aceita | 001, 005, 002, 1xx |
| [012](ADR-012-estilo-arquitetural-hexagonal.md) | Estilo arquitetural: microkernel, monolito modular e hexagonal por módulo | Aceita | todas |
| [013](ADR-013-seams-transversais-trace-e-tempo.md) | Seams transversais: Trace Sink e tempo de referência | Aceita | 001, 004, 005, 006, 009, 101, 103, 105 |
| [014](ADR-014-politica-versoes-0x-contratos.md) | Política de versões 0.x de `ai-core-contracts` | Aceita | 001, 002, 101 |
| [015](ADR-015-persistencia-postgres-por-modulo.md) | Persistência em Postgres por módulo: psycopg 3, schema próprio, migrações no adapter | Aceita | 003, 004, 005, 007, 008, 011 |
| [016](ADR-016-grant-carrega-politica-de-modelos.md) | O Execution Grant carrega a política de modelos da 006: seta 003 → 006 | Aceita | 003, 005, 006 |
| [017](ADR-017-trace-sink-cresce-por-eventos-aditivos.md) | O Trace Sink cresce por eventos aditivos | Aceita | 009, 004, 005 |
| [018](ADR-018-seam-execution-engine-fase-3.md) | Seam Execution Engine na Fase 3: grant da 003 e gravidade dos registros | Aceita | 005, 008, 009, 011, 003 |
| [019](ADR-019-papeis-por-flow-no-seam-execution-engine.md) | O Execution Engine publica os papéis de modelo que cada flow exige | Aceita | 005, 003, 011 |
| [020](ADR-020-segredos-uma-fonte-por-perfil-uma-porta-por-modulo.md) | Segredos: uma fonte por perfil, uma porta por módulo; credencial ausente degrada, não derruba | Aceita | 011, 006, 007 |
| [021](ADR-021-workspace-ai-core-permanece-no-repositorio-da-plataforma.md) | O workspace `ai-core` permanece no repositório da plataforma (refina o 004) | Aceita | 001, 010, 1xx |

## Modelo para ADR novo

```markdown
# ADR-NNN — Título

- **Status:** Proposta | Aceita | Substituída por ADR-MMM · AAAA-MM-DD
- **Specs afetadas:** links
- **Origem:** o que motivou

## Contexto
## Decisão
## Alternativas rejeitadas
## Consequências
```
