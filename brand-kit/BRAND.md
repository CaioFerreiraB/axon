# Axon — Brand Kit v0.1

> **Design. Connect. Build.**
>
> Um ambiente open source para projetar, conectar e executar sistemas agênticos.

Este kit orienta a aplicação visual da marca Axon no projeto de software. É uma direção inicial de marca para implementação, não um manual jurídico ou uma identidade final registrada.

## 1. Essência da marca

**O que é:** uma plataforma modular para projetar, configurar e executar sistemas agênticos, conectando agentes, modelos, ferramentas, fluxos e capacidades.

**Ideia central:** transformar uma ideia em um sistema funcional.

**Personalidade**
- Técnica, sem ser fria.
- Acessível, sem ser infantil.
- Modular e prática.
- Clara e orientada à construção.
- Open source e amigável para desenvolvedores.

**A marca deve transmitir**
- Projeto e construção.
- Conexão entre componentes.
- Experimentação e iteração.
- Execução confiável.
- Controle e clareza.

**Evitar**
- Estética sci-fi genérica, robôs, cérebros e cabeças de IA.
- Gradientes em excesso, brilho neon e efeitos 3D decorativos.
- Aparência corporativa distante ou dashboards SaaS genéricos.
- Usar o símbolo como decoração sem relação com conexões ou construção.
- Tratar Axon como apenas um chatbot.

## 2. Nome e linguagem

**Nome de marca:** Axon  
**Grafia preferida:** `Axon` em textos corridos; `axon` no wordmark e em interfaces, se combinar com o sistema tipográfico.  
**Tagline principal:** `Design. Connect. Build.`

**Descrição curta em português:**  
Axon é um ambiente open source para projetar, conectar e executar sistemas agênticos.

**Descrição curta em inglês:**  
Axon is an open-source workspace to design, connect, and run agentic systems.

**Mensagens de apoio**
- From idea to execution.
- Build agentic systems, piece by piece.
- Design workflows. Connect capabilities. Run agents.

Use a tagline como assinatura institucional, não como texto obrigatório em todas as telas. Não afirmar funcionalidades que ainda não existam no produto.

## 3. Conceito do símbolo

Direção sugerida: um símbolo geométrico compacto inspirado em um axônio e suas ramificações — três terminais conectados por uma estrutura central. A metáfora é conexão e transmissão entre partes de um sistema.

**Requisitos do símbolo**
- Legível em 16×16 px e  favicon.
- Funcionar em uma cor, sem gradiente.
- Não depender de detalhes finos.
- Ser reconhecível em fundos claros e escuros.
- Evitar copiar formas neurais genéricas ou marcas existentes.
- Não desenhar uma letra “A” literal se isso prejudicar a simplicidade.

**Lockups**
1. Símbolo + `axon` horizontal: uso principal em navegação e cabeçalho.
2. Símbolo isolado: favicon, avatar, app icon.
3. Monocromático: documentação, impressão e contextos de alto contraste.

O conceito visual gerado durante a exploração é apenas referência de direção. Recrie o símbolo como SVG vetorial próprio antes de usar em produção; não reproduza detalhes imperfeitos de mockups gerados por IA.

## 4. Paleta de cores

Paleta proposta para começar. Os tokens devem ser centralizados e aplicados de forma consistente.

| Token | Hex | Uso |
|---|---|---|
| `axon-night` | `#0B0F19` | Fundo escuro principal, superfícies profundas |
| `axon-blue` | `#3882F6` | Ação primária, foco, links e destaque |
| `axon-violet` | `#8B5CF6` | Destaques secundários, estado criativo ou agentes |
| `axon-ink` | `#111827` | Texto forte em fundo claro |
| `axon-slate` | `#64748B` | Texto secundário e metadados |
| `axon-line` | `#E5E7EB` | Bordas e divisores em tema claro |
| `axon-mist` | `#F8FAFC` | Fundo claro |
| `axon-white` | `#FFFFFF` | Superfícies e texto em fundos escuros |

### Regras de uso
- Azul é a cor de ação principal. Reserve-o para botões primários, links, foco e seleção.
- Violeta é complementar; use com moderação para diferenciar agentes, experimentação ou elementos secundários.
- Não use azul e violeta simultaneamente em todos os componentes.
- No tema escuro, use `axon-night` como base e superfícies ligeiramente mais claras para cartões.
- No tema claro, use `axon-mist` ou branco como base, texto `axon-ink` e bordas `axon-line`.
- Não use cor apenas para comunicar estado. Combine com texto, ícone ou outro sinal.
- Verifique contraste WCAG antes de publicar; as cores de marca não garantem contraste adequado em todas as combinações.

## 5. Tipografia

**Direção:** sans-serif moderna, neutra, legível e adequada a interfaces técnicas.

**Sugestão principal:** Inter.  
**Alternativa:** Geist Sans, se já fizer parte do stack visual do projeto.  
**Código e identificadores:** uma fonte monoespaçada já usada pelo projeto; preferir Geist Mono ou JetBrains Mono se não houver padrão existente.

### Hierarquia
- Títulos: peso 600–700, espaçamento compacto.
- Texto de interface: 400–500.
- Labels e metadados: 400–500, sem excesso de letras maiúsculas.
- Código: monoespaçada, com bom contraste e line-height confortável.

Não carregue fontes externas desnecessárias se o projeto já possuir uma solução de tipografia consistente.

## 6. Direção visual e interface

**Princípios**
1. **Workspace first:** a área de construção deve ser o centro visual do produto.
2. **Clareza antes da decoração:** hierarquia, estados e próximos passos devem ser óbvios.
3. **Modularidade visível:** agentes, ferramentas, fluxos e capacidades devem parecer peças combináveis.
4. **Feedback de execução:** estados de rascunho, execução, sucesso e erro precisam ser distinguíveis.
5. **Densidade controlada:** interfaces técnicas podem ser densas, mas precisam de agrupamento e respiro.

### Elementos gráficos
- Grades discretas como apoio para canvas/diagramas.
- Linhas de conexão finas e nós claros para representar fluxos.
- Cantos moderadamente arredondados; evitar arredondar tudo como uma app de consumo.
- Sombras discretas, somente quando ajudam a hierarquia.
- Animações curtas e funcionais para transições, execução ou conexão de nós.
- Gradientes opcionais apenas em material de marketing ou pequenos acentos; não como base da interface.

### Ícones
- Use uma única família de ícones outline consistente (por exemplo, Lucide, se já estiver no projeto).
- Mesmo tamanho, espessura e alinhamento dentro de cada contexto.
- Não misture emoji com ícones de interface.
- Ícones devem ter rótulos quando seu significado não for óbvio.

## 7. Componentes e estados

### Botão primário
- Fundo `axon-blue`, texto branco.
- Usar para a ação principal da tela (ex.: Executar, Criar agente, Salvar).
- Estado hover/pressed deve ser discreto; não usar brilho neon.

### Botão secundário
- Fundo transparente ou superfície neutra, borda sutil.
- Deve competir menos visualmente com a ação primária.

### Campos
- Bordas neutras e foco azul claramente visível.
- Labels persistentes; placeholder não substitui label.
- Erros com mensagem textual e ícone, não apenas cor.

### Nós de fluxo
- Cada tipo de nó pode ter um acento discreto, mas manter a mesma estrutura visual.
- Mostrar nome, tipo e estado de forma consistente.
- Seleção com contorno azul; erro com indicação textual e visual.
- Linhas de conexão devem ser legíveis sem dominar o canvas.

### Status recomendados
- Draft: neutro.
- Running: azul.
- Success: verde semântico do design system existente.
- Warning: âmbar semântico.
- Error: vermelho semântico.
Não redefinir cores semânticas se o projeto já tiver tokens acessíveis.

## 8. Voz e tom

**Tom:** claro, direto, colaborativo e tecnicamente competente.

Preferir:
- “Crie um agente”
- “Conecte uma ferramenta”
- “Configure o fluxo”
- “Teste a execução”
- “Ver logs”

Evitar:
- “Revolucione sua inteligência”
- “Desbloqueie o poder infinito da IA”
- Jargão de marketing sem explicação.
- Promessas de autonomia que o produto não garante.

A interface deve orientar sem infantilizar. Mensagens de erro devem explicar o problema e, quando possível, sugerir como resolver.

## 9. Exemplos de aplicação

**Página inicial**
- Headline: “Da ideia à execução.”
- Subheadline: “Projete, conecte e execute sistemas agênticos em um ambiente modular e open source.”
- CTA principal: “Começar a construir”
- CTA secundário: “Explorar documentação”

**Tela de projeto**
- Nome do projeto e estado (Rascunho/Ativo).
- Canvas de fluxo como foco.
- Painel de propriedades contextual.
- Ação primária clara: Executar ou Publicar, conforme o estado real.

**Documentação**
- Fundo claro, tipografia legível, snippets de código com alto contraste.
- Usar a marca de forma discreta; priorizar conteúdo e navegação.

## 10. Diretrizes para implementação no repositório

1. Primeiro inspecione o stack, os componentes existentes e o design system. Não reescreva a aplicação nem troque bibliotecas sem necessidade.
2. Centralize as cores em tokens CSS ou no mecanismo de tema já utilizado pelo projeto.
3. Crie o símbolo em SVG próprio e versões claro/escuro/monocromática.
4. Atualize nome, favicon, títulos, metadados e textos de marca de maneira consistente.
5. Preserve acessibilidade, responsividade, estados existentes e comportamento funcional.
6. Não substitua telas funcionais por mockups estáticos.
7. Não introduza novas dependências se as existentes forem suficientes.
8. Use `Axon` como nome de produto, mas não altere automaticamente nomes técnicos de pacotes, diretórios, imports ou identificadores internos sem verificar impactos.
9. Se houver dúvidas sobre a estrutura atual, faça uma alteração incremental e liste as decisões em vez de inventar componentes inexistentes.
10. Verifique contraste, navegação por teclado, estados de foco, loading, vazio, erro e sucesso.

## 11. Critérios de aceite

- Marca coerente em aplicação, login, navegação, documentação e favicon.
- Tema claro e escuro consistentes, caso ambos já sejam suportados.
- Tokens de cor centralizados.
- Símbolo vetorial legível em tamanho pequeno e em monocromático.
- Componentes com contraste e foco acessíveis.
- Nenhuma regressão funcional introduzida pela mudança visual.
- A identidade parece uma ferramenta para construir sistemas, não um chatbot genérico.

## 12. Estado da marca

Este kit é uma proposta inicial. Antes de lançamento público, verificar disponibilidade do nome Axon, marcas registradas, domínios, organizações/repositórios e pacotes de software. Não presumir exclusividade do nome.
