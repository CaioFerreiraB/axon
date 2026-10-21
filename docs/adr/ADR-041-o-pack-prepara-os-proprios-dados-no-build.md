# ADR-041 — O pack prepara os próprios dados no build

- **Status:** Aceita · 2026-10-21
- **Specs afetadas:** [001-core-contracts](../../specs/001-core-contracts/spec.md) (hook opcional `prepare` e
  `PackContext.data_dir`; contratos `0.2.1`), [002-core-pack-runtime](../../specs/002-core-pack-runtime/spec.md)
  (`axon packs prepare`; o `data_dir` de cada pack na carga; a instalação, com o ADR-042),
  [011-core-bootstrap](../../specs/011-core-bootstrap/spec.md) (`AXON_PACKS_DATA_DIR`; registro do subcomando),
  [101-scouting-pack](../../specs/101-scouting-pack/spec.md) e [102-scouting-corpus-ingestion](../../specs/102-scouting-corpus-ingestion/spec.md)
  (o scouting baixa o modelo denso no `prepare`)
- **Origem:** conversa com o mantenedor (2026-10-21) sobre o deploy: o `axon-deploy` passa a ser público e de referência
  (ADR-042) e não pode conhecer pack nenhum — hoje o `Dockerfile` dele roda `axon-scouting-corpus model fetch` e copia
  `/opt/axon-scouting`

## Contexto

Um pack pode precisar, em runtime, de arquivos que não cabem no pacote Python: o scouting usa o `multilingual-e5-small`
em ONNX (~470 MB), fixado por revisão e sha256, que nunca é baixado em runtime (102). Hoje quem baixa é a instalação, num
passo do `Dockerfile` que só existe por causa do scouting, e o caminho do modelo é repetido no `packs.yaml`
(`embedding_dir`) e no ambiente da CLI (`AXON_SCOUTING_EMBEDDING_DIR`).

Instalar um pack é uma linha no build-arg `PACKS` (ADR-009). Cada pack com dados próprios acrescentaria passos à
instalação — conhecimento do pack fora dele. O pip não tem gancho de pós-instalação para wheels, e baixar na primeira
execução violaria a FR-014 da 002 (nada se instala em runtime), o sistema de arquivos somente leitura e o runtime sem
rede para fora do necessário.

## Decisão

1. **Hook opcional `prepare`.** O contrato 001 ganha um Protocol separado, `PreparesData`, com `prepare(ctx:
   PackContext) -> None` (síncrono); `PackBase` ganha o default que não faz nada. O `AgentPack` **não** muda (como no
   ADR-027): pack sem o hook continua conforme.
2. **`PackContext.data_dir`.** O contexto de carga ganha `data_dir: Path | None` — o diretório do pack que a plataforma
   entrega, `<raiz>/<nome do pack>`, o mesmo no build e em runtime. A raiz vem de `AXON_PACKS_DATA_DIR`; sem ela,
   `data_dir` é `None`, e o pack recorre à própria configuração (desenvolvimento e suítes).
3. **`axon packs prepare`.** Para cada pack habilitado no `packs.yaml`, com a configuração já validada contra o
   `config_schema`, cria o `data_dir` e chama o `prepare`. Falha de qualquer pack sai com 1, nomeando o pack; `packs.yaml`
   inválido sai com 2, como o `packs check`. Na instalação, roda antes do `packs check`, que então carrega o pack com os
   dados presentes.
4. **O `prepare` só roda no build.** `axon serve` nunca o chama, e em runtime o `data_dir` é somente leitura (está na
   imagem). O `prepare` pode usar a rede, mas tudo o que baixa é fixado e conferido (revisão, hash); ele é idempotente —
   o que já está presente e íntegro não é baixado de novo.
5. **Serviços continuam fora.** O `prepare` produz arquivos, nunca processos: um pack que precisa de um serviço (um
   banco de vetores, por exemplo) o documenta no próprio repositório, e a instalação o acrescenta ao compose (ADR-042).
6. **Versão.** Mudança aditiva: contratos `0.2.1`. Um pack que implementa `prepare` ou lê `data_dir` pede
   `axon-ai-contracts>=0.2.1,<0.3` (ADR-014).

## Alternativas rejeitadas

*Scripts de preparo na instalação* (uma pasta `setup/` executada no build). Funciona sem tocar o contrato, mas cada
instalação passa a copiar conhecimento de cada pack, e um pack novo exige mudança em toda instalação que o usa.

*Baixar na primeira execução.* Contraria a FR-014, o sistema de arquivos somente leitura e a regra da 102 de nunca
baixar o modelo em runtime; e a primeira pergunta pagaria o download.

*Um entry point próprio para o preparo.* Separa o preparo do pack que sabe o que preparar e duplica a descoberta da 002.

*`prepare` no `AgentPack`.* Quebraria a conformidade de todo pack que não herda de `PackBase`.

## Consequências

- A instalação não tem nenhuma linha específica de pack: `PACKS`, o `packs.yaml`, `axon packs prepare` e `axon packs
  check` servem a qualquer pack.
- O scouting move o `model fetch` para o `prepare`; o `embedding_dir` passa a ter default `data_dir/e5-small` e sai da
  configuração obrigatória.
- A suíte de conformidade do 001 passa a exercitar o hook quando presente (chamado duas vezes, sem erro).
- A imagem de runtime copia a raiz de dados inteira do estágio de build (`/opt/axon-data`), sem saber o que há nela.
