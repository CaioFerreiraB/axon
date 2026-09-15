"""Ambiente limpo (SC-001, US1): contratos + pack de teste resolvem só três distribuições, e os testes do pack passam.

Uso, a partir de `ai-core/`: `uv run python packages/contracts/tools/check_clean_env.py [--python 3.14]`.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
import tempfile
from pathlib import Path

CONTRACTS_DIR = Path(__file__).resolve().parents[1]
PACK_DIR = CONTRACTS_DIR / "tests" / "fixtures" / "contract_test_pack"
EXPECTED = {"ai-core-contracts", "typing-extensions", "contract-test-pack"}


def _normalize(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _run(command: list[str], *, capture: bool = False, cwd: Path | None = None) -> str:
    completed = subprocess.run(command, check=True, text=True, capture_output=capture, cwd=cwd)
    return completed.stdout if capture else ""


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--python", default="3.14", help="versão de Python do ambiente limpo")
    args = parser.parse_args(argv)

    with tempfile.TemporaryDirectory(prefix="contracts-clean-env-") as tmp:
        venv = Path(tmp) / "venv"
        python = venv / "bin" / "python"
        _run(["uv", "venv", "--quiet", "--python", args.python, str(venv)])
        _run(["uv", "pip", "install", "--quiet", "--python", str(python), str(CONTRACTS_DIR), str(PACK_DIR)])
        frozen = _run(["uv", "pip", "freeze", "--python", str(python)], capture=True)
        installed = {_normalize(re.split(r"==| @ ", line, maxsplit=1)[0]) for line in frozen.splitlines() if line}
        if installed != EXPECTED:
            print(f"ambiente limpo com distribuições inesperadas: {sorted(installed ^ EXPECTED)}", file=sys.stderr)
            print(frozen, file=sys.stderr)
            return 1
        print(f"resolução do pack: {', '.join(sorted(installed))}")
        _run(["uv", "pip", "install", "--quiet", "--python", str(python), "pytest"])
        return subprocess.call([str(python), "-m", "pytest", "-q", "-p", "no:cacheprovider", "tests"], cwd=PACK_DIR)


if __name__ == "__main__":
    sys.exit(main())
