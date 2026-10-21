# Quickstart — validar `axon-ai-contracts` 0.2

Guia de validação da Fase 0 (US1–US4). Mostra como provar que a entrega funciona; o código em si sai do `tasks.md`.
Referências: [python-api.md](contracts/python-api.md), [compatibility.md](contracts/compatibility.md),
[testing-kit.md](contracts/testing-kit.md), [data-model.md](data-model.md).

## Pré-requisitos

- `uv` ≥ 0.12 (baixa o Python 3.14 do workspace e o 3.12 do piso: `uv python install 3.14 3.12`)
- `git` (o repositório foi inicializado em 2026-09-15; tags `contracts-v*` só a partir da Fase 4)
- Rede para resolver `typing_extensions` e as ferramentas de dev na primeira sincronização

Todos os comandos rodam a partir de `axon-ai/`, salvo indicação.

```bash
cd axon-ai
uv sync                                  # workspace + grupo dev; Python 3.14 via .python-version
```

## 1. Suíte dos contratos

```bash
uv run pytest packages/contracts/tests                                   # 3.14
uv run --no-project --python 3.12 --with ./packages/contracts --with pytest --with pytest-asyncio \
  --with hypothesis --with packaging pytest packages/contracts/tests -q      # piso, fora do workspace (3.14)
uv run ruff check packages/contracts && uv run ruff format --check packages/contracts
uv run mypy packages/contracts/src
```

**Esperado**: tudo verde nas duas versões. Os testes cobrem imutabilidade em profundidade, invariantes dos value objects,
defaults do `PackBase`, `retrieval_tool_spec`, a regra de versões (incluindo os testes diferenciais contra `packaging`) e
a depreciação.

## 2. Fronteiras (FR-001, FR-017)

```bash
uv run lint-imports
uv run pytest packages/contracts/tests/boundary
```

**Esperado**: o import-linter passa nos contratos da Fase 0 (sem frameworks do runtime; runtime não importa `testing`);
o teste de allowlist confirma que só há imports da stdlib, de `typing_extensions` ou do próprio pacote, e que nenhum
módulo de runtime importa I/O ou relógio. Para ver a falha: acrescente `import os` a `pack.py` → o teste nomeia arquivo,
linha e módulo.

## 3. Pack num ambiente limpo (US1, SC-001)

```bash
tmp=$(mktemp -d)
uv venv --python 3.14 "$tmp/venv"
uv pip install --python "$tmp/venv" ./packages/contracts ./packages/contracts/tests/fixtures/contract_test_pack
uv pip freeze --python "$tmp/venv"
```

**Esperado**: exatamente três distribuições — `axon-ai-contracts`, `typing-extensions` e `contract-test-pack`. Nada de
runtime, HTTP, grafo, banco ou vetores.

```bash
uv pip install --python "$tmp/venv" pytest
"$tmp/venv/bin/pytest" packages/contracts/tests/fixtures/contract_test_pack/tests
```

**Esperado**: os testes do pack passam usando só `axon_ai_contracts.testing` (fixtures de Turn View e
`assert_pack_conforms`) — US1 cenário 2, SC-003.

## 4. Conformidade e declaração (US1 cenário 3, US2)

Rode a suíte de conformidade contra os packs defeituosos de `packages/contracts/tests/conformance/`:

```bash
uv run pytest packages/contracts/tests/conformance -v
```

**Esperado** — cada pack defeituoso produz exatamente o código previsto em [testing-kit.md](contracts/testing-kit.md):

| Pack de teste | Código |
|---|---|
| importa `axon_ai` | `imports.forbidden` (arquivo, linha e módulo na mensagem) |
| duas tools com o mesmo nome | `tool.duplicate_name` |
| retriever com o nome de uma tool nativa | `retriever.name_collision` |
| retriever sem coleção | `ValueError` na construção do `NamedRetriever` → `hook.raised` no hook `retrievers` |
| tool declarada com `kind="retrieval"` | `tool.not_native` |
| `parameters` sem `type: "object"` | `tool.parameters.invalid` |
| `prepare_context` devolve valor não-JSON | `prepare_context.not_json` |
| validator não determinístico | `validator.non_deterministic` |
| reranker que devolve mais que `top_k` ou chunk que não veio da entrada | `reranker.contract` |
| herda de `PackBase` sem hooks opcionais | nenhuma issue; hooks devolvem vazio (US2 cenário 2) |

Os contratos de serviço têm a mesma prova, em `tests/conformance/test_service_conformance.py`: o provider e o cliente MCP
falsos passam em `acheck_llm_provider` e `acheck_mcp_client`, e cada variante quebrada produz o código previsto
(`llm.response.invalid`, `llm.stream.invalid`, `mcp.discovery.invalid`, `mcp.result.invalid`).

## 5. Compatibilidade (US3)

```bash
uv run python -c "from axon_ai_contracts import check_compatibility as c; print(c('0.2', installed='0.2.1')); print(c('0.3', installed='0.2.1').message)"
```

**Esperado**: o primeiro resultado com `ok=True`; a mensagem do segundo é `requer axon-ai-contracts>=0.3, instalado
0.2.1`. As tabelas de [compatibility.md §4](contracts/compatibility.md) viram testes parametrizados em
`tests/unit/test_compat.py`.

Dependência declarada (FR-018): `check_contracts_requirement(["axon-ai-contracts>=0.2"], "0.2")` (uma dependência
sem teto) devolve `distribution.range_too_wide` citando `>=0.2,<0.3`; com `["axon-ai-contracts>=0.2,<0.3"]`, que é o que o
`contract_test_pack` declara, não devolve nenhuma issue.

Depreciação (US3 cenário 3): o teste com um símbolo depreciado só nos testes (`since="0.1.0"`) confirma a
`ContractDeprecationWarning` com `desde axon-ai-contracts 0.1.0` e `será removido em 0.2.0`, e a issue
`deprecation.used` na conformidade.

## 6. Turn View (US4)

```bash
uv run pytest -v packages/contracts/tests/unit/test_view_types.py packages/contracts/tests/unit/test_view_immutability.py \
  packages/contracts/tests/unit/test_contexts_no_services.py packages/contracts/tests/conformance/test_conformance_prepare_context.py
```

**Esperado**:

- montar a view com `list`/`dict` mutáveis e alterar os originais depois não muda a view; atribuir campo ou item levanta
  erro (cenário 1);
- a view da fixture e a montada à mão com os mesmos dados são iguais (`==`), e o mesmo hook devolve o mesmo resultado
  com as duas (independent test — a metade "motor real" é da conformidade da 005);
- uma view montada para um pack sem `depends_on` não tem fatias de outros packs (cenário 2);
- `reference_time` sem fuso é rejeitado;
- `ValidatorContext` não tem nenhum atributo de modelo ou serviço (cenário 3).

## 7. Detecção de breaking change (FR-020, SC-004)

Antes da tag `contracts-v0.1.0` o job de CI só registra "sem linha de base". Para validar a ferramenta localmente:

```bash
uv run python packages/contracts/tools/api_surface.py dump > "$tmp/head.json"
uv run python packages/contracts/tools/api_surface.py diff "$tmp/head.json" "$tmp/head.json" --old-version 0.1.0 --new-version 0.1.0
uv run pytest packages/contracts/tests/surface -v
```

**Esperado**: `diff` sem mudanças e saída 0. Os testes de `tests/surface/` cobrem **cada linha** da tabela de
classificação de [compatibility.md §7](contracts/compatibility.md) com pares de snapshots sintéticos, além da decisão
"bump declarado < exigido → falha" (§8).

Depois da tag (Fase 4), o CI também roda os testes do `contract_test_pack` **da tag** contra os contratos do HEAD —
só enquanto o HEAD estiver na mesma série compatível da tag; numa série nova, o job registra "série nova" e passa
([compatibility.md §8](contracts/compatibility.md)). Remover um símbolo que não estava depreciado na tag falha o `diff`.

## 8. CI

`.github/workflows/contracts.yml` (na raiz enquanto `axon-ai/` for subpasta) executa as seções 1–4 e 6, em matriz
3.12/3.13/3.14 onde há testes, e a seção 7 com a regra da tag. Um PR que muda a superfície pública sem o bump exigido
falha antes do merge.

## 9. Identidade Axon (US6, ADR-037)

```bash
uv run python -c "import axon_ai_contracts as c; print(c.__version__)"
uv run python -c "import ai_core_contracts" 2>&1 | tail -1
uv run python -c "from axon_ai_contracts import check_compatibility as c; print(c('0.1', installed='0.2.0').message)"
uv run python -c "from axon_ai_contracts.testing import check_contracts_requirement as r; print([i.code for i in r(['ai-core-contracts>=0.1,<0.2'], '0.2')])"
uv run pytest packages/contracts/tests/surface packages/contracts/tests/boundary -v
```

**Esperado**: `0.2.0`; `ModuleNotFoundError: No module named 'ai_core_contracts'` (corte seco, cenário 1); `requer
axon-ai-contracts<0.2, instalado 0.2.0` (cenário 2); `['distribution.missing_requirement']` (cenário 3); e os testes de
superfície e de fronteira passam, inclusive o do renome (cenário 4).

Contra a última tag, como no CI (`contracts.yml`, job `surface`):

```bash
git worktree add "$tmp/base" contracts-v0.1.2   # a última tag; a 0.1.3 não foi marcada
uv run --isolated --no-project --with "$tmp/base/ai-core/packages/contracts" python packages/contracts/tools/api_surface.py \
  dump --package ai_core_contracts --output "$tmp/old.json"
uv run python packages/contracts/tools/api_surface.py dump --output "$tmp/new.json"
uv run python packages/contracts/tools/api_surface.py diff "$tmp/old.json" "$tmp/new.json" --old-version 0.1.2 --new-version 0.2.0
git worktree remove "$tmp/base"
```

**Esperado**: três linhas — `[breaking] axon_ai_contracts: distribuição renomeada: ai-core-contracts (ai_core_contracts) →
axon-ai-contracts (axon_ai_contracts)`, `[additive] axon_ai_contracts.ChatUsage['cost']: chave nova opcional` (0.1.3) e
`[breaking] axon_ai_contracts.testing.check_imports: parâmetros alterados` (default de `forbidden`) —, `bump exigido:
minor; declarado: minor` e saída 0; com `--new-version 0.1.4`,
saída 1 ("bump declarado menor que o exigido").

## 10. O pack prepara os próprios dados (0.2.1, ADR-041)

A partir de `axon-ai/`:

```bash
uv run pytest packages/contracts/tests/conformance/test_conformance_prepare.py packages/contracts/tests/unit -q
git worktree add "$tmp/base" contracts-v0.2.0
uv run --isolated --no-project --with "$tmp/base/axon-ai/packages/contracts" python packages/contracts/tools/api_surface.py \
  dump --output "$tmp/old.json"
uv run python packages/contracts/tools/api_surface.py dump --output "$tmp/new.json"
uv run python packages/contracts/tools/api_surface.py diff "$tmp/old.json" "$tmp/new.json" --old-version 0.2.0 --new-version 0.2.1
git worktree remove --force "$tmp/base"
```

**Esperado**: os testes verdes; no diff, só linhas `[additive]` — `PackBase.prepare`, `PackContext.data_dir`,
`PreparesData`, o código `hook.not_sync` e o parâmetro `data_dir` em `pack_context`, `acheck_pack` e variantes — e
`bump exigido: patch; declarado: patch`, saída 0.
