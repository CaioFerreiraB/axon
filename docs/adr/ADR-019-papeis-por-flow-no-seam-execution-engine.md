# ADR-019 — O Execution Engine publica os papéis de modelo que cada flow exige

- **Status:** Aceita · 2026-10-02
- **Specs afetadas:** [005-core-execution-engine](../../specs/005-core-execution-engine/spec.md) (dona do seam;
  contracts/execution-engine.md), [003-core-assistants-access](../../specs/003-core-assistants-access/spec.md)
  (consome, FR-011), [011-core-bootstrap](../../specs/011-core-bootstrap/spec.md) (injeta), [specs/README.md](../../specs/README.md)
  (tabela de seams)
- **Origem:** clarificação de 2026-10-02 da 003 (pergunta 1); pendência R33 da 005

## Contexto

O seam *Execution Engine* publica os **nomes de flow** como dado (`flows()`), que a 003 usa para recusar Assistant de
flow inexistente antes de servir (FR-011 dela). Na Fase 3 surgiu um segundo dado do mesmo tipo: o flow `agentic` usa
o papel de modelo `controller`, e o `chat` só usa `generation`. O motor já confere isso na chamada de `run`
(ExecutionRequestInvalid, research R25 da 005), mas a validação de Assistants não enxerga: um Assistant `agentic` sem
`controller` aparece disponível e falha em toda requisição. O princípio VII pede detecção o mais cedo possível.

Quais papéis cada flow usa é decisão da 005 (`domain/request.py`). Se a 003 escrevesse "agentic exige controller",
conheceria um interior do motor — o que o princípio II proíbe —, e as duas regras poderiam divergir.

## Decisão

1. O `Protocol` `ExecutionEngine` (005) ganha `flow_roles() -> Mapping[str, tuple[ModelRole, ...]]`: para cada flow
   que `flows()` oferece, os papéis de modelo (vocabulário da 006) que uma execução dele resolve. É dado, como os
   nomes de flow, e vem da mesma regra que `run` aplica.
2. A 003 recebe esse mapeamento pela composition root (011), junto com os nomes de flow, e marca indisponível — na
   validação e na resolução — o Assistant cujo flow efetivo exige um papel que ele não declara; Assistant de usuário
   assim é recusado na criação e na atualização.
3. Mudança aditiva: nada existente muda de forma; implementações do `Protocol` fora do core não existem.

## Alternativas rejeitadas

*A 003 conhece a regra.* Viola o princípio II e duplica uma regra que precisa ser a mesma do motor.

*A 011 monta o mapa a partir das constantes internas da 005.* A composition root passaria a conhecer política de
domínio de outro módulo, o que a spec dela proíbe ("não conhece regras de negócio de qualquer módulo").

*Não validar; deixar o erro na requisição (400).* Assistant mal configurado ficaria disponível no relatório de
validação e na listagem.

## Consequências

- `contracts/execution-engine.md` da 005 registra o método e a regra "papéis de `flow_roles()` == papéis que `run`
  confere".
- A linha do seam *Execution Engine* em `specs/README.md` passa a citar os papéis por flow como dado consumido pela 003.
- Um flow futuro (`rag_first`, Fase 5) declara os papéis dele no mesmo lugar, e a validação da 003 o acompanha sem
  mudar.
