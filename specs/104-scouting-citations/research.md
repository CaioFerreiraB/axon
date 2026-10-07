# Research — 104 Scouting Citations, Fase 4 (esqueleto dos validators)

Insumos pré-aprovados: [design.md](design.md), [spec.md](spec.md) §Clarifications (sessão de 2026-10-07),
[ADR-007](../../docs/adr/ADR-007-citacao-mecanica.md), [ADR-012](../../docs/adr/ADR-012-estilo-arquitetural-hexagonal.md),
[ADR-021](../../docs/adr/ADR-021-workspace-ai-core-permanece-no-repositorio-da-plataforma.md); constituição (princípios
V, VII, IX, XII, XIII). Código de referência: o contrato de validator da 001 na tag `contracts-v0.1.0`
(`AnswerValidator`, `ValidationResult`, `ValidatorContext`, `TurnView.generation_context`, `Chunk`, `Citation`, kit
`ai_core_contracts.testing`); o pack `ai-scouting` da 101 (Fase 4); e, no core, como os resultados são aplicados —
`PackRuntime.validate` encadeia resposta e citações entre validators (`apply_validation`), o motor transforma cada
`issue` em registro `notice` e passa adiante `flags`, e a API devolve a resposta reescrita sem streaming e, com
streaming, só `citations`, `flags` e `errors` no último pedaço.

## R1 — Escopo da Fase 4

**Decision** (clarificação 1, FR-008): os dois validators completos e testados em `ai-scouting`, com Turn Views
sintéticas; o `pack.py` **não** os publica — `validators()` continua vazio — até a Fase 5, quando chegam o retriever, a
coleção e a sintaxe de citação nas instruções (101 FR-007/FR-010, 104 FR-007). Fora do escopo: a publicação, o prompt de
citação e o comportamento em streaming (R11).

**Rationale**: sem corpus, `generation_context` é sempre vazio — publicados agora, os validators marcariam toda resposta
como não fundamentada, repetindo o que o prompt da Fase 4 já manda dizer.

**Alternatives considered**: publicar já (clarificação 1, opções B e C).

## R2 — Onde mora e como se organiza

**Decision** (design.md): `src/ai_scouting/validators/` com `citations.py` (sintaxe, extração e numeração — puro),
`integrity.py` (`CitationIntegrityValidator`, `name = "citation_integrity"`), `notice.py` (`ValidityNoticeValidator`,
`name = "validity_notice"`) e `_text.py` (dobra de texto para comparação). `validators/__init__.py` reexporta as duas
classes e documenta a ordem: `citation_integrity` antes de `validity_notice`.

**Rationale** (ADR-012): núcleo funcional puro — recebe a Turn View, devolve `ValidationResult`; sem porta, sem
adapter. Arquivos por responsabilidade, como em `context/`.

**Alternatives considered**: um arquivo só (mistura sintaxe, integridade e vigência, que mudam por motivos diferentes).

## R3 — Sintaxe de citação

**Decision** (design.md, proposta adotada): `[[<chunk_id>]]`. Extração por `\[\[\s*([^\[\]]+?)\s*\]\]`; identificadores
comparados **sem espaços e sem diferença de maiúsculas** (caso de borda "variação de formatação"). A citação devolvida
usa o `chunk_id` canônico do trecho, não a grafia do modelo.

**Rationale**: delimitador duplo é fácil de ensinar a modelo pequeno e de extrair por regex; `chunk_id` com `#`, `@`,
`.` e `-` cabe sem escape.

**Alternatives considered**: notas de rodapé numeradas pelo modelo (exigiria que o modelo mantivesse a numeração em
sincronia com o contexto); JSON estruturado ao fim da resposta (frágil em modelo pequeno, e a 005 gera texto livre).

## R4 — Fonte da verdade da integridade

**Decision** (ADR-007, design.md): o conjunto de identificadores de `view.generation_context` — nem `retrieved`, nem
`reranked`. Identificadores repetidos no contexto (mesma chave normalizada): vale o primeiro.

**Rationale**: só vale o que foi entregue à geração (US1 cen. 2: recuperado e cortado pelo orçamento é inválido).

**Alternatives considered**: `reranked` (aceitaria trecho que o modelo nunca viu).

## R5 — `citation_integrity`: algoritmo e resultado

**Decision**:

1. `view.answer is None` → `ValidationResult(ok=True)` sem mudança (não há resposta a validar).
2. Extrai os marcadores na ordem do texto; cada um é **válido** se a chave normalizada está no contexto de geração.
3. Numeração (clarificação 3, FR-009): cada trecho válido recebe `n` pela ordem da primeira aparição; repetido
   reaproveita o número; o marcador vira `[n]`. Marcador inválido sai do texto **com o espaço que o precede**
   ("conforme o manual [[x]]." → "conforme o manual.").
4. `citations`: os trechos válidos, únicos, na ordem de `n`, como `Citation` com `chunk_id`, `document`, `version`,
   `status`, `section`, `page` (FR-005).
5. Nenhuma válida (inclusive resposta sem nenhum marcador) → aviso "não fundamentada" ao fim (R7) e flag `ungrounded`.
6. `issues`: uma por marcador inválido ("citação fora do contexto da geração: <id como escrito>"), e "nenhuma citação
   válida" quando for o caso; flags `invalid_citation` (algum removido) e `ungrounded`. `ok = not issues`.
7. Sempre devolve `answer` (reescrita) e `citations` (mesmo vazia), para o próximo validator e para o evento final.

**Rationale** (US1, US2, casos de borda): o core transforma `issues` em registros `notice` nomeando pack e validator —
é o "registrada em erros" da US1 — e a reprovação não derruba a execução (005, `final_event`).

**Alternatives considered**: trocar o marcador inválido por "[citação removida]" (polui o texto e não ajuda o leitor).

## R6 — `validity_notice`: status e detecção de aviso já presente

**Decision** (clarificação 2, FR-004): lê `view.citations` (as já validadas — por isso roda depois). Status dobrado
(sem acento, minúsculo): `vigente` → sem aviso; `revogado`, `substituido`, `rascunho` → aviso com documento, versão e
status; vazio ou outro → aviso de "vigência não confirmada". O aviso de uma citação `[n]` conta como **já presente**
quando (a) a linha padrão dela está no texto, ou (b) alguma frase da resposta contém `[n]` e uma marca do status —
`revogad`, `substitu`, `nao vigente`, `nao esta vigente`, `rascunho`, ou `vigencia nao confirmada` para o status
desconhecido. Avisos faltantes vão num bloco ao fim, um por citação, na ordem de `n`. Resultado: `ok=True` (a resposta
foi corrigida), `answer` reescrita só quando acrescentou algo, flag `non_current_source` quando alguma citação não é
vigente.

**Rationale** (US3 cen. 1–2, princípio IX): o modelo pode avisar por conta própria; a regra (b) é determinística e
amarra o aviso à citação certa pela referência `[n]`; sem ela, o padrão entra. Reexecutar não duplica (regra a).

**Alternatives considered**: só a linha padrão exata (duplicaria quando o modelo já avisou — contra US3 cen. 2);
procurar o nome do documento em qualquer lugar (frases como "o Manual 2026 substituiu…" esconderiam a falta de aviso
sobre a versão 2023).

## R7 — Textos dos avisos

**Decision**: constantes em `notice.py` e `integrity.py`, em português, separadas da resposta por uma linha em branco:

- não fundamentada: `Atenção: esta resposta não se apoia em nenhum documento do acervo consultado. Confirme a
  informação na fonte oficial.`
- não vigente: `Atenção: [n] cita {documento} ({versão}), que está {status} — não é a versão vigente.` (sem versão:
  `{documento}`)
- vigência não confirmada: `Atenção: [n] cita {documento} ({versão}), cuja vigência não foi confirmada.`

**Rationale**: texto fixo é verificável em teste e reconhecível por quem lê; `[n]` liga o aviso à citação.

**Alternatives considered**: aviso no começo da resposta (interrompe a leitura; o padrão de nota é ao fim).

## R8 — Fronteiras e pureza

**Decision**: no `pyproject.toml` do `ai-scouting`, o contrato "só o pack.py compõe" passa a ter a camada
`ai_scouting.context | ai_scouting.prompts | ai_scouting.validators` (independentes entre si), e o contrato de modelo e
MCP passa a cobrir `ai_scouting.validators` (nome: "derivação e validators não alcançam modelo nem MCP").
`tests/test_purity.py` passa a varrer também `validators/`. A dobra de texto dos validators fica em `_text.py` próprio
— a camada não importa `context/`.

**Rationale** (FR-006, design.md "context/ e validators/ não importam rag"; ADR-012): os validators só conhecem o
contrato 001; independência entre submódulos do pack é a regra do design.

**Alternatives considered**: reaproveitar `context.text.normalize` (acopla dois submódulos que o design separa por
spec; a dobra tem seis linhas).

## R9 — Testes

**Decision**: `tests/test_citations.py` (extração, normalização, numeração e remoção — tabela),
`tests/test_integrity.py` (US1, US2, US4 e casos de borda com `turn_view` e `chunk` do kit), `tests/test_notice.py` (US3,
status, aviso já presente, idempotência) e `tests/test_validators_chain.py` (os dois em sequência, como o Pack Runtime
encadeia: a saída do primeiro vira a Turn View do segundo). Cada validator: determinismo (duas chamadas, mesmo
resultado) e "nunca levanta" para resposta `None`, vazia e contexto vazio. Hooks assíncronos com `asyncio.run`. O
`test_pack.py` da 101 já garante que o pack não publica validators (FR-008).

**Rationale**: o kit da 001 só exercita validators publicados; aqui eles são testados diretamente.

**Alternatives considered**: publicar só nos testes (testaria algo que a Fase 4 não entrega).

## R10 — Toques fora da 104

**Decision**: no `ai-scouting`, só `validators/`, os testes novos, `tests/test_purity.py` e o `[tool.importlinter]` do
`pyproject.toml` (R8). O `pack.py` da 101 não muda na Fase 4. No `agentic-app`: documentação e o ponteiro do submódulo.

**Rationale**: a publicação é um toque da Fase 5 no `pack.py`, declarado aqui para a 101.

## R11 — Lacuna do core em streaming (nota para a Fase 5)

**Decision**: registrar como pendência da 005/008 para a Fase 5: com streaming, os pedaços já saíram quando os
validators rodam, e o último pedaço leva `delta` vazio — a resposta reescrita (`[n]`, citação inventada removida,
avisos) não chega ao cliente; só `citations`, `flags` e `errors` chegam em `x_ai_core`. Sem streaming, chega tudo.

**Rationale**: a US2 e a US3 exigem aviso **visível**; com streaming, hoje, ele só existe nos metadados. A solução é do
core (por exemplo, `rag_first` sem streaming de tokens quando há validator que reescreve, ou um campo de substituição no
último pedaço) e precisa de decisão na Fase 5 — não muda nada na 104.

**Alternatives considered**: o validator só acrescentar, nunca remover (não resolve citação inventada já transmitida).

## R12 — Streaming: `citation_integrity` filtra ([ADR-024](../../docs/adr/ADR-024-validators-filtram-o-streaming.md); resolve a R11)

**Decision**: `IntegrityStream`: a cada `feed`, a resposta acumulada é cortada no trecho estável — antes do primeiro
`[[` sem `]]` depois dele, antes de um `[` final e antes do espaço que precede esse ponto — e a reescrita desse trecho
(a mesma do lote) é liberada no que ainda não saiu. `finish` é `_check` sobre a resposta inteira, a mesma função do
`validate`. A estabilidade do corte garante que a reescrita do trecho é prefixo da reescrita da resposta inteira.

**Rationale**: SC-001 com streaming — nenhum identificador inventado sai, e o atraso é só o de um marcador aberto.

**Verificação**: `tests/test_integrity_stream.py` — igualdade com o lote e "o fim só acrescenta" em quatro partições de
dez respostas (marcadores válidos, inventados, repetidos, sem fechar, colchete solto, colchetes aninhados, espaços).
