# Contrato — adapters dos providers remotos (OpenAI e OpenRouter)

Interno do módulo (`ai_core/llm/adapters/`), Fase 3. Os dois cumprem a porta `ModelProvider` ([ports.md](ports.md))
sobre a mesma camada compatível do Ollama ([ollama-adapter.md](ollama-adapter.md)): tradução de mensagens, streaming,
mapeamento de erro e timeouts são os de lá. Este contrato descreve só o que muda. Decisões em
[research.md](../research.md) R18–R22.

## Construção

```python
secrets = EnvSecretResolver()                      # a 011 escolhe o adapter (porta llm_secrets)
OpenAIProvider(secrets=secrets)                    # name="openai",     https://api.openai.com/v1
OpenRouterProvider(secrets=secrets)                # name="openrouter", https://openrouter.ai/api/v1
# ambos aceitam connect_seconds=5.0, idle_seconds=120.0, http_client=None e base_url (só para teste)
```

| Provider | Credencial lida | Na falta |
|---|---|---|
| `OpenAIProvider` | `AI_CORE_OPENAI_API_KEY` | registrado; "sem credencial: defina AI_CORE_OPENAI_API_KEY" |
| `OpenRouterProvider` | `AI_CORE_OPENROUTER_API_KEY` | registrado; "sem credencial: defina AI_CORE_OPENROUTER_API_KEY" |

- A credencial é resolvida **uma vez, na construção**. Vazia ou só espaços conta como ausente.
- Chave e URL base vão sempre explícitas ao SDK: as leituras implícitas dele (`OPENAI_API_KEY`, `OPENAI_BASE_URL`) nunca
  acontecem.
- `max_retries=0`, como na Fase 1.

## Sem credencial (FR-011)

| Operação | Comportamento |
|---|---|
| `chat(…)`, com ou sem streaming | `ModelCallFailed(provider, model, reason="sem credencial: defina AI_CORE_…")` **antes** de qualquer requisição HTTP |
| `probe(model)` | `ProbeResult(available=False, detail="sem credencial: defina AI_CORE_…")`, sem rede |

## Restrição de formato (FR-005, camada 2)

Vale para toda chamada com `response_format` do tipo `json_schema`, em **qualquer** provider da camada compatível:

```json
{"type": "json_schema", "json_schema": {"name": "…", "schema": {…}, "strict": true}}
```

- `strict` é forçado para `true`, mesmo que quem chama mande `false`. O `response_format` recebido não é alterado (cópia).
- No OpenRouter, com `response_format`, o corpo leva também `"provider": {"require_parameters": true}`; sem
  `response_format`, não.
- O esquema não é reescrito — **salvo** na OpenAI e nos modelos `openai/…` do OpenRouter, que recebem a conversão para o
  subconjunto estrito (seção abaixo, ADR-023). Se o provider recusa o esquema ou se nenhum upstream do OpenRouter cumpre
  os parâmetros, a resposta de erro vira `ModelCallFailed` com o código e o corpo truncado — e a chamada **não** é
  refeita sem a restrição (camada 3).

## Mensagens de erro

As da camada compatível, com uma regra a mais: o valor da credencial, se aparecer no motivo, é trocado por `***` antes de
a mensagem existir. Nenhum erro, log ou trace leva o valor (FR-011).

## Sondagem (`probe`)

| Situação | `ProbeResult` |
|---|---|
| Sem credencial | `available=False`, "sem credencial: defina …" |
| Modelo na lista | `available=True` |
| OpenRouter: modelo com sufixo de variante cuja base está na lista (`qwen/qwen3-8b:nitro`) | `available=True` |
| Modelo ausente | `available=False`, "modelo … não encontrado em …; disponíveis: <até 20 ids> (+N)" |
| Chave inválida, provider fora do ar | `available=False`, com o motivo (já limpo) |

Nunca levanta, nunca gera tokens. A lista truncada vale também para o Ollama (lista curta não muda).

## Conformidade (`tests/llm/contract/test_model_provider_port.py`, `test_remote_providers.py`)

1. a suíte da porta `ModelProvider` roda também contra `OpenAIProvider` e `OpenRouterProvider` com transporte HTTP falso;
2. sem credencial: `chat` (com e sem streaming) levanta `ModelCallFailed` nomeando a variável, e o transporte não recebe
   nenhuma requisição; `probe` relata a falta;
3. `strict: true` no corpo enviado, inclusive quando quem chama manda `false`; o mapeamento recebido continua igual;
4. `require_parameters` no corpo do OpenRouter só quando há `response_format`;
5. resposta 400 do provider → `ModelCallFailed` com código e corpo, e o transporte recebe **uma** requisição;
6. sondagem do OpenRouter por base da variante; lista truncada com `(+N)`;
7. corpo de erro que contém a chave sai com `***` no lugar dela.

## Integração com os providers reais (opcional)

Marcada e pulada sem `AI_CORE_OPENROUTER_API_KEY` (e `AI_CORE_OPENAI_API_KEY`, para o caso da OpenAI). Cobre o
*Independent Test* da US4 — o controller com um esquema de ação recebe resposta parseável segundo o esquema — e a
sondagem com modelo presente e ausente. Faz chamadas pagas: nunca roda por default ([quickstart.md](../quickstart.md)).

## Subconjunto estrito da OpenAI (2026-10-07, ADR-023)

Para `OpenAIProvider` (sempre) e `OpenRouterProvider` com modelo `openai/…`, com `response_format` do tipo
`json_schema` (decisões em [research.md](../research.md) R27–R29):

| Na ida (esquema enviado) | Na volta (conteúdo devolvido) |
|---|---|
| raiz que não é objeto → `{"type": "object", "properties": {"value": …}, "required": ["value"], "additionalProperties": false}` | `value` desembrulhado |
| propriedade opcional → obrigatória e anulável | `null` introduzido pela conversão sai; `null` que o original admitia fica |
| todo objeto com `additionalProperties: false`; `oneOf` → `anyOf`; sem `default`/`examples`/`title`; `const`/`enum` sem `type` ganham o `type` do valor | — |
| nome de função fora de `^[a-zA-Z0-9_-]{1,64}$` (tools e `tool_calls` da transcrição) → apelido determinístico | `tool_calls` com o nome original |

Sem equivalente estrito (objeto livre, `additionalProperties` aberto, `allOf`, `not`, `if`/`then`/`else`,
`patternProperties`, nó sem tipo…): `ModelCallFailed(reason="esquema fora do subconjunto estrito da OpenAI: <caminho>:
<motivo>")` **antes** de qualquer requisição. Com streaming, o conteúdo desfeito sai num pedaço só, antes do final.

| # | Verificação |
|---|---|
| 8 | o corpo enviado pela OpenAI tem raiz objeto, todo campo em `required` e `additionalProperties: false`; o `response_format` recebido não muda |
| 9 | o conteúdo devolvido está na forma do esquema original (sem `value`, sem os `null` introduzidos) e valida contra ele |
| 10 | esquema sem equivalente estrito → `ModelCallFailed` antes da rede, com o caminho |
| 11 | OpenRouter: `openai/…` convertido; outro autor (`z-ai/…`) enviado como veio |
| 12 | nome com namespace (`demo.eco`) sai como apelido válido nas mensagens e nas tools; `tool_call` devolvida com o apelido volta como `demo.eco` |

