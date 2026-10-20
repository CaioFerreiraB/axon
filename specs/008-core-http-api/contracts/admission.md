# Contrato — admissão e fila (Fase 7; FR-016, FR-017; research R35, R36)

Desenho pré-aprovado no [design.md](../design.md) ("Admissão e fila"). A decisão é pura (`domain/admission.py`); as
vagas e a fila são estado em memória do `ChatService` (`ExecutionSlots`), por processo.

## Ordem

```text
autenticação (401/503 storage) → corpo e cabeçalho (400) → conversa (404/400) → grant (404/424/429) → ADMISSÃO → motor
```

## Configuração (011)

| Variável | Faixa | Provisório |
|---|---|---|
| `AXON_MAX_EXECUTIONS` | 1–64 | 2 |
| `AXON_QUEUE_SIZE` | 0–1000 (0 = sem fila) | 8 |
| `AXON_QUEUE_WAIT_MS` | 1–600 000 | 60 000 |

Os provisórios são medidos no hardware alvo na implementação e fixados com os números no quickstart. Sem `admission`
em `create_app`, não há limite.

## Comportamento

| Situação | Sem streaming | Com streaming |
|---|---|---|
| vaga livre | executa | executa |
| vagas cheias, fila livre | espera na fila; vaga → executa; espera esgotada → 503 `overloaded` + `Retry-After` | stream aberto na hora, com a linha de fila como raciocínio; vaga → segue normalmente; espera esgotada → chunk final `finish_reason: "error"` com `QueueTimeout`, `[DONE]` |
| vagas e fila cheias | 503 `overloaded` + `Retry-After` | 503 `overloaded` + `Retry-After`, sem abrir o stream |

- A vaga é ocupada do início da execução até o evento final, ou até o iterador ser fechado (cliente desconectou).
- Quem desconecta na fila sai dela sem ocupar vaga; a ordem é de chegada.
- `Retry-After` = espera máxima em segundos, arredondada para cima, no mínimo 1.

## Verificações

| # | Verificação | Cenário |
|---|---|---|
| 1 | 10 pedidos simultâneos, 2 vagas, fila de 3: nunca mais de 2 execuções ao mesmo tempo; 5 recusados com 503 antes de qualquer chamada de modelo | SC-006, US6 cen. 3 |
| 2 | pedido na fila em streaming recebe a linha de fila no primeiro chunk depois da abertura, e segue ao ganhar a vaga | US6 cen. 2, SC-003 |
| 3 | espera esgotada: 503 sem streaming; `finish_reason: "error"` + `QueueTimeout` em streaming, sem chamada de modelo | FR-017 |
| 4 | cliente que fecha o stream na fila não ocupa vaga; o próximo da fila entra | Edge Cases |
| 5 | recusas de 404, 424 e 429 acontecem antes da admissão (não ocupam lugar na fila) | Ordem |
| 6 | a 011 lê as três variáveis e recusa valor fora da faixa nomeando a variável | 011 |
