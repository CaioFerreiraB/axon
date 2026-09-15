# ADR-006 — `rag_first` determinístico como default do scouting

- **Status:** Aceita · 2026-09-10
- **Specs afetadas:** [101-scouting-pack](../../specs/101-scouting-pack/spec.md), [005-core-execution-engine](../../specs/005-core-execution-engine/spec.md)
- **Origem:** arch-v1 Parte VIII

## Contexto

O desenho original levava toda pergunta ao `agent_controller`, que decidia se recuperava documentos — inclusive no caso dominante do scouting, que é responder a partir do corpus.

## Decisão

O flow default do scouting é `rag_first`: retrieval e rerank determinísticos, depois geração. Escalada para o loop agêntico acontece por **portão determinístico** (score abaixo de limiar, nenhum documento vigente), nunca por decisão de LLM.

## Consequências

- Elimina uma a duas chamadas de LLM no caminho comum, o que importa a 5–15 tok/s
- Mais confiável: não depende de um modelo de 1.7B decidir corretamente que precisa buscar
- Aplica literalmente o princípio "determinismo antes de LLM"
- Custo: perguntas fora do padrão pagam retrieval desnecessário antes de escalar — barato comparado a uma chamada de LLM
- Nota de modularidade (2026-09-10): o pack referencia o flow só por nome (dado), e o Assistant pode sobrescrever. Se o grafo for reescrito e o nome mudar, a validação de assistants acusa a referência pendente.
