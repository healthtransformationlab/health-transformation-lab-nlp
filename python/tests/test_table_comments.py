"""Spec 034 US2 (#534): every Unity Catalog table the jobs write gets its table comment and column comments from
the declarations (diagrams/_build/gold_model.py, opendental_silver_model.py), after every write."""
import re

import pandas as pd
import pytest

from health_transformation_lab_nlp import delta
from health_transformation_lab_nlp import table_comments as tc
from health_transformation_lab_nlp.paths import REPO_ROOT

CAT = "health_transformation_lab"


class FakeSpark:
    """Records SQL; tables exist with the columns given."""

    def __init__(self, tables, fail_on=None):
        self.tables, self.sql_calls, self.fail_on = tables, [], fail_on
        self.catalog = self

    def tableExists(self, name):
        return name in self.tables

    def table(self, name):
        cols = self.tables[name]
        return type("T", (), {"columns": cols, "schema": type("S", (), {"fieldNames": lambda s: cols,
                                                                         "fields": []})()})()

    def sql(self, statement):
        if self.fail_on and self.fail_on in statement:
            raise RuntimeError("permission denied")
        self.sql_calls.append(statement)

    def createDataFrame(self, rows, schema=None):
        spark = self

        class W:
            def mode(self, m):
                return self

            def option(self, *a):
                return self

            def saveAsTable(self, name):
                spark.tables.setdefault(name, list(rows.columns))

        class DF:
            write = W()

            def withColumn(self, *a):
                return self

            def __getitem__(self, k):
                return type("C", (), {"cast": lambda s, t: None})()

        return DF()


def test_every_declared_table_and_column_has_a_comment():
    for schema, table in tc.declared_tables():
        comment, columns = tc.declared(schema, table)
        assert comment, f"{schema}.{table}: no table comment"
        assert all(columns.values()), f"{schema}.{table}: a column without a description"


def test_gold_tables_take_gold_models_grain_and_column_text():
    comment, columns = tc.declared("gold_perio_bench", "fact_prediction")
    assert comment.lower().startswith("one ")                        # the grain
    assert columns.get("predicted_status_code")


def test_bronze_open_dental_tables_reuse_the_silver_column_text():
    _, silver = tc.declared("silver_opendental_perio", "patient")
    comment, bronze = tc.declared("bronze_opendental_perio", "patient")
    assert bronze == silver and "bronze" in comment.lower()


@pytest.mark.parametrize("table", ["person", "visit_occurrence", "measurement", "note"])
def test_the_omop_tables_get_a_table_comment(table):
    comment, _ = tc.declared("gold_perio_bench", table)
    assert comment and "OMOP" in comment and "synthetic" in comment.lower()


def test_statements_comment_the_table_and_only_the_declared_columns_it_has():
    fqn = f"{CAT}.gold_perio_bench.fact_prediction"
    sql = tc.statements(fqn, ["method_name", "visit_id", "predicted_status_code", "an_extra_column"])
    assert sql[0].startswith(f"COMMENT ON TABLE {fqn} IS '")
    altered = [re.search(r"ALTER COLUMN (\w+) COMMENT", s).group(1) for s in sql[1:]]
    assert altered == ["method_name", "visit_id", "predicted_status_code"]   # the undeclared column is left alone


def test_quotes_and_backslashes_in_a_description_are_escaped():
    assert tc.sql_string("it's a \\ path") == "'it\\'s a \\\\ path'"


def test_a_bad_table_name_is_refused():
    with pytest.raises(ValueError):
        tc.statements("cat.schema.table; DROP TABLE x", [])


def test_an_undeclared_table_gets_nothing_and_a_warning(capsys):
    assert tc.statements(f"{CAT}.gold_perio_bench.not_a_table", ["a"]) == []
    spark = FakeSpark({f"{CAT}.gold_perio_bench.not_a_table": ["a"]})
    assert tc.apply(spark, f"{CAT}.gold_perio_bench.not_a_table") == 0
    assert "no declared comment" in capsys.readouterr().out


def test_apply_runs_the_statements_and_a_failure_only_warns(capsys):
    fqn = f"{CAT}.gold_perio_bench.fact_prediction"
    spark = FakeSpark({fqn: ["method_name", "visit_id"]})
    assert tc.apply(spark, fqn) == 3 and spark.sql_calls[0].startswith("COMMENT ON TABLE")
    failing = FakeSpark({fqn: ["method_name"]}, fail_on="ALTER")
    assert tc.apply(failing, fqn) == 1                                # a comment never fails the job
    assert "comment not applied" in capsys.readouterr().out


def test_apply_all_comments_every_declared_table_that_exists():
    spark = FakeSpark({f"{CAT}.gold_perio_bench.fact_prediction": ["visit_id"],
                       f"{CAT}.silver_opendental_perio.patient": ["patnum"]})
    assert tc.apply_all(spark, CAT) == 2
    assert {s.split(" IS ")[0] for s in spark.sql_calls if s.startswith("COMMENT ON TABLE")} == {
        f"COMMENT ON TABLE {CAT}.gold_perio_bench.fact_prediction", f"COMMENT ON TABLE {CAT}.silver_opendental_perio.patient"}


def test_the_delta_writers_comment_what_they_write():
    fqn = f"{CAT}.gold_perio_bench.fact_prediction"
    rows = pd.DataFrame({"method_name": ["m"], "visit_id": [1], "predicted_status_code": ["healthy"]})
    spark = FakeSpark({})
    delta.replace_batch(spark, rows, fqn, {"run_id": "r1"})
    assert any(s.startswith(f"COMMENT ON TABLE {fqn}") for s in spark.sql_calls)
    spark = FakeSpark({})
    delta.replace_keys(spark, rows.assign(run_id="r1"), fqn, "run_id")
    assert any(s.startswith(f"COMMENT ON TABLE {fqn}") for s in spark.sql_calls)


NOTEBOOKS = REPO_ROOT / "databricks" / "notebooks"


@pytest.mark.parametrize("path", sorted(p.name for p in NOTEBOOKS.glob("*.py") if "saveAsTable" in p.read_text()))
def test_every_notebook_that_writes_a_table_comments_it(path):
    text = (NOTEBOOKS / path).read_text()
    assert text.count("saveAsTable") <= text.count("table_comments.apply"), path   # one apply per write


def test_load_results_sweeps_every_declared_table_after_a_deploy():
    assert "table_comments.apply_all(" in (NOTEBOOKS / "10_load_results.py").read_text()


def test_the_sql_judge_sets_its_table_comment_from_gold_model():
    comment, _ = tc.declared("gold_perio_bench", "fact_corpus_judge_call")
    sql = (NOTEBOOKS / "02_llm_judge.sql").read_text()
    assert f"COMMENT ON TABLE IDENTIFIER(:catalog || '.' || :schema || '.fact_corpus_judge_call') IS {tc.sql_string(comment)};" in sql
