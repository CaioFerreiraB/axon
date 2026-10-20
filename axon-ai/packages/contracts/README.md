# axon-ai-contracts

Contratos públicos do núcleo da plataforma Axon: a **única** superfície que um pack enxerga
([spec 001](../../../specs/001-core-contracts/spec.md)). Só depende da biblioteca padrão e de `typing_extensions`; um pack
que dependa só destes contratos não arrasta runtime, HTTP, framework de grafo nem banco.

## Dependência recomendada

```toml
# pyproject.toml do pack
[project]
dependencies = ["axon-ai-contracts>=0.2,<0.3"]   # nunca axon-ai

[project.entry-points."ai_core.packs"]
meu_pack = "meu_pack.pack:MeuPack"
```

A faixa sai da `contract_version` que o pack declara (`"0.2"` → `>=0.2,<0.3`). A suíte de conformidade aponta dependência
mais larga que isso.

## Escrevendo um pack

Herde de `PackBase` — todo hook opcional já devolve vazio — e defina identidade e manifest:

```python
from axon_ai_contracts import PackBase, PackContext, PackManifest, TurnView


class MeuPack(PackBase):
    name = "meu_pack"
    contract_version = "0.2"

    def manifest(self) -> PackManifest:
        return PackManifest(name="meu_pack", version="0.1.0", preferred_flow="chat")

    async def prepare_context(self, view: TurnView, ctx: PackContext):
        # devolve só a atualização da própria fatia; datas saem de view.reference_time, nunca do relógio
        return {"retrieval_filters": {"effective_on": view.reference_time.date().isoformat()}}
```

- Hooks de catálogo (`system_prompt`, `tools`, `retrievers`, `reranker`, `validators`) são chamados **uma vez**, na carga.
- `tools()` declara só tools **nativas** (com handler assíncrono que recebe um `ToolInvocation`); retrievers viram tools
  `retrieval` pelo core (`retrieval_tool_spec`); tools `mcp` vêm da descoberta do cliente MCP.
- Todo retriever declara as coleções que consulta (`NamedRetriever.collections`).
- Validators são determinísticos e não acessam modelos.

## Testando

O kit `axon_ai_contracts.testing` é só stdlib e funciona com qualquer runner:

```python
from axon_ai_contracts.testing import assert_pack_conforms, turn_view
from meu_pack.pack import MeuPack


def test_pack_conforms():
    assert_pack_conforms(MeuPack(), views=[turn_view(question="pergunta de exemplo")])
```

`turn_view`, `chunk`, `pack_context`, `validator_context` e `tool_invocation` montam fixtures determinísticas (data padrão
`REFERENCE_TIME`). A conformidade verifica forma, identidade, manifest, catálogo, `prepare_context`, validators, imports
proibidos e a dependência declarada; cada problema vem com um código estável (`ISSUE_CODES`). Em código assíncrono,
use `await acheck_pack(...)`.

## Versões

Política do [ADR-014](../../../docs/adr/ADR-014-politica-versoes-0x-contratos.md): enquanto a versão for 0.x, mudança
aditiva sobe o patch e breaking sobe o minor; um símbolo depreciado em 0.N.x só sai a partir de 0.(N+1).0. Regras
completas em [compatibility.md](../../../specs/001-core-contracts/contracts/compatibility.md). `LLMProvider` e `MCPClient`
são provisórios até a tag `contracts-v0.1.0`.

## Fronteiras no repositório do pack

Além da varredura de imports da conformidade, recomenda-se o import-linter no CI do pack:

```toml
[tool.importlinter]
root_packages = ["meu_pack"]
include_external_packages = true

[[tool.importlinter.contracts]]
name = "pack importa só os contratos"
type = "forbidden"
source_modules = ["meu_pack"]
forbidden_modules = ["axon_ai", "axon_generic"]
```

## Desenvolvimento (neste workspace)

```bash
cd axon-ai
uv sync
uv run pytest && uv run mypy && uv run ruff check packages/contracts && uv run lint-imports
uv run python packages/contracts/tools/check_clean_env.py        # SC-001
uv run python packages/contracts/tools/api_surface.py dump       # snapshot da superfície (FR-020)
```

Roteiro completo de validação: [quickstart da 001](../../../specs/001-core-contracts/quickstart.md).
