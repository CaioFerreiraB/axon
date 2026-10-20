#!/usr/bin/env bash
# O nginx da instalação servindo o dist/ da console e repassando ao core do e2e (013 T036). Rede do host: o nginx
# escuta 8080 e o core está em 127.0.0.1:8765 (o serve_platform.py). Rode a partir de ai-core/console, depois do build.
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
exec docker run --rm --name console-e2e-nginx --network host \
  -e AI_CORE_UPSTREAM="${AI_CORE_UPSTREAM:-http://127.0.0.1:8765}" \
  -e NGINX_ENVSUBST_FILTER=AI_CORE_ \
  -v "$here/dist:/usr/share/nginx/html:ro" \
  -v "$here/deploy/nginx.conf.template:/etc/nginx/templates/default.conf.template:ro" \
  --read-only --tmpfs /tmp:uid=101,gid=101,mode=0755 --tmpfs /etc/nginx/conf.d:uid=101,gid=101,mode=0755 \
  nginxinc/nginx-unprivileged:1.28.0-alpine
