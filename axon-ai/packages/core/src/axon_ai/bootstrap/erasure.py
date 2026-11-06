"""Os apagadores da porta `SubjectDataEraser` da 012 (incremento 9.7; ADR-058 item 3, ADR-059 item 3; R58, R59).

A composition root é a única que conhece os módulos donos de dado de usuário. Cada apagador chama o seam de apagamento
de um módulo e traduz o relatório dele em contagens e avisos; a 012 só vê a porta. A ordem é a do ADR-059: o Assistant
de usuário (003) sai antes do servidor MCP que ele referencia (007), e as conversas (008) antes da auditoria das
execuções delas (004).

Os seams são montados na primeira chamada (R59): a 012 nasce na etapa `identity`, antes de `packs`, `mcp_registry`,
`engine` e `assistants`. No servidor (`session is parts`), os serviços da plataforma — os caches das sobreposições e da
descoberta são os do processo que atende; na linha de comando, os da sessão de armazenamento do comando (FR-033).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Awaitable, Callable, Mapping
from typing import Any, Final

from axon_ai.assistants.service import SubjectEraser
from axon_ai.http.service import ConversationService
from axon_ai.identity.ports import ErasedData
from axon_ai.observability.service import SubjectPseudonymizer

ORDER: Final = ("assistants", "mcp", "conversations", "audit", "observability")
"""ADR-059, item 3: 003 → 007 → 008 → 004 → 009."""

type Call = Callable[[Any, str, str, str], Awaitable[Any]]
"""(seam, subject, ator, pseudônimo) → relatório do módulo."""

CALLS: Final[Mapping[str, Call]] = {
    "assistants": lambda seam, subject, actor, pseudonym: seam.erase_subject(subject, actor=actor, pseudonym=pseudonym),
    "mcp": lambda seam, subject, _actor, _pseudonym: seam.erase_subject(subject),
    "conversations": lambda seam, subject, _actor, _pseudonym: seam.erase_subject(subject),
    "audit": lambda seam, subject, _actor, pseudonym: seam.erase_subject(subject, pseudonym=pseudonym),
    "observability": lambda seam, subject, _actor, pseudonym: seam.erase_subject(subject, pseudonym=pseudonym),
}
"""Cada seam recebe só o que aceita: a 007 e a 008 apagam tudo (nada a pseudonimizar), a 004 e a 009 não registram
quem altera (research R58)."""

CONFIG_REFERENCES: Final = "referências na configuração (assistants.yaml): "


class ModuleEraser:
    """Um apagador com nome (porta `SubjectDataEraser` da 012). A falha do seam sobe: quem a registra é a 012."""

    def __init__(self, name: str, build: Callable[[], Any], call: Call) -> None:
        self.name = name
        self._build = build
        self._call = call
        self._seam: Any = None

    async def erase(self, subject: str, *, actor: str, pseudonym: str) -> ErasedData:
        if self._seam is None:
            self._seam = self._build()
        report = await self._call(self._seam, subject, actor, pseudonym)
        return ErasedData(counts=_counts(report), warnings=_warnings(report))


def erasers(factories: Mapping[str, Callable[[], Any]]) -> tuple[ModuleEraser, ...]:
    """Os cinco apagadores, na ordem, sobre as fábricas dadas (uma por nome de `ORDER`)."""
    return tuple(ModuleEraser(name, factories[name], CALLS[name]) for name in ORDER)


def subject_erasers(parts: Mapping[str, Any], session: Mapping[str, Any]) -> tuple[ModuleEraser, ...]:
    """Os apagadores sobre os armazenamentos de `session`: os da plataforma no servidor, os de uma sessão própria na
    linha de comando (FR-033)."""
    on_platform = session is parts

    def assistants() -> Any:
        from axon_ai.bootstrap.wiring import session_assistants

        service = parts["assistants"] if on_platform else session_assistants(parts, session)
        return SubjectEraser(
            keys=session["api_keys"],
            users=session["user_assistants"],
            overrides=session["system_overrides"],
            config=parts["assistants_config"],
            assistants=service,
            clock=parts["clock"],
        )

    def mcp() -> Any:
        from axon_ai.bootstrap.wiring import mcp_service

        return parts["mcp"] if on_platform else mcp_service(parts, store=session["mcp_store"])

    def conversations() -> Any:
        return ConversationService(store=session["conversations"], clock=parts["clock"])

    def audit() -> Any:
        from axon_ai.bootstrap.wiring import capabilities_service

        if on_platform:
            return parts["capabilities"]
        return capabilities_service(parts, audit=session["audit"], mcp=mcp())

    def observability() -> Any:
        return SubjectPseudonymizer(prices=session["price_store"], settings=session["destination_settings"])

    return erasers(
        {
            "assistants": assistants,
            "mcp": mcp,
            "conversations": conversations,
            "audit": audit,
            "observability": observability,
        }
    )


def _counts(report: Any) -> dict[str, int]:
    """Os campos inteiros do relatório do módulo, pelo nome (R58)."""
    return {
        field.name: value
        for field in dataclasses.fields(report)
        if isinstance(value := getattr(report, field.name), int) and not isinstance(value, bool)
    }


def _warnings(report: Any) -> tuple[str, ...]:
    """Só a 003 tem aviso: as referências do `assistants.yaml`, que a plataforma não muda (ADR-058 item 7)."""
    references = getattr(report, "config_references", ())
    return (CONFIG_REFERENCES + ", ".join(references),) if references else ()
