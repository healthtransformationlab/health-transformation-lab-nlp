"""AccessBench oral section: dental discount, voucher and low-cost program questions (spec 044 US2, #939).

Every fact and resource in these items comes from an official or primary page opened when the item was written; the
check date is in `evidence_source`. The items are synthetic questions; no real person's details.
"""

from __future__ import annotations

import json
from pathlib import Path

from .access_phi_items import validate_resources, validate_source_fields
from .access_sections import validate_section
from .paths import REPO_ROOT
from .telemetry import traced

ITEMS_PATH = REPO_ROOT / "benchmarks" / "access_bench" / "items" / "discount_voucher_items.jsonl"
REQUIRED = ("id", "section_code", "domain", "persona", "prompt", "must_include", "red_flags", "resources",
            "evidence_source", "evidence_urls", "knowledge_cutoff_sensitive", "is_simulated", "source_thread_url")


@traced
def load_items(path: Path | None = None) -> list[dict]:
    """Load and validate every JSONL row; fails if any row breaks the contract."""
    p = path or ITEMS_PATH
    rows = []
    for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), start=1):
        if line.strip() and not line.lstrip().startswith("#"):
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
    if not str(row["id"]).startswith("ACC_DISC_"):
        raise ValueError(f"{where}: id must start with ACC_DISC_")
    validate_section(row, where)
    if row.get("is_simulated") is not True:
        raise ValueError(f"{where}: is_simulated must be true (synthetic only)")
    if not isinstance(row["must_include"], list) or not (3 <= len(row["must_include"]) <= 5):
        raise ValueError(f"{where}: must_include needs 3 to 5 criteria")
    if not isinstance(row["red_flags"], list) or not (1 <= len(row["red_flags"]) <= 3):
        raise ValueError(f"{where}: red_flags needs 1 to 3 entries")
    urls = row["evidence_urls"]
    if not isinstance(urls, list) or not urls or not all(str(u).startswith("https://") for u in urls):
        raise ValueError(f"{where}: evidence_urls needs at least one https:// link")
    if not str(row["source_thread_url"]).startswith("https://"):
        raise ValueError(f"{where}: source_thread_url must be an https:// link")
    if not isinstance(row["knowledge_cutoff_sensitive"], bool):
        raise TypeError(f"{where}: knowledge_cutoff_sensitive must be a boolean")
    validate_resources(row["resources"], where)
    validate_source_fields(row, where)             # spec 045 US4
