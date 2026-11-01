"""Delta writes are idempotent: delete-then-append by batch key (AGENTS.md, docs/operations.md)."""

import types

import pandas as pd
import pytest

from health_transformation_lab_nlp.delta import replace_batch, replace_keys


class _Col:
    def __init__(self, name):
        self.name = name

    def cast(self, t):
        return ("cast", self.name, t)


class _Writer:
    def __init__(self, log):
        self.log = log

    def mode(self, m):
        self.log.append(("mode", m))
        return self

    def option(self, k, v):
        self.log.append(("option", k, v))
        return self

    def saveAsTable(self, t):
        self.log.append(("save", t))


class _DF:
    def __init__(self, pdf, log):
        self.pdf, self.log = pdf, log

    def __getitem__(self, name):
        return _Col(name)

    def withColumn(self, name, col):
        self.log.append(("withColumn", name, col))
        return self

    @property
    def write(self):
        return _Writer(self.log)


class _Spark:
    def __init__(self, existing=None):
        self.log, self.existing = [], existing or {}
        self.catalog = types.SimpleNamespace(tableExists=lambda t: t in self.existing)

    def createDataFrame(self, pdf, schema=None):
        self.log.append(("create", list(pdf.columns), len(pdf)) + ((schema,) if schema else ()))
        return _DF(pdf, self.log)

    def table(self, t):
        fields = [types.SimpleNamespace(name=n, dataType=d) for n, d in self.existing[t].items()]
        return types.SimpleNamespace(schema=types.SimpleNamespace(fields=fields, fieldNames=lambda: [f.name for f in fields]))

    def sql(self, q):
        self.log.append(("sql", q))


ROWS = pd.DataFrame({"method": ["m", "m"], "visit_id": [1, 2], "pred": ["healthy", "gingivitis"],
                     "error": [None, None]})
KEY = {"source": "databricks", "run_id": "123", "method": "m"}


def test_a_new_table_is_created_by_appending():
    s = _Spark()
    assert replace_batch(s, ROWS, "c.s.ai_predictions", KEY) == 2
    assert not [e for e in s.log if e[0] == "sql"]                 # nothing to delete yet
    assert ("save", "c.s.ai_predictions") in s.log and ("mode", "append") in s.log
    assert ("option", "mergeSchema", "true") in s.log
    created = next(e for e in s.log if e[0] == "create")
    assert {"source", "run_id", "method"} <= set(created[1])          # every row carries its batch key


def test_a_rerun_deletes_its_own_batch_first():
    s = _Spark({"c.s.ai_predictions": {"method": "string", "visit_id": "bigint", "source": "string",
                                       "run_id": "string", "error": "string"}})
    replace_batch(s, ROWS, "c.s.ai_predictions", KEY)
    sql = [e[1] for e in s.log if e[0] == "sql"]
    assert sql == ["DELETE FROM c.s.ai_predictions WHERE source = 'databricks' AND run_id = '123' AND method = 'm'"]
    assert s.log.index(("sql", sql[0])) < s.log.index(("save", "c.s.ai_predictions"))
    assert ("withColumn", "error", ("cast", "error", "string")) in s.log    # all-null column takes the table's type


def test_a_table_without_the_key_columns_gets_them_but_loses_nothing():
    # Load results' rows have no run_id: the first reader run adds the column (mergeSchema), deleting nothing
    s = _Spark({"c.s.ai_predictions": {"method": "string", "visit_id": "bigint", "source": "string"}})
    replace_batch(s, ROWS, "c.s.ai_predictions", KEY)
    assert not [e for e in s.log if e[0] == "sql"]


@pytest.mark.parametrize("bad", ["x' OR '1'='1", "a;b", ""])
def test_batch_key_values_are_checked(bad):
    with pytest.raises(ValueError, match="batch key"):
        replace_batch(_Spark(), ROWS, "c.s.t", {**KEY, "run_id": bad})


# spec 027 US5: the pipeline doctor rewrites the runs it read, keyed by run_id, whichever doctor run read them first
def test_replace_keys_deletes_the_rows_of_these_keys_then_appends_with_the_given_schema():
    s = _Spark({"c.s.fact_pipeline_run": {"run_id": "string", "pipeline_name": "string"}})
    rows = pd.DataFrame({"run_id": ["11", "12", "11"], "pipeline_name": ["a", "a", "b"]})
    ddl = "run_id string, pipeline_name string"
    assert replace_keys(s, rows, "c.s.fact_pipeline_run", "run_id", schema=ddl) == 3
    sql = [e[1] for e in s.log if e[0] == "sql"]
    assert sql == ["DELETE FROM c.s.fact_pipeline_run WHERE run_id IN ('11', '12')"]
    assert s.log.index(("sql", sql[0])) < s.log.index(("save", "c.s.fact_pipeline_run"))
    assert ("mode", "append") in s.log and ("create", ["run_id", "pipeline_name"], 3, ddl) in s.log


def test_replace_keys_on_a_new_table_or_an_empty_batch_deletes_nothing():
    s = _Spark()
    replace_keys(s, pd.DataFrame({"run_id": ["1"]}), "c.s.t", "run_id")
    assert not [e for e in s.log if e[0] == "sql"] and ("save", "c.s.t") in s.log
    s = _Spark({"c.s.t": {"run_id": "string"}})
    assert replace_keys(s, pd.DataFrame({"run_id": []}), "c.s.t", "run_id") == 0
    assert s.log == []


@pytest.mark.parametrize("bad", ["x' OR '1'='1", "a;b", ""])
def test_replace_keys_checks_its_key_values(bad):
    with pytest.raises(ValueError, match="key"):
        replace_keys(_Spark(), pd.DataFrame({"run_id": [bad]}), "c.s.t", "run_id")
