# ADR-037 — A plataforma se chama Axon, e os nomes técnicos seguem a marca

- **Status:** Aceita · 2026-10-20
- **Specs afetadas:** todas. Com US nova pelo spec-kit:
  [001-core-contracts](../../specs/001-core-contracts/spec.md) (distribuição e import dos contratos, 0.2.0),
  [011-core-bootstrap](../../specs/011-core-bootstrap/spec.md) (distribuição `axon-ai`, comando `axon`, prefixo `AXON_`,
  recusa dos nomes antigos, nome padrão), [010-core-generic-pack](../../specs/010-core-generic-pack/spec.md)
  (`axon-generic` 0.2.0), [002-core-pack-runtime](../../specs/002-core-pack-runtime/spec.md) (grupo `axon.packs`;
  instalação `axon-deploy`), [003-core-assistants-access](../../specs/003-core-assistants-access/spec.md) (audiências,
  prefixo da chave de API), [009-core-observability-evaluation](../../specs/009-core-observability-evaluation/spec.md)
  (`service.name`, rótulo HKDF), [008-core-http-api](../../specs/008-core-http-api/spec.md) (cabeçalhos `x-axon-*`),
  [012-core-identity](../../specs/012-core-identity/spec.md) (cookie, realm, rótulos HKDF e CSRF),
  [013-core-admin-console](../../specs/013-core-admin-console/spec.md) (pacote npm) e
  [101-scouting-pack](../../specs/101-scouting-pack/spec.md) (`axon-scouting` 0.4.0). Só nomes, sem FR novo: 004, 005,
  006, 007, 102–106. Substitui o [ADR-021](ADR-021-workspace-ai-core-permanece-no-repositorio-da-plataforma.md) e o
  [ADR-022](ADR-022-instalacao-constroi-o-core-num-estagio-proprio.md) **só quanto aos nomes**: as decisões deles
  continuam valendo com os nomes novos
- **Origem:** decisão do mantenedor (2026-10-20): "agentic-app" não tem identidade; o nome novo é Axon, com as
  diretrizes em `brand-kit/` ("Design. Connect. Build."). A marca visível está no
  [ADR-038](ADR-038-marca-da-plataforma-e-marca-da-instalacao.md)

## Contexto

O repositório nasceu como `agentic-app`, a constituição como "Plataforma Agentic AI", e o nome exibido nas páginas de
login e na console é o provisório "Agentic" (012 FR-023, 013). Os nomes técnicos vieram do mesmo rascunho: `ai-core`,
`ai-core-contracts`, `ai-generic`, `ai-scouting`, o comando `ai-core`, as variáveis `AI_CORE_*`, os cabeçalhos
`x-ai-core-*` e o grupo de entry point `ai_core.packs`.

O brand kit (§10.8) pede para não renomear identificadores técnicos sem medir o impacto. O impacto foi medido:
`ai_core` aparece em cerca de 3.000 linhas e `AI_CORE_*` em cerca de 700. Os contratos e o grupo de entry point são a
superfície que o pack externo consome por tag. Alguns nomes estão em dado persistido ou em credencial emitida: os
rótulos HKDF que selam as chaves de assinatura (012) e o segredo do Langfuse (009), o prefixo `aic_` das chaves de API
(003), as audiências `ai-core`/`ai-core-admin` dos tokens, o cookie `aic_session` e os volumes do compose, cujo nome
deriva da pasta `agentic-deploy`.

Não há instalação com dado a preservar: tudo ainda é desenvolvimento. No PyPI, `axon` está ocupado, e `axon-ai`,
`axon-ai-contracts`, `axon-generic` e `axon-scouting` estão livres (consultado em 2026-10-20). A plataforma não publica
lá, mas um nome de distribuição igual ao de um pacote público abre espaço para confusão de dependência.

## Decisão

1. **O produto se chama Axon.** Em texto corrido, `Axon`. No wordmark e onde o sistema tipográfico pedir, `axon`.
   A constituição passa a "Axon Constitution".
2. **Os nomes técnicos seguem uma regra.** No código, `ai-core` vira `axon-ai` e o prefixo `ai-` vira `axon-`. Na
   operação, o que se digita fica curto: `axon`.

   | Hoje | Novo |
   |---|---|
   | distribuição `ai-core` · import `ai_core` · pasta `ai-core/` | `axon-ai` · `axon_ai` · `axon-ai/` |
   | `ai-core-contracts` · `ai_core_contracts` | `axon-ai-contracts` · `axon_ai_contracts` |
   | `ai-generic` · `ai_generic` | `axon-generic` · `axon_generic` |
   | `ai-scouting` · `ai_scouting` · `ai-scouting-corpus` | `axon-scouting` · `axon_scouting` · `axon-scouting-corpus` |
   | comando `ai-core` | `axon` |
   | `AI_CORE_*` · `AI_SCOUTING_*` | `AXON_*` · `AXON_SCOUTING_*` |
   | `x-ai-core-store` · `x-ai-core-progress` | `x-axon-store` · `x-axon-progress` |
   | grupo de entry point `ai_core.packs` | `axon.packs` |
   | audiências `ai-core` · `ai-core-admin` | `axon` · `axon-admin` |
   | chave de API `aic_<id>_<segredo>` · cookie `aic_session` | `axn_<id>_<segredo>` · `axon_session` (com `__Host-` quando seguro) |
   | rótulos HKDF `ai-core/identity/v1`, `ai-core/observability/v1` · contexto CSRF `ai-core/identity/csrf:` | `axon-ai/identity/v1`, `axon-ai/observability/v1` · `axon-ai/identity/csrf:` |
   | `service.name` do OTel, `title` do OpenAPI, realm Basic, nome do pool | `axon` |
   | compose: serviço `ai-core`, imagens `agentic-deploy*`, `/etc/ai-core`, `/run/secrets/ai-core`, Postgres `ai_core` | `axon`, `axon:local`/`axon-console:local`, `/etc/axon`, `/run/secrets/axon`, `axon`; `name: axon` fixo no compose |
   | npm `@agentic/console` | `@axon/console` |
   | repositórios `agentic-app`, `agentic-deploy`, `ai-scouting` | `axon`, `axon-deploy`, `axon-scouting` (submódulos em `axon-deploy/` e `axon-scouting/`) |
   | nome exibido padrão "Agentic" | "Axon" |

3. **Corte seco.** Nenhum nome antigo continua aceito: nem o prefixo `aic_`, nem a audiência antiga, nem o rótulo HKDF
   antigo. Ambientes locais são recriados (contas, chaves, volumes, corpus reingerido). A única concessão é de
   diagnóstico: **o boot recusa** qualquer variável `AI_CORE_*` no ambiente, e o pack recusa `AI_SCOUTING_*`, com uma
   mensagem que cita a variável nova. Um `.env` antigo falha fechado, sem ser ignorado em silêncio.
4. **Versões.** Os contratos vão a `0.2.0`, porque renomear o import é quebra e o
   [ADR-014](ADR-014-politica-versoes-0x-contratos.md) sobe a minor em 0.x. O `axon-generic` vai a `0.2.0` (faixa
   `>=0.2,<0.3`), o core a `0.7.0rc1` (a linha 0.6.0 termina no rc6 com o nome antigo) e o `axon-scouting` a `0.4.0`.
   As tags são `contracts-v0.2.0` e `v0.7.0-rc1`, criadas com o aval do mantenedor. Core, pack e instalação mudam
   juntos, porque o pack resolve contratos e core pela mesma tag.
5. **O que não muda.** O flow `agentic` (é termo técnico do motor, como `chat` e `rag_first`). Os nomes de pack
   (`generic`, `scouting`) e a coleção `scouting`. Os schemas Postgres por módulo
   ([ADR-015](ADR-015-persistencia-postgres-por-modulo.md)). Os números e as pastas das specs (`0xx-core-*`). Os
   clientes OIDC (`console`, `open-webui`) e a chave `console.theme` do `localStorage`.
6. **O histórico não se reescreve.** Os ADRs aceitos 001–036, `docs/archive/`, os `research.md`, `plan.md` e
   `tasks.md` já executados, `.impeccable/mocks/` e as tags antigas ficam como estão; a tabela do item 2 é a chave de
   leitura. As passadas novas **acrescentam** research e tarefas. `spec.md`, `design.md`, `contracts/`, `data-model.md`
   e `quickstart.md`, que são documentos vivos, passam aos nomes novos.
7. **Ordem das passadas** (spec-kit, uma US "Identidade Axon" por spec): 001 → 011 → 010 → 002 → 003 → 009 → 008 → 012
   → 013 → tags → 101 → 002 (instalação). A passada que renomeia uma distribuição atualiza, de forma mecânica, os imports
   de quem a consome, para a CI ficar verde. Os repositórios são renomeados no GitHub antes das tags, para as fontes
   `git+ssh` já apontarem para `axon.git`.

## Alternativas rejeitadas

*Só a marca, com os nomes técnicos mantidos* (o que o brand kit sugere por padrão). Deixaria dois vocabulários para
sempre. Sem instalação a preservar, nunca vai ser tão barato mudar quanto agora.

*Distribuição `axon` com import `axon`.* Mais curto, mas colide com o pacote `axon` do PyPI no import e no nome de
distribuição.

*`axon-ai` também na operação* (`axon-ai serve`, `AXON_AI_*`, `x-axon-ai-*`). O operador digita esses nomes todo dia, e
o sufixo não acrescenta nada fora do ecossistema Python.

*Período de transição com os nomes antigos aceitos* (os dois prefixos de chave, as duas audiências, o rótulo HKDF
congelado). Só valeria com dado a preservar, e não há. Carregaria código de compatibilidade sem nenhum usuário.

*Uma spec transversal nova para o renome.* A constituição dá uma spec por módulo (princípio II). O renome é um seam que
muda em todos eles, e esse é o caso de um ADR com passadas nas specs afetadas.

## Consequências

- O pack externo troca de dependência (`axon-ai-contracts>=0.2,<0.3`), de grupo de entry point e de imports. Com isso,
  todo pack escrito para `0.1.x` precisa de nova versão. Hoje só existem `generic` e `scouting`.
- Quem tem um ambiente local recria contas e chaves, e reingere o corpus. As credenciais de teste exportadas pela
  distribuição (`TEST_API_KEY` e as do perfil `test`) mudam de valor e de módulo (`axon_ai.bootstrap.profiles`).
- A conexão do Open WebUI na instalação passa a mandar `x-axon-store` e `x-axon-progress`.
- "Axon" é marca de terceiros também em software (AxonIQ: Axon Framework/Server; Axon Enterprise). Antes de um
  lançamento público, é preciso verificar disponibilidade e registro (brand kit §12). Isso não bloqueia o
  desenvolvimento.
- A pasta local do repositório e a memória do Claude Code, que é indexada pelo caminho, mudam por último, à mão.
