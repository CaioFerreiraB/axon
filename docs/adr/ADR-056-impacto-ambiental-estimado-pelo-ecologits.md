# ADR-056 — Impacto ambiental das chamadas de modelo, estimado pelo EcoLogits

- **Status:** Aceita · 2026-11-03
- **Specs afetadas:** [009-core-observability-evaluation](../../specs/009-core-observability-evaluation/spec.md) (US9:
  porta `ImpactEstimator`, colunas novas no uso, seam **Impact Report**),
  [008-core-http-api](../../specs/008-core-http-api/spec.md) (US12: `GET /admin/v1/impact`),
  [011-core-bootstrap](../../specs/011-core-bootstrap/spec.md) (US8: montagem, variáveis `AXON_IMPACT_*`, saúde e
  `axon usage impact-backfill`), [013-core-admin-console](../../specs/013-core-admin-console/spec.md) (US11: página
  Meio ambiente e a célula Emissões em Uso e custo)
- **Origem:** pedido do mantenedor (2026-11-03): medir o impacto ambiental das chamadas de LLM com todas as métricas do
  EcoLogits, gravar por chamada e mostrar na console com filtro de datas, agregação por dia, semana, mês, trimestre ou
  semestre e a estimativa de árvores para compensar. Mockup aprovado no Penpot ("axon mockup", páginas Console — claro
  e Console — escuro, boards "Meio ambiente…" e "Uso e custo — com emissões") em 2026-11-03.

## Contexto

O `ModelCall` da 009 já traz o que uma estimativa precisa: provider, modelo, tokens de saída e duração, emitido pela 006
a cada chamada. O destino de uso projeta esses eventos em `observability.model_calls`, num buffer esvaziado a cada 2 s
fora do caminho da requisição (ADR-034).

O EcoLogits 0.11.3 (2026-10-14; Python 3.10–3.14; dependências `pydantic`, `wrapt` e `packaging`) estima, por chamada,
energia (kWh), aquecimento global (GWP, kgCO₂eq), recursos abióticos (ADPe, kgSbeq), energia primária (PE, MJ) e água
(WCF, L), com as fases de uso e de fabricação (esta só para GWP, ADPe e PE). A função sem wrapper é
`ecologits.tracers.utils.llm_impacts(provider, model_name, output_token_count, request_latency, electricity_mix_zone)`,
que devolve valores com mínimo e máximo (`RangeValue`), avisos (`warnings`) e erros (`errors`: modelo ou zona não
registrados). A base de modelos tem 351 entradas em seis provedores — `openai`, `anthropic`, `mistralai`,
`google_genai`, `cohere` e `huggingface_hub` —, e o datacenter de cada provedor (zona elétrica, PUE e WUE) vem de
`PROVIDER_CONFIG_MAP`. **Não há OpenRouter**, e os modelos chegam aqui com nomes do OpenRouter
(`openrouter` + `z-ai/glm-5.3-flash`, `openai/gpt-4.1-mini`) ou locais (`ollama` + `qwen3:1.7b`).

O tracer do LiteLLM no EcoLogits resolve nomes desconhecidos por `rapidfuzz` (`token_sort_ratio`, corte 51) sobre
`provedor/modelo`. Medido em 2026-11-03 contra a base da 0.11.3, esse método liga **`z-ai/glm-5.3-flash` ao
`google_genai/gemini-2.5-flash`** (55), embora exista `mistralai/zai-glm-5-3`; é o modelo da instalação do mantenedor.

As ordens de grandeza são pequenas: o `gpt-4.1-mini` com 500 tokens de saída e 3 s dá 0,03–0,10 g CO₂e e
0,08–0,26 Wh por chamada; o `zai-glm-5-3`, cerca de 0,07 g e 1,3 Wh.

## Decisão

1. **A estimativa é da 009, atrás de uma porta.** A porta `ImpactEstimator.estimate(provider, model, output_tokens,
   latency_s)` devolve uma `ImpactEstimate` ou nada. O adapter `EcologitsEstimator` (`observability/adapters/`) é o
   único lugar que importa `ecologits` e `rapidfuzz` (import-linter). A 006 não muda: o `ModelCall` já basta.
2. **Estima-se no esvaziamento do buffer de uso**, antes de gravar o lote, fora do caminho da requisição. Uma
   estimativa que falha é contada e a linha grava sem impacto; nada derruba o lote. Chamada com falha ou sem tokens de
   saída não é estimada. As chamadas antigas, que já têm tokens e duração, são estimadas por um comando de
   preenchimento (`axon usage impact-backfill`), que só preenche linhas sem estimativa.
3. **Resolução do modelo, automática e sem cadastro** (decisão do mantenedor). A regra é pura, no domínio da 009, sobre
   a lista de modelos que o adapter fornece. A consulta é o nome do modelo como o Axon o conhece (o `model` do
   `ModelCall`, com o prefixo do fornecedor quando há):
   - **normalização:** minúsculas; sem o sufixo `:<tag>`; `.`, `_`, `:` e espaços viram `-`;
   - **exato:** o nome normalizado, ou o prefixo do fornecedor sem hífens unido ao nome (`z-ai/glm-5.3` →
     `glm-5-3` e `zai-glm-5-3`), igual ao nome normalizado de um modelo da base → `exact`. Com mais de um provedor
     para o mesmo nome, vence o do prefixo (`openai/`→`openai`, `anthropic/`→`anthropic`, `google/`→`google_genai`,
     `mistralai/`→`mistralai`, `cohere/`→`cohere`) e, sem prefixo, a ordem fixa da lista;
   - **aproximado:** senão, o candidato de maior similaridade (`rapidfuzz.fuzz.ratio` sobre os nomes normalizados)
     com nota ≥ 75 **e** com a família da consulta — o primeiro termo alfabético do nome, sem o fornecedor (`glm`,
     `llama`, `gpt`) — presente no nome do candidato → `approximate`;
   - **sem par:** senão, a chamada fica sem estimativa.

   A resolução é guardada num cache por (provider, model). Os dados do datacenter são os do provedor do EcoLogits do
   modelo encontrado. `AXON_IMPACT_ZONE` (ISO alpha-3) substitui a zona elétrica em todas as estimativas.
4. **Grava-se na linha da chamada, com a impressão digital.** A migração `005` acrescenta a `observability.model_calls`:
   o modelo do EcoLogits usado, o casamento (`exact`/`approximate`), a zona, a versão do EcoLogits, os avisos e mínimo e
   máximo de energia, GWP, ADPe, PE e WCF, e de GWP, ADPe e PE por fase. A retenção é a do uso
   (`AXON_USAGE_RETENTION_DAYS`). Totais somam mínimos e máximos; o valor exibido é a média dos dois.
5. **Seam Impact Report (009 → 008).** Para um período, fuso, grão (`day`, `week` — ISO, começando na segunda —,
   `month`, `quarter`, `semester` — janeiro e julho), agrupamento (modelo ou Assistant) e origem, devolve os baldes, os
   totais, o período anterior de mesmo tamanho, as linhas por modelo ou Assistant, a cobertura (chamadas estimadas,
   aproximadas e sem estimativa), as respostas (requisições distintas), os tokens de saída e as árvores para compensar
   (GWP médio ÷ `AXON_IMPACT_TREE_KG_CO2E`, padrão 140 kg CO₂e por árvore da Mata Atlântica em 20 anos — Revista DAE,
   Programa Plante Árvore). O grão `day` vai até 366 dias; os demais, até a retenção (o intervalo é recortado, com
   aviso).
6. **Exposição.** `GET /admin/v1/impact` na superfície de administração (008), com os números como texto decimal; a
   página Meio ambiente e a célula Emissões de Uso e custo na console (013), conforme o mockup aprovado. Verde, âmbar e
   vermelho continuam só como estado (DESIGN.md): nada de "verde ecológico".
7. **Montagem (011).** `AXON_IMPACT_ENABLED` (padrão `true`; `false` não monta o estimador e o relatório diz que está
   desligado), `AXON_IMPACT_ZONE` (conferida no boot contra os mixes do EcoLogits) e `AXON_IMPACT_TREE_KG_CO2E`. O
   estimador real entra nos três perfis (é determinístico e não usa rede). A saúde ganha o item informativo `impact`,
   com a versão e a cobertura das últimas 24 h.

## Alternativas rejeitadas

*Estimar na 006, na hora da chamada.* Põe uma dependência e trabalho de CPU no caminho da requisição e espalha a regra
por dois módulos; o `ModelCall` já leva tudo à 009.

*Usar os wrappers ou tracers do EcoLogits.* Eles instrumentam SDKs de provedor (inclusive por `wrapt`), não conhecem o
OpenRouter e duplicariam o que o trace já observa.

*Casar nomes como o tracer do LiteLLM (`token_sort_ratio`, corte 51, sobre `provedor/modelo`).* Liga o GLM ao Gemini.
Um modelo errado com aparência de exato é pior que "sem estimativa".

*Cadastro manual de modelos.* Trabalho que o mantenedor não quer; a resolução automática marca o aproximado e conta o
sem par na cobertura.

*Estimar na consulta.* Torna o relatório lento e faz o passado mudar quando o EcoLogits muda; gravando a versão, cada
número continua reproduzível.

*Gravar só a média.* Perde a incerteza, que é parte do resultado do EcoLogits.

## Consequências

- O core ganha `ecologits>=0.11.3,<0.12` e `rapidfuzz>=3.12,<4`. O EcoLogits registra avisos por `logger.warning_once`;
  o adapter os silencia e os guarda na linha.
- Uma versão nova do EcoLogits só vale para as chamadas novas; o preenchimento não reescreve linhas já estimadas.
- No OpenRouter, a zona, o PUE e o WUE são os do provedor do modelo encontrado (o GLM sai com os da Mistral, na Suécia),
  não os do datacenter que de fato atendeu. É estimativa, e a nota de método da console diz isso.
- Os valores por chamada são de miligramas a gramas: a console formata com prefixo (`mg`/`g`/`kg CO₂e`, `Wh`/`kWh`,
  `mL`/`L`), e árvores abaixo de 0,01 aparecem como "menos de 0,01".
- "Por conversa" fica fora: o Axon não recebe um id de conversa confiável do Open WebUI. A unidade é a **resposta** (a
  requisição do usuário, que pode ter várias chamadas no `agentic`).
