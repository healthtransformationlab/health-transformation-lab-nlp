"""Spec 040 US1 (#753): a task statement written from a failing run's spans, at three levels: `symptom` (what a
person sees go wrong), `span_names` (plus the names telemetry adds) and `span_names_message` (plus the error message,
masked). No statement may carry a source line, a path, an unmasked value or note text."""

import json
import random

import pandas as pd
import pytest

pytest.importorskip("opentelemetry.sdk")

from health_transformation_lab_nlp import span_statement as ss
from health_transformation_lab_nlp import telemetry as tm

FORBIDDEN = ("/home/user", "notes.csv", "3437", "Patient reports", "raise KeyError", "line 41", "Traceback")


def _span(name, span_id, parent=None, start="2026-11-15T10:00:00.000000Z", error=None, attrs=None, events=None):
    """One span line as the SDK's file exporter writes it (the keys `read_spans` uses, and a stack trace event)."""
    return {"name": name, "context": {"trace_id": "0x1", "span_id": span_id}, "kind": "SpanKind.INTERNAL",
            "parent_id": parent, "start_time": start, "end_time": start,
            "status": {"status_code": "ERROR", "description": error} if error else {"status_code": "UNSET"},
            "attributes": attrs or {}, "events": events or [], "links": [], "resource": {"attributes": {}}}


def _write(path, spans):
    path.write_text("".join(json.dumps(s) + "\n" for s in spans), encoding="utf-8")
    return path


FAILING = [
    _span("load_results", "0xa", start="2026-11-15T10:00:00.000000Z", error="KeyError: 'visit_date'",
          attrs={"pipeline.step": "load_results", "pipeline.kind": "script", "data.label": "synthetic"}),
    _span("results_store.new_files", "0xb", parent="0xa", start="2026-11-15T10:00:01.000000Z",
          error=("KeyError: 'Patient reports bleeding gums' in /home/user/data/raw/notes.csv after 3437 rows"),
          attrs={"error.type": "KeyError", "row_in_count": 4, "data.label": "synthetic"},
          events=[{"name": "exception", "attributes": {
              "exception.type": "KeyError", "exception.message": "'Patient reports bleeding gums'",
              "exception.stacktrace": 'Traceback (most recent call last):\n  File "/home/user/x.py", line 41\n'
                                      "    raise KeyError(note)\n"}}]),
]


def test_the_three_conditions_and_an_unknown_one_is_refused_by_name():
    assert ss.CONDITIONS == ("symptom", "span_names", "span_names_message")
    with pytest.raises(ValueError, match="person"):
        ss.write_statement(FAILING, "person")


def test_a_failing_run_gives_three_statements_each_adding_to_the_last(tmp_path):
    spans = ss.read_spans(_write(tmp_path / "spans.jsonl", FAILING))
    symptom, names, message = (ss.write_statement(spans, c) for c in ss.CONDITIONS)
    assert symptom == "The load_results step stopped with an error."
    assert names.startswith(symptom) and message.startswith(names)
    assert "results_store.new_files" in names and "synthetic" in names and "KeyError" in names
    assert "Rows in: 4." in names and "Rows out" not in names
    assert "results_store.new_files" not in symptom and "KeyError" not in symptom
    assert message.endswith("Error message: KeyError: <value>")     # all after the first ": " is the value


def test_no_statement_carries_a_source_line_a_path_a_value_or_note_text(tmp_path):
    spans = ss.read_spans(_write(tmp_path / "spans.jsonl", FAILING))
    for condition in ss.CONDITIONS:
        text = ss.write_statement(spans, condition)
        assert not [f for f in FORBIDDEN if f in text], (condition, text)


def test_the_same_spans_in_any_order_give_the_same_text(tmp_path):
    first = ss.read_spans(_write(tmp_path / "a.jsonl", FAILING))
    shuffled = FAILING[::-1]
    random.Random(7).shuffle(shuffled)
    second = ss.read_spans(_write(tmp_path / "b.jsonl", shuffled))
    for condition in ss.CONDITIONS:
        assert ss.write_statement(first, condition) == ss.write_statement(second, condition)


def test_a_span_without_counts_gives_span_names_without_them():
    spans = [dict(FAILING[0]), dict(FAILING[1], attributes={"error.type": "KeyError"})]
    assert "Rows" not in ss.write_statement(spans, "span_names")


def test_a_run_that_did_not_fail_looks_wrong_and_names_the_rows_of_each_counted_step():
    spans = [_span("load_results", "0xa", attrs={"pipeline.step": "load_results", "data.label": "synthetic"}),
             _span("results_store.new_files", "0xb", parent="0xa", start="2026-11-15T10:00:01.000000Z",
                   attrs={"row_in_count": 4, "row_out_count": 0})]
    assert ss.write_statement(spans, "symptom") == "The load_results step finished, but its output looks wrong."
    names = ss.write_statement(spans, "span_names")
    assert "results_store.new_files: rows in 4, rows out 0" in names and "Error" not in names
    assert ss.write_statement(spans, "span_names_message") == names


def test_without_a_pipeline_step_the_outermost_span_names_the_step():
    """History tasks' base commits predate the run spans (#712): their outermost span stands for the step."""
    spans = [_span("study.build_study", "0xa", error="ValueError: no visits"),
             _span("study.visits_in_study", "0xb", parent="0xa", start="2026-11-15T10:00:01.000000Z",
                   error="ValueError: no visits", attrs={"error.type": "ValueError"})]
    assert ss.write_statement(spans, "symptom") == "The study.build_study step stopped with an error."
    assert "It failed in study.visits_in_study." in ss.write_statement(spans, "span_names")


def test_the_error_message_is_cut_to_240_characters():
    assert len(_message("no objects to concatenate " + "x" * 400)) == 240


def test_a_real_failing_step_written_by_the_file_exporter(tmp_path):
    out = tmp_path / "spans.jsonl"
    tm.setup(tm.TelemetryConfig(exporter="file", file_path=str(out), level="detail"))

    @tm.traced
    @tm.counts_rows
    def drop_visits(frame: pd.DataFrame) -> pd.DataFrame:
        raise KeyError("visit_date")

    try:
        with pytest.raises(KeyError), tm.pipeline_step("study_benchmark", data_label="synthetic"):
            drop_visits(pd.DataFrame({"x": range(5)}))
    finally:
        tm.setup(tm.TelemetryConfig(exporter="off"))
    spans = ss.read_spans(out)
    assert ss.write_statement(spans, "symptom") == "The study_benchmark step stopped with an error."
    names = ss.write_statement(spans, "span_names")
    assert "It failed in test_span_statement.drop_visits." in names
    assert "Rows in: 5." in names and "Error type: KeyError." in names and "Data label: synthetic." in names
    assert ss.write_statement(spans, "span_names_message").endswith("Error message: <value>")


def _message(description: str) -> str | None:
    """The `span_names_message` error line of a one-span run that failed with this status message."""
    spans = [_span("step", "0xa", error=description, attrs={"pipeline.step": "step", "error.type": "ValueError"})]
    lines = ss.write_statement(spans, "span_names_message").splitlines()
    found = [line.split("Error message: ", 1)[1] for line in lines if line.startswith("Error message: ")]
    return found[0] if found else None


NOTE = "S: Pt presents for new pt exam. Gums bleed when brushing. O: probing depths up to 6 mm"


def test_a_value_pandas_prints_without_quotes_is_masked():
    with pytest.raises(ValueError) as err:
        pd.to_datetime([NOTE], format="mixed")
    masked = _message(str(err.value))
    assert masked.endswith(": <value>") and "Gums" not in masked and "Pt presents" not in masked


@pytest.mark.parametrize("description, expected", [
    ("can't parse 'Patient reports bleeding gums'", "can't parse <value>"),
    ("could not convert string to float: 'Pt states \"it hurts\" and can't chew'",
     "could not convert string to float: <value>"),
    ("'S: periodic oral eval. Pt reports no complaint", "<value>"),          # a quote left open by the 500-char cut
    ("'O'Brien's chart' is missing", "<value> is missing"),
    ('bad value "Patient reports pain" in row', "bad value <value> in row"),
    ("row V3437 for patient_3437 at 2026-11-21T00:00:00 off by 1.5e-3, -4 or 3.14",
     "row V<n> for patient_<n> at <n>-<n>-<n>T<n>:<n>:<n> off by <n>, -<n> or <n>"),
    (r"C:\Users\pt\notes.csv and data/raw/notes.csv not readable", "<path> and <path> not readable"),
    ("results.xlsx and model.pkl and notes.csv are stale", "<path> and <path> and <path> are stale"),
])
def test_masking_leaves_no_value_path_file_name_or_number(description, expected):
    assert _message(description) == expected


def test_a_message_that_embeds_a_traceback_is_left_out():
    description = ('git failed\nTraceback (most recent call last):\n  File "x.py", line 3, in <module>\n'
                   "    raise KeyError(note)")
    assert _message(description) is None


def test_the_failure_named_is_the_one_that_ended_the_run_not_one_the_code_caught(tmp_path):
    out = tmp_path / "spans.jsonl"
    tm.setup(tm.TelemetryConfig(exporter="file", file_path=str(out), level="detail"))

    @tm.traced
    def optional_lookup(key: str) -> str:
        raise KeyError(key)

    @tm.traced
    def build_table(rows: int) -> int:
        raise ValueError("no rows left after the filter")

    try:
        with pytest.raises(ValueError), tm.pipeline_step("study_benchmark", data_label="synthetic"):
            try:
                optional_lookup("visit_date")
            except KeyError:
                pass
            build_table(3)
    finally:
        tm.setup(tm.TelemetryConfig(exporter="off"))
    names = ss.write_statement(ss.read_spans(out), "span_names")
    assert "It failed in test_span_statement.build_table." in names and "Error type: ValueError." in names


def test_the_step_named_is_the_one_around_the_failure():
    roots = [_span("study.visit_exclusions", "0xa", start="2026-11-15T10:00:00.000000Z"),
             _span("study.visits_in_study", "0xb", start="2026-11-15T10:00:05.000000Z", error="ValueError: x")]
    assert ss.write_statement(roots, "symptom") == "The study.visits_in_study step stopped with an error."
    steps = [_span("load_results", "0xa", attrs={"pipeline.step": "load_results"}),
             _span("study_benchmark", "0xb", start="2026-11-15T10:00:05.000000Z", error="ValueError: x",
                   attrs={"pipeline.step": "study_benchmark"})]
    assert ss.write_statement(steps, "symptom") == "The study_benchmark step stopped with an error."


def test_a_script_run_span_names_the_step_over_an_inner_step():
    spans = [_span("run_benchmark", "0xa", error="ValueError: x",
                   attrs={"pipeline.step": "run_benchmark", "pipeline.kind": "script"}),
             _span("inner", "0xb", parent="0xa", start="2026-11-15T10:00:01.000000Z", error="ValueError: x",
                   attrs={"pipeline.step": "inner"})]
    assert ss.write_statement(spans, "symptom") == "The run_benchmark step stopped with an error."


def test_read_spans_skips_metrics_lines_and_a_cut_off_last_line(tmp_path):
    path = _write(tmp_path / "spans.jsonl", FAILING)
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({"resource_metrics": []}) + "\n" + '{"name": "cut off", "context": {"span_')
    assert [s["name"] for s in ss.read_spans(path)] == ["load_results", "results_store.new_files"]


def test_spans_that_tie_on_start_time_give_the_same_text_in_any_order():
    tied = [_span(name, f"0x{i}", attrs={"row_in_count": i}) for i, name in enumerate(["c.step", "a.step", "b.step"])]
    texts = set()
    for seed in range(6):
        shuffled = tied[:]
        random.Random(seed).shuffle(shuffled)
        texts.add(tuple(ss.write_statement(shuffled, c) for c in ss.CONDITIONS))
    assert len(texts) == 1 and next(iter(texts))[0] == "The a.step step finished, but its output looks wrong."


def test_a_run_that_did_not_fail_names_at_most_ten_counted_steps():
    spans = [_span(f"m.f{i:02d}", f"0x{i}", start=f"2026-11-15T10:00:{i:02d}.000000Z", attrs={"row_in_count": i})
             for i in range(12)]
    named = [line for line in ss.write_statement(spans, "span_names").splitlines() if line.startswith("m.f")]
    assert len(named) == ss.MAX_COUNTED_STEPS == 10 and named[0].startswith("m.f00")


def test_a_span_whose_attributes_are_null_is_read_as_having_none():
    spans = [dict(_span("step", "0xa", error="ValueError: x"), attributes=None)]
    assert ss.write_statement(spans, "span_names").startswith("The step step stopped with an error.")
