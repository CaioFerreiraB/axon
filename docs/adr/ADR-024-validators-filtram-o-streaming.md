# ADR-024 — Validators que reescrevem a resposta filtram o streaming

- **Status:** Aceita · 2026-10-07
- **Specs afetadas:** [001-core-contracts](../../specs/001-core-contracts/spec.md) (protocolo novo, aditivo — contratos
  `0.1.1`), [002-core-pack-runtime](../../specs/002-core-pack-runtime/spec.md) (seam Pack Hooks ganha a abertura do
  filtro e aceita o resultado filtrado), [005-core-execution-engine](../../specs/005-core-execution-engine/spec.md)
  (a geração passa pelo filtro; o acréscimo final sai como token), [104-scouting-citations](../../specs/104-scouting-citations/spec.md)
  (`citation_integrity` filtra; resolve a pendência 104 R11). A 008 não muda.
- **Origem:** pendência 104 R11 (2026-10-07) e decisão do mantenedor no mesmo dia

## Contexto

Os validators rodam depois da geração. Com streaming, os pedaços já saíram: a resposta reescrita (citação `[n]`, citação
inventada removida, avisos) chegava só sem streaming; com streaming, o cliente via `[[id]]` cru — inclusive a citação
inventada — e nenhum aviso. Isso fura o SC-001 da 104 ("0 citações inventadas em respostas entregues") e a US2/US3
("aviso visível"). Desligar o streaming de tokens quando há validator que reescreve deixaria o usuário de 20 a 60
segundos sem ver nada no hardware alvo (princípio XI).

## Decisão

1. **Contrato 001 (`0.1.1`, aditivo).** Um validator pode também implementar `StreamingValidator`:
   `open_stream(view, ctx) -> AnswerStream`, com `feed(delta) -> str` (o texto pronto para sair agora; pode segurar o
   que ainda não decidiu) e `finish() -> ValidationResult`. Regras: `finish().answer` **começa** com a concatenação do
   que `feed` devolveu (o fim só acrescenta) e o resultado é **igual** ao de `validate` sobre a resposta inteira, para
   qualquer partição em pedaços. A sessão vê a Turn View da abertura (antes da geração) e não depende de citações de
   validators anteriores. O kit de conformidade verifica a igualdade e o acréscimo em três partições.
2. **Pack Hooks (002).** `open_answer_stream(composition, view, slices)` devolve um filtro que encadeia os validators
   com `open_stream` que formam o **prefixo** da sequência de validators da composição; `finish()` devolve o resultado
   filtrado (cauda, resposta e execuções). `validate(..., streamed=…)` reaproveita essas execuções e roda só os
   restantes.
3. **Motor (005).** A geração passa cada pedaço pelo filtro e emite só o que ele libera; ao fim, emite a cauda. Depois
   dos validators restantes, se a resposta final só **acrescenta** ao que saiu, o acréscimo sai como token; se reescreve
   no meio, fica um registro `notice` (o cliente em streaming recebeu o texto anterior). Os dois modos da API entregam o
   mesmo texto.
4. **104.** `citation_integrity` filtra: segura o texto só enquanto há um marcador `[[` aberto (e o espaço antes dele) e
   solta `[n]` ou nada quando o marcador fecha. `validity_notice` continua em lote — ele só acrescenta, e o acréscimo
   sai como token pelo item 3.

## Alternativas rejeitadas

*Desligar o streaming de tokens quando há validator que reescreve.* Simples, mas contra o princípio XI no hardware alvo.

*Mandar a resposta corrigida num campo do último pedaço.* Clientes padrão (Open WebUI) não o aplicariam, e a citação
inventada já teria sido exibida.

*Validator só acrescenta, nunca reescreve.* Não resolve a citação inventada, que precisa sair do texto.

## Consequências

- Nenhuma citação inventada chega ao cliente, com ou sem streaming; avisos aparecem no texto em ambos
- O atraso visível é só o trecho de um marcador `[[…]]` enquanto ele não fecha
- Contratos `0.1.1` (tag `contracts-v0.1.1`); packs que não implementam `open_stream` não mudam
- Validator em lote que reescreve no meio da resposta continua possível, mas com streaming o cliente vê o texto anterior
  e a execução registra isso
