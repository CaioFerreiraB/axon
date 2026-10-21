# Quickstart — validar os validators da 104 (Fase 4, esqueleto)

Dentro de `axon-scouting/`, com `XDG_DATA_HOME=$HOME/.local/share`. Regras em [data-model.md](data-model.md); contrato em
[contracts/validators.md](contracts/validators.md).

## 1. Testes dos validators

```bash
uv run pytest tests/test_citations.py tests/test_integrity.py tests/test_notice.py tests/test_validators_chain.py -v
```

**Esperado**: os oito casos de aceite do contrato, determinismo e "nunca levanta" verdes.

## 2. Os dois em sequência, à mão

```bash
uv run python -c "
import asyncio
from axon_ai_contracts.testing import chunk, turn_view, validator_context
from axon_scouting.validators import CitationIntegrityValidator, ValidityNoticeValidator
ctx = [chunk('man-pio-2023#4.2', document='Manual Pioneiro', version='2023', status='substituído'),
       chunk('man-pio-2026#4.2', document='Manual Pioneiro', version='2026', status='vigente')]
view = turn_view(answer='A regra mudou [[man-pio-2026#4.2]]; antes era outra [[ MAN-PIO-2023#4.2 ]] [[inventado#1]].',
                 generation_context=ctx)
first = asyncio.run(CitationIntegrityValidator().validate(view, validator_context('scouting')))
view = turn_view(answer=first.answer, citations=first.citations, generation_context=ctx)
second = asyncio.run(ValidityNoticeValidator().validate(view, validator_context('scouting')))
print(second.answer); print(first.issues, first.flags | second.flags)"
```

**Esperado**: `A regra mudou [1]; antes era outra [2].` seguido, após uma linha em branco, de
`Atenção: [2] cita Manual Pioneiro (2023), que está substituído — não é a versão vigente.`; uma issue sobre
`inventado#1`; flags `invalid_citation` e `non_current_source`.

## 3. Fronteiras e o que o pack publica

```bash
uv run lint-imports
uv run pytest tests/test_purity.py tests/test_pack.py -v
```

**Esperado**: os três contratos `KEPT`, com `validators` na camada independente e no contrato de modelo e MCP;
nenhuma chamada de relógio em `validators/`; o pack continua sem validators publicados (FR-008).

## 4. Suíte completa e CI

```bash
uv run pytest && uv run --python 3.12 pytest && uv run ruff check && uv run ruff format --check && uv run mypy
```

**Esperado**: tudo verde; no push, os quatro jobs do `ci.yml`.
