# agentic-app — Plataforma Agentic AI (SDD com spec-kit)

Este repositório é o **Spec-Driven Development** da plataforma: `ai-core` (runtime genérico), `ai-generic` (pack de referência)
e `ai-scouting` (pack de domínio escoteiro). Spec-kit 1.0.6, integração Claude em modo skills (`/speckit-*`).

## Onde está cada coisa

| O quê | Onde |
|---|---|
| Princípios (lidos por toda skill do spec-kit) | `.specify/memory/constitution.md` |
| Mapa de módulos, seams e dependências | `specs/README.md` |
| Uma spec por módulo + insumo técnico | `specs/NNN-nome/spec.md` e `specs/NNN-nome/design.md` |
| Decisões arquiteturais | `docs/adr/` |
| Estilo arquitetural (microkernel · monolito modular · hexagonal) e seus motivos | ADR-012 e `docs/relatorio-estilo-arquitetural.md` |
| Fases → specs/user stories | `docs/roadmap.md` |
| Arquitetura original (histórico, "arch-v1") | `docs/archive/architecture-v1.md` |
| Overrides de template do projeto | `.specify/templates/overrides/` |

## Regras para trabalhar neste repositório

1. **Modularidade é inegociável (princípio II).** Antes de mexer numa spec ou em código, leia a seção *Module Boundary* dela e a
   tabela de seams em `specs/README.md`. Nunca referencie internals de outro módulo (nomes de nós, campos de estado interno,
   tabelas, classes privadas) — só seams. Se uma mudança exige editar outra spec, pare: ou um seam está mudando (precisa de ADR)
   ou a fronteira está sendo violada.
2. **`/speckit-plan`**: leia obrigatoriamente o `design.md` da pasta da spec e os ADRs citados. Essas decisões são pré-aprovadas —
   leve-as para `research.md` como "Decision / Rationale (ADR) / Alternatives", sem re-pesquisar. Divergência = ADR novo.
3. **`/speckit-specify` (spec nova)**: escolha o número no bloco do módulo — `0xx` core, `1xx` scouting, `2xx`+ packs futuros — e
   passe `SPECIFY_FEATURE_DIRECTORY=specs/NNN-nome` explicitamente (a numeração automática do spec-kit só faz "maior + 1").
   A seção *Module Boundary* é obrigatória (vem no template do projeto). Registre a spec em `specs/README.md`.
4. **Core agnóstico de domínio (princípio I)**: nada de escotismo em specs, código ou prompts do `0xx`.
5. **Idioma**: conteúdo em português; títulos de seção dos templates em inglês (compatibilidade com as skills).
6. **ADR aceito não se edita**: cria-se outro que o substitui (`docs/adr/README.md`).
7. **Portas e adapters (princípio XIII, ADR-012).** Dentro de cada módulo: `api.py` (seams), `domain/` (políticas puras),
   `ports.py` (portas secundárias), `service.py` e `adapters/` (infraestrutura). I/O, tempo, segredos e trace ficam atrás
   de portas; um módulo só importa o `api.py` de outro; só a composition root (spec 011) — ou o `pack.py`, num pack —
   instancia serviços e adapters. Todo `design.md` tem a seção "Portas e adapters". Porta nova só onde há I/O,
   não-determinismo ou troca prevista.

## Fluxo por spec

```text
/speckit-clarify   → resolve ambiguidades (máx. 5 perguntas) e grava na spec
/speckit-plan      → plan.md, research.md, data-model.md, contracts/, quickstart.md
/speckit-tasks     → tasks.md (limite às user stories da fase, ver docs/roadmap.md)
/speckit-analyze   → consistência entre spec, plano e tarefas
/speckit-implement → executa tasks.md
```

**Spec ativa**: as skills usam `.specify/feature.json` (`{"feature_directory": "specs/NNN-nome"}`), que é local e fica fora do git.
Para trocar de spec: edite esse arquivo ou exporte `SPECIFY_FEATURE_DIRECTORY=specs/NNN-nome`.

## Reescrever um módulo

Ver "Como reescrever um módulo" em `specs/README.md`. Resumo:
- **Grafo do core** → só `specs/005-core-execution-engine/` muda; nomes de nós, estado interno e framework são livres (ADR-011).
  Na prática, troca-se `ai_core/graph/adapters/langgraph/` e preservam-se `api.py` e `domain/` (ADR-012).
- **ai-scouting** → só `specs/1xx-*` mudam; o core enxerga o pack apenas pelo contrato 001 e pelo nome do flow preferido.

## Código

Implementado até agora: `ai-core-contracts` (spec 001, Fase 0) em `ai-core/packages/contracts/`; a distribuição
`ai-core` em `ai-core/packages/core/`, com o Pack Runtime (`ai_core/packs/`, spec 002, Fase 1: US1, US2, US3 cenários
2–4), o trace por requisição (`ai_core/observability/`, spec 009, Fase 1: US1) — seam Trace Sink com eventos tipados,
consulta por requisição, redação de credenciais e backends de memória e JSONL (`ai_core/eval/`, o harness, é Fase 6) —
o Model Router (`ai_core/llm/`, spec 006, Fase 1: US1) — resolução de papel a partir de uma Model Policy, allowlist,
saúde sob demanda, trace por chamada e o provider local do Ollama pela camada compatível com OpenAI (SDK `openai`,
confinado a `adapters/` por import-linter), mais o provider simulado do perfil de teste; OpenAI e OpenRouter são Fase 3
— e o motor de execução (`ai_core/graph/`, spec 005, Fase 1: US1) — seam Execution Engine (`run(grant, request)` →
token, progresso e evento final), o flow `chat` em LangGraph (framework preso a `adapters/langgraph/` por
import-linter) e o grant chegando como `Protocol` estrutural até a 003 existir; `agentic` e `rag_first` são Fases 3 e 5
— e a API HTTP (`ai_core/http/`, spec 008, Fase 1: US1) — chat completions compatível com OpenAI, com e sem streaming
SSE, nas superfícies `/v1` e `/private/v1`, com autenticação e resolução de Assistant atrás de portas até a 003
existir; listagem de modelos, conversas e fila são Fases 2 e 7;
e o pack de referência `ai-generic` em `ai-core/packages/generic/` (spec 010, Fase 1: US1) — prompt de uso geral,
tool nativa `calculate` e validator `non_empty_answer`, descoberto pelo entry point `ai_core.packs` como qualquer pack
externo. O resto dos caminhos-alvo está nos `design.md`, no layout hexagonal do ADR-012.
Decidido em 2026-09-15 (plano da 001): `ai-core/` é subpasta deste repositório nas Fases 0–3 e se separa antes da Fase 4;
Python 3.14 no workspace, piso 3.12 em `ai-core-contracts`; CI em `.github/workflows/` da raiz. O `ai-scouting` segue a
mesma regra: subpasta até existir repositório próprio, dependendo só de `ai-core-contracts`.

O `ai-generic` é o exemplo a copiar num pack novo: piso de Python dos contratos (`>=3.12`, não o 3.14 do core),
dependência pela faixa derivada da `contract_version` (`>=0.1,<0.2`, ADR-014) com `[tool.uv.sources] ... { workspace =
true }`, suíte de conformidade nos próprios testes e zero import do core (import-linter, nas duas direções). Ele é
dependência de desenvolvimento do workspace porque o teste de carga real por entry point roda na suíte do core
(`packages/core/tests/packs/integration/test_packs_generic_entry_point.py`). A etapa de distribuição da conformidade só
verifica a faixa numa instalação normal — no workspace tudo é editável —, então ela vale no ambiente limpo:

```bash
tmp=$(mktemp -d) && uv venv --python 3.12 "$tmp/venv"
uv pip install --python "$tmp/venv/bin/python" ./packages/contracts ./packages/generic pytest
(cd packages/generic && "$tmp/venv/bin/python" -m pytest -q tests) ; rm -rf "$tmp"
```

Verificação dos contratos (a partir de `ai-core/`; roteiro completo no quickstart da 001):

```bash
uv sync
uv run pytest && uv run mypy && uv run ruff check packages && uv run lint-imports
uv run python packages/contracts/tools/check_clean_env.py      # SC-001: pack só com os contratos
```

O workspace exige Python 3.14 (por causa do core); o piso 3.12 dos contratos roda fora dele:
`uv run --no-project --python 3.12 --with ./packages/contracts --with pytest --with pytest-asyncio --with hypothesis
--with packaging pytest packages/contracts/tests`.

Nesta máquina, rode o `uv` com `XDG_DATA_HOME=$HOME/.local/share` (o VSCode snap aponta o XDG para uma pasta que some).
