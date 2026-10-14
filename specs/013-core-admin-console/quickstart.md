# Quickstart — validação da 013 Admin Console

Comandos a partir de `ai-core/console/`, com `source ~/.nvm/nvm.sh && nvm use` (Node 24) e, para o e2e,
`XDG_DATA_HOME=$HOME/.local/share` (uv).

## 1. Checagens estáticas e unidades

```bash
npm ci
npm run typecheck && npm run lint && npm test
```

Esperado: esquemas `zod` aceitam os exemplos do contrato da 008 e recusam variações; componentes e hooks verdes com MSW.

## 2. Ponta a ponta contra a plataforma em memória

```bash
npx playwright install chromium
npm run e2e
```

O `webServer` do Playwright sobe `uv run python e2e/serve_platform.py` (perfil `test` com identidade, provider
programado, Google simulado, admin semeado, uso semeado) e `vite preview` com o repasse do nginx. Esperado: os cenários
das sete user stories, o axe sem violações nos dois temas (SC-005) e as capturas de referência.

| Cenário | Arquivo |
|---|---|
| US1: entrar por senha e pelo Google simulado; acesso negado; sair | `e2e/auth.spec.ts` |
| US2: trocar o modelo de geração, testar, salvar, descartar; travado; inativa; conflito | `e2e/assistant-models.spec.ts` |
| US3: ligar servidor e marcar tools; escrita bloqueada em público | `e2e/assistant-mcp.spec.ts` |
| US4: dashboard 7/30/90, por modelo e por Assistant; preço novo recalcula | `e2e/usage.spec.ts` |
| US5: Langfuse salvo e testado; segredo só "definido"; captura com aviso | `e2e/observability.spec.ts` |
| US6: cadastrar pessoa e ver a senha uma vez; desativar; Google desligado sem cliente | `e2e/access.spec.ts` |
| US7: servidores MCP globais; do arquivo somente leitura | `e2e/mcp-servers.spec.ts` |

## 3. Desenvolvimento local

```bash
# outro terminal, a partir de ai-core/: uv run ai-core serve (perfil memory com identidade)
npm run dev
```

O `vite dev` repassa os mesmos prefixos do nginx para `http://127.0.0.1:8000`.

## 4. Imagem e instalação

Na passada da 002: build da imagem `console` e o `scripts/check-console` contra o compose.
