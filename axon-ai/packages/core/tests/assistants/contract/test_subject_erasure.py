"""T136 — US15: o seam Subject Erasure (ADR-058; research R52 a R54; SC-012). Roda sobre o armazenamento das duas
versões."""

from __future__ import annotations

from typing import Any

import pytest
from assistants_testkit import (
    ANA,
    CAIO_KEY,
    POLICIES,
    MutableClock,
    access_service,
    assistant,
    assistants_service,
    config,
    draft,
    private,
)

from axon_ai.assistants.adapters.memory import (
    InMemoryApiKeyStore,
    InMemoryAssistantConfigSource,
    InMemorySystemOverrideStore,
    InMemoryUserAssistantStore,
)
from axon_ai.assistants.api import (
    AssistantNotFound,
    AuthOverride,
    Conflict,
    ErasureReport,
    ModelsOverride,
    NotFound,
    Principal,
    RequestRejected,
)
from axon_ai.assistants.domain.overrides import StoredOverride
from axon_ai.assistants.service import SubjectEraser
from axon_ai.llm.api import ModelRef

pytestmark = pytest.mark.us15

ACTOR = "user:caio"
PSEUDO = "deleted:0123456789abcdef"
EVA = Principal(subject="user:eva", scheme="oidc", groups=frozenset({"equipe"}))
ANA_EQUIPE = Principal(subject="user:ana", scheme="oidc", groups=frozenset({"equipe"}))


def _yaml() -> dict[str, Any]:
    auth = {"schemes": ["oidc", "api_key"], "allow": ["group:equipe"]}
    return config(
        {
            "geral": assistant(flow="chat", overrides=["auth", "models"], auth=auth),
            "solo": assistant(flow="chat", overrides=["auth"], auth=auth),
            "interno": private(allow=["user:ana", "group:equipe"], schemes=["oidc"], flow="chat"),
            "outro": private(allow=["user:anabela"], schemes=["oidc"], flow="chat"),
        },
        policies=POLICIES,
    )


@pytest.fixture(params=["memoria", "postgres"])
def stores(request: pytest.FixtureRequest) -> tuple[Any, Any, Any]:
    if request.param == "memoria":
        return InMemoryApiKeyStore(), InMemoryUserAssistantStore(), InMemorySystemOverrideStore()
    from axon_ai.assistants.adapters.api_keys_postgres import PostgresApiKeyStore
    from axon_ai.assistants.adapters.assistants_postgres import PostgresUserAssistantStore
    from axon_ai.assistants.adapters.overrides_postgres import PostgresSystemOverrideStore

    pool = request.getfixturevalue("migrated_pool")
    return PostgresApiKeyStore(pool), PostgresUserAssistantStore(pool), PostgresSystemOverrideStore(pool)


class Env:
    def __init__(self, keys: Any, users: Any, overrides: Any, data: dict[str, Any] | None = None) -> None:
        data = data or _yaml()
        self.clock = MutableClock()
        self.keys, self.users, self.overrides = keys, users, overrides
        self.access = access_service(keys=keys, clock=self.clock)
        self.assistants = assistants_service(
            data, users=users, overrides=overrides, clock=self.clock, flow_roles={"chat": ("generation",)}
        )
        self.eraser = SubjectEraser(
            keys=keys,
            users=users,
            overrides=overrides,
            config=InMemoryAssistantConfigSource(data).load(),
            assistants=self.assistants,
            clock=self.clock,
        )

    async def erase(self, subject: str = "user:ana") -> ErasureReport:
        report: ErasureReport = await self.eraser.erase_subject(subject, actor=ACTOR, pseudonym=PSEUDO)
        return report


@pytest.fixture
def env(stores: tuple[Any, Any, Any]) -> Env:
    return Env(*stores)


def _auth(*allow: str) -> AuthOverride:
    return AuthOverride(schemes=frozenset({"oidc", "api_key"}), allow=allow)


async def _ana(env: Env) -> tuple[str, str]:
    """Dois Assistants de usuário, uma chave ativa e uma revogada, e `user:ana` no `allow` sobreposto de `geral`."""
    await env.assistants.create(ANA, draft("um"))
    await env.assistants.create(ANA, draft("dois"))
    ativa = await env.access.issue_as_operator(subject="user:ana")
    revogada = await env.access.issue_as_operator(subject="user:ana")
    await env.access.revoke_as_operator(key_id=revogada.info.key_id)
    await env.assistants.override_auth("geral", _auth("user:ana", "group:equipe"), actor=CAIO_KEY, version=None)
    return ativa.plaintext, revogada.info.key_id


# --- cenário independente e cenários 1 a 3, 5 e 7 --------------------------------------------------------------------


async def test_apaga_assistants_chaves_e_entradas_e_avisa_do_yaml(env: Env) -> None:
    chave, _ = await _ana(env)
    bia = await env.access.issue_as_operator(subject="user:bia")
    await env.assistants.resolve(model="geral", principal=ANA_EQUIPE)  # aquece o cache da efetiva

    report = await env.erase()

    assert report == ErasureReport(
        user_assistants=2, api_keys=2, override_entries=1, authored=1, config_references=("interno",)
    )
    assert await env.access.authenticate(surface="private", credential=chave) is None
    assert [info.subject for info in await env.access.keys_as_operator()] == ["user:bia"]
    assert bia.info.key_id in {info.key_id for info in await env.access.keys_as_operator()}
    assert list(await env.assistants.mine(ANA)) == []
    with pytest.raises(NotFound):
        await env.assistants.get(ANA, "~um")

    view = await env.assistants.system_assistant("geral", actor=CAIO_KEY)
    (override,) = view.overrides
    assert override.payload == _auth("group:equipe")
    assert override.version == 2 and override.updated_by == ACTOR and override.state == "active"
    historico = await env.assistants.history("geral", actor=CAIO_KEY)
    assert historico[0].action == "saved" and historico[0].actor == ACTOR
    # A resolução seguinte já vê a versão nova: `user:ana` sem `equipe` não entra mais.
    with pytest.raises(AssistantNotFound):
        await env.assistants.resolve(model="geral", principal=ANA)
    assert (await env.assistants.resolve(model="geral", principal=EVA)).assistant == "geral"


async def test_impressao_digital_preservada(env: Env) -> None:
    await env.assistants.override_auth("geral", _auth("user:ana", "group:equipe"), actor=CAIO_KEY, version=None)
    (antes,) = await env.overrides.get("geral")
    await env.erase()
    (depois,) = await env.overrides.get("geral")
    assert depois.fingerprint == antes.fingerprint and depois.version == antes.version + 1


# --- cenário 4: allow vazio, falha fechada ---------------------------------------------------------------------------


async def test_unica_entrada_deixa_o_allow_vazio_e_o_assistant_indisponivel(env: Env) -> None:
    await env.assistants.override_auth("solo", _auth("user:ana"), actor=CAIO_KEY, version=None)

    report = await env.erase()

    assert report.override_entries == 1
    (guardada,) = await env.overrides.get("solo")
    assert guardada.payload["allow"] == []
    with pytest.raises(AssistantNotFound):
        await env.assistants.resolve(model="solo", principal=EVA)  # nunca volta ao `group:equipe` do YAML
    view = await env.assistants.system_assistant("solo", actor=CAIO_KEY)
    assert any("override.auth" in reason for reason in view.status.reasons)
    assert view.effective_auth.allow == ()


async def test_sobreposicao_inativa_tambem_e_limpa_e_continua_inativa(stores: tuple[Any, Any, Any]) -> None:
    keys, users, overrides = stores
    antes = Env(keys, users, overrides)
    await antes.assistants.override_auth("geral", _auth("user:ana", "group:equipe"), actor=CAIO_KEY, version=None)
    # Deploy que muda a seção `auth` do YAML: a sobreposição fica inativa.
    mudado = _yaml()
    mudado["assistants"]["geral"]["auth"] = {"schemes": ["oidc"], "allow": ["group:outra"]}
    depois = Env(keys, users, overrides, mudado)

    report = await depois.erase()

    assert report.override_entries == 1
    (guardada,) = await overrides.get("geral")
    assert guardada.payload["allow"] == ["group:equipe"]
    (view,) = (await depois.assistants.system_assistant("geral", actor=CAIO_KEY)).overrides
    assert view.state == "inactive"


# --- cenário 6: idempotência; sistemas; validação --------------------------------------------------------------------


async def test_repetir_da_zero_e_as_mesmas_referencias(env: Env) -> None:
    await _ana(env)
    await env.erase()
    assert await env.erase() == ErasureReport(config_references=("interno",))


async def test_subject_sem_dado_nenhum(env: Env) -> None:
    assert await env.erase("user:zeca") == ErasureReport()


async def test_sistema_perde_chaves_e_entradas(env: Env) -> None:
    await env.access.issue_as_operator(subject="svc:robo")
    await env.assistants.override_auth("geral", _auth("svc:robo", "group:equipe"), actor=CAIO_KEY, version=None)

    report = await env.erase("svc:robo")

    assert report == ErasureReport(api_keys=1, override_entries=1, authored=1)


async def test_subject_mal_formado_e_recusado(env: Env) -> None:
    with pytest.raises(RequestRejected) as error:
        await env.erase("ana")
    assert error.value.field == "subject"


# --- conflito de versão (R53) ----------------------------------------------------------------------------------------


class _Disputed(InMemorySystemOverrideStore):
    """Um admin grava entre a leitura e a escrita do apagamento, `times` vezes."""

    def __init__(self, times: int) -> None:
        super().__init__()
        self.times = times
        self.erasing = False

    async def put(self, record: StoredOverride, *, expected_version: int | None) -> StoredOverride:
        if self.erasing and self.times > 0:
            self.times -= 1
            current = await super().get(record.assistant)
            (atual,) = [item for item in current if item.section == record.section]
            await super().put(atual, expected_version=atual.version)  # a gravação concorrente
        return await super().put(record, expected_version=expected_version)


@pytest.mark.parametrize(("vezes", "conclui"), [(2, True), (3, False)])
async def test_conflito_de_versao_tenta_de_novo_ate_tres_vezes(vezes: int, conclui: bool) -> None:
    store = _Disputed(vezes)
    env = Env(InMemoryApiKeyStore(), InMemoryUserAssistantStore(), store)
    await env.assistants.override_auth("geral", _auth("user:ana", "group:equipe"), actor=CAIO_KEY, version=None)
    store.erasing = True

    if conclui:
        assert (await env.erase()).override_entries == 1
        (guardada,) = await store.get("geral")
        assert guardada.payload["allow"] == ["group:equipe"]
    else:
        with pytest.raises(Conflict):
            await env.erase()


async def test_sem_armazenamento_de_sobreposicoes(stores: tuple[Any, Any, Any]) -> None:
    keys, users, _ = stores
    eraser = SubjectEraser(
        keys=keys,
        users=users,
        overrides=None,
        config=InMemoryAssistantConfigSource(_yaml()).load(),
        assistants=assistants_service(_yaml(), users=users),
        clock=MutableClock(),
    )
    assert await eraser.erase_subject("user:ana", actor=ACTOR, pseudonym=PSEUDO) == ErasureReport(
        config_references=("interno",)
    )


async def test_assistant_de_usuario_apagado_some_da_resolucao(env: Env) -> None:
    await _ana(env)
    await env.erase()
    with pytest.raises(AssistantNotFound):
        await env.assistants.resolve(model="~um", principal=ANA)


# --- cenário 8: o que fica, pseudonimizado (ADR-059; research R56) ---------------------------------------------------


async def test_autora_ator_e_versoes_antigas_passam_ao_pseudonimo(env: Env) -> None:
    ana_admin = Principal(
        subject="user:ana", scheme="api_key", groups=frozenset({"operadores"}), scopes=frozenset({"admin"})
    )
    await env.assistants.override_auth("geral", _auth("user:ana", "group:equipe"), actor=ana_admin, version=None)
    await env.assistants.override_auth("geral", _auth("user:ana", "user:bia"), actor=CAIO_KEY, version=1)

    report = await env.erase()

    assert report.override_entries == 1 and report.authored >= 3
    historico = await env.assistants.history("geral", actor=CAIO_KEY)
    textos = repr(historico)
    assert "user:ana" not in textos and PSEUDO in textos and "user:bia" in textos
    assert (await env.erase()).authored == 0


async def test_pseudonimo_mal_formado_e_recusado(env: Env) -> None:
    for pseudonym in ("deleted:xyz", "user:ana", "deleted:0123456789ABCDEF"):
        with pytest.raises(RequestRejected) as error:
            await env.eraser.erase_subject("user:ana", actor=ACTOR, pseudonym=pseudonym)
        assert error.value.field == "pseudonym"


async def test_nada_no_schema_cita_o_subject(stores: tuple[Any, Any, Any], request: pytest.FixtureRequest) -> None:
    if isinstance(stores[0], InMemoryApiKeyStore):
        pytest.skip("busca no schema: só no Postgres")
    env = Env(*stores)
    await _ana(env)
    ana_admin = Principal(
        subject="user:ana", scheme="api_key", groups=frozenset({"operadores"}), scopes=frozenset({"admin"})
    )
    await env.assistants.override_models(
        "geral",
        ModelsOverride(roles={"generation": ModelRef.parse("ollama/qwen3:1.7b")}),
        actor=ana_admin,
        version=None,
    )
    await env.erase()

    pool = request.getfixturevalue("migrated_pool")
    async with pool.connection() as connection:
        cursor = await connection.execute(
            "SELECT table_name, column_name FROM information_schema.columns WHERE table_schema = 'assistants' "
            "AND data_type IN ('text', 'jsonb', 'ARRAY')"
        )
        columns = await cursor.fetchall()
        achados = []
        for table, column in columns:
            cursor = await connection.execute(
                f"SELECT count(*) FROM assistants.{table} WHERE {column}::text LIKE %s", ("%user:ana%",)
            )
            (count,) = await cursor.fetchone()
            if count:
                achados.append((table, column, count))
    assert achados == []
