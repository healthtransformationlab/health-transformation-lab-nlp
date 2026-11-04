"""Unity Catalog table and column comments from the declarations (spec 034 US2, #534).

    declared(schema, table)  (table comment, {column: comment}) from diagrams/_build/gold_model.py (the gold tables)
                             and opendental_silver_model.py (silver, and bronze for its source tables); a table
                             comment only for the tables nothing declares (the OMOP tables, load_log)
    declared_tables()        every (schema, table) with a declared comment
    statements(table, cols)  COMMENT ON TABLE and ALTER TABLE ... ALTER COLUMN ... COMMENT for one table, for the
                             declared columns it has
    apply(spark, table)      run them after a write; a failure warns and never fails the job (a comment is
                             documentation, not data: AGENTS.md, optional settings warn)
    apply_all(spark, catalog)  every declared table that exists (Load results runs it after each deploy)

The writers save with saveAsTable, and an overwrite with overwriteSchema drops comments, so each write applies them
again. Genie and Catalog Explorer read them.
"""

from __future__ import annotations

import importlib.util
import re
import sys
from functools import lru_cache

from .paths import REPO_ROOT
from .telemetry import traced

_BUILD = REPO_ROOT / "diagrams" / "_build"
_NAME = re.compile(r"\w+(\.\w+){2}")
GOLD_SCHEMA = {"fact_tooth_loss_prediction": "gold_opendental_perio"}   # every other gold_model table: gold_perio_bench
NOT_TABLES = {"review_key"}                                             # declared in gold_model, but a file

# Tables nothing declares column by column: a table comment, so Catalog Explorer still says what they hold.
OTHER = {
    ("gold_perio_bench", "person"): "OMOP CDM person: one row per synthetic patient of the study build (seed 42), "
                                    "rewritten by the Benchmark job. Synthetic data only.",
    ("gold_perio_bench", "visit_occurrence"): "OMOP CDM visit_occurrence: one row per synthetic dental visit, "
                                              "rewritten by the Benchmark job. Synthetic data only.",
    ("gold_perio_bench", "measurement"): "OMOP CDM measurement: one row per synthetic periodontal measurement at a "
                                         "visit, rewritten by the Benchmark job. Synthetic data only.",
    ("gold_perio_bench", "note"): "OMOP CDM note: one row per synthetic dental chart note, rewritten by the "
                                  "Benchmark job. Synthetic data only.",
    ("silver_opendental_perio", "load_log"): "One row per table per Open Dental extract load: what was read and "
                                             "how many rows, appended by the Open Dental load job (spec 029).",
}


def _load(name: str):
    if name in sys.modules:
        return sys.modules[name]
    if str(_BUILD) not in sys.path:   # opendental_silver_model imports gold_model by name
        sys.path.insert(0, str(_BUILD))
    spec = importlib.util.spec_from_file_location(name, _BUILD / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def _text(s: str) -> str:
    return " ".join(str(s).replace("·", ",").split())


@lru_cache(maxsize=1)
def _all() -> dict:
    out = {}
    for name, t in _load("gold_model").TABLES.items():
        if name not in NOT_TABLES:
            out[(GOLD_SCHEMA.get(name, "gold_perio_bench"), name)] = (
                _text(t.description), {c.name: _text(c.description) for c in t.columns})
    for name, t in _load("opendental_silver_model").TABLES.items():
        cols = {c.name: _text(c.description) for c in t.columns}
        out[("silver_opendental_perio", name)] = (_text(t.description), cols)
        if t.area == "source":   # bronze holds the same source tables, as extracted, before types are enforced
            bronze = (f"Bronze: Open Dental {name} as extracted, before types are enforced. {_text(t.description)} "
                      f"(silver_opendental_perio.{name} is the typed copy). Synthetic data only.")
            out[("bronze_opendental_perio", name)] = (bronze, cols)
    for key, comment in OTHER.items():
        out[key] = (comment, {})
    return out


@traced
def declared(schema: str, table: str) -> tuple[str | None, dict]:
    return _all().get((schema, table), (None, {}))


@traced
def declared_tables() -> list[tuple[str, str]]:
    return sorted(_all())


@traced
def sql_string(text: str) -> str:
    """A Spark SQL string literal."""
    return "'" + text.replace("\\", "\\\\").replace("'", "\\'") + "'"


@traced
def statements(table: str, columns: list[str]) -> list[str]:
    if not _NAME.fullmatch(table):
        raise ValueError(f"table {table!r}: catalog.schema.table, letters, digits and _ only")
    _, schema, name = table.split(".")
    comment, cols = declared(schema, name)
    if not comment:
        return []
    out = [f"COMMENT ON TABLE {table} IS {sql_string(comment)}"]
    out += [f"ALTER TABLE {table} ALTER COLUMN {c} COMMENT {sql_string(cols[c])}"
            for c in columns if c in cols and re.fullmatch(r"\w+", c)]
    return out


@traced
def apply(spark, table: str) -> int:
    """Comment one table after a write. Returns the statements that ran. Nothing here fails the write: a table
    that can't be read or commented gets a warning."""
    try:
        columns = list(spark.table(table).columns)
    except Exception as e:  # noqa: BLE001 - a comment never fails the job
        print(f"warning: comment not applied on {table}: can't read its columns ({type(e).__name__})")
        return 0
    todo = statements(table, columns)
    if not todo:
        print(f"warning: {table} has no declared comment (diagrams/_build/gold_model.py or table_comments.OTHER)")
        return 0
    done = 0
    for s in todo:
        try:
            spark.sql(s)
            done += 1
        except Exception as e:  # noqa: BLE001 - a comment never fails the job; the warning names it
            print(f"warning: comment not applied on {table}: {type(e).__name__}: {str(e)[:200]}")
    return done


@traced
def apply_all(spark, catalog: str) -> int:
    """Comment every declared table that exists in the catalog. Returns the tables commented."""
    n = 0
    for schema, name in declared_tables():
        table = f"{catalog}.{schema}.{name}"
        if spark.catalog.tableExists(table):
            apply(spark, table)
            n += 1
    print(f"commented {n} tables in {catalog}")
    return n
