"""`GenericPack`: pack de uso geral e pack de referência (spec 010).

Composition root do pack (ADR-012): aqui só se compõe — as políticas vivem em `tools/` e `validators/`. O pack não faz
I/O, então não declara porta secundária (princípio XIII).
"""

from __future__ import annotations

from collections.abc import Sequence

from axon_ai_contracts import AnswerValidator, PackBase, PackContext, PackManifest, ToolSpec
from axon_generic.prompts import SYSTEM_PROMPT
from axon_generic.tools.arithmetic import calculate_spec
from axon_generic.validators.answer import NonEmptyAnswer

VERSION = "0.2.0"
"""Versão do manifest; igual à da distribuição `axon-generic` (verificado em tests/test_pack.py)."""


class GenericPack(PackBase):
    """Prompt de uso geral, uma tool nativa determinística e um validator determinístico."""

    name = "generic"
    contract_version = "0.2"

    def manifest(self) -> PackManifest:
        # Manifest mínimo (FR-007): sem flow preferido, schema de configuração, dependências ou coleções.
        return PackManifest(name=self.name, version=VERSION)

    def system_prompt(self, ctx: PackContext) -> str | None:
        return SYSTEM_PROMPT

    def tools(self, ctx: PackContext) -> Sequence[ToolSpec]:
        return (calculate_spec(),)

    def validators(self, ctx: PackContext) -> Sequence[AnswerValidator]:
        return (NonEmptyAnswer(),)
