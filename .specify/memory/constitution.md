<!--
Sync Impact Report
- Version change: 1.2.0 → 1.3.0 (MINOR: orientação materialmente ampliada — componentes novos na
  tabela de stack e no vocabulário; nenhum princípio removido nem redefinido)
- Origem: ADRs 029–034, aceitos em 2026-10-13 (console de administração própria; a plataforma é o
  provedor de identidade; superfície de administração; sobreposição de Assistants de sistema;
  segredos de runtime cifrados; trace com destinos e conteúdo opcional)
- Princípios modificados (títulos inalterados):
  - VI. Conteúdo externo é não-confiável — novo item: segredo configurado em runtime é cifrado com a
    chave mestra da instalação, nunca devolvido pela API, e a variável de ambiente prevalece (ADR-033)
  - XI. API independente da interface; streaming desde o início — o primeiro item passa a cobrir
    Open WebUI e a console: nenhuma lógica de agente nem regra de negócio na interface; toda tela da
    console tem equivalente na API (ADR-029)
- Seções modificadas:
  - Vocabulário normativo — termos novos "Console" e "Sobreposição"
  - Stack e restrições técnicas — linha "Interface" (Open WebUI para chat + console opcional), linha
    nova "Identidade" (provedor OIDC da plataforma, ADR-030), linha de PostgreSQL passa a citar
    contas, sobreposições e uso
- Seções removidas: nenhuma
- Templates: nenhum ajuste necessário (.specify/templates/overrides/* não citam interface, identidade
  nem segredos de runtime)
- Artefatos afetados fora da constituição: specs/README.md (tabela "fora de escopo": a linha da
  interface passa a valer para as duas interfaces; módulos 012 e 013) e docs/roadmap.md (Fase 9) —
  ajustados na mesma sessão, fora deste comando
- TODOs: nenhum.
-->

# Plataforma Agentic AI Constitution

## Core Principles

### I. Núcleo agnóstico de domínio

- O `ai-core` NÃO DEVE conhecer escotismo, finanças ou qualquer outro domínio. Nenhum nome,
  regra, léxico ou prompt de domínio pode aparecer no código ou nas specs do core (exemplos
  ilustrativos em specs são permitidos quando marcados como tal).
- Todo conhecimento de domínio vive em Capability Packs. RAG de domínio pertence ao pack dono do
  domínio; o core fornece apenas o contrato.
- Adicionar um pack ou um Assistant NÃO DEVE exigir modificação no core.

**Por quê:** o core é infraestrutura genérica; qualquer vazamento de domínio vira acoplamento que
impede reescrever packs sem tocar no core.

### II. Módulos substituíveis por seams (NON-NEGOTIABLE)

- Cada módulo tem **exatamente uma spec** em `specs/`, que é a única fonte de verdade sobre seu
  comportamento. A spec declara na seção *Module Boundary* o que consome, o que expõe e o que
  não conhece.
- Módulos se comunicam **apenas por seams** declarados (ver `specs/README.md`), publicados no
  `api.py` do módulo dono. Uma spec NÃO DEVE referenciar detalhes internos de outro módulo: nomes
  de nós, campos de estado interno, tabelas, classes privadas.
- Reescrever um módulo que preserva seus seams NÃO DEVE exigir mudança em nenhuma outra spec
  nem em outro módulo. Mudar um seam exige ADR e lista explícita das specs consumidoras afetadas.
- Os contratos de pack (`ai-core-contracts`) são independentes do motor de execução: não expõem
  tipos do framework de grafo, de HTTP ou de armazenamento (ADR-011, aceito).
- O estado interno do motor de execução é privado do core; packs enxergam apenas a visão estável
  definida nos contratos (ADR-011, aceito).
- Fronteiras de import são verificadas no CI (import-linter) em todo repositório: contratos não
  importam nada do projeto; packs importam apenas contratos; core e `ai-generic` não se importam;
  um módulo do core importa de outro apenas o `api.py` (princípio XIII).

**Por quê:** o mantenedor pretende reescrever por completo o `ai-scouting` e o grafo do `ai-core`
em breve; isso só é barato se cada um estiver atrás de seams estáveis.

### III. O core orquestra; packs fornecem capacidades

- O core é dono da topologia. Packs registram capacidades (tools, retrievers, reranker, prompts,
  validators, preparação de contexto) e NÃO constroem nem alteram grafos (ADR-001).
- Flows são poucos, nomeados e escritos à mão; um flow novo é decisão arquitetural registrada.
  Um pack apenas *seleciona* um flow por nome; o Assistant pode sobrescrever.
- Um único ponto de execução de tools despacha por tipo (`retrieval`, `mcp`, `native`);
  retrieval é tool (ADR-005). Adicionar capacidade nunca exige passo novo no grafo.
- Os passos do grafo são finos: a lógica vive em serviços com spec própria (catálogo, gateway de
  tools, hooks de pack, roteador de modelos). O grafo apenas os ordena. As políticas do próprio
  motor (portão de cobertura, limites) vivem fora do framework de grafo (princípio XIII).
- Escape hatch: um pack PODE fornecer uma rotina isolada, invocada como passo único, operando só
  sobre a própria fatia de estado e com limites herdados. Injeção de nós ou arestas no grafo pai
  é proibida em qualquer hipótese.

### IV. O Assistant é a fronteira de isolamento

- Toda decisão sobre o que uma execução enxerga é resolvida no Assistant: flow, packs, MCPs,
  coleções, política de modelos, limites e ACL (ADR-002).
- A requisição nomeia um Assistant e, no máximo, **restringe** dentro do permitido; NUNCA amplia.
  Campos que ampliariam capacidades são rejeitados explicitamente.
- **Capacidade não declarada não existe**: ela é ausência do catálogo, não permissão negada. O
  modelo nunca vê uma tool que o Assistant não declara.
- Principal não autorizado recebe **404, nunca 403** — a existência de Assistant privado não vaza.
- A cadeia de enforcement (descoberta → resolução → capacidade → MCP → retrieval → provider →
  orçamento) falha fechada em cada elo.

### V. Determinismo antes de LLM

- Se uma decisão pode ser tomada deterministicamente, NÃO se gasta chamada de LLM com ela
  (roteamento, filtros, portões de cobertura, validação).
- O contexto enviado ao LLM é o menor conjunto suficiente; o catálogo em contexto é mínimo.
- Citação é verificada **mecanicamente** no caminho da requisição; julgamento por LLM pertence
  apenas à avaliação offline (ADR-007).
- Todo loop tem limite de iteração; atingir o limite leva a uma resposta com o que se tem e
  registra o truncamento — nunca a loop infinito nem a falha silenciosa.
- Saída estruturada é obrigatória em toda decisão de controle feita por modelo.

### VI. Conteúdo externo é não-confiável

- Toda saída de tool (MCP, retrieval, nativa) entra no contexto delimitada e rotulada como dado;
  **nunca é instrução**. Saída acima do limite é truncada com marca visível.
- MCPs pertencem aos sistemas donos dos dados; credenciais são referências a um secret store e
  são resolvidas server-side; nunca trafegam na requisição do usuário.
- O cliente MCP aplica allowlist de hosts, bloqueio de localhost e faixas privadas (SSRF),
  timeout e limite de resposta.
- Tools que mutam estado são indisponíveis em Assistants públicos por default, exigem declaração
  explícita em Assistants privados e são sempre auditadas (Principal + argumentos).
- Usuário final nunca executa código no processo do core: extensão de usuário é MCP remoto;
  código Python é extensão do operador (ADR-003).
- Segredo configurado em runtime (pela administração) é gravado cifrado com a chave mestra da
  instalação, no módulo dono, e nunca é devolvido pela API; a variável de ambiente da instalação,
  quando definida, prevalece sobre ele (ADR-033).

### VII. Falha fechada e explícita

- Pack com contrato incompatível, manifest inválido ou erro de instanciação não carrega, é
  registrado e aparece com erro na introspecção; o sistema sobe sem ele.
- Assistant que depende de algo indisponível fica indisponível **com erro explícito** — nunca
  silenciosamente degradado.
- Incompatibilidades são detectadas o mais cedo possível: no build da imagem, depois no boot,
  depois na validação da requisição (4xx antes de qualquer custo).

### VIII. Modelos explícitos por papel

- Provider e modelo são sempre explícitos e podem variar por papel (`controller`, `generation`,
  `rerank`) (ADR-008). Variantes de roteamento automático de modelo são proibidas.
- Todo uso de modelo passa por allowlist de provider/modelo do Assistant.

### IX. Proveniência e vigência das fontes

- Conteúdo recuperado preserva fonte, versão e vigência; o texto original é a fonte de verdade e
  chunks são índice, não substituto.
- Fonte não vigente citada numa resposta DEVE ser marcada como tal na resposta.
- Relações inferidas por LLM são distinguidas de relações presentes na fonte e nunca citadas do
  mesmo modo.

### X. Medir antes de calibrar

- Nenhum número de RAG ou de modelo (top_k, tamanho de chunk, limiar de portão, escolha de
  embedding ou de LLM) é fixado sem medição contra o conjunto dourado do domínio.
- O harness de avaliação roda em CI a cada mudança de chunking, prompt, retriever ou modelo.

### XI. API independente da interface; streaming desde o início

- A API NÃO DEPENDE de interface gráfica. Open WebUI e a console de administração são só
  apresentação: nenhuma lógica de agente nem regra de negócio (validação, autorização, precedência
  de configuração) vive nelas, e toda tela da console tem equivalente na API (ADR-029).
- Streaming faz parte do contrato desde a primeira fase; não é retrofit.

### XII. Simplicidade deliberada

- Não entra na arquitetura componente sem caso de uso (ex.: motor de workflow durável — ADR-010).
- Toda complexidade adicional num plano é justificada na tabela *Complexity Tracking*.

### XIII. Portas e adapters por módulo

- A arquitetura tem um estilo nomeado por escala (ADR-012): o **sistema** é um microkernel (o core
  é o kernel dono do fluxo; packs e servidores MCP são plug-ins; `ai-core-contracts` é o contrato
  de plug-in); a **organização** do core é um monolito modular (um processo, uma imagem, módulos
  com seams); cada **módulo** é hexagonal, com as políticas determinísticas no centro (núcleo
  funcional).
- Cada módulo separa `api.py` (seams que expõe e value objects publicados), `domain/` (políticas
  puras), `ports.py` (portas secundárias como `Protocol`), `service.py` (implementa `api.py`
  orquestrando `domain/` e as portas) e `adapters/` (infraestrutura). Módulo sem I/O PODE omitir
  `ports.py` e `adapters/`. Packs seguem a mesma organização por dentro.
- Todo acesso a I/O (banco, rede, disco, provedor de modelo), a tempo, a aleatoriedade, a segredos
  e a trace passa por porta secundária. `domain/` NÃO DEVE fazer I/O.
- Um módulo NÃO DEVE importar de outro nada além do `api.py`. A única exceção é a composition
  root, que importa também o `service.py` e os `adapters/` dos módulos para construí-los.
  `api.py` NÃO DEVE importar o resto do próprio módulo. `api.py`, `domain/`, `ports.py` e
  `service.py` NÃO DEVEM importar frameworks de infraestrutura (HTTP, driver ou ORM de banco,
  cliente de vetores, framework de grafo, SDK de provedor de modelo, biblioteca de OIDC).
- Só a composition root (spec 011) instancia serviços e adapters de outros módulos e os injeta
  nas portas; num pack, esse papel é do `pack.py`.
- Uma porta secundária existe só onde há I/O, não-determinismo (tempo, aleatoriedade, LLM) ou
  troca prevista em roadmap ou ADR. Regra pura não ganha porta.
- Toda porta secundária tem um adapter em memória e uma suíte de conformidade que roda contra ele
  e contra o adapter real.
- A direção dos seams entre módulos não muda: o seam pertence a quem o implementa. Inverter uma
  dependência entre módulos só é aceitável para quebrar ciclo e exige ADR.

**Por quê:** o core é essencialmente integração (providers, MCP, bancos, vetores, identidade), e as
trocas previstas no roadmap (memória → Postgres, modelo de embedding, reranker, backend de trace,
framework do grafo) são trocas de adapter. Com a infraestrutura atrás de portas, cada troca vira um
adapter novo mais uma mudança na composition root, e a reescrita do grafo preserva as políticas e
seus testes.

## Vocabulário normativo

Os termos abaixo têm significado único em todas as specs, planos e código.

| Termo | Definição |
|---|---|
| **Capability Pack** (pack) | Unidade de extensão que fornece capacidades. Não é agente e não tem grafo próprio |
| **Assistant** | Configuração nomeada server-side que amarra flow + packs + MCPs + coleções + modelos + limites + ACL. É a fronteira de isolamento |
| **Principal** | Identidade autenticada da requisição (usuário, serviço ou chave de API) |
| **Flow** | Topologia de execução escrita à mão pelo core, referenciada por nome |
| **Tool** | Capacidade invocável com schema; retrieval e chamadas MCP são tools |
| **Seam** | Interface pública pela qual um módulo é consumido por outro — a porta primária, publicada no `api.py` do módulo dono; o único ponto de acoplamento permitido |
| **Porta secundária** | Interface (`Protocol`) que um módulo declara em `ports.py` para o que ele aciona fora de si: armazenamento, rede, tempo, segredos, trace |
| **Adapter** | Implementação de uma porta com uma tecnologia concreta (Postgres, Qdrant, FastAPI, LangGraph, SDK de provedor) ou em memória, para testes |
| **Composition Root** | O único código que instancia adapters e os injeta nas portas dos módulos: spec 011 no core; `pack.py` num pack |
| **Execution Grant** | Resultado da resolução de um Assistant para um Principal: a configuração efetiva, já restrita, de uma execução |
| **Turn View** | Visão somente-leitura e estável da execução entregue aos hooks de pack (ADR-011) |
| **Operador** | Quem administra a instalação: escolhe packs, builda a imagem, define Assistants de sistema |
| **Usuário** | Quem consome a plataforma: cria Assistants próprios e registra MCPs próprios |
| **Console** | Interface de administração da plataforma, opcional na instalação e restrita ao grupo de administração; consome só a API (ADR-029) |
| **Sobreposição** | Alteração em runtime de uma seção de um Assistant de sistema que o YAML do operador declara sobreponível; o YAML continua sendo o teto (ADR-032) |

```text
Pack       → o que o sistema SABE FAZER      (capacidade)
Assistant  → o que uma execução PODE FAZER   (fronteira)
Flow       → COMO a execução acontece        (controle)
Estado     → o que a execução CARREGA        (dados — privado do core)
Contexto   → a que a execução TEM ACESSO     (serviços, já restritos)
```

## Stack e restrições técnicas

Decisões pré-aprovadas. Um plano que diverge delas precisa de ADR.

| Componente | Tecnologia |
|---|---|
| Linguagem | Python (versão fixada no plano da spec 001) |
| API | FastAPI, compatível com o formato OpenAI, streaming SSE — adapter primário (spec 008) |
| Orquestração | LangGraph — adapter interno do motor (spec 005, `adapters/langgraph/`), nunca exposto a packs |
| Componentes auxiliares | LangChain, somente quando útil e somente dentro de adapters do core |
| LLM local / externo | Ollama · OpenAI · OpenRouter — adapters do contrato `LLMProvider` (spec 006) |
| Vetores | Qdrant (denso + esparso, fusão nativa) — adapter do índice do scouting (spec 102) |
| Registries, histórico, auditoria, contas, sobreposições, uso | PostgreSQL — adapters das portas de armazenamento de cada módulo |
| Interface | Open WebUI (chat, via compat OpenAI) · console de administração própria (SPA React + TypeScript, opcional na instalação; ADR-029) |
| Identidade | Provedor OIDC da própria plataforma (módulo 012): contas locais com senha argon2id e login Google só para usuários cadastrados; a 003 verifica o JWT localmente (ADR-030) |
| Packs | Distribuições Python descobertas por entry point `ai_core.packs` |
| Contratos | `ai-core-contracts`, semver próprio com convenção 0.x deslocada (ADR-014), apenas stdlib + `typing_extensions` |
| Composição | Composition root na spec 011 (`ai_core/bootstrap/`); num pack, o `pack.py` |
| Repositório do core | uv workspace (`contracts`, `core`, `generic`) + import-linter (fronteiras entre distribuições, `api.py` entre módulos, camadas dentro do módulo) |
| Deploy | Imagem Docker com lista de packs por build-arg; `ai-core packs check` no build |

Restrições de ambiente:

- Hardware alvo: 2 OCPU · 12 GB RAM · ARM64 · sem GPU. Expectativa: 5–15 tokens/s com modelo
  local de ~1.7B; tool calling nesse porte é nominal, não confiável.
- Repositórios: `ai-core` (contratos + core + pack genérico), um repositório por pack de domínio
  (`ai-scouting`, …) e um repositório de instalação por deploy. Packs dependem de
  `ai-core-contracts` por faixa semver (`>=0.1,<0.2`), nunca de `ai-core`.
- Versionamento (ADR-014): semver em `ai-core-contracts` com a convenção 0.x deslocada —
  enquanto o major for 0, mudança aditiva sobe o patch e breaking sobe o minor; a partir de 1.0,
  aditiva sobe o minor e breaking sobe o major. A faixa do pack é derivada da `contract_version`
  (`0.N` → `>=0.N,<0.(N+1)`; `X.Y` → `>=X.Y,<(X+1)`). Janela de depreciação de uma série
  compatível: um símbolo depreciado em 0.N.x só sai a partir de 0.(N+1).0. A `contract_version`
  do pack é verificada no boot, e o CI dos contratos barra bump insuficiente e remoção sem
  depreciação prévia.

## Organização do SDD e fluxo de trabalho

- **Blocos de numeração** em `specs/`: `0xx` = repositório `ai-core` (core, contratos, pack
  genérico); `1xx` = `ai-scouting`; `2xx`+ = packs futuros. Specs novas são criadas no bloco do
  módulo dono.
- Toda spec contém a seção **Module Boundary** (obrigatória pelo template do projeto), incluindo
  a linha de dependências de infraestrutura (via portas).
- `design.md` em cada pasta de spec contém as decisões técnicas herdadas da arquitetura e a seção
  obrigatória **Portas e adapters** (porta, tipo, adapters por fase, teste). É insumo obrigatório
  do `/speckit-plan`: suas decisões são pré-aprovadas e não são re-pesquisadas; divergir delas
  exige ADR.
- Decisões arquiteturais vivem em `docs/adr/`. Um ADR nunca é editado depois de aceito: é
  substituído por outro. O estilo arquitetural está no ADR-012 e em
  `docs/relatorio-estilo-arquitetural.md`.
- Fluxo por spec: `/speckit-clarify` → `/speckit-plan` → `/speckit-tasks` → `/speckit-analyze`
  → `/speckit-implement`. A ordem entre specs segue `docs/roadmap.md`.
- Specs escritas em português; títulos de seção do template permanecem em inglês para manter
  compatibilidade com as skills do spec-kit.

## Governance

- Esta constituição prevalece sobre qualquer outra prática, spec ou plano. Em conflito, a spec
  ou o plano é corrigido — ou a constituição é emendada explicitamente.
- Emendas: via `/speckit-constitution`, com Sync Impact Report, e ADR quando a emenda muda uma
  decisão arquitetural.
- Versionamento desta constituição: MAJOR para remoção ou redefinição de princípio; MINOR para
  princípio ou seção nova; PATCH para redação.
- Todo `plan.md` DEVE, no *Constitution Check*, verificar explicitamente os princípios II
  (fronteira do módulo e seams), IV (isolamento) e XIII (portas e adapters), além dos demais
  aplicáveis.
- Todo PR de implementação DEVE passar nas verificações de fronteira de import, na suíte de
  conformidade dos seams que o módulo expõe e nas suítes das portas secundárias que ele declara.

**Version**: 1.3.0 | **Ratified**: 2026-09-10 | **Last Amended**: 2026-10-13
