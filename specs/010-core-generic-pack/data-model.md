# Data Model — 010 Pack genérico (`axon-generic`), Fase 1

O pack não define tipos próprios publicados: ele **instancia** os tipos do contrato 001. Este documento fixa os valores
concretos que cada instância carrega e as regras de validação que os testes verificam.

## Identidade (lida pelo Pack Runtime sem instanciar — 002 FR-017)

| Campo | Onde | Valor |
|---|---|---|
| nome do entry point | `pyproject.toml`, grupo `ai_core.packs` | `generic` |
| alvo do entry point | `pyproject.toml` | `axon_generic.pack:GenericPack` |
| `GenericPack.name` | atributo de classe | `"generic"` (igual ao entry point, senão a 002 marca `error`) |
| `GenericPack.contract_version` | atributo de classe | `"0.2"` (faixa `>=0.2,<0.3`; passada de 2026-10-20 da 001) |
| distribuição | `pyproject.toml` | `axon-generic` (import `axon_generic`), versão `0.2.0`, `requires-python >=3.12` |

## `PackManifest` (manifest mínimo — FR-007)

| Campo | Valor | Regra |
|---|---|---|
| `name` | `"generic"` | igual a `GenericPack.name`, senão a 002 marca `manifest inválido:` |
| `version` | `"0.2.0"` | igual à versão da distribuição instalada (teste de consistência — R12; `0.2.0` pelo R22) |
| `preferred_flow` | `None` | a v1 não declara preferência de flow |
| `depends_on` | `()` | o pack não depende de outro pack |
| `requires_collections` | `()` | o pack não usa retrieval |
| `config_schema` | `None` | o bloco do pack em `packs.yaml` é só `enabled: true` |

## `system_prompt`

Devolve o texto de `prompts/general.md` — sempre a mesma string, independente do `PackContext` (não há configuração).
Regras verificadas: string não vazia; sem nome de domínio, de organização ou de produto; sem instrução que peça ao
modelo confiar em saída de tool (princípio VI é do core, mas o prompt não deve contradizê-lo).

## Tool `calculate` (`ToolSpec`)

| Campo | Valor |
|---|---|
| `name` | `"calculate"` (o core aplica o namespace `generic.calculate`) |
| `kind` | `"native"` |
| `mutates` | `False` |
| `handler` | corrotina em `tools/arithmetic.py` |
| `parameters` | `{"type": "object", "properties": {"expression": {"type": "string"}}, "required": ["expression"], "additionalProperties": false}` |

### Entrada e saída do handler

Recebe `ToolInvocation` (`arguments`, `request_id`, `reference_time`) e devolve sempre um mapeamento JSON, nunca
exceção:

| Caso | Retorno |
|---|---|
| expressão válida | `{"expression": <recebida com `strip()`>, "result": <número>}` |
| `expression` ausente ou não string | `{"error": "expression precisa ser uma string"}` |
| sintaxe inválida | `{"error": "expressão inválida"}` |
| nó ou operador não permitido (nome, chamada, atributo, índice, comparação, booleano) | `{"error": "expressão inválida: só aritmética com números é permitida"}` |
| divisão (ou módulo) por zero | `{"error": "divisão por zero"}` |
| expressão acima do tamanho máximo | `{"error": "expressão longa demais"}` |
| expoente acima do limite | `{"error": "expoente fora do limite"}` |
| resultado não finito (`inf`, `nan`) | `{"error": "resultado fora do domínio"}` |

Regras da aritmética pura (`evaluate`): operadores `+ - * / // % **` e unários `+ -`; operandos `int` e `float`
literais; divisão inteira e módulo exigem divisor diferente de zero; nenhum acesso a nome, atributo, chamada, índice,
f-string, comprehension ou walrus. Mesma entrada → mesma saída (a suíte de conformidade chama cada hook duas vezes e
compara).

Limites, como constantes do módulo (valores fixados aqui para o teste não ter de adivinhar):

| Constante | Valor | Motivo |
|---|---|---|
| `MAX_LENGTH` | `200` caracteres (após `strip()`) | expressão de calculadora não precisa de mais; evita AST grande vindo do modelo |
| `MAX_EXPONENT` | `1000` (magnitude do expoente em `**`) | `2 ** 1000` é instantâneo; `2 ** 10**9` travaria o processo |
| `MAX_RESULT_BITS` | `4096` (magnitude estimada do resultado de `**`, em bits) | com expoente dentro do limite, a base pode crescer: `(2**1000)**1000` pediria 1 Mbit. Excedê-lo devolve `"expoente fora do limite"` |

A verificação de expoente é feita **antes** de avaliar a potência, sobre o valor já calculado do expoente; expoente
não inteiro é permitido dentro da mesma magnitude (`2 ** 0.5`).

## Validator `non_empty_answer` (`AnswerValidator` → `ValidationResult`)

| Entrada (`TurnView.answer`) | `ok` | `issues` | `flags` |
|---|---|---|---|
| texto com pelo menos um caractere não-espaço | `True` | `()` | `frozenset()` |
| `None` | `False` | `("resposta vazia",)` | `{"empty_answer"}` |
| `""` ou só espaços/quebras | `False` | `("resposta vazia",)` | `{"empty_answer"}` |

Nunca altera `answer` nem `citations` (os dois ficam `None` no resultado, o que o Pack Hooks da 002 interpreta como
"não mexi"). Determinístico e sem acesso a modelo (contrato `AnswerValidator`).

## `PackCapabilities` resultante no Pack Registry (002)

O que a 002 registra depois de carregar este pack — é o que o teste de integração verifica:

| Campo | Valor |
|---|---|
| `status` | `enabled` (com `enabled: true` em `packs.yaml`) |
| `distribution` | `"axon-generic"` |
| `version` | `"0.2.0"` (da distribuição) |
| `contract_version` | `"0.2"` |
| `system_prompt` | presente (string não vazia) |
| tools | uma: `calculate` |
| retrievers | nenhum |
| reranker | ausente |
| validators | um: `non_empty_answer` |
| `preferred_flow` | `None` |
| `depends_on` / `requires_collections` | vazios |

---

# Fase 3 (2026-10-07): US2, FR-005, FR-007 e FR-008

Decisões em [research.md](research.md) R13–R21. **Nenhuma entidade nova** e nenhum campo novo: o pack continua
publicando `PackManifest`, um `system_prompt`, um `ToolSpec` e um `AnswerValidator`.

## O que muda

| Item | Fase 1 | Fase 3 |
|---|---|---|
| `system_prompt` | parágrafo "Sobre cálculos" (usar a ferramenta de cálculo) | parágrafo "Sobre resultados de ferramentas" (FR-008; texto em [contracts/generic-pack.md](contracts/generic-pack.md)) |
| `PackManifest` | `name="generic"`, `version="0.1.0"`, sem `preferred_flow` | igual (FR-007, R15; versão em R17) |
| Tool `calculate`, validator `non_empty_answer` | — | iguais |
| Existência do pack (FR-005) | aberta | decidida: continua pack enquanto agregar hook além de prompt (R14) |

## O Assistant genérico (formato da 003, referência)

| Campo da declaração | Valor | Por quê |
|---|---|---|
| `flow` | `agentic` | o pack não declara flow preferido (R15) |
| `packs` | `[generic]` | prompt, `calculate` e `non_empty_answer` |
| `mcp` | `[<alias>]` | servidor global do `mcp.yaml` (007), com `policy.allowed_tools` |
| `models.generation` | `<provider>/<modelo>` | a voz da resposta, com o prompt do pack |
| `models.controller` | `<provider>/<modelo>` | exigido pelo `agentic` (ADR-019); não recebe o prompt do pack |
| `models.allow` | os padrões dos dois | allowlist (006) |

Sem `controller`, o Assistant fica indisponível (424 pela API) — regra da 003, não do pack.
