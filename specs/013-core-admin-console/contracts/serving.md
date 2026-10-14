# Contrato — como a console é servida

Artefato: `ai-core/console/dist/` (arquivos estáticos do `vite build`) servidos por nginx a partir de
`ai-core/console/deploy/nginx.conf.template`. O estágio de imagem e o serviço no compose são da 002.

| Caminho | Comportamento |
|---|---|
| `/assets/*` (com hash) | arquivo; `Cache-Control: public, max-age=31536000, immutable` |
| `/index.html` e qualquer rota da SPA sem extensão | `index.html`; `Cache-Control: no-cache` |
| `/v1/`, `/private/v1/`, `/admin/v1/`, `/oauth2/`, `/.well-known/` | repasse ao core (`${AI_CORE_UPSTREAM}`, padrão `http://ai-core:8000`) **sem reescrever o caminho**, com `X-Forwarded-Proto`, `X-Forwarded-Host`, `X-Forwarded-For`; `proxy_buffering off` e `proxy_read_timeout 300s` em `/v1/` (SSE) |

Cabeçalhos da console (não dos repasses, que mantêm os do core):

```text
Content-Security-Policy: default-src 'self'; img-src 'self' data:; style-src 'self'; font-src 'self';
                         connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'
X-Content-Type-Options: nosniff
Referrer-Policy: no-referrer
Strict-Transport-Security: max-age=31536000   (só atrás de https)
```

Com a console, `AI_CORE_PUBLIC_URL` é a origem dela, e `AI_CORE_TRUSTED_PROXIES` inclui o endereço do nginx na rede do
compose. O cliente `console` do `identity.yaml` registra `<origem>/callback` e `<origem>/` (012).
