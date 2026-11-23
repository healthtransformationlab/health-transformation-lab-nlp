"""Unity Catalog table and column comments from the declarations (spec 034 US2, #534).

    declared(schema, table)  (table comment, {column: comment}) from diagrams/_build/gold_model.py (the gold tables)
                             and opendental_silver_model.py (silver, and bronze for its source tables); a table
                             comment only for the tables nothing declares (the OMOP tables, load_log)
    declared_tables()        every (schema, table) with a declared comment
    statements(table, cols)  COMMENT ON TABLE and ALTER TABLE ... ALTER COLUMN ... COMMENT for one table, for the
                             declared columns it has; given the comments in place, only those that differ (#741)
    apply(spark, table)      run the ones the table doesn't already hold, after a write; a failure warns and never
                             fails the job (a comment is documentation, not data: AGENTS.md, optional settings warn)
    with_comments(sdf, table)  the frame with each declared column's comment in its schema, for an overwrite to
                             commit with the data (#751); a refused comment then fails that write
    apply_all(spark, catalog)  every declared table that exists (Load results runs it after each deploy)

The writers save with saveAsTable, and an overwrite with overwriteSchema drops comments unless the frame carries them
(with_comments), so each write checks them and sends the missing ones again. Genie and Catalog Explorer read them.
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
GOLD_SCHEMA = {
    "fact_tooth_loss_prediction": "gold_opendental_perio",
    "dim_access_question": "gold_access_bench",   # spec 043
    "fact_access_answer": "gold_access_bench",
}   # every other gold_model table: gold_perio_bench
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
    ("ops_agent_trace", "trace_migration_check"): "One row per experiment and assessment name after a US3 migrate "
                                                   "or reload check (spec 041 #858). Delete-then-append by run_id.",
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
def statements(table: str, columns: list[str], *, table_comment: str | None = None,
               column_comments: dict | None = None) -> list[str]:
    """`table_comment` and `column_comments` ({column: comment or None}) are the comments already in place: a
    statement whose comment equals its declared text is left out (#741). Without them, every statement."""
    if not _NAME.fullmatch(table):
        raise ValueError(f"table {table!r}: catalog.schema.table, letters, digits and _ only")
    _, schema, name = table.split(".")
    comment, cols = declared(schema, name)
    if not comment:
        return []
    held = column_comments or {}
    out = [] if table_comment == comment else [f"COMMENT ON TABLE {table} IS {sql_string(comment)}"]
    out += [f"ALTER TABLE {table} ALTER COLUMN {c} COMMENT {sql_string(cols[c])}"
            for c in columns if c in cols and re.fullmatch(r"\w+", c) and held.get(c) != cols[c]]
    return out


def _table_comment(spark, table: str) -> str | None:
    """The comment Unity Catalog holds for the table; None when it can't be read, so the comment is sent again."""
    try:
        return spark.catalog.getTable(table).description
    except Exception:  # noqa: BLE001 - unreadable means send it, as before #741
        return None


@traced
def apply(spark, table: str) -> int:
    """Comment one table after a write, sending only the comments it doesn't already hold: sending all of them, one
    statement each, made Load results' sweep about 17 minutes a run (#741). Returns the statements that ran. Nothing
    here fails the write: a table that can't be read or commented gets a warning."""
    try:
        fields = list(spark.table(table).schema.fields)
    except Exception as e:  # noqa: BLE001 - a comment never fails the job
        print(f"warning: comment not applied on {table}: can't read its columns ({type(e).__name__})")
        return 0
    if not (_NAME.fullmatch(table) and declared(*table.split(".")[1:])[0]):
        print(f"warning: {table} has no declared comment (diagrams/_build/gold_model.py or table_comments.OTHER)")
        return 0
    held = {f.name: (getattr(f, "metadata", None) or {}).get("comment") for f in fields}
    todo = statements(table, list(held), table_comment=_table_comment(spark, table), column_comments=held)
    done = 0
    for s in todo:
        try:
            spark.sql(s)
            done += 1
        except Exception as e:  # noqa: BLE001 - a comment never fails the job; the warning names it
            print(f"warning: comment not applied on {table}: {type(e).__name__}: {str(e)[:200]}")
    return done


@traced
def with_comments(sdf, table: str):
    """`sdf` with each declared column's comment in its schema (metadata["comment"]), so an overwrite commits them and
    apply sends no column comment afterwards; the table's own may still be sent. Load results' overwrites from pandas
    dropped them, and 200 column comments were sent again on every run (#751). The comments are written with the data,
    so one the catalog refused would fail that write. Columns keep their names and order; an undeclared table's frame
    comes back as it is."""
    if not _NAME.fullmatch(table):
        return sdf
    comment, cols = declared(*table.split(".")[1:])
    if not comment:
        return sdf
    return sdf.select(*[sdf[c].alias(c, metadata={"comment": cols[c]}) if c in cols else sdf[c] for c in sdf.columns])


@traced
def apply_all(spark, catalog: str) -> int:
    """Comment every declared table that exists in the catalog. Returns the tables checked; the log also says how many
    statements went out, so a run shows whether the comments in place were read (#741)."""
    n = sent = 0
    for schema, name in declared_tables():
        table = f"{catalog}.{schema}.{name}"
        if spark.catalog.tableExists(table):
            sent += apply(spark, table)
            n += 1
    print(f"checked {n} tables in {catalog}, sent {sent} comment statements")
    return n
