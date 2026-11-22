"""Spec 041 US4 (#859): SQL views over coding-agent UC traces name our grain and columns.

The views live in databricks/setup/agent_trace_views.sql and are applied once per workspace (like
billing_views.sql). This test holds the file to the issue contract and AGENTS.md SQL naming rules.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SQL = ROOT / "databricks/setup/agent_trace_views.sql"

# Issue #859 Contract
TASK_RUN_COLUMNS = (
    "trace_id",
    "run_label",
    "agent_name",
    "instance_id",
    "repo_name",
    "is_resolved",
    "outcome_code",
    "ended_code",
    "task_start_ts",
    "task_seconds",
    "tool_call_count",
    "input_token_count",
    "output_token_count",
)
TOOL_CALL_COLUMNS = (
    "trace_id",
    "span_id",
    "run_label",
    "agent_name",
    "instance_id",
    "step_num",
    "tool_name",
    "call_start_ts",
    "call_seconds",
    "is_error",
)

SUFFIX_OR_IS = re.compile(
    r"^(is_[a-z0-9_]+|"
    r".*(_id|_key|_code|_name|_text|_date|_ts|_count|_ratio|_pct|_rate|_coef|"
    r"_seconds|_hours|_days|_dbu|_usd|_num|_url|_sha256|_sha|_mm))$"
)
# Contract mirrors US2 trace tags and Databricks ids; those names are fixed in the issue, not renamed here.
CONTRACT_TAG_OR_ID = {
    "trace_id", "span_id", "run_label", "agent_name", "instance_id", "repo_name", "step_num", "tool_name",
}


def _sql() -> str:
    assert SQL.is_file(), f"missing {SQL.relative_to(ROOT)}"
    return SQL.read_text()


def _view_block(name: str) -> str:
    """The create-or-replace view statement for `name`, including its comment."""
    text = _sql()
    pattern = re.compile(
        rf"create\s+or\s+replace\s+view\s+[\w.]+\.{name}\b(.*?)(?=create\s+or\s+replace\s+view\b|\Z)",
        re.IGNORECASE | re.DOTALL,
    )
    m = pattern.search(text)
    assert m, f"no create or replace view ….{name} in {SQL.name}"
    return m.group(0)


def _outer_select_list(block: str) -> str:
    """Text of the outer SELECT's column list (between SELECT and its FROM)."""
    # CTE views: ") <select … from>"; plain: "as <select … from>". Prefer the last SELECT…FROM pair.
    matches = list(re.finditer(
        r"(?is)\bselect\b(.*?)\bfrom\b",
        block,
    ))
    assert matches, "view has no SELECT … FROM"
    return matches[-1].group(1)


def _select_aliases(block: str) -> list[str]:
    """Outer SELECT column aliases (each output column ends with AS name)."""
    aliases = []
    for line in _outer_select_list(block).splitlines():
        line = re.sub(r"--.*$", "", line).strip().rstrip(",")
        if not line:
            continue
        as_m = re.search(r"(?i)\bas\s+([a-z][a-z0-9_]*)$", line)
        assert as_m, f"outer SELECT line must end with AS alias: {line!r}"
        aliases.append(as_m.group(1))
    return aliases


def _comment(block: str) -> str:
    m = re.search(r"(?i)\bcomment\s+'([^']*)'", block)
    assert m, "view has no COMMENT"
    return m.group(1)


def test_agent_task_run_columns_match_the_contract():
    cols = _select_aliases(_view_block("agent_task_run"))
    assert cols == list(TASK_RUN_COLUMNS), cols


def test_agent_tool_call_columns_match_the_contract():
    cols = _select_aliases(_view_block("agent_tool_call"))
    assert cols == list(TOOL_CALL_COLUMNS), cols


def test_each_view_comment_states_its_grain():
    task = _comment(_view_block("agent_task_run")).lower()
    tool = _comment(_view_block("agent_tool_call")).lower()
    assert "one row per" in task and "task" in task
    assert "one row per" in tool and "tool" in tool


def test_view_names_are_singular_snake_case():
    text = _sql().lower()
    assert "agent_task_run" in text and "agent_tool_call" in text
    assert "agent_task_runs" not in text and "agent_tool_calls" not in text


def test_typed_columns_follow_sql_naming_suffixes():
    for col in TASK_RUN_COLUMNS + TOOL_CALL_COLUMNS:
        if col in CONTRACT_TAG_OR_ID:
            continue
        assert SUFFIX_OR_IS.match(col), f"{col}: needs a typed suffix or is_ prefix (AGENTS.md)"


def test_views_read_the_coding_agent_uc_tables_not_write_them():
    text = _sql().lower()
    assert "coding_agent_trace_metadata" in text
    assert "coding_agent_otel_spans" in text
    assert "insert into" not in text and "merge into" not in text
    assert "ops_agent_trace" in text
