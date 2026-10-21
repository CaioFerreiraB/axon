# Contrato — `retrieval_filters` do pack `scouting` (101 → 103)

Interno ao repositório `axon-scouting`: produzido pela derivação de contexto (101) em `prepare_context`, consumido pelo
retriever da 103 (Fase 5), que o recebe do core pelo campo `filters` do contrato `Retriever` (001 — só da fatia do
próprio pack, nunca do modelo). Decisões em [research.md](../research.md) R8 e R12.

```json
{
  "branch": "pioneiro",
  "topics": ["lideranca"],
  "document_types": ["manual", "programa_educativo"],
  "effective_from": "2023-01-01",
  "effective_until": "2023-12-31",
  "include_superseded": true,
  "previous_version": false
}
```

| Chave | Tipo | Presença | Significado para a recuperação |
|---|---|---|---|
| `branch` | string (id de ramo) | só com ramo derivado | restringe ao ramo |
| `topics` | lista de ids de tema | só se não vazia | sinal de relevância (a 103 decide filtro ou reforço) |
| `document_types` | lista de ids de tipo | só se não vazia | restringe aos tipos |
| `effective_from`, `effective_until` | data ISO | sempre | documentos vigentes em **algum** momento do intervalo, inclusivo |
| `include_superseded` | bool | sempre | inclui revogados e substituídos; a resposta marca a fonte como não vigente (104) |
| `previous_version` | bool | sempre | mira a versão imediatamente substituída em relação a `effective_until` |

Regras: valores são ids do léxico do pack (ASCII, `_`); ordem estável (a do léxico); nenhuma chave nova sem atualizar
este contrato e a 103. Mudança aqui é mudança interna do pack — não é seam do core.
