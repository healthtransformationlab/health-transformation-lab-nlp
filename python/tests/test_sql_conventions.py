"""Spec 018 US1: every gold table declared in diagrams/_build/gold_model.py follows AGENTS.md "SQL and data names"."""
import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("gold_model", ROOT / "diagrams" / "_build" / "gold_model.py")
gm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gm)

GOLD = {n: t for n, t in gm.TABLES.items() if t.area != "file"}
TYPES = {"_id": {"bigint", "string"}, "_key": {"string"}, "_code": {"string"}, "_name": {"string"}, "_text": {"string"},
         "_date": {"date"}, "_ts": {"timestamp"}, "_count": {"bigint"}, "_ratio": {"double"}, "_pct": {"double"},
         "_rate": {"double"}, "_coef": {"double"}, "_seconds": {"double"}, "_usd": {"double"}, "_num": {"bigint"},
         "_url": {"string"}, "_sha256": {"string"}, "_sha": {"string"}, "_mm": {"double"}}


def kind(column):
    if column.startswith("is_"):
        return "is_"
    return next((s for s in TYPES if column.endswith(s)), None)


def test_gold_tables_are_lowercase_snake_case_and_singular():
    for name in GOLD:
        assert re.fullmatch(r"[a-z][a-z0-9_]*", name), name
        assert not name.endswith("s"), f"{name}: tables are singular"


def test_gold_tables_are_facts_dimensions_or_summaries_named_subject_then_noun():
    for name in GOLD:
        assert name.startswith(("fact_", "dim_", "kpi_")) or re.fullmatch(r"[a-z0-9]+_[a-z0-9_]+", name), name


def test_every_gold_column_ends_in_a_suffix_that_says_its_kind():
    for name, t in GOLD.items():
        for c in t.columns:
            assert re.fullmatch(r"[a-z][a-z0-9_]*", c.name), (name, c.name)
            assert kind(c.name), f"{name}.{c.name}: no kind suffix (AGENTS.md, SQL and data names)"


def test_each_columns_type_matches_its_suffix():
    for name, t in GOLD.items():
        for c in t.columns:
            k = kind(c.name)
            if k == "is_":
                assert c.type == "boolean", (name, c.name)
            elif k == "_count" and c.name.startswith("avg_"):
                assert c.type == "double", (name, c.name)          # an average of counts
            else:
                assert c.type in TYPES[k], (name, c.name, c.type)
