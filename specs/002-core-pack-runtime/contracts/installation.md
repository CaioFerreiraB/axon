# Contrato — repositório de instalação `axon-deploy` (Fase 4, US5)

Decisões em [research.md](../research.md) R21–R29; [ADR-009](../../../docs/adr/ADR-009-deploy-docker-build-arg.md) e
[ADR-022](../../../docs/adr/ADR-022-instalacao-constroi-o-core-num-estagio-proprio.md). Repositório privado
`CaioFerreiraB/axon-deploy`, submódulo `axon-deploy/` do `axon`.

## Build-args

| Arg | Default | Significado |
|---|---|---|
| `CORE_REF` | `v0.1.0` | tag (ou branch) do `axon` de onde vêm `axon-ai-contracts`, `axon-ai` e `axon-generic` — clone raso, sem submódulos |
| `CORE_REPO` | `ssh://git@github.com/CaioFerreiraB/axon.git` | repositório do core |
| `PACKS` | `axon-scouting @ git+ssh://git@github.com/CaioFerreiraB/axon-scouting.git@329d592010a74eaaa0cc113ef2f717905455be8f` | requisitos dos packs, separados por espaço (PyPI, URL de git ou caminho em `/build/packages`) |

Identidades SSH do BuildKit: `core` (lê `CORE_REPO`) e `packs` (lê os repositórios dos packs).

## Estágios

| Estágio | Conteúdo | Falha quando |
|---|---|---|
| `core` | `/opt/axon` com os contratos, o core e o `axon-generic` da tag | a tag ou o acesso ao `axon` faltam |
| `packs` | `core` + packs + `/etc/axon/packs.yaml`; `axon packs check` | um pack não instala, ou `packs check` sai ≠ 0 (pack em erro → 1; `packs.yaml` inválido → 2) |
| `runtime` | o ambiente e o `packs.yaml` do `packs`, sem `uv`, `pip` nem `ensurepip`; usuário `axon` (uid 10001) sem escrita em `/opt/axon`; `CMD ["axon", "serve"]` | — |

## Ambiente do runtime

| Variável | Valor | Origem |
|---|---|---|
| `AXON_HOST` | `0.0.0.0` | imagem |
| `AXON_PACKS_FILE` | `/etc/axon/packs.yaml` (na imagem) | imagem |
| `AXON_ASSISTANTS_FILE` | `/etc/axon/assistants.yaml` (montado, somente leitura) | imagem |
| perfil, chaves, OIDC, provedores | — | `.env` (fora do git; modelo em `.env.example`) |

## `scripts/check-build.sh` (o *Independent Test*)

| Passo | Esperado |
|---|---|
| build do `runtime` com o `PACKS` default | sucesso (US5 cen. 1) |
| `axon packs list` na imagem | `generic` e `scouting` `enabled` |
| `axon assistants validate` com `config/assistants.yaml` | sai com 0 |
| `uv`, `pip`, `python -m ensurepip` na imagem; escrita em `/opt/axon` como o usuário do processo | ausentes / recusada (US5 cen. 3) |
| build do `packs` com `PACKS=/build/packages/incompatible-pack` | falha no `packs check`, saída nomeando `incompatible` (US5 cen. 2) |

Sai com 0 só se todos valem. `SSH_CORE` e `SSH_PACKS` escolhem a origem de cada identidade (default: o agente SSH).

## CI (`.github/workflows/build.yml`)

Push e PR: deploy keys só de leitura nos segredos `AGENTIC_APP_DEPLOY_KEY` (cadastrada no `axon`) e
`AI_SCOUTING_DEPLOY_KEY` (no `axon-scouting`), gravadas em arquivo e passadas por `SSH_CORE`/`SSH_PACKS`;
`scripts/check-build.sh` em `linux/amd64`.

## Fase 5 (2026-10-13): RAG na instalação (research R31–R35)

| Item | Valor |
|---|---|
| `CORE_REF` | `v0.2.0` |
| `PACKS` | `axon-scouting @ git+ssh://git@github.com/CaioFerreiraB/axon-scouting.git@c60ffb460e082751e39705b539fbb82aa46eeccb` |
| Estágio `packs` | depois dos packs, `axon-scouting-corpus model fetch /opt/axon-scouting/e5-small`; depois, `packs check` |
| Estágio `runtime` | copia também `/opt/axon-scouting` (o modelo, somente leitura) |
| `config/packs.yaml` | `scouting.config`: `qdrant_url: http://qdrant:6333`, `embedding_dir: /opt/axon-scouting/e5-small` |
| `config/assistants.yaml` | `scouting` sem `flow` (logo `rag_first`) e com `collections: [scouting]` |
| `docker-compose.yml` | serviço `qdrant` (`qdrant/qdrant:v1.19.2`, volume nomeado, sem porta publicada); `axon` depende dele e recebe `AXON_SCOUTING_QDRANT_URL` e `AXON_SCOUTING_EMBEDDING_DIR` para a CLI |
| Ingestão | `docker compose run --rm -v <axon-scouting>/corpus:/corpus:ro axon axon-scouting-corpus ingest /corpus/corpus.yaml` |
| Chave do Qdrant (opcional) | o mesmo valor em `QDRANT__SERVICE__API_KEY` e `AXON_SCOUTING_QDRANT_API_KEY`, no `.env` |
| Imagem | `ORT_DISABLE_TELEMETRY=1` (sem telemetria do onnxruntime) |
| Porta do host | `AXON_HOST_PORT` no `.env` (default 8000) |

`scripts/check-build.sh`, passo novo: `/opt/axon-scouting/e5-small` tem `model.onnx` e `tokenizer.json`, e
`axon-scouting-corpus --help` roda na imagem. A conversa com o índice ingerido é verificação manual.

## Fase 7 (2026-10-13): Open WebUI e Keycloak de desenvolvimento (research R36–R40)

> Histórico: o Keycloak saiu na Fase 9 (seção abaixo), e os nomes desta seção são os de antes do ADR-037 (tabela do
> incremento 9.5, no fim).

| Item | Valor |
|---|---|
| `CORE_REF` | `v0.4.1` (a `v0.4.0` com a correção do verificador OIDC da 003) |
| `PACKS` | `ai-scouting @ git+ssh://git@github.com/CaioFerreiraB/ai-scouting.git@24cb157590dbc81c9b6778de0b868fcc8064c36b` |
| Perfil do compose | `webui`: `keycloak` e `open-webui` sobem com `docker compose --profile webui up`; sem o perfil, a instalação é a de antes |
| `keycloak` | `quay.io/keycloak/keycloak:26.7.5`, `start-dev --import-realm`, realm `config/keycloak/agentic-realm.json`, dados no volume `keycloak-data`, porta `${KEYCLOAK_HOST_PORT:-8180}` → 8080, `KC_HOSTNAME=http://localhost:8180`, `KC_HOSTNAME_BACKCHANNEL_DYNAMIC=true` |
| Realm `agentic` | cliente `open-webui` (confidencial), audiência `ai-core` e `groups` no access token, grupo `equipe`, usuários `ana` e `bia` (`equipe`); sessão de 10 h; segredo e senha por placeholder do `.env` |
| `open-webui` | `ghcr.io/open-webui/open-webui:v0.12.0`, porta `${OPEN_WEBUI_HOST_PORT:-3000}` → 8080, volume `open-webui-data`, configuração da 008 R40 só por ambiente, mais `DEFAULT_USER_ROLE=user`, `DEFAULT_MODEL_PARAMS={"function_calling": "legacy"}` e `DEFAULT_MODEL_METADATA={"capabilities": {"builtin_tools": false}}`, `JWT_EXPIRES_IN=${OPEN_WEBUI_SESSION_EXPIRES_IN:-8h}` |
| Core (`.env`) | `AI_CORE_OIDC_ISSUER`, `AI_CORE_OIDC_AUDIENCE=ai-core`, `AI_CORE_OIDC_JWKS_URL` (rede interna), `AI_CORE_OIDC_SUBJECT_CLAIM=preferred_username`; fila (`AI_CORE_MAX_EXECUTIONS`, `AI_CORE_QUEUE_SIZE`, `AI_CORE_QUEUE_WAIT_MS`) opcionais |
| `config/assistants.yaml` | + `interno`: privado, `allow: ["group:equipe"]`, só `oidc`, flow `chat`, pack `generic` |

`scripts/check-webui.py` (manual, com o perfil `webui` de pé): login OIDC de `ana` e de `bia` pelo Open WebUI, listas
de modelos diferentes (`interno` só para a `bia`), uma mensagem montada como a tela de chat do v0.12 a monta (conversa
salva, `session_id`, `model_item`, `features`) respondida pela plataforma, e exatamente um `POST /v1/chat/completions`
no log do `ai-core`, com 200 (sem `tools` e efêmero).

## Timeline de status (2026-10-13; research R41; 008 FR-005a)

| Item | Valor |
|---|---|
| `CORE_REF` | `v0.5.0` (o motor publica o desfecho de cada etapa, ADR-028; a API mostra a timeline de status) |
| `OPENAI_API_CONFIGS` | `headers` com `x-axon-store: false` **e** `x-axon-progress: status` |

`scripts/check-webui.py`, passo novo: a mensagem gravada pelo Open WebUI tem `statusHistory`, começando em "Preparando o
contexto da pergunta…", com a linha "Resposta de <modelo>" e terminando em "Concluído em …" com `done: true`.

## Fase 9 (2026-10-14): com ou sem console, sem Keycloak (research R42–R50)

| Modo | `COMPOSE_PROFILES` | Serviços | Login |
|---|---|---|---|
| Padrão | vazio | `axon`, `postgres`, `qdrant` | só chaves de API (`axon keys create`) |
| Com chat | `webui` | + `open-webui` | página da plataforma (012); Open WebUI como cliente confidencial |
| Com console | `console` | + `console` (nginx) | página da plataforma; console como cliente público |
| Completo | `webui,console` | todos | os dois |

- **Sempre**: `AXON_PROFILE=persistent`, Postgres com volume, `AXON_MASTER_KEY`.
- **Com interface**: `AXON_IDENTITY_ENABLED=true`, `AXON_PUBLIC_URL`, `config/identity.yaml` montado,
  `AXON_IDENTITY_SECRET_OPEN_WEBUI` (com `webui`), admin inicial por arquivo; Google opcional.
- **Langfuse**: sem console, pelas variáveis `AXON_LANGFUSE_*`; com console, pela tela.
- **Removidos**: `keycloak`, `keycloak-data`, `config/keycloak/`, `KEYCLOAK_*`, `OPEN_WEBUI_OIDC_SECRET`.
- **Provas**: `scripts/check-build.sh` (com o alvo `console`), `scripts/check-webui.py` (login da plataforma),
  `scripts/check-console.py` (admin, sobreposição, uso).

## Fase 9, incremento 9.5 (2026-10-20): os nomes da Axon (research R56–R61; ADR-037)

| Antes | Agora |
|---|---|
| projeto do compose (da pasta `agentic-deploy`) | `name: axon` fixo no arquivo |
| serviço `ai-core` · imagens `agentic-deploy:local`, `agentic-deploy-console:local` | `axon` · `axon:local`, `axon-console:local` |
| `CORE_REPO` `agentic-app.git` · `CORE_REF=v0.6.0-rc6` | `axon.git` · `v0.7.0-rc1` |
| `/opt/ai-core`, `/opt/ai-scouting`, `/etc/ai-core`, `/run/secrets/ai-core` | `/opt/axon`, `/opt/axon-scouting`, `/etc/axon`, `/run/secrets/axon` |
| usuário do processo `ai-core` · `CMD ai-core serve` | `axon` (uid 10001) · `axon serve` |
| Postgres `ai_core` (usuário e banco) | `axon` |
| `AI_CORE_*` · `AI_SCOUTING_*` | `AXON_*` · `AXON_SCOUTING_*` |
| pack `ai-scouting` 0.3.0 | `axon-scouting` 0.4.0 (repositório `axon-scouting`) |
| `x-ai-core-store`, `x-ai-core-progress` na conexão do Open WebUI | `x-axon-store`, `x-axon-progress` |
| audiências `ai-core`, `ai-core-admin` nos clientes | `axon`, `axon-admin` |
| nome padrão "Agentic" no botão de login | "Axon"; `WEBUI_NAME=Axon` |
| console: `AI_CORE_UPSTREAM`, filtro `AI_CORE_` | `AXON_UPSTREAM`, filtro `AXON_` |

- **Corte seco**: um `.env` com `AI_CORE_*` ou `AI_SCOUTING_*` não sobe; o `check-build.sh` prova a recusa na imagem.
- **Migração**: volumes novos (`axon_*`), contas recriadas, corpus reingerido; o roteiro está no README.
- **Ficam**: os segredos da CI (`AGENTIC_APP_DEPLOY_KEY`, `AI_SCOUTING_DEPLOY_KEY`); os nomes dos volumes sem o prefixo;
  o uid do processo; os clientes `open-webui` e `console`.
