"""Spec 019: the grader dashboards are built by health_transformation_lab_nlp.dashboards, and every dataset's SQL runs, here in
DuckDB, on the tables grader_tables builds from the committed CSVs, under the same three-part names as in Databricks."""

import json
import re

import pandas as pd
import pytest

from health_transformation_lab_nlp import dashboards as dash
from health_transformation_lab_nlp import gold_names
from health_transformation_lab_nlp import grader_tables as gt
from health_transformation_lab_nlp.paths import DATASETS_DIR, REPO_ROOT

duckdb = pytest.importorskip("duckdb")
DASH_DIR = REPO_ROOT / "databricks" / "dashboards"


@pytest.fixture(scope="module")
def con():
    c = duckdb.connect()
    c.execute("ATTACH ':memory:' AS health_transformation_lab")
    c.execute("CREATE SCHEMA health_transformation_lab.gold_perio_bench")
    now = pd.Timestamp("2026-10-28", tz="UTC")
    for name, df in {**gt.dq_tables(DATASETS_DIR), **gt.lab_tables(DATASETS_DIR)}.items():   # under their gold names
        df = gold_names.to_gold(df.assign(git_commit="abc1234", loaded_at=now), name)
        c.register(f"src_{name}", df)
        c.execute(f"CREATE TABLE health_transformation_lab.gold_perio_bench.{name} AS SELECT * FROM src_{name}")
    return c


@pytest.mark.parametrize("name", sorted(dash.DASHBOARDS))
def test_committed_dashboard_matches_the_builder(name):
    built = dash.render(name)
    committed = (DASH_DIR / f"{name}.lvdash.json").read_text()
    assert committed == built, "run python python/scripts/42_build_dashboards.py"


def _datasets(name):
    return json.loads(dash.render(name))["datasets"]


def test_every_dq_dataset_runs_and_returns_rows(con):
    for ds in _datasets("dq_grader"):
        sql = "".join(ds["queryLines"])
        rows = con.execute(sql).fetchall()
        assert rows, ds["name"]


def test_dq_tiles_give_the_values_the_tables_hold(con):
    sql = {d["name"]: "".join(d["queryLines"]) for d in _datasets("dq_grader")}
    tiles = dict(zip([c[0] for c in con.execute(sql["tiles"]).description], con.execute(sql["tiles"]).fetchone()))
    visits = gt.dq_tables(DATASETS_DIR)["fact_visit_evidence"]
    known = (visits[["exam_form", "proc_dx_completed", "probing_chart"]] != "unknown").all(axis=1)
    assert tiles["completeness_pct"] == pytest.approx(round(100 * known.mean(), 1))
    acc = (visits.algorithm_v0 == visits.truth_status).mean()
    assert tiles["accuracy_pct"] == pytest.approx(round(100 * acc, 1))
    assert 0 < tiles["consistency_pts"] < 100 and 0 <= tiles["implausible_pct"] < 100


def test_every_widget_query_names_a_dataset_and_its_fields(con):
    for name in dash.DASHBOARDS:
        d = json.loads(dash.render(name))
        cols = {}
        for ds in d["datasets"]:
            cols[ds["name"]] = {c[0] for c in con.execute("".join(ds["queryLines"])).description}
        for page in d["pages"]:
            for item in page["layout"]:
                for q in item["widget"].get("queries", []):
                    ds = q["query"]["datasetName"]
                    assert ds in {x["name"] for x in d["datasets"]}, (name, ds)
                    if ds in cols:
                        for f in q["query"]["fields"]:
                            for col in re.findall(r"`([^`]+)`", f["expression"]):
                                assert col in cols[ds], (name, ds, col)


def test_dq_dashboard_says_synthetic_and_reliability_not_assessed():
    text = dash.render("dq_grader")
    assert "Synthetic data" in text and "not clinical performance" in text
    assert "Reliability" in text and "Not assessed" in text


def test_dashboards_are_in_the_bundle():
    bundle = (REPO_ROOT / "databricks" / "resources" / "dashboards.yml").read_text()
    for name in dash.DASHBOARDS:
        assert f"file_path: ../dashboards/{name}.lvdash.json" in bundle, name


GENIE_DIR = REPO_ROOT / "databricks" / "genie"


@pytest.mark.parametrize("name", sorted(dash.GENIE_SPACES))
def test_committed_genie_space_matches_the_builder(name):
    assert (GENIE_DIR / f"{name}.geniespace.json").read_text() == dash.render_genie(name), \
        "run python python/scripts/42_build_dashboards.py"


def test_dq_genie_space_reads_only_dq_tables_and_defines_each_tile():
    space = json.loads(dash.render_genie("dq_grader"))
    assert space["version"] == 2
    tables = {t["identifier"] for t in space["data_sources"]["tables"]}
    assert tables == {f"{dash.GOLD}.{n}" for n in gt.dq_tables(DATASETS_DIR)}
    text = " ".join(" ".join(i["content"]) for i in space["instructions"]["text_instructions"])
    for measure in ("Completeness", "Accuracy", "Consistency", "Temporal plausibility", "Reliability"):
        assert measure in text, measure
    assert "synthetic" in text.lower() and "note text" in text
    ids = [q["id"] for q in space["config"]["sample_questions"]] + \
          [i["id"] for i in space["instructions"]["text_instructions"]]
    assert all(re.fullmatch(r"[0-9a-f]{32}", i) for i in ids) and len(set(ids)) == len(ids)
    assert len(space["config"]["sample_questions"]) >= 4


@pytest.mark.parametrize("name", sorted(dash.GENIE_SPACES))
def test_genie_space_has_one_general_instruction_and_sorted_questions(name):
    # Genie keeps one general text instruction; sample questions are sorted by id, as an exported space is
    space = json.loads(dash.render_genie(name))
    assert len(space["instructions"]["text_instructions"]) == 1
    ids = [q["id"] for q in space["config"]["sample_questions"]]
    assert ids == sorted(ids)


def test_genie_spaces_are_in_the_bundle_and_ci_has_a_cli_that_knows_them():
    # issue #155: a space is created only once its tables exist, so the spaces are their own bundle
    bundle = (REPO_ROOT / "databricks" / "genie" / "databricks.yml").read_text()
    for name in dash.GENIE_SPACES:
        assert f"file_path: ./{name}.geniespace.json" in bundle, name
    assert not list((REPO_ROOT / "databricks" / "resources").glob("genie*.yml"))
    for f in (REPO_ROOT / "databricks" / "resources").glob("*.yml"):
        assert "genie_spaces:" not in f.read_text(), f.name
    for wf in ("ci.yml", "deploy.yml"):
        pins = re.findall(r"databricks/setup-cli@v(\d+)\.(\d+)", (REPO_ROOT / ".github" / "workflows" / wf).read_text())
        assert pins and all((int(a), int(b)) >= (1, 3) for a, b in pins), wf   # genie_spaces: CLI 1.3.0


# ---------------------------------------------------------------- the lab grader (US4)

def _run(con, name, ds):
    sql = {d["name"]: "".join(d["queryLines"]) for d in _datasets(name)}[ds]
    return con.execute(sql).df()


def test_every_lab_dataset_runs_and_returns_rows(con):
    for ds in _datasets("lab_grader"):
        assert con.execute("".join(ds["queryLines"])).fetchall(), ds["name"]


def test_uplift_is_the_with_agent_score_minus_the_own_score_access_to_care_first(con):
    up = _run(con, "lab_grader", "uplift")
    assert up.category.iloc[0] == "Access to care"
    lab = gt.lab_tables(DATASETS_DIR)
    m = lab["fact_grader_answer"].merge(lab["dim_grader_question"][["question_id", "category"]], on="question_id")
    mean = m.groupby(["category", "with_agent"]).score.mean().unstack()
    for r in up.itertuples():
        assert r.own_pct == pytest.approx(round(100 * mean.loc[r.category, False], 1))
        assert r.agent_pct == pytest.approx(round(100 * mean.loc[r.category, True], 1))
        assert r.uplift_lo <= r.uplift_pts <= r.uplift_hi


def test_leaderboard_ranks_only_within_a_category(con):
    lb = _run(con, "lab_grader", "leaderboard")
    assert set(lb.category) == set(gt.CATEGORIES)
    for (_, _), g in lb.groupby(["category", "answer_mode"]):
        assert sorted(g["rank"]) == list(range(1, len(g) + 1))
    assert "overall" not in dash.render("lab_grader").lower()


def test_safety_and_levels_follow_globaldentbench(con):
    s = _run(con, "lab_grader", "safety")
    assert ((s.unsafe_pct >= s.s2_pct) & (s.s2_pct >= 0)).all()
    lv = _run(con, "lab_grader", "by_level")
    assert set(lv.level) == {"L1", "L2", "L3", "Macro average"}


def test_lab_dashboard_and_space_say_simulated():
    text = dash.render("lab_grader")
    assert "SIMULATED" in text and "not a result" in text
    space = json.loads(dash.render_genie("lab_grader"))
    instructions = " ".join(" ".join(i["content"]) for i in space["instructions"]["text_instructions"])
    assert "simulated" in instructions and "never rank" in instructions.lower()
    tables = {t["identifier"] for t in space["data_sources"]["tables"]}
    assert tables == {f"{dash.GOLD}.dim_grader_question", f"{dash.GOLD}.fact_grader_answer"}


def test_bundle_resource_keys_are_unique_across_resource_types():
    # bundle validate: "multiple resources ... have been defined with the same key" (a dashboard and a space)
    import yaml
    keys = []
    for f in sorted((REPO_ROOT / "databricks" / "resources").glob("*.yml")):
        for kind, items in (yaml.safe_load(f.read_text()).get("resources") or {}).items():
            keys += [(k, f"{f.name}:{kind}") for k in items]
    names = [k for k, _ in keys]
    assert len(names) == len(set(names)), sorted(x for x in keys if names.count(x[0]) > 1)


# ---------------------------------------------------------------- issue #155: the spaces wait for their tables

def _missing_mod():
    import importlib.util
    spec = importlib.util.spec_from_file_location("genie_tables_missing",
                                                  REPO_ROOT / ".github" / "scripts" / "genie_tables_missing.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_genie_check_lists_every_table_the_spaces_read_and_reports_the_missing():
    m = _missing_mod()
    tables = m.space_tables(REPO_ROOT / "databricks" / "genie")
    assert {f"{dash.GOLD}.dq_check", f"{dash.GOLD}.fact_grader_answer"} <= set(tables)
    assert m.missing(tables, exists=lambda t: True) == []
    assert m.missing(tables, exists=lambda t: not t.endswith(".dq_check")) == [f"{dash.GOLD}.dq_check"]


def test_deploy_creates_the_spaces_last_and_only_when_their_tables_exist():
    import yaml
    steps = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "deploy.yml").read_text())["jobs"]
    steps = next(iter(steps.values()))["steps"]
    runs = [s.get("run", "") for s in steps]
    load = next(i for i, r in enumerate(runs) if "load_results" in r)
    genie = next(i for i, r in enumerate(runs) if "databricks/genie" in r)
    assert genie > load
    assert "genie_tables_missing.py" in runs[genie] and "exit 0" in runs[genie]
    ci = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text()
    assert "cd databricks/genie && databricks bundle validate" in ci


def test_dq_genie_space_explains_the_case_profiles():
    """Spec 026 US1: profiles are usable from Genie before the recheck page exists."""
    space = json.loads(dash.render_genie("dq_grader"))
    text = " ".join(" ".join(i["content"]) for i in space["instructions"]["text_instructions"])
    assert "fact_case_profile_item" in text and "not recorded" in text and "never note text" in text
    questions = " ".join(q["question"][0] for q in space["config"]["sample_questions"])
    assert "profile of visit" in questions


def test_dq_genie_space_explains_every_value_a_profile_can_hold():
    space = json.loads(dash.render_genie("dq_grader"))
    text = " ".join(" ".join(i["content"]) for i in space["instructions"]["text_instructions"])
    for value in ("'none'", "cal_drop", "rbl_drop", "teeth_regained", "perio_resolved", "stage_drop"):
        assert value in text, value


def test_dq_genie_space_explains_the_record_mismatch_rules():
    """Spec 026 US2: the mismatch tables are in Genie, explained in the Words rule's terms."""
    space = json.loads(dash.render_genie("dq_grader"))
    text = " ".join(" ".join(i["content"]) for i in space["instructions"]["text_instructions"])
    for term in ("fact_record_mismatch", "dq_mismatch_rule", "record mismatch", "checkable_count",
                 "coding or charting gap", "any_rule"):
        assert term in text, term
    questions = " ".join(q["question"][0] for q in space["config"]["sample_questions"])
    assert "stage III code" in questions


# ---------------------------------------------------------------- spec 026 US3: Records to recheck

def _recheck_page():
    pages = json.loads(dash.render("dq_grader"))["pages"]
    page = next(p for p in pages if p["name"] == "records_to_recheck")
    return page, {i["widget"]["name"]: i["widget"] for i in page["layout"]}


def test_dq_grader_has_a_records_to_recheck_page_after_the_grader():
    pages = json.loads(dash.render("dq_grader"))["pages"]
    assert [p["displayName"] for p in pages] == ["EHR DQ grader", "Records to recheck"]


def test_the_recheck_page_says_synthetic_and_what_a_mismatch_is():
    _, w = _recheck_page()
    banner = "".join(w["recheck_banner"]["multilineTextboxSpec"]["lines"])
    assert "Synthetic" in banner and "coding or charting gap, not a clinical error" in banner
    assert "checkable" in banner


def test_the_recheck_page_shows_rule_scores_flagged_visits_and_a_visit_profile():
    _, w = _recheck_page()
    datasets = {q["query"]["datasetName"] for x in w.values() for q in x.get("queries", [])}
    assert {"mismatch_rules", "mismatch_visits", "case_profile"} <= datasets
    rules = [c["fieldName"] for c in w["tb_rules"]["spec"]["encodings"]["columns"]]
    assert {"checkable", "flagged", "precision_pct", "recall_pct", "only_this_rule"} <= set(rules)
    visit_filter = w["f_visit"]
    assert visit_filter["spec"]["widgetType"] == "filter-single-select"
    assert {q["query"]["datasetName"] for q in visit_filter["queries"]} == {"mismatch_visits", "case_profile"}


def test_the_recheck_datasets_read_only_the_spec_026_tables():
    sql = {d["name"]: "".join(d["queryLines"]) for d in _datasets("dq_grader")}
    for name in ("mismatch_rules", "mismatch_visits", "case_profile"):
        tables = set(re.findall(r"gold_perio_bench\.(\w+)", sql[name]))
        assert tables <= {"fact_record_mismatch", "dq_mismatch_rule", "fact_case_profile_item", "fact_visit_evidence"}


def test_flagged_visits_come_most_rules_failed_first_and_profiles_cover_every_flagged_visit(con):
    sql = {d["name"]: "".join(d["queryLines"]) for d in _datasets("dq_grader")}
    visits = con.execute(sql["mismatch_visits"]).df()
    assert visits.rules_failed.iloc[0] == visits.rules_failed.max()
    assert visits.rules_failed.is_monotonic_decreasing
    rules = con.execute(sql["mismatch_rules"]).df()
    assert rules.clinic.iloc[0] == "All" and "Any rule" in set(rules.rule)


def test_the_profile_table_names_its_visit_and_says_to_pick_one():
    _, w = _recheck_page()
    cols = [c["fieldName"] for c in w["tb_profile"]["spec"]["encodings"]["columns"]]
    assert cols[0] == "visit_id"
    assert "Pick a visit" in w["tb_profile"]["spec"]["frame"]["description"]


def test_filters_keep_the_all_rows_and_say_what_they_narrow():
    _, w = _recheck_page()
    assert {q["query"]["datasetName"] for q in w["f_recheck_clinic"]["queries"]} == {"mismatch_visits"}
    assert {q["query"]["datasetName"] for q in w["f_rule"]["queries"]} == {"mismatch_visits", "mismatch_rules"}
    rules_note = w["tb_rules"]["spec"]["frame"]["description"]
    assert "blank" in rules_note.lower() and "clinic filter" in rules_note.lower()
    flagged_note = w["tb_flagged"]["spec"]["frame"]["description"]
    assert "Rules failed" in flagged_note and "rule filter" in flagged_note.lower()
