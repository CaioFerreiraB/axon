# Design — 006 LLM Providers

> Insumo técnico pré-aprovado para `/speckit-plan`. Origem: arch-v1 §5, §26, §27; ADR-008, ADR-012, ADR-013.

## Localização

```text
ai-core/packages/core/src/ai_core/llm/
├── api.py           # seam Model Router; BoundModel, ModelRole
├── domain/          # resolução por papel, allowlist do grant, rejeição de roteamento automático — puro
├── ports.py         # SecretResolver
├── service.py       # router: aplica domain/, entrega BoundModel, emite dados de chamada ao Trace Sink (009)
└── adapters/        # implementações de LLMProvider (contrato 001)
    ├── ollama.py        # OllamaProvider (API compat OpenAI em :11434/v1)
    ├── openai.py        # OpenAIProvider
    ├── openrouter.py    # OpenRouterProvider
    └── fake.py          # provider simulado — perfil de teste (011)
```

```text
LLMProvider (contrato 001)
├── OllamaProvider        # local; API compatível OpenAI em :11434/v1
├── OpenAIProvider
└── OpenRouterProvider
```

## Modelo por papel

| Papel | Requisito | Escolha típica |
|---|---|---|
| `controller` | JSON confiável, raciocínio curto | modelo forte, poucos tokens |
| `generation` | fluência em português, contexto longo | pode ser local |
| `rerank` | ordenação | modelo dedicado ou nenhum |

```yaml
models:
  controller: { provider: openrouter, model: "qwen/qwen3-8b" }
  generation: { provider: ollama,     model: "qwen3:1.7b" }
  allow: ["ollama/*", "openrouter/*"]
```

```python
class ModelRouter(Protocol):
    def for_role(self, role: Literal["controller", "generation", "rerank"]) -> BoundModel: ...
    # BoundModel = (LLMProvider, model) já conferido contra a allowlist do grant
```

## OpenRouter

Evitar `openrouter/auto` ou variantes que escolhem modelo dinamicamente — reduzem previsibilidade e dificultam avaliação. Preferir modelo explícito. Modelos gratuitos são fallback, não SLA.

## Ollama e o hardware alvo (arch-v1 §27)

```text
2 OCPU · 12 GB RAM · ARM64 · sem GPU
```

```bash
curl -fsSL https://ollama.com/install.sh | sh    # há instalação manual para ARM64
ollama serve                                      # ou como serviço systemd

ollama pull qwen3:1.7b
ollama list          # modelos disponíveis
ollama ps            # modelos carregados em memória
```

API nativa em `:11434/api`; camada compatível OpenAI em `:11434/v1` — o `OllamaProvider` usa a segunda e fica quase idêntico ao `OpenAIProvider`.

### Benchmark antes de decidir (executado com o harness da spec 009, conjunto da 105)

Comparar `Qwen3 1.7B` e `Gemma 4 E2B` em:

```text
tokens/s · tempo até primeiro token · RAM · CPU
qualidade em português · tool calling · fidelidade em RAG
```

As duas últimas são as decisivas, e são exatamente as que o benchmark padrão não mede.

### Expectativa honesta

5–15 tok/s em CPU ARM. Tool calling em 1.7B é nominal, não confiável. É isso que justifica `rag_first` como default, modelo por papel e saída estruturada obrigatória no controller.

## Portas e adapters **[ADR-012]**

| Porta | Tipo | Adapters por fase | Teste |
|---|---|---|---|
| Model Router | primária (seam) | `service.py` + `domain/` | allowlist, papel não configurado, roteamento automático rejeitado |
| `LLMProvider` (contrato 001) | secundária | Ollama (Fase 1); OpenAI e OpenRouter (Fase 3); simulado (teste) | suíte de conformidade de provider, com streaming e `response_format` |
| `SecretResolver` | secundária | variáveis de ambiente (adapter único, injetado pela 011) | dicionário em memória |

Consome por seam: Execution Grant (003) e Trace Sink (009). Este é o módulo que já nasceu hexagonal na arch-v1: a
mudança é só a separação `domain/` × `adapters/` e a porta de segredos.
