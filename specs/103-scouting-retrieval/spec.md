# Feature Specification: Retrieval híbrido e rerank do scouting

**Feature Branch**: `103-scouting-retrieval`

**Created**: 2026-09-10

**Status**: Draft

**Input**: Tradução de arch-v1 §21 (retrieval híbrido, reranker, números), §22 (comportamento default de vigência, consulta histórica); ADR-006.

## Module Boundary *(mandatory)*

- **Módulo**: Scouting Retrieval — busca híbrida na coleção do scouting, com filtros de vigência e de contexto, e reordenação dos candidatos.
- **Repositório / distribuição**: `axon-scouting` → `src/axon_scouting/rag/retrieval/`.
- **Consome (seams)**: contratos `Retriever`, `Reranker`, `Chunk` — 001; Índice do scouting (modelo + porta `ChunkIndex`) — 102; filtros publicados pela preparação de contexto — 101 (repassados pelo core de forma opaca).
- **Expõe (seams)**: um `Retriever` (exposto também como tool `scouting.search_docs`) e um `Reranker` — consumidos pelo pack (101) e, através dele, pelo core.
- **Depende de infraestrutura (via portas)**: nenhuma direta — o índice é consultado pela porta de 102. Um reranker hospedado (v2) ou local (v3), quando existir, entra como adapter.
- **Não conhece**: o core, flows, o portão de cobertura (o core decide a partir dos scores devolvidos), validators, a base de vetores.
- **Substituição**: qualquer implementação do contrato `Retriever` serve — incluindo GraphRAG (106) — sem mudança em 101, 104 ou no core.
- **Insumo técnico**: [design.md](design.md); [ADR-006](../../docs/adr/ADR-006-rag-first-default-scouting.md), [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md), [ADR-013](../../docs/adr/ADR-013-seams-transversais-trace-e-tempo.md).

## Clarifications

### Session 2026-10-08

- Q: Que número a 103 devolve como `score` de cada trecho — o que o portão de cobertura do `rag_first` (005) compara com o limiar? → A: A similaridade densa (cosseno entre a pergunta e o trecho, de 0 a 1), absoluta e comparável entre perguntas e packs; a fusão RRF só decide a ordem. Exige um campo aditivo no modelo do índice da 102 (`similarity` no `IndexedChunk`), calculado pelo adapter com os vetores que a busca já devolve.
- Q: Como o reranker v1 aplica o "reforço por metadados" (vigência, ramo, tipo) sobre os candidatos da fusão? → A: Como desempate, sem pesos: mantém a ordem da fusão e, entre candidatos empatados nela, prefere o vigente, depois o específico do ramo pedido, depois o de um tipo que a pergunta sugeriu; corta em N. Nenhum peso numérico na v1 (princípio X) — reforço com pesos entra se a 105 medir ganho.
- Q: O que a 103 faz com os temas (`topics`) publicados pela 101, se o índice da 102 não guarda tema nos chunks? → A: Ignora na v1: os temas seguem na fatia da 101 (a 105 mede a derivação), mas não filtram nem reforçam a busca. Expandir a consulta acoplaria a 103 ao léxico da 101; etiquetar na ingestão mudaria a 102 sem medição.

### Session 2026-10-21

- Q: Com qual modelo a pergunta é codificada depois do [ADR-043](../../docs/adr/ADR-043-indice-do-scouting-gerado-no-desenvolvimento.md)? → A: Com o embedder da configuração do pack (`e5`, `pplx` ou `hashing`), o mesmo dos vetores carregados do artefato; a combinação errada é `IndexMismatch`, como antes. Falha do embedder remoto (sem a chave, provedor fora) é falha da recuperação: o `rag_first` encerra sem gerar (005). O retriever não muda.

### Session 2026-10-27

Revisão do RAG ([relatório](../../docs/revisao-rag-scouting-2026-10.md)) e [ADR-045](../../docs/adr/ADR-045-filhotes-e-consulta-multifaceta-no-scouting.md).

- Q: Como o retriever atende uma pergunta sobre vários ramos, se o core entrega os primeiros trechos na ordem do reranker? → A: Com `branches` nos filtros, uma busca por ramo — a pergunta seguida de "Ramo X", com o filtro do ramo e o limite inteiro (o índice corta as listas antes da fusão) —, guardando de cada uma a sua parte do `top_k`; o resultado intercala as facetas, sem repetir trecho, com a faceta e a posição nos metadados, e o `MetadataReranker` reconstrói essa ordem: os primeiros trechos são um de cada ramo.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Busca híbrida com fusão na própria base (Priority: P1)

Uma consulta é executada ao mesmo tempo como busca densa e esparsa; a fusão dos resultados acontece na própria base de vetores, produzindo de 20 a 30 candidatos.

**Why this priority**: Fase 5. Fusão nativa evita fundir resultados de buscas separadas na aplicação (correção em relação à v0).

**Independent Test**: Para perguntas com termo exato (número de artigo) e perguntas parafraseadas, os documentos esperados aparecem entre os candidatos.

**Acceptance Scenarios**:

1. **Given** uma pergunta que cita "Art. 42", **When** a busca roda, **Then** o artigo 42 está entre os candidatos (componente esparsa).
2. **Given** uma pergunta parafraseada, **When** a busca roda, **Then** o trecho semanticamente correspondente está entre os candidatos (componente densa).

---

### User Story 2 - Só o vigente, por default (Priority: P1)

Toda busca aplica, por default, o filtro "vigente na data de referência da execução" (recebida de 101 nos filtros; o dia da requisição, salvo quando fixada numa avaliação — ADR-013). Documentos revogados, substituídos ou em rascunho não aparecem, a menos que a consulta peça explicitamente.

**Why this priority**: Citar norma revogada sem aviso é o pior erro do domínio.

**Independent Test**: Com as versões 2023 e 2026 de um manual indexadas, uma busca default retorna só chunks da 2026.

**Acceptance Scenarios**:

1. **Given** versões vigente e substituída do mesmo manual, **When** a busca default roda, **Then** só a vigente aparece.

---

### User Story 3 - Busca numa data passada (Priority: P2)

Com data de referência passada e inclusão de revogados (filtros derivados em 101), a busca retorna o que estava vigente naquela data, com o status atual de cada chunk preservado para o aviso na resposta.

**Why this priority**: Consulta histórica é legítima e precisa ser explícita.

**Independent Test**: Data de referência 2023 retorna chunks da versão 2023, com status `substituído`.

**Acceptance Scenarios**:

1. **Given** data de referência 2023, **When** a busca roda, **Then** retorna a versão vigente em 2023 e informa seu status atual.

---

### User Story 4 - Rerank barato na v1 (Priority: P2)

Os candidatos ficam na ordem da fusão; entre empatados nela, o reforço por metadados desempata — vigente, depois específico do ramo, depois do tipo sugerido pela pergunta — e a lista é reduzida a 3–8 trechos, com custo praticamente nulo.

**Why this priority**: Um cross-encoder sobre 30 candidatos custa segundos no hardware alvo; a v1 precisa ser barata. O contrato permite evoluir sem mudar o core.

**Independent Test**: Entre dois candidatos empatados na fusão, o vigente e específico do ramo fica acima do geral.

**Acceptance Scenarios**:

1. **Given** 30 candidatos, **When** o rerank roda, **Then** devolve no máximo N (configurável, 3–8), na ordem da fusão, com os empates desfeitos pelo reforço por metadados.
2. **Given** a troca do reranker por um hospedado (v2), **When** configurada, **Then** nenhuma mudança é necessária no core nem em 101.

---

### User Story 5 - Filtros de contexto aplicados (Priority: P3)

Os filtros de ramo e tipos de documento publicados por 101 restringem a busca.

**Why this priority**: Aumenta a precisão; o default sem filtros já funciona.

**Independent Test**: Com filtro ramo = pioneiro, nenhum chunk de outro ramo aparece.

**Acceptance Scenarios**:

1. **Given** filtro ramo = pioneiro, **When** a busca roda, **Then** só aparecem chunks do ramo pioneiro ou gerais.

---

### User Story 6 - Um trecho de cada ramo pedido (Priority: P1)

Uma pergunta sobre vários ramos recebe, nos primeiros trechos, um de cada ramo pedido, e não os mais parecidos com a
pergunta inteira.

**Why this priority**: Medido na revisão do RAG: na busca única, uma ou duas facetas de cinco chegavam à geração; com
uma subbusca por ramo, a evidência fica em primeiro dentro do ramo em 9 de 10 combinações de marco simbólico e lema.

**Independent Test**: Com `branches`, o resultado intercala os ramos (o primeiro de cada um antes do segundo de
qualquer um), sem trecho repetido, e a ordem sobrevive ao reranker.

**Acceptance Scenarios**:

1. **Given** `branches = [escoteiro, pioneiro]` e `top_k = 6`, **When** busca, **Then** os dois primeiros são o
   primeiro de cada ramo, e nenhum trecho aparece duas vezes.
2. **Given** um trecho geral achado pelas duas facetas, **When** busca, **Then** ele fica só na primeira, e a segunda
   também tem uma posição 0.
3. **Given** `branches` com um ramo só, repetido ou desconhecido, ou junto de `branch`, **When** busca, **Then**
   `InvalidFilters` nomeando `branches`.

---

### User Story 7 - A lista de documentos que a pergunta pede (Priority: P1)

Quem pergunta "quais são as políticas nacionais" recebe os documentos do acervo, um por um, com versão, vigência e
link, e não os trechos mais parecidos com a pergunta ([ADR-047](../../docs/adr/ADR-047-lista-de-documentos-do-acervo-no-scouting.md)).

**Why this priority**: Medido na 105 (R20): com 20 ou 30 trechos, as listas ficavam em 0,62–0,75 de `fact_recall`;
nenhuma quantidade razoável de trechos traz todos os documentos de uma lista.

**Independent Test**: Com o pedido de lista nos filtros, a tool `list_documents` devolve uma ficha por documento cujo
título casa, sob a mesma vigência da busca, e o reranker as põe antes dos trechos.

**Acceptance Scenarios**:

1. **Given** `catalog = {kind: politica, terms: [nacionais]}`, **When** a tool roda, **Then** cada política nacional
   vigente vem numa ficha, do documento mais recente ao mais antigo, com "ficha do acervo, N de M".
2. **Given** um qualificador que nenhum título tem, **When** a tool roda, **Then** nenhuma ficha.
3. **Given** filtros sem `catalog`, **When** a tool roda, **Then** nada; **Given** `catalog` malformado, **Then**
   `InvalidFilters` nomeando `catalog`.
4. **Given** fichas e trechos, **When** o `MetadataReranker` ordena, **Then** as fichas vêm primeiro, na ordem da lista.

---

### User Story 8 - A enumeração respondida pela estrutura (Priority: P1)

Quem pergunta "quais são as especialidades do ramo pioneiro?" recebe a lista inteira, com página; quem pergunta "quais
são os órgãos nacionais da UEB?" recebe o artigo que os enumera — e não os trechos que explicam o assunto
([ADR-048](../../docs/adr/ADR-048-arvore-de-unidades-e-enumeracao-no-scouting.md)).

**Why this priority**: Uma lista perde da prosa nas duas buscas, por construção: no teste do mantenedor, o trecho com as
32 especialidades ficou em 86º no denso e 142º no BM25, e o Art. 12 do Estatuto, em 92º e 35º. Restrita à estrutura, a
busca os põe em 1º ou 2º (102 R34). Três das 20 vagas da resposta foram para o mesmo texto repetido.

**Independent Test**: Com `enumeration` nos filtros, a tool `list_units` devolve a lista das unidades do tipo pedido ou,
sem tipo, os melhores trechos `list` e sumários; o reranker os põe antes dos trechos, e o total não muda.

**Acceptance Scenarios**:

1. **Given** `enumeration = {unit_kind: especialidade}` e `branch = pioneiro`, **When** a tool roda, **Then** uma
   ficha com as 32 especialidades do guia Sênior/Pioneiro, cada uma com eixo e página, e nenhuma do Lobinho/Escoteiro.
2. **Given** `enumeration = {unit_kind: null}` e a pergunta dos órgãos nacionais, **When** a tool roda, **Then** o
   Art. 12 do Estatuto está entre os trechos `list` devolvidos.
3. **Given** três trechos de texto idêntico entre os candidatos, **When** a busca devolve, **Then** fica um, com os
   títulos dos outros nos metadados.
4. **Given** dois trechos irmãos da mesma unidade entre os entregues, **When** a entrega monta o contexto, **Then** eles
   vão juntos, em ordem, com o caminho da unidade, até o teto de tokens por unidade.
5. **Given** filtros sem `enumeration`, **When** a tool roda, **Then** nada; **Given** `enumeration` malformado,
   **Then** `InvalidFilters` nomeando `enumeration`.

---

### Edge Cases

- Nenhum resultado após filtros: retorna vazio — o portão do core escala (spec 005).
- Filtro de ramo zera os resultados mas sem filtro haveria resultados gerais: documentos gerais (sem ramo) são incluídos por default.
- Consulta vazia ou só com termos de parada: retorna vazio sem erro.
- Coleção indisponível: erro explícito (não resultado vazio silencioso).

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: O retriever DEVE executar busca densa e esparsa e fundi-las na própria base de vetores.
- **FR-002**: O retriever DEVE aplicar por default o filtro de vigência na data de referência recebida nos filtros (101 a deriva da Turn View — ADR-013); o retriever NÃO DEVE ler o relógio do sistema.
- **FR-003**: O retriever DEVE aceitar data de referência e inclusão de revogados/substituídos a partir dos filtros recebidos.
- **FR-004**: Cada chunk devolvido DEVE carregar proveniência completa (identificador, documento, versão, status atual, seção, página) e score. O score é a similaridade densa entre a pergunta e o trecho (cosseno, 0–1), comparável entre perguntas e entre packs; a ordem vem da fusão (e do reranker), não do score.
- **FR-005**: O reranker v1 DEVE manter a ordem da fusão, desfazer empates por metadados nesta ordem — vigente antes de não vigente, específico do ramo pedido antes de geral, tipo sugerido pela pergunta antes dos demais — e devolver no máximo N trechos. A v1 NÃO DEVE usar pesos numéricos (princípio X).
- **FR-006**: O retriever DEVE estar disponível também como tool de recuperação para o loop agêntico.
- **FR-007**: Indisponibilidade da coleção DEVE gerar erro explícito.
- **FR-008**: Quantidades DEVEM ser configuráveis e calibradas pela spec 105: a 103 configura quantos trechos devolve quando o chamador não diz (`default_limit`) e o teto do que aceita (`max_limit`); o número de candidatos e o N após o rerank chegam do chamador (`top_k` — a 005 no `rag_first`).
- **FR-009**: Os temas (`topics`) recebidos nos filtros NÃO DEVEM restringir nem reforçar a busca na v1; o retriever usa só vigência, ramo e tipos de documento.
- **FR-010**: A busca DEVE codificar a pergunta com o embedder escolhido na configuração do pack, e uma falha dele DEVE chegar ao core como falha da recuperação, sem resultado parcial.
- **FR-011**: Com `branches` nos filtros, o retriever DEVE fazer uma busca por ramo (a pergunta seguida do nome do ramo, com o filtro dele), repartir o `top_k` entre as facetas e intercalá-las sem repetir trecho; a ordem (posição na faceta, ordem da faceta, depois a da FR-005) DEVE ir nos metadados, para o reranker reconstruí-la ([ADR-045](../../docs/adr/ADR-045-filhotes-e-consulta-multifaceta-no-scouting.md)).
- **FR-012**: `suggested_types` nos filtros NÃO DEVE restringir a busca: só liga a marca de tipo da ordem (FR-005), como o tipo citado ([ADR-046](../../docs/adr/ADR-046-tipo-sugerido-ordena-no-scouting.md)).
- **FR-013**: O pack DEVE oferecer a tool `scouting.list_documents` (a coleção da busca) sobre o seam *Catálogo de documentos* da 102: com `catalog` nos filtros, uma ficha por documento cujo título tem a espécie e a maior fração dos qualificadores que algum título alcança, sob os mesmos filtros de vigência, ramo e tipo, do mais recente ao mais antigo, até `max_cards` (15); sem `catalog`, nada ([ADR-047](../../docs/adr/ADR-047-lista-de-documentos-do-acervo-no-scouting.md)).
- **FR-014**: A ficha DEVE trazer título, versão, vigência, abrangência, ramo e o link do original, com id `<doc_key>#acervo`, seção "ficha do acervo, N de M" e sem página; o reranker DEVE pô-la antes de todo trecho, na ordem da lista.
- **FR-015**: O pack DEVE oferecer a tool `scouting.list_units` (a coleção da busca) sobre o seam *Índice do scouting* (102 FR-029): com `enumeration` e `unit_kind`, uma ficha por documento com as unidades daquele tipo que os filtros admitem (título, caminho e página de cada uma), com id `<doc_key>#unidades/<tipo>`; com `enumeration` sem `unit_kind`, a busca restrita aos trechos `shape="list"` (até 3) e aos sumários (`outline`, até 2); sem `enumeration`, nada. O reranker DEVE pôr o que ela devolve antes de todo trecho, depois das fichas do acervo, e o total de trechos não muda ([ADR-048](../../docs/adr/ADR-048-arvore-de-unidades-e-enumeracao-no-scouting.md)).
- **FR-016**: A busca DEVE juntar os candidatos de texto idêntico (o corpo sem o rótulo, normalizado): fica o de melhor posição, e os títulos dos outros vão nos metadados.
- **FR-017**: O trecho entregue DEVE levar o caminho da unidade; dois ou mais irmãos da mesma unidade entre os entregues DEVEM ir juntos, na ordem do documento, até um teto de tokens por unidade (provisório: 1.500).
- **FR-018** ([ADR-049](../../docs/adr/ADR-049-taxonomia-e-a-tipologia-do-acervo-no-scouting.md)): O retriever DEVE traduzir `bodies` e `scopes` em filtros do índice e desempatar pelo órgão sugerido (`suggested_bodies`), depois do tipo sugerido; a lista de documentos DEVE escolher pelo tipo da taxonomia e casar os qualificadores no título ou na classificação do documento.

### Key Entities

- **Retrieval Query**: texto, filtros (ramo, tipos, data de referência, inclusão de revogados), quantidade.
- **Candidate / Reranked Chunk**: chunk com score (similaridade densa) e proveniência, na ordem da fusão e do reranker.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 0 chunks não vigentes em resultados de busca default no conjunto dourado.
- **SC-002**: recall@k no conjunto dourado atinge a meta definida após a linha de base da Fase 6.
- **SC-003**: O rerank v1 não adiciona atraso perceptível à resposta no hardware alvo.
- **SC-004**: Trocar o reranker (v1 → v2 → v3) exige só configuração/implementação no `axon-scouting`, nenhuma mudança no core.

## Assumptions

- Números iniciais: 20–30 candidatos, 3–8 após rerank — faixas a calibrar na Fase 6.
- Progressão do reranker: v1 fusão + desempate por metadados; v2 hospedado; v3 cross-encoder local se o hardware crescer. Reforço com pesos só se a 105 medir ganho.
