# Data model — 006 LLM Providers (Fase 1)

Todos os tipos publicados são imutáveis (`@dataclass(frozen=True, slots=True, kw_only=True)`) e vivem em
`ai_core/llm/api.py`, exceto onde indicado. Nenhum deles carrega tipo de SDK, de HTTP ou de outro módulo do core.

## Value objects publicados

### `ModelRole`

```python
type ModelRole = Literal["controller", "generation", "rerank"]
```

Vocabulário fechado do ADR-008. A Fase 1 usa apenas `generation`; os outros dois são resolvíveis desde já e só ganham
provider remoto na Fase 3.

### `ModelRef` — provider e modelo, sempre explícitos

| Campo | Tipo | Regra |
|---|---|---|
| `provider` | `str` | não vazio; sem `/`; é a chave do provider no registro montado pela 011 |
| `model` | `str` | não vazio; **pode** conter `/` (modelos do OpenRouter) e `:` (tag do Ollama) |

- `ModelRef.parse("ollama/qwen3:1.7b")` divide no **primeiro** `/` ([research.md](research.md) R12);
  texto sem `/` é erro (`ValueError`), porque provider implícito é proibido pelo princípio VIII.
- `str(ref)` devolve `"provider/model"` — é a forma usada na allowlist, no trace e nas mensagens de erro.

### `ModelPolicy` — a Key Entity "Model Policy" da spec

| Campo | Tipo | Regra |
|---|---|---|
| `roles` | `Mapping[ModelRole, ModelRef]` | pelo menos um papel; guardado como `MappingProxyType` |
| `allow` | `tuple[str, ...]` | padrões `fnmatch` sobre `"provider/model"`; vazio = nenhuma restrição declarada |

Construída pela composition root (011) na Fase 1 e pela 003, dentro do Execution Grant, a partir da Fase 2 ([ADR-016](../../docs/adr/ADR-016-grant-carrega-politica-de-modelos.md)) — a forma é a
mesma nas duas fases (R1). `__post_init__` rejeita papel fora do vocabulário e política sem papel nenhum.

### `ModelHealth` — resultado da verificação sob demanda (FR-009)

| Campo | Tipo | Significado |
|---|---|---|
| `role` | `ModelRole` | papel verificado |
| `ref` | `ModelRef` | provider e modelo declarados para ele |
| `available` | `bool` | o provider respondeu **e** conhece o modelo |
| `detail` | `str \| None` | motivo quando `available` é falso; `None` quando está tudo certo |

## Protocols do seam

### `BoundModel` — cliente já ligado ao modelo

```python
class BoundModel(Protocol):
    role: ModelRole
    ref: ModelRef
    async def complete(self, messages, *, tools=None, response_format=None) -> ChatResponse: ...
    def stream(self, messages, *, tools=None, response_format=None) -> AsyncIterator[ChatChunk]: ...
```

`messages`, `tools`, `response_format`, `ChatResponse` e `ChatChunk` são os tipos do contrato 001. Quem chama **não**
passa `model`: ele já foi resolvido e conferido (R3). A implementação (`service.TracedModel`) é quem mede e emite o
trace — ver "Instrumentação".

### `ModelRouter` — um por execução

```python
class ModelRouter(Protocol):
    def for_role(self, role: ModelRole) -> BoundModel: ...
```

Assinatura literal do `design.md`. Resolver duas vezes o mesmo papel devolve clientes equivalentes; não há estado
acumulado entre chamadas além do que o trace registra.

### `ModelRouting` — o seam montado no boot

```python
class ModelRouting(Protocol):
    def for_execution(self, *, policy: ModelPolicy, request_id: str) -> ModelRouter: ...
    async def check(self, policy: ModelPolicy) -> tuple[ModelHealth, ...]: ...
```

`check` percorre os papéis da política, sonda o provider de cada um e devolve um `ModelHealth` por papel, na ordem
`controller`, `generation`, `rerank` (só os configurados). Nunca levanta por provider indisponível: indisponibilidade é
resultado, não exceção (R8).

## Portas secundárias (`ports.py`)

### `ModelProvider` — o contrato 001 mais a sondagem

```python
class ModelProvider(LLMProvider, Protocol):
    name: str
    async def probe(self, model: str) -> ProbeResult: ...
```

`ProbeResult(available: bool, detail: str | None)`. Estende `LLMProvider` (001) em vez de alterá-lo (R8). Adapters da
fase: `OllamaProvider` (real) e `ScriptedProvider` (simulado).

### `Clock` — relógio monotônico

```python
class Clock(Protocol):
    def monotonic(self) -> float: ...
```

Só duração é medida aqui; o instante de parede de cada registro é estampado pela 009 (ADR-013). O adapter de produção é
`time.monotonic`; o de teste devolve valores programados, o que torna a duração no trace determinística.

## Erros (`api.py`)

| Erro | Quando | Mensagem contém |
|---|---|---|
| `ModelRoutingError` | base da hierarquia | — |
| `RoleNotConfigured` | papel pedido não está na política (US2 cenário 2) | papel e papéis configurados |
| `ModelNotAllowed` | `provider/model` não casa com nenhum padrão da allowlist (FR-003) | referência e padrões |
| `UnknownProvider` | o `provider` da referência não existe no registro montado pela 011 | provider e providers conhecidos |
| `ModelCallFailed` | provider fora do ar, erro de status, stream interrompido ou timeout | provider, modelo e causa |

`ModelCallFailed` guarda `provider`, `model` e `reason` como atributos, para que a 008 (Fase 2) traduza sem reparsear
texto.

## Instrumentação (R7)

Cada chamada de `complete()` ou `stream()` emite exatamente um `ModelCall` (009) quando termina:

| Campo do `ModelCall` | Origem |
|---|---|
| `request_id` | fixado em `for_execution` |
| `role`, `provider`, `model` | do `BoundModel` |
| `duration_ms` | diferença entre duas leituras da porta `Clock` |
| `input_tokens`, `output_tokens` | `ChatUsage` da resposta ou do último pedaço; `None` quando o provider não informa |
| `finish_reason` | da resposta; `"error"` quando a chamada falhou |

Em streaming, a emissão acontece ao encerrar o iterador — normalmente, por erro ou por abandono de quem consome. Uma
chamada nunca emite dois eventos, e uma chamada que falha também emite: é o que faz SC-002 valer.

## Modos de falha

| Situação | Resultado | Trace |
|---|---|---|
| Papel não configurado | `RoleNotConfigured` antes de qualquer I/O | nenhum (não houve chamada) |
| Modelo fora da allowlist | `ModelNotAllowed` antes de qualquer I/O | nenhum |
| Provider desconhecido no registro | `UnknownProvider` antes de qualquer I/O | nenhum |
| Provider fora do ar | `ModelCallFailed` nomeando provider e modelo (US1 cenário 2) | `ModelCall` com `finish_reason="error"` |
| Erro de status do provider (4xx/5xx, limite de taxa) | `ModelCallFailed` com código e corpo truncado; sem repetição e sem fallback (FR-007) | idem |
| Stream para de entregar pedaços | `ModelCallFailed` por inatividade após `idle_seconds` (FR-010) | idem |
| Modelo declarado não existe no provider | `check` devolve `available=False` com o motivo; a chamada falha com `ModelCallFailed` | evento só na chamada |
| Trace Sink levanta | impossível por contrato da 009 (`emit` nunca levanta); mesmo assim a emissão é o último passo, depois do resultado pronto | — |

---

# Fase 3 (2026-10-02): US2–US5

Decisões em [research.md](research.md) R15–R26. Nenhum value object, Protocol de seam ou erro novo: muda uma invariante
do `ModelRef` e o que o `ModelCallFailed` pode relatar.

## `ModelRef` — invariante nova (FR-004, R16)

| Regra | Exemplo recusado | Exemplo aceito |
|---|---|---|
| No provider `openrouter`, a base do modelo (minúsculas, antes do primeiro `:`) não pode ser `auto` | `openrouter/auto`, `openrouter/AUTO`, `openrouter/auto:free` | — |
| No provider `openrouter`, a base do modelo não pode começar com `openrouter/` | `openrouter/openrouter/auto`, `openrouter/openrouter/qualquer` | `openrouter/qwen/qwen3-8b`, `openrouter/qwen/qwen3-8b:free`, `…:nitro`, `…:floor` |
| Outros providers não são afetados | — | `ollama/auto`, `openai/gpt-4o-mini` |
| Aliases de versão do OpenRouter não são roteamento automático (clarificação de 2026-10-07) | — | `openrouter/~z-ai/glm-flash-latest` |

Recusa = `ValueError("'<provider/modelo>' é roteamento automático, que escolhe o modelo sozinho: declare um modelo
explícito (autor/modelo)")`, levantado na construção — `ModelRef(...)` e `ModelRef.parse(...)` —, antes da allowlist.

## Restrição de formato do `controller` (FR-005, R17)

`domain/output.py`:

| Entrada (`role`, `response_format`) | `constraint_problem` |
|---|---|
| `generation`/`rerank`, qualquer | `None` |
| `controller`, `{"type": "json_schema", "json_schema": {"name": …, "schema": {…}}}` | `None` |
| `controller`, `None` | "o papel 'controller' exige response_format com esquema (json_schema)" |
| `controller`, `{"type": "json_object"}` ou outro tipo | idem, nomeando o tipo recebido |
| `controller`, `json_schema` sem `schema` mapeamento | idem |

Forma enviada pelo adapter (R18): `json_schema.strict` sempre `true`; no OpenRouter, com formato, também
`provider.require_parameters: true` no corpo.

## Porta `SecretResolver` (`ports.py`, R21)

```python
class SecretResolver(Protocol):
    def resolve(self, name: str) -> str | None:
        """Valor da credencial pelo nome, ou None quando ausente ou vazia. Nunca levanta."""
```

| Adapter | Fonte | Uso |
|---|---|---|
| `EnvSecretResolver(environ=None)` | variável de ambiente com o nome pedido | perfis `memory` e `persistent` |
| `InMemorySecretResolver(values=None)` | dicionário | perfil `test` e suítes |

## Providers remotos (`adapters/`, R20)

| Provider | `name` | URL base | Credencial | Particularidade |
|---|---|---|---|---|
| `OpenAIProvider` | `openai` | `https://api.openai.com/v1` | `AI_CORE_OPENAI_API_KEY` | — |
| `OpenRouterProvider` | `openrouter` | `https://openrouter.ai/api/v1` | `AI_CORE_OPENROUTER_API_KEY` | `require_parameters` com formato; sondagem aceita a base da variante (R22) |

Estado de um remoto, fixado na construção: **com credencial** (chamadas normais) ou **sem credencial** (toda chamada e
toda sondagem relatam a falta, sem rede). Não há transição em processo: trocar a credencial é reiniciar.

## Erros — o que muda

`ModelCallFailed` passa a cobrir também falhas **antes** da rede, sempre com `provider`, `model` e `reason`:

| `reason` | Quando |
|---|---|
| "o papel 'controller' exige response_format com esquema (json_schema)…" | guarda do R17 |
| "sem credencial: defina AI_CORE_OPENAI_API_KEY" (ou `…OPENROUTER…`) | remoto sem credencial (R21) |
| "erro 400 do provider: …" / "erro 404 do provider: …" | recusa da restrição pelo provider (R19) |

## Modos de falha — acréscimos

| Situação | Resultado | Trace |
|---|---|---|
| Referência de roteamento automático | `ValueError` na construção do `ModelRef` — a 003 e a 008 relatam como configuração ou requisição inválida | nenhum |
| `controller` sem `response_format` de esquema | `ModelCallFailed` antes do provider | `ModelCall` com `finish_reason="error"` |
| Remoto sem credencial | `ModelCallFailed` antes da rede; `check` → `available=False`, "sem credencial: defina …" | `ModelCall` de erro na chamada |
| Provider recusa a restrição (modelo sem suporte, esquema fora do modo estrito, nenhum upstream no OpenRouter) | `ModelCallFailed` com código e corpo; sem reenvio | `ModelCall` de erro |
| Chave inválida | `ModelCallFailed` com o 401 (valor da chave trocado por `***`); `check` → indisponível | `ModelCall` de erro na chamada |
