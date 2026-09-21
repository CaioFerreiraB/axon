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
    FLOW_CHAT,
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
| `flows()` lista os nomes disponíveis; na Fase 1, `{"chat"}` | US5 cen. 1 | conformidade do registro |
| Fechar o iterador no meio cancela a execução sem erro | edge case "cliente desconecta" | conformidade do seam |
| Nenhum tipo de framework de grafo aparece na superfície | ADR-011, SC-001 | import-linter + revisão da superfície |

## Forma exigida do grant

O motor lê `assistant`, `flow`, `composition` (002) e `models` (006) — nada mais. Qualquer objeto com esses quatro
atributos serve, o que permite à 003 produzir o valor na Fase 2 sem que este módulo a importe
([research.md](../research.md) R3, R4).

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
