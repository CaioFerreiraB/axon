# Contrato — adapter do provider local (Ollama)

Interno do módulo (`ai_core/llm/adapters/`): descreve como o contrato `LLMProvider` (001) é cumprido sobre a camada
compatível com OpenAI do Ollama (`:11434/v1`), pelo SDK oficial em modo assíncrono ([research.md](../research.md) R4).
`openai_compat.py` tem a parte que serve a qualquer endpoint compatível; `ollama.py` só fixa os defaults do Ollama.

## Construção

```python
OllamaProvider(
    base_url="http://localhost:11434/v1",   # a 011 lê da configuração do operador
    connect_seconds=5.0,
    idle_seconds=120.0,
    http_client=None,                        # os testes injetam um transporte falso (R10)
)
```

- `name` é `"ollama"` — é a chave do registro da 011 e o que aparece em `ModelRef.provider`.
- A credencial é uma sentinela fixa: o Ollama exige o cabeçalho, mas ignora o valor. Nenhum segredo é lido nesta fase.
- `max_retries=0` no cliente do SDK: nenhuma repetição silenciosa (R5).

## Timeouts (FR-010)

| Parâmetro | Traduzido para | Default | Efeito |
|---|---|---|---|
| `connect_seconds` | `connect` do cliente HTTP | 5 s | provider fora do ar falha em segundos, não em minutos |
| `idle_seconds` | `read` do cliente HTTP | 120 s | em streaming, é o tempo máximo **sem pedaço novo** |

Não há teto de tempo total: uma resposta longa e saudável no hardware alvo (5–15 tok/s) nunca é cortada.

## Tradução das mensagens

| Contrato 001 | Camada compatível |
|---|---|
| `ChatMessage.role/content/name` | campos homônimos |
| `ChatMessage.tool_calls` | `tool_calls` com `{"id", "type": "function", "function": {"name", "arguments"}}` |
| `ChatMessage.tool_call_id` | `tool_call_id` |
| `ChatTool` | `{"type": "function", "function": {name, description, parameters}}` |
| `response_format` | passado como veio (o módulo não interpreta o esquema) |

Chave ausente no `TypedDict` **não** é enviada como `None`: o corpo carrega só o que foi declarado.

## Resposta única

`ChatResponse` com `message` (papel `assistant`, conteúdo e `tool_calls` quando houver), `finish_reason`, `model` e
`usage` (`prompt_tokens`, `completion_tokens`) quando o provider informa. Ausência de `usage` vira ausência do campo —
o adapter nunca estima tokens.

## Streaming

- `stream=True` e `stream_options={"include_usage": True}`, para que o último pedaço traga `usage` quando o provider
  suportar; quando não vier, o campo simplesmente não aparece.
- Cada pedaço vira `ChatChunk` com `delta` (texto, possivelmente vazio) e, quando houver, `tool_calls`.
- `finish_reason` e `usage` aparecem **apenas** no último pedaço, como o contrato 001 exige.
- O iterador é fechado ao final, inclusive quando quem consome abandona a geração no meio.

## Mapeamento de erro (R6)

| Erro do SDK | Vira | Motivo na mensagem |
|---|---|---|
| `APIConnectionError` | `ModelCallFailed` | "provider inalcançável em `<base_url>`" |
| `APITimeoutError` | `ModelCallFailed` | "sem resposta por `<idle_seconds>`s" |
| `APIStatusError` | `ModelCallFailed` | código HTTP + corpo truncado em 500 caracteres |
| `OpenAIError` (demais) | `ModelCallFailed` | nome da classe + texto |

Toda mensagem começa nomeando provider e modelo (US1 cenário 2). O corpo do provider é truncado antes de entrar na
mensagem; a redação de credenciais no que for parar no trace é da 009.

## Sondagem (`probe`)

Lista os modelos da camada compatível e confere se o modelo declarado está entre eles.

| Situação | `ProbeResult` |
|---|---|
| Modelo presente | `available=True`, `detail=None` |
| Provider responde, modelo ausente | `available=False`, `detail="modelo não encontrado em <base_url>; disponíveis: …"` |
| Provider inalcançável ou erro de status | `available=False`, `detail=<motivo>` |

`probe` nunca levanta e nunca gera tokens.

## Provider simulado (`adapters/fake.py`)

`ScriptedProvider` cumpre a mesma porta com respostas, pedaços e falhas programados, e registra as chamadas recebidas.
É o adapter em memória da porta `ModelProvider` (princípio XIII), o provider do perfil de teste da 011 (US3) e o segundo
parâmetro das suítes de conformidade.

## Integração com Ollama real

Marcada e pulada por default; roda quando `OLLAMA_BASE_URL` está definida. Cobre streaming incremental de verdade,
`probe` com modelo presente e ausente, e o erro de provider fora do ar ([quickstart.md](../quickstart.md)).

## Fase 3 (2026-10-02)

Duas regras da camada compatível, descritas em [remote-adapters.md](remote-adapters.md), valem também para o Ollama:
`json_schema.strict` é sempre enviado como `true` (o Ollama ignora o campo e restringe por gramática), e a lista de
disponíveis da sondagem é truncada nos 20 primeiros ids, com `(+N)`.
