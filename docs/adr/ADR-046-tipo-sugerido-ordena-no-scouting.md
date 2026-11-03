# ADR-046 — No scouting, o tipo de documento sugerido pelo tema ordena; só o citado filtra

- **Status:** Aceita · 2026-10-27
- **Specs afetadas:** [101-scouting-pack](../../specs/101-scouting-pack/spec.md) (léxico, derivação e o contrato
  `retrieval_filters`), [103-scouting-retrieval](../../specs/103-scouting-retrieval/spec.md) (a marca de tipo da
  ordem), [105-scouting-evaluation](../../specs/105-scouting-evaluation/spec.md) (o campo novo em `extra.context`)
- **Origem:** teste do mantenedor no ambiente de dev em 2026-10-27 e o relatório "RAG do scouting por dentro": 4 de 17
  perguntas sem nenhum trecho, todas sobre especialidades

## Contexto

A derivação da 101 publica `document_types` nos `retrieval_filters`, e a 103 o aplica como filtro obrigatório do
índice. Esse campo juntava duas coisas diferentes: o tipo que a pergunta **cita** ("segundo o estatuto") e o tipo que um
**tema** costuma ter no léxico ("especialidades" → programa educativo; "diretoria" → POR, estatuto e resolução).

Com o corpus de 593 documentos, o segundo uso esconde documentos. Medido no índice de 27/10: o tema "especialidades"
filtrava pelo tipo `programa_educativo`, que nenhum documento tem (0 de 15.504 trechos); nenhum tema incluía o tipo
`guia`, então os 6 guias dos jovens — de especialidades, do Desafio Sênior, do Horizonte Pioneiro… — ficavam fora de
toda pergunta de programa; "diretoria" deixava 18% do corpus, sem as atas; e citar "programa educativo" filtrava tudo,
porque o léxico o tratava como nome de tipo.

## Decisão

1. **Só o tipo citado filtra.** `document_types` nos `retrieval_filters` passa a trazer apenas os tipos que a pergunta
   nomeia.
2. **O tipo sugerido ordena.** Os tipos que os temas e os sinais sugerem vão num campo novo, `suggested_types`, só
   quando a pergunta não cita tipo. A 103 não filtra por ele: ele liga a marca de tipo que desempata a ordem da fusão
   (103 FR-005), como o tipo citado já fazia.
3. **O léxico só sugere e só reconhece tipos que existem no catálogo.** `programa_educativo` sai das citações
   (nomeia um assunto); temas e sinais sugerem `manual`, `guia`, `por`, `resolucao` ou `estatuto`; "guia de" passa a
   citar o tipo `guia`. O tipo `programa_educativo` continua no esquema do índice (102), sem uso.
4. **Nada muda no core nem no contrato 001**: `retrieval_filters` é opaco para o core.

## Consequências

- Nenhuma pergunta perde documento por causa do tema. Medido no conjunto de regressão da 105: as três perguntas de
  especialidades vão de 0 a 1 em `fact_recall`, e o conjunto, de 0,7634 a 0,8705, sem regressão na semente.
- A marca de tipo só desempata: com a fusão dando scores raramente iguais, o efeito do tipo sugerido na ordem é
  pequeno. Se a medição pedir preferência mais forte, ela entra como peso, com outro ADR.
- `extra.context` da 105 aceita `suggested_types`.
- Os tipos do catálogo ainda não descrevem o acervo (atas e políticas como `manual`). Uma taxonomia nova é decisão à
  parte, com o curador.

## Alternativas

- **Corrigir só o léxico** (tipos que existem, com `guia`): mantém o filtro duro por palpite; o próximo tema mal mapeado
  esconde documentos de novo.
- **Tirar os tipos sugeridos de vez**: perde o desempate, que ajuda quando a fusão empata.
- **Filtrar pelo sugerido e, sem resultado, repetir sem filtro**: duas buscas e o mesmo problema quando o filtro deixa
  poucos, não zero.
