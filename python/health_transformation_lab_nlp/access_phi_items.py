"""AccessBench items with planted synthetic PHI for dual scoring (pathway + leak gate).

Items live under benchmarks/access_bench/items/ as JSONL. Every planted identifier is
invented (challenge-pool names, reserved example phones/emails, SSNs starting with 9).
Real PHI must never appear here.
"""

from __future__ import annotations

import json
from pathlib import Path

from .paths import REPO_ROOT
from .telemetry import traced

ITEMS_PATH = REPO_ROOT / "benchmarks" / "access_bench" / "items" / "simulated_access_phi_items.jsonl"

REQUIRED = ("id", "domain", "persona", "prompt", "must_include", "red_flags",
            "evidence_source", "knowledge_cutoff_sensitive", "planted_phi", "is_simulated")


@traced
def load_items(path: Path | None = None) -> list[dict]:
    """Load and validate every JSONL row; fails if any row breaks the contract."""
    p = path or ITEMS_PATH
    if not p.is_file():
        raise FileNotFoundError(f"missing AccessBench PHI items: {p}")
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
    if row.get("is_simulated") is not True:
        raise ValueError(f"{where}: is_simulated must be true (synthetic only)")
    if not isinstance(row["must_include"], list) or not (3 <= len(row["must_include"]) <= 5):
        raise ValueError(f"{where}: must_include needs 3 to 5 criteria")
    if not isinstance(row["red_flags"], list) or not (1 <= len(row["red_flags"]) <= 3):
        raise ValueError(f"{where}: red_flags needs 1 to 3 entries")
    if not isinstance(row["planted_phi"], list) or len(row["planted_phi"]) < 2:
        raise ValueError(f"{where}: planted_phi needs at least 2 identifiers")
    if not isinstance(row["knowledge_cutoff_sensitive"], bool):
        raise TypeError(f"{where}: knowledge_cutoff_sensitive must be a boolean")
    prompt = row["prompt"]
    for p in row["planted_phi"]:
        text = p.get("text")
        if not text or "type" not in p:
            raise ValueError(f"{where}: planted_phi entries need text and type")
        if text not in prompt:
            raise ValueError(f"{where}: planted {text!r} not in prompt")


@traced
def known_phi_for_leak_check(row: dict) -> list[dict]:
    """Shape expected by deid.leak_check: [{'text': ...}, ...]."""
    return [{"text": p["text"]} for p in row["planted_phi"]]
