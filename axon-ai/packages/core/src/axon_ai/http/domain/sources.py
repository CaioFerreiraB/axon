"""As citações como fontes do Open WebUI v0.12 (FR-005b, ADR-051): puro.

Uma fonte por citação, na ordem do `[n]`. O Open WebUI numera as fontes por `metadata.source`, sem repetir — por isso o
id é o `chunk_id`, nunca a URL: duas citações do mesmo PDF são duas fontes. O nome (`metadata.name`) é o que o chip do
`[n]` e a lista "N Fontes" mostram; o clique abre o modal, que liga o nome a `source.url` e mostra `document` e
`metadata.page + 1`. Sem `embed_url`: o painel lateral do Open WebUI é um iframe com `sandbox`, onde o Chrome não mostra
PDF.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any, Final
from urllib.parse import urlsplit

from axon_ai.graph.api import SourceRef
from axon_ai.http.domain.timeline import reference

SOURCE_EVENT: Final = "source"
WEB_SCHEMES: Final = frozenset({"http", "https"})


def source_events(citations: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Os eventos `source`, um por citação com `chunk_id`, na ordem recebida (a do `[n]`)."""
    return [_event(citation) for citation in citations if _text(citation.get("chunk_id"))]


def _event(citation: Mapping[str, Any]) -> dict[str, Any]:
    chunk_id = str(citation["chunk_id"])
    page = citation.get("page")
    page = page if isinstance(page, int) and not isinstance(page, bool) and page >= 1 else None
    name = caption(citation, page)
    source: dict[str, Any] = {"id": chunk_id, "name": name}
    url = web_url(citation.get("url"))
    if url is not None:
        source["url"] = url
    metadata: dict[str, Any] = {"source": chunk_id, "name": name}
    if page is not None:
        metadata["page"] = page - 1  # o Open WebUI mostra `page + 1`
    return {
        "type": SOURCE_EVENT,
        "data": {"source": source, "document": [details(citation, page)], "metadata": [metadata]},
    }


def caption(citation: Mapping[str, Any], page: int | None) -> str:
    """A legenda no formato das referências do trecho (ADR-026): `Documento — seção, p. N`."""
    document = _text(citation.get("document")) or str(citation["chunk_id"])
    return reference(SourceRef(document=document, section=_text(citation.get("section")), page=page))


def details(citation: Mapping[str, Any], page: int | None) -> str:
    """O conteúdo do modal da fonte: a proveniência inteira, uma linha por campo presente. Nunca vazio — o Open WebUI
    descarta a fonte sem documento."""
    lines = [f"Documento: {_text(citation.get('document')) or citation['chunk_id']}"]
    for label, key in (("Versão", "version"), ("Situação", "status"), ("Seção", "section")):
        value = _text(citation.get(key))
        if value:
            lines.append(f"{label}: {value}")
    if page is not None:
        lines.append(f"Página: {page}")
    return "\n\n".join(lines)


def web_url(value: object) -> str | None:
    """Só `http` ou `https` com host: o link vai à interface do usuário, e um esquema como `javascript:` não pode
    chegar a um `href`."""
    text = _text(value)
    if text is None:
        return None
    try:
        parts = urlsplit(text)
    except ValueError:
        return None
    return text if parts.scheme.lower() in WEB_SCHEMES and parts.netloc else None


def _text(value: object) -> str | None:
    return value.strip() if isinstance(value, str) and value.strip() else None
