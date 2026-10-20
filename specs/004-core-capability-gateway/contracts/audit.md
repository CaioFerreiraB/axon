# Contrato — auditoria de tools de escrita (US4; FR-011, FR-015; clarificações 4 e 5; research R8)

## A ordem

```text
execute(call) de tool com mutates=True
  ├─ AuditLog.begin(entrada)   ── falhou? → FencedToolResult(status="error", "auditoria indisponível"); NADA executa
  ├─ despacho (sob prazo)
  └─ AuditLog.finish(id, status, resultado como o modelo recebeu, instante)
                                ── falhou? → o registro fica "started"; o resultado volta ao modelo normalmente
```

Toda escrita executada tem registro (SC-002). Duas chamadas iguais → dois registros.

## O registro

Campos e regras em [data-model.md](../data-model.md) ("AuditRecord"). `result` é o texto **cercado e cortado** que foi
ao contexto do modelo. Sem expiração nesta fase.

## A porta

```python
class AuditLog(Protocol):
    async def begin(self, entry: AuditEntry) -> str: ...            # id do registro
    async def finish(self, record_id: str, *, status: AuditStatus, result: str, at: datetime) -> None: ...
    async def query(self, filter: AuditFilter) -> Sequence[AuditRecord]: ...
```

Postgres: schema `capabilities`, tabela `audit` (ADR-015); `arguments` em `jsonb`; índices por `started_at`, `principal`,
`assistant` e `tool`. Datas como parâmetro, nunca `now()`.

## O comando `axon audit` (registrado pela 011)

```text
axon audit [--principal P] [--assistant A] [--tool T] [--since ISO] [--until ISO] [--limit N]
```

Uma linha por registro, do mais recente para o mais antigo: instante de início, status, Principal, Assistant, tool, e os
argumentos em JSON numa linha. O resultado não é impresso por padrão (`--results` o inclui). Código 0; 2 para filtro
inválido (data fora do ISO 8601, limite fora de 1–1 000).

Conformidade: `contract/test_audit_log.py` (memória e Postgres: abrir, fechar, ficar `started`, filtros, ordem, limite),
`contract/test_audit_write.py` (a ordem acima) e `contract/test_audit_query.py` (o comando, por função).
