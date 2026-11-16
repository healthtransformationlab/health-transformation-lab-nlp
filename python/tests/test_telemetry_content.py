"""014 US9 (#850): a coding-agent run's own content may reach a span when DENTAL_TELEMETRY_CONTENT=full, with secrets
taken out and long text kept in parts. Dental-record code still sends short labels only (ADR 0010).

Every "secret" here is made up, and written in pieces so that no scanner reads a token in this file."""
import json
import time

import pytest

from health_transformation_lab_nlp.paths import REPO_ROOT

pytest.importorskip("opentelemetry.sdk")

from health_transformation_lab_nlp import telemetry as tm

T0 = 1_763_000_000_000_000_000
PW = "S3cret" + "Passw0rd"
KEY20 = "abcd1234" + "efgh5678ijkl"
HEX32 = "0123456789abcdef" * 2
JWT = "eyJhbGciOiJIUzI1NiJ9" + "." + "eyJzdWIiOiIxMjM0NTY3ODkwIn0" + "." + "SflKxwRJSMeKKF2QT4fwpMeJf36POk6yJV"
PEM_BODY = "MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSj" + "FAKEFAKEFAKE"
PEM = "-----BEGIN " + "PRIVATE KEY-----\n" + PEM_BODY + "\n-----END " + "PRIVATE KEY-----"
AWS_SECRET = "wJalrXUtnFEMI/K7MDENG" + "/bPxRfiCYEXAMPLEKEY"


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


SHAPES = {"Kaggle": "KGAT_" + "a1B2c3D4" * 4, "Hugging Face": "hf_" + "Zx9" * 12,
          "GitHub ghp": "ghp_" + "Q7w" * 12, "GitHub gho": "gho_" + "Q7w" * 12, "GitHub ghu": "ghu_" + "Q7w" * 12,
          "GitHub ghs": "ghs_" + "Q7w" * 12, "GitHub ghr": "ghr_" + "Q7w" * 12,
          "GitHub fine-grained": "github_pat_" + "11AB_cd" * 6, "sk-": "sk-" + "proj_9fK" * 4,
          "Stripe-style": "sk_" + "live_" + "FAKEfake" * 3, "AWS id": "AKIA" + "ABCDEFGH12345678",
          "AWS temporary id": "ASIA" + "ABCDEFGH12345678", "Databricks": "dapi" + HEX32,
          "Google": "AIza" + "SyA-FAKEFAKEFAKEFAKEFAKEFAKEFAKE123", "Slack": "xoxb-" + "123456789012-FAKEfakeFAKE",
          "PyPI": "pypi-" + "AgEIcHlwaS5vcmcCJGZha2VmYWtl", "GitLab": "glpat-" + "FAKEfakeFAKEfakeFAKE",
          "npm": "npm_" + "FAKEfake" * 5, "Modal secret": "as-" + "FAKEfakeFAKEfakeFAKEfa", "JSON web token": JWT}


@pytest.mark.parametrize("kind", sorted(SHAPES))
def test_token_shapes_are_redacted(kind):
    secret = SHAPES[kind]
    out = tm.scrub(f"see {secret}\ncurl -H 'x: {secret}' https://example.org")
    assert secret not in out and out.count(tm.REDACTED) == 2 and "curl -H" in out


LEAKS = {   # what a run's commands, files and outputs hold: the text, and what must not survive
    "export NAME=value": (f"export API_KEY={KEY20}", KEY20),
    "legacy Kaggle key": (f"export KAGGLE_KEY={HEX32}", HEX32),
    "NAME=value before a command": (f"PGPASSWORD={PW} psql -h db -U app", PW),
    "printenv line": (f"MY_SERVICE_TOKEN={KEY20}", KEY20),
    "printenv AWS secret": (f"AWS_SECRET_ACCESS_KEY={AWS_SECRET}", AWS_SECRET),
    "dotenv quoted": (f'SECRET_KEY="{KEY20}"', KEY20),
    "double-quoted export": (f'export DB_PASSWORD="{PW}"', PW),
    "single-quoted export": (f"export DB_PASSWORD='{PW}'", PW),
    "mysql -p": (f"mysql -u root -p{PW} appdb", PW),
    "curl -u": (f"curl -u admin:{PW} https://example.org/api", PW),
    "docker login -p": (f"docker login -u someone -p {PW} registry.example.org", PW),
    "--password value": (f"tool login --username admin --password {PW}", PW),
    "--token=value": (f"tool --token={KEY20} sync", KEY20),
    "X-API-Key header": (f'curl -H "X-API-Key: {KEY20}" https://example.org', KEY20),
    "Authorization: Basic": ("curl -H 'Authorization: Basic YWRtaW46UzNjcmV0UGFzc3cwcmQ=' https://example.org",
                             "YWRtaW46UzNjcmV0UGFzc3cwcmQ="),
    "Authorization: token": (f"Authorization: token {HEX32}", HEX32),
    "a short Bearer token": ("authorization: BEARER ab12CD34ef56", "ab12CD34ef56"),
    "Cookie": (f"Cookie: sessionid={HEX32}", HEX32),
    "user:password in a URL": (f"git clone https://someuser:{PW}@github.com/org/repo.git", PW),
    "database URL": (f'engine = create_engine("postgresql://app:{PW}@db:5432/app")', PW),
    "api_key in a query": (f"GET https://example.org/v1/items?api_key={KEY20}&page=2", KEY20),
    "Azure SAS": ("https://acct.blob.core.windows.net/c/b?sv=2022&sig=AbCdEfGhIjKlMnOp0123456789%2Bab%3D", "AbCdEfGhIjKlMnOp0123"),
    "InstrumentationKey": ("InstrumentationKey=0f0f0f0f-1111-2222-3333-444444444444;IngestionEndpoint=https://x.example/", "0f0f0f0f"),
    "AccountKey": ("AccountName=acct;AccountKey=FAKEfake0FAKEfake1==;EndpointSuffix=core.windows.net", "FAKEfake0FAKEfake1"),
    "SharedAccessKey": ("Endpoint=sb://x/;SharedAccessKey=FAKEfake0FAKEfake1=", "FAKEfake0FAKEfake1"),
    "SharedAccessSignature": ("SharedAccessSignature=sr%3Dx%26sig%3DFAKE0fake1", "FAKE0fake1"),
    "password = literal": (f'password = "{PW}"', PW),
    "a passphrase of two words": ('password = "correct horse"', "correct horse"),
    "secret = literal": (f'client_secret = "{KEY20}"', KEY20),
    "passwd: literal": (f"passwd: '{PW}'", PW),
    "api_key keyword": (f'client = Client(api_key="{KEY20}")', KEY20),
    "os.environ item": (f'os.environ["API_KEY"] = "{KEY20}"', KEY20),
    "getenv default": (f'token = os.getenv("TOKEN", "{KEY20}")', KEY20),
    "auth tuple": (f'requests.get(url, auth=("admin", "{PW}"))', PW),
    "bytes literal": (f'password = b"{PW}"', PW),
    "a value holding an apostrophe": ('password = "it\'s-S3cret-Passw0rd"', "S3cret-Passw0rd"),
    "a five-character value": ('token = "ab12X"', "ab12X"),
    "key, private_key, passphrase, pwd, credentials": (
        f'key = "{KEY20}"\nprivate_key = "{HEX32}"\npassphrase = "{PW}"\npwd = "x9{PW}"\ncredentials = "y8{KEY20}"', "S3cret"),
    "header dict": (f'headers = {{"X-Api-Key": "{KEY20}"}}', KEY20),
    "YAML without quotes": (f"database:\n  user: app\n  password: {PW}\n", PW),
    "aws credentials file": (f"[default]\naws_secret_access_key = {AWS_SECRET}", AWS_SECRET),
    ".netrc": (f"machine github.com login someone password {PW}", PW),
    "private key block": (PEM, PEM_BODY),
    "JSON token": (json.dumps({"access_token": JWT, "token_type": "bearer"}), JWT),
    "kaggle.json": (json.dumps({"username": "someone", "key": HEX32}), HEX32),
    "service account": (json.dumps({"type": "service_account", "private_key_id": HEX32, "private_key": PEM}), PEM_BODY),
    "docker config": (json.dumps({"auths": {"r.example.org": {"auth": "c29tZW9uZTpTM2NyZXRQYXNzdzByZA=="}}}), "c29tZW9uZTpT"),
    "ARM output": (json.dumps({"instrumentationKey": "0f0f0f0f-1111-2222-3333-444444444444"}), "0f0f0f0f"),
    "arguments as JSON, double-quoted export": (json.dumps({"command": f'export DB_PASSWORD="{PW}" && pytest'}), PW),
    "arguments as JSON, a written file": (json.dumps({"filepath": "settings.py", "content": f'PASSWORD = "{PW}"\n'}), PW),
    "a tool's output as a JSON string": (json.dumps({"content": f'api_key = "{KEY20}"\n'}), KEY20),
    "JSON inside JSON": (json.dumps({"stdout": json.dumps({"access_token": JWT})}), JWT),
    "a diff's added line": (f'+++ b/settings.py\n@@ -1 +1 @@\n-API_TOKEN = None\n+API_TOKEN = "{KEY20}"', KEY20),
    "a diff's added .env line": (f"+++ b/.env\n@@ -0,0 +1 @@\n+API_TOKEN={KEY20}", KEY20),
}


@pytest.mark.parametrize("case", sorted(LEAKS))
def test_a_secret_in_a_command_a_file_or_an_output_is_redacted(case):
    text, secret = LEAKS[case]
    out = tm.scrub(text)
    assert secret not in out and tm.REDACTED in out, out


ORDINARY = [
    "def login(username: str, password: str, token: str | None = None):",
    "    user = authenticate(username=username, password=form_data.password)",
    "    return get_token(user)  # the token's type",
    'return {"access_token": access_token, "token_type": "bearer"}',
    'oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")',
    'oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")',
    'tokenizer = "bert-base-uncased"',
    'bos_token = "<|startoftext|>"',
    'password_field = "new_password"',
    'API_KEY_NAME = "X-API-Key"',
    '{"password": "Password must be at least 8 characters"}',
    '"max_tokens": "unlimited"',
    'data={"username": "johndoe", "password": "secret"}',
    'secret_file = "/run/secrets/app"',
    'parser.add_argument("--token", help="API token to use")',
    "git checkout -b task-refactor-authentication-flow",
    "Collecting flask-debugtoolbar-sqlalchemy-panel",
    "scripts/disk-usage-report-generator.py",
    "HTTP Bearer authentication_credentials are read from the header",
    'headers={"WWW-Authenticate": "Bearer"}',
    'headers = {"Authorization": f"Bearer {token}"}',
    "sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
    "commit 3f786850e387550fdab836ed7e6dc881de23001b",
    "request_id=0f0f0f0f-1111-2222-3333-444444444444",
    "session_cookie: str = Cookie(None)",
    "PIP_KEYRING_PROVIDER=disabled TOKEN_TTL=3600 SSH_KEY_PATH=/home/user/.ssh/id_ed25519",
    "password: SecretStr",
    "mkdir -p build/output && ls -u",
]


@pytest.mark.parametrize("code", ORDINARY)
def test_ordinary_code_is_left_as_it_is(code):
    assert tm.scrub(code) == code


def test_what_a_scrubber_of_shapes_gets_wrong_is_known():
    """Recorded, not wanted: a quoted value with a digit under a telling name is redacted even when it is a type's
    name, and a password that is one plain word is taken for ordinary text (ADR 0010, "Harder")."""
    assert tm.scrub('def refresh(token: "OAuth2Token") -> None:') == f'def refresh(token: "{tm.REDACTED}") -> None:'
    assert tm.scrub('password = "hunter"') == 'password = "hunter"'


@pytest.mark.parametrize("text", ["passwordless_" + "Qx7_" * 100_000 + ' token_value = "abcd1234"', "token" * 40_000,
                                  "PASSWORD_" * 20_000, 'key="' * 20_000, "Bearer " * 20_000, "https://" * 20_000,
                                  "-----BEGIN " + "PRIVATE KEY-----\n" + "A" * 100_000])
def test_scrubbing_long_and_repetitive_text_stays_fast(text):
    """A tool's output can be one long word or one phrase many times over: no rule may go quadratic on it."""
    start = time.perf_counter()
    tm.scrub(text)
    assert time.perf_counter() - start < 2.0


def test_the_process_own_secret_values_are_redacted_as_written_and_as_json_escapes_them(monkeypatch):
    monkeypatch.setenv("MY_SERVICE_API_KEY", 'plain"value\\with-no-known-shape')
    monkeypatch.setenv("APPLICATIONINSIGHTS_CONNECTION_STRING", "Endpoint=https://y.example/;Something=else-entirely")
    monkeypatch.setenv("HOME_DIR_NAME", "plainvalue-that-is-not-secret")
    monkeypatch.setenv("PIP_KEYRING_PROVIDER", "import-disabled")        # KEYRING is not KEY
    monkeypatch.setenv("SHORT_TOKEN", "short77")                          # under 12 characters: too likely a word
    raw = 'a plain"value\\with-no-known-shape b plainvalue-that-is-not-secret c import-disabled d short77'
    assert tm.scrub(raw) == f"a {tm.REDACTED} b plainvalue-that-is-not-secret c import-disabled d short77"
    assert 'plain\\"value' not in tm.scrub(json.dumps({"stdout": raw}))
    assert tm.scrub("x Endpoint=https://y.example/;Something=else-entirely y") == f"x {tm.REDACTED} y"


def test_scrub_value_redacts_under_telling_keys_and_inside_every_text():
    value = {"command": f'export DB_PASSWORD="{PW}" && pytest', "password": "plainwordpass9", "token_type": "bearer",
             "nested": [{"client_secret": KEY20, "note": f"see {SHAPES['Kaggle']}"}, 3, None, True], "count": 2}
    out = tm.scrub_value(value)
    assert out["password"] == tm.REDACTED and out["token_type"] == "bearer" and out["count"] == 2
    assert out["nested"][0] == {"client_secret": tm.REDACTED, "note": f"see {tm.REDACTED}"} and out["nested"][1:] == [3, None, True]
    assert PW not in out["command"] and out["command"].endswith("&& pytest")
    assert value["password"] == "plainwordpass9", "the value passed in is not changed"


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
    secret = SHAPES["Hugging Face"]
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


def test_only_the_run_forwarder_puts_text_on_a_span():
    """ADR 0010: text reaches a span through content_span, and nothing but the forwarder of a coding-agent run calls it."""
    callers = []
    for folder in ("python/health_transformation_lab_nlp", "python/scripts", "kaggle", "databricks"):
        for path in (REPO_ROOT / folder).rglob("*.py"):
            if "content_span(" in path.read_text(encoding="utf-8", errors="replace"):
                callers.append(path.relative_to(REPO_ROOT).as_posix())
    assert sorted(callers) == ["kaggle/forward_run_telemetry.py", "python/health_transformation_lab_nlp/telemetry.py"]
