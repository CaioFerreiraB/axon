# ADR-042 — Instalação por camadas: imagens base da plataforma e um repositório por instalação (substitui o ADR-022)

- **Status:** Aceita · 2026-10-21
- **Specs afetadas:** [002-core-pack-runtime](../../specs/002-core-pack-runtime/spec.md) (US5, US7, FR-013;
  contrato `installation.md`), [011-core-bootstrap](../../specs/011-core-bootstrap/spec.md) (arquivos de configuração
  na imagem; nenhum arquivo de segredo obrigatório)
- **Origem:** conversa com o mantenedor (2026-10-21): fazer o deploy de verdade numa VM pequena gerida pelo Portainer CE
  (Docker standalone, Caddy em contêiner na frente), com o `axon-deploy` público e de referência, sem dados de
  instalação nem conhecimento de pack. Refina o ADR-009; depende do ADR-041

## Contexto

O ADR-022 pôs o core num estágio do `Dockerfile` da instalação e previu: "quando houver mais de uma instalação, o
estágio `core` vira a imagem publicada, e este ADR é substituído". Hoje o `axon-deploy` é, ao mesmo tempo, a
referência e a instalação do mantenedor: o `PACKS` default, o passo do modelo do scouting, o Qdrant no compose, os
Assistants e os endereços `localhost` estão todos nele.

E o deploy real expõe três problemas:
- **Build na VM.** O build precisa de leitura SSH nos repositórios privados e de memória para instalar o core e os
  packs; numa VM pequena, nenhum dos dois é aceitável.
- **Arquivos montados.** `assistants.yaml` e `identity.yaml` são montados de `./config` por caminho relativo. Numa stack
  do Portainer CE, um caminho relativo resolve dentro do diretório de dados do próprio Portainer; volumes relativos em
  stacks do Git são do Business Edition, e `configs` do Docker exigem Swarm.
- **Pack na referência.** Quem fizer um pack próprio teria de editar o `Dockerfile` da referência.

Nenhum dos arquivos de configuração tem segredo: o `identity.yaml` referencia o segredo do cliente por nome de variável,
e o dia a dia dos Assistants já mudou para as sobreposições pela console (ADR-032, ADR-040).

## Decisão

1. **Três camadas, três donos.**
   - **Plataforma (`axon-deploy`, público):** imagens base, o modelo de instalação e a documentação. Nenhum pack além
     do `axon-generic`, nenhum endereço, nenhum segredo.
   - **Pack (o repositório de cada pack):** o que ele precisa em runtime ele prepara no build (ADR-041); serviços de que
     dependa, ele documenta.
   - **Instalação (um repositório privado por instalação):** escolhe a versão da plataforma, os packs, a configuração e
     os serviços de que os packs dependem.
2. **Imagens base, por versão do core.** O CI do `axon-deploy` publica, a partir de uma tag do `axon`, com a versão do
   core como tag da imagem (imutável; nunca `latest`):
   - `axon-build`: contratos, core e `axon-generic` em `/opt/axon`, com `uv`, git e cliente SSH — o ponto de partida do
     estágio que instala os packs;
   - `axon-runtime`: o mesmo ambiente endurecido como no ADR-022 (sem `uv`, `pip` nem `ensurepip`; usuário `axon`, uid
     10001, sem escrita no ambiente; `axon serve`). Roda sozinha, só com o `generic`;
   - `axon-console`: a console de administração da mesma tag, no nginx sem privilégio.

   O registry é o GHCR do dono do `axon`. A visibilidade das imagens acompanha a do `axon`: privadas enquanto ele for.
3. **O modelo de instalação** (`template/` no `axon-deploy`), copiado para o repositório da instalação:
   - `Dockerfile` sem nada de pack: `FROM axon-build` → instala `PACKS` (SSH do BuildKit, `--no-sources`) → `axon packs
     prepare` → `axon packs check`; `FROM axon-runtime` → copia `/opt/axon`, a raiz de dados dos packs e `config/`;
   - `config/` (`packs.yaml`, `assistants.yaml`, `identity.yaml`, logotipo opcional), com o `generic` e endereços de
     exemplo;
   - `compose.yml` só com imagens (sem `build`), tags fixadas, sem porta publicada; os serviços que o proxy alcança
     entram numa rede externa (`AXON_PROXY_NETWORK`) com apelidos próprios (`axon-console`, `axon-chat`), para não
     colidirem com outras aplicações na mesma rede; um `compose.local.yml` acrescenta build e portas para rodar na
     máquina do operador;
   - `.env.example` e o workflow de release (abaixo).
4. **Configuração sem segredo vai na imagem** (`/etc/axon/`), não é montada: o build valida exatamente o que roda (como
   o `packs.yaml` já fazia, R24 da 002), e o deploy não depende de arquivo no servidor. Mudar a configuração é um commit e
   uma imagem nova; mudar em runtime continua sendo pela console (ADR-032, ADR-040).
5. **Segredos só no ambiente** da stack (no Portainer, as variáveis da stack; localmente, o `.env`). Nenhum arquivo de
   segredo é obrigatório: o primeiro administrador é criado por `axon users create` no console do contêiner (o
   `AXON_BOOTSTRAP_ADMIN_PASSWORD_FILE` continua valendo para quem monta arquivos).
6. **Release pelo CI da instalação.** Push na branch principal ou tag constrói a imagem da instalação, com deploy keys
   só de leitura nos repositórios de packs privados, e a publica no registry privado da instalação, com a tag do commit
   (e a da versão, numa tag do git). O compose referencia a tag; atualizar é um commit que troca a tag.
7. **Deploy no Portainer CE.** Stack do tipo *Repository*, apontando para o `compose.yml` do repositório da instalação;
   segredos nas variáveis da stack; o registry cadastrado com uma credencial só de leitura de pacotes; atualização pelo
   *redeploy* (ou o *polling* do Git). O proxy reverso (Caddy, no caso do mantenedor) roteia os domínios para os
   apelidos da rede externa; o domínio da console é o `AXON_PUBLIC_URL`, porque o nginx dela repassa `/v1`, `/oauth2`,
   `/.well-known` e `/admin/v1` ao core (R45 da 002).

## Alternativas rejeitadas

*Manter o build na VM* (`docker compose up --build`, o README de hoje). Exige as chaves SSH dos repositórios privados no
servidor e memória para o build; cada servidor builda de novo o que o CI já buildou.

*Arquivos de configuração numa pasta fixa da VM*, com montagem por caminho absoluto. Funciona no Portainer CE, mas a
configuração sai do git e passa a ser editada por SSH no servidor.

*Volumes relativos de stacks do Git (Portainer BE) ou `configs` do Swarm.* Amarram a instalação a uma edição paga ou a
outro modo de orquestração.

*O `axon-deploy` publicar uma imagem por combinação de packs.* Acopla a referência aos packs de cada instalação, que é
o que este ADR desfaz.

*Instalação como fork do `axon-deploy`.* O fork carrega as imagens base, os testes da referência e o histórico dela;
o modelo de instalação é pequeno de propósito, e as imagens base absorvem o que evolui com a plataforma.

## Consequências

- O `axon-deploy` perde o `PACKS` default, o passo do modelo do scouting, o Qdrant, os Assistants e os endereços do
  mantenedor; o `check-build.sh` prova a US5 com o `generic` e o pack incompatível de propósito, sobre as imagens base e
  o modelo de instalação.
- A instalação do mantenedor sai do `axon-deploy` para um repositório próprio e privado, criado a partir do modelo.
- O CI de uma instalação precisa ler as imagens base no GHCR (acesso do repositório da instalação ao pacote, ou um
  token só de leitura) e os repositórios dos packs privados (deploy keys).
- Tornar o `axon-deploy` público não torna a plataforma instalável por terceiros enquanto o `axon` e as imagens base
  forem privados; isso é decisão à parte.
- O contrato `installation.md` da 002 deixa de ter `assistants.yaml` e `identity.yaml` montados; o FR-013 passa a falar
  de imagens base e do modelo de instalação.
