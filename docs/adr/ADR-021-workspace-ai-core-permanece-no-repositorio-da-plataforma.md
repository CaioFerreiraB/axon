# ADR-021 — O workspace `ai-core` permanece no repositório da plataforma

- **Status:** Aceita · 2026-10-07
- **Specs afetadas:** [001-core-contracts](../../specs/001-core-contracts/spec.md) (research R1 — supera a separação
  "antes da Fase 4"), [010-core-generic-pack](../../specs/010-core-generic-pack/spec.md), todas as specs `1xx`;
  refina o [ADR-004](ADR-004-contratos-no-repo-do-core.md) quanto a **onde** fica o repositório do core, sem mudar a
  decisão dele
- **Origem:** preparação da Fase 4 (2026-10-07): o mantenedor questionou a separação — o sistema não existe sem o core

## Contexto

O plano da 001 (R1, 2026-09-15) pôs o workspace `ai-core/` como subpasta deste repositório (`agentic-app`) nas Fases
0–3 e marcou a separação num repositório `ai-core` próprio para antes da Fase 4, com a tag `contracts-v0.1.0` criada
já no repositório separado. A Fase 4 começa agora, e o que ela de fato exige é outra coisa: um **pack de domínio** em
repositório próprio, dependendo só de `ai-core-contracts` por versão (ADR-004, ADR-014).

O `ai-core` não é opcional nem tem ciclo de vida próprio diante deste repositório: as specs `0xx` descrevem exatamente
o código do workspace, e cada passada até aqui foi um par "SDD + código" no mesmo histórico.

## Decisão

O workspace `ai-core/` (com `ai-core-contracts`, `ai-core` e `ai-generic`) **permanece** neste repositório. "O
repositório `ai-core`" do ADR-004 passa a ser este repositório; a decisão do ADR-004 — contratos no repositório do
core, packs de domínio em repositórios próprios dependendo só de `ai-core-contracts` com faixa semver — continua
valendo.

- As tags `contracts-vX.Y.Z` são criadas aqui, no commit que fixa a versão dos contratos; a primeira é
  `contracts-v0.1.0`.
- Um pack externo declara a dependência pela faixa (ADR-014) e resolve pela tag, com o subdiretório:
  `ai-core-contracts = { git = "ssh://git@github.com/CaioFerreiraB/agentic-app.git", tag = "contracts-v0.1.0",
  subdirectory = "ai-core/packages/contracts" }` em `[tool.uv.sources]`.
- Packs de domínio (`ai-scouting` e os próximos) vivem em repositórios próprios, privados como este, ligados aqui como
  submódulos na raiz (`ai-scouting/`), para que as specs `1xx` e as skills do spec-kit continuem citando caminhos deste
  repositório. O código do pack é commitado no repositório dele; aqui só muda o ponteiro do submódulo.
- A CI do core continua em `.github/workflows/` da raiz.

## Alternativas rejeitadas

*Repositório `ai-core` próprio, ligado aqui como submódulo (a decisão anterior).* Toda passada de spec do core viraria
dois commits em dois repositórios, mais o ponteiro do submódulo, sem ganho: core e SDD não têm donos nem ciclos de
release diferentes — o mesmo argumento que o ADR-004 usou para não separar contratos e pack genérico.

*Repositório `ai-core` próprio, clonado ao lado.* Além do custo acima, specs e skills passariam a citar caminhos de
outro repositório.

*Publicar `ai-core-contracts` num índice de pacotes já.* Resolve o acesso de packs de terceiros, que ainda não existem;
para os packs do próprio mantenedor, a tag no git basta.

## Consequências

- A Fase 4 não depende de mover código: a tag `contracts-v0.1.0` neste repositório é o pré-requisito do roadmap
- Um PR continua cobrindo spec e código do core; o histórico do core não é reescrito
- Custo: quem instala os contratos pelo git (a CI de um pack externo, o build da instalação da 002 US5) precisa de
  acesso de leitura a este repositório inteiro, specs incluídas — uma deploy key ou token só de leitura. Se surgirem
  donos de packs que não devem ver o SDD, publica-se `ai-core-contracts` num índice privado (sem mudar a faixa nem o
  código dos packs), e este ADR é revisto
- O `agentic-app` passa a ter três linhas de versão por tag: contratos (`contracts-v*`) e, quando houver release, o
  core com o pack genérico (ADR-004, "lançados juntos")
