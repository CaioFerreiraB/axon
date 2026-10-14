# ADR-029 — Console de administração própria

- **Status:** Aceita · 2026-10-13
- **Specs afetadas:** [013-core-admin-console](../../specs/013-core-admin-console/spec.md) (nova),
  [008-core-http-api](../../specs/008-core-http-api/spec.md) (superfície de administração, ADR-031),
  [002-core-pack-runtime](../../specs/002-core-pack-runtime/spec.md) (instalação com ou sem console); constituição
  (tabela de stack, princípio XI) e `specs/README.md` (tabela "fora de escopo")
- **Origem:** pedido do mantenedor (2026-10-13): aplicar configurações por uma interface gráfica — modelos e MCPs de
  cada Assistant, dashboard de uso e custo, Langfuse e ajustes de login —, com a opção de instalar a plataforma sem ela

## Contexto

Toda configuração da plataforma vem hoje de arquivos da instalação (`assistants.yaml`, `mcp.yaml`, `packs.yaml`,
`.env`) ou da superfície privada da API, chamada com chave de API. A única interface é o Open WebUI, que é chat e só
apresentação (princípio XI). A constituição registra "Interface: Open WebUI (via compat OpenAI)" na tabela de stack, e
o `specs/README.md` põe "lógica de agente na interface" fora de escopo.

O mantenedor quer ajustar a plataforma sem novo deploy, por uma tela, e quer que essa tela seja opcional: a instalação
padrão continua sem ela.

## Decisão

1. A plataforma ganha uma **console de administração**: uma SPA (React + TypeScript, Vite) em `ai-core/console/`,
   especificada pela spec **013**. Ela é **só apresentação**: toda regra (validação, autorização, precedência entre
   instalação e console) vive no core, atrás da API HTTP da 008.
2. A console fala com a plataforma **só pela API HTTP** — a superfície de administração (ADR-031) — e entra pelo
   protocolo OIDC do provedor de identidade da plataforma (ADR-030), como cliente público com PKCE. Ela não importa
   código do core nem lê o banco.
3. A console é **opcional na instalação**: imagem própria (estágio do `agentic-deploy/Dockerfile`) servida por um
   servidor estático que repassa à plataforma os prefixos do core, sem reescrever caminhos. Sem ela, nada muda no core:
   a mesma API de administração atende automação com chave de API.
4. A console é para o **grupo de administração**. Usuário comum não tem tela nela; a superfície de usuário (Assistants
   e MCPs próprios) continua só pela API pública.
5. A console não fica em `ai-core/packages/`: o workspace do uv casa `packages/*` e exige `pyproject.toml` em cada
   membro. Ela tem o próprio toolchain (Node, `.nvmrc`), fora do uv.
6. Emenda da constituição (MINOR, 1.3.0, por `/speckit-constitution`): a linha "Interface" da tabela de stack passa a
   "Open WebUI (chat, via compat OpenAI) · console de administração própria (SPA, opcional)"; entra a linha
   "Identidade" (ADR-030); o princípio XI passa a dizer que nenhuma interface — Open WebUI ou console — carrega lógica
   de agente nem regra de negócio.

## Alternativas rejeitadas

*Páginas renderizadas no servidor, num pacote Python do workspace.* Sem toolchain Node, mas gráficos e formulários
ricos dão mais trabalho, e as páginas ficariam dentro do processo do core, com a tentação de importar serviços em vez de passar
pela API. A escolha pela SPA foi do mantenedor.

*Usar a área de administração do Open WebUI.* Ela administra o Open WebUI, não a plataforma: não conhece Assistants,
sobreposições, MCP por Assistant nem uso por modelo, e prenderia a configuração a um produto que hoje é só apresentação.

*Editar `assistants.yaml` e `mcp.yaml` por uma tela que escreve os arquivos.* Os arquivos são do operador, montados
somente leitura e versionados fora do processo; escrever neles mistura deploy e runtime sem rastro de quem mudou o quê.

## Consequências

- A spec 013 é um módulo sem seam: consome a API da 008 e o protocolo da 012. Reescrevê-la não toca nenhuma outra spec
  enquanto a API de administração (contrato `admin-api.md` da 008) se mantiver.
- O repositório passa a ter um toolchain Node (`ai-core/console/`), com CI própria.
- O `specs/README.md` ajusta a linha "Lógica de agente na interface" para valer para as duas interfaces.
- Toda tela da console tem um equivalente na API de administração; automação e testes não dependem da console.
