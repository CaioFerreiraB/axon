# ADR-035 — O custo informado pelo provider entra na chamada; a administração lista os providers prontos

- **Status:** Aceita · 2026-10-20
- **Specs afetadas:** [001-core-contracts](../../specs/001-core-contracts/spec.md) (`ChatUsage.cost`, contratos
  `0.1.3`), [006-core-llm-providers](../../specs/006-core-llm-providers/spec.md) (lê o custo; `ModelRouting.providers`),
  [009-core-observability-evaluation](../../specs/009-core-observability-evaluation/spec.md) (`ModelCall.cost_usd`; o
  custo do relatório), [008-core-http-api](../../specs/008-core-http-api/spec.md) (`GET /admin/v1/providers`),
  [013-core-admin-console](../../specs/013-core-admin-console/spec.md) (provedor como seleção); refina o item 5 do
  [ADR-034](ADR-034-trace-com-destinos-e-conteudo-opcional.md)
- **Origem:** pedido do mantenedor (2026-10-20): não cadastrar preço de modelo do OpenRouter à mão, e escolher o
  provedor numa lista na console, só entre os que a plataforma consegue usar

## Contexto

O OpenRouter devolve, em `usage.cost`, o custo em USD de cada chamada — também no último pedaço do streaming. A camada
compatível da 006 lia só os tokens, e a 009 calculava todo custo pela tabela de preços (ADR-034, item 5). Cada modelo do
OpenRouter precisava de preço cadastrado e mantido à mão, embora o provider já dissesse quanto cobrou.

Na console, o modelo de um papel e o de um preço eram digitados como `provider/modelo`. Nada dizia quais providers
existiam nem quais funcionavam: os remotos sem chave e o Ollama sem servidor ficam registrados (006 FR-011).

## Decisão

1. **O custo informado é fato da chamada.** `ChatUsage` (contrato 001) ganha `cost: NotRequired[float]`, o USD que o
   provider informou — aditivo, contratos `0.1.3` (ADR-014). A camada compatível o lê de `usage.cost` de qualquer
   endpoint que o informe; com chave própria no upstream (`is_byok`), soma `cost_details.upstream_inference_cost`. O
   adapter do OpenRouter pede `usage.include` em todo pedido.
2. **O `ModelCall` da 009 ganha `cost_usd: float | None`**, que o `TracedModel` da 006 preenche. É um evento aditivo
   sem texto (ADR-017).
3. **O custo informado vence a tabela.** No relatório, o custo de um grupo (dia, chave, modelo) é a soma informada mais,
   pela tabela, os tokens das chamadas sem custo informado. A tabela continua valendo para os providers que não informam
   e para as chamadas de antes desta decisão. Um modelo só "precisa de preço" quando sobram tokens sem custo informado:
   uma chamada que falhou, sem tokens, não pede preço.
4. **Providers prontos.** O seam Model Router ganha `providers() -> tuple[ProviderStatus, ...]` (`name`, `ready`,
   `detail`), e a porta `ModelProvider`, `ready()`. O remoto está pronto se tem a credencial (sem rede); o local, se o
   endpoint responde à lista de modelos. A 008 expõe `GET /admin/v1/providers`, e a console oferece na escolha de modelo
   os prontos, mais o provider já em uso no papel, marcado como indisponível.

## Alternativas rejeitadas

*Custo só pela tabela, com o preço buscado no catálogo do OpenRouter.* Seria uma estimativa: não cobre descontos,
cache de prompt, BYOK nem o upstream que o OpenRouter escolheu de fato.

*Custo informado substituindo o preço da tabela.* Deixaria sem custo as chamadas antigas e as de providers que não
informam.

*Tipo próprio da 006 com o custo, sem tocar o contrato 001.* `ChatResponse.usage` é do contrato; um subtipo fora dele
exigiria leitura com `cast` e esconderia um campo que de fato atravessa o seam.

*Providers prontos pela saúde agregada da 011.* A saúde sonda modelos de Assistants; a escolha de provedor precisa da
lista de providers, independente de modelo.

## Consequências

- O item 5 do ADR-034 passa a ser: o custo **calculado** não entra no trace; o custo **informado** pelo provider, sim,
  como dado da chamada.
- `observability.model_calls` ganha `reported_cost_usd numeric` (migração `004`), nulo nas linhas antigas.
- O Langfuse recebe o custo informado na geração (`cost_details`); sem ele, estima pela tabela própria.
- Quem implementa `ModelProvider` fora do core (dublês de teste) precisa de `ready()`.
