# Contrato — `retrieval_filters` do pack `scouting` (101 → 103)

Interno ao repositório `axon-scouting`: produzido pela derivação de contexto (101) em `prepare_context`, consumido pelo
retriever da 103 (Fase 5), que o recebe do core pelo campo `filters` do contrato `Retriever` (001 — só da fatia do
próprio pack, nunca do modelo). Decisões em [research.md](../research.md) R8, R12, R35 e R37; facetas e Filhotes no [ADR-045](../../../docs/adr/ADR-045-filhotes-e-consulta-multifaceta-no-scouting.md).

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
| `branch` | string (id de ramo) | só com um ramo derivado | restringe ao ramo |
| `branches` | lista de ids de ramo (dois ou mais) | só com facetas derivadas; nunca junto de `branch` | uma busca por ramo, intercaladas (ADR-045) |
| `topics` | lista de ids de tema | só se não vazia | sinal de relevância (a 103 decide filtro ou reforço) |
| `document_types` | lista de ids de tipo | só se a pergunta cita um tipo | restringe aos tipos citados |
| `suggested_types` | lista de ids de tipo | só sem tipo citado e com tema ou sinal | não restringe: desempata a ordem (ADR-046) |
| `effective_from`, `effective_until` | data ISO | sempre | documentos vigentes em **algum** momento do intervalo, inclusivo |
| `include_superseded` | bool | sempre | inclui revogados e substituídos; a resposta marca a fonte como não vigente (104) |
| `previous_version` | bool | sempre | mira a versão imediatamente substituída em relação a `effective_until` |

Regras: valores são ids do léxico do pack (ASCII, `_`); ordem estável (a do léxico); nenhuma chave nova sem atualizar
este contrato e a 103. Mudança aqui é mudança interna do pack — não é seam do core.

Ids de ramo: `filhotes`, `lobinho`, `escoteiro`, `senior`, `pioneiro` (a ordem das idades e do léxico).
