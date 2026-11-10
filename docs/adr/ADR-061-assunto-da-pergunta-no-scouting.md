# ADR-061 — No scouting, o órgão que é assunto da pergunta não filtra, e a pergunta de seguimento herda o assunto da anterior (refina o item 4 do 049)

- **Status:** Aceita · 2026-11-09. O mantenedor liberou as duas correções ("pode seguir") depois do relatório
  [Diretoria Regional](../revisao-rag-scouting-2026-11-diretoria-regional.md).
- **Specs afetadas:**
  - [101-scouting-pack](../../specs/101-scouting-pack/spec.md): derivação, fatia `retrieval_filters` e prompt.
  - [103-scouting-retrieval](../../specs/103-scouting-retrieval/spec.md): chave `anchor` e recuo sem órgão e
    abrangência.
- **Origem:** em 08/11, em produção, uma conversa sobre a Diretoria Regional precisou de dois documentos, o Estatuto da
  UEB e o Regulamento da Região SP. A reprodução local achou dois defeitos, além da causa principal daquele caso (a
  distância de vocabulário, que fica para o grafo e para a reescrita da consulta):
  - "O que o regulamento regional diz sobre a diretoria regional?" devolvia **0 trechos**;
  - a pergunta de seguimento ("e no estatuto nacional?", "qual o prazo de gestão?") perdia o assunto da anterior.

## Contexto

O item 4 do ADR-049 faz o órgão e a abrangência citados filtrarem sempre que a pergunta cita um tipo ou pede uma lista.
Mas o órgão de um documento (`bodies`) é a **pasta da taxonomia** em que ele está guardado, isto é, quem o emite:
- o Regulamento SP está em `gestao_institucional_e_governanca`, não em `diretoria_regional`;
- o Estatuto é `nacional`, e "diretoria **regional**" ainda virava `scopes: [regional]`.

Quando o órgão é o **assunto** ("o regulamento sobre a diretoria regional"), o filtro exclui exatamente os documentos
que tratam dele.

O `rag_first` busca só com a última mensagem, e a derivação só via `view.question`. A Turn View já traz as mensagens
anteriores (`messages`), mas o pack não as usava. Medido com o artefato de 0.8.1 e o e5: o Estatuto Art. 27 não aparece
entre os 20 trechos de "qual o prazo de gestão?" nem de "e no estatuto nacional?". Com a pergunta anterior junto, ele
fica em 2º e 4º.

## Decisão

1. **O órgão só filtra quando é o emissor.** Emissor é o órgão nomeado logo depois do tipo citado ou do plural da lista,
   ligado por da/do/das/dos/de, com no máximo uma palavra de complemento antes da ligação:
   - exemplos: "resoluções **da** diretoria regional", "atas **da** assembleia regional", "regimento interno **do**
     conselho jovem", "regulamento regional **da** …";
   - um termo de tipo que já traz a ligação também conta ("parecer da comissão fiscal");
   - o órgão que não é emissor vai em `suggested_bodies` e só desempata, também quando há tipo citado.

   Os termos ficam no léxico (`issuer_links`, `issuer_fillers`).
2. **O nome do órgão-assunto não é abrangência.** A abrangência é casada no texto sem os nomes dos órgãos que são
   assunto. O nome do órgão emissor continua valendo: "atas da assembleia **regional**" segue filtrando `regional`,
   porque `assembleias` reúne as duas.
3. **Busca filtrada vazia é refeita sem órgão e abrangência.** Se a busca com `bodies` ou `scopes` não acha nada, o
   retriever a refaz sem os dois, mantendo os demais filtros (vigência, tipo, ramo), e marca os trechos com `relaxed`.
   Na dúvida, não filtra (101 research R8).
4. **A pergunta de seguimento herda o assunto da anterior.**
   - **É de seguimento** a pergunta sem assunto próprio (sem tema, órgão, espécie de lista ou tipo de unidade) que é
     curta (até 6 palavras) ou tem marcador de retomada. Os marcadores ficam no léxico: no texto ("isso", "disso",
     "nele", "também"…), em `follow_up_markers`; no início ("e no", "e quanto", "olhe no"…), em `follow_up_openers`.
   - **Âncora**: a última pergunta anterior do usuário que tem assunto, recuando até 3 turnos, com até 400 caracteres.
   - **Da âncora com a atual** saem os temas, os órgãos sugeridos e o pedido de lista ou de enumeração. O ramo e o
     período vêm da atual e, sem eles, da âncora.
   - **Só da atual** saem o tipo citado, a abrangência e o emissor: "e no estatuto nacional?" troca o documento, não o
     assunto.
   - A derivação continua pura. O `prepare_context` lhe passa as perguntas `user` anteriores de `view.messages`.
5. **A âncora vai em `retrieval_filters.anchor`** (texto, até 400 caracteres; outro valor → `InvalidFilters`).
   - O retriever faz duas buscas e junta pela melhor posição de cada trecho: a da âncora com a pergunta e a da pergunta
     sozinha. A âncora traz o assunto, e a pergunta sozinha protege de uma âncora errada.
   - Nas facetas por ramo, uma busca só, com a âncora.
   - As tools de lista e de unidades seguem o pedido derivado.
6. **O prompt junta os níveis das normas.** Numa pergunta sobre um órgão ou sobre o que estatutos e regulamentos dizem,
   a resposta põe primeiro a regra do nível de cima e depois o que o nível de baixo acrescenta, sem contrariá-la. Se
   chegou um nível só, ela diz que o outro pode completar.

## Alternativas rejeitadas

- **Nunca filtrar por órgão.** "As atas da assembleia regional" voltaria a trazer atas de todos os órgãos; o filtro do
  emissor é o que o ADR-049 resolveu.
- **Reescrever a pergunta de seguimento por um modelo no core.** É o caminho mais geral, e é a mesma etapa que a
  distância de vocabulário pede, mas muda o `rag_first` (005) e soma uma chamada por turno. Fica para quando o grafo
  (Fase 2 do relatório) estiver medido; a regra no pack é determinística e não custa nada.
- **Buscar só com a âncora.** Uma âncora errada (pergunta nova curta depois de outro assunto) tomaria todas as vagas.
  As duas buscas juntas custam uma consulta em memória a mais.
- **Herdar também o tipo citado da anterior.** "E qual o prazo?" depois de "o que o regulamento diz…" ficaria preso
  ao regulamento. A regra da hierarquia das normas pede o contrário: mais níveis, não menos.

## Consequências

- O contrato de `retrieval_filters` (101) ganha `anchor`, e a 103 o aceita em `KNOWN`. Os dois mudam juntos, e o pack
  vai a 0.9.0.
- `context_accuracy` (105) compara o contexto inteiro, e `anchor` entra nele. Os itens de avaliação são de uma pergunta
  só, então a âncora sai `null` neles. O seguimento é coberto pelos testes da derivação e do retriever.
- O caso de 08/11 em si (o vice-presidente regional) **não** é resolvido aqui. O Art. 27 continua fora dos 20: a
  pergunta descreve um caso, e a norma fala em abstrato. A recuperação guiada pelo grafo e a reescrita da consulta
  ficam para a Fase 2 do relatório.
