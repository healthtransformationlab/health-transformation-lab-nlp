"""The gold ERDs are drawn from diagrams/_build/gold_model.py. Its columns are what gold_names writes
(test_gold_names.py) and follow the conventions (test_sql_conventions.py); here, the model holds together."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("gold_model", ROOT / "diagrams" / "_build" / "gold_model.py")
gm = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gm)


def cols(table):
    return [c.name for c in gm.TABLES[table].columns]


def test_the_model_declares_the_gold_tables_the_jobs_write():
    gold = {n for n, t in gm.TABLES.items() if t.area != "file"}
    assert gold == {"dim_result_file", "fact_prediction", "fact_llm_call", "fact_chart_answer", "fact_judge_call",
                    "judge_metric", "judge_agreement", "judge_cost", "deid_score", "judge_queue",
                    "fact_corpus_judge_call",
                    # spec 019: the EHR DQ grader
                    "dq_check", "dq_column_missing", "dq_prevalence", "dq_temporal_change", "dq_stage_transition",
                    "dq_source_concordance", "fact_visit_evidence", "dq_injected_error",
                    "fact_case_profile_item", "fact_record_mismatch", "dq_mismatch_rule",   # spec 026
                    "dim_grader_question", "fact_grader_answer",
                    "fact_pipeline_run", "fact_pipeline_signal", "fact_remediation_decision",   # spec 027
                    "fact_tooth_loss_prediction",                                              # spec 029
                    # spec 031: the Benchmark job's tables
                    "dim_study_note", "benchmark_metric"}


def test_every_relationship_joins_declared_columns():
    for r in gm.RELATIONSHIPS:
        for table, columns in ((r.parent, r.parent_cols), (r.child, r.child_cols)):
            assert set(columns) <= set(cols(table)), (r, table)


def test_every_table_and_column_says_what_it_is():
    for name, t in gm.TABLES.items():
        assert t.description and t.writer, name
        for c in t.columns:
            assert c.type and c.description, (name, c.name)
