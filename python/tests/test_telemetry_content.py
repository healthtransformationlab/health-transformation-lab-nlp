"""014 US9 (#850): a coding-agent run's own content may reach a span when DENTAL_TELEMETRY_CONTENT=full, with secrets
taken out and long text kept in parts. Dental-record code still sends short labels only (ADR 0010)."""
import pytest

pytest.importorskip("opentelemetry.sdk")

from health_transformation_lab_nlp import telemetry as tm

T0 = 1_763_000_000_000_000_000


@pytest.fixture
def mem():
    exporter = tm.setup(tm.TelemetryConfig(exporter="memory"))
    yield exporter
    tm.setup(tm.TelemetryConfig(exporter="off"))


def test_the_setting_is_labels_by_default_and_any_other_value_stops_at_once(monkeypatch):
    monkeypatch.delenv("DENTAL_TELEMETRY_CONTENT", raising=False)
    assert tm.content_level() == "labels"
    monkeypatch.setenv("DENTAL_TELEMETRY_CONTENT", " Full ")
    assert tm.content_level() == "full"
    monkeypatch.setenv("DENTAL_TELEMETRY_CONTENT", "everything")
    with pytest.raises(SystemExit) as e:
        tm.content_level()
    assert "DENTAL_TELEMETRY_CONTENT" in str(e.value) and "labels" in str(e.value) and "full" in str(e.value)
    assert tm.CONTENT_LEVELS == ("labels", "full")


SECRETS = ["KGAT_" + "a1B2c3D4" * 4, "hf_" + "Zx9" * 12, "ghp_" + "Q7w" * 12, "github_pat_" + "11AB_cd" * 6,
           "sk-" + "proj_9fK" * 4, "AKIA" + "ABCDEFGH12345678"]


@pytest.mark.parametrize("secret", SECRETS)
def test_token_shapes_are_redacted(secret):
    out = tm.scrub(f"export TOKEN={secret}\ncurl -H 'x: {secret}' https://example.org")
    assert secret not in out and out.count(tm.REDACTED) == 2 and "curl -H" in out


def test_bearer_tokens_connection_strings_and_assigned_literals_are_redacted():
    out = tm.scrub('Authorization: Bearer abcDEF123456ghiJKL789\n'
                   'InstrumentationKey=0f0f0f0f-1111-2222-3333-444444444444;IngestionEndpoint=https://x.example/\n'
                   'password = "correct horse"\n{"api_key": \'s3cr3t-value\'}\nDB_PASSWORD="hunter22"')
    for leaked in ("abcDEF123456ghiJKL789", "0f0f0f0f-1111", "correct horse", "s3cr3t-value", "hunter22"):
        assert leaked not in out, leaked
    assert "Authorization: Bearer " + tm.REDACTED in out and "IngestionEndpoint=https://x.example/" in out
    assert 'password = "' + tm.REDACTED + '"' in out


def test_ordinary_code_is_left_as_it_is():
    code = ("def login(username: str, password: str, token: str | None = None):\n"
            "    user = authenticate(username=username, password=form_data.password)\n"
            "    return get_token(user)  # the token's type\n")
    assert tm.scrub(code) == code


def test_the_process_own_secret_values_are_redacted(monkeypatch):
    monkeypatch.setenv("MY_SERVICE_API_KEY", "plainvalue-with-no-known-shape")
    monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "InstrumentationKey=abc;IngestionEndpoint=https://y/")
    monkeypatch.setenv("HOME_DIR_NAME", "plainvalue-that-is-not-secret")
    out = tm.scrub("a plainvalue-with-no-known-shape b plainvalue-that-is-not-secret")
    assert out == f"a {tm.REDACTED} b plainvalue-that-is-not-secret"


def test_text_parts_join_back_to_the_text():
    text = "x" * 8000 + "y" * 8000 + "z" * 5
    parts = tm.text_parts(text)
    assert [len(p) for p in parts] == [8000, 8000, 5] and "".join(parts) == text
    assert tm.text_parts("") == [""] and tm.text_parts("abc", size=2) == ["ab", "c"]
    assert tm.MAX_TEXT_CHARS == 8000


def test_content_span_sends_nothing_unless_the_level_is_full(mem, monkeypatch):
    monkeypatch.delenv("DENTAL_TELEMETRY_CONTENT", raising=False)
    assert tm.content_span("agent_step", T0, T0 + 1, message_text="hello") is None
    assert mem.get_finished_spans() == ()


def test_content_span_keeps_text_scrubbed_and_long_text_in_parts(mem, monkeypatch):
    monkeypatch.setenv("DENTAL_TELEMETRY_CONTENT", "full")
    secret = "hf_" + "Zx9" * 12
    long = "A" * 7990 + " " + secret + "\n" + "B" * 9000   # the secret straddles the first part's end before scrubbing
    parent = tm.content_span("agent_task", T0, T0 + 9_000_000_000, instance_id="rich_1", is_resolved=False)
    span = tm.content_span("agent_step", T0 + 1_000, T0 + 2_000, parent=parent, instance_id="rich_1", step_num=3,
                           tool_name="read_file", output_text=long, message_text="short", seconds=1.5)
    spans = mem.get_finished_spans()
    steps = [s for s in spans if s.name == "agent_step"]
    parts = sorted((s for s in spans if s.name == "agent_step_part"), key=lambda s: s.attributes["part_num"])
    assert len(steps) == 1 and steps[0].context.span_id == span.context.span_id
    a = steps[0].attributes
    assert a["message_text"] == "short" and a["tool_name"] == "read_file" and a["step_num"] == 3 and a["seconds"] == 1.5
    assert "message_text_part_count" not in a
    scrubbed = tm.scrub(long)
    assert a["output_text_part_count"] == len(tm.text_parts(scrubbed)) == 1 + len(parts)
    assert a["output_text"] + "".join(p.attributes["part_text"] for p in parts) == scrubbed
    assert secret not in str([dict(s.attributes) for s in spans])
    assert [p.attributes["part_num"] for p in parts] == list(range(2, 2 + len(parts)))
    for p in parts:
        assert p.attributes["field_name"] == "output_text" and p.attributes["instance_id"] == "rich_1"
        assert p.attributes["step_num"] == 3 and p.parent.span_id == span.context.span_id
        assert "message_text" not in p.attributes
    assert (steps[0].start_time, steps[0].end_time) == (T0 + 1_000, T0 + 2_000)
    assert steps[0].parent.span_id == parent.context.span_id


def test_labels_only_paths_are_unchanged(mem, monkeypatch):
    """annotate() still keeps text only as a short label, whatever the content setting (dental-record code)."""
    monkeypatch.setenv("DENTAL_TELEMETRY_CONTENT", "full")
    with tm.pipeline_step("outer"):
        @tm.traced
        def work():
            tm.annotate(note_text="a clinical note would be text", engine_name="rules")
        work()
    sent = str([dict(s.attributes) for s in mem.get_finished_spans()])
    assert "a clinical note" not in sent and "rules" in sent
