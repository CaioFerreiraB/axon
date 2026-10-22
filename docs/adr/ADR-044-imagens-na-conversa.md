# ADR-044 — Imagens na conversa: as que as tools devolvem e as que o usuário envia

- **Status:** Aceita · 2026-10-22
- **Specs afetadas:** [001-core-contracts](../../specs/001-core-contracts/spec.md) (`Attachment`, anexos no `ToolResult` e na
  `Message`), [002-core-pack-runtime](../../specs/002-core-pack-runtime/spec.md) (Turn View com anexos),
  [007-core-mcp-integration](../../specs/007-core-mcp-integration/spec.md) (partes de imagem preservadas),
  [004-core-capability-gateway](../../specs/004-core-capability-gateway/spec.md) (anexo fora da cerca),
  [005-core-execution-engine](../../specs/005-core-execution-engine/spec.md) (evento de anexo, decisão de ver a
  imagem nos três flows, `controller` opcional no `chat`), [006-core-llm-providers](../../specs/006-core-llm-providers/spec.md)
  (mensagem com imagem, `vision` na política de modelos),
  [003-core-assistants-access](../../specs/003-core-assistants-access/spec.md) (`vision` no papel, `controller` opcional no
  `chat`), [008-core-http-api](../../specs/008-core-http-api/spec.md) (imagem na entrada, na resposta, no histórico
  recebido e na conversa guardada), [009-core-observability-evaluation](../../specs/009-core-observability-evaluation/spec.md)
  (trace sem bytes, decisão `view_image`), [011-core-bootstrap](../../specs/011-core-bootstrap/spec.md) (limites,
  provider simulado com imagem), [013-core-admin-console](../../specs/013-core-admin-console/spec.md) (`vision` na
  sobreposição de modelos)
- **Origem:** teste do MCP do mango pelo Open WebUI (2026-10-22): a tool `grafico` devolve PNG e tabela; o Axon
  entregou só a tabela, e o modelo disse ao usuário que não tinha acesso à imagem. O mesmo MCP, no Claude Code, mostra
  o gráfico. Na mesma conversa, o mantenedor pediu que o usuário também possa enviar imagens (anexo do Open WebUI ou
  qualquer cliente da API)

## Contexto

O resultado de uma tool é texto até o fim. A 007 transforma toda parte não textual de um resultado MCP na marca
`[conteúdo image omitido]` (research R9), o `ToolResult` da 001 carrega um `content` serializável e a 005 só conhece
`FencedToolResult.text`. Não há caminho para bytes: nem até o usuário, nem até o modelo.

Na entrada, a 008 recusa com 400 toda mensagem cujo `content` não é texto (`domain/chat_request.py`). O formato da
OpenAI manda imagem do usuário como partes (`[{"type": "text", …}, {"type": "image_url", …}]`), e é assim que o Open
WebUI manda um anexo: hoje, anexar imagem no chat dá erro. A 008 também não limita o tamanho do corpo da requisição.

O mantenedor fixou cinco regras:

- **A imagem de uma tool sempre chega ao usuário.** É o produto da tool, e o servidor MCP a gerou para ser mostrada.
- **O modelo só vê uma imagem antiga quando a pergunta é sobre ela, e só se ele enxerga imagem.** Mandar todo PNG
  custa tokens, e servidores sérios (o mango incluído) já repetem em texto os números do gráfico. Vale para os três
  flows.
- **O usuário pode enviar imagem**, pela API ou pelo anexo do Open WebUI.
- **A imagem é só do usuário**, como as mensagens: nada de link público.
- **A imagem vive o mesmo tempo que a conversa.**

Uma conversa vive hoje em um de dois lugares:

- **No cliente** (`x-axon-store: false`). É o caso do Open WebUI da instalação: o histórico fica no banco dele, e o
  Axon não guarda nada nem fica sabendo quando a conversa é apagada. O cliente reenvia o histórico inteiro a cada
  turno.
- **No Axon** (schema `http`, o padrão sem o cabeçalho). As mensagens apontam para a conversa com `ON DELETE CASCADE`,
  e a conversa expira por inatividade (`AXON_CONVERSATION_RETENTION_DAYS`).

O Open WebUI v0.12 renderiza imagem em markdown na mensagem do assistente. Não renderiza MCP Apps nem figura Plotly em
JSON; HTML vai para o painel de Artifacts, fora da mensagem.

## Decisão

### O tipo

1. **Anexo é um tipo dos contratos** (001, aditivo, versão pela política do ADR-014):
   `Attachment(id, mime, data: bytes, alt: str | None)`.
   - `ToolResult` ganha `attachments: tuple[Attachment, ...] = ()`, e `Message` ganha `attachments` opcional
     (`NotRequired`). `content` continua texto. Os packs passam a ver os anexos das mensagens pela Turn View (002).
   - Só entram `image/png`, `image/jpeg`, `image/webp` e `image/gif`. SVG fica fora: é documento ativo e viraria
     vetor de XSS no cliente.
   - **O `id` vem do conteúdo**: `img-` seguido dos 12 primeiros hexadecimais do SHA-256 dos bytes. É o que permite
     reconhecer a mesma imagem quando ela volta no histórico do cliente, onde o markdown não carrega id nenhum, e
     junta repetições da mesma imagem.
   - **O `alt` é dado não confiável** (vem do servidor MCP). Antes de sair em qualquer lugar, o motor o limpa: sem
     quebras de linha nem `[`, `]`, `(`, `)`, com no máximo 120 caracteres.

### Imagem devolvida por tool

2. **A 007 preserva a parte de imagem** (`RemotePart` com `mime` e `data`). Uma imagem acima do teto por anexo
   (`AXON_TOOL_MAX_ATTACHMENT_BYTES`, proposto 2 MiB) ou de tipo fora da lista vira a marca de omissão de hoje, com o
   motivo. O teto de texto do gateway (`AXON_TOOL_MAX_RESPONSE_BYTES`) não conta os anexos.
3. **A 004 tira o anexo da cerca.** Dentro do texto cercado, no lugar de cada imagem, vai a marca
   `[imagem <id> mostrada ao usuário: <alt>]`. O modelo sabe que a imagem existe e que o usuário a viu, sem receber
   os bytes. `FencedToolResult` passa a ter `attachments`. A auditoria de escrita e o evento `tool_call` registram
   quantidade, tipo e tamanho, nunca bytes.
4. **A 005 publica o anexo e não o manda ao modelo no turno em que ele nasce.**
   - Evento novo `AttachmentEvent(attachment, tool)` no `ExecutionEvent`, emitido depois do `StepFinished` da tool, e
     `FinalEvent.attachments` na ordem em que as tools os produziram, sem repetição de `id`.
   - O controller e a geração do turno veem só a marca do item 3.
   - Um texto de sistema fixo, junto da `FENCE_INSTRUCTION`, diz à geração que o usuário vê as imagens marcadas junto
     da resposta: não diga que não consegue mostrá-las.
   - Só o `ToolResult` carrega imagem. Os trechos dos retrievers (`Chunk`) não mudam.

### Imagem enviada pelo usuário

5. **A API aceita imagem na mensagem do usuário** (008). `content` pode vir em partes no formato da OpenAI: `text` e
   `image_url` com **data URI** dos tipos do item 1. A mensagem precisa ter texto ou imagem; só imagem vale como
   pergunta.
   - **A última mensagem do usuário é validada antes de qualquer custo**, com 400 e `param`:
     - URL que não é data URI (`http(s)://…`): o Axon buscaria um endereço escolhido pelo cliente (SSRF);
     - tipo fora da lista;
     - imagem acima de `AXON_MAX_INPUT_IMAGE_BYTES` (proposto 5 MiB);
     - mais de `AXON_MAX_INPUT_IMAGES` imagens nela (proposto 4);
     - papel `generation` sem `vision`: 400 `vision_unsupported`, nomeando o Assistant, antes de qualquer chamada de
       modelo. O usuário fica sabendo que mandou a imagem ao lugar errado, em vez de receber uma resposta que a ignora.
   - **Mensagens anteriores não são validadas assim.** O cliente reenvia o histórico, e uma imagem antiga não pode
     travar a conversa (o usuário pode ter trocado de Assistant no meio dela). Toda imagem de mensagem anterior do
     usuário vira a marca `[imagem <id> enviada pelo usuário]`, e os bytes são descartados na leitura.
   - **A imagem da última mensagem do usuário é a pergunta**: vai à geração sem decisão nenhuma. Ao controller só vai
     se o papel `controller` também declara `vision`; senão ele vê a marca.
   - **Tools não recebem a imagem do usuário** nesta decisão. Mandá-la como argumento a um MCP (OCR de um recibo, por
     exemplo) exige argumento binário no gateway da 004 e fica para outro ADR.
6. **O corpo da requisição ganha teto** (008): `AXON_MAX_REQUEST_BYTES` (proposto 32 MiB), com 413 acima dele, lido
   antes de decodificar o JSON. Com a conversa no cliente, as imagens da conversa inteira voltam a cada turno.

### Imagem no turno seguinte

7. **Só a última mensagem do assistente tem imagens candidatas.** A 008 troca toda imagem das mensagens do assistente
   pela marca `[imagem <id> mostrada ao usuário]`, sem `alt` (o histórico tem papel `assistant`, e o `alt` vem de
   fora). Guarda os bytes só da última mensagem do assistente, e só dos tipos do item 1; os outros são descartados na
   leitura. Valem os dois formatos em que um cliente devolve uma mensagem do assistente: o markdown
   `![…](data:…)` do item 9 e as partes `image_url`.
8. **A geração só recebe uma imagem candidata se a pergunta for sobre ela — nos três flows.**

   | Situação | Decisão |
   |---|---|
   | Não há imagem candidata, ou o papel `generation` não declara `vision: true` | Nenhuma: nenhum byte vai ao modelo, nenhuma chamada a mais |
   | `agentic`, e o `rag_first` que escalou para o loop | O formato da ação do controller ganha o ramo `{"action": "view_image", "id": "<id>"}`, e o sistema do controller lista só os **ids** candidatos. Escolhê-lo marca a imagem para a geração e conta como iteração; a imagem não volta ao controller. Pedir a mesma imagem de novo segue a regra da ação repetida (005 R50). Não é tool e não passa pelo gateway da 004 |
   | `chat`, e o `rag_first` no caminho coberto, com o papel `controller` declarado | Uma etapa nova, `image_gate`, antes da geração (no `rag_first`, depois do portão): uma chamada ao `controller` com saída estruturada `{"view": ["<id>", …]}`, cujos ids precisam estar entre os candidatos. Falha da chamada segue sem imagem, com `notice` (a regra do FR-006a) |
   | `chat` ou `rag_first` sem `controller` | Sem quem decida, as imagens candidatas vão à geração |

   - O `controller` passa a ser papel **opcional** também no `chat` (`OPTIONAL_ROLES`, ADR-019), e a 003 aceita
     Assistant `chat` que o declare.
   - A decisão é o evento `controller_decision` da 009 com uma ação nova, `view_image` (aditivo, ADR-017), e os ids no
     lugar do nome da tool. A etapa `image_gate` publica progresso e desfecho como as outras (ADR-028).
   - A imagem escolhida entra na **última mensagem do usuário** enviada à geração, como parte `image_url`, junto da
     marca que diz de onde ela veio.

### Onde a imagem fica e como chega ao cliente

9. **A imagem mora onde a conversa mora, e só o dono a lê.**
   - **Conversa no cliente** (`x-axon-store: false`): a resposta leva cada imagem das tools dentro da mensagem do
     assistente, como `![<alt>](data:<mime>;base64,…)`, em parágrafo próprio, **depois** do texto. Em streaming, os
     anexos ficam retidos e saem depois do último token. A imagem passa a fazer parte da conversa do usuário no
     cliente: só ele a vê, e ela é apagada quando a conversa é apagada. O Axon não guarda nada.
   - **Conversa no Axon** (schema `http`): as imagens das tools e as do usuário vão para `http.attachments`, presas à
     mensagem por `ON DELETE CASCADE`. A mensagem guarda o texto com a marca, não o data URI.
     - A imagem expira e é apagada junto com a conversa, pela mesma tarefa de expiração, sem retenção própria.
     - A resposta do turno também leva o data URI, para o cliente mostrar a imagem na hora.
     - A leitura das mensagens de uma conversa traz, em cada mensagem, os metadados dos anexos (`id`, `mime`, tamanho).
       Os bytes saem por `GET /v1/conversations/{conversation_id}/attachments/{attachment_id}`, com a mesma
       autenticação e a mesma regra das mensagens: outro usuário recebe 404, não 403.
     - No turno seguinte, a 008 lê do banco as imagens da última mensagem do assistente.
   - Nos dois modos, a extensão `x_axon` traz `id`, `mime` e tamanho de cada anexo da resposta.

### Modelo, trace e configuração

10. **A 006 aceita mensagem com imagem.** `ChatMessage.content` passa a admitir partes (`text` e `image_url` com data
    URI), no formato compatível com a OpenAI que os três providers falam. `vision: true` é um campo do papel na
    política de modelos da 006 (ADR-016), escrito no Assistant da 003 e sobreponível pela console (ADR-032, seção
    `models`). O cliente instrumentado recusa imagem a papel sem `vision`, como a guarda do `response_format` do
    controller: é erro de programação, e a 005 nunca a envia.
11. **Trace e uso sem bytes** (009). `model_exchange` (captura opcional) registra a marca no lugar da imagem.
12. **Configuração** (011): `AXON_TOOL_MAX_ATTACHMENT_BYTES`, `AXON_MAX_INPUT_IMAGE_BYTES`, `AXON_MAX_INPUT_IMAGES` e
    `AXON_MAX_REQUEST_BYTES`. O provider simulado do perfil `test` aceita partes de imagem e as registra, para as
    suítes provarem o que chegou ao modelo.

## Onde as imagens ficam

| Lugar | O que fica | Quem lê | Por quanto tempo |
|---|---|---|---|
| Memória do processo | os bytes, da tool ou da requisição até a resposta sair | o motor | uma requisição |
| Conversa no cliente (Open WebUI) | o data URI na mensagem do assistente; a imagem do usuário, como o cliente a guardou | o dono da conversa, no cliente | o mesmo da conversa: some quando ela é apagada |
| Conversa no Axon (`http.attachments`) | os bytes, presos à mensagem do assistente ou do usuário | o dono da conversa, pela API autenticada | o mesmo da conversa: cascata e expiração dela |
| Trace, uso, auditoria, Langfuse | só id, tipo e tamanho | administração | a retenção de cada um |

## Alternativas rejeitadas

- **Link assinado público (`/v1/attachments/<token>`) com retenção própria.** Quem tivesse o link veria a imagem, e
  a retenção da imagem não acompanharia a da conversa: rejeitado pelo mantenedor.
- **Imagem servida pelo Axon e autenticada pelo cookie de sessão da 012**, para o navegador do Open WebUI buscar por
  URL. O cookie é `__Host-` (só o host da identidade), a sessão expira antes da conversa e a imagem quebraria nas
  conversas antigas. E, com a conversa no cliente, o Axon não fica sabendo quando ela é apagada: a imagem
  sobreviveria à conversa.
- **Guardar no Axon toda imagem, mesmo com a conversa no cliente, por um prazo fixo.** Os dados ficariam mais tempo
  que a conversa, ou menos, e não haveria como o usuário apagá-los.
- **Subir a imagem para a API de arquivos do Open WebUI.** Acopla o core a um cliente. O data URI na mensagem
  funciona em qualquer cliente compatível com a OpenAI que renderize markdown.
- **Id sequencial (`img-1`) atribuído pelo motor.** Não sobrevive à volta pelo histórico do cliente, que só guarda o
  markdown.
- **Mandar toda imagem ao modelo, sempre.** Custa tokens em cada iteração do controller, exige modelo com visão em
  todo Assistant com MCP e não acrescenta nada quando a tool já repete os números em texto.
- **Mandar a imagem da última mensagem do assistente sempre que o modelo tem visão.** Paga a imagem em toda pergunta
  de seguimento, inclusive nas que não tratam dela, como "e em setembro?". Fica só como regra de quem não declara
  `controller`.
- **Regra por palavras na pergunta ("gráfico", "barra", "imagem").** Frágil em português coloquial e cega para
  "o que é aquele pico?".
- **`view_image` como tool MCP ou de pack, pelo gateway.** A imagem não é capacidade de nenhum servidor: veio do
  histórico, e o gateway não a conhece.
- **Aceitar URL de imagem do usuário e buscá-la.** O Axon faria requisição a endereço escolhido pelo cliente (SSRF),
  com prazo, tamanho e redirecionamento para controlar. O cliente que tem a imagem a manda em data URI.
- **Imagem para Assistant sem visão segue com só a marca.** O modelo responderia sem ver o que o usuário mandou, e o
  usuário não saberia por quê. O 400 diz o que fazer: escolher outro Assistant.
- **Validar as imagens do histórico inteiro.** Uma imagem antiga, mandada quando o Assistant era outro, travaria a
  conversa para sempre.
- **MCP Apps (gráfico interativo).** O Open WebUI não os renderiza; fica para quando houver cliente que os renderize.
- **Plotly em bloco HTML (Artifact do Open WebUI).** Depende de o servidor MCP devolver HTML, abre no painel lateral e
  não serve a outros clientes. Fica possível depois, como outro tipo de anexo, sem mudar esta decisão.

## Consequências

- Anexar imagem no Open WebUI deixa de dar erro em Assistant com visão e passa a dar um erro claro nos outros.
- O contrato 001 muda de forma aditiva. Packs atuais não mudam; um pack pode passar a devolver imagem pelas próprias
  tools e passa a ver os anexos das mensagens pela Turn View.
- Com a conversa no cliente, as imagens da conversa inteira vão e voltam a cada turno. O teto por imagem e o teto do
  corpo limitam o tráfego; a 008 descarta os bytes que não são candidatos logo na leitura.
- A 008 ganha uma migração no schema `http` (`http.attachments`) e uma rota de leitura. A expiração das conversas não
  muda: a cascata leva as imagens.
- O `chat` e o `rag_first` ganham uma etapa (`image_gate`) que só roda quando há imagem candidata e modelo com visão;
  sem isso, os dois seguem idênticos ao que são hoje.
- O teto de contexto da 005 (FR-011) passa a estimar cada imagem enviada ao modelo por um custo fixo, a calibrar com o
  provider.
- A console (013) ganha o campo `vision` por papel na sobreposição de modelos.
- **A verificar antes de tudo, na passada da 008:**
  - que o Open WebUI v0.12 renderiza `![](data:image/png;base64,…)` na mensagem do assistente e o devolve intacto no
    histórico;
  - o formato exato em que ele manda o anexo do usuário (partes `image_url` com data URI) e o reenvia nos turnos
    seguintes;
  - o que ele mostra quando recebe o 400 `vision_unsupported` e o 413.

  Se ele sanitizar data URI, a entrega para conversas no cliente precisa de outro caminho, com ADR que substitua os
  itens 7 e 9.
