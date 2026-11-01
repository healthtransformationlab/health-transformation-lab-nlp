"""Spec 012: judge-backed scorecard. Every system's answer on the scored review charts (221 of the 240 since spec 032
US8, at five status groups: rr.phenotype_predictions), the judge's
queue, a resumable judge run (simulated here, no network), and every README phenotyping metric
against the truth and against the judge."""

import math

import pandas as pd
import pytest

from health_transformation_lab_nlp import judge_scorecard as js
from health_transformation_lab_nlp import readme_results as rr
from health_transformation_lab_nlp.labels import DEFAULT_GROUPING, GROUPINGS, LABELS
from health_transformation_lab_nlp.ladder_eval import grouped

GROUPS = GROUPINGS[DEFAULT_GROUPING]


@pytest.fixture(scope="module")
def inp():
    return rr.load_inputs()


@pytest.fixture(scope="module")
def answers(inp):
    return js.chart_answers(inp)


def test_chart_answers_cover_every_readme_system_on_every_review_chart(inp, answers):
    truth, pred, _ = rr.phenotype_predictions(inp)
    assert set(answers["system"]) == set(pred)
    n = len(truth)
    assert len(answers) == n * len(pred) and not answers.duplicated(["visit_id", "system"]).any()
    assert set(answers["answer"].dropna()) <= set(GROUPS)
    assert set(answers["difficulty"]) == {"L1", "L2", "L3"}
    one = answers[answers.system == "algorithm_v0"].set_index("visit_id")["answer"]
    pd.testing.assert_series_equal(one.reindex(truth.index), pred["algorithm_v0"], check_names=False)


def test_queue_has_one_status_call_per_chart_and_one_verdict_per_distinct_answer(inp, answers):
    q = js.judge_queue(answers, inp["key"])
    status, verdict = q[q.kind == "status"], q[q.kind == "verdict"]
    n = answers["visit_id"].nunique()
    assert len(status) == n and status["answer"].isna().all()
    distinct = answers.dropna(subset=["answer"]).drop_duplicates(["visit_id", "answer"])
    assert len(verdict) == len(distinct) < n * len(GROUPS)
    assert not q.duplicated(["visit_id", "kind", "answer"]).any()
    notes = inp["key"]["note_text"]
    assert (q["note_text"].to_numpy() == notes.reindex(q["visit_id"]).to_numpy()).all()


def test_cost_estimate_prices_every_call():
    q = pd.DataFrame({"note_text": ["x" * 400] * 10})
    est = js.estimate_cost(q, usd_per_1m_in=1.0, usd_per_1m_out=2.0, system_tokens=1000, out_tokens=100)
    assert est["calls"] == 10
    assert est["usd"] == pytest.approx(10 * (1100 / 1e6 * 1.0 + 100 / 1e6 * 2.0))


NOTE = "S: bleeding gums. O: max CAL 4 mm interproximal, PD 5 mm. A: Generalized periodontitis stage II, grade B."


def test_status_prompt_shows_no_answer_and_uses_the_aap_criteria():
    from health_transformation_lab_nlp import judge
    assert judge.CRITERIA in judge.STATUS_SYSTEM
    prompt = judge.STATUS_USER.format(note=NOTE)
    assert NOTE in prompt and "Predicted" not in prompt and "{pred}" not in judge.STATUS_USER
    assert judge.STATUS_PROMPT_VERSION != judge.PROMPT_VERSION


@pytest.mark.parametrize(("out", "ok", "why"), [
    ({"supported_status": "periodontitis_stage_2", "quote": "max CAL 4 mm interproximal"}, True, ""),
    ({"supported_status": None, "quote": ""}, True, ""),                      # can't tell is allowed
    ({"supported_status": "stage two", "quote": "max CAL 4 mm"}, False, "bad status"),
    ({"supported_status": "periodontitis_stage_2", "quote": "CAL of 4mm"}, False, "quote not in note"),
    ({"supported_status": "periodontitis_stage_2"}, False, "quote not in note"),
])
def test_status_gate(out, ok, why):
    from health_transformation_lab_nlp import judge
    assert judge.gate_status(NOTE, out) == (ok, why)


def test_simulated_judge_gives_a_status_and_a_verbatim_quote():
    from health_transformation_lab_nlp import judge
    j = judge.SimulatedJudge({1: "periodontitis_stage_2"}, seed=0)
    v = j.status(NOTE, visit_id=1)
    assert v.supported_status in (None, *LABELS) and v.quote_ok
    assert v.supported_status is None or v.quote in NOTE


def test_openai_judge_status_call_sends_no_answer_and_gates_the_reply(monkeypatch):
    """The HTTP path, with the endpoint faked: the request carries the status prompt, the reply is gated."""
    import io
    import json

    from health_transformation_lab_nlp import judge
    sent = {}

    def fake_urlopen(req, timeout):
        sent["body"] = json.loads(req.data)
        reply = {"supported_status": "periodontitis_stage_2", "quote": "max CAL 4 mm interproximal",
                 "rationale": "CAL 3-4 mm"}
        return io.BytesIO(json.dumps({"choices": [{"message": {"content": json.dumps(reply)}}],
                                      "usage": {"prompt_tokens": 900, "completion_tokens": 40}}).encode())

    monkeypatch.setattr(judge.urllib.request, "urlopen", fake_urlopen)
    j = judge.OpenAIJudge(model="m", base_url="https://example.invalid/serving-endpoints", api_key="k")
    v = j.status(NOTE)
    assert sent["body"]["messages"][0]["content"] == judge.STATUS_SYSTEM
    assert "Predicted" not in sent["body"]["messages"][1]["content"]
    assert (v.verdict, v.supported_status, v.quote_ok, v.input_tokens) == ("status", "periodontitis_stage_2", True, 900)


JUDGMENT_COLS = ["visit_id", "kind", "answer", "verdict", "judge_status", "quote", "gate_ok", "gate_reason",
                 "endpoint", "prompt_version", "prompt_tokens", "completion_tokens", "latency_s", "simulated", "api_error"]


def _small_queue(inp, answers, n=12):
    q = js.judge_queue(answers, inp["key"])
    return q[q["visit_id"].isin(sorted(q["visit_id"].unique())[:n])].reset_index(drop=True)


def test_run_judge_returns_one_judgment_per_queue_row(inp, answers):
    from health_transformation_lab_nlp import judge
    q = _small_queue(inp, answers)
    sim = judge.SimulatedJudge(inp["key"]["truth_status"].to_dict(), seed=1)
    out = js.run_judge(q, sim, endpoint="sim:judge")
    assert list(out.columns) == JUDGMENT_COLS and len(out) == len(q)
    assert out["simulated"].all() and (out["endpoint"] == "sim:judge").all()
    st, vd = out[out.kind == "status"], out[out.kind == "verdict"]
    assert st["verdict"].isna().all() and set(st["judge_status"].dropna()) <= set(LABELS)
    assert set(vd["verdict"]) <= {"correct", "incorrect", "not_determinable"} and vd["judge_status"].isna().all()
    assert set(out["prompt_version"]) == {judge.STATUS_PROMPT_VERSION, judge.PROMPT_VERSION}


def test_a_failed_gate_counts_as_not_determinable_and_no_status(inp, answers):
    from health_transformation_lab_nlp.judge import Verdict

    class Liar:
        simulated = False

        def __call__(self, note, pred):
            return Verdict("correct", pred, "not in the note", "", False, 1, 1, 0.0, "quote not in note")

        def status(self, note):
            return Verdict("status", "healthy", "not in the note", "", False, 1, 1, 0.0, "quote not in note")

    out = js.run_judge(_small_queue(inp, answers, 2), Liar(), endpoint="x")
    assert not out["gate_ok"].any() and (out["gate_reason"] == "quote not in note").all()
    assert (out.loc[out.kind == "verdict", "verdict"] == "not_determinable").all()
    assert out.loc[out.kind == "status", "judge_status"].isna().all()


def test_run_judge_resumes_and_skips_rows_already_judged(inp, answers):
    from health_transformation_lab_nlp import judge
    q = _small_queue(inp, answers)
    sim = judge.SimulatedJudge(inp["key"]["truth_status"].to_dict(), seed=1)
    first = js.run_judge(q.iloc[:5], sim, endpoint="sim:judge")
    calls = []

    class Counting(judge.SimulatedJudge):
        def __call__(self, *a, **k):
            calls.append(1)
            return super().__call__(*a, **k)

        def status(self, *a, **k):
            calls.append(1)
            return super().status(*a, **k)

    rest = js.run_judge(q, Counting(inp["key"]["truth_status"].to_dict(), seed=1), endpoint="sim:judge", done=first)
    assert len(calls) == len(q) - 5 and len(rest) == len(q)
    pd.testing.assert_frame_equal(rest.iloc[:5].reset_index(drop=True), first.reset_index(drop=True))


def test_calls_that_failed_on_the_network_are_retried_on_resume(inp, answers):
    """An endpoint error isn't a judgment: it's recorded as such and asked again on the next run."""
    from health_transformation_lab_nlp import judge
    q = _small_queue(inp, answers, 2)

    class Down:
        simulated = False

        def __call__(self, note, pred):
            return judge.Verdict("", None, "", "", False, 0, 0, 0.0, "URLError: rate limited")

        def status(self, note):
            return self(note, None)

    failed = js.run_judge(q, Down(), endpoint="e")
    assert failed["api_error"].all()

    class Up(Down):
        def __call__(self, note, pred):
            return judge.Verdict("not_determinable", None, "", "", True, 5, 5, 0.0, "")

    again = js.run_judge(q, Up(), endpoint="e", done=failed)
    assert not again["api_error"].any() and (again["prompt_tokens"] == 5).all()


METRICS = ["correct", "incorrectly_assigned", "incorrectly_ruled_out", "incorrect_stage", "no_answer",
           "unsafe_rate", "sensitivity", "specificity", "ppv", "npv", "stage4_correct",
           "correct_L1", "correct_L2", "correct_L3"]


def _perfect_judgments(inp, answers):
    """A judge that always knows the truth: its status is the truth, its verdict is right."""
    q = js.judge_queue(answers, inp["key"])
    truth = grouped(inp["key"]["truth_status"])          # the status groups the answers are in
    t = truth.reindex(q["visit_id"]).to_numpy()
    out = q[["visit_id", "kind", "answer"]].copy()
    out["verdict"] = [None if k == "status" else ("correct" if a == x else "incorrect")
                      for k, a, x in zip(q["kind"], q["answer"], t)]
    out["judge_status"] = [x if k == "status" else None for k, x in zip(q["kind"], t)]
    out["gate_ok"], out["api_error"] = True, False
    return out


def test_metrics_against_the_truth_are_the_readme_numbers(inp, answers):
    truth, pred, level = rr.phenotype_predictions(inp)
    m = js.judge_metrics(inp, answers, _perfect_judgments(inp, answers), n_boot=50).set_index(["system", "metric"])
    assert set(m.index.get_level_values("metric")) == set(METRICS)
    lad = rr.ladder_eval.ladder_table(truth, pred, n_boot=1, reference="").set_index("method")
    for s in ("algorithm_v0", "modernbert-base+cw", "note_rules", "medgemma-1.5-4b-it", "probing_chart"):
        yn, bd = rr.yes_no(truth, pred[s]), rr.breakdown(truth, pred[s])
        assert m.loc[(s, "correct"), "vs_truth"] == pytest.approx(lad.loc[s, "accuracy"], abs=1e-12)
        for k, b in (("correct", "correct"), ("incorrectly_assigned", "dx_said_yes"),
                     ("incorrectly_ruled_out", "dx_said_no"), ("incorrect_stage", "stage"), ("no_answer", "no_answer")):
            assert m.loc[(s, k), "vs_truth"] == pytest.approx(bd[b], abs=1e-12), (s, k)
        assert m.loc[(s, "stage4_correct"), "vs_truth"] == pytest.approx(lad.loc[s, "stage4_recall"], abs=1e-12)
        assert m.loc[(s, "unsafe_rate"), "vs_truth"] == pytest.approx(lad.loc[s, "unsafe_rate"], abs=1e-12)
        for k in ("sensitivity", "specificity", "ppv", "npv"):
            assert m.loc[(s, k), "vs_truth"] == pytest.approx(yn[k], abs=1e-12, nan_ok=True)
        ok = pred[s] == truth
        assert m.loc[(s, "correct_L3"), "vs_truth"] == pytest.approx(ok[level == "L3"].mean(), abs=1e-12)


def test_a_judge_that_knows_the_truth_scores_every_system_exactly_as_the_truth(inp, answers):
    m = js.judge_metrics(inp, answers, _perfect_judgments(inp, answers), n_boot=50)
    both = m.dropna(subset=["vs_truth"])
    assert (both["vs_judge"] - both["vs_truth"]).abs().max() < 1e-12
    assert both["difference"].abs().max() < 1e-12 and (m["n_judged"] == answers["visit_id"].nunique()).all()
    ex = m[m.metric == "correct"].set_index("system")
    answered = answers.dropna(subset=["answer"]).groupby("system").size()
    truth = grouped(inp["key"]["truth_status"])
    right = answers.assign(ok=answers["answer"] == truth.reindex(answers["visit_id"]).to_numpy()
                           ).groupby("system")["ok"].sum()
    assert ex["corrected_accuracy"].to_numpy() == pytest.approx((right / answered).reindex(ex.index).to_numpy())
    assert (ex["ci_low"] <= ex["corrected_accuracy"] + 1e-12).all() and (ex["corrected_accuracy"] <= ex["ci_high"] + 1e-12).all()


def test_judge_agreement_with_the_truth(inp, answers):
    a = js.judge_agreement(inp, _perfect_judgments(inp, answers), n_boot=50).set_index(["group", "value"])
    assert a.loc[("all", "all"), "agreement"] == 1 and a.loc[("all", "all"), "kappa"] == 1
    assert a.loc[("all", "all"), "coverage"] == 1 and a.loc[("all", "all"), "n"] == answers["visit_id"].nunique()
    assert {"truth_status", "difficulty"} <= set(a.index.get_level_values("group"))


def test_script_dry_run_writes_simulated_tables(tmp_path):
    """scripts/36_judge_scorecard.py --simulated: no endpoint, outputs named and marked simulated."""
    import subprocess
    import sys

    from health_transformation_lab_nlp.paths import REPO_ROOT
    r = subprocess.run([sys.executable, str(REPO_ROOT / "python" / "scripts" / "36_judge_scorecard.py"),
                        "--simulated", "--out", str(tmp_path), "--n-boot", "20"],
                       capture_output=True, text=True, check=True)
    assert "SIMULATED" in r.stdout
    for name in ("chart_answers", "judgments", "judge_metrics", "judge_agreement"):
        assert (tmp_path / f"simulated_{name}.csv").exists(), name
    j = pd.read_csv(tmp_path / "simulated_judgments.csv")
    assert j["simulated"].all() and (j["endpoint"] == "sim:judge").all()


def test_tables_use_the_readme_names(inp, answers):
    """Metric and group names are the README's own, so the dashboard reads like the README."""
    from health_transformation_lab_nlp.paths import REPO_ROOT
    m = js.judge_metrics(inp, answers, _perfect_judgments(inp, answers), n_boot=20)
    header = next(line for line in (REPO_ROOT / "docs" / "results.md").read_text().splitlines()
                  if line.startswith("| Rank | Method |"))
    for label in m["metric_label"].unique():
        assert label.split(":")[0] in header, label          # the README's column names, verbatim
    assert set(m.loc[m.metric == "incorrectly_assigned", "metric_label"]) == {rr.COL_ASSIGNED}
    assert set(m.loc[m.metric == "correct_L3", "metric_label"]) == {"Correct: hard note"}
    assert set(m["group"]) <= set(rr.PHENOTYPE_GROUPS)                  # a group with no results yet is absent
    assert set(rr.PHENOTYPE_GROUPS[:6]) <= set(m["group"])
    assert (m["group"] == m["system"].map(rr.phenotype_group)).all()
    a = js.judge_agreement(inp, _perfect_judgments(inp, answers), n_boot=20)
    assert set(a.loc[a.group == "difficulty", "label"]) == {"Easy note", "Medium note", "Hard note"}


def test_without_a_judge_the_truth_metrics_still_publish(inp, answers):
    """judge_endpoint = none: no judgments; vs_truth is filled, the judge columns are empty."""
    empty = pd.DataFrame(columns=JUDGMENT_COLS)
    m = js.judge_metrics(inp, answers, empty, n_boot=20)
    assert m["vs_truth"].notna().any() and m["vs_judge"].isna().all() and (m["n_judged"] == 0).all()
    a = js.judge_agreement(inp, empty, n_boot=20)
    assert (a["coverage"] == 0).all() and a["agreement"].isna().all()


def test_chart_answers_carry_the_truth_for_the_drill_down(inp, answers):
    truth, _, _ = rr.phenotype_predictions(inp)
    assert (answers["truth"].to_numpy() == truth.reindex(answers["visit_id"]).to_numpy()).all()


def test_run_summary_reports_cost_and_speed_per_call_type():
    """Out-of-box cost and performance: tokens and US$ at the endpoint's list price, latency, failures."""
    j = pd.DataFrame({"visit_id": [1, 1, 2, 2], "kind": ["status", "verdict", "status", "verdict"],
                      "prompt_tokens": [1000, 1200, 800, 0], "completion_tokens": [100, 80, 60, 0],
                      "latency_s": [1.0, 2.0, 3.0, 0.0], "gate_ok": [True, True, False, False],
                      "api_error": [False, False, False, True]})
    r = js.judge_run_summary(j, usd_per_1m_in=0.5, usd_per_1m_out=1.5).set_index("kind")
    assert list(r.index) == ["status", "verdict", "all"]
    a = r.loc["all"]
    assert (a["calls"], a["endpoint_errors"], a["gate_failures"], a["charts"]) == (4, 1, 1, 2)
    assert a["usd"] == pytest.approx((3000 * 0.5 + 240 * 1.5) / 1e6)
    assert a["usd_per_chart"] == pytest.approx(a["usd"] / 2)
    assert a["latency_mean_s"] == pytest.approx(2.0)            # endpoint errors carry no latency
    assert r.loc["status", "latency_p95_s"] == pytest.approx(2.9)


def test_kappa_is_blank_where_the_truth_doesnt_vary(inp, answers):
    """Within one true status kappa is undefined, not 0."""
    j = _perfect_judgments(inp, answers)
    st = j.index[j["kind"] == "status"][::3]
    j.loc[st, "judge_status"] = "periodontitis_stage_1"   # a judge that errs, so its status varies within a group
    a = js.judge_agreement(inp, j, n_boot=20)
    assert a.loc[a.group == "truth_status", "kappa"].isna().all()
    assert a.loc[a.group == "difficulty", "kappa"].notna().all()


def test_correct_rows_show_how_well_the_judge_caught_each_systems_answers(inp, answers):
    """Rogan-Gladen assumes the judge errs at the same rate for every system. On synthetic charts we can
    check: the judge's share of this system's right answers it called correct (verdict_sensitivity) and
    of its wrong answers it called incorrect (verdict_specificity), and the raw share it called correct."""
    j = _perfect_judgments(inp, answers)
    m = js.judge_metrics(inp, answers, j, n_boot=20).set_index(["system", "metric"])
    r = m.loc[("note_rules", "correct")]
    assert r["verdict_sensitivity"] == 1 and r["verdict_specificity"] == 1
    assert r["judged_correct"] == pytest.approx(r["vs_truth"] / (1 - m.loc[("note_rules", "no_answer"), "vs_truth"]))
    # a judge that calls everything correct catches no wrong answer
    lenient = j.assign(verdict=j["verdict"].where(j["kind"] != "verdict", "correct"))
    r2 = js.judge_metrics(inp, answers, lenient, n_boot=20).set_index(["system", "metric"]).loc[("note_rules", "correct")]
    assert r2["judged_correct"] == 1 and r2["verdict_specificity"] == 0


def test_tables_keep_their_column_types_when_no_judge_ran():
    """judge_endpoint=none (uat/prod default): every judge column is empty, yet each table keeps typed
    columns, so Spark can write it and the dashboard's queries still find every column."""
    inp = rr.load_inputs()
    answers = js.chart_answers(inp)
    empty = js.empty_judgments()
    assert list(empty.columns) == js.JUDGMENT_COLS and len(empty) == 0
    metrics = js.judge_metrics(inp, answers, empty, n_boot=10)
    ddl = dict(c.rsplit(" ", 1) for c in js.spark_ddl(metrics).split(", "))
    assert ddl["`vs_judge`"] == "DOUBLE" and ddl["`verdict_specificity`"] == "DOUBLE" and ddl["`system`"] == "STRING"
    jd = dict(c.rsplit(" ", 1) for c in js.spark_ddl(empty).split(", "))
    assert jd["`gate_ok`"] == "BOOLEAN" and jd["`visit_id`"] == "BIGINT" and jd["`latency_s`"] == "DOUBLE"
    assert jd["`quote`"] == "STRING"
    rows = js.spark_rows(metrics)
    assert not any(isinstance(v, float) and math.isnan(v) for r in rows for v in r)   # NaN → null


def test_a_rerun_only_reuses_judgments_from_the_same_endpoint_and_prompt():
    """Resuming must not mix in judgments made with another endpoint or an older prompt."""
    from health_transformation_lab_nlp import judge as jg
    base = {"visit_id": 1, "answer": None, "verdict": None, "judge_status": "healthy", "quote": "q", "gate_ok": True,
            "gate_reason": "", "prompt_tokens": 1, "completion_tokens": 1, "latency_s": 0.1, "simulated": False}
    done = pd.DataFrame([
        {**base, "kind": "status", "endpoint": "e1", "prompt_version": jg.STATUS_PROMPT_VERSION, "api_error": False},
        {**base, "visit_id": 2, "kind": "status", "endpoint": "e2", "prompt_version": jg.STATUS_PROMPT_VERSION,
         "api_error": False},
        {**base, "visit_id": 3, "kind": "status", "endpoint": "e1", "prompt_version": "judge-status-v0", "api_error": False},
        {**base, "visit_id": 4, "kind": "status", "endpoint": "e1", "prompt_version": jg.STATUS_PROMPT_VERSION,
         "api_error": True},
        {**base, "visit_id": 5, "kind": "verdict", "answer": "healthy", "verdict": "correct", "endpoint": "e1",
         "prompt_version": jg.PROMPT_VERSION, "api_error": False},
    ])[js.JUDGMENT_COLS]
    assert sorted(js.reusable(done, "e1")["visit_id"]) == [1, 5]
    assert js.reusable(None, "e1") is None
