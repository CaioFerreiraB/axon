"""A ação do controller: o formato pedido ao provider e a leitura da saída — puras, sem I/O (research R17, R18).

O controller emite **uma** ação por iteração (FR-005): chamar uma tool ou responder. O formato é um `anyOf` com um ramo
por tool do catálogo — nome como `const`, parâmetros da tool saneados —, para que a saída estruturada restrinja, no
modelo pequeno, justamente o que ele mais erra: o nome e a forma dos argumentos (arch-v1 §9). A validação de verdade
dos argumentos continua no gateway (004 FR-006); aqui só se lê a forma da ação.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Final

from axon_ai.capabilities.api import CatalogTool
from axon_ai_contracts import JSONValue

CONTROLLER_INSTRUCTION: Final = (
    "Você decide o próximo passo para responder à última mensagem do usuário. Responda apenas com um objeto JSON, sem "
    'texto fora dele: {"action": "tool", "name": "<nome>", "arguments": {...}} para chamar uma das ferramentas '
    'listadas, ou {"action": "answer"} quando já tiver o necessário para responder. Uma ação por vez; use só '
    "ferramentas da lista. As imagens que as ferramentas devolvem são mostradas ao usuário junto da resposta: se ele "
    "pedir um gráfico, uma imagem ou uma figura, ou perguntar por uma que uma ferramenta devolveu, e houver "
    "ferramenta que a produza, chame-a em vez de descrevê-la ou desenhá-la em texto."
)
"""Texto do core, sem domínio (princípio I): o catálogo e o assunto chegam pelas tools e pela conversa."""

SCHEMA_NAME: Final = "controller_action"

EMPTY: Final = "resposta vazia"
MALFORMED: Final = "JSON malformado"
NOT_OBJECT: Final = "a ação precisa ser um objeto JSON"
UNKNOWN_ACTION: Final = 'ação desconhecida: use "tool" ou "answer"'
MISSING_NAME: Final = "ação tool sem nome de ferramenta"
BAD_ARGUMENTS: Final = "os argumentos precisam ser um objeto JSON"
UNKNOWN_IMAGE: Final = "view_image com id fora das imagens da resposta anterior"

INVALID_REASONS: Final = frozenset(
    {EMPTY, MALFORMED, NOT_OBJECT, UNKNOWN_ACTION, MISSING_NAME, BAD_ARGUMENTS, UNKNOWN_IMAGE}
)
"""Os motivos possíveis de uma ação inválida. São texto do motor: nunca copiam a saída do modelo, que pode trazer
argumentos ou conteúdo de tool — é o que mantém o evento de trace sem conteúdo (ADR-017)."""


@dataclass(frozen=True, slots=True, kw_only=True)
class ToolAction:
    name: str
    arguments: Mapping[str, JSONValue] = field(default_factory=lambda: MappingProxyType({}))


@dataclass(frozen=True, slots=True)
class AnswerAction:
    pass


@dataclass(frozen=True, slots=True, kw_only=True)
class ViewImageAction:
    """Marca uma imagem da resposta anterior para a geração (ADR-044, item 8). Não é tool: não passa pelo gateway."""

    id: str


@dataclass(frozen=True, slots=True, kw_only=True)
class InvalidAction:
    reason: str


type Action = ToolAction | AnswerAction | ViewImageAction | InvalidAction


# --- esquema --------------------------------------------------------------------------------------------------------

_DROPPED: Final = frozenset({"pattern", "patternProperties"})
"""Regex de terceiro vira gramática no provider local (o mesmo risco que levou a 004 a desligar `pattern` em MCP)."""

_SCHEMA_MAPS: Final = frozenset({"properties", "$defs", "definitions", "dependentSchemas"})
_SCHEMA_VALUES: Final = frozenset(
    {
        "items",
        "additionalProperties",
        "not",
        "if",
        "then",
        "else",
        "contains",
        "propertyNames",
        "unevaluatedProperties",
        "unevaluatedItems",
        "additionalItems",
    }
)
_SCHEMA_LISTS: Final = frozenset({"allOf", "anyOf", "oneOf", "prefixItems"})

_FREE_OBJECT: Final[Mapping[str, JSONValue]] = MappingProxyType({"type": "object"})


def _has_ref(value: object) -> bool:
    if isinstance(value, Mapping):
        return "$ref" in value or any(_has_ref(item) for item in value.values())
    if isinstance(value, list | tuple):
        return any(_has_ref(item) for item in value)
    return False


def _clean(schema: object) -> Any:
    """Copia o esquema sem `pattern`/`patternProperties` nas posições de esquema — um parâmetro chamado `pattern`
    (dentro de `properties`) é nome, não palavra-chave, e fica."""
    if not isinstance(schema, Mapping):
        return schema
    cleaned: dict[str, Any] = {}
    for key, value in schema.items():
        if key in _DROPPED:
            continue
        if key in _SCHEMA_MAPS and isinstance(value, Mapping):
            cleaned[key] = {name: _clean(item) for name, item in value.items()}
        elif key in _SCHEMA_VALUES:
            cleaned[key] = _clean(value)
        elif key in _SCHEMA_LISTS and isinstance(value, list | tuple):
            cleaned[key] = [_clean(item) for item in value]
        else:
            cleaned[key] = _plain(value)
    return cleaned


def _plain(value: object) -> Any:
    """Cópia em tipos simples (o catálogo da 004 chega congelado), para o formato ir ao provider como JSON."""
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [_plain(item) for item in value]
    return value


def sanitize(parameters: Mapping[str, JSONValue]) -> dict[str, Any]:
    """Parâmetros de uma tool prontos para o formato: sem regex; com `$ref` em qualquer ponto, objeto livre — dentro
    do `anyOf` o `$ref` passaria a apontar para a raiz errada (R17). O gateway valida os argumentos de verdade."""
    if _has_ref(parameters):
        return dict(_FREE_OBJECT)
    cleaned: dict[str, Any] = _clean(parameters)
    return cleaned


def action_schema(tools: Sequence[CatalogTool], images: Sequence[str] = ()) -> dict[str, Any]:
    """`anyOf`: o ramo `answer` primeiro, depois o de `view_image` — só com imagens candidatas, o id restrito a elas
    (ADR-044, item 8) —, e um ramo por tool, na ordem do catálogo."""
    answer: dict[str, Any] = {
        "type": "object",
        "properties": {"action": {"const": "answer"}},
        "required": ["action"],
        "additionalProperties": False,
    }
    branches = [
        {
            "type": "object",
            "properties": {
                "action": {"const": "tool"},
                "name": {"const": tool.name},
                "arguments": sanitize(tool.parameters),
            },
            "required": ["action", "name", "arguments"],
            "additionalProperties": False,
        }
        for tool in tools
    ]
    view: list[dict[str, Any]] = []
    if images:
        view.append(
            {
                "type": "object",
                "properties": {"action": {"const": "view_image"}, "id": {"type": "string", "enum": list(images)}},
                "required": ["action", "id"],
                "additionalProperties": False,
            }
        )
    return {"anyOf": [answer, *view, *branches]}


def response_format(tools: Sequence[CatalogTool], images: Sequence[str] = ()) -> dict[str, Any]:
    """O `response_format` do papel `controller`. Sem `strict`: a rigidez por provider é da 006 (US4)."""
    return {"type": "json_schema", "json_schema": {"name": SCHEMA_NAME, "schema": action_schema(tools, images)}}


def catalog_text(tools: Sequence[CatalogTool]) -> str:
    """O catálogo para o texto de sistema do controller: uma linha por tool. O formato guia a gramática; o texto
    guia a escolha."""
    lines = ["Ferramentas disponíveis:"]
    for tool in tools:
        parameters = json.dumps(_plain(tool.parameters), ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        lines.append(f"- {tool.name}: {tool.description} Parâmetros: {parameters}")
    return "\n".join(lines)


# --- leitura ------------------------------------------------------------------------------------------------------


def parse_action(content: str | None, images: Sequence[str] = ()) -> Action:
    """Lê a saída do controller. Nunca levanta: o que não é ação vira `InvalidAction`, que conta como iteração.

    Nome fora do catálogo **não** é inválido — o gateway responde "tool inexistente" e o resultado volta ao
    controller (US2 cen. 4). O nome não é aparado: a comparação no gateway é exata. `view_image` só vale com um id
    entre as imagens candidatas: as imagens não são catálogo de ninguém, e o motor é quem as conhece.
    """
    if content is None or not content.strip():
        return InvalidAction(reason=EMPTY)
    try:
        data = json.loads(content)
    except (ValueError, RecursionError):
        return InvalidAction(reason=MALFORMED)
    if not isinstance(data, dict):
        return InvalidAction(reason=NOT_OBJECT)
    action = data.get("action")
    if action == "answer":
        return AnswerAction()
    if action == "view_image":
        image = data.get("id")
        return (
            ViewImageAction(id=image)
            if isinstance(image, str) and image in images
            else InvalidAction(reason=UNKNOWN_IMAGE)
        )
    if action != "tool":
        return InvalidAction(reason=UNKNOWN_ACTION)
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        return InvalidAction(reason=MISSING_NAME)
    arguments = data.get("arguments")
    if arguments is None:
        arguments = {}
    if not isinstance(arguments, dict):
        return InvalidAction(reason=BAD_ARGUMENTS)
    return ToolAction(name=name, arguments=MappingProxyType(arguments))
