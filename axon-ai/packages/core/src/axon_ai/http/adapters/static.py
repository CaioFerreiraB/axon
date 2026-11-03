"""O ECharts servido pela plataforma (FR-005c, ADR-052, item 6; research R62).

Os arquivos são vendorizados no pacote, numa versão fixa, e lidos uma vez, na montagem; o desenhista da plataforma
(`axon-chart.js`) vai num caminho com a impressão digital do conteúdo, para o cache imutável nunca servir uma versão
velha. As rotas são públicas: o script carrega dentro do iframe do Open WebUI, que não tem credencial nenhuma da
plataforma. O endereço absoluto e a integridade (`sha384`) de cada script vão para a página do gráfico.
"""

from __future__ import annotations

import base64
import hashlib
from pathlib import Path
from typing import Final

from fastapi import APIRouter
from fastapi.responses import Response

from axon_ai.http.domain.charts import ECHARTS_VERSION, ChartScripts, ScriptRef

STATIC_PREFIX: Final = "/static/echarts"
RENDERER_PREFIX: Final = "/static/charts"
STATIC_DIR: Final = Path(__file__).parent / "static"
ASSETS: Final = STATIC_DIR / "echarts" / ECHARTS_VERSION
ECHARTS_FILE: Final = "echarts.min.js"
LOCALE_FILE: Final = "langPT-br.js"
RENDERER_FILE: Final = "axon-chart.js"
_SERVED: Final = (ECHARTS_FILE, LOCALE_FILE, "LICENSE", "NOTICE")
_HEADERS: Final = {
    "Cache-Control": "public, max-age=31536000, immutable",
    # O iframe do gráfico tem origem `null`: o `integrity` exige CORS para conferir o script.
    "Access-Control-Allow-Origin": "*",
    "Cross-Origin-Resource-Policy": "cross-origin",
    "X-Content-Type-Options": "nosniff",
}


class ChartAssets:
    """Os arquivos do ECharts em memória, lidos uma vez."""

    def __init__(self, directory: Path = ASSETS, renderer: Path = STATIC_DIR / RENDERER_FILE) -> None:
        self.files = {name: (directory / name).read_bytes() for name in _SERVED}
        self.renderer = renderer.read_bytes()
        self.digest = hashlib.sha256(self.renderer).hexdigest()[:12]

    def scripts(self, base_url: str) -> ChartScripts:
        """Os scripts da página do gráfico, sob `base_url` (o endereço da plataforma que o navegador alcança)."""
        base = base_url.rstrip("/")
        root = f"{base}{STATIC_PREFIX}/{ECHARTS_VERSION}"
        return ChartScripts(
            echarts=ScriptRef(url=f"{root}/{ECHARTS_FILE}", integrity=integrity(self.files[ECHARTS_FILE])),
            locale=ScriptRef(url=f"{root}/{LOCALE_FILE}", integrity=integrity(self.files[LOCALE_FILE])),
            renderer=ScriptRef(
                url=f"{base}{RENDERER_PREFIX}/{self.digest}/{RENDERER_FILE}", integrity=integrity(self.renderer)
            ),
        )


def integrity(data: bytes) -> str:
    """O valor do atributo `integrity` (Subresource Integrity) de um arquivo."""
    return "sha384-" + base64.b64encode(hashlib.sha384(data).digest()).decode()


def static_router(assets: ChartAssets) -> APIRouter:
    router = APIRouter()

    @router.get(STATIC_PREFIX + "/{version}/{name}", include_in_schema=False)
    async def asset(version: str, name: str) -> Response:
        data = assets.files.get(name) if version == ECHARTS_VERSION else None
        if data is None:
            return Response(status_code=404, headers={"X-Content-Type-Options": "nosniff"})
        media_type = "text/javascript; charset=utf-8" if name.endswith(".js") else "text/plain; charset=utf-8"
        return Response(data, media_type=media_type, headers=_HEADERS)

    @router.get(RENDERER_PREFIX + "/{digest}/" + RENDERER_FILE, include_in_schema=False)
    async def renderer(digest: str) -> Response:
        if digest != assets.digest:
            return Response(status_code=404, headers={"X-Content-Type-Options": "nosniff"})
        return Response(assets.renderer, media_type="text/javascript; charset=utf-8", headers=_HEADERS)

    return router
