# Roadmap — fases → specs

Tradução de arch-v1 §31. As **specs** são organizadas por módulo (para poderem ser reescritas isoladamente);
as **fases** cortam essas specs por user story. Numa fase, rode o fluxo spec-kit em cada spec listada,
limitando `/speckit-tasks` e `/speckit-implement` às user stories da fase (ex.: `/speckit-tasks apenas US1 e US3`).

| Fase | Objetivo | Specs · user stories |
|---|---|---|
| **0 — Contratos** | Workspace `ai-core` e `ai-core-contracts` 0.1 **antes de qualquer implementação** | 001 · US1–US4 (US5 pode esperar) |
| **1 — Core mínimo** ✅ | Conversa ponta a ponta, pack carregado por entry point, resposta em stream | 011 · US1, US2 (perfil em memória), US3 · 002 · US1, US2, US3 (execução de hooks: cenários 2–4) · 005 · US1 (`chat`) · 006 · US1 · 008 · US1 · 010 · US1 · 009 · US1 (trace mínimo, Trace Sink) |
| **2 — Assistants e autorização** ✅ | A fronteira de isolamento existe; tudo depois depende dela | 003 · US1–US7 · 002 · US4 · 008 · US2, US3, US4, US5, US7 · 011 · US2 (perfil persistente), US4, US5 |
| **3 — ai-generic e MCP** ✅ | Loop agêntico seguro com MCP | 005 · US2 (`agentic`) · 004 · US1–US5 · 007 · US1–US6 · 006 · US2–US5 · 010 · US2 + decisão FR-005 · 002 · US3 (catálogo com namespace: cenário 1) |
| **4 — ai-scouting sem RAG** | Prova a arquitetura de packs com pack real em repositório próprio | 101 · US1, US2, US3 · 104 · esqueleto · 002 · US5 (build da instalação) — **exige a tag `contracts-v0.1.0`** |
| **5 — RAG** | Recuperação híbrida com vigência e citação verificada | 102 · US1–US5 · 103 · US1–US5 · 104 · US1–US4 · 005 · US3, US4 (`rag_first`) · 101 · US4, US5 |
| **6 — Avaliação** | **Antes de calibrar qualquer número do RAG** | 009 · US2, US3, US4 · 105 · US1–US5 |
| **7 — Open WebUI** | Assistants aparecem como modelos | 008 · US6, US8 |
| **8 — GraphRAG** | Retriever de grafo atrás do contrato existente | 106 (resolver a ontologia primeiro) |

**Fase 1 concluída em 2026-09-21.** `ai-core serve` sobe a plataforma a partir de `packs.yaml` e `assistants.yaml`, e
uma requisição no formato OpenAI atravessa API (008), motor (005), Pack Hooks (002) com o `ai-generic` (010) e Model
Router (006), deixando rastro no trace (009) — em streaming, do primeiro token ao `[DONE]`.

**Fase 2 concluída em 2026-10-01.** Nenhuma requisição chega à execução sem Principal verificado: OIDC na superfície
pública e chave de API na privada (003), nos três perfis. No perfil `persistent`, chaves, Assistants de usuário e
conversas vivem no Postgres (schemas `assistants` e `http`, migrados no boot) e sobrevivem a um restart; a raiz
`ai-core` reúne `serve`, `packs`, `assistants validate`, `keys` e `health`; e a saúde agregada só responde 503 quando
algo crítico — o banco — cai.

**Fase 3 concluída em 2026-10-07.** Um Assistant `agentic` decide com o papel `controller` (saída sempre restrita por
esquema) e chama tools de pack e de MCP pelo gateway (004): catálogo com namespace e allowlist, argumentos validados,
resultado cercado como dado e tool de escrita auditada antes de executar. Os servidores MCP vêm do registry (007) —
globais pelo `mcp.yaml` ou pela API, de usuário com `~` —, com política por servidor, credencial só por referência e
proteções de rede. Os modelos podem ser locais ou remotos (OpenAI, OpenRouter) por papel, sem roteamento automático
(006); a API expõe MCP e decide o desfecho pela gravidade (008); e o `ai-generic` continua pack de referência, base do
Assistant genérico com MCP (010).

Itens de prioridade P3 não listados (ex.: 001 US5 rotina isolada, 002 US6 pack declarativo, 004 US6 catálogo mínimo, 005 US6) entram quando houver caso de uso.

**Pendências entre specs.** 005: esquema de ação de raiz objeto, para OpenAI como controller no modo estrito (006 R19)
— até lá, um Assistant `agentic` com `controller` em `openai/…` falha explicitamente na chamada do controller (o `anyOf`
na raiz é recusado pela OpenAI); Ollama e OpenRouter funcionam. 005/008: com streaming, os pedaços já saíram quando os
validators rodam e o último pedaço leva `delta` vazio — a resposta reescrita (citação `[n]`, citação inventada removida,
avisos de vigência e de "não fundamentada") não chega ao cliente, só `citations`, `flags` e `errors` em `x_ai_core`
(104 R11); decidir antes de publicar os validators da 104 na Fase 5.

## Antes de começar

1. ~~Aceitar ou rejeitar o ADR-011~~ — [ADR-011](adr/ADR-011-contratos-independentes-do-motor.md), [ADR-012](adr/ADR-012-estilo-arquitetural-hexagonal.md) e [ADR-013](adr/ADR-013-seams-transversais-trace-e-tempo.md) aceitos em 2026-09-14. Os contratos da Fase 0 já incluem a Turn View com `reference_time`.
2. ~~Criar os repositórios `ai-core` e `ai-scouting` (ou decidir mantê-los como subpastas deste repositório durante o desenvolvimento — ver CLAUDE.md)~~ — decidido em 2026-09-15 (plano da 001): `ai-core/` é subpasta deste repositório nas Fases 0–3 (git inicializado na raiz). Revisto em 2026-10-07 ([ADR-021](adr/ADR-021-workspace-ai-core-permanece-no-repositorio-da-plataforma.md)): o `ai-core` **não** se separa; a tag `contracts-v0.1.0` nasce aqui, e o `ai-scouting` vive em repositório próprio, ligado como submódulo. Python 3.14 no workspace; piso 3.12 em `ai-core-contracts`.
3. ~~Resolver o ponto em aberto da 008 (FR-012)~~ — resolvido em 2026-09-14 (`/speckit-clarify`): a data de referência só é fixada em processo, pelo harness; a API rejeita o campo.

## Persistência por fase (arch-v1 §28)

Cada linha é uma troca de adapter atrás de uma porta (ADR-012); quem escolhe o adapter é o perfil da composition root
(spec 011). Até a fase indicada, a porta usa o adapter em memória.

| Dado | Porta | Adapter | Fase | Spec |
|---|---|---|---|---|
| Checkpoint de execução | `CheckpointStore` | quando houver retomada (FR-014; adiada em 2026-10-01) | — | 005 |
| Histórico de conversa | `ConversationStore` | memória → Postgres | 1 → 2 | 008 |
| Assistants de usuário | `AssistantStore` | memória → Postgres | 1 → 2 | 003 |
| Contadores de rate limit | `RateCounterStore` | memória (processo único) | 2 | 003 |
| MCP registry | `McpServerStore` | memória → Postgres | 3 | 007 |
| Auditoria de tool mutante | `AuditLog` | memória → Postgres | 3 | 004 |
| Trace | `TraceExporter` | arquivo → a decidir | 1 | 009 |
| Chunks e vetores | `ChunkIndex` (seam do índice) | Qdrant | 5 | 102 |
