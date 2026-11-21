"""042 AI1 (#875): --rerun deps are a declared pyproject extra, named in the script docstring."""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PYPROJECT = ROOT / "python" / "pyproject.toml"
SCRIPT = ROOT / "python" / "scripts" / "76_deid_drivers.py"
SPACY_WHEEL = (
    "https://github.com/explosion/spacy-models/releases/download/"
    "en_core_web_lg-3.8.0/en_core_web_lg-3.8.0-py3-none-any.whl"
)


def _extras() -> dict:
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    return data["project"]["optional-dependencies"]


def test_deid_extra_declares_presidio_torch_transformers_and_spacy_wheel():
    extras = _extras()
    assert "deid" in extras, "add a deid optional-extra for scripts/76_deid_drivers.py --rerun"
    joined = "\n".join(extras["deid"])
    assert "presidio-analyzer" in joined
    assert re.search(r"(^|\n)torch", joined) or "torch>" in joined or "torch=" in joined
    assert "transformers" in joined
    assert SPACY_WHEEL in joined


def test_76_deid_drivers_docstring_names_the_deid_extra():
    doc = SCRIPT.read_text(encoding="utf-8")
    assert 'pip install -e ".[deid]"' in doc or "pip install -e '.[deid]'" in doc
