"""Fábricas dos testes da 011: etapas de teste, configuração em memória e arquivos de exemplo."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Final

from ai_core.bootstrap.lifecycle import BootContext, Stage
from ai_core.bootstrap.settings import TEST_PROFILE, Settings

ASSISTANT: Final = "geral"
MODEL: Final = "qwen3:1.7b"
MODEL_ID: Final = f"{ASSISTANT}/{MODEL}"

PACKS_YAML: Final = """
packs:
  generic:
    enabled: true
"""

PACKS_YAML_COM_QUEBRADO: Final = """
packs:
  generic:
    enabled: true
  inexistente:
    enabled: true
"""

ASSISTANTS_YAML: Final = f"""
assistants:
  {ASSISTANT}:
    flow: chat
    packs: [generic]
    models:
      generation: ollama/{MODEL}
    allow: ["ollama/*"]
"""

ASSISTANTS_YAML_SEM_PACK: Final = f"""
assistants:
  {ASSISTANT}:
    packs: [generic]
    models:
      generation: ollama/{MODEL}
  orfao:
    packs: [inexistente]
    models:
      generation: ollama/{MODEL}
"""


class Recorder:
    """Guarda a ordem em que as etapas rodaram e em que os recursos foram liberados."""

    def __init__(self) -> None:
        self.ran: list[str] = []
        self.closed: list[str] = []

    def stage(self, name: str, *, critical: bool = True, fails: Exception | None = None) -> Stage:
        def run(ctx: BootContext) -> None:
            self.ran.append(name)
            ctx.on_close(lambda: self.closed.append(name))
            if fails is not None:
                raise fails

        return Stage(name=name, run=run, critical=critical)

    def degrading_stage(self, name: str, detail: str) -> Stage:
        """Etapa que conclui, mas relata degradação — é o caso de um pack em erro."""

        def run(ctx: BootContext) -> None:
            self.ran.append(name)
            ctx.parts[f"{name}:degraded"] = detail

        return Stage(name=name, run=run, critical=False)


class MemoryConfig:
    """Adapter em memória da porta `ConfigSource`."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or Settings(profile=TEST_PROFILE)

    def load(self) -> Settings:
        return self._settings


def write_config(tmp_path: Path, *, packs: str = PACKS_YAML, assistants: str = ASSISTANTS_YAML) -> Settings:
    """Escreve os dois arquivos e devolve a configuração que os aponta."""
    packs_file = tmp_path / "packs.yaml"
    assistants_file = tmp_path / "assistants.yaml"
    packs_file.write_text(packs, encoding="utf-8")
    assistants_file.write_text(assistants, encoding="utf-8")
    return Settings(profile=TEST_PROFILE, packs_file=packs_file, assistants_file=assistants_file)


def body(**overrides: Any) -> dict[str, Any]:
    base: dict[str, Any] = {
        "model": MODEL_ID,
        "messages": [{"role": "user", "content": "qual é a capital?"}],
    }
    return base | overrides


class FakeServer:
    """Servidor injetado no comando: registra a chamada em vez de abrir porta."""

    def __init__(self) -> None:
        self.calls: list[tuple[Any, str, int, float]] = []

    def __call__(self, app: Any, host: str, port: int, grace: float) -> None:
        self.calls.append((app, host, port, grace))


def names(stages: Sequence[Any]) -> list[str]:
    return [stage.name for stage in stages]


Factory = Callable[[Settings], Any]
