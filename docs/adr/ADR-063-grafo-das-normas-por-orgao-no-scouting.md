# ADR-063 — No scouting, a pergunta sobre um órgão recebe as seções das normas que o disciplinam, pelo grafo das normas

- **Status:** Aceita · 2026-11-10. O mantenedor aprovou o desenho do grafo (`corpus/Organização Escoteira.revisado.json`)
  e disse para começar a Fase 2 ("pode seguir").
- **Specs afetadas:**
  - [101-scouting-pack](../../specs/101-scouting-pack/spec.md): `organs` na derivação.
  - [102-scouting-corpus-ingestion](../../specs/102-scouting-corpus-ingestion/spec.md): o catálogo de órgãos, o grafo
    e o seam `NormGraph`.
  - [103-scouting-retrieval](../../specs/103-scouting-retrieval/spec.md): a busca guiada pelo grafo.
- **Origem:** a pergunta de 08/11 ("um vice regional, depois de duas gestões seguidas, pode se candidatar a
  presidente?") não achava o Estatuto Art. 27 §3º: 448º no denso, 1.273º no BM25. A pergunta descreve um caso, e a norma
  fala em abstrato. O [relatório](../revisao-rag-scouting-2026-11-diretoria-regional.md) propôs um GraphRAG de esquema
  fixo; este ADR faz a parte que leva da pergunta ao artigo.

## Contexto

As normas de organização têm uma seção por órgão. O Estatuto tem "Seção III – Da Diretoria Regional"; o Regulamento da
Região SP, "Capítulo III – Da Diretoria Regional". As duas disciplinam o mesmo tipo de órgão em níveis diferentes, e a
regra do mantenedor pede as normas do nível da pergunta e de todos os de cima.

## Decisão

1. **O catálogo de órgãos é curado** em `corpus/organizacao.yaml`: tipos de órgão e de instituição, com nome, apelidos
   e nível. As relações de governança (ELEGE, FISCALIZA…), que ainda não são usadas na busca, ficam ali com a fonte.
2. **A ligação `DISCIPLINA` sai por regra**, em `rag/ingestion/domain/graph.py` e `scripts/grafo.py build`, sem
   modelo:
   - nas normas vigentes (estatuto, regulamento, POR), a unidade de estrutura mais funda cujo título nomeia o órgão,
     pelo nome mais longo ("do conselho consultivo regional" é o regional);
   - o regulamento cujo título nomeia um **órgão** vale inteiro ("Regulamento Interno do Conselho de Administração
     Nacional"), porque as seções dele não repetem o nome. Instituições nunca valem pelo título do documento:
     "Escoteiros do Brasil" está em quase toda pergunta.

   Resultado: 28 seções para 21 órgãos e instituições, gravadas em `graph.jsonl` ao lado do índice, fora do manifesto.
3. **Seam *Índice do scouting***: `NormSection` e a porta `NormGraph`, com `organ_terms()` e `sections(organs)`. O
   adapter é o `ArtifactGraph`.
4. **Derivação (101).** O pack injeta os nomes dos órgãos no léxico (`organ_terms`, como `unit_kinds`), e a derivação
   publica `organs`: os órgãos nomeados, pelo nome mais longo, na ordem da menção. O campo fica vazio na síntese, na
   lista, na enumeração e na pergunta com período. Ali o órgão não pede a regra.
5. **Busca (103).** Com `organs`, o `ScoutingRetriever` pede as seções ao grafo:
   - documento a documento, da norma de cima para a de baixo, até 3 documentos;
   - até 3 trechos por documento, os que mais casam com a pergunta (o BM25 do módulo `domain/terms.py`, comum com a
     ADR-062);
   - os trechos entram à frente dos da busca (`graph_rank`), sem filtro de tipo: a pergunta que cita o regulamento
     recebe também o Estatuto, como pede a hierarquia.

## Alternativas rejeitadas

- **GraphRAG com extração por LLM** de entidades e relações: o título das seções já diz qual órgão cada uma
  disciplina, e a regra é determinística e testável. A extração por LLM fica para as relações que a busca vier a usar.
- **Reescrever a consulta por modelo**: resolveria o vocabulário em geral, mas soma uma chamada por turno e muda o core.
  O grafo resolve o caso do órgão sem custo na pergunta.
- **Parágrafo e inciso na árvore antes do grafo**: medido no relatório, o §3º sozinho não muda a similaridade (0,876
  contra 0,872). A citação ao parágrafo fica para depois.

## Consequências

- **A pergunta de 08/11**: o Estatuto Art. 27 vai do 448º ao **1º lugar**, e o Regulamento SP Art. 26 fica em 4º, com
  os Arts. 28 e 29 (presidente e vice) junto.
- **Acervo**: de 0,8768 a **0,9203**. A pergunta de 08/11 (controle) e a da assembleia extraordinária foram de 0 a 1, e
  nenhum item caiu: as reuniões do CAN caíam antes de o regulamento valer inteiro.
- **Outros conjuntos**: regressão (0,9768), síntese (0,8462) e `golden` ficaram iguais.
- **Na instalação**: a cópia do índice leva `graph.jsonl`, e o instalador precisa aceitá-lo, como o `summaries.jsonl`.
- **Manutenção**: um órgão novo é uma linha no `organizacao.yaml` e um `scripts/grafo.py build`. Uma ingestão nova pede
  o build de novo.
