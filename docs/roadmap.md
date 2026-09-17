# Roadmap — fases → specs

Tradução de arch-v1 §31. As **specs** são organizadas por módulo (para poderem ser reescritas isoladamente);
as **fases** cortam essas specs por user story. Numa fase, rode o fluxo spec-kit em cada spec listada,
limitando `/speckit-tasks` e `/speckit-implement` às user stories da fase (ex.: `/speckit-tasks apenas US1 e US3`).

| Fase | Objetivo | Specs · user stories |
|---|---|---|
| **0 — Contratos** | Workspace `ai-core` e `ai-core-contracts` 0.1 **antes de qualquer implementação** | 001 · US1–US4 (US5 pode esperar) |
| **1 — Core mínimo** | Conversa ponta a ponta, pack carregado por entry point, resposta em stream | 011 · US1, US2 (perfil em memória), US3 · 002 · US1, US2, US3 (execução de hooks: cenários 2–4) · 005 · US1 (`chat`) · 006 · US1 · 008 · US1 · 010 · US1 · 009 · US1 (trace mínimo, Trace Sink) |
| **2 — Assistants e autorização** | A fronteira de isolamento existe; tudo depois depende dela | 003 · US1–US7 · 002 · US4 · 008 · US2, US3, US4, US5, US7 · 011 · US2 (perfil persistente), US4, US5 |
| **3 — ai-generic e MCP** | Loop agêntico seguro com MCP | 005 · US2 (`agentic`) · 004 · US1–US5 · 007 · US1–US6 · 006 · US2–US5 · 010 · US2 + decisão FR-005 · 002 · US3 (catálogo com namespace: cenário 1) |
| **4 — ai-scouting sem RAG** | Prova a arquitetura de packs com pack real em repositório próprio | 101 · US1, US2, US3 · 104 · esqueleto · 002 · US5 (build da instalação) — **exige a tag `contracts-v0.1.0`** |
| **5 — RAG** | Recuperação híbrida com vigência e citação verificada | 102 · US1–US5 · 103 · US1–US5 · 104 · US1–US4 · 005 · US3, US4 (`rag_first`) · 101 · US4, US5 |
| **6 — Avaliação** | **Antes de calibrar qualquer número do RAG** | 009 · US2, US3, US4 · 105 · US1–US5 |
| **7 — Open WebUI** | Assistants aparecem como modelos | 008 · US6, US8 |
| **8 — GraphRAG** | Retriever de grafo atrás do contrato existente | 106 (resolver a ontologia primeiro) |

Itens de prioridade P3 não listados (ex.: 001 US5 rotina isolada, 002 US6 pack declarativo, 004 US6 catálogo mínimo, 005 US6) entram quando houver caso de uso.

## Antes de começar

1. ~~Aceitar ou rejeitar o ADR-011~~ — [ADR-011](adr/ADR-011-contratos-independentes-do-motor.md), [ADR-012](adr/ADR-012-estilo-arquitetural-hexagonal.md) e [ADR-013](adr/ADR-013-seams-transversais-trace-e-tempo.md) aceitos em 2026-09-14. Os contratos da Fase 0 já incluem a Turn View com `reference_time`.
2. ~~Criar os repositórios `ai-core` e `ai-scouting` (ou decidir mantê-los como subpastas deste repositório durante o desenvolvimento — ver CLAUDE.md)~~ — decidido em 2026-09-15 (plano da 001): `ai-core/` é subpasta deste repositório nas Fases 0–3 (git inicializado na raiz); a separação em repositório próprio acontece antes da Fase 4, quando nasce a tag `contracts-v0.1.0`. Python 3.14 no workspace; piso 3.12 em `ai-core-contracts`.
3. ~~Resolver o ponto em aberto da 008 (FR-012)~~ — resolvido em 2026-09-14 (`/speckit-clarify`): a data de referência só é fixada em processo, pelo harness; a API rejeita o campo.

## Persistência por fase (arch-v1 §28)

Cada linha é uma troca de adapter atrás de uma porta (ADR-012); quem escolhe o adapter é o perfil da composition root
(spec 011). Até a fase indicada, a porta usa o adapter em memória.

| Dado | Porta | Adapter | Fase | Spec |
|---|---|---|---|---|
| Checkpoint de execução | `CheckpointStore` | memória → Postgres | 1 → 3 | 005 |
| Histórico de conversa | `ConversationStore` | memória → Postgres | 1 → 2 | 008 |
| Assistants de usuário | `AssistantStore` | memória → Postgres | 1 → 2 | 003 |
| Contadores de rate limit | `RateCounterStore` | memória (processo único) | 2 | 003 |
| MCP registry | `McpServerStore` | memória → Postgres | 3 | 007 |
| Auditoria de tool mutante | `AuditLog` | memória → Postgres | 3 | 004 |
| Trace | `TraceExporter` | arquivo → a decidir | 1 | 009 |
| Chunks e vetores | `ChunkIndex` (seam do índice) | Qdrant | 5 | 102 |
