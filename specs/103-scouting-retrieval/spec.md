# Feature Specification: Retrieval híbrido e rerank do scouting

**Feature Branch**: `103-scouting-retrieval`

**Created**: 2026-09-10

**Status**: Draft

**Input**: Tradução de arch-v1 §21 (retrieval híbrido, reranker, números), §22 (comportamento default de vigência, consulta histórica); ADR-006.

## Module Boundary *(mandatory)*

- **Módulo**: Scouting Retrieval — busca híbrida na coleção do scouting, com filtros de vigência e de contexto, e reordenação dos candidatos.
- **Repositório / distribuição**: `ai-scouting` → `src/ai_scouting/rag/retrieval/`.
- **Consome (seams)**: contratos `Retriever`, `Reranker`, `Chunk` — 001; Índice do scouting (modelo + porta `ChunkIndex`) — 102; filtros publicados pela preparação de contexto — 101 (repassados pelo core de forma opaca).
- **Expõe (seams)**: um `Retriever` (exposto também como tool `scouting.search_docs`) e um `Reranker` — consumidos pelo pack (101) e, através dele, pelo core.
- **Depende de infraestrutura (via portas)**: nenhuma direta — o índice é consultado pela porta de 102. Um reranker hospedado (v2) ou local (v3), quando existir, entra como adapter.
- **Não conhece**: o core, flows, o portão de cobertura (o core decide a partir dos scores devolvidos), validators, a base de vetores.
- **Substituição**: qualquer implementação do contrato `Retriever` serve — incluindo GraphRAG (106) — sem mudança em 101, 104 ou no core.
- **Insumo técnico**: [design.md](design.md); [ADR-006](../../docs/adr/ADR-006-rag-first-default-scouting.md), [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md), [ADR-013](../../docs/adr/ADR-013-seams-transversais-trace-e-tempo.md).

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

Os candidatos são reordenados pela fusão mais reforço por metadados (vigência, tipo de documento, especificidade) e reduzidos a 3–8 trechos, com custo praticamente nulo.

**Why this priority**: Um cross-encoder sobre 30 candidatos custa segundos no hardware alvo; a v1 precisa ser barata. O contrato permite evoluir sem mudar o core.

**Independent Test**: Entre dois candidatos de mesmo score, o documento institucional e específico do ramo fica acima do genérico.

**Acceptance Scenarios**:

1. **Given** 30 candidatos, **When** o rerank roda, **Then** devolve no máximo N (configurável, 3–8) ordenados com o reforço por metadados.
2. **Given** a troca do reranker por um hospedado (v2), **When** configurada, **Then** nenhuma mudança é necessária no core nem em 101.

---

### User Story 5 - Filtros de contexto aplicados (Priority: P3)

Os filtros de ramo e tipos de documento publicados por 101 restringem a busca.

**Why this priority**: Aumenta a precisão; o default sem filtros já funciona.

**Independent Test**: Com filtro ramo = pioneiro, nenhum chunk de outro ramo aparece.

**Acceptance Scenarios**:

1. **Given** filtro ramo = pioneiro, **When** a busca roda, **Then** só aparecem chunks do ramo pioneiro ou gerais.

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
- **FR-004**: Cada chunk devolvido DEVE carregar proveniência completa (identificador, documento, versão, status atual, seção, página) e score.
- **FR-005**: O reranker v1 DEVE combinar a fusão com reforço por metadados (vigência, tipo, especificidade) e devolver no máximo N trechos.
- **FR-006**: O retriever DEVE estar disponível também como tool de recuperação para o loop agêntico.
- **FR-007**: Indisponibilidade da coleção DEVE gerar erro explícito.
- **FR-008**: Quantidades (candidatos, N após rerank) DEVEM ser configuráveis e calibradas pela spec 105.

### Key Entities

- **Retrieval Query**: texto, filtros (ramo, tipos, data de referência, inclusão de revogados), quantidade.
- **Candidate / Reranked Chunk**: chunk com score e proveniência.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 0 chunks não vigentes em resultados de busca default no conjunto dourado.
- **SC-002**: recall@k no conjunto dourado atinge a meta definida após a linha de base da Fase 6.
- **SC-003**: O rerank v1 não adiciona atraso perceptível à resposta no hardware alvo.
- **SC-004**: Trocar o reranker (v1 → v2 → v3) exige só configuração/implementação no `ai-scouting`, nenhuma mudança no core.

## Assumptions

- Números iniciais: 20–30 candidatos, 3–8 após rerank — faixas a calibrar na Fase 6.
- Progressão do reranker: v1 fusão + metadados; v2 hospedado; v3 cross-encoder local se o hardware crescer.
