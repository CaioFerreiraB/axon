# Implementation Plan: Provedor de identidade da plataforma

**Branch**: `012-core-identity` | **Date**: 2026-10-14 | **Spec**: [spec.md](spec.md)

**Input**: Feature specification from `/specs/012-core-identity/spec.md`

**Architecture inputs** *(PROJECT OVERRIDE — agentic-app)*: before filling Technical Context, READ
`/specs/012-core-identity/design.md` (including its "Portas e adapters" section) and every ADR listed
in the spec's Module Boundary, plus ADR-012 (architectural style). Decisions recorded there are
**pre-approved**: carry them into this plan and into `research.md` as
"Decision / Rationale (ADR-xxx) / Alternatives", do not re-research them. Any deviation requires a
new ADR in `docs/adr/` and must be listed in Complexity Tracking.

Insumos lidos: [design.md](design.md), ADR-030, ADR-031, ADR-033, ADR-012, ADR-015, ADR-020; as cinco clarificações de
2026-10-13; o desenho aprovado (Penpot, página "Login e conta") e o `PRODUCT.md`. **Refinamentos do `design.md`, sem
divergência de decisão**: sessão de 30 dias (clarificação), páginas sem `jinja2` e formulários sem `python-multipart`
(R3, R4), senha temporária em grupos em vez de lista de palavras (R10). **Nenhum ADR novo.**

## Summary

A plataforma passa a ser o próprio provedor OIDC (ADR-030). Um módulo novo, `ai_core/identity/`, guarda contas,
grupos e vínculos Google, autentica por usuário ou e-mail e senha (argon2id) ou por Google (só contas cadastradas),
serve a página de login, a troca de senha e "Minha conta", e emite tokens RS256 para dois clientes do operador — o Open
WebUI (confidencial, audiência `ai-core`) e a console (pública com PKCE, audiência `ai-core-admin`). Expõe três seams:
`AccountAdmin` e `LoginSettings` para a 008, `PublicKeySet` para a 011 injetar no verificador da 003. Escopo:
**US1–US7**; o encaixe na 003, 008, 011 e 002 é das passadas delas (R17).

## Technical Context

**Language/Version**: Python 3.14 (distribuição `ai-core`)

**Primary Dependencies**: já presentes — `pyjwt[crypto]` (com `cryptography`), `httpx`, `psycopg`/`psycopg-pool`,
`pyyaml`, `fastapi` (só no adapter HTTP). **Nova**: `argon2-cffi>=25.1,<26` (R2), confinada a `adapters/`. **Nova de
desenvolvimento**: `authlib>=1.8,<2`, só nos testes (R1, R16)

**Storage**: Postgres no schema `identity` (ADR-015) — contas, grupos, membros, pedidos pendentes, códigos, sessões,
renovação, chaves de assinatura (privada cifrada, ADR-033), ajustes; arquivo `identity.yaml` do operador, somente
leitura; contadores de tentativa em memória

**Testing**: pytest + pytest-asyncio + hypothesis; `unit/`, `contract/` (seams e portas, memória × real),
`integration/` (protocolo com o authlib como RP via transporte ASGI do `httpx`; Google simulado; varredura de segredos)

**Target Platform**: processo do core na imagem Linux ARM64 (2 OCPU, 12 GB)

**Project Type**: módulo do monolito modular (`ai_core/identity/`), com adapter primário HTTP próprio (ADR-030)

**Performance Goals**: verificação de senha < 250 ms no hardware alvo (argon2id 64 MiB, t=3); troca de código e
renovação sem hash de senha; JWKS em memória, sem I/O por requisição

**Constraints**: nenhum segredo em log, trace, erro ou resposta (FR-020); respostas de login indistinguíveis (SC-005);
`api.py`/`domain/`/`ports.py`/`service.py` sem `jwt`, `cryptography`, `argon2`, `httpx`, `psycopg`, `yaml`, `fastapi`
nem `starlette`; páginas sem script, com CSP restrita

**Scale/Scope**: 1 módulo, 3 seams, 13 portas secundárias, 5 tabelas principais; dezenas a poucas centenas de contas;
2 clientes OIDC

Nenhum `NEEDS CLARIFICATION`: as cinco perguntas foram resolvidas em 2026-10-13, e o que o `design.md` deixou para o
plano está em [research.md](research.md) (R1–R17).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Princípio | Resultado | Evidência |
|---|---|---|
| I. Núcleo agnóstico | ✅ | Nome e logotipo vêm da instalação; nenhum termo de domínio nas páginas (FR-023) |
| II. Seams | ✅ | Não consome seam de outro módulo; expõe três seams com conformidade; o grupo de admin chega como configuração |
| III. O core orquestra | N/A | Sem execução de agente |
| IV. Assistant é a fronteira | ✅ | Este módulo não decide acesso a Assistants; só diz a que grupos a pessoa pertence. A audiência própria da console impede que um token do chat alcance a administração (ADR-031) |
| V. Determinismo | ✅ | Regras do protocolo, do bloqueio e do Google são funções puras; nenhum LLM |
| VI. Conteúdo externo | ✅ | Segredos: senha só em hash, códigos, sessões e renovação só em hash, chave privada cifrada com a chave mestra (ADR-033), segredo de cliente por referência (ADR-020); `id_token` do Google verificado contra o JWKS dele |
| VII. Falha fechada | ✅ | Cliente ou `redirect_uri` inválido → página de erro, nunca redirecionamento; chave mestra ausente no `persistent` → a identidade não sobe (011); conta desativada não renova |
| VIII. Modelos por papel | N/A | Sem modelo |
| IX. Proveniência | N/A | Sem retrieval |
| X. Medir antes de calibrar | ✅ | Os números (10 min, 30 dias, 5 falhas em 15 min, argon2 64 MiB) são controles de segurança decididos na spec, não calibração de qualidade |
| XI. API independente da interface | ✅ | As páginas do provedor existem sem a console; a console é só um cliente OIDC |
| XII. Simplicidade | ⚠️ justificado | 13 portas — ver Complexity Tracking |
| XIII. Portas e adapters | ✅ | Ver gate abaixo |

**Module boundary gate** *(PROJECT OVERRIDE — principle II, mandatory)*:

- [x] Source changes stay inside this module's paths — `ai-core/packages/core/src/ai_core/identity/**` e
  `ai-core/packages/core/tests/identity/**`; fora dele, só `ai-core/packages/core/pyproject.toml` (`argon2-cffi`),
  `ai-core/pyproject.toml` (import-linter, grupo de dev com `authlib`) e `specs/README.md`. **Nada** em `assistants/`,
  `http/` nem `bootstrap/` (R17)
- [x] Every consumed seam is listed with its owner spec; no internals of other modules are used — nenhum seam consumido
- [x] Every seam this module exposes has a conformance test planned — [contracts/identity-api.md](contracts/identity-api.md)
- [x] No seam changes — os três seams nascem agora; as mudanças nos seams da 003 e da 008 são dos ADR-030/031, nas
  passadas delas
- [x] Import boundaries (import-linter) cover the new code — ver "Fronteiras verificadas"

**Ports & adapters gate** *(PROJECT OVERRIDE — principle XIII, ADR-012, mandatory)*:

- [x] The module follows `api.py` / `domain/` / `ports.py` / `service.py` / `adapters/` — completo
- [x] `api.py`, `domain/`, `ports.py` and `service.py` import no infrastructure framework — `jwt`, `cryptography`,
  `argon2`, `httpx`, `psycopg`, `psycopg_pool`, `yaml`, `fastapi`, `starlette` proibidos fora de `adapters/`
- [x] Other modules are imported only through their `api.py` — a 012 não importa nenhum; ninguém importa os internals dela
  além da 011
- [x] All I/O, time, randomness, secrets and trace go through a secondary port — banco (quatro stores), arquivo
  (`ClientSource`), rede (`UpstreamOidc`), segredos (`IdentitySecrets`), cifra (`SecretCipher`), tempo (`Clock`),
  aleatoriedade (`TokenGenerator`), hash (`PasswordHasher`), assinatura (`TokenSigner`). Trace: nenhum (R15)
- [x] Every secondary port exists for I/O, non-determinism or a planned swap — [contracts/ports.md](contracts/ports.md);
  `PasswordHasher` e `TokenSigner` existem porque o real é lento ou criptográfico e a troca por um rápido é o que deixa as
  suítes ágeis; as regras do protocolo não têm porta
- [x] Every secondary port has an in-memory adapter and a conformance suite that also runs against the real adapter
- [x] Services and adapters of other modules are instantiated only in the composition root — a 012 não instancia nada
  de outro módulo

**Resultado do gate (antes da Phase 0)**: PASS, com a justificativa de XII abaixo. **Depois da Phase 1**: PASS — o
desenho não acrescentou porta nem seam além dos listados.

## Project Structure

### Documentation (this feature)

```text
specs/012-core-identity/
├── spec.md
├── design.md
├── plan.md              # este arquivo
├── research.md          # R1–R17
├── data-model.md
├── quickstart.md
├── contracts/
│   ├── identity-api.md  # os três seams, erros e conformidade
│   ├── oidc.md          # descoberta, endpoints, tokens, erros, suíte de protocolo
│   ├── identity-yaml.md # clientes do operador
│   ├── pages.md         # login, troca de senha, Minha conta, erro
│   └── ports.md         # portas secundárias, adapters e conformidade
└── tasks.md             # /speckit-tasks
```

### Source Code (repository root)

```text
ai-core/
├── pyproject.toml                           # import-linter; grupo dev: authlib
└── packages/core/
    ├── pyproject.toml                       # argon2-cffi>=25.1,<26
    ├── src/ai_core/identity/
    │   ├── __init__.py
    │   ├── api.py                           # AccountAdmin, LoginSettings, PublicKeySet; value objects; erros
    │   ├── domain/
    │   │   ├── names.py                     # usuário, grupo, e-mail, senha, identificador de login
    │   │   ├── authorize.py                 # validação do pedido de autorização e do cliente
    │   │   ├── clients.py                   # validação do identity.yaml
    │   │   ├── pkce.py                      # S256
    │   │   ├── tokens.py                    # claims de acesso e de identidade; prazos
    │   │   ├── refresh.py                   # rotação e reuso
    │   │   ├── attempts.py                  # decisão de bloqueio
    │   │   ├── google.py                    # decisão de vínculo e recusa
    │   │   ├── keys.py                      # ciclo de vida das chaves de assinatura
    │   │   ├── settings.py                  # precedência instalação > runtime > padrão
    │   │   └── accounts.py                  # proteção do grupo de admin; regras de cadastro
    │   ├── ports.py
    │   ├── service.py                       # IdentityService: seams + casos de uso de cada endpoint
    │   └── adapters/
    │       ├── http.py                      # router(service, settings): protocolo e páginas
    │       ├── pages.py                     # HTML com escape por padrão
    │       ├── assets/identity.css
    │       ├── memory.py
    │       ├── postgres.py
    │       ├── postgres_schema.py           # migrate(pool) do schema identity
    │       ├── sql/001_accounts.sql … 004_settings.sql
    │       ├── passwords.py                 # argon2id
    │       ├── signing.py                   # RS256, geração de chave
    │       ├── cipher.py                    # AES-GCM + HKDF
    │       ├── google.py                    # UpstreamOidc
    │       ├── clients_yaml.py              # ClientSource
    │       ├── secrets_env.py               # IdentitySecrets
    │       └── cli.py                       # users …, identity keys rotate
    └── tests/identity/
        ├── conftest.py
        ├── identity_testkit.py              # contas, clientes, relógio fixo, Google simulado, app de teste com o router
        ├── unit/
        ├── contract/
        └── integration/
```

**Structure Decision**: layout hexagonal completo do ADR-012, com os nomes do `design.md`; `templates/`/`static/` do
design viram `pages.py` e `assets/` (R3).

## Fronteiras verificadas (import-linter)

Contratos novos em `ai-core/pyproject.toml`, no padrão dos módulos existentes:

1. `api.py` da 012 não importa o resto do módulo;
2. `domain/` não importa portas, service nem adapters;
3. `service.py` não importa adapters;
4. o núcleo da 012 não importa `jwt`, `cryptography`, `argon2`, `httpx`, `psycopg`, `psycopg_pool`, `yaml`, `fastapi`,
   `starlette`;
5. a 012 não importa nenhum outro módulo do core;
6. nenhum outro módulo importa `identity.domain`, `.ports`, `.service` nem `.adapters` — só a composition root;
7. `argon2` só em `ai_core.identity.adapters`.

E a 012 entra nos contratos existentes de "framework HTTP só nos adapters" e "nenhum módulo importa a composition root".

## Complexity Tracking

| Violation | Why Needed | Simpler Alternative Rejected Because |
|-----------|------------|-------------------------------------|
| 13 portas secundárias | Quatro armazenamentos com ciclos de vida diferentes (contas; pedidos, códigos, sessões e renovação; chaves; ajustes), mais rede (Google), arquivo, segredos, cifra, hash, assinatura, relógio, aleatoriedade e contadores — cada uma é I/O, não-determinismo ou algo lento cuja troca deixa as suítes ágeis (princípio XIII) | Um único store: misturaria a expiração curta de códigos com contas permanentes e impediria testar o uso único do código isolado; hash e assinatura sem porta: as suítes de protocolo levariam segundos por login com argon2 real |
| Adapter de cifra (`SecretCipher`) com código parecido com o da 009 | ADR-033: cada módulo cifra os próprios segredos com subchave própria; nenhum módulo decifra o de outro | Um módulo comum de cifra: seria um seam novo consumido por 009 e 012 só para ~40 linhas, com acoplamento que a regra "uma porta por módulo" do ADR-020 evita |

---

# Passada de 2026-10-20: identidade Axon (US8; [ADR-037](../../docs/adr/ADR-037-a-plataforma-se-chama-axon.md), [ADR-038](../../docs/adr/ADR-038-marca-da-plataforma-e-marca-da-instalacao.md))

> As seções acima são os planos das passadas anteriores e ficam como foram executadas (ADR-037, item 6); os nomes
> antigos nelas se leem pela tabela do ADR-037. Esta seção é o plano da US8.

**Insumos lidos**: [spec.md](spec.md) (US8, FR-023 reescrita, FR-024–FR-027, SC-008, clarificações de 2026-10-20),
[design.md](design.md), ADR-033, ADR-037, ADR-038, `DESIGN.md` ("Brand" e tokens), `brand-kit/svg/` e o README dele,
constituição 1.3.1, as passadas da 011 (`AXON_DISPLAY_NAME` padrão "Axon") e da 008 (`instance.custom`, a mesma regra).
Research: R20–R26. **Sem divergência do `design.md`** além do desenho da marca, que o ADR-038 decide; sem ADR novo.

## Summary (US8)

As páginas do provedor mostram o lockup Axon quando a instalação não tem marca própria, e a marca dela com "com Axon" no
rodapé quando tem; o favicon é sempre o símbolo (R20), servido com os outros assets da marca copiados do `brand-kit`
(R21). Os tokens de cor passam aos do `DESIGN.md`, com AA verificado por teste (R22). Cookie, realm, subchave e CSRF
ganham os nomes novos, em corte seco, com a mensagem de chave que não abre ampliada (R23, R24). Testes e documentos
acompanham (R25); capturas nos dois temas e duas larguras fecham a verificação (R26).

## Technical Context (US8)

- **Language/Version, dependências, storage**: sem mudança; sem migração. Cinco SVG novos no pacote (cópias do `brand-kit`).
- **Testing**: páginas (marca, atribuição, favicon), assets (servidos e iguais ao `brand-kit`), contraste dos tokens,
  cookie, realm, rótulos; o e2e da console; capturas pelo Playwright do MCP.
- **Constraints**: HTML sem script (CSP `script-src 'none'`), `img-src 'self'`; princípio I (nenhuma marca de domínio).
- Nenhum `NEEDS CLARIFICATION`.

## Constitution Check (US8)

| Princípio | Resultado | Evidência |
|---|---|---|
| I. Núcleo agnóstico de domínio | ✅ | Axon é a marca da plataforma; a da instalação continua vindo da configuração (ADR-038, Consequências) |
| II. Módulos substituíveis por seams | ✅ | Nenhum seam muda; a marca e os nomes ficam no adapter primário (`pages.py`, `http.py`) e nos adapters de cifra |
| VI. Conteúdo externo é não-confiável | ✅ | O nome da instalação continua escapado; os SVG da marca são arquivos do pacote, com a CSP de SVG |
| VII. Falha fechada e explícita | ✅ | Chave selada com o rótulo antigo para o boot, com a causa e o comando de recuperação (R24) |
| XI. API independente da interface | ✅ | As páginas continuam sem script e sem dependência da console |
| XIII. Portas e adapters | ✅ | Tudo em `adapters/` e `domain/digest.py`; nenhuma porta nova |

**Module boundary gate**: `axon_ai/identity/**` e `tests/identity/**`. Fora do módulo, só o teste de cookie da
integração da 011 e documentos vivos. **Ports & adapters gate**: sem mudança. **Resultado**: PASS.

## Project Structure (US8)

```text
axon-ai/packages/core/src/axon_ai/identity/
├── adapters/
│   ├── pages.py            # DEFAULT_NAME "Axon"; Brand.custom; lockup, atribuição e favicon (R20)
│   ├── http.py             # custom; assets da marca; cookie axon_session; realm axon (R20, R21, R23)
│   ├── cipher.py           # INFO = b"axon-ai/identity/v1" (R24)
│   └── assets/
│       ├── identity.css    # tokens do DESIGN.md; .lockup e .attribution (R20, R22)
│       └── brand/          # cópias de brand-kit/svg (R21)
├── domain/digest.py        # _CSRF_CONTEXT = "axon-ai/identity/csrf:" (R24)
└── service.py              # mensagem da chave que não abre (R24)
```

## Seam Notes for Consumers (US8)

| Consumidor | O que muda para ele |
|---|---|
| Open WebUI e console | Entram pelas mesmas páginas; quem tinha sessão entra de novo (cookie novo) |
| 011 | Nada no código: passa `AXON_DISPLAY_NAME` e `AXON_LOGO_FILE` como antes |
| 013 | Usa os mesmos SVG e tokens na passada dela |
| Operador com chaves antigas | `axon identity keys rotate --force`, como a mensagem do boot diz |

## Complexity Tracking (US8)

Nenhuma linha nova.

## Constitution Check — pós-design (US8)

Reavaliado com [contracts/pages.md](contracts/pages.md), [contracts/oidc.md](contracts/oidc.md),
[data-model.md](data-model.md) e [quickstart.md](quickstart.md) ("Fase 9, incremento 9.5"): **PASS**.
