---

description: "Task list for 104 — citações, proveniência e aviso de vigência, Fase 4 (esqueleto)"
---

# Tasks: Citações, proveniência e aviso de vigência

**Input**: Design documents from `/specs/104-scouting-citations/`

**Prerequisites**: [plan.md](plan.md), [spec.md](spec.md), [research.md](research.md), [data-model.md](data-model.md),
[contracts/](contracts/), [quickstart.md](quickstart.md)

**Tests**: incluídos — os validators são o caso de aceite da spec, verificados com Turn Views sintéticas.

**Organization**: **Fase 4 — esqueleto**: US1–US4 implementadas e testadas; os validators **não** são publicados pelo
pack (FR-008). A publicação, a sintaxe nas instruções e o streaming são Fase 5.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: pode rodar em paralelo (arquivos diferentes, sem dependência pendente)
- **[Story]**: user story da tarefa (US1–US4)

## Path Conventions

- Caminhos a partir de `ai-scouting/` (submódulo), salvo os que começam com `specs/`, `docs/` ou `CLAUDE.md`
- Comandos dentro de `ai-scouting/`, com `XDG_DATA_HOME=$HOME/.local/share`

---

## Phase 1: Setup

- [X] T001 Em `pyproject.toml`, `[tool.importlinter]`: a camada de baixo do contrato "só o pack.py compõe" passa a ser
  `"ai_scouting.context | ai_scouting.prompts | ai_scouting.validators"`; o contrato de modelo e MCP passa a se chamar
  "derivação e validators não alcançam modelo nem MCP" com `source_modules = ["ai_scouting.context",
  "ai_scouting.validators"]` (research R8)
- [X] T002 Criar `src/ai_scouting/validators/__init__.py` (docstring: spec 104, núcleo funcional puro, não publicado
  na Fase 4 — FR-008 —, ordem `citation_integrity` → `validity_notice`) e `src/ai_scouting/validators/_text.py` com
  `fold(text: str) -> str` (casefold, NFKD sem marcas combinantes, espaços colapsados)
- [X] T003 [P] Em `tests/test_purity.py`, varrer também `src/ai_scouting/validators/` (parametrizar pelas duas pastas)

---

## Phase 2: Foundational — sintaxe e reescrita (bloqueia US1–US4)

- [X] T004 [P] Criar `tests/test_citations.py` (research R3, R5; data-model "Marcador"): `extract` acha `[[a]]`,
  `[[ a b ]]` e `[[MAN#1@p2]]` na ordem, com o texto escrito; `key` tira todo espaço e faz casefold (`" MAN #1 "` →
  `"man#1"`); `rewrite(answer, numbers)` troca o marcador válido por `[n]`, mantém o número no repetido e remove o
  inválido com o espaço anterior (`"conforme o manual [[x]]."` → `"conforme o manual."`); texto sem marcador volta igual
- [X] T005 Criar `src/ai_scouting/validators/citations.py`: `MARKER` (regex `\[\[\s*([^\[\]]+?)\s*\]\]`),
  `key(raw: str) -> str`, `extract(answer: str) -> list[str]` (ids como escritos, na ordem) e
  `rewrite(answer: str, numbers: Mapping[str, int]) -> str` (chave → número; ausente = remover) (T004 passa)

---

## Phase 3: User Story 1 — Citação inventada nunca chega ao usuário (P1) 🎯

**Independent Test**: `uv run pytest tests/test_integrity.py -k "us1 or borda"`.

- [X] T006 [P] [US1] Criar `tests/test_integrity.py` com os casos 1, 2 e 7 de
  [contracts/validators.md](contracts/validators.md) (`test_us1_*`, `test_borda_*`): três marcadores com um inventado →
  `[1]`, `[2]`, duas citações, uma issue nomeando o id como escrito, flag `invalid_citation`, `ok=False`; trecho em
  `reranked` mas fora de `generation_context` → inválido; `[[ A ]]` casa com o trecho `a`; marcador repetido → um só
  `[1]` em dois lugares e uma citação; e, para todo caso, duas chamadas dão o mesmo resultado e `answer=None` devolve
  `ValidationResult(ok=True)` sem mudança
- [X] T007 [US1] Criar `src/ai_scouting/validators/integrity.py` com `CitationIntegrityValidator` (`name =
  "citation_integrity"`): chaves de `view.generation_context` (o primeiro vence), extração, numeração pela primeira
  aparição, `citations` como `Citation` com `chunk_id` canônico, `document`, `version`, `status`, `section`, `page`, e
  `issues`/`flags`/`ok` da tabela do [data-model.md](data-model.md); reexportar em `validators/__init__.py` (T006 passa)

## Phase 4: User Story 2 — Resposta sem fundamento é marcada (P1)

**Independent Test**: `uv run pytest tests/test_integrity.py -k us2`.

- [X] T008 [P] [US2] Em `tests/test_integrity.py`, `test_us2_*` (caso 3): só citações inválidas → resposta sem
  marcadores + linha em branco + `UNGROUNDED_NOTICE`, `citations == ()`, issues com "nenhuma citação válida", flags
  `ungrounded` e `invalid_citation`; resposta sem nenhum marcador → o mesmo aviso e só `ungrounded`; resposta vazia →
  aviso, sem levantar
- [X] T009 [US2] Em `integrity.py`, `UNGROUNDED_NOTICE` (texto de [contracts/validators.md](contracts/validators.md)) e o
  ramo "nenhuma válida" (T008 passa)

## Phase 5: User Story 3 — Fonte não vigente sempre sinalizada (P1)

**Independent Test**: `uv run pytest tests/test_notice.py`.

- [X] T010 [P] [US3] Criar `tests/test_notice.py` (casos 4, 5 e 8; research R6): citação `[1]` de trecho
  `substituído`, versão `2023`, sem aviso → resposta + linha em branco + `NON_CURRENT_NOTICE` formatado, flag
  `non_current_source`, `ok=True`; aviso já presente pela linha padrão → `answer is None`; aviso já presente numa frase
  com `[1]` e "revogado"/"substituída"/"não está vigente" → `answer is None`; `status=None` e `status="arquivado"` →
  `UNCONFIRMED_NOTICE`; `vigente`/`Vigente` → nenhum aviso; trecho sem versão → `{source}` só com o documento; duas
  citações não vigentes → dois avisos na ordem de `n`; reexecutar sobre a própria saída não duplica; determinismo
- [X] T011 [US3] Criar `src/ai_scouting/validators/notice.py` com `ValidityNoticeValidator` (`name =
  "validity_notice"`), `NON_CURRENT_NOTICE`, `UNCONFIRMED_NOTICE`, os status dobrados da 102 e a detecção de aviso já
  presente do [data-model.md](data-model.md); reexportar em `validators/__init__.py` (T010 passa)

## Phase 6: User Story 4 — Proveniência exibível (P2)

**Independent Test**: `uv run pytest tests/test_integrity.py -k us4 tests/test_validators_chain.py`.

- [X] T012 [P] [US4] Em `tests/test_integrity.py`, `test_us4_*` (caso 6): a citação traz exatamente `chunk_id`,
  `document`, `version`, `status`, `section` e `page` do trecho (o `chunk_id` canônico, não a grafia do modelo)
- [X] T013 [P] [US4] Criar `tests/test_validators_chain.py`: os dois validators em sequência, como o Pack Runtime
  encadeia (a Turn View do segundo leva `answer` e `citations` do primeiro) — o exemplo do
  [quickstart.md](quickstart.md) §2 dá exatamente a resposta e as flags esperadas

---

## Phase 7: Polish

- [X] T014 Verificação completa dentro de `ai-scouting/`: `uv run pytest` (3.14 e 3.12), `ruff check`, `ruff format
  --check`, `mypy`, `lint-imports` (três contratos `KEPT`, com `validators`) e a integração (`--group platform`)
- [X] T015 Executar o [quickstart.md](quickstart.md) §1–4 e corrigir divergências com o "Esperado"
- [X] T016 [P] Documentação no `agentic-app`: CLAUDE.md (os validators da 104 existem no `ai-scouting`, não publicados
  na Fase 4); linha da 104 em `specs/README.md` ("Fase 4: esqueleto implementado — validators testados, publicação na
  Fase 5"); em `docs/roadmap.md`, nas pendências entre specs, "005/008: com streaming, a resposta reescrita pelos
  validators não chega ao cliente (104 R11) — decidir antes de publicar os validators na Fase 5"
- [X] T017 Com o aval do mantenedor: commit e push no `ai-scouting`; commit no `agentic-app` com o SDD da 104, a
  documentação e o ponteiro do submódulo, e push; conferir a CI do `ai-scouting`

---

## Passada de 2026-10-07: streaming ([ADR-024](../../docs/adr/ADR-024-validators-filtram-o-streaming.md); research R12)

- [X] T018 `integrity.py`: `open_stream` e `IntegrityStream` (corte estável, reescrita do trecho, `finish` = `_check`);
  `_check`, `_delivered` e `_numbers` extraídos do `validate`
- [X] T019 `tests/test_integrity_stream.py`: igualdade com o lote, fim que só acrescenta e nenhum id inventado liberado,
  em quatro partições; liberação incremental

---

## Dependencies & Execution Order

- **Setup**: T001, T002 e T003 (T003 depois de T002, que cria a pasta)
- **Foundational**: T004 → T005; bloqueia todas as histórias
- **US1**: T006 → T007; **US2**: depende de US1 (mesmo arquivo); T008 → T009
- **US3**: depende só do Foundational e de T002; T010 → T011 (paralela a US1/US2)
- **US4**: T012 depende de T007; T013 depende de T007, T009 e T011
- **Polish**: T014 → T015 → T017; T016 em paralelo

## Parallel Example

```bash
Task: "tests/test_integrity.py — US1 (T006)"
Task: "tests/test_notice.py — US3 (T010)"
```

## Implementation Strategy

1. Setup e sintaxe (T001–T005)
2. US1 e US3 em paralelo; depois US2 e US4
3. **PARE e VALIDE**: os oito casos do contrato e o encadeamento
4. Polish: verificação, quickstart, documentação (com a pendência de streaming) e publicação

### Depois desta fase

- Fase 5 (101 US5): `validators()` publica `CitationIntegrityValidator()` e `ValidityNoticeValidator()`, nesta ordem;
  as instruções ensinam `[[chunk_id]]`; o flow rotula os trechos e resolve a lacuna de streaming (R11)
