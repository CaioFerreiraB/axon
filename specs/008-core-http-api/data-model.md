# Data model — 008 HTTP API (Fase 1)

Este módulo não publica seam Python: o que ele expõe é a superfície HTTP. Os tipos abaixo são internos — ou formas
que ele **exige** de outro módulo, declaradas como `Protocol` para que a 003 as satisfaça na Fase 2 sem import.

## O que chega

### Corpo aceito em `POST /{surface}/chat/completions`

| Campo | Tipo | Regra |
|---|---|---|
| `model` | `str` | obrigatório; `"<assistant>"` ou `"<assistant>/<modelo>"` — a parte do modelo é opcional e, ausente, usa o default do Assistant |
| `messages` | lista de `{role, content}` | obrigatória, não vazia; ao menos uma de papel `user` |
| `stream` | `bool` | default `false`, como na OpenAI |

Campos de amostragem (`temperature`, `top_p`, `max_tokens`) são aceitos e **ignorados** nesta fase: entram com os
limites do Assistant, na Fase 2. Qualquer campo de ampliação de capacidade é rejeitado — ver "Rejeições".

### Rejeições (antes de qualquer execução)

| Campo na requisição | Resposta | Origem |
|---|---|---|
| `tools`, `functions`, `tool_choice`, `function_call` | 400 nomeando o campo | princípio IV, edge case da spec |
| `reference_time` (ou qualquer nome de data de referência) | 400 nomeando o campo | FR-012, ADR-013 |
| `messages` vazio ou sem mensagem de usuário | 400 | 005 FR-013 |
| `model` ausente ou vazio | 400 | — |

## O que este módulo exige de fora (`ports.py`)

```python
class Principal(Protocol):
    @property
    def id(self) -> str: ...

class Authenticator(Protocol):
    async def authenticate(self, *, surface: str, credential: str | None) -> Principal | None: ...

class GrantResolver(Protocol):
    async def resolve(self, *, model: str, principal: Principal) -> ExecutionGrant: ...   # levanta AssistantNotFound

class RequestIds(Protocol):
    def next(self) -> str: ...
```

`ExecutionGrant` é o `Protocol` da 005. `surface` é `"public"` ou `"private"`. `authenticate` devolvendo `None`
significa credencial inválida → 401. `AssistantNotFound` → **404**, igual para inexistente e para não autorizado
(FR-009, regra 404-não-403 da 003).

**Adapters desta fase** (`adapters/development.py`): `AnonymousAuthenticator`, que devolve sempre o mesmo Principal de
desenvolvimento e diz isso no nome, e `Uuid4RequestIds`; nos testes, `SequentialRequestIds`.

## O que sai

### Sem streaming — objeto `chat.completion`

| Campo | Valor |
|---|---|
| `id` | `chatcmpl-<request_id>` |
| `object` | `"chat.completion"` |
| `created` | instante, em segundos |
| `model` | o id pedido, como veio |
| `choices[0].message` | `{"role": "assistant", "content": <resposta final>}` |
| `choices[0].finish_reason` | `"stop"`, ou `"error"` quando o evento final traz erro de execução |
| `x_ai_core` | campo extra: citações, marcações e erros do evento final |

Cabeçalho `X-Request-Id` com o identificador do trace, sempre (FR-010).

### Com streaming — sequência de `chat.completion.chunk`

1. **primeiro chunk**: `delta = {"role": "assistant"}`, sem conteúdo — é o que os clientes esperam para abrir a
   mensagem;
2. **progresso**: `delta = {}` e `x_ai_core.progress = {"stage": …}` — clientes padrão ignoram (R5);
3. **token**: `delta = {"content": <pedaço>}`, um chunk por pedaço, escrito na hora;
4. **chunk final**: `delta = {}`, `finish_reason` e `x_ai_core` com citações, marcações e erros;
5. `data: [DONE]`.

Todo chunk repete `id`, `object`, `created` e `model`.

## Modos de falha

| Situação | Resultado |
|---|---|
| Campo de ampliação ou data de referência no corpo | 400 nomeando o campo, antes de qualquer execução |
| Corpo malformado (sem `model`, sem mensagem de usuário) | 400 |
| Credencial inválida na superfície | 401 |
| Assistant inexistente **ou** não autorizado | 404, com o mesmo corpo nos dois casos (FR-009) |
| Motor levanta antes do primeiro evento (`ExecutionRequestInvalid`, `UnknownFlow`) | 400 nomeando o problema; nada foi executado |
| Execução falha depois do stream aberto | chunk final com `finish_reason="error"`, motivos em `x_ai_core.errors`, e `[DONE]`; conexão fecha limpa (R6) |
| Execução falha sem streaming | **502** com os motivos e o texto parcial no corpo. Sem streaming ainda dá para escolher o status, e 200 com marcador de erro seria degradação silenciosa, que o princípio VII proíbe — em streaming o 200 já foi enviado e o chunk com desfecho de erro é o melhor possível |
| Cliente desconecta no meio do stream | o iterador do motor é fechado e a execução cancelada (005) |
