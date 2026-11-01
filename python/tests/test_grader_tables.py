"""Spec 019: the tables the two graders read, built from the committed CSVs (US1 data quality, US3 lab grader)."""

import pytest

from health_transformation_lab_nlp import grader_tables as gt
from health_transformation_lab_nlp.paths import DATASETS_DIR

DQ = {
    "dq_check": {"check_name", "category", "clinic", "n_checked", "n_fail", "pass_rate", "status"},
    "dq_column_missing": {"evidence_column", "n_rows", "n_missing", "pct_missing"},
    "dq_prevalence": {"method", "level", "group_name", "n", "periodontitis", "periodontitis_ci_low",
                      "periodontitis_ci_high", "stage3_4"},
    "dq_temporal_change": {"method", "n_later_visits", "perio_resolved", "stage_drop", "pairs", "better", "same", "worse"},
    "dq_stage_transition": {"method", "from_status", "to_status", "n", "row_pct", "direction"},
    "dq_source_concordance": {"method_a", "method_b", "n", "pct_agree", "kappa"},
    "fact_visit_evidence": {"visit_id", "person_id", "clinic", "visit_date", "visit_seq", "truth_status", "notes",
                  "exam_form", "proc_dx_completed", "proc_dx_planned", "probing_chart", "algorithm_v0",
                  "algorithm_design", "algorithm_patel2022"},
    "dq_injected_error": {"injected_errors", "caught_share", "flag_rate_without_error"},
    # spec 026 US1
    "fact_case_profile_item": {"visit_id", "category", "category_order", "item", "item_order", "value", "unit"},
    # spec 026 US2
    "fact_record_mismatch": {"visit_id", "rule", "rule_label", "evidence", "related_visit_id", "failed_rule_count",
                             "clinic",
                             "injected_error"},
    "dq_mismatch_rule": {"rule", "rule_label", "clinic", "checkable_count", "not_checkable_count", "flagged_count",
                         "code_truth_mismatch_count", "true_flag_count", "precision", "recall", "only_rule_count",
                         "injected_checkable_count", "injected_caught_count"},
}
PROVENANCE = {"sha256", "source_files"}   # analysis names; gold_names.to_gold renames them for gold


@pytest.fixture(scope="module")
def dq():
    return gt.dq_tables(DATASETS_DIR)


def test_every_dq_table_has_its_columns_and_provenance(dq):
    assert set(dq) == set(DQ)
    for name, cols in DQ.items():
        df = dq[name]
        assert len(df), name
        assert cols | PROVENANCE <= set(df.columns), (name, (cols | PROVENANCE) - set(df.columns))
        assert df.sha256.str.fullmatch(r"[0-9a-f]{64}").all(), name


def test_no_note_text_reaches_a_dq_table(dq):
    # the evidence columns are statuses, never the note itself
    statuses = {"unknown", "healthy_gingivitis", "healthy", "gingivitis"} | {f"periodontitis_stage_{i}" for i in range(1, 5)}
    for col in ("notes", "exam_form", "probing_chart", "algorithm_design", "truth_status"):
        assert set(dq["fact_visit_evidence"][col].dropna()) <= statuses, col
    assert "text" not in " ".join(c for df in dq.values() for c in df.columns)


def test_checks_hold_the_overall_rows_and_every_clinic(dq):
    c = dq["dq_check"]
    overall = c[c.clinic == "All"]
    assert len(overall) == 16 and c.clinic.nunique() == 1 + 8


def test_transitions_are_long_form_with_row_shares_and_direction(dq):
    t = dq["dq_stage_transition"]
    assert len(t) == 25
    sums = t.groupby("from_status").row_pct.sum()
    assert ((sums - 100).abs() < 1e-6).all()
    worse = t[(t.from_status == "healthy_gingivitis") & (t.to_status == "periodontitis_stage_1")]
    better = t[(t.from_status == "periodontitis_stage_2") & (t.to_status == "periodontitis_stage_1")]
    assert worse.direction.item() == "worse" and better.direction.item() == "better"


def test_prevalence_holds_clinics_and_scales(dq):
    p = dq["dq_prevalence"]
    assert set(p.level) == {"clinic", "scale"}
    assert p[p.level == "clinic"].group_name.nunique() == 8


def test_dq_tables_are_the_same_on_every_build():
    a, b = gt.dq_tables(DATASETS_DIR), gt.dq_tables(DATASETS_DIR)
    for name in a:
        assert a[name].equals(b[name]), name


def test_load_results_overwrites_every_grader_table():
    # spec 019 US1: the job writes each table whole, so a rerun leaves the same rows
    from health_transformation_lab_nlp.paths import REPO_ROOT
    nb = (REPO_ROOT / "databricks" / "notebooks" / "10_load_results.py").read_text()
    assert "grader_tables.dq_tables(data_dir)" in nb and "grader_tables.lab_tables(data_dir)" in nb
    assert '.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(table(name))' in nb
    assert "gold_names.to_gold(df.assign(git_commit=commit, loaded_at=now), name)" in nb   # gold names


def test_every_dq_table_becomes_its_declared_gold_table(dq):
    # AGENTS.md "SQL and data names": the frames keep analysis names; to_gold gives the declared gold columns
    import importlib.util

    import pandas as pd

    from health_transformation_lab_nlp import gold_names
    from health_transformation_lab_nlp.paths import REPO_ROOT
    spec = importlib.util.spec_from_file_location("gold_model", REPO_ROOT / "diagrams" / "_build" / "gold_model.py")
    gm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gm)
    for name, df in dq.items():
        gold = gold_names.to_gold(df.assign(git_commit="abc", loaded_at=pd.Timestamp("2026-10-28", tz="UTC")), name)
        assert list(gold.columns) == [c.name for c in gm.TABLES[name].columns], name


# ---------------------------------------------------------------- the lab grader (US3)

LAB = {
    "dim_grader_question": {"question_id", "category", "category_order", "level", "n_key_points", "source", "simulated"},
    "fact_grader_answer": {"question_id", "model", "with_agent", "key_points_covered", "score", "harm", "cost_usd",
                       "judge", "run_id", "simulated"},
}


@pytest.fixture(scope="module")
def sim():
    return gt.simulate_grader(seed=2026)


def test_simulated_sample_is_seeded_and_reproducible(sim):
    again = gt.simulate_grader(seed=2026)
    for name in sim:
        assert sim[name].equals(again[name]), name
    assert not sim["fact_grader_answer"].equals(gt.simulate_grader(seed=7)["fact_grader_answer"])


def test_simulated_sample_has_the_spec_shape(sim):
    q, a = sim["dim_grader_question"], sim["fact_grader_answer"]
    assert set(sim) == set(LAB)
    for name, cols in LAB.items():
        assert cols <= set(sim[name].columns), (name, cols - set(sim[name].columns))
    assert q.simulated.all() and a.simulated.all()                          # never a result
    assert a.model.str.startswith("sim:").all() and a.judge.str.startswith("sim:").all()
    assert q.groupby("category").size().eq(25).all()                         # the pitch's pilot size
    assert q.sort_values("category_order").category.iloc[0] == "Access to care"   # the mission first
    assert set(q.level) == {"L1", "L2", "L3"} and set(a.harm) <= {"S0", "S1", "S2"}
    assert (a.score == a.key_points_covered / a.question_id.map(q.set_index("question_id").n_key_points)).all()
    per_question = a.groupby(["question_id", "model"]).with_agent.nunique()
    assert per_question.eq(2).all()                                          # each model with and without the agent
    assert not set(a.judge.str.split(":").str[1]) & set(a.model.str.split(":").str[1])   # never self-judged


def test_lab_tables_use_real_files_when_present_else_the_sample(tmp_path, sim):
    out = gt.lab_tables(tmp_path)                                            # nothing there: the seeded sample
    assert out["fact_grader_answer"].simulated.all() and (out["fact_grader_answer"].sha256.str.len() == 64).all()
    (tmp_path / "grader").mkdir()
    for name, f in (("dim_grader_question", "grader_questions"), ("fact_grader_answer", "grader_answers")):
        sim[name].assign(simulated=False).to_csv(tmp_path / "grader" / f"{f}.csv", index=False)
    real = gt.lab_tables(tmp_path)
    assert not real["fact_grader_answer"].simulated.any()
    assert real["fact_grader_answer"].source_files.iloc[0] == "grader/grader_answers.csv"


def test_the_lab_tables_become_their_declared_gold_tables(sim):
    import importlib.util

    import pandas as pd

    from health_transformation_lab_nlp import gold_names
    from health_transformation_lab_nlp.paths import REPO_ROOT
    spec = importlib.util.spec_from_file_location("gold_model", REPO_ROOT / "diagrams" / "_build" / "gold_model.py")
    gm = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gm)
    for name, df in gt.lab_tables(DATASETS_DIR).items():
        gold = gold_names.to_gold(df.assign(git_commit="abc", loaded_at=pd.Timestamp("2026-10-28", tz="UTC")), name)
        assert list(gold.columns) == [c.name for c in gm.TABLES[name].columns], name


def test_every_visit_has_a_case_profile_in_gold(dq):
    p = dq["fact_case_profile_item"]
    visits = dq["fact_visit_evidence"]
    assert set(p.visit_id) == set(visits.visit_id)
    assert p.groupby("visit_id").category.nunique().eq(9).all()


def test_every_record_mismatch_names_a_known_rule_and_the_scores_cover_every_clinic(dq):
    m, s = dq["fact_record_mismatch"], dq["dq_mismatch_rule"]
    assert set(m.rule) <= set(s.rule) and "any_rule" in set(s.rule)
    assert set(s.clinic) == {"All"} | {str(i) for i in range(1, 9)}
    assert set(m.visit_id) <= set(dq["fact_visit_evidence"].visit_id)
