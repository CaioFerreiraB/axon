# Design — 010 Pack genérico

> Insumo técnico pré-aprovado para `/speckit-plan`. Origem: arch-v1 §30, Parte IX; ADR-004.

## Localização

```text
axon-ai/packages/generic/
├── pyproject.toml       # distribuição ai-generic; entry point ai_core.packs
└── src/ai_generic/
    ├── pack.py
    ├── tools/
    └── prompts/
```

> Atualizado na clarificação de 2026-09-17: a pasta é `packages/generic/` (cabe no `members = ["packages/*"]` criado na
> Fase 0), não `packs/generic/` como dizia a redação original, escrita antes de o workspace existir.

Pack de referência, com o mesmo formato de um pack externo: `pyproject.toml` próprio, entry point e dependência apenas de contratos. É o primeiro consumidor real dos contratos e a fixture dos testes de carregamento de pack do core.

```toml
[project]
name = "ai-generic"
dependencies = ["axon-ai-contracts>=0.1,<0.2"]      # faixa derivada da contract_version (ADR-014)

[tool.uv.sources]
axon-ai-contracts = { workspace = true }            # resolve no commit local enquanto mora no workspace

[project.entry-points."ai_core.packs"]
generic = "ai_generic.pack:GenericPack"
```

> Atualizado na clarificação de 2026-09-17: a redação original ("mesmo commit, sem faixa") precede o
> [ADR-014](../../docs/adr/ADR-014-politica-versoes-0x-contratos.md) e a etapa de distribuição da suíte de
> conformidade (001 FR-018), que trata dependência sem faixa como erro (`distribution.range_too_wide`). A faixa
> derivada mais a fonte do workspace preservam a intenção original e mantêm o pack conforme.

## Portas e adapters **[ADR-012]**

O pack é um **plug-in do microkernel**: implementa as portas do contrato 001 e é descoberto por entry point. Na v1 não
faz I/O. Se uma tool nativa passar a fazer I/O, segue o princípio XIII por dentro do pack: porta em `ports.py`, cliente
em `adapters/`, e o `pack.py` como composition root do pack.

| Porta | Tipo | Adapters | Teste |
|---|---|---|---|
| `AgentPack` e hooks (contrato 001) | porta de plug-in implementada | `pack.py` | suíte de conformidade de pack |

## Questão em aberto (arch-v1 Parte IX)

Com o modelo de Assistants, `ai-generic` pode não precisar existir como pack: um Assistant com `packs: []`, flow `agentic` e MCPs configurados já é "um agente genérico". Avaliar na Fase 3 se o pack agrega algo além de prompts — e, se não agregar, ele vira um Assistant e `packs/generic` sai do workspace. Nesse caso, a fixture de carregamento de pack do core precisa de outro pack mínimo.

> Fechada na clarificação de 2026-10-07 (FR-005): o pack agrega a tool `calculate` e o validator `non_empty_answer`,
> então **continua pack**, e a regra fica permanente — se um dia contiver só prompts, vira Assistant e um pack mínimo de
> teste assume a fixture. O manifest segue sem flow preferido (FR-007): o Assistant genérico declara `flow: agentic` e
> `controller` ([research.md](research.md) R14, R15).
