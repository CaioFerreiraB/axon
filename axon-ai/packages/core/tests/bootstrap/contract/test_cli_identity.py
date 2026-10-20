"""T057 — `axon users …` e `axon identity keys rotate` pela raiz (research R42), com a identidade desligada e,
contra o Postgres, ligada no `persistent`."""

from __future__ import annotations

import base64
import io
import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from bootstrap_testkit import ASSISTANTS_YAML, PACKS_YAML, FakeServer

from axon_ai.bootstrap import cli
from axon_ai.identity.domain.accounts import TEMPORARY_PASSWORD_PATTERN

PG_DSN = os.environ.get("AXON_TEST_POSTGRES_DSN")
needs_pg = pytest.mark.skipif(PG_DSN is None, reason="defina AXON_TEST_POSTGRES_DSN para rodar contra um Postgres")
Cap = pytest.CaptureFixture[str]


@pytest.fixture
def ambiente(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    for name in ("AXON_DEV_API_KEY", "AXON_OIDC_ISSUER", "AXON_DATABASE_URL", "AXON_IDENTITY_ENABLED"):
        monkeypatch.delenv(name, raising=False)
    (tmp_path / "packs.yaml").write_text(PACKS_YAML, encoding="utf-8")
    (tmp_path / "assistants.yaml").write_text(ASSISTANTS_YAML, encoding="utf-8")
    monkeypatch.setenv("AXON_PROFILE", "test")
    monkeypatch.setenv("AXON_PACKS_FILE", str(tmp_path / "packs.yaml"))
    monkeypatch.setenv("AXON_ASSISTANTS_FILE", str(tmp_path / "assistants.yaml"))
    return tmp_path


def _run(argv: list[str]) -> tuple[int, str, str]:
    out, err = io.StringIO(), io.StringIO()
    code = cli.main(argv, server=FakeServer(), out=out, err=err)
    return code, out.getvalue(), err.getvalue()


def test_sem_identidade_os_comandos_explicam_e_saem_com_1(ambiente: Path) -> None:
    code, _, err = _run(["users", "list"])
    assert code == 1 and "identidade desligada" in err


@pytest.fixture
def persistente(ambiente: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    if PG_DSN is None:
        pytest.skip("defina AXON_TEST_POSTGRES_DSN")
    import psycopg

    with psycopg.connect(PG_DSN, autocommit=True) as connection:
        connection.execute("DROP SCHEMA IF EXISTS identity CASCADE")
    clients = ambiente / "identity.yaml"
    clients.write_text(
        "version: 1\nclients:\n  console:\n    type: public\n    audience: ai-core-admin\n"
        "    redirect_uris: [http://localhost:8080/callback]\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AXON_PROFILE", "persistent")
    monkeypatch.setenv("AXON_DATABASE_URL", PG_DSN)
    monkeypatch.setenv("AXON_IDENTITY_ENABLED", "true")
    monkeypatch.setenv("AXON_PUBLIC_URL", "http://localhost:8000")
    monkeypatch.setenv("AXON_IDENTITY_CLIENTS_FILE", str(clients))
    monkeypatch.setenv("AXON_MASTER_KEY", base64.b64encode(bytes(range(32))).decode())
    yield


@needs_pg
def test_persistent_cria_lista_redefine_e_gira_chaves(persistente: None, monkeypatch: pytest.MonkeyPatch) -> None:
    # o primeiro admin, antes de o servidor subir: o grupo de administração nasce aqui (FR-018)
    monkeypatch.setattr("sys.stdin", io.StringIO("senha-forte-do-root\n"))
    argv = ["users", "create", "root", "--email", "root@exemplo.org", "--group", "admin", "--password-stdin"]
    code, out, err = _run(argv)
    assert code == 0, err
    assert "senha-forte-do-root" not in out + err

    code, out, _ = _run(["users", "list"])
    assert code == 0 and out.splitlines() == ["root  root@exemplo.org  admin  ativa"]

    code, out, err = _run(["groups", "create", "equipe"])
    assert code == 0, err
    monkeypatch.setattr("sys.stdin", io.StringIO("senha-forte-da-bia\n"))
    argv = ["users", "create", "bia", "--email", "bia@exemplo.org", "--group", "equipe", "--password-stdin"]
    assert _run(argv)[0] == 0
    code, out, _ = _run(["groups", "list"])
    assert code == 0 and out.splitlines() == ["admin  1  (administração)", "equipe  1"]

    code, out, _ = _run(["users", "password", "root"])
    assert code == 0 and TEMPORARY_PASSWORD_PATTERN.fullmatch(out.splitlines()[-1])

    code, out, _ = _run(["identity", "keys", "rotate"])
    assert code == 0 and "chave nova" in out
