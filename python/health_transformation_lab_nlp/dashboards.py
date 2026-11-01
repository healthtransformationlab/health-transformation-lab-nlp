"""The grader dashboards (spec 019), built as Databricks AI/BI `.lvdash.json` from Python, so widgets and their
datasets are wired in one place instead of hand-edited JSON.

    python scripts/42_build_dashboards.py           # write databricks/dashboards/<name>.lvdash.json
    python scripts/42_build_dashboards.py --check   # exit 1 if a committed dashboard is stale

The grid is 6 columns wide. Datasets read health_transformation_lab.gold_perio_bench, the same names in every target, and
keep to SQL that DuckDB also runs, so the tests can run every query on the tables grader_tables builds.
"""

from __future__ import annotations

import hashlib
import json

from .telemetry import traced

GOLD = "health_transformation_lab.gold_perio_bench"


def _lines(text: str) -> list[str]:
    return [line + "\n" for line in text.strip("\n").split("\n")]


def _dataset(name: str, sql: str) -> dict:
    return {"name": name, "displayName": name, "queryLines": _lines(sql.replace("{gold}", GOLD))}


def _at(x, y, w, h) -> dict:
    return {"x": x, "y": y, "width": w, "height": h}


def _frame(title: str, description: str = "") -> dict:
    f = {"showTitle": True, "title": title}
    if description:
        f.update(showDescription=True, description=description)
    return f


def _text(name, markdown, pos) -> dict:
    return {"widget": {"name": name, "multilineTextboxSpec": {"lines": _lines(markdown)}}, "position": _at(*pos)}


def _fields(*cols, agg=None) -> list[dict]:
    """Plain columns, plus (name, expression) pairs for aggregates."""
    out = [{"name": c, "expression": f"`{c}`"} for c in cols]
    return out + [{"name": n, "expression": e} for n, e in (agg or [])]


def _counter(name, ds, field, title, description, pos) -> dict:
    return {"widget": {"name": name, "queries": [{"name": "main_query", "query": {
        "datasetName": ds, "fields": _fields(field), "disaggregated": True}}],
        "spec": {"version": 2, "widgetType": "counter", "encodings": {
            "value": {"fieldName": field, "displayName": title}}, "frame": _frame(title, description)}},
        "position": _at(*pos)}


def _table(name, ds, columns, title, description, pos) -> dict:
    """columns: (field, display name) pairs."""
    return {"widget": {"name": name, "queries": [{"name": "main_query", "query": {
        "datasetName": ds, "fields": _fields(*[c for c, _ in columns]), "disaggregated": True}}],
        "spec": {"version": 2, "widgetType": "table", "encodings": {
            "columns": [{"fieldName": c, "displayName": d} for c, d in columns]},
            "frame": _frame(title, description)}}, "position": _at(*pos)}


def _bar(name, ds, x, y, title, description, pos, *, agg=None, x_title="", y_title="", color=None) -> dict:
    """x categorical; y a column, or (field, aggregate expression) when the dataset is row level."""
    y_field, y_expr = (y, None) if isinstance(y, str) else y
    fields = _fields(x, *([color] if color else []), *([] if y_expr else [y_field]),
                     agg=[(y_field, y_expr)] if y_expr else None)
    enc = {"x": {"fieldName": x, "scale": {"type": "categorical"}, "displayName": x_title or x},
           "y": {"fieldName": y_field, "scale": {"type": "quantitative"}, "displayName": y_title or y_field}}
    if color:
        enc["color"] = {"fieldName": color, "scale": {"type": "categorical"}, "displayName": color}
    return {"widget": {"name": name, "queries": [{"name": "main_query", "query": {
        "datasetName": ds, "fields": fields, "disaggregated": not y_expr}}],
        "spec": {"version": 3, "widgetType": "bar", "encodings": enc, "frame": _frame(title, description)}},
        "position": _at(*pos)}


def _heatmap(name, ds, x, y, value, title, description, pos, *, x_title="", y_title="", value_title="") -> dict:
    return {"widget": {"name": name, "queries": [{"name": "main_query", "query": {
        "datasetName": ds, "fields": _fields(x, y, value), "disaggregated": True}}],
        "spec": {"version": 3, "widgetType": "heatmap", "encodings": {
            "x": {"fieldName": x, "scale": {"type": "categorical"}, "displayName": x_title or x},
            "y": {"fieldName": y, "scale": {"type": "categorical"}, "displayName": y_title or y},
            "color": {"fieldName": value, "scale": {"type": "quantitative"}, "displayName": value_title or value}},
            "frame": _frame(title, description)}}, "position": _at(*pos)}


def _scatter(name, ds, x, y, color, title, description, pos, *, x_title="", y_title="") -> dict:
    return {"widget": {"name": name, "queries": [{"name": "main_query", "query": {
        "datasetName": ds, "fields": _fields(x, y, color), "disaggregated": True}}],
        "spec": {"version": 3, "widgetType": "scatter", "encodings": {
            "x": {"fieldName": x, "scale": {"type": "quantitative"}, "displayName": x_title or x},
            "y": {"fieldName": y, "scale": {"type": "quantitative"}, "displayName": y_title or y},
            "color": {"fieldName": color, "scale": {"type": "categorical"}, "displayName": color}},
            "frame": _frame(title, description)}}, "position": _at(*pos)}


def _filter(name, field, datasets, title, pos, widget_type="filter-multi-select") -> dict:
    queries = [{"name": f"f_{name}_{ds}", "query": {"datasetName": ds, "fields": _fields(field),
                                                    "disaggregated": False}} for ds in datasets]
    return {"widget": {"name": name, "queries": queries, "spec": {
        "version": 2, "widgetType": widget_type, "encodings": {"fields": [
            {"fieldName": field, "displayName": title, "queryName": q["name"]} for q in queries]},
        "frame": _frame(title)}}, "position": _at(*pos)}


# ---------------------------------------------------------------- EHR DQ grader (spec 019 US2)

# each evidence source as the study names it, and its plain name (evidence_rules.md)
SOURCES = [("exam_form_status_code", "Exam form"), ("dx_completed_status_code", "Diagnosis codes, done"),
           ("dx_planned_status_code", "Diagnosis codes, planned"), ("note_status_code", "Chart note"),
           ("probing_chart_status_code", "Gum measurements"), ("rules_v0_status_code", "Rules, measurements first (v0)"),
           ("rules_design_status_code", "Rules, exam form first (design)")]

# gold names (AGENTS.md "SQL and data names"); the output aliases are the widgets' field names
DQ_SQL = {
    "tiles": """
SELECT
  ROUND(100 * AVG(CASE WHEN exam_form_status_code <> 'unknown' AND dx_completed_status_code <> 'unknown'
                        AND probing_chart_status_code <> 'unknown' THEN 1.0 ELSE 0.0 END), 1) AS completeness_pct,
  ROUND(100 * AVG(CASE WHEN rules_v0_status_code = truth_status_code THEN 1.0 ELSE 0.0 END), 1) AS accuracy_pct,
  ROUND(100 * AVG(CASE WHEN rules_design_status_code = truth_status_code THEN 1.0 ELSE 0.0 END), 1)
    AS accuracy_design_pct,
  (SELECT ROUND(100 * (MAX(periodontitis_ratio) - MIN(periodontitis_ratio)), 1) FROM {gold}.dq_prevalence
    WHERE level_code = 'clinic' AND method_name = 'algorithm_design') AS consistency_pts,
  (SELECT ROUND(100 * better_ratio, 1) FROM {gold}.dq_temporal_change WHERE method_name = 'algorithm_design')
    AS implausible_pct,
  COUNT(*) AS n_visits
FROM {gold}.fact_visit_evidence""",
    "missingness": """
SELECT evidence_column_name AS evidence_column, ROUND(missing_pct, 1) AS pct_missing, missing_count AS n_missing,
  row_count AS n_rows
FROM {gold}.dq_column_missing
ORDER BY missing_pct DESC""",
    "checks": """
SELECT clinic_code AS clinic, check_category_code AS category, check_name, checked_count AS n_checked,
  failed_count AS n_fail, ROUND(100 * pass_ratio, 2) AS pass_pct, check_status_code AS status
FROM {gold}.dq_check
ORDER BY CASE WHEN clinic_code = 'All' THEN 0 ELSE 1 END, clinic_code, check_category_code, check_name""",
    "accuracy": "\nUNION ALL\n".join(f"""
SELECT clinic_code AS clinic, '{label}' AS evidence_source,
  CASE WHEN {col} <> 'unknown' THEN 100.0 ELSE 0.0 END AS answered_pct,
  CASE WHEN {col} = 'unknown' THEN NULL WHEN {col} = truth_status_code THEN 100.0 ELSE 0.0 END AS agree_pct
FROM {{gold}}.fact_visit_evidence""" for col, label in SOURCES),
    "concordance": """
SELECT method_a_name AS method_a, method_b_name AS method_b, ROUND(100 * agreement_ratio, 1) AS pct_agree,
  ROUND(kappa_coef, 2) AS kappa, visit_count AS n
FROM {gold}.dq_source_concordance
WHERE level_code = 'status'""",
    "prevalence_clinic": """
SELECT group_name AS clinic, ROUND(100 * periodontitis_ratio, 1) AS periodontitis_pct,
  ROUND(100 * periodontitis_ci_low_ratio, 1) AS ci_low, ROUND(100 * periodontitis_ci_high_ratio, 1) AS ci_high,
  subject_count AS n
FROM {gold}.dq_prevalence
WHERE level_code = 'clinic' AND method_name = 'algorithm_design'
ORDER BY group_name""",
    "prevalence_scale": """
SELECT method_name AS method, group_name AS scale, subject_count AS n,
  ROUND(100 * periodontitis_ratio, 1) AS periodontitis_pct, ROUND(100 * stage3_4_ratio, 1) AS stage3_4_pct
FROM {gold}.dq_prevalence
WHERE level_code = 'scale'
ORDER BY method_name, group_name""",
    "transitions": """
SELECT from_status_code AS from_status, to_status_code AS to_status, visit_pair_count AS n,
  ROUND(row_pct, 1) AS row_pct, direction_code AS direction
FROM {gold}.dq_stage_transition""",
    "temporal": """
SELECT method_name AS method, visit_pair_count AS pairs, ROUND(100 * better_ratio, 1) AS improved_pct,
  ROUND(100 * same_ratio, 1) AS same_pct, ROUND(100 * worse_ratio, 1) AS worse_pct,
  ROUND(100 * perio_resolved_ratio, 1) AS resolved_pct, ROUND(100 * stage_drop_ratio, 1) AS stage_drop_pct
FROM {gold}.dq_temporal_change
ORDER BY improved_pct""",
    "injected": """
SELECT injected_error_count AS injected_errors, ROUND(100 * caught_ratio, 1) AS caught_pct,
  ROUND(100 * false_flag_ratio, 2) AS false_flag_pct
FROM {gold}.dq_injected_error""",
    # spec 026 US3: Records to recheck
    "mismatch_rules": """
SELECT rule_label_name AS rule, clinic_code AS clinic, checkable_count AS checkable, flagged_count AS flagged,
  ROUND(100 * precision_ratio, 1) AS precision_pct, ROUND(100 * recall_ratio, 1) AS recall_pct,
  only_rule_count AS only_this_rule, injected_caught_count AS injected_caught,
  injected_checkable_count AS injected_checkable
FROM {gold}.dq_mismatch_rule
ORDER BY CASE WHEN clinic_code = 'All' THEN 0 ELSE 1 END, clinic_code,
  CASE WHEN rule_name = 'any_rule' THEN 1 ELSE 0 END, rule_name""",
    "mismatch_visits": """
SELECT m.visit_id, m.clinic_code AS clinic, v.visit_date, m.failed_rule_count AS rules_failed,
  m.rule_label_name AS rule, m.mismatch_evidence_text AS evidence
FROM {gold}.fact_record_mismatch m
INNER JOIN {gold}.fact_visit_evidence v ON m.visit_id = v.visit_id
ORDER BY m.failed_rule_count DESC, m.visit_id, m.rule_name""",
    "case_profile": """
WITH flagged AS (SELECT DISTINCT visit_id FROM {gold}.fact_record_mismatch)
SELECT p.visit_id, p.category_name AS category, p.item_name AS item, p.item_value_name AS shown_value,
  p.item_unit_name AS unit, p.category_order_num, p.item_order_num
FROM {gold}.fact_case_profile_item p
INNER JOIN flagged f ON p.visit_id = f.visit_id
ORDER BY p.visit_id, p.category_order_num, p.item_order_num""",
}

DQ_BANNER = """## EHR DQ grader: is this dental record fit for periodontal phenotyping?
**Synthetic data** from the study's generator, scored against its own truth: **not clinical performance**. The
light version of the Perio DQ Monitor design: five domains (Zozus completeness, accuracy and consistency; Kahn
temporal plausibility; reliability after de Vet et al. 2006), then one section per domain. Ask the **EHR DQ grader** Genie space for
anything not shown."""


@traced
def dq_grader() -> dict:
    filtered = ["accuracy", "prevalence_clinic"]          # checks keep their All rows, so they show every clinic
    tiles = [("t_complete", "completeness_pct", "Completeness (%)",
              "Visits with exam form, diagnosis codes and gum measurements all present. All clinics."),
             ("t_accuracy", "accuracy_pct", "Accuracy (%)",
              "Rules on the whole record, measurements first (v0), against the truth, all visits."),
             ("t_consistency", "consistency_pts", "Consistency (points)",
              "Spread of periodontitis prevalence across the 8 clinics (design rules). Smaller is steadier."),
             ("t_temporal", "implausible_pct", "Temporal plausibility (%)",
              "Visit pairs 1–2 years apart, no treatment between, whose stage improved (design rules). Lower is better.")]
    layout = [_text("banner", DQ_BANNER, (0, 0, 6, 3)),
              _filter("f_clinic", "clinic", filtered, "Clinic", (0, 3, 2, 2)),
              _text("how", "Tiles are for all clinics; the clinic filter applies to accuracy by source and "
                           "prevalence. The checks table lists every clinic and All. Per-visit evidence is in "
                           "`fact_visit_evidence` (statuses only, never note text).",
                    (2, 3, 4, 2))]
    layout += [_counter(n, "tiles", f, t, d, (i, 5, 1, 3)) for i, (n, f, t, d) in enumerate(tiles)]
    layout += [_text("t_reliability", "**Reliability** (de Vet)\n\n**Not assessed**: needs real reviewers to label "
                                      "charts. Simulated reviewers are a dry run.", (4, 5, 1, 3)),
               _counter("t_accuracy_design", "tiles", "accuracy_design_pct", "Accuracy, exam form first (%)",
                        "Rules in the study design's order. The order changes the answer.", (5, 5, 1, 3)),
               _text("s_complete", "### Completeness", (0, 8, 6, 1)),
               _bar("b_missing", "missingness", "evidence_column", "pct_missing", "Missing by evidence column (%)",
                    "Share of visits where the column is empty. Diagnosis codes done are missing as often as planned (29.5%); the per-source share answered is under Accuracy.", (0, 9, 3, 6),
                    x_title="Evidence column", y_title="Missing (%)"),
               _table("tb_checks", "checks", [("clinic", "Clinic"), ("category", "Category"),
                                               ("check_name", "Check"), ("n_checked", "Checked"),
                                               ("n_fail", "Failed"), ("pass_pct", "Pass (%)"),
                                               ("status", "Status")],
                      "Conformance, completeness and plausibility checks",
                      "All = every clinic together. PASS: no failures allowed and none found; REPORT: a rate to "
                      "read, with no pass mark.",
                      (3, 9, 3, 6)),
               _text("s_accuracy", "### Accuracy", (0, 15, 6, 1)),
               _bar("b_answered", "accuracy", "evidence_source", ("answered", "AVG(`answered_pct`)"),
                    "Visits each source gives a status for (%)", "", (0, 16, 2, 6),
                    x_title="Evidence source", y_title="Answered (%)"),
               _bar("b_agree", "accuracy", "evidence_source", ("agree", "AVG(`agree_pct`)"),
                    "Agreement with the truth where it answers (%)",
                    "Comparison to truth, the top rung of the accuracy hierarchy.", (2, 16, 2, 6),
                    x_title="Evidence source", y_title="Agrees with truth (%)"),
               _heatmap("h_concord", "concordance", "method_a", "method_b", "pct_agree",
                        "Concordance between sources (%)", "Comparison to independent measurement, truth excluded.",
                        (4, 16, 2, 6), value_title="Agree (%)"),
               _text("s_consistency", "### Consistency", (0, 22, 6, 1)),
               _bar("b_clinic", "prevalence_clinic", "clinic", "periodontitis_pct",
                    "Periodontitis prevalence by clinic (%)", "Design rules; 95% intervals in the table.",
                    (0, 23, 3, 6), x_title="Clinic", y_title="Periodontitis (%)"),
               _table("tb_clinic", "prevalence_clinic", [("clinic", "Clinic"), ("n", "People"),
                                                         ("periodontitis_pct", "Periodontitis (%)"),
                                                         ("ci_low", "95% CI low"), ("ci_high", "95% CI high")],
                      "By clinic, with intervals", "", (3, 23, 1, 6)),
               _table("tb_scale", "prevalence_scale", [("method", "Method"), ("scale", "Scale"), ("n", "Visits"),
                                                       ("periodontitis_pct", "Periodontitis (%)"),
                                                       ("stage3_4_pct", "Stage III–IV (%)")],
                      "By scale: all visits, complete cases, reference set", "", (4, 23, 2, 6)),
               _text("s_temporal", "### Temporal plausibility", (0, 29, 6, 1)),
               _heatmap("h_trans", "transitions", "to_status", "from_status", "row_pct",
                        "Stage at one visit (rows) and the next (columns), % of the row",
                        "Cells where the next visit's stage is lower than the earlier one show improvement: a charting or rule error unless treated.",
                        (0, 30, 3, 7), x_title="Next visit", y_title="Earlier visit", value_title="% of row"),
               _table("tb_temporal", "temporal", [("method", "Method"), ("pairs", "Visit pairs"),
                                                  ("improved_pct", "Improved (%)"), ("same_pct", "Same (%)"),
                                                  ("worse_pct", "Worse (%)"), ("resolved_pct", "Resolved (%)"),
                                                  ("stage_drop_pct", "Stage dropped (%)")],
                      "Implausible change by method", "Lower improved and resolved shares are more plausible.",
                      (3, 30, 3, 4)),
               _table("tb_injected", "injected", [("injected_errors", "Errors injected"),
                                                  ("caught_pct", "Caught (%)"),
                                                  ("false_flag_pct", "Flagged without an error (%)")],
                      "Injected charting errors the temporal checks catch (synthetic only)", "", (3, 34, 3, 3))]
    return {"datasets": [_dataset(n, s) for n, s in DQ_SQL.items()],
            "pages": [{"name": "dq_grader", "displayName": "EHR DQ grader", "pageType": "PAGE_TYPE_CANVAS",
                       "layout": layout},
                      {"name": "records_to_recheck", "displayName": "Records to recheck",
                       "pageType": "PAGE_TYPE_CANVAS", "layout": _recheck_layout()}]}


RECHECK_BANNER = """## Records to recheck
**Synthetic records**, scored against the generator's truth: **not clinical performance**. Each rule asks whether a
visit's recorded code (the completed diagnosis code) fits the rest of its record. A flag is a record mismatch: a
coding or charting gap, not a clinical error. Precision and recall count only the visits a rule can check
(*checkable*); *only this rule* is how many of its flags no other rule makes. Pick a flagged visit to see its case
profile (spec 026, after KEEPER)."""


def _recheck_layout() -> list[dict]:
    return [_text("recheck_banner", RECHECK_BANNER, (0, 0, 6, 3)),
            # the clinic filter leaves the rule scores alone, so their All rows stay (as page 1 keeps its checks')
            _filter("f_recheck_clinic", "clinic", ["mismatch_visits"], "Clinic", (0, 3, 2, 2)),
            _filter("f_rule", "rule", ["mismatch_visits", "mismatch_rules"], "Rule", (2, 3, 2, 2)),
            _filter("f_visit", "visit_id", ["mismatch_visits", "case_profile"], "Visit", (4, 3, 2, 2),
                    widget_type="filter-single-select"),
            _table("tb_rules", "mismatch_rules", [("rule", "Rule"), ("clinic", "Clinic"),
                                                  ("checkable", "Checkable"), ("flagged", "Flagged"),
                                                  ("precision_pct", "Precision (%)"), ("recall_pct", "Recall (%)"),
                                                  ("only_this_rule", "Only this rule"),
                                                  ("injected_caught", "Injected errors caught"),
                                                  ("injected_checkable", "Injected errors checkable")],
                   "Each rule against the truth (synthetic)",
                   "All = every clinic; the clinic filter doesn't apply here, so All always shows. Blank precision "
                   "or recall = the rule flags nothing there. Per-clinic injected-error counts are too few to "
                   "compare.", (0, 5, 6, 6)),
            _table("tb_flagged", "mismatch_visits", [("visit_id", "Visit"), ("clinic", "Clinic"),
                                                     ("visit_date", "Date"), ("rules_failed", "Rules failed"),
                                                     ("rule", "Rule"), ("evidence", "Evidence")],
                   "Flagged visits, most rules failed first",
                   "One row per visit and failed rule. Rules failed counts all of the visit's rules, even when the "
                   "rule filter shows only some of them.", (0, 11, 3, 9)),
            _table("tb_profile", "case_profile", [("visit_id", "Visit"), ("category", "Category"), ("item", "Item"),
                                                  ("shown_value", "Value"), ("unit", "Unit")],
                   "Case profile of the selected visit",
                   "Pick a visit in the Visit filter; until then every flagged visit's profile is listed. "
                   "Structured values only, never note text. Not recorded = the record lacks it.", (3, 11, 3, 9))]


# ---------------------------------------------------------------- Lab grader (spec 019 US4)

MODE = "CASE WHEN ans.is_with_agent THEN 'With the agent' ELSE 'On its own' END"
ANSWERS = "{gold}.fact_grader_answer ans JOIN {gold}.dim_grader_question q ON ans.question_id = q.question_id"

# gold names (AGENTS.md "SQL and data names"); the output aliases are the widgets' field names
LAB_SQL = {
    "status": """
SELECT ROUND(100 * AVG(CASE WHEN is_simulated THEN 1.0 ELSE 0.0 END), 1) AS simulated_pct,
  COUNT(DISTINCT question_id) AS questions, COUNT(DISTINCT model_name) AS models, COUNT(*) AS answers
FROM {gold}.fact_grader_answer""",
    "uplift": f"""
WITH s AS (
  SELECT q.category_name, q.category_order_num,
    AVG(CASE WHEN NOT ans.is_with_agent THEN ans.score_ratio END) AS own,
    AVG(CASE WHEN ans.is_with_agent THEN ans.score_ratio END) AS agent,
    VAR_SAMP(CASE WHEN NOT ans.is_with_agent THEN ans.score_ratio END) AS v_own,
    VAR_SAMP(CASE WHEN ans.is_with_agent THEN ans.score_ratio END) AS v_agent,
    SUM(CASE WHEN NOT ans.is_with_agent THEN 1 ELSE 0 END) AS n_own,
    SUM(CASE WHEN ans.is_with_agent THEN 1 ELSE 0 END) AS n_agent,
    AVG(CASE WHEN NOT ans.is_with_agent THEN ans.cost_usd END) AS cost_own,
    AVG(CASE WHEN ans.is_with_agent THEN ans.cost_usd END) AS cost_agent
  FROM {ANSWERS}
  GROUP BY q.category_name, q.category_order_num)
SELECT category_name AS category, category_order_num AS category_order, ROUND(100 * own, 1) AS own_pct,
  ROUND(100 * agent, 1) AS agent_pct, ROUND(100 * (agent - own), 1) AS uplift_pts,
  ROUND(100 * (agent - own - 1.96 * SQRT(v_own / n_own + v_agent / n_agent)), 1) AS uplift_lo,
  ROUND(100 * (agent - own + 1.96 * SQRT(v_own / n_own + v_agent / n_agent)), 1) AS uplift_hi,
  ROUND(cost_own, 4) AS cost_own_usd, ROUND(cost_agent, 4) AS cost_agent_usd, n_own AS answers_each
FROM s
ORDER BY category_order_num""",
    "leaderboard": f"""
WITH s AS (
  SELECT q.category_name, q.category_order_num, ans.model_name, {MODE} AS answer_mode,
    AVG(ans.score_ratio) AS score, COUNT(*) AS n
  FROM {ANSWERS}
  GROUP BY q.category_name, q.category_order_num, ans.model_name, ans.is_with_agent)
SELECT category_name AS category, category_order_num AS category_order, answer_mode,
  RANK() OVER (PARTITION BY category_name, answer_mode ORDER BY score DESC) AS rank,
  model_name AS model, ROUND(100 * score, 1) AS score_pct, n
FROM s
ORDER BY category_order_num, answer_mode, rank""",
    "safety": f"""
SELECT ans.model_name AS model, {MODE} AS answer_mode,
  ROUND(100 * AVG(CASE WHEN ans.harm_code IN ('S1', 'S2') THEN 1.0 ELSE 0.0 END), 1) AS unsafe_pct,
  ROUND(100 * AVG(CASE WHEN ans.harm_code = 'S2' THEN 1.0 ELSE 0.0 END), 1) AS s2_pct, COUNT(*) AS n
FROM {{gold}}.fact_grader_answer ans
GROUP BY ans.model_name, ans.is_with_agent
ORDER BY model, answer_mode""",
    "by_level": f"""
WITH l AS (
  SELECT ans.model_name, ans.is_with_agent, q.level_code, AVG(ans.score_ratio) AS score
  FROM {ANSWERS}
  GROUP BY ans.model_name, ans.is_with_agent, q.level_code)
SELECT ans.model_name AS model, {MODE} AS answer_mode, ans.level_code AS level,
  ROUND(100 * ans.score, 1) AS score_pct FROM l ans
UNION ALL
SELECT ans.model_name AS model, {MODE} AS answer_mode, 'Macro average' AS level,
  ROUND(100 * AVG(ans.score), 1) AS score_pct
FROM l ans
GROUP BY ans.model_name, ans.is_with_agent""",
    "cost_vs_score": f"""
SELECT ans.model_name || CASE WHEN ans.is_with_agent THEN ' + agent' ELSE '' END AS entry, {MODE} AS answer_mode,
  ROUND(AVG(ans.cost_usd), 4) AS cost_usd, ROUND(100 * AVG(ans.score_ratio), 1) AS score_pct
FROM {{gold}}.fact_grader_answer ans
GROUP BY ans.model_name, ans.is_with_agent""",
}

LAB_BANNER = """## Lab grader: do AI answers improve with an open agent built on public evidence?
**SIMULATED sample: every number on this page is made up, not a result.** It shows the shape of what a real run
brings back (the pitch's uplift and leaderboard slides) until one exists; the *Simulated rows* tile then reads 0.
Practices from GlobalDentBench: five key points per answer, harm graded S0 safe, S1 reversible, S2 irreversible,
reasoning levels L1–L3 macro-averaged, cost per answer, and a judge from a family no model shares."""


@traced
def lab_grader() -> dict:
    by_category = ["uplift", "leaderboard"]
    by_model = ["leaderboard", "safety", "by_level"]
    layout = [_text("banner", LAB_BANNER, (0, 0, 6, 3))]
    layout += [_counter(n, "status", f, t, d, (i, 3, 1, 3)) for i, (n, f, t, d) in enumerate([
        ("c_sim", "simulated_pct", "Simulated rows (%)", "100 until a real run is committed."),
        ("c_q", "questions", "Questions", "About 25 per category: a pilot that shows direction only."),
        ("c_m", "models", "Models", "Each answers every question on its own and with the agent."),
        ("c_a", "answers", "Answers", "Every answer judged on its key points and graded for harm.")])]
    layout += [_filter("f_category", "category", by_category, "Category", (4, 3, 2, 3)),
               _filter("f_model", "model", by_model, "Model", (4, 6, 2, 2)),
               _text("s_uplift", "### Uplift by category, access to care first", (0, 6, 4, 2)),
               _table("tb_uplift", "uplift", [("category", "Category"), ("own_pct", "On its own (%)"),
                                              ("agent_pct", "With the agent (%)"), ("uplift_pts", "Uplift (points)"),
                                              ("uplift_lo", "95% CI low"), ("uplift_hi", "95% CI high"),
                                              ("cost_own_usd", "Cost per answer, own (US$)"),
                                              ("cost_agent_usd", "Cost per answer, agent (US$)"),
                                              ("answers_each", "Answers each")],
                      "Score with and without the agent", "Score = key points covered / key points. Interval: "
                      "answers treated as independent. The uplift can be small, zero or negative.", (0, 8, 6, 5)),
               _text("s_board", "### Leaderboard within each category (never one rank across categories)",
                     (0, 13, 6, 1)),
               _table("tb_board", "leaderboard", [("category", "Category"), ("answer_mode", "Answer"),
                                                  ("rank", "Rank"), ("model", "Model"), ("score_pct", "Score (%)"),
                                                  ("n", "Answers")],
                      "Models ranked within a category", "", (0, 14, 3, 8)),
               _bar("b_board", "leaderboard", "model", "score_pct", "Score by model (%)",
                    "Pick one category with the filter.", (3, 14, 3, 8), color="answer_mode",
                    x_title="Model", y_title="Score (%)"),
               _text("s_safety", "### Safety: unsafe (S1 + S2) and irreversible harm (S2)", (0, 22, 6, 1)),
               _bar("b_unsafe", "safety", "model", "unsafe_pct", "Unsafe answers (%)",
                    "S1 reversible or S2 irreversible harm, graded by clinicians' rules, not by the judge.",
                    (0, 23, 3, 6), color="answer_mode", x_title="Model", y_title="Unsafe (%)"),
               _table("tb_safety", "safety", [("model", "Model"), ("answer_mode", "Answer"),
                                              ("unsafe_pct", "Unsafe, S1+S2 (%)"), ("s2_pct", "Irreversible, S2 (%)"),
                                              ("n", "Answers")], "Harm by model", "", (3, 23, 3, 6)),
               _text("s_level", "### By reasoning level: L1 recall, L2 routine, L3 individualized", (0, 29, 6, 1)),
               _bar("b_level", "by_level", "level", "score_pct", "Score by level (%)",
                    "The macro average weights each level equally, so easy questions don't flatter a model.",
                    (0, 30, 3, 6), color="answer_mode", x_title="Level", y_title="Score (%)"),
               _table("tb_level", "by_level", [("model", "Model"), ("answer_mode", "Answer"), ("level", "Level"),
                                               ("score_pct", "Score (%)")], "By model and level", "", (3, 30, 3, 6)),
               _text("s_cost", "### Cost against score", (0, 36, 6, 1)),
               _scatter("sc_cost", "cost_vs_score", "cost_usd", "score_pct", "answer_mode",
                        "Cost per answer (US$) against score (%)", "One point per model, on its own and with the "
                        "agent.", (0, 37, 4, 6), x_title="Cost per answer (US$)", y_title="Score (%)"),
               _text("t_cost", "In GlobalDentBench (2026), paying more for a model did not reliably buy a better "
                               "answer, so cost sits next to score here.", (4, 37, 2, 6))]
    return {"datasets": [_dataset(n, s) for n, s in LAB_SQL.items()],
            "pages": [{"name": "lab_grader", "displayName": "Lab grader", "pageType": "PAGE_TYPE_CANVAS",
                       "layout": layout}]}


# ---------------------------------------------------------------- Pipeline doctor (spec 027 US5)

SCHEMA_STATE = ("CASE WHEN is_schema_changed THEN 'changed' WHEN NOT is_schema_changed THEN 'same' "
                "ELSE 'unknown' END")

# gold names (AGENTS.md "SQL and data names"); the output aliases are the widgets' field names
DOCTOR_SQL = {
    "tiles": """
SELECT COUNT(DISTINCT pipeline_name) AS pipelines, COUNT(*) AS runs,
  SUM(CASE WHEN run_status_code <> 'ok' THEN 1 ELSE 0 END) AS failed_runs,
  (SELECT COUNT(*) FROM {gold}.fact_remediation_decision WHERE decided_action_code IS NULL) AS awaiting_decision
FROM {gold}.fact_pipeline_signal""",
    "latest_signals": f"""
WITH ranked AS (
  SELECT pipeline_name, run_id, started_ts, run_status_code, freshness_seconds, sla_seconds, volume_ratio,
    is_schema_changed, quality_ratio, duration_ratio, cost_ratio,
    ROW_NUMBER() OVER (PARTITION BY pipeline_name ORDER BY started_ts DESC) AS run_rank
  FROM {{gold}}.fact_pipeline_signal)
SELECT pipeline_name AS pipeline, run_id, started_ts AS started, run_status_code AS status,
  ROUND(freshness_seconds / 3600, 1) AS freshness_hours, ROUND(sla_seconds / 3600, 1) AS sla_hours,
  ROUND(volume_ratio, 2) AS volume_ratio, {SCHEMA_STATE} AS schema_state,
  ROUND(100 * quality_ratio, 1) AS quality_pct, ROUND(duration_ratio, 2) AS duration_ratio,
  ROUND(cost_ratio, 2) AS cost_ratio
FROM ranked
WHERE run_rank = 1
ORDER BY pipeline_name""",
    "runs_by_status": """
SELECT pipeline_name AS pipeline, run_status_code AS status, COUNT(*) AS runs
FROM {gold}.fact_pipeline_signal
GROUP BY pipeline_name, run_status_code""",
    "signal_history": f"""
SELECT pipeline_name AS pipeline, run_id, started_ts AS started, run_status_code AS status,
  ROUND(freshness_seconds / 3600, 1) AS freshness_hours, ROUND(volume_ratio, 2) AS volume_ratio,
  {SCHEMA_STATE} AS schema_state, ROUND(100 * quality_ratio, 1) AS quality_pct,
  ROUND(duration_ratio, 2) AS duration_ratio, ROUND(cost_ratio, 2) AS cost_ratio
FROM {{gold}}.fact_pipeline_signal
ORDER BY started_ts DESC""",
    "decisions": """
SELECT pipeline_name AS pipeline, run_id, run_started_ts AS started, failure_class_code AS failure_class,
  rule_name AS rule, recommended_action_code AS recommended, severity_code AS severity, run_mode_code AS run_mode,
  decided_action_code AS decided,
  CASE WHEN decided_action_code IS NULL THEN 'awaiting decision' WHEN is_match THEN 'matched'
    ELSE 'overridden' END AS match_state,
  impact_text AS impact
FROM {gold}.fact_remediation_decision
ORDER BY run_started_ts DESC""",
    "by_class": """
SELECT failure_class_code AS failure_class, severity_code AS severity, COUNT(*) AS failures,
  SUM(CASE WHEN decided_action_code IS NOT NULL THEN 1 ELSE 0 END) AS decided,
  SUM(CASE WHEN is_match THEN 1 ELSE 0 END) AS matched
FROM {gold}.fact_remediation_decision
GROUP BY failure_class_code, severity_code
ORDER BY failures DESC, failure_class_code""",
}

DOCTOR_BANNER = """## Pipeline doctor: what ran, what failed, and what it recommends
Each of this bundle's jobs, from the job run timeline: six signals per run against the pipeline's runs before
it, and for each failed run a failure class, the first allowed runbook action, its severity and its impact. Run
metadata only (names, states, times, counts, error types), never note text. The doctor recommends; the owner
decides (the job's `decisions` parameter) and nothing acts on its own. Empty until the job has run."""


@traced
def doctor_dashboard() -> dict:
    tiles = [("c_pipelines", "pipelines", "Pipelines", "Bundle jobs with a run in the lookback window."),
             ("c_runs", "runs", "Runs", "Finished runs in the window."),
             ("c_failed", "failed_runs", "Failed runs", "Failed or timed out: each has a decision row."),
             ("c_awaiting", "awaiting_decision", "Awaiting a decision",
              "Recommendations the owner hasn't decided yet.")]
    layout = [_text("banner", DOCTOR_BANNER, (0, 0, 6, 3))]
    layout += [_counter(n, "tiles", f, t, d, (i, 3, 1, 3)) for i, (n, f, t, d) in enumerate(tiles)]
    layout += [_filter("f_pipeline", "pipeline", ["latest_signals", "signal_history", "decisions"], "Pipeline",
                       (4, 3, 2, 3)),
               _text("s_signals", "### Signals, latest run per pipeline", (0, 6, 6, 1)),
               _table("tb_latest", "latest_signals", [
                   ("pipeline", "Pipeline"), ("status", "Status"), ("started", "Started"),
                   ("freshness_hours", "Freshness (h)"), ("sla_hours", "SLA (h)"), ("volume_ratio", "Volume ×"),
                   ("schema_state", "Schema"), ("quality_pct", "Checks passed (%)"),
                   ("duration_ratio", "Duration ×"), ("cost_ratio", "Cost ×")],
                   "Freshness, volume, schema, quality, duration and cost",
                   "Freshness: hours since the last ok run ended, against the SLA. Volume, duration and cost: this "
                   "run over the median of the pipeline's last 5 ok runs (1 = usual). Blank = the run table has no "
                   "count, check or cost for it (the span export isn't set).", (0, 7, 6, 6)),
               _bar("b_status", "runs_by_status", "pipeline", "runs", "Runs by pipeline and status", "",
                    (0, 13, 3, 6), color="status", x_title="Pipeline", y_title="Runs"),
               _table("tb_class", "by_class", [("failure_class", "Failure class"), ("severity", "Severity"),
                                               ("failures", "Failures"), ("decided", "Decided"),
                                               ("matched", "Matched the recommendation")],
                      "Failures by class",
                      "A reversible class may run on its own only after 5 decisions in a row matched; two misses "
                      "send it back (ops/runbook.yaml).", (3, 13, 3, 6)),
               _text("s_decisions", "### Recommendations and decisions", (0, 19, 6, 1)),
               _table("tb_decisions", "decisions", [
                   ("pipeline", "Pipeline"), ("run_id", "Run"), ("started", "Started"),
                   ("failure_class", "Failure class"), ("rule", "Rule"), ("recommended", "Recommended"),
                   ("severity", "Severity"), ("run_mode", "Mode"), ("decided", "Decided"),
                   ("match_state", "Match"), ("impact", "Impact")],
                   "One row per failed run",
                   "SEV1 and SEV2 reach the owner when first seen; SEV3 and SEV4 wait for the digests.",
                   (0, 20, 6, 7)),
               _text("s_history", "### Every run in the window", (0, 27, 6, 1)),
               _table("tb_history", "signal_history", [
                   ("pipeline", "Pipeline"), ("run_id", "Run"), ("started", "Started"), ("status", "Status"),
                   ("freshness_hours", "Freshness (h)"), ("volume_ratio", "Volume ×"), ("schema_state", "Schema"),
                   ("quality_pct", "Checks passed (%)"), ("duration_ratio", "Duration ×"),
                   ("cost_ratio", "Cost ×")], "Signals per run, newest first", "", (0, 28, 6, 7))]
    return {"datasets": [_dataset(n, s) for n, s in DOCTOR_SQL.items()],
            "pages": [{"name": "pipeline_doctor", "displayName": "Pipeline doctor", "pageType": "PAGE_TYPE_CANVAS",
                       "layout": layout}]}


DASHBOARDS = {"dq_grader": dq_grader, "lab_grader": lab_grader, "pipeline_doctor": doctor_dashboard}


# ---------------------------------------------------------------- Genie spaces (spec 019 US5)

def _id(text: str) -> str:
    """A stable 32-hex id, so rebuilding the space changes nothing unless its text does."""
    return hashlib.md5(text.encode()).hexdigest()


def _space(tables: list[str], instructions: list[str], questions: list[str]) -> dict:
    general = "\n\n".join(instructions)       # Genie keeps one general text instruction
    return {"version": 2,
            "config": {"sample_questions": sorted(({"id": _id(q), "question": [q]} for q in questions),
                                                  key=lambda q: q["id"])},
            "data_sources": {"tables": [{"identifier": f"{GOLD}.{t}"} for t in sorted(tables)]},
            "instructions": {"text_instructions": [{"id": _id(general), "content": [general]}]}}


DQ_TABLES = ["dq_check", "dq_column_missing", "dq_prevalence", "dq_temporal_change", "dq_stage_transition",
             "dq_source_concordance", "fact_visit_evidence", "dq_injected_error", "fact_case_profile_item",
             "fact_record_mismatch", "dq_mismatch_rule"]

DQ_INSTRUCTIONS = [
    ("Every table holds synthetic data from the study's generator, scored against its own truth. Start every "
     "answer that gives a number with 'On synthetic data:' and never call a figure clinical performance."),
    ("fact_visit_evidence has one row per visit: clinic_code, visit_date, each evidence source's status and "
     "truth_status_code. The *_status_code columns hold statuses (healthy, gingivitis, periodontitis_stage_1 to 4, "
     "or unknown when the source is missing), never note text; note_status_code is the status read from the note."),
    ("Completeness: share of visits where exam_form_status_code, dx_completed_status_code and "
     "probing_chart_status_code are all not 'unknown', from fact_visit_evidence. Missingness by column is "
     "dq_column_missing.missing_pct."),
    ("Accuracy: share of visits where a source equals truth_status_code, from fact_visit_evidence. The headline uses "
     "rules_v0_status_code (rules, gum measurements first). For a single evidence source, report both the share of "
     "visits it answers (not 'unknown') and its agreement with the truth where it answers."),
    ("Consistency: the spread of periodontitis prevalence across clinics, MAX minus MIN of "
     "dq_prevalence.periodontitis_ratio where level_code = 'clinic' and method_name = 'algorithm_design', in "
     "percentage points."),
    ("Temporal plausibility: dq_temporal_change.better_ratio for method_name 'algorithm_design', the share of visit "
     "pairs 1 to 2 years apart with no treatment between (visit_pair_count) whose stage improved, which is "
     "implausible; lower is better. Use visit_pair_count as the denominator, not later_visit_count. "
     "dq_stage_transition has the full matrix: row_pct is the share of the earlier stage's pairs that moved to "
     "each stage."),
    ("Reliability (de Vet et al. 2006: whether independent reviewers reach the same answer): not assessed. It needs real reviewers to label charts; the study's reviewers are "
     "simulated, so never report a reliability figure."),
    ("dq_check holds each check per clinic; clinic_code = 'All' is every clinic together. Do not add the clinic rows "
     "to the 'All' rows."),
    ("fact_case_profile_item is each visit's case profile (spec 026, after KEEPER): one row per visit and item, "
     "grouped by category_name in category_order_num order, items in item_order_num order. item_value_name is the "
     "value as shown, with item_unit_name; 'not recorded' means the record lacks it, 'not taken' means no probing "
     "chart, 'no later visit' means the patient's last visit. The item \"next visit's plausibility flags\" lists "
     "the checks the next visit fails, or 'none': cal_drop (max CAL fell by more than 1.5 mm), rbl_drop (bone loss "
     "fell by more than 5 points), teeth_regained (fewer teeth lost than before), perio_resolved (periodontitis "
     "before, not now), stage_drop (a lower stage than before). Structured values only, never note text. To show a "
     "visit's profile, list category_name, item_name, item_value_name and item_unit_name for its visit_id in order. "
     "Recorded diagnosis codes are what the dentist recorded; we find gum disease in records, we don't diagnose."),
    ("fact_record_mismatch has one row per visit and failed rule: a record mismatch, where the recorded code "
     "(the completed diagnosis code) doesn't fit the rest of the record. Call it a record mismatch or a record to "
     "recheck: it is usually a coding or charting gap, never a judgment that a dentist got it wrong. rule_name is "
     "code_vs_chart, code_above_chart, code_below_chart, no_periodontal_care, code_vs_radiograph or stage_drop; "
     "mismatch_evidence_text gives the values; for stage_drop, related_visit_id is the earlier visit with the "
     "higher code; failed_rule_count is how many rules the visit fails (list visits with most first). dq_mismatch_rule scores each rule, and any_rule, against the generator's truth over the visits "
     "it can check (checkable_count), overall (clinic_code = 'All') and per clinic: precision_ratio, recall_ratio, "
     "only_rule_count (flags no other rule makes), injected_caught_count of injected_checkable_count. Always give "
     "checkable_count with a rule's precision or recall. Per-clinic injected-error counts are too few to compare."),
]

DQ_QUESTIONS = [
    "Which evidence source is missing most often?",
    "Which clinic has the highest periodontitis prevalence, and what is its 95% interval?",
    "How often does the exam form agree with the truth when it is filled in?",
    "Which data quality checks failed at clinic 3?",
    "What share of later visits show the stage improving, by method?",
    "How well do the chart note and the exam form agree with each other?",
    "Show the case profile of visit 1234.",
    "Which visits have a stage III code but max CAL under 3 mm?",
    "Which record-mismatch rule adds the most flags no other rule makes?",
]


@traced
def dq_genie() -> dict:
    return _space(DQ_TABLES, DQ_INSTRUCTIONS, DQ_QUESTIONS)


LAB_INSTRUCTIONS = [
    ("While any row of fact_grader_answer has is_simulated = true, the data is a SIMULATED sample: every number is "
     "made up. Start every answer that gives a number with 'SIMULATED, not a result:' and never present it as a "
     "finding about any real model."),
    ("dim_grader_question has one row per question: category_name (Access to care first, by category_order_num), "
     "level_code (L1 recall, L2 routine reasoning, L3 individualized reasoning), key_point_count and source_text. "
     "fact_grader_answer has one row per question, model_name and is_with_agent (true = with the open agent)."),
    ("Score: score_ratio = covered_key_point_count / key_point_count; report it as a percentage. Uplift: the "
     "average score_ratio with the agent minus on its own, in percentage points, per category."),
    ("Unsafe rate: share of answers with harm_code S1 or S2. Irreversible-harm rate: share with harm_code S2. Harm "
     "is graded by clinicians' rules, not by the judge."),
    ("By level, report L1, L2 and L3 separately and their macro average (each level weighted equally)."),
    ("Never rank models across categories or give one overall rank: rank only within a category, and on its own "
     "and with the agent separately."),
    ("Cost: cost_usd is the cost of one answer in US dollars; report it next to the score, never alone."),
]

LAB_QUESTIONS = [
    "What is the uplift with the agent on access-to-care questions?",
    "Which model has the highest score on medical-dental integration questions with the agent?",
    "What share of answers were unsafe for each model, with and without the agent?",
    "How does each model score on L3 questions compared with L1?",
    "What does one answer cost for each model with the agent?",
]


@traced
def lab_genie() -> dict:
    return _space(["dim_grader_question", "fact_grader_answer"], LAB_INSTRUCTIONS, LAB_QUESTIONS)


GENIE_SPACES = {"dq_grader": dq_genie, "lab_grader": lab_genie}


@traced
def render(name: str) -> str:
    """The dashboard's .lvdash.json text, as committed."""
    return json.dumps(DASHBOARDS[name](), indent=2, ensure_ascii=False) + "\n"


@traced
def render_genie(name: str) -> str:
    """The Genie space's .geniespace.json text, as committed."""
    return json.dumps(GENIE_SPACES[name](), indent=2, ensure_ascii=False) + "\n"
