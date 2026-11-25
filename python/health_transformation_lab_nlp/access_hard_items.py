"""Hard AccessBench items for periodontal screening access pathways (issue #919).

No planted PHI in this set. Synthetic prompts only; forum URLs cite public posts.
"""

from __future__ import annotations

import json
from pathlib import Path

from .paths import REPO_ROOT
from .access_sections import validate_section
from .access_phi_items import validate_resources as api_validate_resources
from .telemetry import traced

ITEMS_PATH = REPO_ROOT / "benchmarks" / "access_bench" / "items" / "perio_screening_hard_items.jsonl"

REQUIRED = (
    "id", "domain", "persona", "prompt", "must_include", "red_flags",
    "evidence_source", "knowledge_cutoff_sensitive", "is_simulated",
    "source_thread_url", "screening_goal_tag",
)
GOAL_TAG = "perio_screening_2030"


@traced
def load_items(path: Path | None = None) -> list[dict]:
    """Load and validate every JSONL row; fails if any row breaks the contract."""
    p = path or ITEMS_PATH
    if not p.is_file():
        raise FileNotFoundError(f"missing AccessBench hard items: {p}")
    rows = []
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        row = json.loads(line)
        validate_item(row, where=f"{p.name}:{i}")
        rows.append(row)
    if not rows:
        raise ValueError(f"no items in {p}")
    return rows


@traced
def validate_item(row: dict, where: str = "item") -> None:
    missing = [k for k in REQUIRED if k not in row]
    if missing:
        raise ValueError(f"{where}: missing {missing}")
    if not str(row["id"]).startswith("ACC_"):
        raise ValueError(f"{where}: id must start with ACC_")
    validate_section(row, where)                   # oral, medical or mental (spec 044, ADR 0014)
    if row.get("is_simulated") is not True:
        raise ValueError(f"{where}: is_simulated must be true (synthetic only)")
    if row.get("screening_goal_tag") != GOAL_TAG:
        raise ValueError(f"{where}: screening_goal_tag must be {GOAL_TAG!r}")
    if not isinstance(row["must_include"], list) or not (3 <= len(row["must_include"]) <= 5):
        raise ValueError(f"{where}: must_include needs 3 to 5 criteria")
    if not isinstance(row["red_flags"], list) or not (1 <= len(row["red_flags"]) <= 3):
        raise ValueError(f"{where}: red_flags needs 1 to 3 entries")
    if not isinstance(row["knowledge_cutoff_sensitive"], bool):
        raise TypeError(f"{where}: knowledge_cutoff_sensitive must be a boolean")
    api_validate_resources(row.get("resources"), where)
    if not str(row["source_thread_url"]).startswith("http"):
        raise ValueError(f"{where}: source_thread_url must be an http(s) URL")
    if "planted_phi" in row:
        raise ValueError(f"{where}: planted_phi is not allowed on the hard screening set")
