# Quickstart — validar o `ai-scouting` (Fase 4: US1, US2, US3)

A partir da raiz do `agentic-app`. Nesta máquina, rode o `uv` com `XDG_DATA_HOME=$HOME/.local/share`. Decisões em
[research.md](research.md); contratos em [contracts/](contracts/).

## 0. Pré-requisitos

```bash
git submodule update --init ai-scouting          # o pack é o submódulo ai-scouting/ (ADR-021)
ssh -T git@github.com                             # o uv busca os contratos no agentic-app (privado) por SSH
```

**Esperado**: `ai-scouting/` com o código; o SSH autentica a sua conta.

## 1. A suíte padrão roda só com os contratos

```bash
cd ai-scouting
uv sync --locked
uv run pytest -v
```

**Esperado**: conformidade, pack, prompt, léxico, derivação, períodos e pureza verdes; `tests/integration` pulado
("ai_core não instalado"). Nenhum pacote `ai_core` no ambiente (`uv pip list | grep ai-core` mostra só
`ai-core-contracts`).

## 2. Ambiente limpo em 3.12 (SC-003, Independent Test de distribuição)

```bash
tmp=$(mktemp -d) && uv venv --python 3.12 "$tmp/venv"
uv pip install --python "$tmp/venv/bin/python" . pytest
"$tmp/venv/bin/python" -m pytest -q tests --ignore=tests/integration ; rm -rf "$tmp"
```

**Esperado**: tudo verde; o relatório de conformidade sem nenhum item — inclusive a etapa de distribuição, que só aqui
(instalação normal) confere a faixa `>=0.1,<0.2`.

## 3. A derivação (US2, US3)

```bash
uv run pytest tests/test_derivation.py tests/test_periods.py -v
uv run python -c "
from datetime import UTC, datetime
from ai_core_contracts.testing import pack_context, turn_view
from ai_scouting.pack import ScoutingPack
import asyncio, json
view = turn_view(question='Quais competências do Pioneiro estão relacionadas à liderança?',
                 reference_time=datetime(2026, 10, 7, 12, tzinfo=UTC))
print(json.dumps(asyncio.run(ScoutingPack().prepare_context(view, pack_context('scouting'))), indent=2))"
```

**Esperado**: a tabela de exemplos do [data-model.md](data-model.md) passa; o comando imprime `branch: pioneiro`,
`topics: [lideranca]`, `document_types: [manual, programa_educativo]`, vigência `2026-10-07` a `2026-10-07`. Com
`reference_time` às 01h UTC de 2026-10-08, o dia ainda é `2026-10-07` (Brasília, R5).

## 4. Fronteiras

```bash
uv run lint-imports
uv run pytest tests/test_purity.py -v
```

**Esperado**: os três contratos `KEPT` (o pack não importa o core; só o `pack.py` compõe; a derivação não alcança
modelo nem MCP); nenhuma chamada de relógio em `context/`.

## 5. Na plataforma (US1 cen. 1–2)

```bash
uv sync --locked --python 3.14 --group platform
uv run --python 3.14 --group platform pytest tests/integration -v
```

**Esperado**: o pack carrega pelo entry point, `enabled`, versão `0.1.0`, contrato `0.1`; a plataforma compõe o prompt
do pack para o Assistant `scouting` (seam `PackHooks`); a conversa (`flow: chat`) responde 200. O teste só usa a
superfície da 011 para packs externos — variáveis `AI_CORE_*` e `platform(profile="test")`.

## 6. Conversa manual com um modelo de verdade (opcional)

Com os arquivos de `~/.config/ai-core/` (servidor local): em `packs.yaml`, acrescente `scouting: { enabled: true }`; em
`assistants.yaml`, um Assistant `scouting` no formato dos outros, com `flow: chat` e `packs: [scouting]`.

```bash
set -a; . ~/.config/ai-core/openrouter.env; . ~/.config/ai-core/dev.env; set +a
uv run --python 3.14 --group platform ai-core packs list
uv run --python 3.14 --group platform ai-core serve
# noutro terminal:
curl -s http://127.0.0.1:8000/private/v1/chat/completions -H "Authorization: Bearer $AI_CORE_DEV_API_KEY" \
  -H 'Content-Type: application/json' \
  -d '{"model":"scouting","messages":[{"role":"user","content":"Qual resolução define a idade do Ramo Pioneiro?"}]}' \
  | jq -r '.choices[0].message.content'
```

**Esperado**: `packs list` mostra `scouting  enabled  0.1.0`; a resposta declara que nenhum documento institucional foi
consultado, **não** cita número de resolução nem trecho, e recomenda confirmar na fonte oficial (US1 cen. 4). É
verificação de comportamento, não teste automatizado — medir é da 105 (princípio X).

## 7. CI do `ai-scouting` (uma vez)

```bash
ssh-keygen -t ed25519 -N '' -C ai-scouting-ci -f /tmp/ai-scouting-ci
gh repo deploy-key add /tmp/ai-scouting-ci.pub --repo CaioFerreiraB/agentic-app --title ai-scouting-ci   # só leitura
gh secret set AGENTIC_APP_DEPLOY_KEY --repo CaioFerreiraB/ai-scouting < /tmp/ai-scouting-ci
rm /tmp/ai-scouting-ci /tmp/ai-scouting-ci.pub
```

**Esperado**: os quatro jobs do `ci.yml` (lint, test em 3.12 e 3.14, clean-env, platform) verdes no primeiro push.

# Fase 5 (2026-10-09): US4, US5

Pré-requisitos: a 005 US3–US4 implementada e a tag do core `v0.2.0` (R16, R22).

## 8. Suíte padrão e conformidade

```bash
uv run pytest && uv run mypy && uv run ruff check && uv run lint-imports
```

Esperado: os testes da configuração do pack, do manifest da Fase 5, das capacidades e do prompt (as cinco prioridades
na ordem — US4) passam; a conformidade da 001 passa com `config={"qdrant_path": …, "embedder": "hashing"}`.

## 9. US5 na plataforma (sem rede)

```bash
uv run --python 3.14 --group platform pytest tests/integration/test_rag.py
```

Esperado: uma pergunta coberta pelo corpus sintético responde 200, com **uma** chamada de modelo no trace da requisição
(SC-004) e a citação `[1]` com documento, versão, seção e página (US5 cen. 1).

## 10. Conversa real (opcional)

Com o índice `scouting` do corpus real (102 quickstart §5), o e5 em `~/.cache/ai-scouting/e5-small` e um modelo de
geração (Ollama ou OpenRouter): `packs.yaml` com `config: {qdrant_url: http://localhost:56333, embedding_dir:
~/.cache/ai-scouting/e5-small}`, Assistant `scouting` concedendo a coleção `scouting`, `ai-core serve`, e as perguntas do
quickstart da 103. Esperado: respostas com `[n]` e a lista de citações; para "receita de bolo de cenoura", o portão
escala ou a resposta vem com a ressalva de "nenhum documento oficial" e a marca de não fundamentada.
