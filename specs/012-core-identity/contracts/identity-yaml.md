# Contrato — `identity.yaml` (clientes do operador)

Lido uma vez no boot pela 011 (`AI_CORE_IDENTITY_CLIENTS_FILE`), somente leitura para a plataforma. Erro de formato
para o boot com mensagem que nomeia o campo (FR-005).

```yaml
version: 1
clients:
  open-webui:
    type: confidential            # confidential | public
    secret: open_webui            # referência → AI_CORE_IDENTITY_SECRET_OPEN_WEBUI (só confidential)
    audience: ai-core             # aud do token de acesso
    redirect_uris:
      - http://localhost:3000/oauth/oidc/callback
    post_logout_redirect_uris:
      - http://localhost:3000/auth
  console:
    type: public                  # PKCE S256 obrigatório
    audience: ai-core-admin       # superfície de administração (ADR-031)
    redirect_uris:
      - http://localhost:8080/callback
    post_logout_redirect_uris:
      - http://localhost:8080/
```

| Campo | Regra |
|---|---|
| chave do cliente | `[a-z0-9][a-z0-9_-]{0,63}`; é o `client_id` |
| `type` | obrigatório |
| `secret` | obrigatório em `confidential`, proibido em `public`; gramática de referência `[a-z0-9_]{1,64}` → `AI_CORE_IDENTITY_SECRET_<REF em maiúsculas>`; variável ausente deixa o cliente indisponível (o boot segue, ADR-020) |
| `audience` | obrigatório; `ai-core` e `ai-core-admin` são os que a 003 aceita hoje |
| `redirect_uris` | 1+ URIs absolutas; `http` só para `localhost`/`127.0.0.1` ou nome sem ponto (rede interna do compose) |
| `post_logout_redirect_uris` | 0+ URIs, mesmas regras |

Nenhum valor de segredo no arquivo.
