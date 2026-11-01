"""PerioBench as a Kaggle Benchmarks task (health_transformation_lab_nlp.kbench): the SDK's task,
assertion and judge primitives wrapped around our reader prompt, quote gate, judge prompt and
`eval/score.py` metrics. Everything here runs on scripted models: no credentials, no network."""

import importlib.util
import json
import sys
from pathlib import Path

import pandas as pd
import pytest

pytest.importorskip("kaggle_benchmarks")

from health_transformation_lab_nlp import judge, kbench, llm_reader
from health_transformation_lab_nlp.labels import LABELS
from health_transformation_lab_nlp.paths import REPO_ROOT

N = 24


@pytest.fixture(autouse=True)
def run_files_in_tmp(tmp_path, monkeypatch):
    """The SDK writes a `*.run.json` per run into the working directory and, under `enable_cache()`,
    reuses any it finds there: keep each test's files in its own folder and out of the repo."""
    monkeypatch.chdir(tmp_path)


@pytest.fixture(scope="module")
def df():
    return kbench.eval_frame(n=N, seed=1)


@pytest.fixture
def reader(df):
    return kbench.ScriptedReader(kbench.answer_key_script(df, wrong_every=4, seed=1))


@pytest.fixture
def judge_llm(df):
    return kbench.ScriptedReader(kbench.judge_script(df), name="sim:scripted-judge")


# ---------------------------------------------------------------- data and prompts
def test_eval_frame_is_the_review_set_with_the_sdk_columns(df):
    assert list(df.columns) == ["visit_id", "note_text", "truth_status", "difficulty"]
    assert len(df) == N and set(df["truth_status"]) <= set(LABELS)
    assert df.equals(kbench.eval_frame(n=N, seed=1))                      # seeded, so reproducible
    assert len(kbench.eval_frame()) == 240


def test_reader_prompt_is_our_reader_system_and_user_messages():
    text = kbench.reader_prompt("PD up to 3 mm.")
    assert text.startswith(llm_reader.PROMPTS[llm_reader.DEFAULT_VARIANT])
    assert text.endswith(llm_reader.USER.format(note="PD up to 3 mm."))


def test_judge_prompt_is_our_judge_system_and_user_messages():
    text = kbench.judge_prompt(["BOP neg."], "healthy")
    assert text.startswith(judge.SYSTEM) and "Predicted status: healthy" in text


# ---------------------------------------------------------------- one note
def test_read_note_scores_a_right_answer_and_passes_both_checks(df):
    r = df.iloc[0]
    reader = kbench.ScriptedReader(kbench.answer_key_script(df))
    run = kbench.read_note.run(reader, **r.to_dict())
    assert run.passed and run.result["is_correct"] and run.result["is_gate_ok"]
    assert run.result["predicted_status_code"] == r["truth_status"]
    assert [a.passed for a in run.assertion_results] == [True, True]
    assert "<<<\n" + r["note_text"] + "\n>>>" in reader.prompts[0]           # the note reached the model


def test_read_note_fails_the_quote_gate_when_the_quote_is_not_in_the_note(df):
    r = df.iloc[0]
    answer = json.dumps({"status": r["truth_status"], "quote": "not in this note"})
    run = kbench.read_note.run(kbench.ScriptedReader(lambda _: answer), **r.to_dict())
    assert not run.passed and not run.result["is_gate_ok"]
    assert run.result["error_text"] == "quote not in note"
    assert run.result["is_correct"]                                         # right status, gate still fails


def test_read_note_records_an_unparseable_answer_instead_of_raising(df):
    r = df.iloc[0]
    run = kbench.read_note.run(kbench.ScriptedReader(lambda _: "I cannot tell."), **r.to_dict())
    assert run.result["predicted_status_code"] is None and not run.passed
    assert run.result["error_text"].startswith("parse:")


# ---------------------------------------------------------------- the judge
def test_judge_note_passes_when_the_judge_supports_the_answer_and_quotes_the_note(df, judge_llm):
    r = df.iloc[0]
    run = kbench.judge_note.run(judge_llm, r["visit_id"], r["note_text"], r["truth_status"])
    assert run.passed and run.result == {"visit_id": int(r["visit_id"]), "verdict_code": "correct",
                                         "is_judge_ok": True, "is_judge_gate_ok": True}


def test_judge_note_fails_a_wrong_answer_and_a_judge_that_does_not_quote(df, judge_llm):
    r = df.iloc[0]
    wrong = next(lab for lab in LABELS if lab != r["truth_status"])
    run = kbench.judge_note.run(judge_llm, r["visit_id"], r["note_text"], wrong)
    assert run.result["verdict_code"] == "incorrect" and not run.result["is_judge_ok"]

    no_quote = json.dumps({"verdict": "correct", "supported_status": r["truth_status"], "quote": "?"})
    run = kbench.judge_note.run(kbench.ScriptedReader(lambda _: no_quote), r["visit_id"],
                                r["note_text"], r["truth_status"])
    assert run.result["verdict_code"] == "not_determinable" and not run.result["is_judge_gate_ok"]


def test_judge_note_skips_a_note_the_reader_did_not_answer(df, judge_llm):
    run = kbench.judge_note.run(judge_llm, 1, "x", None)
    assert run.result["verdict_code"] == "no_answer" and not judge_llm.prompts


# ---------------------------------------------------------------- scoring
def _eval_score():
    spec = importlib.util.spec_from_file_location("eval_score", REPO_ROOT / "eval" / "score.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules["eval_score"] = mod
    spec.loader.exec_module(mod)
    return mod


def _rows(truth, pred):
    perio = kbench.PERIO
    return pd.DataFrame({"truth_status_code": truth, "predicted_status_code": pred,
                         "is_correct": [t == p for t, p in zip(truth, pred)],
                         "is_gate_ok": [p is not None for p in pred],
                         "is_perio_truth": [t in perio for t in truth],
                         "is_perio_predicted": [p in perio for p in pred]})


def test_score_rows_matches_eval_score_py_to_1e_9():
    truth = LABELS * 4
    pred = LABELS[1:] + LABELS[:1] + LABELS + LABELS + ["healthy"] * 6
    ours = kbench.score_rows(_rows(truth, pred))
    theirs = _eval_score().score(truth, pred, None, "m").set_index("metric")["value"]
    for metric in ("macro_f1", "sensitivity", "specificity", "ppv", "npv"):
        assert abs(ours[metric] - theirs[metric]) < 1e-9, metric
    assert next(iter(ours)) == "sensitivity" and ours["n"] == len(truth)


def test_score_rows_leaves_an_undefined_ratio_blank():
    out = kbench.score_rows(_rows(["healthy"] * 3, ["healthy", "gingivitis", None]))
    assert out["sensitivity"] is None                                        # no periodontitis in the truth
    assert out["specificity"] == 1.0 and out["accuracy"] == 1 / 3 and out["gate_ok_ratio"] == 2 / 3


# ---------------------------------------------------------------- the whole task
def test_perio_bench_runs_the_review_set_and_scores_it(df, reader):
    run = kbench.perio_bench.run(reader, df, n_jobs=1)
    out = run.result
    assert out["n"] == N and out["errored_count"] == 0 and 0 < out["accuracy"] < 1
    assert out["is_simulated"] and out["reader_name"].startswith("sim:")
    assert "judge_ok_ratio" not in out
    assert kbench.perio_bench_sensitivity.run(reader, df).result == pytest.approx(out["sensitivity"])


def test_perio_bench_with_a_judge_adds_the_judge_agreement(df, reader, judge_llm):
    out = kbench.perio_bench.run(reader, df, judge_llm=judge_llm, n_jobs=1).result
    assert out["judge_ok_ratio"] == pytest.approx(out["accuracy"])          # this judge knows the key
    assert len(judge_llm.prompts) == N


# ---------------------------------------------------------------- the task file Kaggle runs
TASK_FILE = REPO_ROOT / "kaggle" / "perio_bench_task.py"


def test_task_file_follows_the_sdk_rules():
    text = TASK_FILE.read_text()
    assert text.startswith("# %%")                                          # jupytext percent cells
    assert "import kaggle_benchmarks as kbench" in text
    assert "perio_bench.run(" in text                                       # without .run() nothing is recorded
    assert "SIMULATED" in text                                              # dry runs say so


def test_task_file_dry_runs_on_a_scripted_model(monkeypatch, capsys):
    monkeypatch.setenv("PERIO_BENCH_N", "6")
    monkeypatch.syspath_prepend(str(Path(kbench.__file__).parents[1]))
    spec = importlib.util.spec_from_file_location("perio_bench_task", TASK_FILE)
    spec.loader.exec_module(importlib.util.module_from_spec(spec))
    out = capsys.readouterr().out
    assert "SIMULATED" in out and '"n": 6' in out
