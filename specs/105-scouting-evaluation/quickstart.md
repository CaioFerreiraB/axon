# Quickstart — 105 Scouting Evaluation, Fase 6 (infraestrutura e semente)

Roteiro de validação. Contratos em [contracts/](contracts/); decisões em [research.md](research.md). Tudo dentro de
`ai-scouting/`, com `XDG_DATA_HOME=$HOME/.local/share` nesta máquina.

## 1. Suíte padrão (só os contratos)

```bash
uv run pytest && uv run mypy && uv run ruff check && uv run lint-imports
```

Esperado: as tabelas de [domain-metrics.md](contracts/domain-metrics.md) passam; `tests/eval/test_golden.py` aceita
`eval/golden.yaml` (regras 1–7 de [golden-set.md](contracts/golden-set.md)); a conformidade da 001 aceita as três
métricas; `lint-imports` mantém o `eval` entre `pack` e os demais.

## 2. Integração com a plataforma (grupo `platform`)

```bash
uv run --python 3.14 --group platform pytest tests/integration
```

Esperado: `ai-core eval run` (em subprocesso) roda a semente sem item inválido; uma rodada, com o Qdrant embutido e o
embedder de teste, traz `scouting:context_accuracy`, `scouting:current_document_rate` e `scouting:validity_notice_rate` no
relatório.

## 3. A rodada da CI, local

```bash
docker run -d --rm --name eval-qdrant -p 6333:6333 qdrant/qdrant:v1.19.2
uv run ai-scouting-corpus model fetch .cache/e5
AI_SCOUTING_QDRANT_URL=http://localhost:6333 AI_SCOUTING_EMBEDDING_DIR=.cache/e5 \
  uv run ai-scouting-corpus ingest corpus/corpus.yaml
AI_CORE_PROFILE=test AI_CORE_PACKS_FILE=eval/packs.yaml AI_CORE_ASSISTANTS_FILE=eval/assistants.yaml \
  uv run --python 3.14 --group platform ai-core eval run \
    --golden eval/golden.yaml --baseline eval/baseline.json --report .cache/report.json
echo $?   # 0
```

Esperado: as métricas de recuperação, as três de domínio e as de operação; comparação com a linha de base sem
`REGRESSÃO`; saída 0. A geração é o provider simulado do perfil `test` (resposta fixa, sem citação): as métricas de
geração e citação aparecem, mas não barram.

**Prova de regressão (US2)**: numa cópia de `eval/golden.yaml`, trocar o `chunk_id` esperado de um item pelo de outra
regra — `recall@5` cai e, contra a linha de base, a saída é 1, nomeando a métrica e o delta.

**Linha de base da semente** (2026-10-13, `eval/baseline.json`; corpus real com 413 trechos, e5, Qdrant `v1.19.2`,
perfil `test`; ingestão em ~40 s, rodada em ~4 s; refeita do zero num Qdrant novo, deltas zero):

| Métrica | Valor | n | Barra? |
|---|---|---|---|
| `recall@5` / `recall@20` | 0,8889 / 0,8889 | 9 | sim |
| `mrr` | 0,7222 | 9 | sim |
| `delivered_recall` | 0,8889 | 9 | sim |
| `rerank_gain` | 0,0000 | 9 | sim |
| `scouting:context_accuracy` | 0,9000 | 10 | sim |
| `scouting:current_document_rate` | 1,0000 | 9 | sim |
| `scouting:validity_notice_rate` | ausente | 0 | não |
| `expected_citation_recall` | 0,0000 | 9 | não (gerador simulado não cita) |

O único item sem a evidência entre os candidatos é o s09 ("Quais nós o lobinho aprende…"): o manual aparece, mas não
o trecho `#7@p63` — "nós" normalizado é "nos", palavra vazia do BM25. O `context_accuracy` abaixo de 1 vem do s02 e do
s03, cujos temas esperados (`gestao_do_grupo` para UEL, `promessa_e_lei` para a Lei do Lobinho) o léxico não reconhece.
Os dois são achados reais, registrados para a calibração e a curadoria — nenhum número foi ajustado sobre eles.

## 4. Gerar ou regravar a linha de base (deliberado)

Mesmo comando do passo 3 com `--update-baseline`; com regressão, só com `--force`. O commit diz por quê.

## 5. Rodada manual com modelo real (fora da CI)

```bash
AI_CORE_PROFILE=memory AI_CORE_PACKS_FILE=eval/packs.yaml AI_CORE_ASSISTANTS_FILE=eval/assistants.yaml \
  uv run --python 3.14 --group platform ai-core eval run \
    --golden eval/golden.yaml --judge openrouter/<modelo> --report .cache/real.json --annotate "máquina, RAM"
```

Com o Ollama local (`qwen3:1.7b`) e a chave do OpenRouter no ambiente (carregada sem eco). Esperado: fidelidade,
citação e aviso de vigência com valores reais e variância do juiz. Nenhuma decisão de calibração sai daqui enquanto o
conjunto for a semente (FR-001).

## 6. CI

Num PR que muda `corpus/`, `src/ai_scouting/{rag,prompts,context,eval}/`, `pack.py`, `eval/`, `pyproject.toml` ou
`uv.lock`, o job `eval` roda o passo 3 com Qdrant de serviço e o e5 do cache; o relatório fica como artefato. Um PR que
só muda `README.md` não dispara o job.
