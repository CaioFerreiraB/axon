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

Construída pela composition root (011) na Fase 1 e derivada do Execution Grant (003) a partir da Fase 2 — a forma é a
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
