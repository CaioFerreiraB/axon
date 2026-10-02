# Contrato — saúde agregada (Fase 2, US5; research R16; clarificação 2)

`bootstrap/health.py` implementa a porta `HealthProvider` da 008. Consumida por `GET /private/v1/health` e por
`ai-core health`.

| Item | Crítico | Quando aparece não saudável |
|---|---|---|
| `database` | **sim** | `persistent` e o `SELECT 1` falha ou passa de 3 s |
| `boot:<etapa>` | não | etapa degradada no boot (o detalhe é o motivo do relatório) |
| `pack:<nome>` | não | pack em erro no Pack Registry |
| `assistant:<nome>` | não | Assistant indisponível na validação (motivos no detalhe) |
| `model:<provider/modelo>` | não | `ModelRouting.check` diz indisponível, ou passa de 3 s |

**Resultado**: `down` se algum item crítico falha; `degraded` se só não críticos falham; `ok` se nenhum. Só `down` é
503 na superfície privada (008); `ok` e `degraded` são 200. Itens saudáveis também aparecem, para que o operador veja o
que foi conferido (SC-005).

**Cache**: o resultado vale por 15 s; consultas dentro da janela não repetem as checagens.

```json
{"status": "degraded",
 "items": [{"name": "database", "ok": true, "critical": true, "detail": null},
           {"name": "model:ollama/qwen3:1.7b", "ok": false, "critical": false, "detail": "fora do ar: ..."}]}
```

Conformidade (`tests/bootstrap/unit/test_health.py`): provider fora do ar → `degraded` com o modelo nomeado e os demais
saudáveis (US5 cen. 1); tudo bem → `ok` (cen. 2); banco inacessível → `down` (cen. 3); checagem lenta vira item não
saudável no timeout; segunda consulta dentro de 15 s não repete checagens.

---

## Fase 3 (2026-10-02): servidores MCP globais (clarificação 1, research R28)

| Item | Crítico | Origem |
|---|---|---|
| `mcp:<alias>` | não | `McpRegistry.check(alias)` (007) para cada servidor de `globals()` |
| `mcp` | não | só quando listar os globais falha — o motivo vai em `detail` |

As checagens rodam em paralelo com as demais, cada uma sob o prazo de 3 s, e entram no cache de 15 s. O boot nunca
verifica servidor MCP. Servidores de usuário não entram: são do usuário, e a saúde responde a qualquer chave.

### Suíte de conformidade — acréscimos

- servidor global fora do ar → `degraded` (200), item `mcp:<alias>` com o motivo, demais saudáveis;
- servidor que não anuncia uma tool da allowlist → item não saudável nomeando a tool;
- registry que não lista → item `mcp` não saudável, não crítico;
- consulta repetida dentro de 15 s não chama `check` de novo.
