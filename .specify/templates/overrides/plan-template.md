# Implementation Plan: [FEATURE]

**Branch**: `[###-feature-name]` | **Date**: [DATE] | **Spec**: [link]

**Input**: Feature specification from `/specs/[###-feature-name]/spec.md`

**Architecture inputs** *(PROJECT OVERRIDE — axon)*: before filling Technical Context, READ
`/specs/[###-feature-name]/design.md` (including its "Portas e adapters" section) and every ADR listed
in the spec's Module Boundary, plus ADR-012 (architectural style). Decisions recorded there are
**pre-approved**: carry them into this plan and into `research.md` as
"Decision / Rationale (ADR-xxx) / Alternatives", do not re-research them. Any deviation requires a
new ADR in `docs/adr/` and must be listed in Complexity Tracking.

**Note**: This template is filled in by the `/speckit-plan` command; its definition describes the execution workflow.

## Summary

[Extract from feature spec: primary requirement + technical approach from research]

## Technical Context

<!--
  ACTION REQUIRED: Replace the content in this section with the technical details
  for the project. The structure here is presented in advisory capacity to guide
  the iteration process. Pre-approved stack: constitution "Stack e restrições técnicas".
-->

**Language/Version**: [e.g., Python 3.11, Swift 5.9, Rust 1.75 or NEEDS CLARIFICATION]

**Primary Dependencies**: [e.g., FastAPI, UIKit, LLVM or NEEDS CLARIFICATION]

**Storage**: [if applicable, e.g., PostgreSQL, CoreData, files or N/A]

**Testing**: [e.g., pytest, XCTest, cargo test or NEEDS CLARIFICATION]

**Target Platform**: [e.g., Linux server, iOS 15+, WASM or NEEDS CLARIFICATION]

**Project Type**: [e.g., library/cli/web-service/mobile-app/compiler/desktop-app or NEEDS CLARIFICATION]

**Performance Goals**: [domain-specific, e.g., 1000 req/s, 10k lines/sec, 60 fps or NEEDS CLARIFICATION]

**Constraints**: [domain-specific, e.g., <200ms p95, <100MB memory, offline-capable or NEEDS CLARIFICATION]

**Scale/Scope**: [domain-specific, e.g., 10k users, 1M LOC, 50 screens or NEEDS CLARIFICATION]

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

[Gates determined based on constitution file]

**Module boundary gate** *(PROJECT OVERRIDE — principle II, mandatory)*:

- [ ] Source changes stay inside this module's paths (listed in Project Structure)
- [ ] Every consumed seam is listed with its owner spec; no internals of other modules are used
- [ ] Every seam this module exposes has a conformance test planned
- [ ] No seam changes — or each change has an ADR and the affected consumer specs are listed
- [ ] Import boundaries (import-linter) cover the new code

**Ports & adapters gate** *(PROJECT OVERRIDE — principle XIII, ADR-012, mandatory)*:

- [ ] The module follows `api.py` / `domain/` / `ports.py` / `service.py` / `adapters/` (any collapsed part is justified)
- [ ] `api.py`, `domain/`, `ports.py` and `service.py` import no infrastructure framework (HTTP, DB driver/ORM, vector client, graph framework, model SDK, OIDC library)
- [ ] Other modules are imported only through their `api.py` (only the composition root also imports their `service.py` and `adapters/`); `api.py` does not import the rest of its own module
- [ ] All I/O, time, randomness, secrets and trace go through a secondary port; `domain/` does no I/O
- [ ] Every secondary port exists for I/O, non-determinism or a planned swap — no port for pure rules
- [ ] Every secondary port has an in-memory adapter and a conformance suite that also runs against the real adapter
- [ ] Services and adapters of other modules are instantiated only in the composition root (spec 011), or in `pack.py` for a pack

## Project Structure

### Documentation (this feature)

```text
specs/[###-feature]/
├── spec.md              # Feature spec (what/why)
├── design.md            # Pre-approved technical input carried from the architecture
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)
<!--
  ACTION REQUIRED: Replace the placeholder tree below with the concrete layout
  for this feature, using the real repository paths from design.md
  (e.g. axon-ai/packages/contracts/..., axon-ai/packages/core/src/axon_ai/graph/...,
  axon-scouting/src/axon_scouting/rag/...). The delivered plan must not include Option labels.
-->

```text
# Standard module layout (principle XIII, ADR-012) — replace <module> and the file names
# with the real paths from design.md; drop ports.py/adapters/ only if the module does no I/O.
axon-ai/packages/core/src/axon_ai/<module>/
├── api.py        # seams this module exposes (primary ports) + published value objects
├── domain/       # pure, deterministic policies — no I/O
├── ports.py      # secondary ports (Protocol): storage, clock, secrets, trace, network
├── service.py    # implements api.py by orchestrating domain/ and the ports
└── adapters/     # infrastructure: memory.py, postgres.py, http.py, cli.py, ...

axon-ai/packages/core/tests/<module>/
├── contract/     # conformance suites: exposed seams + each secondary port (in-memory and real adapter)
├── unit/         # domain/ (pure) and service.py wired with in-memory adapters
└── integration/  # real adapters against real infrastructure
```

**Structure Decision**: [Document the selected structure and reference the real
directories captured above]

## Complexity Tracking

> **Fill ONLY if Constitution Check has violations that must be justified**

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| [e.g., 4th project] | [current need] | [why 3 projects insufficient] |
| [e.g., Repository pattern] | [specific problem] | [why direct DB access insufficient] |
