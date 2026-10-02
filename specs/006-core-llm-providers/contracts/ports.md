# Contrato — portas secundárias da 006

Internas do módulo (`ai_core/llm/ports.py`): não são seams e nenhum outro módulo as importa. Quem escolhe o adapter de
cada uma é a composition root (011). Cada porta tem adapter simulado e suíte de conformidade que roda contra ele e
contra o adapter real (princípio XIII).

## `ModelProvider` — acesso a um provedor de modelos

```python
class ModelProvider(LLMProvider, Protocol):
    name: str
    async def probe(self, model: str) -> ProbeResult: ...
```

Estende o contrato `LLMProvider` da 001 — que continua sendo o que um provider implementa — com a sondagem que a FR-009
exige ([research.md](../research.md) R8). `name` é a chave pela qual a 011 registra o provider e o texto que aparece em
`ModelRef.provider`, no trace e nas mensagens de erro.

| Exigência | Detalhe |
|---|---|
| `chat(..., stream=False)` | devolve `ChatResponse` do contrato 001, com `usage` quando o provider informa |
| `chat(..., stream=True)` | devolve `AsyncIterator[ChatChunk]`; `finish_reason` e `usage` só no último pedaço |
| Erros | toda falha de rede, status ou inatividade sai como `ModelCallFailed` (`api.py`) — nenhum erro de SDK escapa |
| `probe(model)` | `ProbeResult(available, detail)`; nunca levanta; nunca gera tokens |
| Timeouts | conexão e inatividade entre pedaços, configuráveis; sem teto total (FR-010, R5) |
| Sem estado por requisição | um provider atende execuções concorrentes; nada é guardado entre chamadas |

**Adapters da fase**: `adapters/ollama.py` (real) e `adapters/fake.py` (`ScriptedProvider`, simulado). OpenAI e
OpenRouter entram na Fase 3, sobre a mesma base `adapters/openai_compat.py`.

### Conformidade (`tests/llm/contract/test_model_provider_port.py`)

Parametrizada pelos dois adapters (o do Ollama com transporte HTTP falso, R10):

1. resposta única devolve `ChatResponse` com `message.role == "assistant"`;
2. streaming devolve ao menos dois pedaços, e só o último tem `finish_reason`;
3. `usage` chega quando o provider informa e é `None` quando não informa — em nenhum caso o adapter inventa número;
4. `tools` e `response_format`, quando passados, chegam ao provider sem alteração de forma;
5. provider inalcançável → `ModelCallFailed` com provider e modelo na mensagem;
6. resposta de erro de status → `ModelCallFailed` com o código;
7. stream que para sem fechar → `ModelCallFailed` por inatividade dentro de `idle_seconds`;
8. `probe` devolve `available=True` para modelo conhecido e `available=False` com motivo para desconhecido e para
   provider fora do ar.

## `Clock` — relógio monotônico

```python
class Clock(Protocol):
    def monotonic(self) -> float: ...
```

Existe por não-determinismo (ADR-013): sem ela a duração no trace seria intestável e o `service.py` leria o relógio do
sistema. Só mede intervalo — o instante de parede de cada registro é da 009.

**Adapters** (ambos em `adapters/clock.py`): `MonotonicClock` (`time.monotonic`) e `ScriptedClock`, que devolve valores
programados — é o adapter em memória que o princípio XIII exige e o relógio do perfil de teste da 011 (US3 cenário 2),
por isso mora em `adapters/` e não no testkit. A 011 injeta o mesmo relógio em todos os módulos que declaram porta de
tempo (011 FR-008).

### Conformidade (`tests/llm/contract/test_clock_port.py`)

1. leituras sucessivas nunca diminuem;
2. a diferença entre duas leituras do relógio programado é exatamente a programada — é o que torna
   `duration_ms` verificável na suíte do seam.

## Porta adiada

`SecretResolver` (credenciais de providers remotos) está no `design.md` e entra na Fase 3, junto com os adapters que
precisam dela: declará-la agora seria porta sem uso, contra o princípio XIII ([research.md](../research.md) R8, R14).
*Entrou na Fase 3 — seção abaixo.*

---

## Fase 3 (2026-10-02): `SecretResolver` — credenciais dos providers remotos

```python
class SecretResolver(Protocol):
    def resolve(self, name: str) -> str | None:
        """Valor da credencial pelo nome, ou None quando ausente ou vazia. Nunca levanta."""
```

- Quem chama são os adapters remotos ([remote-adapters.md](remote-adapters.md)), uma vez, na construção, com um dos dois
  nomes fixos: `AI_CORE_OPENAI_API_KEY` e `AI_CORE_OPENROUTER_API_KEY`. Nenhum nome vem de entrada
  ([research.md](../research.md) R21).
- Adapters: `EnvSecretResolver(environ=None)` (ambiente do processo; perfis `memory` e `persistent`) e
  `InMemorySecretResolver(values=None)` (perfil `test` e suítes), em `adapters/secrets.py`. A 011 escolhe qual, pela
  porta `llm_secrets`.

### Conformidade (`tests/llm/contract/test_secret_resolver_port.py`)

Parametrizada pelos dois adapters (o de ambiente sobre um dicionário injetado):

1. nome presente devolve o valor exato;
2. nome ausente devolve `None`;
3. valor vazio ou só espaços devolve `None`;
4. nunca levanta, nem para nome vazio.

### `ModelProvider` — o que muda

Nada na forma da porta. Os remotos entram como adapters dela, e a suíte de conformidade da porta passa a ser
parametrizada também por eles (com transporte HTTP falso). Um remoto **sem credencial** cumpre a porta assim: `chat`
levanta `ModelCallFailed` antes da rede, e `probe` devolve `available=False` com o motivo — continua sem levantar.
