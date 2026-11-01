# Databricks notebook source
# MAGIC %md
# MAGIC # Migrate gold names (spec 018)
# MAGIC
# MAGIC The gold tables were renamed to the SQL conventions (AGENTS.md, "SQL and data names"): `ai_predictions` is now
# MAGIC `fact_prediction`, `gate_ok` is `is_gate_ok`, and so on (`health_transformation_lab_nlp.gold_names`). This copies each old
# MAGIC table that still exists to its new name, columns renamed, so the MedGemma reader's Databricks rows and the
# MAGIC judge's earlier calls are kept. It runs before Load results. If a job already wrote the new table, the old rows
# MAGIC it lacks are added (by batch key), so running it again adds nothing. An old `judgments` table goes to
# MAGIC `fact_judge_call` or, if the corpus judge wrote it, `fact_corpus_judge_call`. What to do with each table is
# MAGIC `gold_names.migration_plan`. Old tables are not dropped: it prints the `DROP TABLE` statements.
# MAGIC
# MAGIC Then the old gold schemas in `legacy_gold_schemas` (issue #228): specs 021 and 022 rebuilt gold in a new
# MAGIC catalog and schema from committed files, which can't bring back rows only Databricks wrote (the MedGemma
# MAGIC reader's). Each batch-keyed table's rows the current one lacks are added (`gold_names.legacy_plan`), every
# MAGIC old key is checked to have arrived, and `DROP TABLE` is printed only for the tables that pass. A summary
# MAGIC table its own job rebuilds is reported as stale, with no `DROP`: compare it by hand first.
# MAGIC Synthetic data only. Serverless CPU.

# COMMAND ----------

# MAGIC %pip install -q -e ../../python

# COMMAND ----------

dbutils.library.restartPython()  # noqa: F821

# COMMAND ----------

from health_transformation_lab_nlp import gold_names, tracking
from pyspark.sql import functions as F

dbutils.widgets.text("git_commit", "")  # noqa: F821  set by the job: the commit it was deployed from
tracking.use_git_commit(dbutils)  # noqa: F821
dbutils.widgets.text("catalog", "health_transformation_lab")  # noqa: F821
dbutils.widgets.text("schema", "gold_perio_bench")  # noqa: F821
dbutils.widgets.text("legacy_gold_schemas", "")  # noqa: F821  set by the job: catalog.schema, comma-separated
catalog, schema = dbutils.widgets.get("catalog"), dbutils.widgets.get("schema")  # noqa: F821
legacy = gold_names.legacy_schemas(dbutils.widgets.get("legacy_gold_schemas"))  # noqa: F821  malformed: fails here
if not legacy:
    print("legacy_gold_schemas is empty: no old gold schemas are read (the job sets it; databricks.yml)")


def table(name: str, where: str = "") -> str:
    return f"{where or f'{catalog}.{schema}'}.{name}"


def renamed(old: str, new: str, where: str = ""):
    """The old table (in schema where, default the current one) under new's column names, _count columns as
    bigint. A value the cast can't keep fails instead of turning into null."""
    names = gold_names.TABLES[new]
    sdf = spark.table(table(old, where))  # noqa: F821
    sdf = sdf.withColumnsRenamed({c: names[c] for c in sdf.columns if c in names})
    counts = [c for c in sdf.columns if c.endswith("_count") and not c.startswith("avg_")]
    if counts:
        nulls = sdf.select([F.count(F.when(F.col(c).isNull(), 1)).alias(c) for c in counts]).first()
        cast = sdf.select([F.col(c).cast("bigint") for c in counts])
        after = cast.select([F.count(F.when(F.col(c).isNull(), 1)).alias(c) for c in counts]).first()
        bad = [c for c in counts if after[c] != nulls[c]]
        if bad:
            raise ValueError(f"{old}: {bad} hold values that aren't whole numbers; fix them before migrating")
        for c in counts:
            sdf = sdf.withColumn(c, F.col(c).cast("bigint"))
    # an old table written from text (benchmark_results.timestamp, ISO 8601) gets a real timestamp (spec 031)
    for c in [f.name for f in sdf.schema.fields if f.name.endswith("_ts") and f.dataType.typeName() == "string"]:
        sdf = sdf.withColumn(c, F.to_timestamp(c))
    return sdf


def rows(name: str) -> int:
    return spark.table(table(name)).count()  # noqa: F821


def keyed(src, new: str):
    """(src with every MERGE_KEYS column, the current table new's distinct keys, the join condition). A key column
    a side lacks (the reader's run_id, in neither fact_llm_call: issue #248) counts as null on that side, typed by
    gold_names.merge_key_types; null matches null, so it never adds or splits rows."""
    current = spark.table(table(new))  # noqa: F821
    key = gold_names.MERGE_KEYS[new]
    types = gold_names.merge_key_types(key, dict(src.dtypes), dict(current.dtypes))
    null = {k: F.lit(None).cast(types[k]).alias(k) for k in key}
    left = src.select(*src.columns, *[null[k] for k in key if k not in src.columns])
    have = current.select(*[current[k] if k in current.columns else null[k] for k in key]).distinct()
    return left, have, [left[k].eqNullSafe(have[k]) for k in key]


def merge_missing(src, new: str) -> None:
    """Append src's rows whose MERGE_KEYS the current table new lacks, with src's own columns only (a stand-in key
    column is never written); mergeSchema adds a column of src's that new doesn't have yet."""
    left, have, cond = keyed(src, new)
    (left.join(have, cond, "left_anti").select(*src.columns)
     .write.mode("append").option("mergeSchema", "true").saveAsTable(table(new)))


def not_carried(src, new: str) -> int:
    """src's rows whose MERGE_KEYS are still missing from the current table new."""
    left, have, cond = keyed(src, new)
    return left.join(have, cond, "left_anti").count()


# Which old tables exist, with their columns; the decision is gold_names.migration_plan (tested).
existing = {t.name: spark.table(table(t.name)).columns  # noqa: F821
            for t in spark.catalog.listTables(f"{catalog}.{schema}")  # noqa: F821
            if t.name in gold_names.RENAMED or t.name in gold_names.TABLES}
plan = gold_names.migration_plan(existing)
failed = [f"{old}: no gold name for column(s) {cols}" for action, old, cols in plan if action == "fail"]
if failed:
    raise ValueError("add them to health_transformation_lab_nlp/gold_names.py first: " + "; ".join(failed))

for action, old, new in plan:
    if action == "copy":
        renamed(old, new).write.mode("overwrite").saveAsTable(table(new))
        if rows(new) != rows(old):
            raise RuntimeError(f"{old} -> {new}: row counts differ ({rows(old)} vs {rows(new)})")
    elif action == "rewrite":       # same name, old columns: Delta overwrites from the snapshot it read
        n = rows(old)
        renamed(old, new).write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(table(new))
        if rows(new) != n:
            raise RuntimeError(f"{old}: row counts differ after renaming its columns ({n} vs {rows(new)})")
    elif action == "merge":         # a job wrote the new table first: add the old rows whose batch key it lacks
        merge_missing(renamed(old, new), new)
    print(f"{action}: {old} -> {new}" + ("" if action != "stale" else " (the new table is rebuilt each run; old copy left)"))

drops = [f"DROP TABLE {table(old)};" for _, old, new in plan if old != new]
print("migrated:", "nothing to do" if not plan else len(plan))

# COMMAND ----------

# The old gold schemas (issue #228). Missing ones (uat and prod never had them) are skipped.
current = {t.name: spark.table(table(t.name)).columns  # noqa: F821
           for t in spark.catalog.listTables(f"{catalog}.{schema}")}  # noqa: F821
for cat, sch in legacy:
    where = f"{cat}.{sch}"
    if not spark.catalog.databaseExists(where):  # noqa: F821
        print(f"{where}: not found, skipped")
        continue
    names = [t.name for t in spark.catalog.listTables(where)]  # noqa: F821
    found = {n: spark.table(table(n, where)).columns  # noqa: F821  only the tables the migration knows are read
             for n in names if n in gold_names.RENAMED or n in gold_names.TABLES}
    lplan = gold_names.legacy_plan(found, current)
    failed = [f"{where}.{old}: no gold name for column(s) {cols}" for action, old, cols in lplan if action == "fail"]
    if failed:
        raise ValueError("add them to health_transformation_lab_nlp/gold_names.py first: " + "; ".join(failed))
    for old, cols in found.items():   # one at a time: an earlier copy makes a later table to the same target a merge
        for action, _, new in gold_names.legacy_plan({old: cols}, current):
            n_old = spark.table(table(old, where)).count()  # noqa: F821
            if action == "copy":
                renamed(old, new, where).write.mode("overwrite").saveAsTable(table(new))
                current[new] = spark.table(table(new)).columns  # noqa: F821
                if rows(new) != n_old:
                    raise RuntimeError(f"{where}.{old} -> {new}: row counts differ ({n_old} vs {rows(new)})")
            elif action == "merge":
                merge_missing(renamed(old, new, where), new)
                left = not_carried(renamed(old, new, where), new)
                if left:
                    raise RuntimeError(f"{where}.{old} -> {new}: {left} rows not carried")
            if action == "stale":   # rebuilt by its own job; nothing carried, so no DROP until checked by hand
                print(f"stale: {where}.{old} ({n_old} rows); {new} ({rows(new)} rows) is rebuilt by its job. "
                      "Not checked: compare before dropping it")
                continue
            print(f"{action}: {where}.{old} ({n_old} rows) -> {new} ({rows(new)} rows), every key carried")
            drops.append(f"DROP TABLE {table(old, where)};")
    others = sorted(set(names) - set(found))
    if others:
        print(f"{where}: not gold tables this migration knows, left as they are: {', '.join(others)}")

if drops:
    print("Old tables left in place. After checking the new ones, drop them with:\n" + "\n".join(drops))
