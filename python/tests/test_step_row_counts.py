"""Spec 040 US6 (#758): pipeline steps record the rows they read and write on their own spans, so a statement written
from a failing run's telemetry (US1) can say how many rows went in and came out. A filter that drops rows shows up
only as those two counts."""

import importlib
import json

import pandas as pd
import pytest

pytest.importorskip("opentelemetry.sdk")

from health_transformation_lab_nlp import telemetry as tm

# The steps the fault injector can target: each takes a table, returns a table, and is called by its module's own
# tests (specs/040-telemetry-tasks/plan.md, "Steps the injector can target").
STEPS = {
    "results_store": ["new_files", "prediction_rows", "detail_rows"],
    "nhanes": ["to_site_tables", "weighted_prevalence", "edentulous_by_age", "classify_people", "missing_teeth_by_age"],
    "study": ["visits_in_study"],
    "completeness": ["column_completeness", "complete_cases", "prevalence_by_scale"],
    "tooth_loss_dq": ["flag_against_rest", "office_missing", "run_checks", "group_consistency"],
    "dq_site": ["flag_outliers"],
}


@pytest.fixture
def span_file(tmp_path):
    """Spans written as JSON lines, as a run with no network writes them, at the level that traces every function."""
    out = tmp_path / "spans.jsonl"
    tm.setup(tm.TelemetryConfig(exporter="file", file_path=str(out), level="detail"))
    yield out
    tm.setup(tm.TelemetryConfig(exporter="off"))


def _spans(path) -> dict:
    tm.setup(tm.TelemetryConfig(exporter="off"))          # flushes and closes the file
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return {s["name"]: s for s in lines if "context" in s}


def test_a_step_records_the_rows_it_reads_and_writes_on_its_own_span(span_file):
    from health_transformation_lab_nlp import results_store as rs

    files = pd.DataFrame({"file": ["a.csv", "b.csv", "c.csv"], "sha256": ["1", "2", "3"]})
    assert len(rs.new_files(files, {"2"})) == 2
    attrs = _spans(span_file)["results_store.new_files"]["attributes"]
    assert attrs["row_in_count"] == 3 and attrs["row_out_count"] == 2
    assert isinstance(attrs["row_in_count"], int) and isinstance(attrs["row_out_count"], int)


def test_a_failing_step_still_records_the_rows_it_was_given(span_file):
    @tm.traced
    @tm.counts_rows
    def drop_all(frame: pd.DataFrame) -> pd.DataFrame:
        raise KeyError("visit_date")

    with pytest.raises(KeyError):
        drop_all(pd.DataFrame({"x": range(4)}))
    span = _spans(span_file)["test_step_row_counts.drop_all"]
    assert span["attributes"]["row_in_count"] == 4 and "row_out_count" not in span["attributes"]
    assert span["attributes"]["error.type"] == "KeyError" and span["status"]["status_code"] == "ERROR"


def test_a_step_with_no_table_records_no_counts(span_file):
    @tm.traced
    @tm.counts_rows
    def summary(n: int) -> dict:
        return {"n": n}

    assert summary(3) == {"n": 3}
    attrs = _spans(span_file)["test_step_row_counts.summary"]["attributes"]
    assert "row_in_count" not in attrs and "row_out_count" not in attrs


def test_a_dict_of_tables_counts_all_their_rows_and_a_tuple_counts_its_first(span_file):
    @tm.traced
    @tm.counts_rows
    def split(tables: dict) -> tuple:
        both = pd.concat(tables.values())
        return both.head(2), both

    split({"a": pd.DataFrame({"x": [1, 2]}), "b": pd.DataFrame({"x": [3, 4, 5]})})
    attrs = _spans(span_file)["test_step_row_counts.split"]["attributes"]
    assert attrs["row_in_count"] == 5 and attrs["row_out_count"] == 2


def test_with_telemetry_off_a_step_returns_what_it_always_did():
    from health_transformation_lab_nlp import results_store as rs

    tm.setup(tm.TelemetryConfig(exporter="off"))
    files = pd.DataFrame({"file": ["a.csv", "b.csv"], "sha256": ["1", "2"]})
    pd.testing.assert_frame_equal(rs.new_files(files, {"1"}), files.iloc[[1]].reset_index(drop=True))


def test_every_step_the_injector_can_target_counts_its_rows_and_no_other_does():
    for module in STEPS:
        importlib.import_module(f"health_transformation_lab_nlp.{module}")
    expected = {f"{m}.{f}" for m, names in STEPS.items() for f in names}
    counted = {name for name in tm.ROW_COUNTED if name.split(".")[0] in STEPS}
    assert counted == expected, f"missing: {sorted(expected - counted)}; not in the plan: {sorted(counted - expected)}"


def test_a_filter_that_drops_every_row_records_zero_and_so_does_an_empty_table(span_file):
    """Zero is the count that shows a filter dropping every row, so it is written, not left out."""
    from health_transformation_lab_nlp import results_store as rs

    files = pd.DataFrame({"file": ["a.csv", "b.csv", "c.csv"], "sha256": ["1", "2", "3"]})
    assert rs.new_files(files, {"1", "2", "3"}).empty
    attrs = _spans(span_file)["results_store.new_files"]["attributes"]
    assert attrs["row_in_count"] == 3 and attrs["row_out_count"] == 0

    tm.setup(tm.TelemetryConfig(exporter="file", file_path=str(span_file), level="detail"))
    rs.new_files(files.iloc[0:0], set())
    attrs = _spans(span_file)["results_store.new_files"]["attributes"]
    assert attrs["row_in_count"] == 0 and attrs["row_out_count"] == 0


def test_the_first_table_is_found_when_it_is_passed_by_name(span_file):
    from health_transformation_lab_nlp import results_store as rs

    files = pd.DataFrame({"file": ["a.csv", "b.csv", "c.csv"], "sha256": ["1", "2", "3"]})
    rs.new_files(files=files, loaded_sha256={"2"})
    attrs = _spans(span_file)["results_store.new_files"]["attributes"]
    assert attrs["row_in_count"] == 3 and attrs["row_out_count"] == 2


def test_counts_rows_above_traced_is_refused_since_its_counts_would_reach_the_callers_span():
    with pytest.raises(TypeError, match="directly under @traced"):
        @tm.counts_rows
        @tm.traced
        def wrong_order(frame: pd.DataFrame) -> pd.DataFrame:
            return frame


def test_in_profile_mode_no_count_lands_on_the_enclosing_span(span_file):
    from health_transformation_lab_nlp import results_store as rs

    files = pd.DataFrame({"file": ["a.csv", "b.csv"], "sha256": ["1", "2"]})
    with tm.pipeline_step("outer_step"), tm.profile():
        rs.new_files(files, {"2"})
    attrs = _spans(span_file)["outer_step"]["attributes"]
    assert "row_in_count" not in attrs and "row_out_count" not in attrs
