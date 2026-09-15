# ADR-013 — Seams transversais: Trace Sink e tempo de referência

- **Status:** Aceita · 2026-09-14 — depende do [ADR-012](ADR-012-estilo-arquitetural-hexagonal.md)
- **Specs afetadas:** [001](../../specs/001-core-contracts/spec.md), [004](../../specs/004-core-capability-gateway/spec.md),
  [005](../../specs/005-core-execution-engine/spec.md), [006](../../specs/006-core-llm-providers/spec.md),
  [009](../../specs/009-core-observability-evaluation/spec.md), [101](../../specs/101-scouting-pack/spec.md),
  [103](../../specs/103-scouting-retrieval/spec.md), [105](../../specs/105-scouting-evaluation/spec.md); 003 e 008 no ponto
  em aberto
- **Origem:** revisão da SDD sob a ótica do estilo arquitetural — [relatório](../relatorio-estilo-arquitetural.md), lacunas
  G3 e G4

## Contexto

1. **Trace.** A 004 (FR-014), a 005 (FR-016) e a 006 (FR-008) exigem "reportar ao trace", e a 009 declara consumir
   "dados de chamada do Tool Gateway — 004 e do Model Router — 006". Nenhum seam diz como: 004 e 006 não conhecem a 009, e
   a 009 não tem de onde puxar os dados. O grafo de dependências só mostra `009 → 005`, mas a 005 também escreve no trace,
   o que é um ciclo não declarado. O backend é decidido no plano da 009 (spec l.121), mas o mecanismo de emissão é seam,
   não detalhe de plano.
2. **Tempo.** A vigência do scouting usa "hoje" por default (101 US2; 103 l.40). Se cada pack lê o relógio do sistema:
   - a preparação de contexto e os validators da mesma execução podem usar datas diferentes na virada do dia;
   - o conjunto dourado (105) com perguntas sobre "o que está vigente" deixa de ser reproduzível: quando um documento é
     revogado, o mesmo caso passa hoje e falha amanhã, sem mudança de código;
   - o teste do pack passa a depender do relógio.

## Decisão

1. **Trace Sink** é um seam novo, com dono 009, consumido por 004, 005 e 006 e por qualquer módulo que emita dados de
   trace. É uma porta de emissão: os módulos registram spans e eventos com o identificador da requisição, e a 009 fornece
   os adapters (backends). Os emissores não conhecem o backend nem o harness.
   - Candidata para o plano da 009: usar a API do OpenTelemetry como porta (só a API). SDK e exporter são adapters,
     montados pela composition root. Se o plano escolher outra forma, a semântica do seam se mantém.
2. **Tempo de referência.** O core tem uma porta `Clock`. Cada execução fixa um instante de referência no início, e a Turn
   View (001) ganha o campo `reference_time`, o mesmo para todos os hooks daquela execução. Packs usam esse valor em vez
   do relógio do sistema. O campo entra na versão 0.1.0 dos contratos, antes da tag, sem custo de versão.
3. **Ponto em aberto** (`NEEDS CLARIFICATION` para 008 e 003): como o harness (009/105) fixa o `reference_time` de um caso
   do conjunto dourado. As opções são um campo de requisição aceito só na superfície privada ou uma execução em processo
   pela porta `ExecutionEngine`, com `Clock` fixo. Fixar a data não amplia capacidade e, por isso, não viola "a
   requisição só restringe", mas a regra precisa estar escrita.

## Alternativas rejeitadas

*Trace por assinatura (a 009 observa 004, 005 e 006).* Cada módulo teria de expor um seam de observação, e a 009 teria de
conhecer todos. A dependência fica invertida para o lado errado e cresce a cada módulo novo.

*Trace só pelos `ExecutionEvent` do motor.* Cobre a 005, mas não a latência de tool (004) nem os tokens por papel (006),
a menos que o motor passe a conhecer detalhes de 004 e 006.

*Um relógio próprio em cada pack.* É mais simples, mas não garante a mesma data entre hooks, e o harness só fixaria a data
entrando no interior do pack.

## Consequências

- O grafo fica honesto: 004, 005 e 006 → 009 (Trace Sink) e 009 → 005 (Execution Engine). Com a regra "só importar o
  `api.py` de outro módulo" do ADR-012, não há ciclo de import
- O conjunto dourado ganha casos datados e reproduzíveis
- Packs ficam testáveis com data fixa, via fixture de Turn View
- Custo: um campo a mais na Turn View e uma porta `Clock` no core
- Custo: todo módulo emissor passa a depender do seam da 009 (só da porta)

## Se for aceito

Emendar:

- 001: `reference_time` na Turn View, com o FR correspondente;
- 009: seam Trace Sink em Module Boundary, na linha "Expõe";
- 004, 005 e 006: Module Boundary, na linha "Consome";
- 101 e 103: usar `reference_time` no default de vigência;
- 105: casos com data de referência;
- `specs/README.md`: tabela de seams e grafo.
