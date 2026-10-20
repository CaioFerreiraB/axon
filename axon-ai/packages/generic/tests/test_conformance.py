"""Suíte de conformidade de pack publicada com os contratos (spec 010 FR-003, T008).

Roda todas as etapas, inclusive imports (o pack não importa o core) e distribuição (a faixa de `axon-ai-contracts`
declarada cabe na faixa derivada da `contract_version`) — nada é desligado.

Sobre a etapa de distribuição: no workspace as distribuições são instaladas em modo editável, e aí
`importlib.metadata.packages_distributions()` não mapeia nenhum pacote de topo para a distribuição dele. A etapa então
não tem o que verificar e emite o aviso `distribution.not_found`. É no ambiente limpo (quickstart §5, job `clean-env`),
com instalação normal, que a faixa declarada é de fato conferida — e lá o relatório tem de vir sem nenhum item.
"""

from __future__ import annotations

from importlib.metadata import packages_distributions

from ai_generic.pack import GenericPack
from axon_ai_contracts.testing import assert_pack_conforms, check_pack, turn_view

VIEWS = (
    turn_view(question="quanto é 2+2?", answer="São 4."),
    turn_view(question="quanto é 2+2?", answer=None),
)

DISTRIBUTION_IS_VISIBLE = "ai-generic" in (packages_distributions().get("ai_generic") or [])
"""Verdadeiro na instalação normal (ambiente limpo); falso no workspace, onde a instalação é editável."""


def test_pack_conforms() -> None:
    assert_pack_conforms(GenericPack(), views=list(VIEWS))


def test_report_has_no_issue() -> None:
    """Nem mesmo `warning`: o pack de referência é o exemplo que os packs de domínio copiam."""
    report = check_pack(GenericPack(), views=list(VIEWS))
    assert report.pack_name == "generic"
    expected = () if DISTRIBUTION_IS_VISIBLE else ("distribution.not_found",)
    assert tuple(issue.code for issue in report.issues) == expected, report.render()


def test_declared_contracts_range_is_checked_when_the_distribution_is_visible() -> None:
    """No ambiente limpo, a etapa de distribuição confere a faixa `>=0.2,<0.3` do `pyproject.toml` do pack."""
    if not DISTRIBUTION_IS_VISIBLE:
        return
    report = check_pack(GenericPack(), views=list(VIEWS))
    assert not any(issue.code.startswith("distribution.") for issue in report.issues), report.render()
