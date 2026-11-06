# Contrato — seams da 012 (`axon_ai/identity/api.py`)

Value objects e erros em [data-model.md](../data-model.md). Todas as operações são `async`. O ator é o subject de quem
pede (`user:<nome>`; `cli` pela linha de comando; `bootstrap` no admin inicial); a 008 o tira do Principal já
autorizado como admin — **este módulo não decide quem é admin** (ADR-031): ele só protege o grupo de administração.

## `AccountAdmin` — consumido pela 008 (superfície de administração) e pela CLI

```python
class AccountAdmin(Protocol):
    async def accounts(self, *, query: str | None = None, active: bool | None = True,
                       limit: int = 50, cursor: str | None = None) -> Page[Account]: ...
    async def account(self, username: str) -> Account: ...                       # AccountNotFound
    async def create(self, draft: AccountDraft, *, actor: str) -> IssuedPassword | Account: ...
    async def update(self, username: str, patch: AccountPatch, *, actor: str, version: int) -> Account: ...
    async def reset_password(self, username: str, *, actor: str) -> IssuedPassword: ...
    async def disable(self, username: str, *, actor: str) -> Account: ...
    async def enable(self, username: str, *, actor: str) -> Account: ...
    async def unlink_google(self, username: str, *, actor: str) -> Account: ...
    async def groups(self) -> tuple[Group, ...]: ...
    async def create_group(self, name: str, *, actor: str) -> Group: ...
    async def delete_group(self, name: str, *, actor: str) -> None: ...            # ProtectedGroup
    async def set_members(self, name: str, usernames: frozenset[str], *, actor: str) -> Group: ...
```

Regras (FR-001, FR-002, FR-010–FR-012, FR-015):

- `create`: nome e e-mail livres entre **todas** as contas (desativadas incluídas); grupos existentes; sem
  `google_only`, gera a senha temporária e a devolve só aqui.
- `update` com `version` desatualizada → `Conflict("version")`. Trocar e-mail não desfaz o vínculo Google.
- `disable` encerra as sessões e revoga os tokens de renovação da conta; tokens de acesso vencem sozinhos (≤ 10 min).
- Último membro **ativo** do grupo de administração: `disable`, `set_members` ou `update` de grupos que o deixem de fora
  → `ProtectedGroup`. `delete_group` do grupo de administração → `ProtectedGroup`.
- `reset_password` marca senha temporária e revoga as sessões da conta.

## `LoginSettings` — consumido pela 008

```python
class LoginSettings(Protocol):
    async def view(self) -> LoginSettingsView: ...
    async def set_google(self, enabled: bool, *, actor: str, version: int) -> LoginSettingsView: ...
```

- Variável `AXON_GOOGLE_LOGIN` definida → `set_google` levanta `InstallationDefined("google_enabled")` (ADR-033).
- Ligar sem cliente Google na instalação → `GoogleNotConfigured`.
- Padrão: ligado quando o cliente Google está configurado e nada mais diz o contrário.

## `PublicKeySet` — consumido pela 011 (injeta no verificador da 003)

```python
class PublicKeySet(Protocol):
    def jwks(self) -> Mapping[str, object]: ...    # {"keys": [jwk, ...]} das chaves active e retiring
```

Síncrono e sem I/O: o serviço mantém o conjunto em memória e o atualiza quando a chave muda (boot, rotação, expurgo).
O endpoint público `/oauth2/jwks` publica o mesmo objeto (FR-017).

## Protocolo HTTP — `adapters/http.py`

`router(service: IdentityService, settings: IdentityHttpSettings) -> APIRouter`, incluído pela 011 no app da 008.
Endpoints em [oidc.md](oidc.md); páginas em [pages.md](pages.md).

## Suítes de conformidade (`tests/identity/contract/`)

| Suíte | Prova |
|---|---|
| `test_account_admin.py` | cadastro, unicidade com contas desativadas, senha temporária só uma vez, proteção do grupo de admin, versão, desativação revoga sessões |
| `test_login_settings.py` | precedência instalação > runtime > padrão; não liga sem cliente Google |
| `test_public_key_set.py` | `active` + `retiring`; rotação mantém a anterior; rotação forçada troca tudo |

## Fase 9, incremento 9.7 (2026-11-04): apagar, um grupo de cada vez, o ator que não administra (ADR-057, ADR-058, ADR-059; research R28–R33)

```python
class AccountAdmin(Protocol):   # acréscimos
    async def delete(self, username: str, *, actor: str, actor_can_admin: bool = True) -> DeletionReport: ...
    async def add_group(self, username: str, group: str, *, actor: str, actor_can_admin: bool = True) -> Account: ...
    async def remove_group(self, username: str, group: str, *, actor: str, actor_can_admin: bool = True) -> Account: ...
    # create, update, reset_password, disable, enable, unlink_google, delete_group e set_members
    # ganham `actor_can_admin: bool = True` (keyword); ausente = como antes (FR-035)
```

| Regra | Origem | Verificada por |
|---|---|---|
| `delete` grava "em apagamento" (inativa, sem grupos, pseudônimo), revoga sessões, roda todos os apagadores com o mesmo `pseudonym`, depois apaga sessões, renovações, códigos, pedidos, associações e a conta, e troca `updated_by` das outras contas e dos ajustes pelo pseudônimo | FR-028, FR-038 | `test_account_deletion.py` |
| Algum apagador falha → `DeletionIncomplete(report)`; a conta fica em apagamento; `delete` de novo retoma com o mesmo pseudônimo | FR-029, US9 cen. 4–5 | `test_account_deletion.py` |
| Em apagamento: login e renovação recusados; `enable`/`update`/`reset_password`/`add_group`/`remove_group` → `Conflict("username")`; `create` com o mesmo nome → `Conflict("username")`; fora de `accounts(active=True)` | FR-030 | `test_account_deletion.py` |
| Própria conta → `InvalidField("username")`; último membro ativo do grupo de administração → `ProtectedGroup` — antes de qualquer mudança | FR-031 | `test_account_deletion.py` |
| `DeletionReport` não contém o pseudônimo | ADR-059, R29 | `test_account_deletion.py` |
| `add_group`/`remove_group` idempotentes, sem versão, comutam entre grupos; `GroupNotFound`/`AccountNotFound`; último admin → `ProtectedGroup` | FR-033, SC-011 | `test_group_membership.py` |
| `actor_can_admin=False`: cada recusa da R31 → `ActorNotAllowed(field)`; leituras liberadas | FR-034, SC-010 | `test_actor_not_admin.py` |
