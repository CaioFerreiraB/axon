# Contrato — versões, compatibilidade e classificação de mudanças

Regras normativas de `axon_ai_contracts.compat` e da ferramenta `tools/api_surface.py` (FR-016, FR-018, FR-020). Decisões
em [research.md](../research.md) (R4–R6, R16, R18).

## 1. Gramática de versão (subconjunto do PEP 440)

```text
version   := release [pre] [dev]
release   := N ("." N)*          ; N = inteiro decimal sem zeros à esquerda
pre       := ("a" | "b" | "rc") N
dev       := ".dev" N
```

- Ordem do PEP 440: `release` comparado com zeros à direita ignorados (`0.1 == 0.1.0`); para o mesmo release,
  `X.devN < XaN < XbN < XrcN < X`; `XaN.devM < XaN`.
- Fora do subconjunto (→ `InvalidVersion`): epoch (`1!2.0`), post-release (`.post1`), local (`+abc`), formas não
  normalizadas (`v1.0`, `1.0-rc1`).
- `contract_version` do pack: só `X.Y` ou `X.Y.Z` (sem pré-release nem dev).

## 2. Especificadores

| Forma | Significado |
|---|---|
| `==V` | igual a V (com zeros à direita) |
| `==V.*` | mesmo prefixo de release que V |
| `!=V`, `!=V.*` | negação das duas acima |
| `>=V`, `<=V`, `>V` | ordem do PEP 440 |
| `<V` | menor que V e, se V for final, **não** pré-release de V |
| `~=V` | V com ≥ 2 componentes; `~=X.Y` ≡ `>=X.Y,==X.*`; `~=X.Y.Z` ≡ `>=X.Y.Z,==X.Y.*` |

Cláusulas separadas por vírgula são combinadas com E. A versão instalada é avaliada como fato (equivale a
`prereleases=True` no `packaging`). Os testes diferenciais usam `packaging.specifiers.SpecifierSet(...).contains(v,
prereleases=True)` como oráculo.

## 3. Faixa derivada (FR-018)

| `contract_version` | Faixa derivada |
|---|---|
| `0.N` | `>=0.N,<0.(N+1)` |
| `0.N.P` | `>=0.N.P,<0.(N+1)` |
| `X.Y` (X ≥ 1) | `>=X.Y,<(X+1)` |
| `X.Y.Z` (X ≥ 1) | `>=X.Y.Z,<(X+1)` |

## 4. Compatibilidade

`check_compatibility(requirement, installed=__version__)`:

- `requirement` que começa com operador é faixa explícita; senão, é `contract_version` e a faixa é derivada.
- `ok = faixa.contains(installed)`.
- Se não for `ok`: `violated` = primeira cláusula violada, na ordem canônica (limite inferior antes do superior), e
  `message = f"requer axon-ai-contracts{violated}, instalado {installed}"`.

| Instalada | Requisito | Resultado |
|---|---|---|
| `0.1.4` | `"0.1"` | ok |
| `0.1.4` | `"0.2"` | `requer axon-ai-contracts>=0.2, instalado 0.1.4` |
| `0.2.0` | `"0.1"` | `requer axon-ai-contracts<0.2, instalado 0.2.0` |
| `0.2.0rc1` | `"0.1"` | `requer axon-ai-contracts<0.2, instalado 0.2.0rc1` |
| `0.1.2` | `"0.1.3"` | `requer axon-ai-contracts>=0.1.3, instalado 0.1.2` |
| `1.4.0` | `">=1.2,<2"` | ok |

Requisito malformado → `InvalidVersion`/`InvalidSpecifier` (quem chama decide: a 002 marca o pack como `error`).

## 5. Dependência declarada pelo pack (FR-018, conformidade)

Entrada: os `Requires-Dist` da distribuição do pack e a `contract_version`. A regra é pura
(`testing.check_contracts_requirement`); a leitura dos metadados é uma função fina de borda.

| Situação | Issue |
|---|---|
| Nenhum `Requires-Dist` de `axon-ai-contracts` | `distribution.missing_requirement` |
| Referência direta (`axon-ai-contracts @ git+...`) sem especificador | `distribution.direct_reference` |
| Especificador fora do subconjunto | `distribution.unsupported_specifier` |
| Conjunto aceito ⊄ faixa derivada (sem limite superior, limite inferior abaixo, etc.) | `distribution.range_too_wide` — mensagem cita a faixa derivada |
| Conjunto aceito ∩ faixa derivada = ∅ | `distribution.range_disjoint` |
| Distribuição do pack não localizada | `distribution.not_found` (*warning*) |

A inclusão é calculada sobre intervalos: cada cláusula vira intervalo (`!=` só remove pontos e é ignorada para a
inclusão); `==V.*` e `~=` viram intervalos semiabertos; a interseção das cláusulas é comparada com a faixa derivada.

## 6. Depreciação

- `removal_version(since)`: `0.N.x → 0.(N+1).0`; `X.Y[.Z] → (X+1).0.0` (X ≥ 1).
- Mensagem: `"<símbolo> está depreciado desde axon-ai-contracts <since> e será removido em <removal>"` + `"; use
  <use_instead>"`, quando houver.
- Categoria: `ContractDeprecationWarning` (subclasse de `DeprecationWarning`).
- `contract_deprecated` grava `__contract_deprecated_since__ = since` no objeto decorado; o snapshot de superfície lê
  esse atributo (§9) para verificar a janela de depreciação (§8).

## 7. Classificação de mudanças de superfície (FR-020, SC-004)

Comparação entre o snapshot da última tag `contracts-v*` e o do HEAD. Na dúvida, a regra é conservadora: toda mudança de
anotação conta como mudança de tipo.

| Mudança | Classe |
|---|---|
| Símbolo exportado removido ou renomeado | breaking |
| Distribuição ou raiz do import renomeada (ex.: `axon-ai-contracts`/`axon_ai_contracts` → `axon-ai-contracts`/`axon_ai_contracts`, ADR-037) | breaking — **uma** mudança só; os símbolos são comparados pelo nome relativo à raiz (§9) e o renome não conta como remoção sem depreciação (§8) |
| Símbolo exportado novo | aditiva |
| Tipo do símbolo mudou (ex.: dataclass → Protocol) | breaking |
| Campo de dataclass removido, renomeado, com tipo ou default alterado, ou que perdeu o default | breaking |
| Campo de dataclass novo **com** default | aditiva |
| Campo de dataclass novo **sem** default | breaking |
| Membro de Protocol removido, ou com assinatura, tipo ou `async` alterado | breaking |
| Membro novo em `AgentPack` **com** default em `PackBase` | aditiva |
| Membro novo em qualquer outro Protocol, ou em `AgentPack` sem default em `PackBase` | breaking |
| Chave de TypedDict removida, com tipo alterado, que passou a obrigatória ou perdeu `ReadOnly` | breaking |
| Chave nova opcional (`NotRequired`) em TypedDict | aditiva |
| Chave nova obrigatória em TypedDict | breaking |
| Parâmetro de função ou método removido, renomeado, reordenado, com tipo ou default alterado, ou novo obrigatório | breaking |
| Parâmetro novo opcional e só-nome (`*, x=...`) | aditiva |
| Tipo de retorno alterado | breaking |
| Valor de constante pública alterado (`RETRIEVAL_TOOL_PARAMETERS`, `RETRIEVAL_FILTERS_KEY`; não vale para `ISSUE_CODES`) | breaking |
| Código de `ContractIssue` removido ou renomeado | breaking |
| Código de `ContractIssue` novo | aditiva |
| Símbolo depreciado (novo `deprecated_since`) | aditiva |
| Só docstring ou símbolo interno (`_`) | nenhuma |

- Códigos de issue entram no snapshot como a lista ordenada `ISSUE_CODES` do kit ([testing-kit.md](testing-kit.md)) e
  são comparados **como conjunto**, pelas duas linhas próprias acima.
- Em TypedDict, obrigatoriedade e `ReadOnly` saem do **texto da anotação** (`Required[`, `NotRequired[`, `ReadOnly[`)
  combinado com `__total__`. Com `from __future__ import annotations`, `__required_keys__` e `__readonly_keys__` ficam
  errados em runtime (verificado em 3.12.3 e 3.14.7).

## 8. Bump exigido × bump declarado

| Maior classe encontrada | Versão anterior 0.x | Versão anterior ≥ 1.0 |
|---|---|---|
| nenhuma | none | none |
| aditiva | patch | minor |
| breaking | minor | major |

`declared_bump(tag, head)`: `major` se o major subiu; `minor` se o minor subiu; `patch` se só o patch subiu; `none`
se igual. **Falha** quando `declared < required` (ordem `none < patch < minor < major`). Depois de uma breaking change
no ciclo (ex.: HEAD já em `0.2.0`), novas breaking changes no mesmo ciclo passam sem novo bump.

**Janela de depreciação** (FR-016, ADR-014): remover um símbolo exportado cujo `deprecated_since` era nulo no snapshot
da tag **falha**, qualquer que seja o bump declarado. O renome da distribuição (§7) não é remoção: decidido por ADR
(ADR-037, corte seco), ele exige só a minor (FR-025).

**Pack congelado** (FR-020 b): roda só se `derive_range(versão da tag).contains(versão do HEAD)` — mesma série
compatível. Numa série nova (ex.: tag `0.1.4`, HEAD `0.2.0`), o job registra "série nova — pack congelado não se
aplica" e passa; a quebra, nesse caso, já foi validada pelo bump (§7).

## 9. Formato do snapshot

JSON com chaves ordenadas: `{"distribution": "axon-ai-contracts", "package": "axon_ai_contracts", "version": "...",
"modules": {"axon_ai_contracts": {...}, "axon_ai_contracts.testing": {...}}}`. `distribution` sai dos metadados
instalados do `package` introspectado (`dump --package`, default `axon_ai_contracts`); o CI passa o pacote que a tag
tinha (`axon_ai_contracts` até `contracts-v0.1.2`, a última marcada da série 0.1). Com a raiz
renomeada, os textos da linha de base que a citam (anotações, `repr` de aliases e defaults) passam à raiz nova, por palavra
inteira, antes da comparação. A comparação (§7) usa o nome do módulo **relativo** a `package`
(raiz e `.testing`), e os símbolos aparecem no relatório com o nome do HEAD; cada símbolo tem `kind` (`dataclass`, `protocol`, `class`, `typeddict`,
`function`, `constant`, `type_alias`), `deprecated_since` (`str` ou `null`) e os detalhes do tipo (campos, membros,
chaves, parâmetros, anotações como texto, `repr` dos defaults). O snapshot não é versionado no git: é gerado no CI
para a tag e para o HEAD.

**Determinismo**: o snapshot do mesmo código é byte a byte igual em qualquer processo. Conjuntos (`frozenset`, `set`)
nunca entram por `repr` — `repr(frozenset)` muda de ordem entre processos —, e sim como listas ordenadas; os testes
geram o snapshot em dois processos com `PYTHONHASHSEED` diferentes e comparam.
