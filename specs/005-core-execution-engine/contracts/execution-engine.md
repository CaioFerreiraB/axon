# Contrato — seam Execution Engine (005)

Dono: spec 005. Consumidores: 008 (traduz em SSE), 011 (monta), 003 (valida nomes de flow), 009 (harness, Fase 6).
Publicado em `ai_core/graph/api.py`. **Mudar qualquer assinatura abaixo exige ADR** (princípio II) — e é justamente o
que precisa sobreviver a uma reescrita completa do grafo (SC-001).

## Superfície

```python
from ai_core.graph.api import (
    ExecutionEngine, ExecutionEvent, ExecutionGrant, ExecutionIssue, ExecutionRequest,
    FinalEvent, ProgressEvent, TokenEvent,
    ExecutionError, ExecutionRequestInvalid, UnknownFlow,
    FLOW_CHAT, FLOW_AGENTIC,          # FLOW_AGENTIC: Fase 3
    FLOW_RAG_FIRST, RagSettings,      # Fase 5 (research R44)
    StepFinished, StepOutcome,        # desfecho de etapa (ADR-028, research R49)
    SourceRef, ToolCallSummary, ToolCallsOutcome, RerankOutcome, GateOutcome, GateRoute,
    ControllerOutcome, ControllerAction, GenerationOutcome, CatalogOutcome,
)
```

Nada além disso é público. `service.py`, `ports.py`, `domain/` e `adapters/` são internos; o estado do motor, os nomes
dos nós e o framework de grafo **não são contrato** (ADR-011).

## Uso

```python
events = engine.run(grant, ExecutionRequest(messages=messages))   # levanta aqui se a requisição for inválida
async for event in events:
    match event:
        case TokenEvent(text=text):       ...   # chega enquanto a geração ainda corre
        case ProgressEvent(stage=stage):  ...
        case StepFinished(stage=stage, outcome=outcome): ...   # ADR-028; quem não precisa, ignora
        case FinalEvent() as final:       ...   # exatamente um, sempre o último
```

## Regras do seam

| Regra | Origem | Verificada por |
|---|---|---|
| `run` levanta `ExecutionRequestInvalid`/`UnknownFlow` **na chamada**, antes de qualquer evento e de qualquer chamada de modelo | FR-013, US1 cen. 2, US5 cen. 2 | conformidade do seam |
| Depois do primeiro evento, nada levanta: falha vira `FinalEvent` com `errors` | [research.md](../research.md) R6 | conformidade do seam |
| Toda execução termina com exatamente um `FinalEvent`, inclusive em falha | FR-001 | conformidade do seam |
| O primeiro `TokenEvent` sai antes de o nó de geração terminar | princípio XI, SC-004 | conformidade do seam |
| `FinalEvent.answer` é a resposta do validator quando ele a altera | US1 cen. 3 | conformidade do seam |
| O motor fala com packs só por Pack Hooks e com modelos só pelo Model Router | FR-002 | conformidade + import-linter |
| `flows()` lista os nomes disponíveis; na Fase 1, `{"chat"}`; com o gateway da 004, também `agentic` (Fase 3) e `rag_first` (Fase 5) | US5 cen. 1 | conformidade do registro |
| `flow_roles()["rag_first"] == ("generation",)`: o `controller` é opcional e, declarado, é resolvido antes do primeiro evento | FR-007a, ADR-019 | conformidade do registro |
| `RagSettings(candidates=20, passages=5, min_score=None)`, do operador pela 011 (`AI_CORE_RAG_*`); sem limiar, só a ausência de resultado escala | FR-007, R44 | `test_graph_api.py`, `test_rag_first_flow.py` |
| Fechar o iterador no meio cancela a execução sem erro | edge case "cliente desconecta" | conformidade do seam |
| Nenhum tipo de framework de grafo aparece na superfície | ADR-011, SC-001 | import-linter + revisão da superfície |

## O grant

**Fase 1 e 2**: o motor lia `assistant`, `flow`, `composition` (002) e `models` (006) por um `Protocol` publicado aqui
([research.md](../research.md) R3, R4).

**A partir da Fase 3**: `ExecutionGrant` é o value object da 003, reexportado por este `api.py` com o mesmo nome
(R15, [ADR-018](../../../docs/adr/ADR-018-seam-execution-engine-fase-3.md)). A assinatura de `run` não muda, e o grant que a 008 já passava continua servindo. O motor lê ainda
`limits.max_iterations` e `limits.max_context_tokens`, e entrega o grant inteiro à 004 ao abrir a sessão de tools.

## Suíte de conformidade

`packages/core/tests/graph/contract/test_execution_engine_seam.py`, rodando o grafo real com o Pack Runtime real, o
pack `ai-generic` e o provider simulado da 006 (R13):

1. execução completa emite, em ordem: progresso de `prepare_context`, progresso de `generate`, tokens, progresso de
   `validate_answer` e um `FinalEvent` — o progresso de `generate` é o "primeiro sinal" barato que a SC-004 mede;
2. os tokens são incrementais e o primeiro chega antes do fim da geração;
3. `FinalEvent.answer` é a resposta completa quando nenhum validator a altera;
4. um validator que altera resposta e citações é refletido no `FinalEvent`, e suas `issues` viram `errors`;
5. requisição sem mensagem de usuário levanta `ExecutionRequestInvalid` na chamada, sem emitir nada;
6. grant com flow inexistente levanta `UnknownFlow` nomeando os disponíveis, sem emitir nada;
7. provider fora do ar vira `FinalEvent` com `kind="ModelCallFailed"`, sem exceção;
8. hook de pack que levanta vira `FinalEvent` com `kind="PackHookError"` e o pack nomeado;
9. `stream=False` entrega só o `FinalEvent`;
10. fechar o iterador depois do primeiro token não levanta, e nada mais é emitido;
11. o trace da execução tem começo, fim, um `ValidationRun` por validator e, nas falhas, um `ExecutionError`;
12. nenhum módulo de `tests/graph/contract` nem de `tests/graph/unit` importa o framework de grafo — é o que torna
    verificável a promessa do SC-001 de que estas suítes sobrevivem à troca do adapter.

## O que este seam **não** promete

- Não expõe estado interno, nomes de nó nem o framework (ADR-011).
- Não decide quais packs ou modelos usar: isso vem resolvido no grant (princípio IV).
- Não traduz nada para HTTP nem sabe o que é SSE — a tradução é da 008.
- Não persiste histórico de conversa: isso é da 008 (arch-v1 §28).

## Fase 3 — o que o seam acrescenta (US2)

| Regra | Origem | Verificada por |
|---|---|---|
| `flows()` inclui `agentic` só quando o motor tem `Capabilities`; sem ela, grant `agentic` → `UnknownFlow` na chamada | R16 | conformidade do registro |
| `flow_roles()`: para cada flow de `flows()`, os papéis que `run` confere (`chat`: `generation`; `agentic`: `controller`, `generation`); flow sem regra → `()`. Consumido pela 003 na validação | [ADR-019](../../../docs/adr/ADR-019-papeis-por-flow-no-seam-execution-engine.md) | conformidade do registro |
| Os papéis do flow (`agentic`: `controller` e `generation`) são resolvidos na chamada de `run`; papel ausente ou fora da allowlist → `ExecutionRequestInvalid` nomeando o papel | FR-013, R25 | conformidade do seam |
| `ExecutionIssue.severity` (`"error"` \| `"notice"`, default `"error"`): `notice` é resultado de política (limite, ação inválida, teto, validator), `error` é falha de dependência (inclusive MCP indisponível); `ExecutionFinished.ok` = nenhum `error` | R23, ADR-018 | unidade de `domain/outcome.py` + conformidade |
| Apontamento de validator sai com `severity="notice"` (o `kind` continua `ValidatorIssue`) | R23 | idem |
| Progresso do loop: `load_capabilities`, `controller` (`detail="iteração <n>"`), `execute_tool` (`detail=<nome pedido>`) | FR-012, R28 | conformidade do `agentic` |
| Depois do primeiro evento nada levanta — vale para o loop inteiro, inclusive `CatalogConflict` | R6 | idem |

A topologia, o que cada passo delega, o limite, o teto e o trace do `agentic` estão em
[agentic-flow.md](agentic-flow.md).

### Suíte de conformidade — acréscimos

`tests/graph/contract/test_agentic_flow.py` (gateway falso do testkit, controller simulado, roteador real da 006):

13. controller que pede `generic.calculate` e depois responde: uma execução, resultado acumulado, geração, `FinalEvent`
    sem `error` (US2 cen. 1);
14. limite 3 e controller que nunca responde: 3 chamadas ao controller, 3 execuções, geração, `IterationLimit`
    (US2 cen. 2) — e o mesmo com o limite do grant ausente (padrão 3);
15. ação malformada conta como iteração, vira `InvalidAction` e não interrompe (US2 cen. 3);
16. tool fora do catálogo: o resultado "tool inexistente" volta ao controller e conta como iteração (US2 cen. 4);
17. falha do controller: geração acontece, `ModelCallFailed` com `severity="error"` (FR-006a);
    MCP indisponível na abertura: a execução segue, com um `McpUnavailable` `error` por alias;
18. catálogo vazio: nenhuma chamada ao controller;
19. teto de contexto: o loop para antes da chamada que passaria do teto; na geração, os resultados mais antigos saem
    com a marca; sem teto, nada é cortado (FR-011);
20. a Turn View de `validate` traz os resultados entregues à geração, na ordem (FR-010);
21. o trace tem uma `ControllerDecision` por chamada ao controller (+ `limit`), sem argumentos (FR-016);
22. `agentic` sem papel `controller` → `ExecutionRequestInvalid` na chamada, sem evento; motor sem `Capabilities` →
    `UnknownFlow`.
23. fechar o iterador no meio do loop (depois do progresso `execute_tool`) não levanta, não há nova chamada ao
    controller nem à tool, e o trace fecha com `ExecutionFinished(reason="cancelled")`.

`tests/graph/contract/test_agentic_properties.py` (hypothesis, SC-002 e SC-005): para roteiros adversariais e limites
de 1 a 6, chamadas ao controller ≤ limite, execuções ≤ limite, exatamente um `FinalEvent`, todos os resultados
executados acumulados e entregues aos validators (salvo os omitidos pelo teto, que nunca é declarado nesta suíte).

## Geração filtrada pelos validators (2026-10-07, ADR-024)

| Regra | Verificada por |
|---|---|
| Só o que o filtro do Pack Hooks libera vira `TokenEvent`; a cauda sai no fim da geração | `tests/graph/contract/test_streaming_filter.py` |
| O `validate` recebe o resultado filtrado; o filtro abre antes da geração, sem `answer` | idem |
| Acréscimo dos validators em lote sai como token antes do evento final | idem |
| Reescrita no meio → `notice` `AnswerRewritten` | idem |
| Com e sem streaming, o texto final é o mesmo | idem; `tests/graph/integration/test_streaming_validators.py` (Pack Runtime real) |

## Desfecho de etapa (2026-10-13, [ADR-028](../../../docs/adr/ADR-028-o-motor-publica-o-desfecho-de-cada-etapa.md); research R49)

| Regra | Verificada por |
|---|---|
| Todo `ProgressEvent` tem um `StepFinished` da mesma etapa antes do próximo `ProgressEvent`; o `FinalEvent` vem depois de tudo | `tests/graph/contract/test_step_outcomes.py` |
| `generate` termina depois do último token, com o modelo e os tokens (`GenerationOutcome`) | idem |
| `retrieve` traz cada chamada com `query`/`top_k`, status e fontes; na falha, a chamada que falhou, e nenhuma etapa depois | idem |
| `rerank` traz as fontes mantidas e os packs com reranker que falhou; `gate`, a decisão e os trechos entregues | idem |
| `controller` traz a ação, o modelo e, em `tool`, os argumentos; `execute_tool`, a chamada com o status | idem |
| Nenhum desfecho traz texto de trecho, conteúdo de resultado, texto de erro de tool nem motivo de MCP indisponível | idem |
| `stream=False` entrega só o `FinalEvent` | idem e item 9 acima |

| Etapa | `outcome` |
|---|---|
| `prepare_context`, `validate_answer` | `None` |
| `load_capabilities` | `CatalogOutcome` |
| `controller` | `ControllerOutcome` |
| `execute_tool`, `retrieve` | `ToolCallsOutcome` |
| `rerank` | `RerankOutcome` |
| `gate` | `GateOutcome` |
| `generate` | `GenerationOutcome` |

