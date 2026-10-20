"""T049 — comandos de linha de comando da 003 (contracts/cli.md): saída e código de saída, com o serviço em memória."""

from __future__ import annotations

import io

from assistants_testkit import (
    T0,
    access_service,
    assistant,
    assistants_service,
    config,
    draft,
)

from axon_ai.assistants.adapters.cli import (
    NOT_PERSISTENT_WARNING,
    keys_create_command,
    keys_list_command,
    keys_revoke_command,
    validate_command,
    validate_config_error,
)
from axon_ai.assistants.adapters.memory import InMemoryUserAssistantStore
from axon_ai.assistants.api import AssistantsConfigError
from axon_ai.assistants.ports import StoredUserAssistant

# --- assistants validate ---------------------------------------------------------------------------------------------


async def test_validate_com_todos_disponiveis_sai_com_zero() -> None:
    out = io.StringIO()
    code = await validate_command(assistants_service(config({"geral": assistant(), "outro": assistant()})), out)
    assert code == 0
    linhas = out.getvalue().splitlines()
    assert linhas[0].split()[:3] == ["geral", "system", "ok"]
    assert linhas[-1] == "2 Assistants disponíveis"


async def test_validate_com_um_indisponivel_sai_com_um_e_imprime_o_motivo() -> None:
    out = io.StringIO()
    service = assistants_service(config({"geral": assistant(), "interno": assistant(packs=["financeiro"])}))
    assert await validate_command(service, out) == 1
    texto = out.getvalue()
    assert "interno" in texto and "indisponível" in texto and "financeiro" in texto
    assert texto.splitlines()[-1] == "1 de 2 Assistants indisponível"


async def test_validate_mostra_o_dono_dos_assistants_de_usuario() -> None:
    users = InMemoryUserAssistantStore()
    await users.insert(StoredUserAssistant(owner="user:ana", draft=draft(), created_at=T0, updated_at=T0))
    out = io.StringIO()
    await validate_command(assistants_service(config(), users=users), out)
    assert "~meu-rag" in out.getvalue() and "(dono user:ana)" in out.getvalue()


def test_erro_de_arquivo_sai_com_dois_e_nomeia_o_campo() -> None:
    err = io.StringIO()
    code = validate_config_error(AssistantsConfigError("assistants.yaml: chave de topo desconhecida: x"), err)
    assert code == 2
    assert "chave de topo desconhecida: x" in err.getvalue()


# --- keys ------------------------------------------------------------------------------------------------------------


async def test_keys_create_imprime_a_chave_uma_vez_na_ultima_linha_e_ela_autentica() -> None:
    service = access_service()
    out, err = io.StringIO(), io.StringIO()
    code = await keys_create_command(
        service, subject="user:caio", groups=["operadores"], label="notebook", persistent=True, out=out, err=err
    )

    assert code == 0 and err.getvalue() == ""
    linhas = out.getvalue().splitlines()
    chave = linhas[-1]
    assert linhas[0] == "key_id: 0000000000000001"
    assert out.getvalue().count(chave) == 1
    principal = await service.authenticate(surface="private", credential=chave)
    assert principal is not None and principal.subject == "user:caio"


async def test_keys_create_recusa_subject_invalido() -> None:
    out, err = io.StringIO(), io.StringIO()
    code = await keys_create_command(
        access_service(), subject="caio", groups=[], label=None, persistent=True, out=out, err=err
    )
    assert code == 1 and "subject" in err.getvalue() and out.getvalue() == ""


async def test_keys_list_nao_mostra_chave_nem_hash() -> None:
    service = access_service()
    issued = await service.issue_as_operator(subject="user:ana", label="teste")
    out = io.StringIO()
    assert await keys_list_command(service, persistent=True, out=out, err=io.StringIO()) == 0
    texto = out.getvalue()
    assert issued.info.key_id in texto and "ativa" in texto and "user:ana" in texto
    assert issued.plaintext not in texto


async def test_keys_revoke_faz_a_chamada_seguinte_ser_recusada() -> None:
    service = access_service()
    issued = await service.issue_as_operator(subject="user:ana")
    out = io.StringIO()
    code = await keys_revoke_command(service, key_id=issued.info.key_id, persistent=True, out=out, err=io.StringIO())
    assert code == 0 and "revogada" in out.getvalue()
    assert await service.authenticate(surface="private", credential=issued.plaintext) is None

    lista = io.StringIO()
    await keys_list_command(service, persistent=True, out=lista, err=io.StringIO())
    assert "revogada em" in lista.getvalue()


async def test_keys_revoke_de_inexistente_sai_com_um() -> None:
    err = io.StringIO()
    code = await keys_revoke_command(
        access_service(), key_id="00000000000000ff", persistent=True, out=io.StringIO(), err=err
    )
    assert code == 1 and "00000000000000ff" in err.getvalue()


async def test_keys_avisa_quando_o_armazenamento_nao_e_persistente() -> None:
    service = access_service()
    err = io.StringIO()
    await keys_create_command(
        service, subject="user:ana", groups=[], label=None, persistent=False, out=io.StringIO(), err=err
    )
    assert NOT_PERSISTENT_WARNING in err.getvalue()
    for command in (keys_list_command,):
        err = io.StringIO()
        await command(service, persistent=False, out=io.StringIO(), err=err)
        assert NOT_PERSISTENT_WARNING in err.getvalue()
