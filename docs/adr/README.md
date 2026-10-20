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
| [022](ADR-022-instalacao-constroi-o-core-num-estagio-proprio.md) | A instalação constrói o core num estágio do próprio Dockerfile | Aceita | 002 |
| [023](ADR-023-adapter-da-openai-converte-para-o-subconjunto-estrito.md) | O adapter da OpenAI converte o esquema para o subconjunto estrito, e desfaz a conversão na resposta | Aceita | 006, 005 |
| [024](ADR-024-validators-filtram-o-streaming.md) | Validators que reescrevem a resposta filtram o streaming | Aceita | 001, 002, 005, 104 |
| [025](ADR-025-indice-do-scouting-devolve-a-similaridade-densa.md) | O índice do scouting devolve a similaridade densa de cada resultado | Aceita | 102, 103 |
| [026](ADR-026-o-modelo-ve-o-identificador-de-cada-trecho.md) | O modelo vê o identificador de cada trecho | Aceita | 004, 005, 101, 104 |
| [027](ADR-027-metricas-de-dominio-pelo-contrato-de-pack.md) | Métricas de domínio pelo contrato de pack | Aceita | 001, 002, 009, 105 |
| [028](ADR-028-o-motor-publica-o-desfecho-de-cada-etapa.md) | O motor publica o desfecho de cada etapa | Aceita | 005, 008, 009 |
| [029](ADR-029-console-de-administracao-propria.md) | Console de administração própria | Aceita | 013, 008, 002 |
| [030](ADR-030-a-plataforma-e-o-provedor-de-identidade.md) | A plataforma é o provedor de identidade | Aceita | 012, 003, 011, 002 |
| [031](ADR-031-superficie-de-administracao.md) | Superfície de administração: admin é o grupo, com token da plataforma ou chave | Aceita | 003, 008, 012, 013 |
| [032](ADR-032-assistants-de-sistema-sobrepostos-em-runtime.md) | Assistants de sistema podem ser sobrepostos em runtime, se o YAML permitir | Aceita | 003, 008, 011, 013 |
| [033](ADR-033-segredos-de-runtime-cifrados-com-a-chave-mestra.md) | Segredos configurados em runtime ficam cifrados com a chave mestra da instalação (refina o 020) | Aceita | 011, 009, 012 |
| [034](ADR-034-trace-com-destinos-e-conteudo-opcional.md) | O trace se ramifica em destinos; conteúdo só por evento dedicado e opcional (refina o 017) | Aceita | 009, 006, 011 |
| [035](ADR-035-custo-informado-pelo-provider-e-providers-prontos.md) | O custo informado pelo provider entra na chamada; a administração lista os providers prontos (refina o 034) | Aceita | 001, 006, 009, 008, 013 |
| [036](ADR-036-provider-que-informa-custo-sem-preco-de-tabela.md) | Provider que informa o custo não tem preço de tabela; o relatório diz as requisições do dia (refina o 035) | Aceita | 006, 009, 008, 013 |

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
