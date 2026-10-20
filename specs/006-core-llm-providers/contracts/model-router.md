# Contrato — seam Model Router (006)

Dono: spec 006. Consumidores: 005 (executa), 011 (monta e verifica saúde), 003 e 008 a partir da Fase 2.
Publicado em `ai_core/llm/api.py`. **Mudar qualquer assinatura abaixo exige ADR** (princípio II).

## Superfície

```python
from ai_core.llm.api import (
    BoundModel, ModelHealth, ModelPolicy, ModelRef, ModelRole, ModelRouter, ModelRouting, ProviderStatus,
    ModelCallFailed, ModelNotAllowed, ModelRoutingError, RoleNotConfigured, UnknownProvider,
)
```

Nada além disso é público. `service.py`, `ports.py`, `domain/` e `adapters/` são internos — só a composition root (011)
importa `service.py` e `adapters/`, para construir.

## Uso por execução (005)

```python
router = routing.for_execution(policy=grant_policy, request_id=request_id)
model = router.for_role("generation")
async for chunk in model.stream(messages):
    yield chunk["delta"]
```

1. `for_execution` **não** faz I/O nem valida a política contra os providers: é barato e síncrono.
2. `for_role` resolve o papel, aplica a allowlist e confere que o provider existe — as três falhas acontecem **antes**
   de qualquer rede, com erro explícito.
3. O `BoundModel` devolvido já sabe provider, modelo e papel; quem chama só passa as mensagens.

## Regras do seam

| Regra | Origem | Verificada por |
|---|---|---|
| Resolver papel ausente levanta `RoleNotConfigured`, nunca escolhe modelo | FR-002, US2 cen. 2 | conformidade do seam |
| Toda resolução passa pela allowlist; `provider/model` fora dela levanta `ModelNotAllowed` | FR-003 | conformidade do seam |
| Allowlist vazia significa "nenhuma restrição declarada" e deixa passar | [research.md](../research.md) R9 | conformidade do seam |
| Provider não registrado levanta `UnknownProvider`, sem tentar rede | princípio VII | conformidade do seam |
| Falha de chamada levanta `ModelCallFailed` nomeando provider e modelo | US1 cen. 2, FR-010 | conformidade do seam |
| Nenhum fallback automático entre providers | FR-007 | conformidade do seam |
| Uma chamada emite exatamente um `ModelCall`, inclusive quando falha | FR-008, SC-002 | conformidade do seam |
| Nenhum tipo de SDK ou de HTTP aparece na superfície | princípio XIII | import-linter + revisão da superfície |
| `stream()` entrega o primeiro pedaço antes do fim da geração | princípio XI, US1 cen. 1 | conformidade do seam |

## Saúde (FR-009)

```python
for health in await routing.check(policy):
    if not health.available:
        report(f"{health.role}: {health.ref} indisponível — {health.detail}")
```

- Sonda um provider por papel configurado; **não** gera tokens.
- Nunca levanta por indisponibilidade: o resultado é `available=False` com motivo.
- Não é etapa de boot (R8): quem a chama é o comando de diagnóstico do operador e a saúde da API (Fase 2).

## Suíte de conformidade

`packages/core/tests/llm/contract/test_model_router_seam.py`, parametrizada pelos adapters da porta
(`ScriptedProvider` e `OllamaProvider` com transporte falso), cobrindo:

1. resolução do papel configurado devolve `BoundModel` com `role` e `ref` corretos;
2. papel ausente → `RoleNotConfigured`, sem I/O;
3. referência fora da allowlist → `ModelNotAllowed`, sem I/O;
4. provider desconhecido → `UnknownProvider`, sem I/O;
5. `stream()` entrega pedaços incrementais, e o último traz `finish_reason`;
6. `complete()` devolve `ChatResponse` do contrato 001;
7. provider fora do ar → `ModelCallFailed` cuja mensagem contém provider e modelo;
8. sucesso e falha emitem um `ModelCall` cada, com papel, provider, modelo e duração;
9. `check` devolve um `ModelHealth` por papel configurado, com `available=False` e motivo quando o modelo não existe;
10. duas `ModelPolicy` que diferem só no modelo levam o mesmo código a chamar modelos diferentes — SC-001, "trocar o
    modelo é configuração".

## O que este seam **não** promete

- Não escolhe modelo, não reordena papéis e não tem default (princípio VIII).
- Não repete chamada, não troca de provider e não degrada para texto livre (FR-007; a degradação é proibida pela FR-005,
  cuja verificação chega com a US4, na Fase 3 — abaixo).
- Não interpreta o conteúdo da resposta: tool calls e validação de formato são de quem chama.
- Não conhece Assistant, grant, flow, pack nem HTTP.

---

## Fase 3 (2026-10-02): o que o seam passa a garantir

Assinaturas inalteradas ([research.md](../research.md) R16, R17). Regras novas:

| Regra | Origem | Verificada por |
|---|---|---|
| `ModelRef` com provider `openrouter` e modelo `auto` (forma curta) ou do namespace `openrouter/…` levanta `ValueError` pedindo modelo explícito; sufixos de variante (`:free`, `:nitro`, `:floor`) passam | FR-004, US3 | `tests/llm/unit/test_llm_api.py` |
| A allowlist não libera roteamento automático: a recusa acontece antes, na construção da referência | FR-004, US3 cen. 2 | idem |
| Chamada do papel `controller` sem `response_format` de esquema (`json_schema` com `schema`) levanta `ModelCallFailed` antes do provider, e emite um `ModelCall` com `finish_reason="error"` | FR-005, US4 cen. 3, SC-003 | conformidade do seam |
| A restrição chega ao provider na forma mais rígida dele (`strict: true`; no OpenRouter, `require_parameters`) | FR-005, US4 cen. 1 | [remote-adapters.md](remote-adapters.md) |
| Recusa da restrição pelo provider vira `ModelCallFailed` com provider e modelo; nenhuma segunda chamada | FR-005, US4 cen. 2 | idem |
| Provider remoto sem credencial: `check` → `available=False`, "sem credencial: defina AI_CORE_…"; chamada → `ModelCallFailed` antes da rede | FR-011 | conformidade do seam + [remote-adapters.md](remote-adapters.md) |
| Papéis da mesma política em providers diferentes resolvem cada um para o seu, com um `ModelCall` por papel no provider certo | US2 cen. 1 | conformidade do seam |
| `allow: ["ollama/*"]` e papel em `openai/…` → `ModelNotAllowed` | US5 cen. 1 | conformidade do seam |

### Suíte de conformidade — casos novos

11. `controller` sem `response_format`, com `json_object` e com `json_schema` sem `schema` → `ModelCallFailed` sem
    tocar o provider, e um `ModelCall` de erro;
12. `generation` sem `response_format` continua aceito;
13. política com `controller` em `openrouter` e `generation` em `ollama` (dois simulados) → cada `BoundModel` no seu
    provider, e os `ModelCall` com o provider certo por papel;
14. `check` com um remoto sem credencial → `available=False` com o nome da variável.

## 2026-10-20: custo informado e providers prontos ([ADR-035](../../../docs/adr/ADR-035-custo-informado-pelo-provider-e-providers-prontos.md))

- `ModelRouting.providers() -> tuple[ProviderStatus, ...]`: os providers registrados, por nome, com `ready` e `detail`.
  Nunca levanta; sonda todos juntos. A porta `ModelProvider` ganha `ready()`: o remoto responde pela credencial, sem
  rede; o local (Ollama), pela lista de modelos do endpoint.
- O `ModelCall` que o cliente ligado emite leva `cost_usd` quando o provider informa o custo em `usage.cost`
  (`ChatUsage.cost`, contratos `0.1.3`); o adapter do OpenRouter pede `usage.include` em todo pedido.
