"""Spec 016: every model result reaches Databricks, wherever it ran (results_store, record_results.py)."""

import subprocess
import sys

import pandas as pd
import pytest

from health_transformation_lab_nlp import results_store as rs
from health_transformation_lab_nlp.paths import REPO_ROOT

RECORD = REPO_ROOT / "kaggle" / "record_results.py"


def _preds(path, n, method_pred="healthy"):
    pd.DataFrame({"visit_id": range(n), "pred": method_pred, "p_healthy": 0.9}).to_csv(path, index=False)


def _details(path, n):
    pd.DataFrame({"visit_id": range(n), "model": "m", "prompt_version": "reader-v2", "shots": 0,
                  "status": "healthy", "gate_ok": [True] * (n - 1) + [False], "fallback": [False] * (n - 1) + [True],
                  "pred": ["healthy"] * (n - 2) + ["gingivitis"] * 2}).to_csv(path, index=False)


@pytest.fixture
def datasets(tmp_path):
    d = tmp_path / "datasets"
    d.mkdir()
    _preds(d / "ai_predictions_tfidf_logreg.csv", 4)
    _preds(d / "ai_predictions_medgemma-x.csv", 4)
    _details(d / "llm_details_medgemma-x.csv", 4)
    _preds(d / "simulated_ai_predictions_medgemma-x.csv", 4)
    _details(d / "simulated_llm_details_medgemma-x.csv", 4)
    return d


# ---- US2: find, fingerprint and shape the rows

def test_result_files_lists_real_results_with_kind_method_hash_and_rows(datasets):
    f = rs.result_files(datasets)
    assert sorted(f.file) == ["ai_predictions_medgemma-x.csv", "ai_predictions_tfidf_logreg.csv",
                              "llm_details_medgemma-x.csv"]                # simulated files are never results
    row = f.set_index("file").loc["llm_details_medgemma-x.csv"]
    assert row["kind"] == "llm_details" and row["method"] == "medgemma-x" and row["rows"] == 4
    assert len(row["sha256"]) == 64
    assert set(f.source) == {"repo"}                                          # nothing in the manifest yet


def test_source_and_run_url_come_from_the_manifest(datasets):
    pd.DataFrame([{"file": "llm_details_medgemma-x.csv", "source": "kaggle", "run_url": "https://x/1",
                   "recorded_at": "2026-10-28T00:00:00Z"}]).to_csv(datasets / rs.MANIFEST, index=False)
    f = rs.result_files(datasets).set_index("file")
    assert f.loc["llm_details_medgemma-x.csv", "source"] == "kaggle"
    assert f.loc["llm_details_medgemma-x.csv", "run_url"] == "https://x/1"
    assert f.loc["ai_predictions_tfidf_logreg.csv", "source"] == "repo"


def test_prediction_rows_keep_method_pred_and_provenance_only(datasets):
    f = rs.result_files(datasets)
    p = rs.prediction_rows(f[f.kind == "predictions"], datasets)
    assert list(p.columns) == ["method", "visit_id", "pred", "sha256", "source"]
    assert len(p) == 8 and set(p.method) == {"tfidf_logreg", "medgemma-x"}


def test_detail_rows_keep_every_details_column_plus_provenance(datasets):
    f = rs.result_files(datasets)
    d = rs.detail_rows(f[f.kind == "llm_details"], datasets)
    assert {"visit_id", "status", "gate_ok", "pred", "method", "sha256", "source"} <= set(d.columns)
    assert len(d) == 4


def test_new_files_drops_versions_already_loaded(datasets):
    f = rs.result_files(datasets)
    loaded = {f.set_index("file").loc["ai_predictions_tfidf_logreg.csv", "sha256"]}
    assert "ai_predictions_tfidf_logreg.csv" not in set(rs.new_files(f, loaded).file)
    assert len(rs.new_files(f, set())) == 3
    _preds(datasets / "ai_predictions_tfidf_logreg.csv", 5)                 # changed file: a new version
    assert "ai_predictions_tfidf_logreg.csv" in set(rs.new_files(rs.result_files(datasets), loaded).file)


# ---- US3: MLflow metrics for one loaded LLM run

def test_llm_run_metrics(datasets):
    d = pd.read_csv(datasets / "llm_details_medgemma-x.csv")
    truth = pd.Series(["healthy"] * 4, index=range(4))
    m = rs.llm_run_metrics(d, truth)
    assert m == {"rows": 4, "gate_fail_rate": 0.25, "fallback_rate": 0.25, "agreement_with_key": 0.5}


# ---- US1: record a collected Kaggle run (kaggle/record_results.py)

def _record(src, dest, *extra):
    return subprocess.run([sys.executable, str(RECORD), "--from", str(src), "--to", str(dest),
                           "--run-url", "https://github.com/o/r/actions/runs/9", *extra],
                          capture_output=True, text=True, check=False)


def test_record_copies_real_results_and_writes_the_manifest(tmp_path, datasets):
    out = tmp_path / "kaggle_out"
    out.mkdir()
    _preds(out / "ai_predictions_medgemma-x.csv", 6)
    _details(out / "llm_details_medgemma-x.csv", 6)
    _preds(out / "simulated_ai_predictions_medgemma-x.csv", 6)
    r = _record(out, datasets, "--min-rows", "6")
    assert r.returncode == 0, r.stdout + r.stderr
    assert len(pd.read_csv(datasets / "ai_predictions_medgemma-x.csv")) == 6
    assert len(pd.read_csv(datasets / "simulated_ai_predictions_medgemma-x.csv")) == 4    # untouched
    m = pd.read_csv(datasets / rs.MANIFEST)
    assert set(m.file) == {"ai_predictions_medgemma-x.csv", "llm_details_medgemma-x.csv"}
    assert set(m.source) == {"kaggle"} and set(m.run_url) == {"https://github.com/o/r/actions/runs/9"}
    r = _record(out, datasets, "--min-rows", "6")                             # recording again: one row per file
    assert len(pd.read_csv(datasets / rs.MANIFEST)) == 2


def test_record_refuses_a_smaller_run_and_changes_nothing(tmp_path, datasets):
    out = tmp_path / "kaggle_out"
    out.mkdir()
    _preds(out / "ai_predictions_medgemma-x.csv", 2)                          # a 2-note test run
    before = (datasets / "ai_predictions_medgemma-x.csv").read_bytes()
    r = _record(out, datasets)
    assert r.returncode == 3 and "fewer rows" in r.stdout
    assert (datasets / "ai_predictions_medgemma-x.csv").read_bytes() == before
    assert not (datasets / rs.MANIFEST).exists()


def test_record_refuses_a_test_run_of_a_new_method(tmp_path, datasets):
    # a 10-note run with shots=2 is named ...+k2: no committed file to compare with, so the full-run size decides
    out = tmp_path / "kaggle_out"
    out.mkdir()
    _preds(out / "ai_predictions_medgemma-x+k2.csv", 3)
    r = _record(out, datasets, "--min-rows", "4")
    assert r.returncode == 3 and "fewer rows" in r.stdout
    assert not (datasets / "ai_predictions_medgemma-x+k2.csv").exists()


def test_record_defaults_to_the_full_review_set():
    import importlib.util

    from health_transformation_lab_nlp.paths import DATASETS_DIR
    spec = importlib.util.spec_from_file_location("record_results", RECORD)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert mod.full_run_rows() == len(pd.read_csv(DATASETS_DIR / "answer_key" / "review_key.csv")) == 240


def test_record_with_no_results_says_so(tmp_path, datasets):
    out = tmp_path / "empty"
    out.mkdir()
    r = _record(out, datasets)
    assert r.returncode == 3 and "no result files" in r.stdout


# ---- workflows, job and notebooks

def _text(rel):
    return (REPO_ROOT / rel).read_text()


def test_kaggle_workflow_opens_a_pr_with_the_results():
    import yaml
    wf = yaml.safe_load(_text(".github/workflows/kaggle-medgemma.yml"))
    on = wf.get("on", wf.get(True))
    assert "open_pr" in on["workflow_dispatch"]["inputs"]
    perms = wf["jobs"]["run"]["permissions"]
    assert perms["contents"] == "write" and perms["pull-requests"] == "write"
    text = _text(".github/workflows/kaggle-medgemma.yml")
    assert "kaggle/record_results.py" in text and "gh pr create" in text
    step = next(s for s in wf["jobs"]["run"]["steps"] if "record_results.py" in s.get("run", ""))
    run = step["run"]
    assert run.index("pip install") < run.index("record_results.py")   # it needs pandas and the package
    assert "!cancelled()" in text and "always() && inputs.open_pr" not in text   # a cancelled run commits nothing


def test_load_results_job_runs_the_notebook_with_the_bundle_schema():
    import yaml
    jobs = yaml.safe_load(_text("databricks/resources/jobs.yml"))["resources"]["jobs"]
    task = next(t for t in jobs["load_results"]["tasks"] if t["task_key"] == "load")["notebook_task"]
    assert task["notebook_path"] == "../notebooks/10_load_results.py"
    p = task["base_parameters"]
    assert p["catalog"] == "${resources.schemas.perio_bench_gold.catalog_name}" and p["schema"] == "${resources.schemas.perio_bench_gold.name}"
    assert p["git_commit"] == "${bundle.git.commit}"


def test_deploy_starts_load_results_without_waiting():
    text = _text(".github/workflows/deploy.yml")
    assert "bundle run -t \"$TARGET\" --no-wait load_results" in text


def test_load_notebook_appends_new_versions_to_the_three_tables():
    nb = _text("databricks/notebooks/10_load_results.py")
    for t in ("dim_result_file", "fact_prediction", "fact_llm_call"):     # spec 018 names
        assert f'"{t}"' in nb, t
    assert "gold_names.to_gold(" in nb
    assert "new_files(" in nb and 'mode("append")' in nb and "mergeSchema" in nb
    assert "DELETE FROM" in nb            # a load that failed partway is redone, not duplicated
    assert "tracking.track(" in nb and "llm_run_metrics(" in nb


def test_reader_job_tags_its_rows_as_databricks():
    assert 'source="databricks"' in _text("databricks/notebooks/03_medgemma_reader.py")


def test_load_notebook_finds_the_deployed_files_and_says_when_there_are_none():
    # issue #71: every run after the first had nothing new and crashed displaying the empty table
    nb = _text("databricks/notebooks/10_load_results.py")
    assert 'Path("../../data/datasets")' in nb          # next to the notebook, as notebook 03 finds them
    assert "No result files in" in nb                   # a clear stop, naming the folder
    assert "if len(new):" in nb                         # never display an empty table


def test_run_rows_label_one_runs_files_with_their_batch_key(tmp_path):
    # the MedGemma reader job writes its own run to ai_predictions and llm_reader_runs (spec 016)
    from health_transformation_lab_nlp.results_store import run_rows
    _preds(tmp_path / "ai_predictions_medgemma-x+k2.csv", 3)
    pd.DataFrame({"visit_id": [1, 2, 3], "pred": "healthy", "gate_ok": True, "error": None}).to_csv(
        tmp_path / "llm_details_medgemma-x+k2.csv", index=False)
    preds, details = run_rows(tmp_path, "medgemma-x+k2", source="databricks", run_id="77", git_commit="abc1234",
                              run_ts=pd.Timestamp("2026-10-28", tz="UTC"))
    assert list(preds.columns) == ["method", "visit_id", "pred", "sha256", "source", "run_id", "run_ts", "git_commit"]
    assert len(preds) == len(details) == 3
    for d in (preds, details):
        assert set(d.method) == {"medgemma-x+k2"} and set(d.source) == {"databricks"} and set(d.run_id) == {"77"}
        assert d.sha256.str.fullmatch(r"[0-9a-f]{64}").all()
    assert preds.sha256.iloc[0] != details.sha256.iloc[0]          # each file's own version


def test_load_results_never_deletes_the_reader_jobs_rows():
    # PR #92 review: the reader job's rows now carry the sha256 of their CSV; a committed file with the same bytes
    # (deterministic predictions) must not make Load results delete that run's rows
    nb = _text("databricks/notebooks/10_load_results.py")
    assert "WHERE file_sha256 IN ({hashes}) AND source_code <> 'databricks'" in nb


def test_reader_job_joins_the_answer_key_by_visit():
    nb = _text("databricks/notebooks/03_medgemma_reader.py")
    assert 'details.merge(d[["visit_id", "truth", "difficulty"]], on="visit_id"' in nb
    assert "d.truth.values" not in nb


def test_load_results_skips_the_files_the_reader_job_loaded_itself():
    # issue #94: the reader job's CSVs sit in the folder Load results reads; loading them again would add the
    # same predictions a second time as source = repo
    nb = _text("databricks/notebooks/10_load_results.py")
    assert """reader.where("source_code = 'databricks'").select("file_sha256")""" in nb
    assert "loaded |=" in nb


def test_reader_job_writes_gold_names_keyed_by_its_run():
    # spec 018: the rows go through gold_names and the batch key uses the gold column names
    nb = _text("databricks/notebooks/03_medgemma_reader.py")
    assert "gold_names.to_gold(" in nb
    assert '{"source_code": "databricks", "run_id": run_id, "method_name": rung}' in nb
    assert '"fact_prediction"' in nb and '"fact_llm_call"' in nb


def test_load_results_job_migrates_the_old_gold_names_before_loading():
    # spec 018 US2: the first task copies old-named tables to the new names, so their rows are kept
    import yaml
    tasks = yaml.safe_load(_text("databricks/resources/jobs.yml"))["resources"]["jobs"]["load_results"]["tasks"]
    migrate, load = tasks[0], next(t for t in tasks if t["task_key"] == "load")
    assert migrate["task_key"] == "migrate_gold_names"
    assert migrate["notebook_task"]["notebook_path"] == "../notebooks/11_migrate_gold_names.py"
    assert {"task_key": "migrate_gold_names"} in load["depends_on"]
    nb = _text("databricks/notebooks/11_migrate_gold_names.py")
    assert "gold_names.RENAMED" in nb and "DROP TABLE" in nb
    assert "spark.sql(f\"DROP" not in nb                     # prints the drops, never runs them


def _deploy_step(tmp_path, plan, rc_first=1):
    """Run the workflow's Deploy script with a fake databricks CLI that prints `plan` and fails once."""
    import os
    import stat
    import subprocess

    import yaml
    steps = next(iter(yaml.safe_load(_text(".github/workflows/deploy.yml"))["jobs"].values()))["steps"]
    script = next(s for s in steps if s.get("name") == "Deploy")["run"]
    calls, fake = tmp_path / "calls", tmp_path / "bin" / "databricks"
    fake.parent.mkdir()
    fake.write_text(f"""#!/bin/bash
echo "$*" >> {calls}
if [ "$(wc -l < {calls})" = 1 ]; then printf '%s\\n' "$PLAN"; exit {rc_first}; fi
""")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    env = {**os.environ, "PATH": f"{fake.parent}:{os.environ['PATH']}", "PLAN": plan, "TARGET": "dev",
           "RUNNER_TEMP": str(tmp_path), "GITHUB_OUTPUT": str(tmp_path / "out")}
    r = subprocess.run(["bash", "-e", "-c", script], env=env, capture_output=True, text=True, check=False)
    return r.returncode, calls.read_text().splitlines()


DESTRUCTIVE = "Error: the deployment requires destructive actions, but the current console does not support prompting."


def test_deploy_approves_only_the_genie_spaces_moved_to_their_own_bundle(tmp_path):
    # issue #164: #157 moved the spaces to databricks/genie, so the main bundle plans to delete its copies
    plan = ("  delete resources.genie_spaces.dq_grader_genie\n  delete resources.genie_spaces.lab_grader_genie\n"
            + DESTRUCTIVE)
    rc, calls = _deploy_step(tmp_path, plan)
    assert rc == 0 and calls == ['bundle deploy -t dev', 'bundle deploy -t dev --auto-approve']


def test_deploy_still_stops_on_any_other_destructive_plan(tmp_path):
    plan = "  delete resources.genie_spaces.dq_grader_genie\n  delete resources.schemas.gold\n" + DESTRUCTIVE
    rc, calls = _deploy_step(tmp_path, plan)
    assert rc == 1 and calls == ['bundle deploy -t dev']


def test_deploy_still_stops_on_an_ordinary_failure(tmp_path):
    rc, calls = _deploy_step(tmp_path, "Error: cannot create job: permission denied")
    assert rc == 1 and calls == ['bundle deploy -t dev']

def test_run_prediction_rows_keep_the_run_key_and_the_files_version(tmp_path):
    # spec 031: the GPU encoder job writes its predictions to fact_prediction as the reader does
    _preds(tmp_path / "ai_predictions_modernbert-large.csv", 3)
    p = rs.run_prediction_rows(tmp_path / "ai_predictions_modernbert-large.csv", "modernbert-large",
                               source="databricks", run_id="5", git_commit="abc", run_ts=pd.Timestamp("2026-10-28"))
    assert list(p.columns) == ["method", "visit_id", "pred", "sha256", "source", "run_id", "run_ts", "git_commit"]
    assert set(p.method) == {"modernbert-large"} and set(p.run_id) == {"5"} and len(p) == 3
    assert p.sha256.str.fullmatch(r"[0-9a-f]{64}").all()
