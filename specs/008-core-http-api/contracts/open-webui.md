# Contrato — Open WebUI conectado (Fase 7; US8; research R37–R40)

O Open WebUI fala só o formato da OpenAI; nada nele é específico da plataforma (FR-011, SC-001). Este contrato diz o que
a API garante a ele e como a conexão é configurada — a instalação de referência (002, passada de encaixe) aplica a
configuração.

## Versão

Open WebUI **v0.12.0** (2026-10-10). Mudança de versão refaz a fixture de `tests/http/open_webui_v0_12.py` a
partir do código da nova versão.

## Identidade (clarificação 1)

| Lado | O que acontece |
|---|---|
| Open WebUI | login pelo provedor OIDC (`OPENID_PROVIDER_URL`, `OAUTH_CLIENT_ID`/`SECRET`); a conexão usa `auth_type: system_oauth`, que manda `Authorization: Bearer <access token do usuário>` e o renova a menos de 5 minutos de expirar |
| Plataforma (003) | verifica o access token JWT: emissor, audiência, chaves (`AI_CORE_OIDC_JWKS_URL`), subject e grupos; token expirado ou de outro emissor → 401 |
| Lista de modelos | o Open WebUI busca `/v1/models` com o token de cada usuário e guarda em cache por usuário; com `BYPASS_MODEL_ACCESS_CONTROL=true`, mostra exatamente essa lista |

Requisito do provedor: access token **JWT** com `aud` contendo a audiência da plataforma e as claims de subject e de
grupos que a 003 lê.

## Conexão (`OPENAI_API_CONFIGS`)

```json
{"0": {"enable": true, "auth_type": "system_oauth", "headers": {"x-ai-core-store": "false"}, "connection_type": "external"}}
```

com `OPENAI_API_BASE_URLS` apontando para o `/v1` da plataforma e `ENABLE_OLLAMA_API=false`.

## Tarefas auxiliares desligadas (clarificação 3)

`ENABLE_TITLE_GENERATION`, `ENABLE_TAGS_GENERATION`, `ENABLE_FOLLOW_UP_GENERATION`, `ENABLE_AUTOCOMPLETE_GENERATION`,
`ENABLE_SEARCH_QUERY_GENERATION` e `ENABLE_RETRIEVAL_QUERY_GENERATION` = `false`; `ENABLE_PERSISTENT_CONFIG=false`
para que o ambiente prevaleça. Chamada de função no modo padrão (o "nativo" mandaria `tools`, recusado com 400).

## O que a API garante

| Pedido do Open WebUI | Resposta |
|---|---|
| `GET /v1/models` com o token do usuário | os Assistants que aquele token resolve (FR-003), id `<assistant>` |
| `POST /v1/chat/completions`, `stream: true`, parâmetros do modelo, `x-ai-core-store: false` | 200 SSE: papel, linhas de raciocínio (progresso, fila), texto, chunk final, `[DONE]`; nenhuma conversa gravada |
| `tools` (modo nativo) | 400 `widening_field` |
| conteúdo multimodal (imagem anexada) | 400 em `messages` |
| plataforma cheia | 503 `overloaded` + `Retry-After` (o Open WebUI mostra o erro) |

## Verificações

| # | Verificação | Onde |
|---|---|---|
| 1 | o pedido do Open WebUI v0.12 (fixture) recebe streaming com raciocínio antes do texto, `[DONE]` e nenhum id de conversa | `tests/http/contract/test_open_webui.py` |
| 2 | dois tokens de grupos diferentes → duas listas diferentes em `/v1/models`, cada uma só com o que o token resolve | idem (US8 cen. 1–2) |
| 3 | a interface de verdade: dois usuários do Keycloak de desenvolvimento, seletor de modelos e uma conversa em streaming; uma execução por mensagem no trace | passada de encaixe da 002 (US8 cen. 2–5) |
