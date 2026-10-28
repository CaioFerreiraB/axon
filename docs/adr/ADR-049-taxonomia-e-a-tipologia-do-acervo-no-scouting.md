# ADR-049 — No scouting, a taxonomia do acervo é a única tipologia: o `type` sai do catálogo, e tipo, órgão e abrangência vêm da pasta

- **Status:** Aceita · 2026-10-28 (pedido do mantenedor: "seguir só com os tipos da taxonomia", "filtrar por tipo na
  taxonomia", "usar mais a taxonomia"; órgão e nível escolhidos por ele entre as opções)
- **Specs afetadas:** [101-scouting-pack](../../specs/101-scouting-pack/spec.md) (léxico de tipos, órgãos e
  abrangência; fatia `retrieval_filters`), [102-scouting-corpus-ingestion](../../specs/102-scouting-corpus-ingestion/spec.md)
  (catálogo sem `type`; seam *Índice do scouting*: `document_type` como id da taxonomia, `bodies`, `scope`),
  [103-scouting-retrieval](../../specs/103-scouting-retrieval/spec.md) (filtros `bodies` e `scopes`, desempate pelo
  órgão, lista de documentos pelo tipo), [105-scouting-evaluation](../../specs/105-scouting-evaluation/spec.md)
  (`context_accuracy` com os campos novos)
- **Origem:** o relatório "Anatomia do RAG do scouting" (2026-10-28) mostrou que o mesmo PDF carrega dois tipos que não
  conversam — o `type` do `corpus.yaml` (6 valores do contrato da 102) e o `tipo` da `taxonomia.yaml` (17 valores) —, e
  que o primeiro é grosso demais para filtrar: 10.722 dos 14.706 trechos eram `manual`, inclusive atas, políticas,
  relatórios e ofícios; 10 resoluções regionais e 7 regulamentos eram `manual` no catálogo e cortados por artigo.

## Contexto

Desde o ADR-048 o perfil de corte já sai do `tipo` da taxonomia, pela pasta do arquivo. O `type` do catálogo ficou só
para o filtro de tipo da busca, a chave de conteúdo e um perfil de reserva quando não há taxonomia. Como filtro, ele
falha nos dois sentidos: "segundo o manual" admite atas e ofícios, e "segundo a resolução" não acha as 10 resoluções
regionais de São Paulo de 2016 a 2021 que o catálogo registrou como `manual`. A taxonomia diz também o órgão (a
categoria: CAN, DEN, Assembleias, Diretoria Regional…) e o nível (nacional, regional, local), que nenhuma pergunta
conseguia usar.

## Decisão

1. **O catálogo não tem mais `type`.** Entrada com o campo é recusada, nomeando o motivo. O tipo do documento é o
   `tipo` da entrada da taxonomia da pasta do arquivo, como id: sem acento nem caixa, os pontos fora e o resto unido por
   `_` (`taxonomy_id`: "P.O.R." → `por`, "Ata" → `ata`, "Planejamento Estratégico" → `planejamento_estrategico`). Os ids
   que já existiam (`por`, `resolucao`, `estatuto`, `manual`) não mudam; `guia` e `programa_educativo` deixam de
   existir — os guias são Manual na taxonomia.
2. **A taxonomia é obrigatória na ingestão.** Sem `taxonomia.yaml` e `estrutura.yaml` ao lado do catálogo, a execução
   para com um problema; o perfil de reserva pelo `type` (`default_profile`) sai.
3. **O seam *Índice do scouting* muda** (a 102 o publica, a 103 o consome, ambos no pack):
   - `IndexedChunk.document_type`, `DocumentFields.document_type` e `CatalogEntry.document_type` passam de enum fixo
     (`DocumentType`) a `str` com o id da taxonomia; o enum e `NORMATIVE_TYPES` saem.
   - Ganham `bodies` (os ids da categoria e da subcategoria) e `scope` (`mundial`, `interamericano`, `nacional`,
     `regional`, `local` — o nível da taxonomia; sem ele, o da jurisdição do catálogo, e uma região é `regional`).
   - `IndexFilters` ganha `bodies` e `scopes`, com a mesma semântica nos três adapters (Qdrant por `MatchAny`).
4. **Na pergunta (101), tipo, órgão e abrangência são termos do léxico** que publicam ids da taxonomia:
   - o tipo citado filtra (ADR-046), agora entre 13 tipos — os 4 de antes e `regulamento` (com "regimento"), `ata`,
     `politica`, `relatorio`, `planejamento_estrategico`, `parecer` ("parecer da/do", "pareceres"), `oficio`, `edital`,
     `boletim`; "recomendação", "apresentação", "posicionamento" e "manifestação" ficam de fora, palavras comuns demais;
   - o órgão (11: CAN, DEN, Assembleias pela "assembleia nacional/regional", Diretoria Regional, Conselho Consultivo,
     Comissão Fiscal, Comissão de Ética, Conselho Jovem, Velhos Lobos, Rede de Jovens Líderes, Comissão Regional
     Pioneira) e a abrangência (`nacional`, `regional` com "SP"/"São Paulo"/"paulista", `local`, `mundial`,
     `interamericano`) **filtram só junto com um tipo citado ou um pedido de lista** ("as atas da assembleia regional");
     sozinhos, o órgão vai em `suggested_bodies` e só desempata, depois do tipo sugerido. "Assembleia" sozinha não é
     órgão: a assembleia de grupo é assunto do POR.
5. **A lista de documentos (ADR-047) escolhe pelo tipo**, não pela palavra do título: a espécie pedida é o id da
   taxonomia (`documento` = qualquer tipo), e os qualificadores casam o título ou a classificação (categoria,
   subcategoria, tipo, nível, abrangência, jurisdição).

## Alternativas rejeitadas

- **Alargar o `type` do catálogo para os 17 tipos.** Duplicaria a taxonomia em 593 entradas, e as duas fontes voltariam
  a divergir na próxima pasta nova.
- **Filtrar sempre pelo órgão e pela abrangência citados.** "Como funciona o CAN?" ficaria restrita às atas e
  resoluções do CAN, perdendo o Estatuto e o POR, que dizem o que o CAN é; é a mesma razão do ADR-046 para o tipo
  sugerido.
- **Guardar só o rótulo da taxonomia e comparar normalizando na busca.** O Qdrant filtra por igualdade de payload; o
  id calculado na ingestão vale igual nos três adapters.

## Consequências

- O artefato e o Qdrant precisam de reingestão (os campos novos entram na chave de conteúdo pelo tipo); a suíte de
  conformidade cobre `bodies` e `scopes`.
- O léxico tem teste contra a `taxonomia.yaml`: todo tipo e órgão que ele publica existe numa pasta.
- Uma pasta nova na taxonomia com tipo novo não exige mudar código: o tipo vira id sozinho; só entra no léxico se uma
  pergunta precisar citá-lo.
- `context_accuracy` (105) passa a comparar `bodies`, `scopes` e `suggested_bodies` também.
