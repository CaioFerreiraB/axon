# Contrato — repositório de instalação `agentic-deploy` (Fase 4, US5)

Decisões em [research.md](../research.md) R21–R29; [ADR-009](../../../docs/adr/ADR-009-deploy-docker-build-arg.md) e
[ADR-022](../../../docs/adr/ADR-022-instalacao-constroi-o-core-num-estagio-proprio.md). Repositório privado
`CaioFerreiraB/agentic-deploy`, submódulo `agentic-deploy/` do `agentic-app`.

## Build-args

| Arg | Default | Significado |
|---|---|---|
| `CORE_REF` | `v0.1.0` | tag (ou branch) do `agentic-app` de onde vêm `ai-core-contracts`, `ai-core` e `ai-generic` — clone raso, sem submódulos |
| `CORE_REPO` | `ssh://git@github.com/CaioFerreiraB/agentic-app.git` | repositório do core |
| `PACKS` | `ai-scouting @ git+ssh://git@github.com/CaioFerreiraB/ai-scouting.git@329d592010a74eaaa0cc113ef2f717905455be8f` | requisitos dos packs, separados por espaço (PyPI, URL de git ou caminho em `/build/packages`) |

Identidades SSH do BuildKit: `core` (lê `CORE_REPO`) e `packs` (lê os repositórios dos packs).

## Estágios

| Estágio | Conteúdo | Falha quando |
|---|---|---|
| `core` | `/opt/ai-core` com os contratos, o core e o `ai-generic` da tag | a tag ou o acesso ao `agentic-app` faltam |
| `packs` | `core` + packs + `/etc/ai-core/packs.yaml`; `ai-core packs check` | um pack não instala, ou `packs check` sai ≠ 0 (pack em erro → 1; `packs.yaml` inválido → 2) |
| `runtime` | o ambiente e o `packs.yaml` do `packs`, sem `uv`, `pip` nem `ensurepip`; usuário `ai-core` (uid 10001) sem escrita em `/opt/ai-core`; `CMD ["ai-core", "serve"]` | — |

## Ambiente do runtime

| Variável | Valor | Origem |
|---|---|---|
| `AI_CORE_HOST` | `0.0.0.0` | imagem |
| `AI_CORE_PACKS_FILE` | `/etc/ai-core/packs.yaml` (na imagem) | imagem |
| `AI_CORE_ASSISTANTS_FILE` | `/etc/ai-core/assistants.yaml` (montado, somente leitura) | imagem |
| perfil, chaves, OIDC, provedores | — | `.env` (fora do git; modelo em `.env.example`) |

## `scripts/check-build.sh` (o *Independent Test*)

| Passo | Esperado |
|---|---|
| build do `runtime` com o `PACKS` default | sucesso (US5 cen. 1) |
| `ai-core packs list` na imagem | `generic` e `scouting` `enabled` |
| `ai-core assistants validate` com `config/assistants.yaml` | sai com 0 |
| `uv`, `pip`, `python -m ensurepip` na imagem; escrita em `/opt/ai-core` como o usuário do processo | ausentes / recusada (US5 cen. 3) |
| build do `packs` com `PACKS=/build/packages/incompatible-pack` | falha no `packs check`, saída nomeando `incompatible` (US5 cen. 2) |

Sai com 0 só se todos valem. `SSH_CORE` e `SSH_PACKS` escolhem a origem de cada identidade (default: o agente SSH).

## CI (`.github/workflows/build.yml`)

Push e PR: deploy keys só de leitura nos segredos `AGENTIC_APP_DEPLOY_KEY` (cadastrada no `agentic-app`) e
`AI_SCOUTING_DEPLOY_KEY` (no `ai-scouting`), gravadas em arquivo e passadas por `SSH_CORE`/`SSH_PACKS`;
`scripts/check-build.sh` em `linux/amd64`.

## Fase 5 (2026-10-13): RAG na instalação (research R31–R35)

| Item | Valor |
|---|---|
| `CORE_REF` | `v0.2.0` |
| `PACKS` | `ai-scouting @ git+ssh://git@github.com/CaioFerreiraB/ai-scouting.git@c60ffb460e082751e39705b539fbb82aa46eeccb` |
| Estágio `packs` | depois dos packs, `ai-scouting-corpus model fetch /opt/ai-scouting/e5-small`; depois, `packs check` |
| Estágio `runtime` | copia também `/opt/ai-scouting` (o modelo, somente leitura) |
| `config/packs.yaml` | `scouting.config`: `qdrant_url: http://qdrant:6333`, `embedding_dir: /opt/ai-scouting/e5-small` |
| `config/assistants.yaml` | `scouting` sem `flow` (logo `rag_first`) e com `collections: [scouting]` |
| `docker-compose.yml` | serviço `qdrant` (`qdrant/qdrant:v1.19.2`, volume nomeado, sem porta publicada); `ai-core` depende dele e recebe `AI_SCOUTING_QDRANT_URL` e `AI_SCOUTING_EMBEDDING_DIR` para a CLI |
| Ingestão | `docker compose run --rm -v <ai-scouting>/corpus:/corpus:ro ai-core ai-scouting-corpus ingest /corpus/corpus.yaml` |
| Chave do Qdrant (opcional) | o mesmo valor em `QDRANT__SERVICE__API_KEY` e `AI_SCOUTING_QDRANT_API_KEY`, no `.env` |
| Imagem | `ORT_DISABLE_TELEMETRY=1` (sem telemetria do onnxruntime) |
| Porta do host | `AI_CORE_HOST_PORT` no `.env` (default 8000) |

`scripts/check-build.sh`, passo novo: `/opt/ai-scouting/e5-small` tem `model.onnx` e `tokenizer.json`, e
`ai-scouting-corpus --help` roda na imagem. A conversa com o índice ingerido é verificação manual.

## Fase 7 (2026-10-13): Open WebUI e Keycloak de desenvolvimento (research R36–R40)

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
| `OPENAI_API_CONFIGS` | `headers` com `x-ai-core-store: false` **e** `x-ai-core-progress: status` |

`scripts/check-webui.py`, passo novo: a mensagem gravada pelo Open WebUI tem `statusHistory`, começando em "Preparando o
contexto da pergunta…", com a linha "Resposta de <modelo>" e terminando em "Concluído em …" com `done: true`.

## Fase 9 (2026-10-14): com ou sem console, sem Keycloak (research R42–R50)

| Modo | `COMPOSE_PROFILES` | Serviços | Login |
|---|---|---|---|
| Padrão | vazio | `ai-core`, `postgres`, `qdrant` | só chaves de API (`ai-core keys create`) |
| Com chat | `webui` | + `open-webui` | página da plataforma (012); Open WebUI como cliente confidencial |
| Com console | `console` | + `console` (nginx) | página da plataforma; console como cliente público |
| Completo | `webui,console` | todos | os dois |

- **Sempre**: `AI_CORE_PROFILE=persistent`, Postgres com volume, `AI_CORE_MASTER_KEY`.
- **Com interface**: `AI_CORE_IDENTITY_ENABLED=true`, `AI_CORE_PUBLIC_URL`, `config/identity.yaml` montado,
  `AI_CORE_IDENTITY_SECRET_OPEN_WEBUI` (com `webui`), admin inicial por arquivo; Google opcional.
- **Langfuse**: sem console, pelas variáveis `AI_CORE_LANGFUSE_*`; com console, pela tela.
- **Removidos**: `keycloak`, `keycloak-data`, `config/keycloak/`, `KEYCLOAK_*`, `OPEN_WEBUI_OIDC_SECRET`.
- **Provas**: `scripts/check-build.sh` (com o alvo `console`), `scripts/check-webui.py` (login da plataforma),
  `scripts/check-console.py` (admin, sobreposição, uso).
