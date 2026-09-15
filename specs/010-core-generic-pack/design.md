# Design — 010 Pack genérico

> Insumo técnico pré-aprovado para `/speckit-plan`. Origem: arch-v1 §30, Parte IX; ADR-004.

## Localização

```text
ai-core/packs/generic/
├── pyproject.toml       # distribuição ai-generic; entry point ai_core.packs
└── src/ai_generic/
    ├── pack.py
    ├── tools/
    └── prompts/
```

Pack de referência, com o mesmo formato de um pack externo: `pyproject.toml` próprio, entry point e dependência apenas de contratos. É o primeiro consumidor real dos contratos e a fixture dos testes de carregamento de pack do core.

```toml
[project]
name = "ai-generic"
dependencies = ["ai-core-contracts"]      # mesmo commit, sem faixa

[project.entry-points."ai_core.packs"]
generic = "ai_generic.pack:GenericPack"
```

## Portas e adapters **[ADR-012]**

O pack é um **plug-in do microkernel**: implementa as portas do contrato 001 e é descoberto por entry point. Na v1 não
faz I/O. Se uma tool nativa passar a fazer I/O, segue o princípio XIII por dentro do pack: porta em `ports.py`, cliente
em `adapters/`, e o `pack.py` como composition root do pack.

| Porta | Tipo | Adapters | Teste |
|---|---|---|---|
| `AgentPack` e hooks (contrato 001) | porta de plug-in implementada | `pack.py` | suíte de conformidade de pack |

## Questão em aberto (arch-v1 Parte IX)

Com o modelo de Assistants, `ai-generic` pode não precisar existir como pack: um Assistant com `packs: []`, flow `agentic` e MCPs configurados já é "um agente genérico". Avaliar na Fase 3 se o pack agrega algo além de prompts — e, se não agregar, ele vira um Assistant e `packs/generic` sai do workspace. Nesse caso, a fixture de carregamento de pack do core precisa de outro pack mínimo.
