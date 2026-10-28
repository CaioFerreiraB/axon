# ADR-048 — No scouting, cada documento vira uma árvore de unidades tipadas, e a pergunta de enumeração é respondida pela estrutura

- **Status:** Aceita · 2026-10-27 (eixos, blocos, taxonomia e perfis validados pelo mantenedor)
- **Specs afetadas:** [101-scouting-pack](../../specs/101-scouting-pack/spec.md) (derivação: pedido de enumeração;
  prompt), [102-scouting-corpus-ingestion](../../specs/102-scouting-corpus-ingestion/spec.md) (árvore, perfis, fontes
  da estrutura, `shape`, ramos por unidade; seam *Índice do scouting*),
  [103-scouting-retrieval](../../specs/103-scouting-retrieval/spec.md) (rota de enumeração, trechos repetidos,
  contexto do pai), [105-scouting-evaluation](../../specs/105-scouting-evaluation/spec.md) (`fact_recall` por grupo,
  itens de enumeração)
- **Origem:** teste do mantenedor no ambiente de dev em 2026-10-27 ("quais são as especialidades do ramo pioneiro?",
  duas vezes sem a lista) e a linha de base do acervo (105 R22), em que `especialidades-pioneiro` tem `fact_recall`
  0,25 e `orgaos-nacionais`, 0,33

## Contexto

A lista das 32 especialidades dos ramos Sênior e Pioneiro está inteira num trecho
(`guia-especialidades-insignias-senior-pioneiro-1.2#s14@p20`) e no sumário do guia (p. 6–9). Nenhum dos dois chegou ao
modelo. Para a pergunta, o trecho da lista ficou em 86º no denso (cosseno 0,887; o 20º, 0,896) e em 142º no BM25. O
sumário nem existe no índice, porque a limpeza descarta página de índice. O `list_documents` (ADR-047) não entra
porque "especialidades" não é espécie de documento, e não deveria entrar, porque a pergunta pede itens de dentro de um
documento. Três das 20 vagas foram para o mesmo texto ("Etapas do projeto", repetido em cada insígnia).

O padrão não é das especialidades. O Art. 12 do Estatuto ("São órgãos Nacionais: I – … VI – …") é uma lista e fica em
92º no denso e 35º no BM25 para "quais são os órgãos nacionais da UEB?". Uma lista tem pouco texto corrido, e os
trechos que explicam o assunto repetem as palavras da pergunta. Ela perde para eles nas duas buscas, por construção.

Medido sem reindexar (scripts no relatório da conversa de 2026-10-27):

| Experimento | Resultado |
|---|---|
| Trecho de sumário concorrendo na busca normal | 200º a 800º — a estrutura perde da prosa como a lista |
| Busca só entre os sumários (um por documento, 277 no filtro) | o documento certo em 1º a 4º |
| Busca só entre os trechos com forma de lista (~160) | a lista das especialidades em 1º ou 2º; o Art. 12 em 1º |

A estrutura que falta já está, em boa parte, nos PDFs e na ingestão:

- O POR já é cortado por regra (197) e o Estatuto e as resoluções por artigo (`structure.py`, `UNIT_BY_TYPE`), mas
  regulamentos, regimentos e resoluções regionais de SP estão no catálogo como `manual` e são cortados em janelas
  (o Regulamento da RNJL tem 130 artigos; o Regional de SP, 49).
- No guia Sênior/Pioneiro, cada especialidade já é um capítulo da `estrutural-v3` com seis filhos (apresentação,
  sugestão de temas, Conhecer, Fazer, Compartilhar, checklist), mas só como rótulo de texto.
- O eixo de cada especialidade, o grupo de insígnias com o ramo e o eixo de cada bloco dos guias de progressão estão
  no **rodapé corrido** ("24 Habilidades para a Vida", "Insígnias de Interesse Especial – Ramo Pioneiro"), que a
  limpeza descarta. Os títulos de eixo das páginas de abertura são imagem.
- 33 documentos têm página de sumário e 62 têm bookmarks (os manuais do escotista, 39 a 64 cada).
- O catálogo põe "documentos de vários ramos" sem ramo, que vale como geral: as especialidades do Sênior/Pioneiro
  entram numa pergunta sobre o Lobinho.

## Decisão

1. **A 102 monta uma árvore por documento.** Cada nó tem id, tipo de unidade, título, páginas e filhos; cada trecho
   guarda o caminho até a raiz. A janela (250–450 tokens) continua sendo o tamanho do que vai para a busca: a unidade
   maior que uma janela vira filhos aninhados, e a menor fica num trecho só. O rótulo do trecho traz o tipo e o caminho
   ("Guia de Especialidades… · Eixo: Saúde e Bem-estar · Especialidade: Gastronomia · Fazer").
2. **O acervo tem uma taxonomia, e a pasta é a entrada dela.** `corpus/taxonomia.yaml` traz o mapeamento semântico do
   mantenedor (2026-10-27: categoria, subcategoria, nível e tipo) e as linhas inferidas pelo mesmo padrão para o que o
   mapeamento não cobre, marcadas como tal (ofícios da Comissão Fiscal e da Diretoria Regional, manifestações do CAN e
   as subcategorias da Rede de Jovens Líderes). Cada entrada é uma pasta `<categoria>/<subcategoria>/<nível>/`; o
   documento de uma região fica numa subpasta com o nome dela, e a cópia OCR repete o caminho sob `ocr/`. O corpus foi
   reorganizado assim: todo original mora na pasta da sua entrada, e `corpus.yaml`, `fontes.yaml` e o `source_file` do
   artefato acompanharam. O **tipo semântico** (17 valores: ata, resolução, regulamento, política, parecer, edital…) é
   mais fino que o `type` do catálogo, que o contrato limita a seis, e vai para o registro do documento no índice com a
   categoria e o nível.
3. **A forma de cada documento é declarada em `corpus/estrutura.yaml`: o tipo semântico dá o perfil padrão
   (`profile_by_type`), e só o documento de forma própria tem regra.** O `type` do catálogo não serve: o `guia` reúne
   documentos de formas diferentes, e o `manual` reúne atas, políticas e regulamentos. O arquivo tem tipos de unidade
   (com o plural que a pergunta usa), um vocabulário compartilhado (os 4 eixos e os 18 blocos, conferidos no rodapé dos
   4 guias de progressão e validados pelo mantenedor), perfis (como montar a árvore) e as exceções em ordem, por pasta
   ou por documento. Os perfis são `regras`, `artigos`, `secoes_numeradas`, `capitulos`, `progressao`,
   `especialidades`, `ata`, `relatorio`, `comunicado`, `apresentacao` e `perguntas`. A ingestão recusa documento fora de
   uma pasta da taxonomia ou de tipo sem perfil. A declaração de unidade com faixa de páginas só existe onde o texto não
   marca a estrutura (os dois guias de especialidades).
4. **Fontes do esqueleto, em ordem de autoridade:** marcadores normativos (Art., Regra, §, Título/Capítulo/Seção),
   sumário do PDF, bookmarks, rodapé corrido e a hierarquia de títulos. O sumário e o rodapé deixam de ser descartados:
   viram estrutura e continuam fora do texto do trecho. O detector de sumário passa a aceitar tracejado além do
   pontilhado.
5. **A unidade pode ter ramos.** `branches` no documento ou no grupo (o guia Sênior/Pioneiro → `senior`, `pioneiro`;
   as insígnias do Ramo Pioneiro → `pioneiro`). O filtro de ramo admite o trecho cujos ramos contêm o pedido; sem ramos,
   continua geral.
6. **A 102 marca a forma do trecho:** `shape: prose | list`, pela contagem de marcadores (•, incisos, alíneas,
   numeração) e pelo tamanho dos itens. O sumário de cada documento é uma visão da árvore, servida pelo seam, e não um
   trecho a mais na busca normal.
7. **O seam *Índice do scouting* muda:** `IndexedChunk` ganha `path`, `unit_kind`, `shape` e `branches`; o índice
   ganha `units(kind, filters)` (as unidades de um tipo que o filtro admite, com título, página e caminho) e
   `outline(doc_key)`; `IndexFilters` ganha `shape`. O artefato muda de formato (`estrutural-v4`) e é reindexado.
8. **A 101 publica `enumeration`** quando a pergunta tem marcador de lista ("quais", "liste", "existem"…) e um plural,
   em `retrieval_filters`, com o tipo de unidade quando o plural é de um tipo declarado. É a generalização do `_catalog`
   do ADR-047 e continua sendo uma função pura. O vocabulário vem dos tipos do `estrutura.yaml`, e não de uma lista no
   léxico.
9. **A 103 responde a enumeração pela estrutura, na tool `list_units`.** Com tipo declarado, a lista exata das unidades
   daquele tipo (uma ficha por documento, com título e página de cada unidade, à frente dos trechos, depois das fichas
   do acervo). Sem tipo, uma busca
   restrita aos trechos `shape=list` e aos sumários, com cota pequena (2 sumários e 3 listas), à frente. O total de
   trechos não muda: o que entra toma a cauda.
10. **A 103 junta trechos de texto idêntico** em qualquer pergunta: fica o primeiro, e os títulos onde ele se repete vão
   nos metadados (910 trechos, 6,5% do índice, estão em grupos repetidos).
11. **A entrega leva o contexto do pai.** O trecho vai com o caminho; dois ou mais irmãos da mesma unidade são
    entregues juntos, em ordem, até um teto de tokens por unidade.
12. **O prompt da 101** diz que a lista de unidades e o sumário trazem nomes e páginas, não o conteúdo, e manda
    enumerar por inteiro a partir deles, citando.
13. **A 105 reporta o `fact_recall` por grupo**, põe os fatos da lista nos itens de especialidades da regressão e ganha
    itens de enumeração de outros documentos, metade de controle.
14. **O core não muda.** A rota de enumeração é do pack, como a do ADR-047.

## Alternativas rejeitadas

- **Cortar por tipo de documento do catálogo.** O tipo é grosso demais: no `guia`, o capítulo é especialidade num
  documento e bloco noutro; no `manual`, há regulamento com 130 artigos e ata.
- **Um trecho por capítulo.** O e5-small corta em 512 tokens, um capítulo de manual tem de 10 a 40 páginas e uma
  especialidade tem cerca de 3 mil tokens; a unidade é nó, e o que se busca e entrega continua do tamanho da janela.
- **Indexar o sumário como trecho comum.** Medido: fica entre o 200º e o 800º.
- **Mais trechos entregues.** O trecho da lista estava em 86º e 142º.
- **Cross-encoder.** Medido sem ganho na 103 R14, e aqui o alvo nem estava entre os candidatos.
- **Reescrever a pergunta com o modelo.** Custa uma chamada a mais, e o ganho depende da palavra exata ("lista das" põe
  o trecho em 16º, "quais são as" o deixa em 86º).
- **Reforço no léxico para "especialidades" ou para o guia.** Resolve uma pergunta e nenhuma outra.

## Consequências

- O corpus foi reorganizado pela taxonomia (15 pastas de categoria, por órgão ou tema, e a `ocr/`), sem mudar conteúdo: o artefato só
  teve o `source_file` trocado, e a suíte do pack (o artefato contra o catálogo) passa.
- 17 documentos que hoje vão em janelas passam a ser cortados por artigo: 10 resoluções regionais de SP, 5 regulamentos
  e 2 regimentos (o perfil `artigos` tem 281 documentos; hoje são 264, o Estatuto e os do tipo `resolucao`).
- Os dois guias de especialidades ficam com eixo, especialidade, grupo de insígnias e ramo explícitos: 32 + 16 no
  Sênior/Pioneiro, 174 + 18 no Lobinho/Escoteiro.
- O `estrutura.yaml` é curadoria: cada versão nova de um guia de especialidades pode mudar as faixas de páginas. A
  ingestão confere as faixas contra o sumário e recusa a que não casa.
- A mudança de forma dos trechos mexe em todas as métricas da 105 (como na 102 R32). Cada passo é medido antes e
  depois no acervo e na regressão, com itens de controle de documentos que nenhuma declaração tocou.
- Tabela cujo título é imagem continua sem o título no texto. O rodapé recupera o eixo dos guias, mas não o de uma
  tabela solta.
- O follow-up que depende da conversa ("e em 2026, não tem nenhum parecer?") continua buscando só pela última
  mensagem. É do core e fica fora deste ADR.

## Ordem

1. 102: árvore genérica, sumário e rodapé como fontes, `shape`, `estrutura.yaml` lido e validado, trechos repetidos
   marcados, artefato `estrutural-v4`.
2. 101 + 103: `enumeration`, `units`/`outline`, a rota de enumeração e a junção dos repetidos.
3. 103: contexto do pai na entrega.
4. 101: prompt.
5. 105: métricas por grupo e itens novos, medidos a cada passo.
