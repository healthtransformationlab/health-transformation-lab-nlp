"""The gold schema health_transformation_lab.gold_perio_bench, declared once: tables, columns, keys, relationships.

The jobs write these tables from pandas (no DDL to read), so this file is the declaration the ERDs
and diagrams/gold/data_model.md are drawn from. python/tests/test_gold_model.py checks its columns
against the CSV twins and results_store, so a column added there fails until it is added here.
Logical keys: Delta enforces none. Synthetic data only.
"""
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Column:
    name: str
    type: str
    description: str
    key: str = ""            # "PK", "FK" or "PK,FK": the logical key


@dataclass(frozen=True)
class Table:
    area: str                # results · judge · deid · corpus · dq · lab · study · file
    description: str         # the grain: one row per ...
    writer: str              # the job and how it writes
    columns: list = field(default_factory=list)


@dataclass(frozen=True)
class Relationship:
    parent: str
    child: str
    parent_cols: tuple
    child_cols: tuple
    label: str
    cardinality: str = "||--o{"   # Mermaid ER: parent side, line, child side
    derived: bool = False         # dashed: summarised from or matched on, not a key


C = Column
PROV = [C("file_sha256", "string", "SHA-256 of the source file: its version (in dim_result_file for repo · kaggle rows only)", "FK"),
        C("source_code", "string", "repo · kaggle · databricks"),
        C("run_id", "string", "Databricks job run id (databricks rows)"),
        C("run_ts", "timestamp", "when the reader job ran (databricks rows); fact_llm_call: also the load time of Load results rows"),
        C("git_commit_sha", "string", "commit the job was deployed from"),
        C("loaded_ts", "timestamp", "when Load results wrote it (Load results rows)")]

DQ_PROV = [C("source_files_text", "string", "the committed CSVs the table is built from"),
           C("file_sha256", "string", "SHA-256 of those files together: the version"),
           C("git_commit_sha", "string", "commit the job was deployed from"),
           C("loaded_ts", "timestamp", "when Load results wrote it")]

DOCTOR_PROV = [C("doctor_run_id", "string", "the Pipeline doctor run that wrote the row (batch key)"),
               C("loaded_ts", "timestamp", "when it wrote it"),
               C("doctor_git_commit_sha", "string", "commit the doctor was deployed from")]

TABLES = {
    "review_key": Table(
        "file", "One per synthetic review chart (answer_key/review_key.csv, not a table)", "10_build_study.py (seeded)", [
            C("visit_id", "bigint", "review chart (240)", "PK"),
            C("truth_status", "string", "the generator's truth"),
            C("difficulty", "string", "L1 · L2 · L3"),
            C("note_text", "string", "de-identified note, through the leak gate"),
        ]),
    "dim_result_file": Table(
        "results", "One per committed result file version", "Load results: delete-then-append by file_sha256, written last", [
            C("file_name", "string", "e.g. ai_predictions_bert-base.csv"),
            C("file_kind_code", "string", "predictions · llm_details"),
            C("method_name", "string", "method (rung) from the file name"),
            C("file_sha256", "string", "SHA-256 of the file: its version", "PK"),
            C("row_count", "bigint", "rows in the file"),
            C("source_code", "string", "repo · kaggle (results_manifest.csv)"),
            C("run_url", "string", "Kaggle workflow run; empty for repo"),
            C("git_commit_sha", "string", "commit the bundle was deployed from"),
            C("loaded_ts", "timestamp", "when Load results wrote it"),
        ]),
    "fact_prediction": Table(
        "results", "One per method and chart, per file version (key file_sha256 + visit_id) or reader run (key source_code + run_id + method_name + visit_id)",
        "Load results: delete-then-append by file_sha256 · MedGemma reader: replace (source_code, run_id, method_name)", [
            C("method_name", "string", "method (rung), e.g. modernbert-base+cw"),
            C("visit_id", "bigint", "review chart", "PK,FK"),
            C("predicted_status_code", "string", "predicted status, one of six"),
            *[(C(c.name, c.type, c.description, "PK,FK") if c.name == "file_sha256" else c) for c in PROV],
        ]),
    "fact_llm_call": Table(
        "results", "One per LLM reader call on a chart", "as fact_prediction", [
            C("visit_id", "bigint", "review chart", "PK,FK"),
            C("model_name", "string", "model id"),
            C("backend_code", "string", "hf (local weights) · openai (OpenAI-compatible endpoint)"),
            C("model_revision_id", "string", "Kaggle Models handle or Hugging Face commit of the weights; empty before #214"),
            C("prompt_version_code", "string", "e.g. reader-v2"),
            C("shot_count", "bigint", "few-shot examples in the prompt"),
            C("input_token_count", "bigint", "prompt tokens"),
            C("output_token_count", "bigint", "completion tokens"),
            C("latency_seconds", "double", "seconds for the call"),
            C("raw_response_text", "string", "the model's full reply"),
            C("answered_status_code", "string", "status the model answered"),
            C("answered_grade_code", "string", "grade the model answered"),
            C("answered_extent_code", "string", "extent the model answered"),
            C("quote_text", "string", "passage quoted from the note"),
            C("is_gate_ok", "boolean", "quote gate passed: the quote is verbatim in the note"),
            C("error_text", "string", "call or parse error"),
            C("is_fallback", "boolean", "gate failed, so the rules answered"),
            C("predicted_status_code", "string", "final status (= fact_prediction.predicted_status_code)"),
            C("method_name", "string", "method (rung), with shot and adapter tags"),
            *[(C(c.name, c.type, c.description, "PK,FK") if c.name == "file_sha256" else c) for c in PROV],
            C("truth_status_code", "string", "answer key truth (databricks rows)"),
            C("difficulty_code", "string", "L1 · L2 · L3 (databricks rows)"),
        ]),
    "fact_chart_answer": Table(
        "judge", "One per system and review chart (README leaderboard systems)", "Judge scorecard: overwrite", [
            C("visit_id", "bigint", "review chart", "PK,FK"),
            C("system_name", "string", "AI method, +rules4 variant, rule phenotype or one evidence type", "PK"),
            C("answer_status_code", "string", "the system's status; null = no answer", "FK"),
            C("difficulty_code", "string", "L1 · L2 · L3"),
            C("truth_status_code", "string", "the generator's truth"),
        ]),
    "fact_judge_call": Table(
        "judge", "One per judge call: a chart's status, or a verdict on one answer",
        "Judge scorecard: overwrite, earlier calls kept and resumed", [
            C("visit_id", "bigint", "review chart", "PK"),
            C("call_kind_code", "string", "status (no answer shown) · verdict", "PK,FK"),
            C("answer_status_code", "string", "answer judged (verdict rows)", "PK"),
            C("verdict_code", "string", "correct · incorrect · not_determinable"),
            C("judge_status_code", "string", "the judge's own status (status rows)"),
            C("quote_text", "string", "verbatim from the note"),
            C("is_gate_ok", "boolean", "quote gate and schema check passed"),
            C("gate_reason_text", "string", "why the gate failed"),
            C("endpoint_name", "string", "serving endpoint"),
            C("prompt_version_code", "string", "judge-status-v1 · judge-v2"),
            C("prompt_token_count", "bigint", "prompt tokens"),
            C("completion_token_count", "bigint", "completion tokens"),
            C("latency_seconds", "double", "seconds for the call"),
            C("is_simulated", "boolean", "true for the simulated judge"),
            C("is_api_error", "boolean", "endpoint failed after retries; asked again next run"),
        ]),
    "judge_metric": Table(
        "judge", "One per system and README metric", "Judge scorecard: overwrite", [
            C("system_name", "string", "as in fact_chart_answer", "PK"),
            C("group_name", "string", "README group, e.g. Trained AI on the note"),
            C("metric_code", "string", "correct · unsafe_rate · sensitivity · …", "PK"),
            C("metric_name", "string", "the metric's README name"),
            C("vs_truth_ratio", "double", "against the generator's truth (as in the README)"),
            C("vs_truth_judged_ratio", "double", "against truth, on charts the judge answered"),
            C("vs_judge_ratio", "double", "with the judge's status as reference"),
            C("difference_ratio", "double", "vs_judge − vs_truth"),
            C("judged_count", "bigint", "charts with a judge answer"),
            C("corrected_accuracy_ratio", "double", "Rogan-Gladen corrected accuracy from verdicts"),
            C("ci_low_ratio", "double", "95% interval, low"),
            C("ci_high_ratio", "double", "95% interval, high"),
            C("judged_correct_ratio", "double", "share the judge called correct"),
            C("verdict_sensitivity_ratio", "double", "verdicts vs truth: sensitivity"),
            C("verdict_specificity_ratio", "double", "verdicts vs truth: specificity"),
        ]),
    "judge_agreement": Table(
        "judge", "One per slice: the judge's status against the truth", "Judge scorecard: overwrite", [
            C("slice_group_code", "string", "all · truth_status · difficulty", "PK"),
            C("slice_value_code", "string", "e.g. L3", "PK"),
            C("slice_name", "string", "display name"),
            C("chart_count", "bigint", "charts in the slice"),
            C("coverage_ratio", "double", "share the judge answered"),
            C("agreement_ratio", "double", "agreement with truth"),
            C("ci_low_ratio", "double", "95% interval, low"),
            C("ci_high_ratio", "double", "95% interval, high"),
            C("kappa_coef", "double", "Cohen's kappa"),
        ]),
    "judge_cost": Table(
        "judge", "One per call type: status · verdict · all", "Judge scorecard: overwrite", [
            C("call_kind_code", "string", "status · verdict · all", "PK"),
            C("call_count", "bigint", "calls made"),
            C("chart_count", "bigint", "charts covered"),
            C("endpoint_error_count", "bigint", "calls the endpoint failed"),
            C("gate_failure_count", "bigint", "answers that failed the quote gate"),
            C("prompt_token_count", "bigint", "prompt tokens"),
            C("completion_token_count", "bigint", "completion tokens"),
            C("cost_usd", "double", "US$ at the endpoint's list price"),
            C("cost_per_chart_usd", "double", "US$ per chart"),
            C("avg_latency_seconds", "double", "mean seconds per answered call"),
            C("p50_latency_seconds", "double", "median seconds"),
            C("p95_latency_seconds", "double", "95th percentile seconds"),
        ]),
    "deid_score": Table(
        "deid", "One per de-identification engine and test tier", "Judge scorecard: overwrite, from data/deid/scores.csv", [
            C("engine_name", "string", "de-identification engine", "PK"),
            C("tier_code", "string", "easy · hard · unseen · external · jsl48 · all", "PK"),
            C("note_count", "bigint", "notes in the tier"),
            C("phi_count", "bigint", "PHI spans"),
            C("entity_recall_ratio", "double", "PHI entities caught"),
            C("char_recall_ratio", "double", "PHI characters caught"),
            C("char_precision_ratio", "double", "removed characters that were PHI"),
            C("decoy_damage_ratio", "double", "clinical decoys wrongly removed"),
            C("hard_negative_count", "bigint", "hard negatives in the tier"),
            C("hard_negative_damage_ratio", "double", "hard negatives wrongly removed"),
            C("token_precision_ratio", "double", "token-level precision"),
            C("token_recall_ratio", "double", "token-level recall"),
            C("token_f1_ratio", "double", "token-level F1"),
            C("leaked_phi_per_1k_note_rate", "double", "PHI left per thousand notes"),
            C("avg_note_char_count", "double", "mean note length"),
            C("group_name", "string", "engine family (readme_results.deid_group)"),
        ]),
    "judge_queue": Table(
        "corpus", "One per prediction sampled for the corpus judge (stratified by method)", "built by hand; read by the LLM judge job", [
            C("method_name", "string", "method (rung)", "PK,FK"),
            C("visit_id", "bigint", "chart or note", "PK,FK"),
            C("note_text", "string", "de-identified note, through the leak gate"),
            C("predicted_status_code", "string", "the method's status, to judge"),
        ]),
    "fact_corpus_judge_call": Table(
        "corpus", "One per corpus judge call (ai_query)", "LLM judge (02_llm_judge.sql): create or replace", [
            C("method_name", "string", "method (rung)", "PK,FK"),
            C("visit_id", "bigint", "chart or note", "PK,FK"),
            C("predicted_status_code", "string", "the status judged"),
            C("verdict_code", "string", "correct · incorrect · not_determinable"),
            C("supported_status_code", "string", "the status the judge says the note supports"),
            C("quote_text", "string", "verbatim from the note"),
            C("rationale_text", "string", "the judge's reason"),
            C("is_gate_ok", "boolean", "quote gate and schema check passed"),
            C("error_text", "string", "ai_query error"),
            C("prompt_version_code", "string", "judge-v2"),
            C("judge_model_name", "string", "serving endpoint"),
        ]),
    # spec 019: the EHR DQ grader (Load results overwrites each from committed CSVs on every run)
    "dq_check": Table(
        "dq", "One per (data-quality check, clinic); clinic_code All = every clinic", "Load results: overwrite", [
            C("check_name", "string", "e.g. plausibility:temporal_stage_drop"),
            C("check_category_code", "string", "conformance · completeness · plausibility"),
            C("checked_count", "bigint", "rows the check looked at"),
            C("failed_count", "bigint", "rows that failed it"),
            C("pass_ratio", "double", "1 - failed / checked"),
            C("check_status_code", "string", "PASS (none allowed, none found) · REPORT (a rate to read)"),
            C("clinic_code", "string", "1-8, or All"),
            *DQ_PROV]),
    "dq_column_missing": Table(
        "dq", "One per evidence column", "Load results: overwrite", [
            C("evidence_column_name", "string", "column of the structured record"),
            C("row_count", "bigint", "visits"),
            C("missing_count", "bigint", "visits where it is empty"),
            C("missing_pct", "double", "missing / visits, 0-100"),
            *DQ_PROV]),
    "dq_prevalence": Table(
        "dq", "One per (method, clinic or scale)", "Load results: overwrite", [
            C("method_name", "string", "status source: algorithm_design, notes, truth_status, ..."),
            C("level_code", "string", "clinic · scale"),
            C("group_name", "string", "clinic 1-8, or all_visits · complete_cases · reference_set"),
            C("subject_count", "bigint", "people (clinic) or visits with a status (scale)"),
            C("periodontitis_ratio", "double", "share with periodontitis"),
            C("periodontitis_ci_low_ratio", "double", "95% interval, low (clinic rows)"),
            C("periodontitis_ci_high_ratio", "double", "95% interval, high (clinic rows)"),
            C("stage3_4_ratio", "double", "share with stage III-IV"),
            *DQ_PROV]),
    "dq_temporal_change": Table(
        "dq", "One per method", "Load results: overwrite", [
            C("method_name", "string", "status source"),
            C("later_visit_count", "bigint", "visits after a patient's first"),
            C("perio_resolved_ratio", "double", "later visits where periodontitis disappeared"),
            C("stage_drop_ratio", "double", "later visits where the stage dropped"),
            C("visit_pair_count", "bigint", "pairs 1-2 years apart, no treatment between"),
            C("better_ratio", "double", "pairs whose stage improved: implausible"),
            C("same_ratio", "double", "pairs with the same stage"),
            C("worse_ratio", "double", "pairs whose stage worsened"),
            *DQ_PROV]),
    "dq_stage_transition": Table(
        "dq", "One per (method, stage at a visit, stage at the next)", "Load results: overwrite", [
            C("method_name", "string", "algorithm_design"),
            C("from_status_code", "string", "stage at the earlier visit"),
            C("to_status_code", "string", "stage at the next"),
            C("visit_pair_count", "bigint", "visit pairs"),
            C("row_pct", "double", "share of the earlier stage's pairs, 0-100"),
            C("direction_code", "string", "better · same · worse"),
            *DQ_PROV]),
    "dq_source_concordance": Table(
        "dq", "One per (pair of evidence sources, level)", "Load results: overwrite", [
            C("method_a_name", "string", "first source"),
            C("method_b_name", "string", "second source"),
            C("visit_count", "bigint", "visits where both give a value"),
            C("agreement_ratio", "double", "share that agree"),
            C("kappa_coef", "double", "Cohen's kappa"),
            C("level_code", "string", "status · stage · ..."),
            *DQ_PROV]),
    "fact_visit_evidence": Table(
        "dq", "One per synthetic visit: each evidence source's status and the truth (statuses only, never note text)",
        "Load results: overwrite", [
            C("visit_id", "bigint", "visit", "PK"),
            C("person_id", "bigint", "patient"),
            C("visit_date", "date", "date of the visit (synthetic)"),
            C("visit_seq_num", "bigint", "0 = the patient's first visit"),
            C("is_in_review", "boolean", "one of the 240 review charts"),
            C("note_status_code", "string", "status read from the chart note"),
            C("exam_form_status_code", "string", "from the exam form; unknown when missing"),
            C("dx_completed_status_code", "string", "from diagnosis codes on completed procedures"),
            C("dx_planned_status_code", "string", "from diagnosis codes on planned procedures"),
            C("probing_chart_status_code", "string", "from gum measurements; unknown when not charted"),
            C("rules_v0_status_code", "string", "rules, gum measurements first"),
            C("rules_design_status_code", "string", "rules in the study design's order"),
            C("truth_status_code", "string", "the generator's truth"),
            C("clinic_code", "string", "clinic 1-8"),
            *DQ_PROV]),
    "dq_injected_error": Table(
        "dq", "One row: charting errors injected into the synthetic data and how many the checks catch",
        "Load results: overwrite", [
            C("injected_error_count", "bigint", "errors injected"),
            C("caught_ratio", "double", "share the temporal checks flag"),
            C("false_flag_ratio", "double", "visits flagged with no error injected"),
            *DQ_PROV]),
    # spec 026: case profiles, KEEPER-style (Schuemie, Ostropolets et al. 2025)
    "fact_case_profile_item": Table(
        "dq", "One per (synthetic visit, profile category, item): the visit's structured evidence, never note text",
        "Load results: overwrite", [
            C("visit_id", "bigint", "visit", "PK"),
            C("category_name", "string", "Demographics · Presentation · Visit context · Measurements · Tests and "
              "imaging · Risk factors · Treatment · Other readings · After the visit"),
            C("category_order_num", "bigint", "1 = Demographics, shown first"),
            C("item_name", "string", "what the row shows, e.g. max attachment loss (CAL)", "PK"),
            C("item_order_num", "bigint", "position in the profile"),
            C("item_value_name", "string", "the value as shown: a number, a status code, yes/no, or not recorded"),
            C("item_unit_name", "string", "mm, %, years, teeth; empty when none"),
            *DQ_PROV]),
    "fact_record_mismatch": Table(
        "dq", "One per (synthetic visit, failed record-mismatch rule): a recorded code that doesn't fit the record",
        "Load results: overwrite", [
            C("visit_id", "bigint", "visit", "PK"),
            C("rule_name", "string", "code_vs_chart · code_above_chart · code_below_chart · no_periodontal_care · "
              "code_vs_radiograph · stage_drop", "PK"),
            C("rule_label_name", "string", "the rule in plain words"),
            C("mismatch_evidence_text", "string", "the values that triggered it"),
            C("related_visit_id", "bigint", "stage drops: the earlier visit with the higher code; else null"),
            C("failed_rule_count", "bigint", "how many rules this visit fails: the visits failing most come first"),
            C("clinic_code", "string", "clinic 1-8"),
            C("is_injected_error", "boolean", "the visit carries an injected charting error (synthetic answer key)"),
            *DQ_PROV]),
    "dq_mismatch_rule": Table(
        "dq", "One per (record-mismatch rule or any_rule, clinic); clinic_code All = every clinic. Scored against "
        "the generator's truth over the visits the rule can check", "Load results: overwrite", [
            C("rule_name", "string", "a rule, or any_rule", "PK"),
            C("rule_label_name", "string", "the rule in plain words"),
            C("clinic_code", "string", "clinic 1-8, or All", "PK"),
            C("checkable_count", "bigint", "visits with a code and the evidence the rule needs"),
            C("not_checkable_count", "bigint", "visits with a code but missing that evidence"),
            C("flagged_count", "bigint", "checkable visits the rule flags"),
            C("code_truth_mismatch_count", "bigint", "checkable visits whose code differs from the truth (stage "
              "drops: either visit's)"),
            C("true_flag_count", "bigint", "flags where the code differs from the truth"),
            C("precision_ratio", "double", "true flags / flags"),
            C("recall_ratio", "double", "true flags / code-truth mismatches"),
            C("only_rule_count", "bigint", "flags at visits failing no other rule"),
            C("injected_checkable_count", "bigint", "checkable visits with an injected charting error"),
            C("injected_caught_count", "bigint", "of those, flagged"),
            *DQ_PROV]),
    # spec 019: the lab grader (a SIMULATED sample until real runs exist)
    "dim_grader_question": Table(
        "lab", "One per grader question", "Load results: overwrite", [
            C("question_id", "string", "q001 ...", "PK"),
            C("category_name", "string", "Access to care · Clinical cases · Medical-dental integration · ..."),
            C("category_order_num", "bigint", "1 = access to care, shown first"),
            C("level_code", "string", "L1 recall · L2 routine reasoning · L3 individualized reasoning"),
            C("key_point_count", "bigint", "key points a full answer covers"),
            C("source_text", "string", "the published evidence behind the question"),
            C("is_simulated", "boolean", "true for the simulated sample"),
            *DQ_PROV]),
    "fact_grader_answer": Table(
        "lab", "One per (question, model, with or without the agent, run)", "Load results: overwrite", [
            C("question_id", "string", "question", "FK"),
            C("model_name", "string", "model answering; sim: names in the sample"),
            C("is_with_agent", "boolean", "answered with the open agent"),
            C("covered_key_point_count", "bigint", "key points the answer covered"),
            C("score_ratio", "double", "covered / key points"),
            C("harm_code", "string", "S0 safe · S1 reversible harm · S2 irreversible harm"),
            C("cost_usd", "double", "cost of the answer"),
            C("judge_model_name", "string", "judge; never a family under test"),
            C("run_id", "string", "the grading run"),
            C("is_simulated", "boolean", "true for the simulated sample"),
            *DQ_PROV]),
    # spec 027 US5: the pipeline doctor (run metadata only, never note text)
    "fact_pipeline_run": Table(
        "ops", "One per finished run of a bundle job (step_name job), from system.lakeflow.job_run_timeline and the "
        "span export", "Pipeline doctor: delete-then-append by run_id", [
            C("pipeline_name", "string", "the job's key in the bundle (ops/pipeline_config.yaml)", "FK"),
            C("step_name", "string", "job (the whole run), or a step from the span export"),
            C("run_id", "string", "Databricks job run id", "PK"),
            C("started_ts", "timestamp", "run start (UTC)"),
            C("ended_ts", "timestamp", "run end (UTC)"),
            C("run_status_code", "string", "ok · failed · timed_out"),
            C("row_in_count", "bigint", "rows read (span export)"),
            C("row_out_count", "bigint", "rows written (span export)"),
            C("schema_sha256", "string", "hash of the output schema (span export)"),
            C("check_passed_count", "bigint", "data-quality checks passed (span export)"),
            C("check_failed_count", "bigint", "data-quality checks failed (span export)"),
            C("error_type_name", "string", "exception type (span export), else the run's termination code"),
            C("error_text", "string", "first line of the error (span export); never row data"),
            C("duration_seconds", "double", "run length"),
            C("cost_usd", "double", "run cost (span export)"),
            C("git_commit_sha", "string", "commit the pipeline ran (span export)"),
            C("data_label_code", "string", "synthetic · public · simulated, from the pipeline's config"),
            *DOCTOR_PROV]),
    "fact_pipeline_signal": Table(
        "ops", "One per run in the doctor's lookback window: its six signals against the pipeline's runs before it",
        "Pipeline doctor: delete-then-append by run_id", [
            C("pipeline_name", "string", "pipeline", "FK"),
            C("step_name", "string", "as fact_pipeline_run"),
            C("run_id", "string", "Databricks job run id", "PK,FK"),
            C("started_ts", "timestamp", "run start (UTC)"),
            C("run_status_code", "string", "ok · failed · timed_out"),
            C("freshness_seconds", "double", "seconds since the pipeline's last ok run ended"),
            C("sla_seconds", "double", "how stale its output may be (ops/pipeline_config.yaml)"),
            C("volume_ratio", "double", "rows out / trailing median of the last 5 ok runs"),
            C("is_schema_changed", "boolean", "schema hash differs from the last ok run; null when unknown"),
            C("quality_ratio", "double", "share of data-quality checks passed"),
            C("duration_ratio", "double", "duration / trailing median"),
            C("cost_ratio", "double", "cost / trailing median"),
            *DOCTOR_PROV]),
    "fact_remediation_decision": Table(
        "ops", "One per failed run: the doctor's recommendation and, once given, the owner's decision",
        "Pipeline doctor: delete-then-append by run_id, decisions carried forward", [
            C("pipeline_name", "string", "pipeline", "FK"),
            C("run_id", "string", "the failed run", "PK,FK"),
            C("run_started_ts", "timestamp", "when that run started"),
            C("failure_class_code", "string", "credential_expiry · platform · schema_drift · ... · unknown (ops/runbook.yaml)"),
            C("rule_name", "string", "the rule that fired (doctor.classify)"),
            C("recommended_action_code", "string", "first allowed runbook action for the class"),
            C("is_reversible", "boolean", "the runbook entry is reversible: it can graduate to automatic"),
            C("severity_code", "string", "SEV1-SEV4 from the runbook"),
            C("owner_name", "string", "who is told (ops/pipeline_config.yaml)"),
            C("impact_text", "string", "outputs and consumers one hop down the lineage"),
            C("notification_text", "string", "templated notification: names and codes, no row data"),
            C("run_mode_code", "string", "recommend_only · automatic (doctor.graduation on past decisions)"),
            C("decided_action_code", "string", "the owner's decision (job parameter); null until given"),
            C("decided_by_name", "string", "who decided"),
            C("decided_ts", "timestamp", "when the decision was recorded"),
            C("is_match", "boolean", "decided = recommended; null until decided"),
            *DOCTOR_PROV]),
    # spec 029 US3 (#371): in health_transformation_lab.gold_opendental_perio, not gold_perio_bench
    "fact_tooth_loss_prediction": Table(
        "tooth", "Schema gold_opendental_perio. One per (synthetic patient, missing or labelled tooth, label set, "
        "feature set, model, run): "
        "P(the tooth was lost to periodontitis)",
        "Load Open Dental (12_load_open_dental.py): delete-then-append by run_id", [
            C("patient_id", "bigint", "Open Dental PatNum (synthetic)", "PK"),
            C("tooth_num", "bigint", "universal tooth number 1-32", "PK"),
            C("tooth_status_code", "string", "how the tooth left the record (silver patient_tooth)"),
            C("label_set_code", "string", "completed · completed_planned (FR-010)", "PK"),
            C("feature_set_code", "string", "shared (applied model) · own (with the tooth's own measures)", "PK"),
            C("model_name", "string", "logistic · xgboost", "PK"),
            C("split_code", "string", "train · test (held-out patients) · applied (no recorded reason)"),
            C("perio_loss_probability_ratio", "double", "P(lost to periodontitis), 0 to 1"),
            C("threshold_ratio", "double", "the fixed threshold, 0.5"),
            C("is_predicted_perio_loss", "boolean", "probability at or above the threshold"),
            C("generator_seed_num", "bigint", "seed of the synthetic extract"),
            C("is_synthetic", "boolean", "always true: synthetic data only"),
            C("run_id", "string", "Databricks job run id: the batch key", "PK"),
            C("run_ts", "timestamp", "when the job ran"),
            C("git_commit_sha", "string", "commit the job was deployed from"),
        ]),
    # spec 031: the Benchmark job (study_benchmark, 01_run_benchmark.py); synthetic study notes and their scores
    "dim_study_note": Table(
        "study", "One per synthetic study note, with its generator label and split", "Benchmark: overwrite", [
            C("note_id", "bigint", "OMOP note_id (= visit_occurrence_id)", "PK"),
            C("person_id", "bigint", "OMOP person_id; the split is by person"),
            C("note_text", "string", "the synthetic SOAP note"),
            C("truth_status_code", "string", "the generator's label, one of six"),
            C("max_probing_depth_mm", "double", "deepest probing depth on the chart"),
            C("bop_pct", "double", "sites bleeding on probing"),
            C("max_cal_mm", "double", "greatest clinical attachment loss"),
            C("rbl_pct", "double", "radiographic bone loss"),
            C("perio_lost_tooth_count", "bigint", "teeth lost to periodontitis"),
            C("split_code", "string", "train · test"),
            C("run_id", "string", "Databricks job run that built it"),
            C("run_ts", "timestamp", "when that run wrote it"),
            C("git_commit_sha", "string", "commit the job was deployed from"),
        ]),
    "benchmark_metric": Table(
        "study", "One per job run, model fit, metric and class (class empty for overall metrics)",
        "Benchmark: replace by run_id (delete-then-append)", [
            C("model_run_id", "string", "one model fit (eval/score.py run_id)", "PK"),
            C("method_name", "string", "method (rung), e.g. tfidf_logreg"),
            C("language_code", "string", "python · r"),
            C("metric_code", "string", "macro_f1 · f1 · sensitivity · specificity · ppv · npv · auroc", "PK"),
            C("class_status_code", "string", "the status an f1 row is for; empty for the others", "PK"),
            C("metric_ratio", "double", "the metric's value, 0 to 1; null when undefined"),
            C("test_note_count", "bigint", "notes in the test split"),
            C("scored_ts", "timestamp", "when the fit was scored"),
            C("run_id", "string", "Databricks job run: the batch key", "PK"),
            C("run_ts", "timestamp", "when that run wrote it"),
            C("git_commit_sha", "string", "commit the job was deployed from"),
        ]),
}

R = Relationship
RELATIONSHIPS = [
    # the reader job's own rows (source_code databricks) carry their scratch CSV's sha256 but have no dim_result_file row
    R("dim_result_file", "fact_prediction", ("file_sha256",), ("file_sha256",), "file_sha256 (repo · kaggle rows)", "|o--o{"),
    R("dim_result_file", "fact_llm_call", ("file_sha256",), ("file_sha256",), "file_sha256 (repo · kaggle rows)", "|o--o{"),
    R("fact_prediction", "fact_llm_call", ("method_name", "visit_id", "source_code"),
      ("method_name", "visit_id", "source_code"), "method_name, visit_id, source_code (per version or run)", "}o..o{", derived=True),
    R("review_key", "fact_prediction", ("visit_id",), ("visit_id",), "visit_id"),
    R("review_key", "fact_llm_call", ("visit_id",), ("visit_id",), "visit_id"),
    R("review_key", "fact_chart_answer", ("visit_id",), ("visit_id",), "visit_id"),
    R("fact_judge_call", "fact_chart_answer", ("visit_id", "answer_status_code"), ("visit_id", "answer_status_code"),
      "visit_id, answer_status_code", "|o--o{"),
    R("judge_cost", "fact_judge_call", ("call_kind_code",), ("call_kind_code",), "call_kind_code", "||..o{", derived=True),
    R("fact_judge_call", "judge_agreement", (), (), "status calls summarised", "}o..o{", derived=True),
    R("fact_chart_answer", "judge_metric", ("system_name",), ("system_name",), "system_name", "}o..o{", derived=True),
    R("fact_prediction", "fact_chart_answer", ("method_name",), ("system_name",), "method_name = system_name",
      "}o..o{", derived=True),
    R("fact_prediction", "judge_queue", ("method_name", "visit_id"), ("method_name", "visit_id"),
      "sampled from", "||..o|", derived=True),
    R("judge_queue", "fact_corpus_judge_call", ("method_name", "visit_id"), ("method_name", "visit_id"),
      "method_name, visit_id", "||--o|"),
    R("dim_grader_question", "fact_grader_answer", ("question_id",), ("question_id",), "question_id"),
    R("fact_visit_evidence", "fact_case_profile_item", ("visit_id",), ("visit_id",), "visit_id"),
    R("fact_visit_evidence", "fact_record_mismatch", ("visit_id",), ("visit_id",), "visit_id"),
    R("fact_record_mismatch", "dq_mismatch_rule", ("rule_name",), ("rule_name",),
      "rule_name (scores are per rule and clinic: join on clinic_code too)", "}o..o{", derived=True),
    R("fact_pipeline_run", "fact_pipeline_signal", ("run_id",), ("run_id",), "run_id", "||--o|"),
    R("fact_pipeline_run", "fact_remediation_decision", ("run_id",), ("run_id",), "run_id (failed runs)", "||--o|"),
    R("dim_study_note", "benchmark_metric", ("run_id",), ("run_id",), "run_id (its test split)",
      "}o..o{", derived=True),
]

AREAS = {   # fill, legend label
    "results": ("#FFF4C2", "gold · results from anywhere (spec 016)"),
    "judge": ("#EFE9FB", "gold · judge scorecard (spec 012)"),
    "deid": ("#E3F1E4", "gold · de-identification benchmark"),
    "corpus": ("#FDE7F1", "gold · corpus judge (ai_query, notebook 02)"),
    "dq": ("#E1EEF6", "gold · EHR DQ grader (spec 019)"),
    "lab": ("#F6E7DE", "gold · lab grader, simulated sample (spec 019)"),
    "ops": ("#ECEFD9", "gold · pipeline doctor, run metadata (spec 027)"),
    "tooth": ("#E8F0DC", "gold_opendental_perio · tooth-loss model, synthetic (spec 029)"),
    "study": ("#EDEDF7", "gold · Benchmark job, synthetic study notes (spec 031)"),
    "file": ("#E4E7EA", "file in git, not a table"),
}
