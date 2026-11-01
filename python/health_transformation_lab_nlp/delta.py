"""Idempotent Delta writes from notebooks: delete-then-append by batch key (AGENTS.md, docs/operations.md).

    replace_batch(spark, rows, "health_transformation_lab.gold_perio_bench.fact_prediction",
                  {"source_code": "databricks", "run_id": run_id, "method_name": method})

A retry of the same batch replaces its rows instead of adding them again. Rows carry the key columns, so a bad
batch can be found and removed. Rows written by other writers are untouched: their key columns are NULL or
differ (Load results keys on file_sha256 and leaves source_code = databricks rows alone).

    replace_keys(spark, rows, table, "run_id", schema=ddl)

For a writer that reads overlapping windows (the pipeline doctor, spec 027): the rows of every run_id in the
batch are deleted, then the batch appended, whichever earlier writer run wrote them.
"""

from __future__ import annotations

import re

import pandas as pd

from .telemetry import traced

_SAFE = re.compile(r"[\w.:+@/-]+")


@traced
def replace_batch(spark, rows: pd.DataFrame, table: str, key: dict) -> int:
    """Delete table's rows with these key values, then append rows (with the key columns set). New columns are
    added (mergeSchema); a column that is empty in this batch takes the table's type, or string in a new table
    (an all-null `error` would otherwise read as a number). Returns the rows written."""
    for k, v in key.items():
        if not re.fullmatch(r"\w+", k) or not _SAFE.fullmatch(str(v)):
            raise ValueError(f"batch key {k}={v!r}: letters, digits and . : + @ / - _ only")
    rows = rows.assign(**{k: str(v) for k, v in key.items()})
    empty = [c for c in rows.columns if rows[c].isna().all()]
    sdf = spark.createDataFrame(rows.astype({c: "string" for c in empty}))
    if spark.catalog.tableExists(table):
        schema = spark.table(table).schema
        if set(key) <= set(schema.fieldNames()):        # a table without the key columns has no rows of this batch
            where = " AND ".join(f"{k} = '{v}'" for k, v in key.items())
            spark.sql(f"DELETE FROM {table} WHERE {where}")
        for field in schema.fields:
            if field.name in empty:
                sdf = sdf.withColumn(field.name, sdf[field.name].cast(field.dataType))
    sdf.write.mode("append").option("mergeSchema", "true").saveAsTable(table)
    return len(rows)


@traced
def replace_keys(spark, rows: pd.DataFrame, table: str, column: str, schema: str | None = None) -> int:
    """Delete table's rows whose `column` holds any value in rows[column], then append rows. For a writer that
    re-reads overlapping windows (the pipeline doctor reads the last days of job runs each time): a run read
    twice replaces its rows, whichever writer run read it first. `schema` (Spark DDL) fixes the column types,
    so an all-null column in one batch never sets the wrong type. Returns the rows written."""
    if not re.fullmatch(r"\w+", column):
        raise ValueError(f"key column {column!r}: letters, digits and _ only")
    if not len(rows):
        return 0
    values = sorted({str(v) for v in rows[column]})
    bad = [v for v in values if not _SAFE.fullmatch(v)]
    if bad:
        raise ValueError(f"key {column}={bad[0]!r}: letters, digits and . : + @ / - _ only")
    sdf = spark.createDataFrame(rows, schema) if schema else spark.createDataFrame(rows)
    if spark.catalog.tableExists(table) and column in spark.table(table).schema.fieldNames():
        listed = ", ".join(f"'{v}'" for v in values)
        spark.sql(f"DELETE FROM {table} WHERE {column} IN ({listed})")
    sdf.write.mode("append").option("mergeSchema", "true").saveAsTable(table)
    return len(rows)
