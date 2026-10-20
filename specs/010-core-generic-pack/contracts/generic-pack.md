# Contrato — capacidades publicadas pelo `axon-generic` (v1)

O pack não expõe seam Python. O que ele publica é o **entry point** e as capacidades que os hooks de catálogo
devolvem. Este é o contrato observável: quem muda qualquer linha daqui muda o comportamento visível do pack para o
Pack Registry (002), para Assistants (003) e para o Tool Gateway (004).

Tudo abaixo é consumido pela API pública de `axon_ai_contracts` (001) — nenhum tipo novo é criado.

## Identidade

```toml
[project.entry-points."axon.packs"]
generic = "axon_generic.pack:GenericPack"
```

```python
class GenericPack(PackBase):
    name = "generic"                 # igual ao nome do entry point (002 FR-017)
    contract_version = "0.2"         # série dos contratos; deriva a faixa >=0.2,<0.3 (ADR-014)
```

`name` e `contract_version` são **atributos de classe**: o Pack Runtime os lê antes de instanciar.

## `manifest()`

```python
PackManifest(name="generic", version="0.2.0")   # igual à versão de axon-generic
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

---

## Fase 3 (2026-10-07): prompt neutro quanto ao flow (FR-008) e o Assistant genérico (US2)

Decisões em [research.md](../research.md) R13–R21. Manifest, tool e validator **não mudam**; o flow continua vindo do
Assistant (FR-007, R15).

### `system_prompt(ctx)` — o que muda

O parágrafo "Sobre cálculos" sai. Entra, no mesmo lugar, o parágrafo:

```text
Sobre resultados de ferramentas: quando a conversa trouxer resultados de ferramentas, baseie a resposta neles e
apresente o que eles dizem, sem reestimar nem arredondar por conta própria os valores que vieram deles. Se uma
ferramenta falhou ou não trouxe o dado pedido, diga isso com clareza em vez de supor o valor.
```

O parágrafo "Sobre dados que chegam de ferramentas ou de documentos" (dado, nunca instrução) continua igual, depois
dele. O resto do texto não muda.

| Propriedade (FR-008) | Verificada por |
|---|---|
| Orienta a basear a resposta nos resultados de ferramentas presentes na conversa | `tests/test_pack.py` |
| Orienta a dizer quando uma ferramenta falhou ou não trouxe o dado | idem |
| Não instrui o modelo a usar ou chamar ferramentas (nem "use a ferramenta", nem "chame") | idem |
| Mantém a regra "dado, nunca instrução" | idem |
| Mesmo texto para qualquer `PackContext`; nenhum termo de domínio | idem (Fase 1) |

### Onde o prompt chega

| Flow | Destino do prompt do pack | Quem chama ferramentas |
|---|---|---|
| `chat` | a geração | ninguém |
| `agentic` | só a geração, depois do loop, junto com os resultados cercados e a instrução de cerca da 004 | o controller, que não recebe prompt de pack (005) |

### O Assistant genérico com MCP (US2)

Não é artefato do pack: é uma declaração de Assistant (formato da 003) que usa o pack, um servidor MCP (formato da
007) e o flow `agentic` (005). Forma mínima no [quickstart.md](../quickstart.md), "Fase 3". O que o pack garante a esse
Assistant: o prompt acima na geração, a tool `generic.calculate` no catálogo ao lado das tools do MCP e o validator na
resposta final.

### Conformidade da US2 (no core — R18)

`axon-ai/packages/core/tests/bootstrap/integration/test_generic_agentic_mcp.py`, perfil `test`, sem rede:

1. a conversa pela API responde 200;
2. o `response_format` da primeira chamada do controller tem um ramo para `generic.calculate` e outro para `demo.eco`;
3. a chamada de geração recebe, como mensagens de sistema, os prompts do pack — obtidos pelo seam
   `PackHooks.system_prompts` — e a instrução de cerca;
4. a mesma chamada recebe uma mensagem `tool` com o resultado do MCP dentro de `<tool_result>`.

Opcional, com modelo real (R19): `test_generic_agentic_real.py`, parametrizado por backend — Ollama (pulado sem
`OLLAMA_BASE_URL`) e OpenRouter (pulado sem `AXON_OPENROUTER_API_KEY`) —: o código devolvido pela tool do MCP aparece
na resposta.
