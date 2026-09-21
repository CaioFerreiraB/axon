# Implementation Plan: Bootstrap e composition root — boot, perfis e plataforma em memória

**Branch**: `011-core-bootstrap` | **Date**: 2026-09-21 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/011-core-bootstrap/spec.md`

**Architecture inputs** *(PROJECT OVERRIDE — agentic-app)*: before filling Technical Context, READ
`/specs/011-core-bootstrap/design.md` (including its "Portas e adapters" section) and every ADR listed
in the spec's Module Boundary, plus ADR-012 (architectural style). Decisions recorded there are
**pre-approved**: carry them into this plan and into `research.md` as
"Decision / Rationale (ADR-xxx) / Alternatives", do not re-research them. Any deviation requires a
new ADR in `docs/adr/` and must be listed in Complexity Tracking.

Insumos lidos: [design.md](design.md), ADR-009, ADR-012, ADR-013; e os seis módulos já implementados — contratos
(001), Pack Runtime (002), motor (005), Model Router (006), API HTTP (008) e trace (009). Consumidores: o operador e a
CI. **Sem divergência do `design.md`**: a única diferença é de escopo — `health.py` e os subcomandos contribuídos por
módulo são da Fase 2, e o `assistants.yaml` que o design previa como armazenamento da 003 nasce aqui, lido por este
módulo, até que a 003 exista ([research.md](research.md) R4, R9). Nenhum ADR novo.

## Summary

Entregar a composition root: carregar a configuração do operador, validar o perfil de adapters, conduzir o boot por
**etapas declaradas** — configuração → adapters → packs → motor → API —, cada uma com política de falha própria, e
servir a aplicação com `ai-core serve`. Dois perfis: `memory` (Ollama de verdade, trace em arquivo) e `test`
(plataforma inteira em memória, provider simulado, relógio fixo), este último **parte da distribuição**, para que
qualquer suíte monte a plataforma com uma chamada. É o módulo que amarra os seis já prontos e substitui as montagens
manuais que hoje existem nas suítes de 005 e 008. Escopo da Fase 1: **US1, US2 (perfil em memória) e US3**.

## Technical Context

**Language/Version**: Python 3.14 (módulo da distribuição `ai-core`, `requires-python = ">=3.14"`)

**Primary Dependencies**: os `api.py`, `service.py` e `adapters/` de 002, 005, 006, 008 e 009 — **este é o único
módulo autorizado a importá-los** (princípio XIII); `pyyaml` (já presente, usado pela 002); **nova** —
`uvicorn>=0.53,<1`, para o `serve` (R5)

**Storage**: arquivos de configuração montados na imagem (`packs.yaml`, `assistants.yaml`) e variáveis de ambiente;
nenhum armazenamento persistente nesta fase

**Testing**: pytest + pytest-asyncio; sequência e políticas de falha verificadas com etapas de teste, sem plataforma;
conversa ponta a ponta pela aplicação montada no perfil `test` (R10)

**Target Platform**: processo do core na imagem Linux ARM64

**Performance Goals**: boot sem I/O além de ler dois arquivos e descobrir entry points; nenhum adapter é instanciado
durante a execução de uma requisição (US1 cenário 5)

**Constraints**: nenhum outro módulo importa este (contrato de import-linter); a ordem de boot é dado, não código
(R1); um único relógio atende todos os módulos com porta de tempo (FR-008, ADR-013); o perfil de teste não fala com
rede nem com serviço externo (FR-014, SC-003)

**Scale/Scope**: 1 módulo — `ports.py`, `settings.py`, `profiles.py`, `grants.py`, `wiring.py`, `lifecycle.py` e
`cli.py`; 2 perfis dos 3; 5 etapas de boot das 7

Nenhum `NEEDS CLARIFICATION`: as quatro perguntas abertas foram resolvidas em 2026-09-21 e estão em
[research.md](research.md) R1, R4, R5 e R7.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Resultado | Evidência |
|---|---|---|
| I. Núcleo agnóstico | ✅ | O bootstrap lê nomes de pack e de Assistant como dado; nenhum domínio aparece em código ou configuração de exemplo |
| II. Seams | ✅ | Não expõe seam Python. Consome os `api.py` e, **por exceção declarada**, os `service.py` e `adapters/` de todos os módulos — é o que o ADR-012 reserva à composition root |
| III. O core orquestra | ✅ | O bootstrap não executa nada: monta e entrega. A topologia continua do motor |
| IV. Assistant é a fronteira | ✅ | O grant é montado a partir de `assistants.yaml` (R4): a fronteira é configuração, não código. O modelo pedido no id só vale dentro da allowlist do Assistant |
| V. Determinismo | ✅ | Validação de configuração, de perfil e a sequência de etapas são puras e testáveis sem plataforma |
| VI. Conteúdo externo | ✅ | Configuração do operador é dado validado, com erro que nomeia o campo; segredo nunca aparece em log ou mensagem (FR-009, Fase 3 com os providers remotos) |
| VII. Falha fechada | ✅ | É o ponto da spec: configuração e perfil inválidos impedem o boot; pack em erro degrada e o resto atende (FR-003, SC-004) |
| VIII. Modelos por papel | ✅ | `assistants.yaml` declara modelo por papel e allowlist, que viram a Model Policy da 006 |
| IX. Proveniência | N/A | Sem retrieval nesta fase |
| X. Medir antes de calibrar | ✅ | Nenhum número calibrável: prazo de encerramento é configuração do operador, não valor de qualidade |
| XI. Streaming e independência da interface | ✅ | O `serve` só abre a porta; a API já entrega streaming, e nenhuma lógica de agente vive aqui |
| XII. Simplicidade | ✅ | Sem container de injeção, sem saúde agregada, sem perfil persistente, sem subcomandos de módulo — cada um na fase que o usa (R2, R9) |
| XIII. Portas e adapters | ✅ | Ver gate abaixo |

**Module boundary gate** *(PROJECT OVERRIDE — principle II, mandatory)*:

- [x] Source changes stay inside this module's paths — `ai-core/packages/core/src/ai_core/bootstrap/**` e
  `ai-core/packages/core/tests/bootstrap/**`; fora dele, apenas `ai-core/packages/core/pyproject.toml` (dependência
  `uvicorn` e o ponto de entrada `ai-core`) e `ai-core/pyproject.toml` (import-linter, pytest)
- [x] Every consumed seam is listed with its owner spec; no internals of other modules are used — consome os `api.py`
  de 002, 005, 006, 008 e 009 **e**, por exceção do princípio XIII, o `service.py` e os `adapters/` de cada um. É o
  único módulo autorizado, e o contrato de import-linter garante que continue sendo
- [x] Every seam this module exposes has a conformance test planned — não expõe seam Python; o que expõe é o processo:
  `tests/bootstrap/contract/test_boot_sequence.py` (ordem e políticas de falha) e
  `tests/bootstrap/integration/test_platform_test_profile.py` (plataforma inteira, conversa por HTTP)
- [x] No seam changes — nenhum. Este módulo só consome
- [x] Import boundaries (import-linter) cover the new code — contratos novos do R11: nenhum módulo importa
  `ai_core.bootstrap`, e cada módulo continua proibido de importar `service.py`/`adapters/` dos outros

**Ports & adapters gate** *(PROJECT OVERRIDE — principle XIII, ADR-012, mandatory)*:

- [x] The module follows `api.py` / `domain/` / `ports.py` / `service.py` / `adapters/` — **não**, e é deliberado: o
  `design.md` fixa um layout próprio para a composition root (`settings.py`, `profiles.py`, `wiring.py`,
  `lifecycle.py`, `cli.py`), porque ela não é um módulo de domínio e não expõe seam. As regras puras (validação de
  configuração e de perfil, sequência) ficam separadas das que fazem I/O, e é isso que a suíte exercita
- [x] `api.py`, `domain/`, `ports.py` and `service.py` import no infrastructure framework — aqui a regra se inverte
  por definição: este módulo importa tudo, inclusive `uvicorn`, e é o único que pode
- [x] Other modules are imported only through their `api.py` — exceção declarada do princípio XIII: só a composition
  root importa também `service.py` e `adapters/`
- [x] All I/O, time, randomness, secrets and trace go through a secondary port; `domain/` does no I/O — a leitura de
  configuração passa pela porta `ConfigSource`, com adapter de ambiente e adapter em memória
- [x] Every secondary port exists for I/O, non-determinism or a planned swap — só `ConfigSource`, por I/O
- [x] Every secondary port has an in-memory adapter and a conformance suite that also runs against the real adapter —
  `InMemoryConfigSource` × `EnvConfigSource`
- [x] Services and adapters of other modules are instantiated only in the composition root — é **este** módulo

**Resultado do gate (antes da Phase 0)**: PASS.

## Project Structure

### Documentation (this feature)

```text
specs/011-core-bootstrap/
├── spec.md
├── design.md
├── plan.md              # este arquivo
├── research.md
├── data-model.md
├── quickstart.md
├── checklists/requirements.md   # 16/16, de 2026-09-14
├── contracts/
│   ├── boot-sequence.md      # etapas, políticas de falha, encerramento
│   ├── profiles.md           # portas exigidas, perfis memory e test, validação
│   └── configuration.md      # packs.yaml (002), assistants.yaml (aqui) e ambiente
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
ai-core/
├── pyproject.toml                       # contratos novos de import-linter (R11)
└── packages/core/
    ├── pyproject.toml                   # uvicorn; [project.scripts] ai-core
    ├── src/ai_core/bootstrap/
    │   ├── __init__.py                  # docstring: a única spec que importa service/adapters de outros módulos
    │   ├── ports.py                     # ConfigSource
    │   ├── settings.py                  # Settings do operador: validação pura + adapters de origem
    │   ├── profiles.py                  # portas exigidas, perfis `memory` e `test`, validação do perfil
    │   ├── grants.py                    # assistants.yaml → resolvedor de grant (porta da 008)
    │   ├── wiring.py                    # constrói Platform: packs, trace, router, motor, app
    │   ├── lifecycle.py                 # etapas declaradas, execução com política de falha, encerramento inverso
    │   └── cli.py                       # `ai-core serve`
    └── tests/bootstrap/
        ├── conftest.py
        ├── bootstrap_testkit.py
        ├── unit/                        # settings, perfis, grants, sequência com etapas de teste
        ├── contract/                    # ordem de boot, falha fechada, encerramento
        └── integration/                 # plataforma inteira no perfil `test`, conversa por HTTP
```

**Structure Decision**: layout do `design.md`. `health.py` não nasce nesta fase (US5 é Fase 2). O perfil `test` fica
em `profiles.py`, dentro da distribuição (R7) — é o que permite a um pack externo montar a plataforma.

## Seam Notes for Consumers

| Consumidor | O que precisa saber |
|---|---|
| Operador | `ai-core serve` sobe a plataforma; a configuração vem de `packs.yaml`, `assistants.yaml` e variáveis de ambiente. Erro de configuração ou de perfil impede o boot e nomeia o campo; pack em erro aparece no relatório de boot e o resto atende |
| Suítes de 005 e 008 | Podem trocar a montagem manual por `platform(profile="test")`; o perfil devolve a plataforma inteira com provider simulado e relógio fixo |
| Packs externos | O perfil `test` é parte da distribuição: a suíte de um pack pode subir a plataforma de verdade e conversar com seu pack por HTTP |
| 003 (Fase 2) | Assume `assistants.yaml` e passa a fornecer o resolvedor de grant e o autenticador; o bootstrap troca o adapter e a etapa de validação de Assistants entra na lista |
| 007 (Fase 3) | Acrescenta a etapa de registry MCP à lista, sem tocar na sequência |

## Constitution Check — pós-design (Phase 1)

Reavaliado com [data-model.md](data-model.md), [contracts/](contracts/) e [quickstart.md](quickstart.md): **PASS**.

- VII: `contracts/boot-sequence.md` fixa a política por etapa e o que acontece em cada falha; a tabela de falhas do
  data-model cobre configuração inválida, perfil incompleto, pack em erro e falha de etapa crítica.
- XIII: a exceção deste módulo está declarada e é verificada nos dois sentidos pelo import-linter — ninguém importa o
  bootstrap, e nenhum módulo importa internals de outro.
- IV: o grant sai de `assistants.yaml`; `contracts/configuration.md` fixa que o modelo pedido no id de modelo só vale
  se a allowlist do Assistant permitir — restringir, nunca ampliar.

## Complexity Tracking

> Nenhuma violação. Complexidade adicional justificada (princípio XII):

| Complexidade | Why Needed | Simpler Alternative Rejected Because |
|---|---|---|
| Etapas de boot como valores (R1) | a ordem e a política de falha são requisito (FR-002, FR-003) e precisam ser verificáveis sem plataforma | função linear espalharia a política pelas chamadas e seria reescrita a cada fase |
| Perfil como conjunto de fábricas, com lista de portas exigidas (R6) | FR-004 manda invalidar perfil incompleto **antes** do boot | confiar no erro de construção faria a falha aparecer tarde e sem nomear a porta |
| `assistants.yaml` lido aqui antes de a 003 existir (R4) | a API resolve `<assistant>/<modelo>` desde a Fase 1 | Assistant em código contraria o princípio IV; por ambiente, o formato seria reinventado na Fase 2 |
