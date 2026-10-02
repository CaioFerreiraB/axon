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
- O esquema não é reescrito. Se o provider o recusa (por exemplo, `anyOf` na raiz no modo estrito da OpenAI) ou se nenhum
  upstream do OpenRouter cumpre os parâmetros, a resposta de erro vira `ModelCallFailed` com o código e o corpo
  truncado — e a chamada **não** é refeita sem a restrição (camada 3).

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
