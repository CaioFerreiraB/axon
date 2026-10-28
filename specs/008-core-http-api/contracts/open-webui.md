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
| Plataforma (003) | verifica o access token JWT: emissor, audiência, chaves (`AXON_OIDC_JWKS_URL`), subject e grupos; token expirado ou de outro emissor → 401 |
| Lista de modelos | o Open WebUI busca `/v1/models` com o token de cada usuário e guarda em cache por usuário; com `BYPASS_MODEL_ACCESS_CONTROL=true`, mostra exatamente essa lista |

Requisito do provedor: access token **JWT** com `aud` contendo a audiência da plataforma e as claims de subject e de
grupos que a 003 lê. A sessão do Open WebUI (`JWT_EXPIRES_IN`) precisa vencer **antes** da sessão do provedor: depois
que a do provedor cai, o Open WebUI não renova mais o token (`invalid_grant`), chama `/v1/models` sem credencial (401),
a lista de modelos fica vazia e a conversa falha com "Model '' was not found" — sair e entrar resolve.

## Conexão (`OPENAI_API_CONFIGS`)

```json
{"0": {"enable": true, "auth_type": "system_oauth", "headers": {"x-axon-store": "false", "x-axon-progress": "status", "x-axon-citations": "sources"}, "connection_type": "external"}}
```

com `OPENAI_API_BASE_URLS` apontando para o `/v1` da plataforma e `ENABLE_OLLAMA_API=false`. O `x-axon-progress:
status` (FR-005a) mostra o progresso na timeline de status do Open WebUI, em vez do bloco de raciocínio (research R42).
O `x-axon-citations: sources` (FR-005b) manda as citações como fontes do Open WebUI: o `[n]` vira um chip que abre o
detalhe da fonte, com o nome ligado ao original, e a lista "N Fontes" é colapsável (research R61, ADR-051).

## Tarefas auxiliares desligadas (clarificação 3)

`ENABLE_TITLE_GENERATION`, `ENABLE_TAGS_GENERATION`, `ENABLE_FOLLOW_UP_GENERATION`, `ENABLE_AUTOCOMPLETE_GENERATION`,
`ENABLE_SEARCH_QUERY_GENERATION` e `ENABLE_RETRIEVAL_QUERY_GENERATION` = `false`; `ENABLE_PERSISTENT_CONFIG=false`
para que o ambiente prevaleça. `DEFAULT_MODEL_PARAMS={"function_calling": "legacy"}` e
`DEFAULT_MODEL_METADATA={"capabilities": {"builtin_tools": false}}`: no v0.12 a chamada de função nativa é o padrão, e
as ferramentas embutidas do Open WebUI (memória, notas, hora, calendário…) iriam no campo `tools` de toda conversa do
navegador — recusado com 400 (princípio IV). O modo legado nunca manda `tools` à conexão, inclusive para um modelo que
ganhou cadastro pela tela (o cadastro vence o metadado padrão, mas não traz parâmetros).

## O que a API garante

| Pedido do Open WebUI | Resposta |
|---|---|
| `GET /v1/models` com o token do usuário | os Assistants que aquele token resolve (FR-003), id `<assistant>` |
| `POST /v1/chat/completions`, `stream: true`, parâmetros do modelo, `x-axon-store: false`, `x-axon-progress: status`, `x-axon-citations: sources` | 200 SSE: papel, timeline de status (fila, início e desfecho de cada etapa, avisos, conclusão), texto, uma fonte `source` por citação, chunk final, `[DONE]`; nenhuma conversa gravada |
| `tools` (modo nativo) | 400 `widening_field` |
| conteúdo multimodal (imagem anexada) | 400 em `messages` |
| plataforma cheia | 503 `overloaded` + `Retry-After` (o Open WebUI mostra o erro) |

## Verificações

| # | Verificação | Onde |
|---|---|---|
| 1 | o pedido do Open WebUI v0.12 (fixture, com `x-axon-progress: status`) recebe streaming com a timeline de status antes e depois do texto, nenhum raciocínio, a última linha com `done: true`, `[DONE]` e nenhum id de conversa; sem o cabeçalho, raciocínio como antes | `tests/http/contract/test_open_webui.py` |
| 2 | dois tokens de grupos diferentes → duas listas diferentes em `/v1/models`, cada uma só com o que o token resolve | idem (US8 cen. 1–2) |
| 1b | com `x-axon-citations: sources`, cada citação sai como fonte `source` depois do texto e antes do chunk final, na ordem do `[n]`, com a legenda, a página − 1 e só URL `http(s)`; sem o cabeçalho ou sem streaming, nenhuma; valor desconhecido → 400 | `tests/http/contract/test_open_webui.py`, `tests/http/unit/test_sources.py` |
| 3 | a interface de verdade: dois usuários do Keycloak de desenvolvimento, seletor de modelos e uma conversa em streaming; uma execução por mensagem no trace | passada de encaixe da 002 (US8 cen. 2–5) |
