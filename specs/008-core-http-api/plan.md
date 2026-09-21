# Implementation Plan: API HTTP — chat completions compatível com OpenAI

**Branch**: `008-core-http-api` | **Date**: 2026-09-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/008-core-http-api/spec.md`

**Architecture inputs** *(PROJECT OVERRIDE — agentic-app)*: before filling Technical Context, READ
`/specs/008-core-http-api/design.md` (including its "Portas e adapters" section) and every ADR listed
in the spec's Module Boundary, plus ADR-012 (architectural style). Decisions recorded there are
**pre-approved**: carry them into this plan and into `research.md` as
"Decision / Rationale (ADR-xxx) / Alternatives", do not re-research them. Any deviation requires a
new ADR in `docs/adr/` and must be listed in Complexity Tracking.

Insumos lidos: [design.md](design.md), ADR-002, ADR-012, ADR-013; Execution Engine da 005, Model Router da 006, Pack
Hooks da 002 e Trace Sink da 009, todos implementados. Consumidores conferidos: clientes externos (Open WebUI, SDKs) e
011 (monta a app e injeta os seams). **Sem divergência do `design.md`**: a única diferença é interna e preserva o
arquivo que ele nomeia — a construção do chunk é pura, em `domain/openai_chunks.py`, e `adapters/sse.py` fica com a
serialização e a conexão ([research.md](research.md) R4). Nenhum ADR novo.

## Summary

Entregar a rota de **chat completions compatível com OpenAI**, com e sem streaming, nas superfícies `/v1` e
`/private/v1`: a requisição vira um `ExecutionRequest` do motor (005), os eventos voltam traduzidos em chunks SSE, e o
identificador de requisição do trace acompanha a resposta. O Principal e o resolvedor de grant entram por portas que
este módulo publica, para que a autenticação e a resolução de Assistant da 003 cheguem na Fase 2 como troca de adapter.
Escopo da Fase 1: **US1**, mais FR-010 e as rejeições de campo de ampliação e de data de referência
([research.md](research.md) R8, R9). Listagem de modelos, conversas, CRUD, saúde e fila ficam para as fases deles.

## Technical Context

**Language/Version**: Python 3.14 (módulo da distribuição `ai-core`, `requires-python = ">=3.14"`)

**Primary Dependencies**: `ai_core.graph.api` (005), `ai_core_contracts` (mensagens); **nova** — `fastapi>=0.141,<1`,
confinada a `ai_core/http/adapters/` por contrato de import (R4, R11); `httpx` como dependência de desenvolvimento, que
é o que o cliente de teste do framework usa

**Storage**: N/A nesta fase — conversas são Fase 2 (R9)

**Testing**: pytest + pytest-asyncio; `domain/` puro (mapeamento da requisição e construção de chunk); suíte ponta a
ponta pelo cliente de teste do framework, com motor real, Pack Runtime real, `ai-generic` e provider simulado (R10)

**Target Platform**: processo do core na imagem Linux ARM64

**Project Type**: adapter primário da plataforma, dentro do monolito modular (`ai-core`)

**Performance Goals**: SC-003 — primeiro sinal em até 2 s. A API não acumula: cada evento do motor vira um chunk
escrito na conexão no mesmo instante, e o progresso de `generate` (005) chega antes da primeira chamada de modelo

**Constraints**: nenhum tipo do framework HTTP fora de `adapters/` (princípio XIII); a API não aceita data de
referência em nenhuma superfície (FR-012, ADR-013); erro de autorização é 404, nunca 403 (FR-009); a API não conhece
flows, packs, providers nem políticas de tool; nenhuma lógica de agente vive aqui (princípio XI)

**Scale/Scope**: 1 módulo — `ports.py` (4 Protocols), `domain/` com 2 arquivos, `service.py`, e `adapters/` com a
fábrica da app, as duas superfícies, a rota de chat completions, a serialização SSE e os adapters de desenvolvimento;
1 rota das ~15 do `design.md`

Nenhum `NEEDS CLARIFICATION`: as quatro perguntas abertas foram resolvidas em 2026-09-21 e estão em
[research.md](research.md) R1, R2, R5 e R6.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Resultado | Evidência |
|---|---|---|
| I. Núcleo agnóstico | ✅ | A API transporta mensagens e eventos; nenhum termo de domínio, nenhum prompt |
| II. Seams | ✅ | Consome o `api.py` da 005 e declara como `Protocol` o que exige da 003. Não expõe seam Python: o seam é a própria API HTTP, com suíte ponta a ponta |
| III. O core orquestra | ✅ | A API não decide topologia nem chama packs: entrega a requisição ao motor e traduz o que volta |
| IV. Assistant é a fronteira | ✅ | O grant vem resolvido de fora (R2); campos de ampliação (`tools`, `functions`) são rejeitados antes de qualquer execução (R8); Assistant não autorizado responde 404 |
| V. Determinismo | ✅ | Mapeamento da requisição e construção de chunk são funções puras; nenhuma decisão por modelo |
| VI. Conteúdo externo | ✅ | O corpo da requisição é dado: só campos conhecidos entram no `ExecutionRequest`, e o resto é rejeitado em vez de repassado |
| VII. Falha fechada | ✅ | Campo proibido, Assistant inexistente e requisição inválida falham com 4xx **antes** de qualquer chamada de modelo; falha depois do stream aberto encerra o stream com motivo (R6) |
| VIII. Modelos por papel | ✅ | O modelo vem do id `<assistant>/<modelo>` e é conferido pela allowlist do grant, na 006 — a API não escolhe modelo |
| IX. Proveniência | ✅ | Citações e marcações do evento final chegam ao cliente no chunk final, sem edição |
| X. Medir antes de calibrar | ✅ | Nenhum número calibrável nesta fase: limite de concorrência e fila são Fase 7, com medição no hardware alvo |
| XI. Streaming e independência da interface | ✅ | É o ponto da fase; nenhuma lógica de agente na API, e nenhuma dependência de interface gráfica |
| XII. Simplicidade | ✅ | Sem conversas, sem fila, sem saúde agregada, sem CRUD — cada um adiado para a fase que o usa (R9) |
| XIII. Portas e adapters | ✅ | Ver gate abaixo |

**Module boundary gate** *(PROJECT OVERRIDE — principle II, mandatory)*:

- [x] Source changes stay inside this module's paths — `ai-core/packages/core/src/ai_core/http/**` e
  `ai-core/packages/core/tests/http/**`; fora dele, apenas `ai-core/packages/core/pyproject.toml` (dependência
  `fastapi`) e `ai-core/pyproject.toml` (import-linter, pytest, `httpx` no grupo de desenvolvimento)
- [x] Every consumed seam is listed with its owner spec; no internals of other modules are used —
  `ExecutionEngine`, `ExecutionRequest`, `ExecutionGrant` e os eventos de `ai_core.graph.api` (005); `Message` de
  `ai_core_contracts` (001). Em `src/`, nada de 002, 006 ou 009: o motor é a única porta de entrada. A suíte de
  integração monta o caminho real (Pack Runtime, Model Router, trace) de propósito — é o que a SC-002 pede
- [x] Every seam this module exposes has a conformance test planned — o seam é a API HTTP:
  `tests/http/contract/test_chat_completions.py` (formato OpenAI, streaming, erros) e
  `tests/http/integration/test_http_end_to_end.py` (SC-002, conversa completa via HTTP)
- [x] No seam changes — a API nasce aqui. As formas exigidas da 003 entram como `Protocol` deste módulo, o que **não**
  move a posse dos seams Authenticator/GrantResolver, que continuam da 003 (R1, R2)
- [x] Import boundaries (import-linter) cover the new code — contratos novos do R11

**Ports & adapters gate** *(PROJECT OVERRIDE — principle XIII, ADR-012, mandatory)*:

- [x] The module follows `api.py` / `domain/` / `ports.py` / `service.py` / `adapters/` — sem `api.py`, por decisão do
  `design.md`: este módulo não expõe seam Python, e sim a própria superfície HTTP
- [x] `api.py`, `domain/`, `ports.py` and `service.py` import no infrastructure framework — nenhum deles importa
  `fastapi` ou `starlette`; o contrato de import-linter do R11 barra
- [x] Other modules are imported only through their `api.py` — só `ai_core.graph.api` e `ai_core_contracts`
- [x] All I/O, time, randomness, secrets and trace go through a secondary port; `domain/` does no I/O —
  aleatoriedade pela porta `RequestIds` (R7); autenticação e resolução de grant por porta; `domain/` é puro
- [x] Every secondary port exists for I/O, non-determinism or a planned swap — `Authenticator` e `GrantResolver` por
  troca prevista (anônimo → 003 na Fase 2); `RequestIds` e `Clock` por não-determinismo (o campo `created` do formato
  OpenAI faz esta fase ler o relógio). `ConversationStore` e `HealthProvider` são da Fase 2 (R9)
- [x] Every secondary port has an in-memory adapter and a conformance suite that also runs against the real adapter —
  os adapters desta fase **são** os de memória; a conformidade roda contra eles e volta a rodar contra os da 003
- [x] Services and adapters of other modules are instantiated only in the composition root — a 008 não instancia nada
  de outro módulo: recebe o motor pronto. Quem monta a app é a 011 (e os testes)

**Resultado do gate (antes da Phase 0)**: PASS.

## Project Structure

### Documentation (this feature)

```text
specs/008-core-http-api/
├── spec.md
├── design.md
├── plan.md              # este arquivo
├── research.md
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── chat-completions.md   # a rota: corpo aceito, rejeições, resposta com e sem streaming
│   ├── sse-format.md         # ExecutionEvent → chunk OpenAI, e o encerramento
│   └── ports.md              # Authenticator, Principal, GrantResolver, RequestIds
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
ai-core/
├── pyproject.toml                       # contratos novos de import-linter (R11); httpx no grupo dev
└── packages/core/
    ├── pyproject.toml                   # dependência fastapi>=0.141,<1 (R4)
    ├── src/ai_core/http/
    │   ├── __init__.py                  # docstring: o seam deste módulo é a própria API HTTP
    │   ├── ports.py                     # Principal, Authenticator, GrantResolver, RequestIds + erros
    │   ├── domain/
    │   │   ├── __init__.py
    │   │   ├── chat_request.py          # corpo OpenAI → (modelo, mensagens, streaming); rejeições (R8)
    │   │   └── openai_chunks.py         # ExecutionEvent → chunk/resposta OpenAI — puro (R4)
    │   ├── service.py                   # ChatService: resolve grant, chama o motor, devolve chunks
    │   └── adapters/
    │       ├── __init__.py
    │       ├── app.py                   # fábrica da app, chamada pela composition root (011)
    │       ├── chat.py                  # rota de chat completions, nas duas superfícies
    │       ├── sse.py                   # serialização `data: …` e a conexão
    │       └── development.py           # Authenticator anônimo e RequestIds — perfil de desenvolvimento
    └── tests/http/
        ├── conftest.py                  # app montada em processo, motor real, provider simulado
        ├── http_testkit.py              # fábricas compartilhadas
        ├── unit/                        # domain/ puro: mapeamento da requisição e construção de chunk
        ├── contract/                    # a rota: formato OpenAI, streaming, rejeições, 404
        └── integration/                 # SC-002: conversa ponta a ponta só via HTTP
```

**Structure Decision**: layout do `design.md` (`ai_core/http/`), sem `api.py` — o seam é a superfície HTTP. Dos
arquivos que o `design.md` lista, nascem `app.py`, `sse.py` e a rota de chat; `auth.py`, `public.py`, `private.py`,
`openai_compat.py` (listagem de modelos) e os adapters de conversa chegam com as fases deles. As duas superfícies são
o mesmo roteador montado em dois prefixos, com a dependência de autenticação parametrizada — é o que o `design.md`
descreve e evita duplicar rota.

## Seam Notes for Consumers

| Consumidor | O que precisa saber |
|---|---|
| 011 (Fase 1) | Montar a app com `create_app(engine=…, authenticator=…, grants=…, request_ids=…)` e servi-la. Na Fase 1, injetar `AnonymousAuthenticator` e um `GrantResolver` montado da configuração; o nome do adapter anônimo aparece no boot, para não ser confundido com produção |
| 003 (Fase 2) | Fornecer o verificador real e o resolvedor de grant: basta satisfazer `Authenticator` e `GrantResolver`; nenhuma rota muda. A regra 404-não-403 já está no caminho da requisição |
| Clientes externos | `POST /v1/chat/completions` e `POST /private/v1/chat/completions`, formato OpenAI. `stream: true` devolve `chat.completion.chunk` e `[DONE]`; o identificador de requisição vem em `X-Request-Id` e no `id` da resposta |
| 005 | Recebe `ExecutionRequest` com o identificador de requisição que a API gerou; a API nunca preenche a data de referência (FR-012) |

## Constitution Check — pós-design (Phase 1)

Reavaliado com [data-model.md](data-model.md), [contracts/](contracts/) e [quickstart.md](quickstart.md): **PASS**.

- IV: `contracts/chat-completions.md` lista os campos aceitos e fixa que qualquer outro campo de capacidade é rejeitado
  com 400 nomeando-o — a ampliação é barrada na borda, antes do motor.
- VII: a tabela de falhas do [data-model.md](data-model.md) separa o que acontece antes do stream (status HTTP) do que
  acontece depois (chunk final com motivo), sem nenhum caso de conexão pendurada.
- XI: `contracts/sse-format.md` fixa que cada evento do motor vira um chunk escrito na hora, sem acumular.
- XIII: três portas, todas por troca prevista ou não-determinismo; `fastapi` só em `adapters/`, verificado por
  import-linter.

## Complexity Tracking

> Nenhuma violação. Complexidade adicional justificada (princípio XII):

| Complexidade | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Porta `RequestIds` para gerar identificador (R7) | o identificador aparece na resposta e é a chave do trace; aleatoriedade é porta por princípio XIII | gerar no adapter deixaria a suíte casando por expressão regular e o elo resposta↔trace sem verificação exata |
| `Principal` e `GrantResolver` como `Protocol` daqui (R1, R2) | os donos são da 003, que é Fase 2 | montar o grant na API poria a fronteira de isolamento no adapter primário; antecipar a 003 criaria código sem spec |
| Construção de chunk separada da escrita (R4) | as regras de formato que quebram cliente são puras e merecem teste sem servidor | tudo no adapter exigiria subir servidor para verificar cada regra de formato |
