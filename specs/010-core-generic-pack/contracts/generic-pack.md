# Contrato — capacidades publicadas pelo `ai-generic` (v1)

O pack não expõe seam Python. O que ele publica é o **entry point** e as capacidades que os hooks de catálogo
devolvem. Este é o contrato observável: quem muda qualquer linha daqui muda o comportamento visível do pack para o
Pack Registry (002), para Assistants (003) e para o Tool Gateway (004).

Tudo abaixo é consumido pela API pública de `ai_core_contracts` (001) — nenhum tipo novo é criado.

## Identidade

```toml
[project.entry-points."ai_core.packs"]
generic = "ai_generic.pack:GenericPack"
```

```python
class GenericPack(PackBase):
    name = "generic"                 # igual ao nome do entry point (002 FR-017)
    contract_version = "0.1"         # série dos contratos; deriva a faixa >=0.1,<0.2 (ADR-014)
```

`name` e `contract_version` são **atributos de classe**: o Pack Runtime os lê antes de instanciar.

## `manifest()`

```python
PackManifest(name="generic", version="0.1.0")
```

Sem `preferred_flow`, `depends_on`, `requires_collections` e `config_schema`. Consequências para os consumidores:

- o bloco do pack em `packs.yaml` aceita `enabled` e nada mais — qualquer `config` é ignorada por ausência de schema;
- um Assistant com `packs: [generic]` não exige coleção nem pack adicional;
- o flow vem do Assistant.

## `system_prompt(ctx)`

Devolve o mesmo texto para qualquer `PackContext`: instruções de assistente de uso geral, em português, sem nenhum
termo de domínio (princípio I). Nunca `None` na v1.

## Tool `calculate`

```python
ToolSpec(
    name="calculate",
    description="Calcula uma expressão aritmética com números.",
    parameters={
        "type": "object",
        "properties": {"expression": {"type": "string"}},
        "required": ["expression"],
        "additionalProperties": False,
    },
    kind="native",
    mutates=False,
    handler=calculate,      # async (ToolInvocation) -> Mapping[str, JSONValue]
)
```

O core aplica o namespace: o modelo vê `generic.calculate`.

**Garantias do handler** — os argumentos vêm do modelo e são tratados como dado não-confiável (princípio VI):

1. Nunca levanta exceção: toda recusa é um mapeamento com a chave `error` (tabela em [data-model.md](../data-model.md)).
2. Nunca executa nada além de aritmética sobre números literais: a expressão é analisada como AST e só nós de uma
   allowlist são aceitos; nome, chamada, atributo, índice, comparação e operador booleano são recusados.
3. Não faz I/O, não lê o relógio, não usa aleatoriedade e não guarda estado — mesma expressão, mesmo resultado.
4. `reference_time` e `request_id` da invocação não influenciam o resultado (a tool não depende de tempo).

Sucesso devolve `{"expression": <a string recebida, com `strip()`>, "result": <int | float>}`. Os limites
(`MAX_LENGTH = 200` caracteres, `MAX_EXPONENT = 1000`) estão em [data-model.md](../data-model.md).

## Validator `non_empty_answer`

```python
class NonEmptyAnswer:
    name = "non_empty_answer"
    async def validate(self, view: TurnView, ctx: ValidatorContext) -> ValidationResult: ...
```

Reprova resposta ausente, vazia ou composta só de espaços, com `issues=("resposta vazia",)` e
`flags={"empty_answer"}`; aprova qualquer outra. Não reescreve `answer` nem `citations`. Determinístico, sem acesso a
modelo (ADR-007: julgamento por LLM só no harness offline).

## O que o pack NÃO publica na v1

`prepare_context` (fatia própria), retrievers, reranker e rotina de pack — os defaults de `PackBase` valem. Nenhum
deles é adiado por dificuldade: não há caso de uso na Fase 1 (princípio XII), e a US2 (Fase 3) reabre a pergunta junto
da FR-005.
