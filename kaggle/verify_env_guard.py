"""Refuse a resolve count when the grading environment is missing a module (#883).

A verdict whose error or output_tail contains ``No module named`` is an environment
fault when that module is part of the grader (``pytest``) or the reference patch
cannot import it either. A module only the agent's patch fails to import, while
the reference patch imports it, is an ordinary failed patch.
"""
from __future__ import annotations

import re

MISSING_MODULE_MARK = "No module named"
# Modules the grader itself must have. A task's own package is not in this set:
# the reference patch is what decides whether that import is the environment.
GRADER_MODULES = frozenset({"pytest"})
_MODULE = re.compile(r"No module named ['\"]([^'\"]+)['\"]")


class MissingModuleError(RuntimeError):
    """The grading environment lacked a module; the resolve count is not a result."""


def module_names(row: dict | None) -> list[str]:
    """Module names in one verdict's error and output, in the order they appear."""
    if not row:
        return []
    parts = (row.get("error") or "", row.get("output_tail") or "")
    blob = "\n".join(part for part in parts if part)
    return _MODULE.findall(blob)


def missing_module_instance_ids(rows: list[dict]) -> list[str]:
    """Instance ids whose verdict text shows a missing module, in input order."""
    hits: list[str] = []
    for row in rows:
        parts = (row.get("error") or "", row.get("output_tail") or "")
        blob = "\n".join(part for part in parts if part)
        if MISSING_MODULE_MARK in blob:
            hits.append(str(row.get("instance_id") or "?"))
    return hits


def environment_faults(rows: list[dict], oracle_by_id: dict) -> list[tuple[str, str]]:
    """``(instance_id, module)`` pairs that are the grader's fault, in input order.

    ``pytest`` is always a fault. Any other module is a fault only when the
    reference verdict for that task fails to import it too. A reference verdict
    that does not mention the module clears it: the agent patch is what failed.
    """
    faults: list[tuple[str, str]] = []
    for row in rows:
        iid = str(row.get("instance_id") or "?")
        oracle = oracle_by_id.get(iid)
        oracle_mods = set(module_names(oracle))
        oracle_tops = {name.split(".")[0] for name in oracle_mods}
        for mod in module_names(row):
            top = mod.split(".")[0]
            if top in GRADER_MODULES or mod in oracle_mods or top in oracle_tops:
                faults.append((iid, mod))
    return faults


def assert_no_missing_modules(rows: list[dict], oracle_by_id: dict | None = None) -> None:
    """Raise MissingModuleError naming every environment fault.

    With no reference verdicts, every ``No module named`` is a fault. That is the
    reference patch's own grade. With reference verdicts, a module the reference
    can import is an ordinary failure and is not raised.
    """
    if oracle_by_id is None:
        hits = missing_module_instance_ids(rows)
        described = ", ".join(hits)
        count = len(hits)
    else:
        faults = environment_faults(rows, oracle_by_id)
        described = ", ".join(f"{iid} ({mod})" for iid, mod in faults)
        count = len(faults)
        hits = faults
    if not hits:
        return
    raise MissingModuleError(
        "grading environment is broken (missing module); not an ordinary failure. "
        f"Affected tasks ({count}): {described}. "
        "Install the missing packages (or fix the sandbox) and re-run; "
        "do not use the resolve count from this run."
    )
