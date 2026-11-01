"""Spec 018 US2: frames reach gold under the convention names; the declared gold model is what gets written."""
import importlib.util
import re
from pathlib import Path

import pandas as pd
import pytest

from health_transformation_lab_nlp import gold_names, results_store

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("gold_model", ROOT / "diagrams" / "_build" / "gold_model.py")
gm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gm)


def declared(table):
    return [c.name for c in gm.TABLES[table].columns]


def csv(path):
    return pd.read_csv(ROOT / path)


@pytest.mark.parametrize("old,new", [("chart_answers", "fact_chart_answer"), ("judgments", "fact_judge_call"),
                                     ("judge_metrics", "judge_metric"), ("judge_agreement", "judge_agreement"),
                                     ("judge_run", "judge_cost")])
def test_each_judge_csv_twin_becomes_its_declared_gold_table(old, new):
    assert list(gold_names.to_gold(csv(f"data/datasets/judge/{old}.csv"), new).columns) == declared(new)


def test_deid_scores_with_their_group_become_deid_score():
    df = csv("data/deid/scores.csv").assign(group="x")
    assert list(gold_names.to_gold(df, "deid_score").columns) == declared("deid_score")


def test_load_results_frames_become_the_declared_result_tables(tmp_path):
    files = results_store.result_files(ROOT / "data" / "datasets").assign(git_commit="abc", loaded_at=pd.Timestamp.now())
    assert list(gold_names.to_gold(files, "dim_result_file").columns) == declared("dim_result_file")
    for kind in ("ai_predictions", "llm_details"):
        pd.DataFrame({"visit_id": [1], "pred": ["healthy"]}).to_csv(tmp_path / f"{kind}_m.csv", index=False)
    preds, _ = results_store.run_rows(tmp_path, "m", "databricks", "1", "abc", pd.Timestamp("2026-01-01"))
    assert list(gold_names.to_gold(preds.assign(loaded_at=pd.Timestamp.now()), "fact_prediction").columns) == declared(
        "fact_prediction")


# Files written before the reader recorded the weights' revision (#214) have no revision column.
NOT_IN_OLDER_READER_FILES = {"model_revision_id"}


def _with_provenance(d):
    return d.assign(method="m", sha256="0" * 64, source="databricks", run_id="1", run_ts=pd.Timestamp.now(),
                    git_commit="abc", loaded_at=pd.Timestamp.now(), truth="healthy", difficulty="L1")


def test_every_llm_details_file_with_its_provenance_becomes_fact_llm_call():
    for path in sorted((ROOT / "data" / "datasets").glob("*llm_details_*.csv")):
        out = list(gold_names.to_gold(_with_provenance(pd.read_csv(path)), "fact_llm_call").columns)
        expected = [c for c in declared("fact_llm_call") if c in out or c not in NOT_IN_OLDER_READER_FILES]
        assert out == expected, path.name


def test_the_readers_revision_column_has_a_gold_name():
    # #214: the reader writes the Kaggle Models handle or Hugging Face commit its weights came from
    assert '"revision":' in (ROOT / "python" / "health_transformation_lab_nlp" / "llm_reader.py").read_text()
    d = pd.read_csv(ROOT / "data" / "datasets" / "llm_details_medgemma-1.5-4b-it.csv").head(2)
    d.insert(3, "revision", "keras/medgemma/keras/medgemma_instruct_4b/1")
    out = gold_names.to_gold(_with_provenance(d), "fact_llm_call")
    assert list(out.columns) == declared("fact_llm_call")
    assert out["model_revision_id"].iloc[0] == "keras/medgemma/keras/medgemma_instruct_4b/1"


def test_a_column_the_mapping_does_not_know_fails_naming_it():
    with pytest.raises(ValueError, match="new_col"):
        gold_names.to_gold(pd.DataFrame({"visit_id": [1], "new_col": [2]}), "fact_prediction")


def test_counts_are_integers_in_gold():
    out = gold_names.to_gold(csv("data/datasets/judge/judge_run.csv"), "judge_cost")
    for c in [c for c in out.columns if c.endswith("_count")]:
        assert pd.api.types.is_integer_dtype(out[c]), c


def test_from_gold_gives_the_frame_back_for_the_judge_resume():
    j = csv("data/datasets/judge/judgments.csv")
    back = gold_names.from_gold(gold_names.to_gold(j, "fact_judge_call"), "fact_judge_call")
    pd.testing.assert_frame_equal(back, j, check_dtype=False)


def test_every_old_table_name_has_one_new_name():
    assert gold_names.RENAMED == {"result_files": "dim_result_file", "ai_predictions": "fact_prediction",
                                  "llm_reader_runs": "fact_llm_call", "chart_answers": "fact_chart_answer",
                                  "judgments": "fact_judge_call", "judge_metrics": "judge_metric",
                                  "judge_agreement": "judge_agreement", "judge_run": "judge_cost",
                                  "deid_scores": "deid_score",
                                  "labeled_notes": "dim_study_note", "benchmark_results": "benchmark_metric"}
    assert set(gold_names.TABLES) == {n for n, t in gm.TABLES.items() if t.area != "file"}


def test_the_corpus_judge_sql_writes_the_declared_columns():
    sql = (ROOT / "databricks/notebooks/02_llm_judge.sql").read_text().lower()
    final = sql.split("from raw;")[0].rsplit("select", 1)[1]
    written = re.findall(r"\bas (\w+),?\s*$", final, re.MULTILINE)
    first = re.search(r"^\s+(\w+), (\w+), (\w+),", final, re.MULTILINE).groups()      # passed through, not aliased
    assert list(first) + written == declared("fact_corpus_judge_call")
    assert "'.fact_corpus_judge_call'" in sql and "'.judge_queue'" in sql
    for c in declared("judge_queue"):
        assert c in sql, c


def dashboard_columns_not_declared(dash):
    """Per dataset: names its queries read (string literals and the alias after each AS left out) that no table
    it reads declares."""
    keywords = {"select", "as", "from", "where", "round", "and", "left", "join", "on", "coalesce",
                "health_transformation_lab", "gold_perio_bench"}
    out = {}
    for ds in dash["datasets"]:
        sql = " ".join(ds["queryLines"]).lower()
        tables = set(re.findall(r"gold_perio_bench\.(\w+)", sql))
        table_aliases = set(re.findall(r"gold_perio_bench\.\w+ (\w+)", sql))
        columns = {c for t in tables for c in declared(t)}
        sql = re.sub(r"\bas\s+`?\w+`?", " ", re.sub(r"'[^']*'", " ", sql))
        used = set(re.findall(r"\b[a-z_][a-z0-9_]*\b", sql)) - keywords - tables - table_aliases
        out[ds["name"]] = used - columns
    return out


def test_the_scorecard_dashboard_reads_only_declared_gold_columns():
    import json
    dash = json.loads((ROOT / "databricks/dashboards/scorecard.lvdash.json").read_text())
    assert all(not v for v in dashboard_columns_not_declared(dash).values()), dashboard_columns_not_declared(dash)


def test_the_dashboard_check_catches_an_old_column_kept_under_its_old_alias():
    dash = {"datasets": [{"name": "x", "queryLines": [
        "SELECT ROUND(100 * difference, 1) AS `difference`, kappa AS kappa FROM health_transformation_lab.gold_perio_bench.judge_metric"]}]}
    assert dashboard_columns_not_declared(dash)["x"] == {"difference", "kappa"}


# spec 018 US2 migration: what 11_migrate_gold_names.py does with each old table, given the tables that exist
# (name -> columns). Actions: copy (new table absent), merge (new table exists: add old rows whose batch key it
# lacks), rewrite (same name, old columns), stale (new table exists and is rebuilt each run), fail (unknown columns).

def _cols(analysis_table):
    return list(gold_names.TABLES[analysis_table])


def test_an_old_table_with_no_new_one_is_copied():
    plan = gold_names.migration_plan({"ai_predictions": _cols("fact_prediction")})
    assert plan == [("copy", "ai_predictions", "fact_prediction")]


def test_nothing_to_do_once_the_old_tables_are_gone():
    assert gold_names.migration_plan({"fact_prediction": declared("fact_prediction")}) == []


def test_a_new_table_written_first_gets_the_old_rows_merged_in_not_lost():
    plan = gold_names.migration_plan({"ai_predictions": _cols("fact_prediction"),
                                      "fact_prediction": declared("fact_prediction")})
    assert plan == [("merge", "ai_predictions", "fact_prediction")]


def test_a_summary_table_rebuilt_since_is_left_as_stale():
    plan = gold_names.migration_plan({"judge_metrics": _cols("judge_metric"), "judge_metric": declared("judge_metric")})
    assert plan == [("stale", "judge_metrics", "judge_metric")]


def test_judgments_written_by_the_corpus_judge_go_to_the_corpus_table():
    plan = gold_names.migration_plan({"judgments": _cols("fact_corpus_judge_call")})
    assert plan == [("copy", "judgments", "fact_corpus_judge_call")]


def test_judgments_written_by_the_scorecard_go_to_fact_judge_call():
    plan = gold_names.migration_plan({"judgments": _cols("fact_judge_call")})
    assert plan == [("copy", "judgments", "fact_judge_call")]


def test_judge_agreement_is_rewritten_in_place_until_it_has_the_gold_columns():
    assert gold_names.migration_plan({"judge_agreement": _cols("judge_agreement")}) == [
        ("rewrite", "judge_agreement", "judge_agreement")]
    assert gold_names.migration_plan({"judge_agreement": declared("judge_agreement")}) == []


def test_an_old_table_with_a_column_no_mapping_knows_fails_naming_it():
    plan = gold_names.migration_plan({"deid_scores": _cols("deid_score") + ["mystery"]})
    assert plan == [("fail", "deid_scores", "mystery")]


def test_every_mergeable_table_has_a_batch_key_of_gold_columns():
    for table, key in gold_names.MERGE_KEYS.items():
        assert set(key) <= set(declared(table)), table


def test_the_migration_notebook_follows_the_plan_and_checks_row_counts():
    nb = (ROOT / "databricks/notebooks/11_migrate_gold_names.py").read_text()
    assert "gold_names.migration_plan(" in nb and "gold_names.MERGE_KEYS" in nb
    assert "localCheckpoint" not in nb                 # not certain on serverless; Delta overwrite reads a snapshot
    assert "row counts differ" in nb                   # a copy that lost rows fails
    assert 'spark.sql(f"DROP' not in nb                # prints the drops, never runs them


def test_the_scorecard_waits_for_the_migration_so_it_never_pays_for_calls_it_has():
    nb = (ROOT / "databricks/notebooks/07_judge_scorecard.py").read_text()
    assert "gold_names.migration_plan(" in nb and "run Load results first" in nb


# spec 027 (#233): the Benchmark job's tables and the GPU encoders' predictions under the gold names

def _study_frame():
    from health_transformation_lab_nlp.build import CHART_FIELDS
    notes = pd.DataFrame({"note_id": [1], "person_id": [1], "note_text": ["synthetic"], "label": ["healthy"],
                          **{f: [1.0] for f in CHART_FIELDS.values()}, "split": ["test"]})
    return notes.assign(run_id="9", run_ts=pd.Timestamp("2026-10-28", tz="UTC"), git_commit="abc")


def test_the_benchmark_notes_become_dim_study_note():
    assert list(gold_names.to_gold(_study_frame(), "dim_study_note").columns) == declared("dim_study_note")


def test_the_benchmark_scores_become_benchmark_metric():
    import sys
    sys.path.insert(0, str(ROOT / "eval"))
    from score import score
    res = score(["healthy", "gingivitis"], ["healthy", "healthy"], None, model_id="tfidf_logreg")
    res = res.assign(job_run_id="9", run_ts=pd.Timestamp("2026-10-28", tz="UTC"), git_commit="abc")
    assert list(gold_names.to_gold(res, "benchmark_metric").columns) == declared("benchmark_metric")


def test_the_old_study_tables_are_migrated_and_earlier_benchmark_runs_kept():
    plan = gold_names.migration_plan({"labeled_notes": _cols("dim_study_note"),
                                      "benchmark_results": _cols("benchmark_metric"),
                                      "benchmark_metric": declared("benchmark_metric")})
    assert plan == [("copy", "labeled_notes", "dim_study_note"), ("merge", "benchmark_results", "benchmark_metric")]


def test_the_study_notebook_writes_gold_names_by_batch_key_never_plain_append():
    nb = (ROOT / "databricks/notebooks/01_run_benchmark.py").read_text()
    assert 'to_gold(' in nb and "dim_study_note" in nb and "benchmark_metric" in nb
    assert "replace_batch(" in nb and 'mode("append")' not in nb
    assert "labeled_notes" not in nb.replace("labeled_notes.csv", "") and "benchmark_results" not in nb


def test_the_gpu_encoders_write_fact_prediction_by_run_never_plain_append():
    nb = (ROOT / "databricks/notebooks/08_encoder_gpu.py").read_text()
    assert "encoder_gpu_predictions" not in nb and 'mode("append")' not in nb
    assert "replace_batch(" in nb and '"fact_prediction"' in nb and "run_prediction_rows(" in nb
    assert '"source_code": "databricks"' in nb


def test_the_study_and_gpu_jobs_pass_their_run_id():
    import yaml
    jobs = yaml.safe_load((ROOT / "databricks/resources/jobs.yml").read_text())["resources"]["jobs"]
    for job in ("study_benchmark", "encoder_gpu"):
        assert jobs[job]["tasks"][0]["notebook_task"]["base_parameters"]["run_id"] == "{{job.run_id}}", job


def test_the_migration_turns_text_timestamps_into_timestamps():
    nb = (ROOT / "databricks/notebooks/11_migrate_gold_names.py").read_text()
    assert 'endswith("_ts")' in nb and "to_timestamp" in nb

# issue #228: tables left in the old gold schemas (the old catalog before spec 021, the old schema before
# spec 022; databricks.yml legacy_gold_schemas) are carried into the current schema.

def test_a_legacy_old_named_table_is_merged_into_the_current_new_one():
    plan = gold_names.legacy_plan({"ai_predictions": _cols("fact_prediction")},
                                  {"fact_prediction": declared("fact_prediction")})
    assert plan == [("merge", "ai_predictions", "fact_prediction")]


def test_a_legacy_table_already_under_its_new_name_is_merged_too():
    plan = gold_names.legacy_plan({"fact_prediction": declared("fact_prediction")},
                                  {"fact_prediction": declared("fact_prediction")})
    assert plan == [("merge", "fact_prediction", "fact_prediction")]


def test_a_legacy_table_with_no_current_one_is_copied():
    plan = gold_names.legacy_plan({"judgments": _cols("fact_judge_call")}, {})
    assert plan == [("copy", "judgments", "fact_judge_call")]


def test_a_legacy_summary_the_current_job_rebuilds_is_stale():
    plan = gold_names.legacy_plan({"judge_metrics": _cols("judge_metric"), "judge_metric": declared("judge_metric")},
                                  {"judge_metric": declared("judge_metric")})
    assert plan == [("stale", "judge_metrics", "judge_metric"), ("stale", "judge_metric", "judge_metric")]


def test_legacy_reader_details_with_their_revision_column_are_carried():
    plan = gold_names.legacy_plan({"llm_reader_runs": _cols("fact_llm_call") + ["revision"]},
                                  {"fact_llm_call": declared("fact_llm_call")})
    assert plan == [("merge", "llm_reader_runs", "fact_llm_call")]


def test_a_legacy_table_with_an_unknown_column_fails_naming_it():
    plan = gold_names.legacy_plan({"ai_predictions": _cols("fact_prediction") + ["mystery"]}, {})
    assert plan == [("fail", "ai_predictions", "mystery")]


def test_tables_the_migration_doesnt_know_are_left_alone():
    assert gold_names.legacy_plan({"person": ["person_id"]}, {}) == []


def test_legacy_schemas_are_parsed_and_a_malformed_one_fails_naming_it():
    assert gold_names.legacy_schemas(" a.b , c_1.d_2 ,") == [("a", "b"), ("c_1", "d_2")]
    assert gold_names.legacy_schemas("") == []
    with pytest.raises(ValueError, match="legacy_gold_schemas.*a.b.c"):
        gold_names.legacy_schemas("a.b.c")


def test_the_migration_notebook_carries_the_legacy_schemas_and_checks_every_key_arrived():
    nb = (ROOT / "databricks/notebooks/11_migrate_gold_names.py").read_text()
    assert "gold_names.legacy_plan(" in nb and "gold_names.legacy_schemas(" in nb
    assert "rows not carried" in nb                    # a legacy table with rows missing gets no DROP
    stale = nb[nb.index('if action == "stale":'):]
    assert stale.index("continue") < stale.index("drops.append")   # a stale table, never checked, gets no DROP
    jobs = (ROOT / "databricks/resources/jobs.yml").read_text()
    assert "legacy_gold_schemas: ${var.legacy_gold_schemas}" in jobs


# issue #248: a key column missing from one or both sides (run_id on fact_llm_call, in neither the legacy nor the
# current table) counts as null on that side; its type comes from the side that has it, or is string.

def test_a_key_column_only_the_legacy_side_has_takes_its_type():
    types = gold_names.merge_key_types(("visit_id", "run_id"), {"visit_id": "bigint", "run_id": "string"},
                                       {"visit_id": "bigint"})
    assert types == {"visit_id": "bigint", "run_id": "string"}


def test_a_key_column_only_the_current_side_has_takes_its_type():
    types = gold_names.merge_key_types(("visit_id", "run_ts"), {"visit_id": "bigint"},
                                       {"visit_id": "bigint", "run_ts": "timestamp"})
    assert types == {"visit_id": "bigint", "run_ts": "timestamp"}


def test_a_key_column_neither_side_has_is_a_string_null_not_an_error():
    cols = {"source_code": "string", "method_name": "string", "file_sha256": "string", "visit_id": "bigint"}
    types = gold_names.merge_key_types(gold_names.MERGE_KEYS["fact_llm_call"], cols, dict(cols))
    assert types["run_id"] == "string"
    assert list(types) == list(gold_names.MERGE_KEYS["fact_llm_call"])


def test_the_migration_notebook_stands_in_nulls_on_both_sides_and_writes_only_the_legacy_columns():
    nb = (ROOT / "databricks/notebooks/11_migrate_gold_names.py").read_text()
    assert "src.schema[k]" not in nb                   # the legacy side may lack the key too (issue #248)
    assert "gold_names.merge_key_types(" in nb
    merge = nb[nb.index("def merge_missing"):nb.index("def not_carried")]
    assert ".select(*src.columns)" in merge            # a stand-in key column is never written
