# ADR-065 — No scouting, a seção de uma política que nomeia um órgão também o disciplina

- **Status:** Aceita · 2026-11-15. O mantenedor escolheu esta opção entre três (a regra ampliada, uma aresta curada
  `SUBORDINADO_A` e as duas), depois de perguntar se o Regulamento do Fórum Regional Pioneiro de SP estava ligado à
  Política Nacional de Envolvimento Juvenil, a que ele é subordinado.
- **Specs afetadas:**
  - [106-scouting-graphrag](../../specs/106-scouting-graphrag/spec.md): a regra dos órgãos, que veio da 102 sem mudança
    (106 R2), e o catálogo `organizacao.yaml` (research R25).
- **Refina:** o item 2 do [ADR-063](ADR-063-grafo-das-normas-por-orgao-no-scouting.md) (quais tipos disciplinam
  órgãos). O resto do ADR-063 e o [ADR-064](ADR-064-grafo-de-dominio-e-consultas-no-scouting.md) não mudam.

## Contexto

A hierarquia das normas entra na busca pelo grafo de forma indireta: quando normas de níveis diferentes disciplinam o
mesmo tipo de órgão, a de cima vem primeiro (`SCOPE_ORDER`, ADR-061 e ADR-063). Não existe aresta de subordinação
entre documentos.

O ADR-063 deixou só estatuto, regulamento e POR disciplinarem órgãos ("resoluções e políticas tratam de temas"). O
ADR-064 depois deu às políticas o papel `norma`. Com isso a PNEJ ficava fora da hierarquia: a seção "4. Equipes
Regionais Pioneiras (e Fóruns Pioneiros)" e o item "4.3 Equipe Regional Pioneira (ou Comissão Regional Pioneira)" não
se ligavam à Comissão Regional Pioneira, e a pergunta sobre ela só recebia o regulamento regional (axon-scouting
0.17.1). A PNEJ chama a Comissão de "Equipe Regional Pioneira", nome que o catálogo não conhecia.

## Decisão

1. **A política disciplina órgão pela seção.** `politica` entra em `NORMATIVE_TYPES`
   (`rag/graph/domain/build/organs.py`). Vale a mesma regra das outras normas: a unidade de estrutura mais funda cujo
   título nomeia o órgão. A política nunca vale inteira pelo título, que fica só para o regulamento.
2. **Na política, só órgão; nunca instituição** (`BODIES_ONLY_TYPES`). Nela, o título que nomeia a UEB ou a OMME é
   crédito, referência ou contexto: medido, "© União dos Escoteiros do Brasil" e "Lista de referências da OMME" davam
   32 e 4 seções falsas.
3. **"Equipe(s) Regional(is) Pioneira(s)" é apelido da Comissão Regional Pioneira** em `corpus/organizacao.yaml`,
   pela própria PNEJ (4.3).

## Alternativas rejeitadas

- **Aresta curada `SUBORDINADO_A` entre documentos**: diz a subordinação de forma explícita e responderia "a que norma
  este regulamento obedece?", mas pede um tipo novo de ligação na 106 e código no retriever para trazer a norma de
  cima. A regra ampliada usa o mecanismo de hierarquia que já existe. Pode vir depois, se a pergunta aparecer.
- **As duas juntas**: o mesmo custo da aresta, sem caso de uso que a peça hoje.

## Consequências

- **A Comissão Regional Pioneira** passa a ter três seções: PNEJ §4 e §4.3 (nacional) antes do regulamento do Fórum
  (regional).
- **Outros órgãos** ganham seções de política, quase todas da Política de Governança Institucional, que descreve as
  competências deles: o CAN (+10), a DEN (+7, uma da política de crises humanitárias) e a Comissão Fiscal Nacional
  (+2). A busca continua limitada a 3 documentos e 3 trechos por documento.
- **Medida** (`scouting:fact_recall`, 20 candidatos e 20 trechos): regressão 0,9696, acervo 0,9549, síntese 0,9487 e
  programa-adultos 0,9091, nenhum item mudou. Seis perguntas sobre o Fórum e a Comissão, fora do git: 0,83 → 1,0. A do
  mandato de um ano (PNEJ 4.3.2) só chega com a regra nova.
- **Versão:** axon-scouting 0.17.2. O índice não muda; só o `graph.jsonl`, que a instalação copia junto.
