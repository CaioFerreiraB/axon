# Feature Specification: Ingestão do corpus, chunking estrutural e modelo de vigência

**Feature Branch**: `102-scouting-corpus-ingestion`

**Created**: 2026-09-10

**Status**: Draft

**Input**: Tradução de arch-v1 §20 (ingestão e chunking), §22 (vigência, versão e revogação), Parte IX (modelo de embedding); princípio IX.

## Module Boundary *(mandatory)*

- **Módulo**: Corpus Ingestion — transforma documentos institucionais em chunks indexados com estrutura, metadados e vigência, preservando o texto original.
- **Repositório / distribuição**: `ai-scouting` → `src/ai_scouting/rag/ingestion/` (pipeline offline, não roda no caminho da requisição) e `src/ai_scouting/rag/index/` (seam do índice e seus adapters).
- **Consome (seams)**: forma de `Chunk` — 001.
- **Expõe (seams)**: **Índice do scouting** — modelo de chunk indexado (schema, metadados, modelo de vigência, identificadores estáveis, versão do índice) e porta de consulta `ChunkIndex` (busca híbrida com filtros) — consumido por 103 e 106; o modelo (valores de status de vigência) também por 104.
- **Depende de infraestrutura (via portas)**: base de vetores, modelo de embedding, armazenamento do texto original.
- **Não conhece**: o core, flows, prompts, como os resultados da busca são usados.
- **Substituição**: preservar o modelo de chunk indexado, a porta `ChunkIndex` e a estabilidade dos identificadores de chunk; base de vetores, parser, chunker e embeddings podem ser trocados com reindexação (são adapters).
- **Insumo técnico**: [design.md](design.md); [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md).

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Curador ingere um documento (Priority: P1)

O curador do corpus submete um documento (PDF). A ingestão extrai a estrutura, gera chunks, enriquece com metadados, calcula representações densa e esparsa e indexa na coleção.

**Why this priority**: Fase 5; sem corpus não há RAG.

**Independent Test**: Ingerir um manual de teste e consultar a coleção: todos os chunks têm texto, metadados obrigatórios e as duas representações.

**Acceptance Scenarios**:

1. **Given** um PDF de manual, **When** ingerido, **Then** a coleção contém seus chunks com identificador estável, metadados e representações densa e esparsa.
2. **Given** o mesmo documento ingerido duas vezes, **When** a segunda ingestão termina, **Then** os identificadores de chunk são os mesmos e não há duplicatas.

---

### User Story 2 - Norma dividida pela própria estrutura (Priority: P1)

Para material normativo, a unidade é a estrutura: um artigo é um chunk, com parágrafos, incisos e alíneas dentro dele. Cada chunk carrega o caminho ancestral (documento · título · capítulo · seção) como prefixo.

**Why this priority**: O chunk fica auto-contido para o modelo e a citação é derivável do próprio chunk.

**Independent Test**: Ingerir uma norma de teste; cada artigo vira exatamente um chunk, com o prefixo completo.

**Acceptance Scenarios**:

1. **Given** uma lei com títulos, capítulos, seções e artigos, **When** ingerida, **Then** cada artigo é um chunk prefixado por "[Lei X · Título II · Capítulo III · Seção I]".
2. **Given** um artigo que atravessa páginas, **When** ingerido, **Then** o chunk registra a faixa de páginas.

---

### User Story 3 - Vigência e substituição modeladas (Priority: P1)

Cada documento registra versão, início e fim de vigência, qual documento o substituiu e status (vigente, revogado, substituído, rascunho). Ingerir uma versão nova atualiza a versão anterior como substituída.

**Why this priority**: "Guardar versão e data não basta; é preciso modelar a substituição" — é o problema central do domínio normativo.

**Independent Test**: Ingerir a versão 2023 e depois a 2026 de um manual; a 2023 fica `substituído` apontando para a 2026.

**Acceptance Scenarios**:

1. **Given** o manual 2023 vigente, **When** o manual 2026 é ingerido como sucessor, **Then** a 2023 fica `substituído`, com fim de vigência e referência à 2026.
2. **Given** um documento marcado como rascunho, **When** ingerido, **Then** fica fora da busca default.

---

### User Story 4 - Material narrativo em janelas semânticas (Priority: P2)

Para manuais narrativos, os chunks são janelas de tamanho moderado que respeitam fronteiras semânticas (seções, parágrafos).

**Why this priority**: Nem todo documento tem estrutura normativa.

**Independent Test**: Ingerir um capítulo narrativo; nenhum chunk corta uma frase no meio.

**Acceptance Scenarios**:

1. **Given** um texto narrativo, **When** ingerido, **Then** os chunks respeitam fronteiras de parágrafo e ficam na faixa de tamanho configurada.

---

### User Story 5 - Texto original preservado e reindexação (Priority: P2)

O texto original de cada documento permanece armazenado e recuperável; chunks são índice, não substituto. Mudar a estratégia de chunking ou o modelo de embedding reindexa a coleção de forma controlada.

**Why this priority**: Princípio IX; e a escolha de embedding só será decidida por medição (105).

**Independent Test**: Reindexar a coleção com outro modelo de embedding sem perder documentos nem alterar identificadores de documento.

**Acceptance Scenarios**:

1. **Given** um chunk qualquer, **When** o original é solicitado, **Then** o trecho original correspondente é recuperável.
2. **Given** uma troca de modelo de embedding, **When** a reindexação termina, **Then** todos os documentos estão presentes e a versão do índice é registrada.

---

### Edge Cases

- PDF escaneado sem camada de texto: sinalizado e rejeitado na v1 (OCR fora de escopo).
- Documento sem estrutura reconhecível: tratado como narrativo.
- Dois documentos vigentes na mesma linhagem: a ingestão rejeita e pede resolução ao curador.
- Metadado obrigatório ausente: documento rejeitado com lista de campos faltantes.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: A ingestão DEVE extrair estrutura, gerar chunks, enriquecer metadados e produzir representações densa e esparsa para cada chunk.
- **FR-002**: Material normativo DEVE ser dividido por artigo, mantendo parágrafos, incisos e alíneas dentro do chunk do artigo.
- **FR-003**: Cada chunk normativo DEVE ser prefixado pelo caminho ancestral.
- **FR-004**: Material narrativo DEVE ser dividido em janelas que respeitam fronteiras semânticas, com tamanho configurável.
- **FR-005**: Cada chunk DEVE ter identificador estável e determinístico, derivado de documento, versão, seção e página.
- **FR-006**: Cada chunk DEVE carregar os metadados da tabela do design (documento, tipo, título, ramo, jurisdição, capítulo, seção, subseção, página, artigo, versão, datas, substituição, status).
- **FR-007**: O modelo de vigência DEVE registrar versão, início e fim de vigência, documento sucessor e status (`vigente`, `revogado`, `substituído`, `rascunho`).
- **FR-008**: Ingerir um sucessor DEVE atualizar o antecessor; no máximo um documento vigente por linhagem.
- **FR-009**: O texto original DEVE ser preservado e recuperável a partir de qualquer chunk.
- **FR-010**: A reindexação DEVE ser idempotente e registrar a versão do índice (estratégia de chunking + modelo de embedding).
- **FR-011**: A ingestão DEVE rejeitar documentos sem metadados obrigatórios, listando os campos faltantes.

### Key Entities

- **Document**: identificador, tipo, título, ramo, jurisdição, versão, datas de vigência, sucessor, status, original.
- **Chunk**: identificador estável, texto com prefixo ancestral, metadados, representações densa e esparsa.
- **Index Version**: estratégia de chunking + modelo de embedding + data.
- **Chunk Index**: porta de consulta do índice (busca densa e esparsa com fusão, filtros de vigência e de contexto), consumida por 103 e 106.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% dos chunks normativos têm caminho ancestral completo e permitem derivar uma citação válida.
- **SC-002**: Reingerir o mesmo documento produz 0 duplicatas e os mesmos identificadores.
- **SC-003**: 0 linhagens com mais de um documento vigente.
- **SC-004**: Uma reindexação completa do corpus inicial conclui dentro da janela de manutenção definida pelo operador (meta a medir).

## Assumptions

- Ingestão é offline, disparada pelo curador/operador; não há ingestão de longa duração que exija motor de workflow (ADR-010).
- Modelo de embedding decidido por medição na Fase 5/6 (candidatos no design); a escolha não altera o modelo de chunk indexado nem a porta `ChunkIndex` — cada candidato é um adapter de embedding.
- Onde o texto original fica armazenado é decidido no plano; o acesso é por porta, e o armazenamento é adapter.
- O corpus inicial é de documentos institucionais em português.
