# ADR-023 — O adapter da OpenAI converte o esquema para o subconjunto estrito, e desfaz a conversão na resposta

- **Status:** Aceita · 2026-10-07
- **Specs afetadas:** [006-core-llm-providers](../../specs/006-core-llm-providers/spec.md) (FR-005; supera a decisão
  "o esquema não é reescrito" da research R19); [005-core-execution-engine](../../specs/005-core-execution-engine/spec.md)
  (retira a pendência "esquema de ação de raiz objeto" — a 005 não muda)
- **Origem:** pendência registrada na Fase 3 (006 R19) e decisão do mantenedor em 2026-10-07

## Contexto

A 006 força `strict: true` em todo `response_format` de esquema (R18) e, na R19, decidiu não reescrever o esquema: a
recusa do provider vira erro explícito. O esquema de ação da 005 tem `anyOf` na raiz, e o modo estrito da OpenAI exige
mais do que raiz objeto: todo campo em `required` (o opcional se emula com união com `null`), `additionalProperties:
false` em todo objeto e nada de `allOf`, `not` ou `if/then/else`. Parâmetros opcionais são comuns nas tools de MCP. Na
prática, a OpenAI não servia de controller do `agentic`, nem com a raiz corrigida na 005.

A objeção da R19 à reescrita era que ela mudaria a forma dos argumentos que o core recebe.

## Decisão

O adapter da OpenAI — e o do OpenRouter para modelos `openai/…` — converte o esquema de saída para o subconjunto
estrito **na ida** e desfaz a conversão **na volta**, de modo que quem chama recebe o conteúdo na forma do esquema
original:

- raiz que não é objeto vira `{"type": "object", "properties": {"value": <esquema>}, "required": ["value"],
  "additionalProperties": false}` (com `$defs` levado para a nova raiz); na volta, o `value` é desembrulhado;
- propriedade opcional vira obrigatória e anulável; na volta, o `null` que a conversão introduziu sai — um `null` que o
  esquema original já admitia fica;
- todo objeto recebe `additionalProperties: false`; `oneOf` vira `anyOf` (o gateway da 004 continua validando os
  argumentos contra o esquema original); anotações sem efeito na geração (`default`, `examples`, `title`) saem;
- o que não tem equivalente estrito — objeto livre, `additionalProperties` aberto, `allOf`, `not`, `if/then/else`,
  `patternProperties`, esquema sem tipo — é recusado **antes da rede**, com `ModelCallFailed` nomeando onde está o
  problema. Nunca se reenvia sem restrição (FR-005).

Pelo mesmo motivo, os **nomes de função** seguem a regra da API da OpenAI (`^[a-zA-Z0-9_-]{1,64}$`): as tools do core
têm namespace com ponto (`demo.eco`, 004), e o adapter troca, na ida, cada nome que não cabe por um apelido
determinístico e sem colisão (prefixo legível e 8 hexadecimais do hash), nas mensagens da transcrição e nas tools; na
volta, as `tool_calls` voltam ao nome original. O teste real com `openai/gpt-4.1-nano` via OpenRouter mostrou as duas
regras — além da documentada, que todo nó do esquema precisa de `type` (inclusive `const` e `enum`).

As regras são puras (`ai_core/llm/domain/strict.py`, `ai_core/llm/domain/names.py`); o adapter só as aplica. Nenhum seam
muda.

## Alternativas rejeitadas

*A 005 publica um esquema de ação de raiz objeto (a pendência original).* Resolve só a raiz; parâmetros opcionais e
objetos sem `additionalProperties: false` continuariam recusados, e a 005 passaria a conhecer a regra de um provider.

*Converter sem desfazer (a objeção da R19).* O core receberia `null` em parâmetros opcionais e a forma embrulhada — o
gateway recusaria argumentos válidos.

*Converter para todo provider.* Recusaria, antes da rede, esquemas que outros providers aceitam (objeto livre, por
exemplo) — perda sem ganho.

## Consequências

- OpenAI (e `openai/…` via OpenRouter) passa a servir de controller do `agentic` — verificado ponta a ponta com o
  esquema de ação da 005 e uma tool de MCP —; a pendência da 005 deixa de existir
- Tool com esquema sem equivalente estrito torna a chamada do controller na OpenAI um erro explícito; o operador escolhe
  outro provider para o papel `controller` desse Assistant
- Um `null` explícito num parâmetro opcional que o esquema original não admitia é tratado como ausente — é exatamente a
  emulação de opcional que a OpenAI documenta
