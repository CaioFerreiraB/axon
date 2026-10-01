# Quickstart — 011 Bootstrap (Fase 1, US1–US3)

Guia de validação. Comandos a partir de `ai-core/`, com `XDG_DATA_HOME=$HOME/.local/share` nesta máquina.

## Pré-requisitos

```bash
uv sync                      # traz uvicorn e instala o comando `ai-core`
```

## Verificação completa

```bash
uv run pytest
uv run mypy
uv run ruff check packages
uv run lint-imports          # ninguém importa o bootstrap; ninguém importa internals de outro módulo
```

## Cenários

### 1. Ordem de boot e falha fechada (US1)

```bash
uv run pytest packages/core/tests/bootstrap/contract -v
```

Esperado: as etapas rodam na ordem declarada; falha crítica interrompe e as seguintes não rodam; falha degradável
segue com o motivo registrado; o encerramento libera recursos na ordem inversa.

### 2. Perfis (US2)

```bash
uv run pytest packages/core/tests/bootstrap/unit/test_profiles.py -v
```

Esperado: os dois perfis atendem todas as portas exigidas; perfil incompleto é recusado nomeando a porta; o relógio
entregue ao motor, à API e ao trace é o mesmo objeto.

### 3. Plataforma inteira em memória (US3, SC-003)

```bash
uv run pytest packages/core/tests/bootstrap/integration -v
```

Esperado: `platform(profile="test")` devolve a plataforma montada e uma conversa completa acontece por HTTP, sem rede
e sem serviço externo.

### 4. Pack defeituoso não derruba o boot (SC-004)

```bash
uv run pytest packages/core/tests/bootstrap/integration -k degradado -v
```

Esperado: com um pack em erro na configuração, o boot conclui, a etapa `packs` aparece como degradada com o pack
nomeado, e um Assistant que não depende dele atende normalmente.

## Subindo a plataforma de verdade

```bash
cat > /tmp/packs.yaml <<'YAML'
packs:
  generic:
    enabled: true
YAML

cat > /tmp/assistants.yaml <<'YAML'
assistants:
  geral:
    flow: chat
    packs: [generic]
    models:
      generation: ollama/qwen3:1.7b
    allow: ["ollama/*"]
YAML

ollama serve &
ollama pull qwen3:1.7b

AI_CORE_PACKS_FILE=/tmp/packs.yaml \
AI_CORE_ASSISTANTS_FILE=/tmp/assistants.yaml \
uv run ai-core serve
```

Em outro terminal:

```bash
curl -N http://127.0.0.1:8000/v1/chat/completions \
  -H 'content-type: application/json' \
  -d '{"model": "geral", "messages": [{"role": "user", "content": "oi"}], "stream": true}'
```

Esperado: o relatório de boot no terminal do servidor, com as cinco etapas; e os pedaços da resposta chegando um a
um, com `data: [DONE]` no fim. **É a conversa ponta a ponta da Fase 1** — HTTP, motor, pack de referência e modelo
local.

Com `AI_CORE_TRACE_DIR=/tmp/trace`, cada requisição vira registros no arquivo do dia: execução iniciada, chamada de
modelo com tokens e duração, validação e fim.

## Montando a plataforma numa suíte

```python
from ai_core.bootstrap.wiring import platform

plataforma = platform(profile="test")
cliente = TestClient(plataforma.app)
```

É assim que a suíte de um pack externo testa o pack contra a plataforma de verdade, sem copiar montagem.

---

## Fase 2 (US2, US4, US5, autenticação real)

```bash
uv run pytest packages/core/tests/bootstrap -v                     # perfis, saúde, CLI, plataforma no test
AI_CORE_TEST_POSTGRES_DSN=postgresql://postgres:pg@localhost:55432/postgres \
  uv run pytest packages/core/tests/bootstrap -k persistent -v     # perfil persistente contra Postgres
```

Esperado: os três perfis atendem todas as portas; sem credencial, 401 em qualquer perfil; no `test`, as credenciais
exportadas conversam; no `persistent`, o boot migra `assistants` e `http`, uma chave emitida por `ai-core keys create`
autentica na API e uma conversa sobrevive a uma plataforma nova sobre o mesmo banco; banco inacessível para o boot
nomeando `database` sem imprimir a URL; a saúde é `degraded` (200) com um modelo fora do ar e `down` (503) com o banco
fora; `ai-core --help` lista todos os subcomandos ([contracts/cli.md](contracts/cli.md)).

Manual, com Postgres local e Ollama:

```bash
export AI_CORE_PROFILE=persistent AI_CORE_DATABASE_URL=postgresql://postgres:pg@localhost:55432/postgres
export AI_CORE_PACKS_FILE=packs.yaml AI_CORE_ASSISTANTS_FILE=assistants.yaml
uv run ai-core keys create --subject user:caio --group operadores   # a chave sai na última linha
uv run ai-core serve
```
