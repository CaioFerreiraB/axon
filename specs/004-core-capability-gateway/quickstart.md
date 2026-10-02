# Quickstart — 004 Capability Gateway (Fase 3)

Roteiro de validação do módulo, a partir de `ai-core/`, com `XDG_DATA_HOME=$HOME/.local/share` nesta máquina. O flow
`agentic` (005), as tools de pack pela 002 e a montagem na 011 são das passadas delas; aqui o módulo é validado pelos
próprios seams, com packs falsos e o cliente MCP real da 007.

```bash
uv run pytest packages/core/tests/capabilities -v
AI_CORE_TEST_POSTGRES_DSN=postgresql://postgres:pg@localhost:55432/postgres \
  uv run pytest packages/core/tests/capabilities -v          # + auditoria no Postgres
uv run mypy && uv run ruff check packages && uv run lint-imports
```

| Cenário | Onde | Esperado |
|---|---|---|
| US1 — catálogo exato | `contract/test_session_catalog.py` | dois grants, dois catálogos exatos; `a.search` sem `b.search` com `allowed_tools: [a.search]`; nome sem namespace não casa |
| US1 cen. 3 / FR-005 | `contract/test_session_execute.py` | proibida e inexistente respondem igual: `unknown` |
| US2 — despacho e limites | `contract/test_session_execute.py` | nativa, recuperação e MCP despachadas; prazo → `timeout`; acima do limite → cortado com marca; argumentos inválidos não despacham |
| US3 — dado, não instrução | `contract/test_prompt_injection.py` | cerca íntegra com `</tool_result>` no conteúdo; nenhuma chamada fora do catálogo executa |
| US4 — escrita | `contract/test_session_catalog.py`, `contract/test_audit_write.py` | sem `write_tools`, a tool não aparece; com, a chamada é auditada antes; auditoria fora → não executa |
| US5 — coleções | `contract/test_session_catalog.py` | retriever com coleção fora do grant ausente; parcial não basta |
| SC-001 | `contract/test_capabilities_adversarial.py` | nomes arbitrários nunca executam |
| FR-014 | `contract/test_session_execute.py` | um `tool_call` no trace por chamada, sem argumentos |
| FR-015 | `contract/test_audit_query.py` | filtros por Principal, Assistant, tool e período; mais recente primeiro |
| MCP real | `integration/test_session_mcp.py` | tools do servidor de demonstração da 007 como `<alias>.<tool>`, executadas pelo cliente restrito |
