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
    assert message.endswith("Error message: KeyError: <value> in <path> after <n> rows")


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
    long = "ValueError: " + "x" * 400
    spans = [_span("step", "0xa", error=long, attrs={"pipeline.step": "step", "error.type": "ValueError"})]
    message = ss.write_statement(spans, "span_names_message").split("Error message: ", 1)[1]
    assert len(message) == 240


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
