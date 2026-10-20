# ADR-036 — Provider que informa o custo não tem preço de tabela; o relatório diz as requisições do dia

- **Status:** Aceita · 2026-10-20
- **Specs afetadas:** [006-core-llm-providers](../../specs/006-core-llm-providers/spec.md) (`ModelProvider.reports_cost`,
  `ProviderStatus.reports_cost`), [009-core-observability-evaluation](../../specs/009-core-observability-evaluation/spec.md)
  (`UsageDay.requests`), [008-core-http-api](../../specs/008-core-http-api/spec.md) (`GET /admin/v1/providers`,
  `POST /admin/v1/prices`, `GET /admin/v1/usage`), [013-core-admin-console](../../specs/013-core-admin-console/spec.md)
  (tela de uso e tabela de preços); refina o item 3 do [ADR-035](ADR-035-custo-informado-pelo-provider-e-providers-prontos.md)
- **Origem:** pedido do mantenedor (2026-10-20): na tela de uso, o custo informado pelo OpenRouter não aparecia na
  tabela nem no gráfico; modelo do OpenRouter nunca deve oferecer cadastro de preço; o gráfico deve alternar entre custo,
  requisições e tokens

## Contexto

O ADR-035 fez o custo informado vencer a tabela, mas manteve a tabela para as chamadas sem custo informado — inclusive
as do OpenRouter anteriores a ele. Na primeira instalação com o ADR-035, das 22 chamadas de um modelo do OpenRouter só
as 2 posteriores ao deploy traziam custo. O relatório devolvia o custo informado com `priced: false` (incompleto), e a
console tratava "incompleto" como "sem custo": a tabela escondia o valor atrás de "Sem preço", oferecia "Cadastrar", e o
gráfico tirava a linha. Cadastrar preço para o OpenRouter é justamente o trabalho manual que o ADR-035 quis eliminar.

A console decidia quem informa custo por um nome fixo (`"openrouter"`), sem nada na API que dissesse isso.

O gráfico passa a mostrar também requisições por dia. A 009 só dava requisições por (dia, chave): agrupado por modelo,
uma requisição do `agentic` com controller e geração em modelos diferentes conta nas duas linhas, e a soma do dia
passaria do total.

## Decisão

1. **Quem informa o custo é dado do provider.** A porta `ModelProvider` da 006 ganha `reports_cost: bool` (o
   `OpenRouterProvider` declara `True`; a camada compatível, `False`), e o `ProviderStatus` do seam Model Router ganha
   `reports_cost`, que `GET /admin/v1/providers` expõe.
2. **Provider que informa o custo não ganha preço de tabela.** `POST /admin/v1/prices` recusa com 422 (`param:
   provider`). As chamadas dele sem custo informado — as anteriores ao ADR-035 — ficam como **custo não informado**: a
   console mostra o custo parcial com o selo "Parcial", ou "Não informado" sem custo nenhum, e nunca "Cadastrar". Os
   preços já gravados continuam valendo para essas chamadas (o item 3 do ADR-035 não muda na 009).
3. **O relatório diz as requisições distintas de cada dia.** `UsageDay` ganha `requests` (aditivo); o armazenamento
   agrega `count(DISTINCT request_id)` por dia local. Por modelo, a console mostra requisições numa barra única por dia,
   sem empilhar; por Assistant, empilha, porque cada requisição tem um Assistant só.

## Alternativas rejeitadas

*Esconder o "Cadastrar" só na console, pelo nome do provider.* Mantém a regra num nome fixo do cliente, e a API
continuaria aceitando o preço.

*Tirar da 009 o custo pela tabela para o OpenRouter.* A 009 não conhece providers; e os preços já gravados deixariam de
valer para as chamadas antigas sem decisão de ninguém.

*Empilhar requisições por modelo com uma nota.* A altura da barra passaria do total do dia, que a dica mostraria
diferente.

## Consequências

- Quem implementa `ModelProvider` fora do core (dublês de teste) precisa de `reports_cost`.
- A console deixa de ter o nome `openrouter` no código; o aviso "Incompleto: N modelos sem preço" conta só os modelos
  de providers que não informam custo, e "Parcial: há chamadas sem custo informado" cobre o resto, sem atalho.
