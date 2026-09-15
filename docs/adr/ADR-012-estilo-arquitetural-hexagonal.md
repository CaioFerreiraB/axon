# ADR-012 — Estilo arquitetural: microkernel, monolito modular e hexagonal por módulo

- **Status:** Aceita · 2026-09-14
- **Specs afetadas:** todas (seção "Portas e adapters" em cada `design.md`); constituição; templates do projeto em
  `.specify/templates/overrides/`; [specs/README.md](../../specs/README.md); spec nova `011-core-bootstrap`
- **Origem:** revisão da SDD sob a ótica do estilo arquitetural — [relatório](../relatorio-estilo-arquitetural.md)

## Contexto

A SDD fixa fronteiras entre módulos (seams, princípio II) e entre core e packs (contrato 001, ADR-004, ADR-011), mas não
diz como cada módulo se organiza por dentro. Os `design.md` misturam regra, I/O e framework. A leitura completa encontrou:

1. Persistência sem portas: Postgres citado diretamente em 003, 004, 005, 007 e 008, embora o roadmap preveja trocas
   (memória → Postgres).
2. Segredos sem porta (006, 007).
3. Tempo sem porta: vigência "hoje" em 101 e 103; rate limit por minuto em 003.
4. Trace sem seam: 004, 005 e 006 "reportam à 009", sem mecanismo definido, e há um ciclo 005↔009 não declarado.
5. Ciclo 003↔007 omitido no grafo de dependências.
6. Ninguém é dono do wiring, da ordem de boot, da montagem do `AgentContext` nem da raiz do CLI.
7. Adapter HTTP (`Depends(oidc)`) no `design.md` da 003.
8. Scouting acoplado ao Qdrant e ao modelo de embedding, que é decisão aberta por medição.

Ainda não há código escrito, então fixar o estilo agora custa só edição de texto.

## Decisão

1. **Sistema — microkernel.** O `ai-core` é o kernel e dono do fluxo (ADR-001). Packs são plug-ins, `ai-core-contracts`
   é o contrato de plug-in, o Pack Registry é o registro, e o MCP é plug-in fora de processo (ADR-003). É o nome oficial
   do que já existe.
2. **Organização — monolito modular.** Um processo e uma imagem (ADR-009); um módulo por spec; seams como `Protocol`;
   fronteiras no import-linter. É o nome oficial do que já existe.
3. **Módulo — hexagonal (Ports & Adapters) com núcleo funcional.** Cada módulo separa:
   - `api.py` — seams publicados (portas primárias) e value objects, sem dependências além de stdlib, contratos e o
     `api.py` de outros módulos;
   - `domain/` — políticas puras e determinísticas, sem I/O;
   - `ports.py` — portas secundárias (`Protocol`) para I/O, tempo, segredos e trace;
   - `service.py` — implementação de `api.py`, orquestrando `domain/` e as portas;
   - `adapters/` — infraestrutura (Postgres, memória, HTTP, CLI, LangGraph, Qdrant, SDKs de LLM).

   Módulos sem I/O dispensam `ports.py` e `adapters/`. Packs seguem a mesma organização por dentro.
4. **Regras de import** (import-linter):
   - (a) um módulo só importa o `api.py` de outro;
   - (b) `api.py`, `domain/`, `ports.py` e `service.py` não importam frameworks de infraestrutura;
   - (c) só a composition root importa `adapters/` de outro módulo.
5. **Só criar porta onde ela se paga:** I/O, não-determinismo (tempo, aleatoriedade, LLM) ou troca prevista em roadmap ou
   ADR. Regra pura não ganha porta.
6. **A direção entre módulos não muda.** O seam continua pertencendo a quem o implementa (princípio das dependências
   estáveis). A inversão de dependência só entra para infraestrutura e para quebrar ciclos.
7. **Composition root.** A spec nova `011-core-bootstrap` é dona da configuração, da escolha de adapters por fase, da
   ordem de boot (que sai do `design.md` da 002), da injeção dos seams e adapters em cada módulo e dos pontos de entrada
   (`ai-core serve` e raiz do CLI). É o único código que instancia adapters de outros módulos. O `AgentContext` continua
   interno da 005: o `service.py` do motor o monta por execução, a partir do grant, com os seams que a 011 injetou. No
   pack, o papel de composition root é do `pack.py`.
8. **Da Clean Architecture** adota-se só a regra de dependência, que já é imposta. Não se adotam anéis globais,
   interactors, presenters nem modelos de requisição e resposta por fronteira.

## Alternativas rejeitadas

*Clean Architecture completa.* Os anéis globais (`entities/`, `usecases/`, `adapters/`) cortam os módulos e brigam com
"um módulo = uma spec = um caminho". O anel de Entidades seria fino, porque o core tem política e orquestração, não
regras de negócio ricas. A execução de um turno viraria um interactor gigante. Presenters e DTOs por fronteira duplicam
`AsyncIterator[ExecutionEvent]` e os value objects dos seams. O que a Clean tem de valioso, a regra de dependência, entra
pela decisão 8.

*Onion.* Mesma regra de dependência, supondo um modelo de domínio rico no centro. Não acrescenta nada ao hexagonal
neste sistema.

*Camadas (n-tier).* A dependência aponta para a persistência, que é o oposto do que as trocas de fase pedem. As camadas
horizontais cortam os módulos verticais e o estilo não tem noção de plug-in.

*Microsserviços.* Poria rede entre motor, gateway e roteador em toda requisição, numa VM de 2 OCPU, e operação
distribuída para um único mantenedor. As fronteiras de processo que fazem falta já existem via MCP. Contraria o princípio
XII.

*Vertical Slice.* Aceita duplicação entre fatias, enquanto a cadeia de enforcement e o gateway único de tools (ADR-005)
existem para que a segurança não se repita.

*Event-driven como estilo global.* Não há integração assíncrona entre módulos (ADR-010). *Pipes & filters* continua
válido localmente, na ingestão (102).

*Deixar o interior dos módulos a critério de cada plano.* Cada `/speckit-plan` decidiria de novo onde fica a
infraestrutura. As trocas de fase virariam refatoração em vez de adapter novo, e a reescrita do grafo (005) perderia as
políticas junto com o framework.

## Consequências

- Trocas do roadmap passam a ser um adapter novo mais uma mudança na composition root
- Todo seam e toda porta secundária ganham um adapter em memória e uma suíte de conformidade que roda contra o adapter em
  memória e o real
- Reescrever o grafo significa trocar `ai_core/graph/adapters/langgraph/` e preservar `domain/` com seus testes
- Os ciclos entre specs (003↔007, 005↔009) deixam de ser ciclos de import
- Custo: mais arquivos por módulo e uma spec a mais (011); o risco de indireção desnecessária é controlado pela decisão 5
  e pelo Constitution Check
- Custo: todos os `design.md` ganham a seção "Portas e adapters"

## Se for aceito

Emendar, nesta ordem:

1. Constituição, via `/speckit-constitution` (MINOR 1.1.0): princípio XIII "Portas e adapters"; vocabulário (Porta,
   Adapter, Composition Root); na tabela de stack, LangGraph, Postgres e Qdrant como adapters.
2. `.specify/templates/overrides/spec-template.md` e `plan-template.md`.
3. `specs/README.md` (estilo, mapa, grafo corrigido, 011) e `CLAUDE.md`.
4. `docs/roadmap.md` (011 na Fase 1).
5. `design.md` de cada módulo, na ordem das fases.

A lista detalhada está na seção 7 do [relatório](../relatorio-estilo-arquitetural.md).

## Se for rejeitado

Nada muda nas specs, e as lacunas passam a ser resolvidas plano a plano. Mesmo assim, as lacunas 4 e 5 (ciclos ocultos)
precisam ser corrigidas no `specs/README.md`.
