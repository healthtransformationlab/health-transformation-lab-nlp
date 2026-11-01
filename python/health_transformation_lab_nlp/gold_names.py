"""Gold table and column names (spec 018; AGENTS.md "SQL and data names").

pandas frames and the committed CSVs keep their analysis names; a job renames them with to_gold just
before writing health_transformation_lab.gold_perio_bench. One entry per gold table: the analysis column names it
is written from, and the gold name of each.

    to_gold    rename for gold; an unknown column fails, naming it; _count columns become integers
    from_gold  the reverse, for a job that reads gold back into the analysis code (the judge resume)
    RENAMED    old table name -> new (same name: columns renamed in place)
    migration_plan  what databricks/notebooks/11_migrate_gold_names.py does with each old table
    legacy_plan     the same for a table left in an old gold schema (issue #228)
    legacy_schemas  the legacy_gold_schemas setting, parsed and checked
    merge_key_types the type of the null stand-in for a MERGE_KEYS column a side lacks (issue #248)
"""

from __future__ import annotations

import re

import pandas as pd

from .telemetry import traced

_PROVENANCE = {"sha256": "file_sha256", "source": "source_code", "run_id": "run_id", "run_ts": "run_ts",
               "git_commit": "git_commit_sha", "loaded_at": "loaded_ts"}

TABLES: dict[str, dict[str, str]] = {
    "dim_result_file": {"file": "file_name", "kind": "file_kind_code", "method": "method_name",
                        "sha256": "file_sha256", "rows": "row_count", "source": "source_code", "run_url": "run_url",
                        "git_commit": "git_commit_sha", "loaded_at": "loaded_ts"},
    "fact_prediction": {"method": "method_name", "visit_id": "visit_id", "pred": "predicted_status_code",
                        **_PROVENANCE},
    "fact_llm_call": {"visit_id": "visit_id", "model": "model_name", "backend": "backend_code",
                      "revision": "model_revision_id",
                      "prompt_version": "prompt_version_code", "shots": "shot_count",
                      "input_tokens": "input_token_count", "output_tokens": "output_token_count",
                      "latency_s": "latency_seconds", "raw": "raw_response_text", "status": "answered_status_code",
                      "grade": "answered_grade_code", "extent": "answered_extent_code", "quote": "quote_text",
                      "gate_ok": "is_gate_ok", "error": "error_text", "fallback": "is_fallback",
                      "pred": "predicted_status_code", "method": "method_name", **_PROVENANCE,
                      "truth": "truth_status_code", "difficulty": "difficulty_code"},
    "fact_chart_answer": {"visit_id": "visit_id", "system": "system_name", "answer": "answer_status_code",
                          "difficulty": "difficulty_code", "truth": "truth_status_code"},
    "fact_judge_call": {"visit_id": "visit_id", "kind": "call_kind_code", "answer": "answer_status_code",
                        "verdict": "verdict_code", "judge_status": "judge_status_code", "quote": "quote_text",
                        "gate_ok": "is_gate_ok", "gate_reason": "gate_reason_text", "endpoint": "endpoint_name",
                        "prompt_version": "prompt_version_code", "prompt_tokens": "prompt_token_count",
                        "completion_tokens": "completion_token_count", "latency_s": "latency_seconds",
                        "simulated": "is_simulated", "api_error": "is_api_error"},
    "judge_metric": {"system": "system_name", "group": "group_name", "metric": "metric_code",
                     "metric_label": "metric_name", "vs_truth": "vs_truth_ratio",
                     "vs_truth_judged": "vs_truth_judged_ratio", "vs_judge": "vs_judge_ratio",
                     "difference": "difference_ratio", "n_judged": "judged_count",
                     "corrected_accuracy": "corrected_accuracy_ratio", "ci_low": "ci_low_ratio",
                     "ci_high": "ci_high_ratio", "judged_correct": "judged_correct_ratio",
                     "verdict_sensitivity": "verdict_sensitivity_ratio",
                     "verdict_specificity": "verdict_specificity_ratio"},
    "judge_agreement": {"group": "slice_group_code", "value": "slice_value_code", "label": "slice_name",
                        "n": "chart_count", "coverage": "coverage_ratio", "agreement": "agreement_ratio",
                        "ci_low": "ci_low_ratio", "ci_high": "ci_high_ratio", "kappa": "kappa_coef"},
    "judge_cost": {"kind": "call_kind_code", "calls": "call_count", "charts": "chart_count",
                   "endpoint_errors": "endpoint_error_count", "gate_failures": "gate_failure_count",
                   "prompt_tokens": "prompt_token_count", "completion_tokens": "completion_token_count",
                   "usd": "cost_usd", "usd_per_chart": "cost_per_chart_usd",
                   "latency_mean_s": "avg_latency_seconds", "latency_p50_s": "p50_latency_seconds",
                   "latency_p95_s": "p95_latency_seconds"},
    "deid_score": {"method": "engine_name", "tier": "tier_code", "n_notes": "note_count", "n_phi": "phi_count",
                   "entity_recall": "entity_recall_ratio", "char_recall": "char_recall_ratio",
                   "char_precision": "char_precision_ratio", "decoy_damage": "decoy_damage_ratio",
                   "n_hard_negatives": "hard_negative_count", "hard_negative_damage": "hard_negative_damage_ratio",
                   "token_precision": "token_precision_ratio", "token_recall": "token_recall_ratio",
                   "token_f1": "token_f1_ratio", "leaked_per_1k_notes": "leaked_phi_per_1k_note_rate",
                   "avg_chars": "avg_note_char_count", "group": "group_name"},
    # written in SQL by 02_llm_judge.sql under the gold names; the analysis names are its CSV export's
    # (data/corpus/judgments_corpus.csv, read by scripts/16_cost_effectiveness.py)
    "judge_queue": {"method": "method_name", "visit_id": "visit_id", "note_text": "note_text",
                    "pred": "predicted_status_code"},
    "fact_corpus_judge_call": {"method": "method_name", "visit_id": "visit_id", "pred": "predicted_status_code",
                               "verdict": "verdict_code", "supported_status": "supported_status_code",
                               "quote": "quote_text", "rationale": "rationale_text", "gate_ok": "is_gate_ok",
                               "error": "error_text", "prompt_version": "prompt_version_code",
                               "judge_model": "judge_model_name"},
}

# spec 019: the EHR DQ grader's tables, built whole from committed CSVs by grader_tables and overwritten each run
_DQ_PROV = {"source_files": "source_files_text", "sha256": "file_sha256", "git_commit": "git_commit_sha",
            "loaded_at": "loaded_ts"}
TABLES |= {
    "dq_check": {"check_name": "check_name", "category": "check_category_code", "n_checked": "checked_count",
                 "n_fail": "failed_count", "pass_rate": "pass_ratio", "status": "check_status_code",
                 "clinic": "clinic_code", **_DQ_PROV},
    "dq_column_missing": {"evidence_column": "evidence_column_name", "n_rows": "row_count",
                          "n_missing": "missing_count", "pct_missing": "missing_pct", **_DQ_PROV},
    "dq_prevalence": {"method": "method_name", "level": "level_code", "group_name": "group_name",
                      "n": "subject_count", "periodontitis": "periodontitis_ratio",
                      "periodontitis_ci_low": "periodontitis_ci_low_ratio",
                      "periodontitis_ci_high": "periodontitis_ci_high_ratio", "stage3_4": "stage3_4_ratio",
                      **_DQ_PROV},
    "dq_temporal_change": {"method": "method_name", "n_later_visits": "later_visit_count",
                           "perio_resolved": "perio_resolved_ratio", "stage_drop": "stage_drop_ratio",
                           "pairs": "visit_pair_count", "better": "better_ratio", "same": "same_ratio",
                           "worse": "worse_ratio", **_DQ_PROV},
    "dq_stage_transition": {"method": "method_name", "from_status": "from_status_code",
                            "to_status": "to_status_code", "n": "visit_pair_count", "row_pct": "row_pct",
                            "direction": "direction_code", **_DQ_PROV},
    "dq_source_concordance": {"method_a": "method_a_name", "method_b": "method_b_name", "n": "visit_count",
                              "pct_agree": "agreement_ratio", "kappa": "kappa_coef", "level": "level_code",
                              **_DQ_PROV},
    "fact_visit_evidence": {"visit_id": "visit_id", "person_id": "person_id", "visit_date": "visit_date",
                            "visit_seq": "visit_seq_num", "in_review": "is_in_review",
                            "notes": "note_status_code", "exam_form": "exam_form_status_code",
                            "proc_dx_completed": "dx_completed_status_code",
                            "proc_dx_planned": "dx_planned_status_code",
                            "probing_chart": "probing_chart_status_code", "algorithm_v0": "rules_v0_status_code",
                            "algorithm_design": "rules_design_status_code", "truth_status": "truth_status_code",
                            "clinic": "clinic_code", **_DQ_PROV},
    "dq_injected_error": {"injected_errors": "injected_error_count", "caught_share": "caught_ratio",
                          "flag_rate_without_error": "false_flag_ratio", **_DQ_PROV},
    # spec 026: case profiles (statuses and measures as short labels, never note text)
    "fact_case_profile_item": {"visit_id": "visit_id", "category": "category_name",
                               "category_order": "category_order_num", "item": "item_name",
                               "item_order": "item_order_num", "value": "item_value_name", "unit": "item_unit_name",
                               **_DQ_PROV},
    "fact_record_mismatch": {"visit_id": "visit_id", "rule": "rule_name", "rule_label": "rule_label_name",
                             "evidence": "mismatch_evidence_text", "related_visit_id": "related_visit_id",
                             "failed_rule_count": "failed_rule_count",
                             "clinic": "clinic_code", "injected_error": "is_injected_error", **_DQ_PROV},
    "dq_mismatch_rule": {"rule": "rule_name", "rule_label": "rule_label_name", "clinic": "clinic_code",
                         "checkable_count": "checkable_count", "not_checkable_count": "not_checkable_count",
                         "flagged_count": "flagged_count", "code_truth_mismatch_count": "code_truth_mismatch_count",
                         "true_flag_count": "true_flag_count", "precision": "precision_ratio",
                         "recall": "recall_ratio", "only_rule_count": "only_rule_count",
                         "injected_checkable_count": "injected_checkable_count",
                         "injected_caught_count": "injected_caught_count", **_DQ_PROV},
    # the lab grader: a SIMULATED sample until real runs are committed
    "dim_grader_question": {"question_id": "question_id", "category": "category_name",
                            "category_order": "category_order_num", "level": "level_code",
                            "n_key_points": "key_point_count", "source": "source_text", "simulated": "is_simulated",
                            **_DQ_PROV},
    "fact_grader_answer": {"question_id": "question_id", "model": "model_name", "with_agent": "is_with_agent",
                           "key_points_covered": "covered_key_point_count", "score": "score_ratio",
                           "harm": "harm_code", "cost_usd": "cost_usd", "judge": "judge_model_name",
                           "run_id": "run_id", "simulated": "is_simulated", **_DQ_PROV},
    # spec 029 US3: the tooth-loss model's answers (health_transformation_lab.gold_opendental_perio), synthetic only
    "fact_tooth_loss_prediction": {"patient_id": "patient_id", "tooth_num": "tooth_num",
                                   "tooth_status_code": "tooth_status_code", "label_set": "label_set_code",
                                   "feature_set": "feature_set_code", "model": "model_name", "split": "split_code",
                                   "probability": "perio_loss_probability_ratio", "threshold": "threshold_ratio",
                                   "predicted_perio": "is_predicted_perio_loss", "generator_seed": "generator_seed_num",
                                   "synthetic": "is_synthetic", "run_id": "run_id", "run_ts": "run_ts",
                                   "git_commit": "git_commit_sha"},
}

# spec 027 US5: the pipeline doctor's frames are built under their gold names already (doctor.RUN_COLUMNS,
# doctor_job.TABLES), so each maps to itself; to_gold still fails on a column nobody declared.
_DOCTOR_PROV = ("doctor_run_id", "loaded_ts", "doctor_git_commit_sha")
TABLES |= {
    "fact_pipeline_run": {c: c for c in (
        "pipeline_name", "step_name", "run_id", "started_ts", "ended_ts", "run_status_code", "row_in_count",
        "row_out_count", "schema_sha256", "check_passed_count", "check_failed_count", "error_type_name", "error_text",
        "duration_seconds", "cost_usd", "git_commit_sha", "data_label_code", *_DOCTOR_PROV)},
    "fact_pipeline_signal": {c: c for c in (
        "pipeline_name", "step_name", "run_id", "started_ts", "run_status_code", "freshness_seconds", "sla_seconds",
        "volume_ratio", "is_schema_changed", "quality_ratio", "duration_ratio", "cost_ratio", *_DOCTOR_PROV)},
    "fact_remediation_decision": {c: c for c in (
        "pipeline_name", "run_id", "run_started_ts", "failure_class_code", "rule_name", "recommended_action_code",
        "is_reversible", "severity_code", "owner_name", "impact_text", "notification_text", "run_mode_code",
        "decided_action_code", "decided_by_name", "decided_ts", "is_match", *_DOCTOR_PROV)},
}

# spec 031: the Benchmark job's tables (01_run_benchmark.py). score()'s own run_id is one model fit (model_run_id);
# run_id is the Databricks job run, the batch key.
_RUN = {"run_id": "run_id", "run_ts": "run_ts", "git_commit": "git_commit_sha"}
TABLES |= {
    "dim_study_note": {"note_id": "note_id", "person_id": "person_id", "note_text": "note_text",
                       "label": "truth_status_code", "max_probing_depth_mm": "max_probing_depth_mm",
                       "bop_pct": "bop_pct", "max_cal_mm": "max_cal_mm", "rbl_pct": "rbl_pct",
                       "teeth_lost_perio": "perio_lost_tooth_count", "split": "split_code", **_RUN},
    "benchmark_metric": {"job_run_id": "run_id", "run_ts": "run_ts", "git_commit": "git_commit_sha",
                         "run_id": "model_run_id", "model_id": "method_name", "language": "language_code",
                         "metric": "metric_code", "class": "class_status_code", "value": "metric_ratio",
                         "n_test": "test_note_count", "timestamp": "scored_ts"},
}

RENAMED = {"result_files": "dim_result_file", "ai_predictions": "fact_prediction", "llm_reader_runs": "fact_llm_call",
           "chart_answers": "fact_chart_answer", "judgments": "fact_judge_call", "judge_metrics": "judge_metric",
           "judge_agreement": "judge_agreement", "judge_run": "judge_cost", "deid_scores": "deid_score",
           "labeled_notes": "dim_study_note", "benchmark_results": "benchmark_metric"}
# judge_agreement keeps its name: the migration renames its columns in place

# An old judgments table was written by the scorecard or, if it ran last, by the corpus judge (02): its columns say which.
_TARGETS = {"judgments": ("fact_judge_call", "fact_corpus_judge_call")}

# When a job has already written the new table, the old rows whose batch key it lacks are added; the other
# new tables are rebuilt on every run, so an old copy is stale.
MERGE_KEYS = {"dim_result_file": ("file_sha256",),
              "fact_prediction": ("source_code", "run_id", "method_name", "file_sha256", "visit_id"),
              "fact_llm_call": ("source_code", "run_id", "method_name", "file_sha256", "visit_id"),
              "fact_judge_call": ("visit_id", "call_kind_code", "answer_status_code", "endpoint_name",
                                  "prompt_version_code"),
              "benchmark_metric": ("model_run_id", "metric_code", "class_status_code")}


@traced
def to_gold(df: pd.DataFrame, table: str) -> pd.DataFrame:
    """df under table's gold column names. Columns already under their gold name pass; any other fails."""
    names = TABLES[table]
    gold = set(names.values())
    unknown = [c for c in df.columns if c not in names and c not in gold]
    if unknown:
        raise ValueError(f"{table}: no gold name for column(s) {unknown}; add them to health_transformation_lab_nlp/gold_names.py")
    out = df.rename(columns=names)
    for c in out.columns:
        if c.endswith("_count") and not c.startswith("avg_") and pd.api.types.is_float_dtype(out[c]):
            out[c] = out[c].round().astype("Int64")       # a sum of counts read back as float
    return out


@traced
def from_gold(df: pd.DataFrame, table: str) -> pd.DataFrame:
    """The reverse of to_gold: gold names back to the analysis names."""
    return df.rename(columns={v: k for k, v in TABLES[table].items()})


def _unknown(columns, table: str) -> list[str]:
    names = TABLES[table]
    return [c for c in columns if c not in names and c not in names.values()]


@traced
def migration_plan(existing: dict[str, list[str]]) -> list[tuple[str, str, str]]:
    """(action, old, new) for each old-named table in existing (table name -> its columns):
    copy (no new table yet), merge (a job wrote the new table first: add the old rows whose MERGE_KEYS it lacks),
    stale (the new table is rebuilt every run), rewrite (same name, old columns) or fail (new is then the
    unknown columns, comma-separated). Tables already under their new names need nothing."""
    plan = []
    for old, new in RENAMED.items():
        if old not in existing:
            continue
        cols = existing[old]
        target = next((t for t in _TARGETS.get(old, (new,)) if not _unknown(cols, t)), None)
        if target is None:
            plan.append(("fail", old, ", ".join(_unknown(cols, new))))
        elif old == target:
            if not set(cols) <= set(TABLES[target].values()):
                plan.append(("rewrite", old, target))
        elif target not in existing:
            plan.append(("copy", old, target))
        else:
            plan.append(("merge" if target in MERGE_KEYS else "stale", old, target))
    return plan


@traced
def legacy_plan(legacy: dict[str, list[str]], current: dict[str, list[str]]) -> list[tuple[str, str, str]]:
    """(action, legacy table, current table) for each table in an old gold schema (legacy: name -> columns) that
    the current schema's tables (current) take over, old-named or already renamed: copy (none there yet), merge
    (add the rows whose MERGE_KEYS it lacks), stale (rebuilt every run from committed files) or fail (the third
    item is then the unknown columns). Tables the migration doesn't know (OMOP) are left out; the study tables
    (spec 031) are carried: labeled_notes is stale once dim_study_note exists, benchmark_results merges."""
    plan = []
    for name, cols in legacy.items():
        if name not in RENAMED and name not in TABLES:
            continue
        candidates = _TARGETS.get(name, (RENAMED.get(name, name),))
        target = next((t for t in candidates if not _unknown(cols, t)), None)
        if target is None:
            plan.append(("fail", name, ", ".join(_unknown(cols, candidates[0]))))
        elif target not in current:
            plan.append(("copy", name, target))
        else:
            plan.append(("merge" if target in MERGE_KEYS else "stale", name, target))
    return plan


@traced
def merge_key_types(key, src: dict[str, str], current: dict[str, str]) -> dict[str, str]:
    """For each key column (in key's order), the Spark type its null stand-in takes on a side that lacks it
    (src, current: column -> type, as DataFrame.dtypes gives them): src's type, else current's, else string when
    neither has it (run_id on fact_llm_call, issue #248). Nulls match nulls, so a column neither side has never
    splits or duplicates rows."""
    return {k: src.get(k) or current.get(k) or "string" for k in key}


@traced
def legacy_schemas(setting: str) -> list[tuple[str, str]]:
    """legacy_gold_schemas ("catalog.schema,catalog.schema"; empty for none) as (catalog, schema) pairs."""
    out = []
    for item in (s.strip() for s in setting.split(",")):
        if not item:
            continue
        if not re.fullmatch(r"\w+\.\w+", item):
            raise ValueError(f"legacy_gold_schemas: {item!r} is not catalog.schema")
        out.append(tuple(item.split(".")))
    return out
