# Changelog — ai-core-contracts

Política de versões: [ADR-014](../../../docs/adr/ADR-014-politica-versoes-0x-contratos.md) — enquanto 0.x, mudança
aditiva sobe o patch e breaking sobe o minor. Mudança só de semântica, sem mudança de forma, é registrada aqui e
classificada na revisão (FR-020).

## 0.1.0 — não lançada

Primeira versão dos contratos (spec 001, Fase 0; US1–US4).

### Contrato de pack

- `AgentPack` (Protocol com a forma completa) e `PackBase` (defaults dos hooks opcionais), `PackManifest`, `PackContext`
  (só dados de carga), `RETRIEVAL_FILTERS_KEY`.
- Tools: `ToolSpec` (só tools nativas declaradas pelo pack), `ToolInvocation`, `NativeHandler`, `ToolResult`, `ToolKind`.
- Recuperação: `Chunk`, `Retriever`, `Reranker`, `NamedRetriever` (com coleções), `retrieval_tool_spec`,
  `RETRIEVAL_TOOL_PARAMETERS`.
- Validação: `AnswerValidator`, `ValidatorContext` (sem modelos), `ValidationResult`.
- Regras de declaração: `ContractIssue`, `check_declaration`.

### Turn View

- `TurnView` imutável em profundidade, com `reference_time` (datetime com fuso) e `generation_context`; `Message` e
  `Citation` como TypedDicts somente-leitura.

### Versões e depreciação

- `Version`, `VersionRange` (subconjunto do PEP 440 só com stdlib), `derive_range`, `check_compatibility`,
  `Compatibility`, `removal_version`, `required_bump`, `declared_bump`, `ContractDeprecationWarning`,
  `contract_deprecated`.

### Contratos de serviço (provisórios até a tag `contracts-v0.1.0`)

- `LLMProvider` e os TypedDicts de chat (`ChatMessage`, `ChatTool`, `ChatToolCall`, `ChatUsage`, `ChatResponse`,
  `ChatChunk`); `MCPClient`. A 006 e a 007 podem refinar essas formas antes da tag.

### Kit de testes (`ai_core_contracts.testing`)

- Fixtures (`turn_view`, `chunk`, `pack_context`, `validator_context`, `tool_invocation`, `REFERENCE_TIME`), suíte de
  conformidade de pack (`acheck_pack`, `check_pack`, `assert_pack_conforms`, `aassert_pack_conforms`,
  `ConformanceReport`), checagens reutilizáveis (`check_imports`, `check_contracts_requirement`), suítes mínimas de
  serviço (`acheck_llm_provider`, `acheck_mcp_client`) e `ISSUE_CODES`.
