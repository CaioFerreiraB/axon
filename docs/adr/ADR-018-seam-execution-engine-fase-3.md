# ADR-018 — Seam Execution Engine na Fase 3: grant da 003 e gravidade dos registros

- **Status:** Aceita · 2026-10-02
- **Specs afetadas:** [005-core-execution-engine](../../specs/005-core-execution-engine/spec.md) (dona do seam:
  research R15, R23; contracts/execution-engine.md),
  [008-core-http-api](../../specs/008-core-http-api/spec.md) (passa o grant; traduz `FinalEvent.errors` e decide o
  `finish_reason`), [009-core-observability-evaluation](../../specs/009-core-observability-evaluation/spec.md)
  (`ExecutionFinished.ok`; o harness da Fase 6 executa pelo motor),
  [011-core-bootstrap](../../specs/011-core-bootstrap/spec.md) (monta o motor),
  [003-core-assistants-access](../../specs/003-core-assistants-access/spec.md) (produz o grant);
  supera, no ponto indicado, as "Consequências" do [ADR-016](ADR-016-grant-carrega-politica-de-modelos.md)
- **Origem:** `/speckit-analyze` da passada da Fase 3 da 005 (achado C1), em 2026-10-02

## Contexto

O flow `agentic` (005 US2) muda duas coisas na superfície do seam *Execution Engine*:

1. **O grant.** Nas Fases 1 e 2 o motor recebia o grant por um `Protocol` publicado no próprio `api.py` (research R3
   da 005), que lia `assistant`, `flow`, `composition` e `models`. O R3 previa que o `Protocol` cresceria de forma
   aditiva. Na Fase 3 o motor precisa entregar o grant ao `Capabilities.open(grant, contexto)` da 004, que recebe o
   `ExecutionGrant` **concreto** da 003 — principal, aliases de MCP, coleções, `allowed_tools`, `write_tools`, limites.
   Um `Protocol` não satisfaz um parâmetro nominal; ampliá-lo até repetir a 003 inteira duplicaria a forma do grant.
   O ADR-016 registrou, como consequência, que "o `Protocol` da 005 continua como está".
2. **A gravidade dos registros.** `FinalEvent.errors` só tinha um tipo de registro que não era falha — o apontamento de
   validator —, reconhecido pelo `kind` `"ValidatorIssue"` na 005 (`succeeded`) e, duplicado como texto, na 008
   (`finish_reason`). O loop cria registros que também não são falha: limite de iterações atingido, ação inválida do
   modelo, parada e corte por teto de contexto. Sem distinguir, toda execução truncada vira falha no trace e
   `finish_reason: "error"` na API, e a 008 teria de conhecer cada `kind` da 005.

O princípio II exige ADR para mudança de seam, com as specs consumidoras listadas.

## Decisão

1. **O motor recebe o `ExecutionGrant` da 003.** O `Protocol` sai do `api.py` da 005, que passa a importar e
   reexportar `ExecutionGrant` de `ai_core.assistants.api` com o mesmo nome. A assinatura `run(grant, request)` não
   muda. A seta 005 → 003 já existe no grafo de `specs/README.md`, e o import-linter já permite `ai_core.graph` →
   `ai_core.assistants.api`.
2. **`ExecutionIssue` ganha `severity: Literal["error", "notice"] = "error"`.** `notice` é registro que não é falha da
   execução: apontamento de validator, limite de iterações, ação inválida do controller, parada e corte por teto de
   contexto. Falha de dependência — provider, hook de pack, conflito de catálogo, MCP indisponível, falha do
   controller — é `error`. O `kind` continua livre e estável, mas consumidores **não** decidem sucesso por ele.
3. **`ExecutionFinished.ok` (009) = nenhum registro `error` no `FinalEvent`.**

### O que muda para cada consumidora

| Spec | Mudança | Quando |
|---|---|---|
| 008 | Nenhuma obrigatória: já passa o grant da 003, e o campo novo tem default. Passa a decidir o `finish_reason` por `severity` em vez de `kind == "ValidatorIssue"`; até lá, uma execução `agentic` truncada sai com `finish_reason: "error"` e a resposta inteira | passada de encaixe da 008 (Fase 3) |
| 009 | `ok` deixa de contar `notice` como falha; o harness lê o mesmo seam | nesta passada, pela 005 |
| 011 | Nenhuma: já monta o motor com o grant que a 003 resolve | — |
| 003 | Nenhuma: produz o mesmo value object | — |

Testes de outros módulos que passam ao motor objetos com a forma antiga do grant continuam funcionando no flow `chat`,
que só lê os quatro campos de antes; ganham o grant da 003 nas passadas desses módulos.

## Alternativas rejeitadas

*Ampliar o `Protocol` com os campos que a 004 lê e mudar a 004 para aceitá-lo.* Edita outra spec, e a forma do grant
passaria a existir em dois `Protocol`s, que podem divergir da 003.

*`cast` na chamada à 004.* Esconde do mypy exatamente a garantia que o tipo dá.

*Registrar os avisos do loop em `flags` em vez de `errors`.* A 005 US2 cen. 2 diz "o truncamento é registrado em
erros"; e `flags` são marcações sobre a resposta, dadas pelos validators.

*Publicar a lista de `kind`s que não são falha.* A 008 continuaria acoplada a nomes da 005, e cada `kind` novo exigiria
mexer nela.

## Consequências

- A frase das "Consequências" do ADR-016 sobre o `Protocol` da 005 fica superada neste ponto; a decisão do ADR-016
  (seta 003 → 006, a 003 monta a `ModelPolicy`) continua inteira.
- O contrato `specs/005-…/contracts/execution-engine.md` registra as duas mudanças com remissão a este ADR.
- A 008 tem uma pendência explícita na passada de encaixe dela (o `finish_reason` por `severity`).
