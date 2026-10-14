# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

SPA React + TypeScript (Vite) em `ai-core/console/`, servida por um contêiner estático opcional na mesma origem da
plataforma (spec 013, ADR-029). A página de login e "Minha conta" são HTML renderizado pelo módulo de identidade do
core, sem script (spec 012). Escolha do mantenedor em 2026-10-13.

## Users

- **Administradores da instalação** (grupo de administração): pessoas técnicas de uma instalação pequena — um operador
  e poucos admins — que ajustam a plataforma sem novo deploy. Usam a console no computador, em sessões curtas e
  pontuais: trocar o modelo de um Assistant, ligar um servidor MCP, cadastrar uma pessoa, conferir quanto custou o mês.
- **Pessoas que usam o chat** (Open WebUI): veem só a página de login da plataforma e "Minha conta" (trocar a senha).
  Entram pelo celular e pelo computador.

## Product Purpose

Plataforma de agentes de IA modular: um núcleo genérico (`ai-core`) que orquestra Assistants — configurações que
amarram flow, packs de capacidade, servidores MCP, modelos por papel, limites e ACL — e packs de domínio que trazem o
conhecimento. A console de administração existe para que o operador aplique, sem deploy, o que o deploy permitir:
modelos e MCPs de cada Assistant, contas e grupos, login Google, Langfuse, e acompanhe uso e custo por modelo e por
dia. Sucesso: um admin troca o modelo de um Assistant e a próxima conversa já usa o novo, em menos de um minuto, sem
tocar em arquivo.

## Positioning

O deploy é o teto, a console escolhe dentro dele: cada Assistant declara no YAML o que pode ser sobreposto
(`overrides`), a allowlist de modelos continua do operador, e o deploy sempre vence uma sobreposição antiga. A console
não tem regra própria — tudo o que ela faz existe na API de administração.

## Operating Context

- A instalação roda em hardware modesto (2 OCPU, 12 GB, ARM64) por Docker Compose: core, Postgres, Qdrant, Open WebUI
  opcional, console opcional.
- Configuração do operador em arquivos versionados (`assistants.yaml`, `packs.yaml`, `mcp.yaml`, `identity.yaml`, `.env`).
- Modelos locais (Ollama) e remotos (OpenAI, OpenRouter), escolhidos por papel: `generation`, `controller`, `rerank`.
- Observabilidade: trace por requisição e, opcional, Langfuse.

## Capabilities and Constraints

- Console só para o grupo de administração; quem não pertence vê "sua conta não tem acesso".
- Seções travadas: o que o YAML não declara em `overrides` aparece somente leitura, com "Só muda por novo deploy".
- Campos definidos pela instalação aparecem somente leitura, com "Definido na instalação"; segredos são só de escrita.
- Uso e custo: requisições, chamadas, tokens de entrada e saída e custo em USD por dia, modelo ou Assistant; preços
  mantidos à mão, com data de início; "sem preço" quando faltar; origem produção ou avaliação.
- Idioma: português do Brasil; números e datas no formato brasileiro; dinheiro em USD.
- Tema claro e escuro, seguindo o sistema, com troca manual na console; a página de login segue o sistema.
- O núcleo é agnóstico de domínio: nenhuma marca, termo ou imagem de domínio no core, na console ou na página de login.
- Nome exibido: definido pela instalação (com logotipo opcional); sem ele, um nome neutro da plataforma (provisório:
  "Agentic").

## Brand Commitments

Nenhuma identidade visual existente. A marca visível é a da instalação (nome e logotipo opcionais), nunca a de um
domínio embutido no core.

Direção escolhida pelo mantenedor em 2026-10-13: **o padrão da categoria**, executado no nível de acabamento de
**Vercel e Linear** (os produtos ao lado dos quais a console deve parecer à vontade). Convenção é o compromisso:
sem ironia, sem enfeite de outro mundo. O mantenedor também disse o que faria a console parecer errada: painel SaaS
genérico (cartões de métrica com ícone, gradiente) e frieza de terminal.

## Evidence on Hand

Nenhum dado real de uso, preço ou contas ainda; telas de exemplo usam dados fictícios neutros. Não inventar clientes,
depoimentos nem números de desempenho.

## Product Principles

1. O deploy manda; a console escolhe dentro do que ele permite e mostra sempre por quê algo está travado.
2. Nenhuma regra na tela: o motivo de toda recusa vem da API e aparece junto ao campo.
3. Segredo nunca volta: a tela diz se existe e de onde vem, nunca o valor.
4. Tarefas curtas e pontuais: cada tela resolve um trabalho sem exigir que o admin lembre de outra.
5. Neutra de domínio: a mesma console serve qualquer pack e qualquer organização.

## Accessibility & Inclusion

WCAG 2.2 AA na console e na página de login, nos dois temas; operável só pelo teclado. Login e "Minha conta" desenhados
primeiro para tela de celular.
