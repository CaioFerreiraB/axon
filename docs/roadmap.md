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
| **4 — ai-scouting sem RAG** ✅ | Prova a arquitetura de packs com pack real em repositório próprio | 101 · US1, US2, US3 · 104 · esqueleto · 002 · US5 (build da instalação) — **exige a tag `contracts-v0.1.0`** |
| **5 — RAG** ✅ | Recuperação híbrida com vigência e citação verificada | 102 · US1–US5 · 103 · US1–US5 · 104 · US1–US4 · 005 · US3, US4 (`rag_first`) · 101 · US4, US5 |
| **6 — Avaliação** | **Antes de calibrar qualquer número do RAG** | 009 · US2, US3, US4 · 105 · US1–US5 |
| **7 — Open WebUI** ✅ | Assistants aparecem como modelos | 008 · US6, US8 |
| **8 — GraphRAG** | Retriever de grafo atrás do contrato existente | 106 (resolver a ontologia primeiro) |
| **9 — Console e identidade própria** | Login da própria plataforma (senha e Google) no lugar do Keycloak e administração gráfica do que o deploy permitir: modelos e MCPs por Assistant, uso e custo, Langfuse, ajustes de login | 012 · todas · 013 · todas · 003 · US9, US10 · 009 · US5–US7 · 006 · toque `model_exchange` · 008 · US9 · 011 · US6 · 002 · US7 · identidade Axon (incremento 9.5): US "Identidade Axon" em 001, 011, 010, 002, 003, 009, 008, 012, 013 e 101 |

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

**Fase 4 concluída em 2026-10-07.** A arquitetura de packs está provada com um pack real fora do core: o `ai-scouting`
(101) mora em repositório próprio, depende só de `ai-core-contracts` pela tag `contracts-v0.1.0` (o `ai-core` ficou no
`agentic-app` — ADR-021), responde sem inventar fonte enquanto não há corpus e deriva ramo, tema e vigência da
pergunta sem chamar modelo; os validators de citação e vigência (104) existem e esperam o RAG para serem publicados. A
instalação (002 US5) monta core e packs numa imagem a partir de tags, roda `packs check` no build — pack incompatível
falha o build — e entrega um runtime sem instalador (ADR-022), verificado a cada push no `agentic-deploy`.

**Fase 6 em andamento (2026-10-13).** O harness de avaliação (009, core `v0.3.0`, contratos `0.1.2`) roda um conjunto
dourado pelo motor com a data de cada item, lê o trace e compara com uma linha de base — só métricas determinísticas
barram. Da 105, a infraestrutura está pronta sobre um conjunto **semente provisório**: métricas de domínio no pack
(`ai-scouting` 0.3.0), validação do conjunto contra o corpus, linha de base e o job `eval` no CI do pack. As US3–US5 da
105 (calibração do RAG, escolha de embedding e de modelo local) esperam a curadoria das perguntas reais, que o
mantenedor fará depois do desenvolvimento; até lá, nenhum número do RAG muda.

**Fase 7 concluída em 2026-10-13.** Os Assistants aparecem como modelos no Open WebUI v0.12, sem código de interface:
o usuário entra por SSO no provedor OIDC e a conexão repassa o token dele à plataforma, que mostra só os Assistants que
a ACL resolve para ele. A API (008) limita as execuções simultâneas com fila curta — quem espera vê o aviso na hora, e
sobrecarga é 503 com `Retry-After` antes de qualquer chamada de modelo —, mostra o progresso como raciocínio
(`reasoning_content`) até o primeiro texto e aceita pedidos efêmeros (`x-ai-core-store: false`), para não duplicar o
histórico que a interface já guarda. A instalação (`agentic-deploy`, perfil `webui`) traz o Open WebUI e um Keycloak de
desenvolvimento, com a prova automatizada (`scripts/check-webui.py`); ela achou e corrigiu um defeito do verificador
OIDC da 003 com o JWKS do Keycloak (core `v0.4.1`). Os valores da fila seguem provisórios até a medição com um modelo
local, que o mantenedor deixou para depois. Depois dela (2026-10-13), o progresso no Open WebUI virou uma timeline de
status — chamadas e argumentos, trechos e documentos, decisões do portão e do controller, modelo, tokens e tempos de cada
etapa — pelo desfecho de etapa que o motor publica (ADR-028) e o cabeçalho `x-ai-core-progress: status` da conexão (008
FR-005a), no lugar do bloco "Pensou por N segundos".

**Fase 9 em especificação (2026-10-13).** ADRs 029–034 aceitos e constituição 1.3.0: a plataforma passa a ser o
provedor de identidade (012) — o Open WebUI e a console entram por ela, e a 003 continua verificando o JWT —, ganha
uma superfície de administração (`/admin/v1`, grupo de administração, token da plataforma ou chave), sobreposições de
Assistants de sistema sob a flag `overrides` do YAML, segredos de runtime cifrados com a chave mestra da instalação
(a variável de ambiente prevalece), e um trace com destinos — uso e custo por dia para o dashboard, Langfuse, e o texto
de prompt e resposta só quando ligado. A console (013) é uma SPA opcional na instalação. A Fase 8 (GraphRAG) não muda
de número: as fases não são estritamente sequenciais.

**Incremento 9.5, identidade Axon (2026-10-20).** ADR-037 e ADR-038 aceitos e constituição 1.3.1: a plataforma passa a
se chamar Axon, e os nomes técnicos seguem a marca (`axon-ai`, `axon-ai-contracts`, `axon-generic`, `axon-scouting`,
comando `axon`, `AXON_*`, `x-axon-*`, grupo `axon.packs`; repositórios `axon`, `axon-deploy`, `axon-scouting`), em corte
seco. A marca Axon aparece por padrão, e a da instalação ocupa o lugar principal quando existe. Cada spec afetada
ganha uma US "Identidade Axon" pelo spec-kit, nesta ordem: 001 → 011 → 010 → 002 → 003 → 009 → 008 → 012 → 013 →
tags `contracts-v0.2.0` e `v0.7.0-rc1` → 101 → 002 (instalação). O símbolo é desenhado no Penpot e escolhido pelo
mantenedor antes das passadas da 012 e da 013. As specs 004–007 e 102–106 mudam só nos nomes, dentro das passadas da
011 e da 101.
Andamento: **001 feita** (2026-10-20) — `axon-ai-contracts` 0.2.0, import `axon_ai_contracts`, consumidores do
workspace atualizados; ainda sem tag.
**011 feita** (2026-10-20) — distribuição `axon-ai` 0.7.0rc1, workspace `axon-ai/`, import `axon_ai` em todos os
módulos, comando `axon` (com `--version`), prefixo `AXON_` com a recusa de `AI_CORE_*`, nome padrão "Axon"; specs 004–007
só nos nomes; ainda sem tag.
**010 feita** (2026-10-20) — `axon-generic` 0.2.0, import `axon_generic`; consumidores do workspace (dependência de
desenvolvimento, import-linter, suíte do core, CI) e documentos vivos atualizados; o grupo `ai_core.packs` fica para a
002; ainda sem tag.
**002 feita** (2026-10-20) — o Pack Runtime descobre packs só pelo grupo `axon.packs` (pack só no grupo antigo,
habilitado, fica `error: não instalado`); `axon-generic`, o pack de teste dos contratos e as distribuições falsas no grupo
novo; a instalação (US7) fica para depois da 101.
**003 feita** (2026-10-20) — audiências `axon` (chat) e `axon-admin` (console), chaves de API `axn_<key_id>_<segredo>`,
credenciais antigas não autenticam; `TEST_API_KEY` com o prefixo novo; clientes de exemplo da identidade, e2e da console
e documentos vivos de 008, 011, 012 e 013 atualizados.
**009 feita** (2026-10-20) — os traces chegam ao Langfuse como o serviço `axon`; o segredo do Langfuse da console é
selado com o rótulo `axon-ai/observability/v1`, e o selado com o antigo não abre (a saúde mostra; regrava-se pela console).
**008 feita** (2026-10-20) — cabeçalhos `x-axon-store`/`x-axon-progress` (os antigos recebem 400 que cita o novo, por decisão
do mantenedor), extensão `x_axon`, OpenAPI "Axon" e `me.instance.custom` (ADR-038).
**012 feita** (2026-10-20) — páginas com o lockup Axon ou a marca da instalação e "com Axon", favicon do símbolo, tokens
da marca com AA (menos o hover escuro, pendente na 013); cookie `axon_session`, realm `axon`, rótulos `axon-ai/identity/…`.

Itens de prioridade P3 não listados (ex.: 001 US5 rotina isolada, 002 US6 pack declarativo, 004 US6 catálogo mínimo, 005 US6) entram quando houver caso de uso.

**Pendências entre specs resolvidas em 2026-10-07.** OpenAI como controller (ADR-023: o adapter converte o esquema
para o subconjunto estrito e troca os nomes de função) e a resposta reescrita pelos validators com streaming (ADR-024:
validators filtram a geração — contratos `0.1.1`).

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
| Uso por chamada de modelo e preços | `UsageStore`, `PriceStore` | memória → Postgres | 9 | 009 |
| Ajustes do Langfuse (segredo cifrado) | `DestinationSettingsStore` | memória → Postgres | 9 | 009 |
| Sobreposições de Assistants de sistema | `SystemOverrideStore` | memória → Postgres | 9 | 003 |
| Contas, grupos, sessões, chaves de assinatura, ajustes de login | `AccountStore`, `GrantStore`, `SigningKeyStore`, `IdentitySettingsStore` | memória → Postgres | 9 | 012 |
| Tentativas de login | `LoginAttempts` | memória (processo único) | 9 | 012 |
| Chunks e vetores | `ChunkIndex` (seam do índice) | Qdrant | 5 | 102 |
