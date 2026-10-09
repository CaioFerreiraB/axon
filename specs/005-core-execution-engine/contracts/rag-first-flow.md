# Contrato — flow `rag_first` (Fase 5)

Recuperação e rerank determinísticos, portão de cobertura e geração com uma chamada de modelo no caminho coberto (US3,
SC-003); validação como nos outros flows (US4). Decisões em [research.md](../research.md) R35–R48; tipos em
[data-model.md](../data-model.md), seção "Fase 5".

```text
START → prepare_context → retrieve → rerank → gate ─┬─ coberto ──────────────────────────→ generate → validate_answer → END
                                                     ├─ sem cobertura, com controller ─→ controller ⇄ execute_tool → generate …
                                                     ├─ sem cobertura, sem controller ─→ generate (sem trechos) …
                                                     └─ recuperação falhou ─────────────→ END (registro error)
```

| Passo | Regra |
|---|---|
| `retrieve` | abre a sessão de tools com os filtros das fatias; executa cada tool `retrieval` com `{"query", "top_k": candidates}`; status ≠ `ok` → `RetrievalFailed` (`error`), fim sem gerar |
| `rerank` | por pack, `PackHooks.reranker(composition, pack)` com `top_k=passages`; sem reranker, os primeiros `passages`; vários packs → junção estável por score; reranker que levanta → `RerankFailed` (`notice`) |
| `gate` | coberto = há trechos e (sem limiar ou melhor score ≥ limiar); emite `CoverageGate`; coberto → um passo de tool sintético por pack com `fence_chunks` dos trechos que cabem no teto |
| escalada | com `controller` → loop do `agentic` (limite do grant ou 3), transcrição vazia; sem → geração sem trechos + `CoverageInsufficient` (`notice`) |
| `generate` | prompts dos packs + `FENCE_INSTRUCTION` + conversa + passos; uma chamada ao papel `generation` |
| `validate_answer` | os validators dos packs com a Turn View — `generation_context` = os trechos entregues |

| Verificação | Cenário |
|---|---|
| uma chamada de modelo no caminho coberto | SC-003, US3 cen. 1 |
| sem resultado ou abaixo do limiar, com `controller` → loop | US3 cen. 2 |
| idem, sem `controller` → geração sem trechos, `notice` | US3 cen. 3 |
| filtros do pack chegam aos retrievers sem leitura | US3 cen. 4 |
| validators na ordem, `generation_context` = os entregues, inclusive depois do corte pelo teto | US4 cen. 1–2 |
| recuperação que falha → `error`, nenhuma chamada de geração | R37 |
| o modelo vê `· id: <chunk_id>` em cada trecho | ADR-026 |
