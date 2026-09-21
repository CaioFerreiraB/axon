# Contrato — seam Model Router (006)

Dono: spec 006. Consumidores: 005 (executa), 011 (monta e verifica saúde), 003 e 008 a partir da Fase 2.
Publicado em `ai_core/llm/api.py`. **Mudar qualquer assinatura abaixo exige ADR** (princípio II).

## Superfície

```python
from ai_core.llm.api import (
    BoundModel, ModelHealth, ModelPolicy, ModelRef, ModelRole, ModelRouter, ModelRouting,
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
  cuja verificação chega com a US4, na Fase 3).
- Não interpreta o conteúdo da resposta: tool calls e validação de formato são de quem chama.
- Não conhece Assistant, grant, flow, pack nem HTTP.
