"""Refuse a resolve count when the grading environment is missing a module (#883).

A verdict whose error or output_tail contains ``No module named`` is an environment fault.
Counting it as an ordinary unresolved task produces a believable wrong number.
"""
from __future__ import annotations

MISSING_MODULE_MARK = "No module named"


class MissingModuleError(RuntimeError):
    """The grading environment lacked a module; the resolve count is not a result."""


def missing_module_instance_ids(rows: list[dict]) -> list[str]:
    """Instance ids whose verdict text shows a missing module, in input order."""
    hits: list[str] = []
    for row in rows:
        blob = "\n".join(part for part in (row.get("error") or "", row.get("output_tail") or "") if part)
        if MISSING_MODULE_MARK in blob:
            hits.append(str(row.get("instance_id") or "?"))
    return hits


def assert_no_missing_modules(rows: list[dict]) -> None:
    """Raise MissingModuleError naming every hit; do not treat them as ordinary failures."""
    hits = missing_module_instance_ids(rows)
    if not hits:
        return
    raise MissingModuleError(
        "grading environment is broken (missing module); not an ordinary failure. "
        f"Affected tasks ({len(hits)}): {', '.join(hits)}. "
        "Install the missing packages (or fix the sandbox) and re-run; "
        "do not use the resolve count from this run."
    )
