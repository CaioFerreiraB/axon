# ADR-047 — No scouting, a pergunta que pede uma lista de documentos recebe uma ficha por documento do acervo

- **Status:** Aceita · 2026-10-27
- **Specs afetadas:** [101-scouting-pack](../../specs/101-scouting-pack/spec.md) (léxico, derivação, contrato
  `retrieval_filters` e prompt), [102-scouting-ingestion-index](../../specs/102-scouting-ingestion-index/spec.md) (seam
  novo *Catálogo de documentos*), [103-scouting-retrieval](../../specs/103-scouting-retrieval/spec.md) (tool
  `list_documents` e a ordem das fichas), [105-scouting-evaluation](../../specs/105-scouting-evaluation/spec.md) (campo
  `catalog` em `extra.context` e o texto das fichas no `fact_recall`)
- **Origem:** teste do mantenedor no ambiente de dev em 2026-10-27 ("Quais são as políticas nacionais que existem?"
  devolveu uma lista enxuta) e a medição da 105 R20: com 20 ou 30 trechos, as listas ficam em 0,62–0,75 de
  `fact_recall`

## Contexto

A recuperação do scouting entrega trechos: pedaços de 250 a 450 tokens, os mais parecidos com a pergunta. Uma pergunta
que pede uma enumeração de documentos ("quais são as políticas nacionais", "que guias existem") não se responde bem por
trechos. Cada política aparece em dezenas de trechos, e os mais parecidos com a pergunta se concentram em poucas delas.
Subir o número de trechos ajuda pouco: com 30 trechos, a lista das 8 políticas nacionais ainda perde duas. A informação
que responde, o título e a vigência de cada documento, já está no catálogo da ingestão (`corpus.yaml`), registrado no
índice documento a documento, mas nenhum caminho a entregava.

## Decisão

1. **A 101 reconhece o pedido de lista.** A derivação publica `catalog: {kind, terms}` em `retrieval_filters` quando a
   pergunta tem um marcador de enumeração ("quais", "liste", "existem"…) e o plural de uma espécie de documento do léxico
   (políticas, manuais, guias, resoluções, atas, regulamentos, relatórios, documentos). `kind` é a palavra do título no
   singular, e `documento` vale para qualquer título. `terms` são as palavras da pergunta que qualificam a lista, sem as
   de ligação e sem as que todo título repete. `documento` sem qualificador não pede nada.
2. **A 102 expõe o seam *Catálogo de documentos*.** `DocumentCatalog.catalog(filters)` devolve uma `CatalogEntry` por
   documento que os `IndexFilters` admitem, com a mesma semântica de vigência, ramo e tipo da busca e o link do original.
   O artefato em memória, a memória e o Qdrant o implementam sobre o registro de documento que já gravam.
3. **A 103 ganha a tool `list_documents`.** O `CatalogRetriever` escolhe os documentos cujo título tem a espécie e a
   maior fração dos qualificadores que algum título alcança. Os escolhidos saem do mais recente ao mais antigo, uma ficha
   por documento: título, versão, vigência, abrangência, ramo e link. A seção da ficha é "ficha do acervo, N de M", e o
   número de fichas tem teto (15). Sem pedido de lista, a tool não devolve nada. Ela usa a coleção da busca, então o
   mesmo grant a libera.
4. **As fichas vêm antes dos trechos.** O `MetadataReranker` as ordena à frente de tudo, na ordem da lista; os trechos
   da busca ocupam as vagas restantes.
5. **O prompt manda listar pelas fichas**, citar cada documento e dizer quantos existem quando M passa do número de
   fichas que chegaram.
6. **Nada muda no core nem no contrato 001.** O `rag_first` já executa toda tool de recuperação do catálogo e entrega
   ao reranker do pack todos os trechos dele; `retrieval_filters` é opaco para o core.

## Consequências

- Medido no conjunto de regressão da 105 com 20 trechos: políticas de 0,625 a 1,0 e o conjunto de 0,978 a 0,991, o
  mesmo dos 30 trechos sem o catálogo; nenhuma outra pergunta muda, e a semente fica igual.
- A lista é por **título**. Sigla que o título não traz não casa: "atas do CAN" não acha as atas do Conselho de
  Administração Nacional, cujos títulos não têm a sigla. A busca por trechos continua rodando ao lado.
- Numa pergunta de lista, as fichas tomam até 15 das vagas da geração; com 20 trechos sobram ao menos 5 para o
  conteúdo.
- A ficha não tem página: o rótulo do core fica sem "p. N", e a citação da 104 também.
- A métrica de fatos da 105 refaz o texto da ficha a partir da entrada do documento (`with_cards`).
- `retrieval_filters` ganha a chave `catalog` (contrato da 101), e `extra.context` da 105 a aceita.

## Alternativas

- **Mais trechos.** 30 trechos ainda perdem duas das oito políticas e custam 37% mais tokens que 20 (105 R20).
- **Uma ficha só, com a lista inteira.** Ocupa uma vaga, mas a citação de cada documento vira a citação de um documento
  sintético, sem link nem vigência por item.
- **A lista dentro do `search_docs`.** Evita uma tool, mas mistura duas buscas com orçamentos diferentes no mesmo
  `top_k` e esconde a lista do timeline e do loop do `agentic`.
- **Busca densa sobre os títulos.** Acha títulos parecidos, não os que têm a espécie pedida; a enumeração precisa de
  casamento exato.
- **Casamento por título com sinônimos e siglas.** Fica para quando a curadoria do catálogo existir: um campo de siglas
  ou de série no `corpus.yaml` resolve melhor que um dicionário no léxico.
