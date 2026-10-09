# Data Model — 101 Scouting Pack, Fase 4 (US1, US2, US3)

Decisões em [research.md](research.md). Tudo aqui é puro e imutável; nada persiste entre execuções. Ids canônicos em
ASCII minúsculo com `_`.

## Identidade (lida pelo Pack Runtime sem instanciar — 002 FR-017)

| Campo | Valor | Origem |
|---|---|---|
| Distribuição | `ai-scouting` 0.1.0 | R4 |
| Pacote | `ai_scouting` | design.md |
| Entry point | `scouting = "ai_scouting.pack:ScoutingPack"` em `ai_core.packs` | FR-002 |
| `ScoutingPack.name` | `"scouting"` | FR-002 |
| `ScoutingPack.contract_version` | `"0.1"` | R2 (faixa `>=0.1,<0.2`) |

## `PackManifest` (Fase 4 — clarificação 1)

`PackManifest(name="scouting", version="0.1.0")`. Sem `preferred_flow`, `depends_on`, `requires_collections` e
`config_schema` na Fase 4; os três primeiros-de-domínio (`preferred_flow="rag_first"`,
`requires_collections=["scouting_docs"]`, `config_schema` com o nome da coleção) chegam na Fase 5, com a US5.

## `Lexicon` (`context/lexicon.py` — FR-007, R7)

| Parte | Forma | Regra |
|---|---|---|
| `branches` | id → termos | ids: `lobinho`, `escoteiro`, `senior`, `pioneiro`; termos não ambíguos, com plural, feminino e sinônimos antigos e regionais |
| `ambiguous` | termos | casam e não aplicam filtro de ramo (ex.: "escoteiro" sozinho, "patrulha") |
| `topics` | id → (termos, tipos sugeridos) | cerca de 15 temas (ex.: `lideranca`, `progressao`, `especialidades`, `promessa_e_lei`) |
| `document_types` | id → termos | ids na ordem: `manual`, `programa_educativo`, `por`, `resolucao`, `estatuto`, `guia` |
| `type_signals` | termo → tipos | palavras que apontam tipo sem nomeá-lo (ex.: "competências" → `programa_educativo`, `manual`) |
| `previous_markers` | termos | consulta à versão anterior sem data ("manual anterior", "versão anterior", "antigamente") |

Invariantes (verificadas em `tests/test_lexicon.py`): todo termo já está normalizado (R6); nenhum termo pertence a dois
ramos; nenhum termo de ramo está em `ambiguous`; todo tipo citado por tema ou sinal existe em `document_types`; ids
únicos.

## `Validity` — vigência (FR-005, clarificação 4)

| Campo | Tipo | Regra |
|---|---|---|
| `start` | `date` | início, inclusivo |
| `end` | `date` | fim, inclusivo; `start <= end` (senão `ValueError`) |

| Pergunta | `start` | `end` |
|---|---|---|
| sem período | dia de referência | dia de referência |
| "em 2023", "no ano de 2023", "durante 2023" | 2023-01-01 | 2023-12-31 |
| "em março de 2023" | 2023-03-01 | 2023-03-31 |
| "em 15/03/2023", "em 15 de março de 2023" | 2023-03-15 | 2023-03-15 |
| "ano passado" (dia de referência em 2026) | 2025-01-01 | 2025-12-31 |
| "resolução 3/2023" (ano solto) | dia de referência | dia de referência |

Dia de referência = `view.reference_time` em UTC−03:00, só a data (R5).

## `ScoutingContext` (Key Entity "Scouting Context")

| Campo | Tipo | Regra (R8) |
|---|---|---|
| `branch` | `str \| None` | exatamente um ramo casado → ele; nenhum, vários ou só ambíguo → `None` |
| `topics` | `tuple[str, ...]` | temas casados, na ordem do léxico |
| `document_types` | `tuple[str, ...]` | explícitos; senão sugeridos por sinais e temas; ordem do léxico |
| `validity` | `Validity` | tabela acima |
| `include_superseded` | `bool` | `True` com período ou com marca de versão anterior |
| `previous_version` | `bool` | `True` com marca de versão anterior sem data |

Exemplos de aceite (dia de referência 2026-10-07):

| Pergunta | branch | topics | document_types | validity | superseded | previous |
|---|---|---|---|---|---|---|
| "Quais competências do Pioneiro estão relacionadas à liderança?" (US2 cen. 1) | `pioneiro` | (`lideranca`,) | (`manual`, `programa_educativo`) | 2026-10-07 a 2026-10-07 | não | não |
| "Como funciona a promessa?" (US2 cen. 2) | `None` | (`promessa_e_lei`,) | sugeridos pelo tema | dia | não | não |
| "Qual era a regra em 2023?" (US3 cen. 1) | `None` | () | sugeridos pelo sinal "regra" | 2023-01-01 a 2023-12-31 | sim | não |
| "O que dizia o manual anterior?" (US3 cen. 2) | `None` | () | (`manual`,) | dia | sim | sim |

## Atualização da fatia (`prepare_context` — R12)

```json
{
  "context": {
    "branch": "pioneiro",
    "topics": ["lideranca"],
    "document_types": ["manual", "programa_educativo"],
    "effective_from": "2026-10-07",
    "effective_until": "2026-10-07",
    "include_superseded": false,
    "previous_version": false
  },
  "retrieval_filters": { "…": "ver contracts/retrieval-filters.md" }
}
```

`context` traz todas as chaves (`branch: null` sem ramo); `retrieval_filters` omite `branch` sem ramo e listas vazias.

## Estado

Nenhum. A derivação é função de (pergunta, dia de referência, léxico); a mesma entrada dá a mesma fatia.

# Fase 5 (2026-10-09): US4, US5

## `PackManifest` (Fase 5 — R20)

`name="scouting"`, `version="0.2.0"`, `preferred_flow="rag_first"`, `requires_collections=("scouting",)`,
`config_schema=SCOUTING_CONFIG_SCHEMA`. A coleção lógica é a constante `COLLECTION = "scouting"` (R17).

## Configuração do pack (`packs.yaml` → `ctx.config` — R18)

| Campo | Tipo | Default | Regra (na carga; violação → `ValueError` nomeando o campo, o pack não carrega) |
|---|---|---|---|
| `qdrant_url` | string `^https?://` | `http://localhost:6333` (sem `qdrant_path`) | exclusivo com `qdrant_path` |
| `qdrant_path` | string não vazia | — | Qdrant embutido (testes, desenvolvimento) |
| `index` | string `^[a-z0-9][a-z0-9_-]*$` | `scouting` | alias no Qdrant |
| `embedder` | `"e5"` \| `"hashing"` | `"e5"` | `hashing` só para suítes |
| `embedding_dir` | string não vazia | — | obrigatório com `e5`; com `model.onnx` e `tokenizer.json` dentro |
| `default_limit`, `max_limit` | inteiro ≥ 1 | 5, 30 | `1 ≤ default_limit ≤ max_limit` (`RetrievalConfig` da 103) |

Fora do esquema: a chave do Qdrant, só em `AI_SCOUTING_QDRANT_API_KEY` (FR-012). `additionalProperties: false`.

## Capacidades publicadas (US5, FR-010)

| Hook | Fase 5 |
|---|---|
| `system_prompt` | o prompt da Fase 5 (R21) |
| `prepare_context` | igual à Fase 4 |
| `retrievers` | `[search_docs(ScoutingRetriever(QdrantIndex(...), RetrievalConfig(...)), collection="scouting")]` → tool `scouting.search_docs` |
| `reranker` | `MetadataReranker()` |
| `validators` | `[CitationIntegrityValidator(), ValidityNoticeValidator()]`, nessa ordem |
| `tools` | nenhuma (a recuperação é tool derivada do retriever — 001) |

## Prompt (R21)

Blocos: papel; prioridades de fonte (as cinco, na ordem da US4); citação `[[id]]` pelo identificador depois de `id:`
(ADR-026); sem trechos → conhecimento geral com ressalva (FR-011); vigência; dado, nunca instrução (FR-009); fora do
escotismo.
