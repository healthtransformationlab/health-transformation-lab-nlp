"""Spec 004: MedGemma (or any LLM) as a note reader."""

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import ClassVar

import pandas as pd
import pytest

from health_transformation_lab_nlp import judge
from health_transformation_lab_nlp.labels import LABELS
from health_transformation_lab_nlp.paths import REPO_ROOT

NOTE = ("perio charting done: BOP 49%, PD up to 5mm, attachment loss 2-3 mm.\n"
        "Diagnosis: Localized Periodontitis Stage II Grade B.\n")


def _ans(status="periodontitis_stage_2", quote="Diagnosis: Localized Periodontitis Stage II Grade B.", **kw):
    return json.dumps({"status": status, "grade": "B", "extent": "localized", "quote": quote,
                       "rationale": "stated", **kw})


# ---------------------------------------------------------------- prompt + parse
def test_judge_prompt_unchanged_after_sharing_criteria():
    assert judge.SYSTEM.startswith("You are a periodontist auditing")
    assert judge.CRITERIA in judge.SYSTEM
    assert judge.PROMPT_VERSION == "judge-v2"
    assert "use radiographic bone loss only when CAL is not recorded" in " ".join(judge.CRITERIA.split())


def test_reader_prompt_shares_criteria_and_has_note():
    from health_transformation_lab_nlp.llm_reader import build_messages
    msgs = build_messages(NOTE)
    assert msgs[0]["role"] == "system" and judge.CRITERIA in msgs[0]["content"]
    assert NOTE in msgs[-1]["content"]
    terse = build_messages(NOTE, variant="reader-v2-terse")
    assert terse[0]["content"] != msgs[0]["content"]


def test_parse_valid_answer():
    from health_transformation_lab_nlp.llm_reader import parse_answer
    out = parse_answer("Sure!\n```json\n" + _ans() + "\n```", NOTE)
    assert out["gate_ok"] and out["status"] == "periodontitis_stage_2"
    assert out["grade"] == "B" and out["extent"] == "localized"


@pytest.mark.parametrize("raw,why", [
    ("not json at all", "parse"),
    (_ans(status="stage_two"), "bad status"),
    (_ans(quote="Periodontitis Stage III"), "quote not in note"),
    (_ans(quote=""), "quote not in note"),
])
def test_parse_failures_are_flagged(raw, why):
    from health_transformation_lab_nlp.llm_reader import parse_answer
    out = parse_answer(raw, NOTE)
    assert not out["gate_ok"] and why in out["error"]


# #134: the committed MedGemma 4B v1 run lost 3 of its 14 fallbacks to a quote that differed from the note
# only in capitals (the note's dx line in upper case, the quote in lower). The words are in the note, so the
# gate passes them; a changed word (respelled, shortened, a typo corrected) still fails.
CAPS_NOTE = "perio charting done: BOP 20%, CAL up to 2mm.\nD:LOCALIZED PERIODONTITIS, STAGE 1 GRADE A\ntx: srp\n"


@pytest.mark.parametrize("quote", [
    "localized periodontitis, stage 1 grade A",      # case only
    "Localized  Periodontitis,\tSTAGE 1 grade a",    # case and whitespace
    "BOP 20%,\nCAL up to 2mm",                       # a line break where the note has a space
])
def test_gate_accepts_case_and_whitespace_differences(quote):
    from health_transformation_lab_nlp.llm_reader import parse_answer
    raw = json.dumps({"status": "periodontitis_stage_1", "grade": "A", "extent": "localized", "quote": quote})
    out = parse_answer(raw, CAPS_NOTE)
    assert out["gate_ok"] and out["error"] == "" and out["quote"] == quote.strip()


@pytest.mark.parametrize("quote", [
    "Localised periodontitis, stage 1 grade A",       # respelled
    "Local periodontitis, stage 1 grade A",           # shortened
    "localized periodontitis stage 1 grade A",        # punctuation dropped
    "BOP 20%, CAL up to 3mm",                         # a number changed
])
def test_gate_still_rejects_changed_words(quote):
    from health_transformation_lab_nlp.llm_reader import parse_answer
    raw = json.dumps({"status": "periodontitis_stage_1", "grade": "A", "extent": "localized", "quote": quote})
    out = parse_answer(raw, CAPS_NOTE)
    assert not out["gate_ok"] and out["error"] == "quote not in note"


def test_parse_skips_medgemma_thought_block():
    # MedGemma 1.5 may think first: <unused94>thought ... <unused95> then the answer.
    from health_transformation_lab_nlp.llm_reader import parse_answer
    draft = _ans(status="healthy")
    out = parse_answer(f"<unused94>thought\nDraft: {draft}\nNo, it is stage II.<unused95>{_ans()}", NOTE)
    assert out["gate_ok"] and out["status"] == "periodontitis_stage_2"
    cut = parse_answer("<unused94>thought\nThe note says {stage} and then I ran out of tokens", NOTE)
    assert not cut["gate_ok"] and "thought not closed" in cut["error"]


def test_parse_normalizes_grade_and_extent():
    from health_transformation_lab_nlp.llm_reader import parse_answer
    out = parse_answer(_ans(status="healthy", grade=None, extent=None), NOTE)
    assert out["grade"] == "NA" and out["extent"] == "NA"


# ---------------------------------------------------------------- reader rung
class _Fixed:
    """Backend stub: returns canned raw text."""
    name, simulated = "stub", False

    def __init__(self, raw):
        self.raw, self.calls = raw, []

    def __call__(self, messages, visit_id=None):
        self.calls.append(messages)
        return {"raw": self.raw, "input_tokens": 100, "output_tokens": 30, "latency_s": 0.01}


def _reader(raw, **kw):
    from health_transformation_lab_nlp.llm_reader import LLMReader
    be = _Fixed(raw)
    return LLMReader("medgemma-4b-it", backend=be, **kw), be


def test_reader_predicts_and_records_details():
    r, _ = _reader(_ans())
    pred, proba = r.fit(pd.DataFrame()).predict(pd.DataFrame({"visit_id": [1], "note_text": [NOTE]}))
    assert pred == ["periodontitis_stage_2"] and proba is None
    d = r.details.iloc[0]
    assert d["gate_ok"] and not d["fallback"] and d["input_tokens"] == 100


def test_reader_falls_back_to_note_rules_on_bad_output():
    from health_transformation_lab_nlp.note_reader import read_note
    r, _ = _reader("garbage")
    pred, _ = r.predict(pd.DataFrame({"visit_id": [1], "note_text": [NOTE]}))
    assert pred == [read_note(NOTE)] and r.details.iloc[0]["fallback"]


def test_reader_never_sends_note_with_residual_phi():
    r, be = _reader(_ans())
    leaky = NOTE + "Call pt at 555-867-5309 re: appt.\n"
    pred, _ = r.predict(pd.DataFrame({"visit_id": [1], "note_text": [leaky]}))
    assert be.calls == [] and r.details.iloc[0]["fallback"]
    assert "residual PHI" in r.details.iloc[0]["error"] and pred[0] in LABELS


def test_few_shot_examples_seeded_k_per_status():
    from health_transformation_lab_nlp.llm_reader import pick_examples
    train = pd.DataFrame({"note_text": [f"note {i}" for i in range(60)],
                          "label": [LABELS[i % len(LABELS)] for i in range(60)]})
    a, b = pick_examples(train, 2, seed=1), pick_examples(train, 2, seed=1)
    assert a == b and len(a) == 2 * len(LABELS)
    assert sorted({json.loads(ans)["status"] for _, ans in a}) == sorted(LABELS)
    r, be = _reader(_ans(), shots=1)
    r.fit(train).predict(pd.DataFrame({"visit_id": [1], "note_text": [NOTE]}))
    assert len(be.calls[0]) == 1 + 2 * len(LABELS) + 1   # system + (user, assistant) per example + note


def test_make_rung_builds_llm_reader_for_llm_models():
    from health_transformation_lab_nlp.llm_reader import LLMReader
    from health_transformation_lab_nlp.registry import load_registry
    from health_transformation_lab_nlp.rungs import make_rung
    reg = load_registry()
    r = make_rung("medgemma-4b-it", reg, backend=_Fixed(_ans()))
    assert isinstance(r, LLMReader)
    assert {m["id"] for m in reg["models"] if m["role"] == "llm"} >= {
        "medgemma-4b-it", "medgemma-1.5-4b-it", "medgemma-27b-text-it"}


# ---------------------------------------------------------------- backends
class _FakeOpenAI(BaseHTTPRequestHandler):
    seen: ClassVar[list] = []

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        _FakeOpenAI.seen.append((self.path, self.headers["Authorization"], body))
        out = json.dumps({"choices": [{"message": {"content": _ans()}}],
                          "usage": {"prompt_tokens": 321, "completion_tokens": 45}}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *a):
        pass


def test_openai_backend_round_trip():
    from health_transformation_lab_nlp.llm_reader import LLMReader, OpenAIChat
    srv = HTTPServer(("127.0.0.1", 0), _FakeOpenAI)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    try:
        be = OpenAIChat(model="medgemma-endpoint", base_url=f"http://127.0.0.1:{srv.server_port}/v1",
                        api_key="tok")
        r = LLMReader("medgemma-4b-it", backend=be)
        pred, _ = r.predict(pd.DataFrame({"visit_id": [7], "note_text": [NOTE]}))
    finally:
        srv.shutdown()
    path, auth, body = _FakeOpenAI.seen[-1]
    assert path == "/v1/chat/completions" and auth == "Bearer tok"
    assert body["model"] == "medgemma-endpoint" and body["temperature"] == 0
    assert pred == ["periodontitis_stage_2"] and r.details.iloc[0]["input_tokens"] == 321


def test_simulated_backend_is_labelled_and_seeded():
    from health_transformation_lab_nlp.llm_reader import LLMReader, SimulatedReader
    truth = {i: LABELS[i % len(LABELS)] for i in range(200)}
    level = {i: ["L1", "L2", "L3"][i % 3] for i in range(200)}
    df = pd.DataFrame({"visit_id": list(truth), "note_text": [NOTE] * 200})
    p1, _ = LLMReader("medgemma-4b-it", backend=SimulatedReader(truth, level, seed=3)).predict(df)
    p2, _ = LLMReader("medgemma-4b-it", backend=SimulatedReader(truth, level, seed=3)).predict(df)
    assert p1 == p2 and SimulatedReader.simulated
    acc = sum(p == truth[i] for i, p in zip(truth, p1)) / 200
    assert 0.7 < acc < 0.95


# ---------------------------------------------------------------- judge family rule, fine-tune data
def test_families_of_evaluated_llms():
    from health_transformation_lab_nlp.registry import families_of, load_registry
    reg = load_registry()
    assert families_of(reg, ["tfidf_logreg", "medgemma-4b-it", "sim:medgemma-27b-text-it"]) == {"gemma"}
    assert families_of(reg, ["note_rules"]) == set()


def test_sft_records_use_reader_format():
    from health_transformation_lab_nlp.llm_reader import parse_answer, sft_records
    train = pd.DataFrame({"note_text": [NOTE], "label": ["periodontitis_stage_2"], "grade": ["B"],
                          "extent": ["localized"]})
    rec = sft_records(train)[0]
    assert [m["role"] for m in rec["messages"]] == ["system", "user", "assistant"]
    target = parse_answer(rec["messages"][-1]["content"], NOTE)
    assert target["gate_ok"] and target["status"] == "periodontitis_stage_2"


# ---- dtype for the GPU the reader lands on (Kaggle T4 / P100 have no native bfloat16) -------------

def test_pick_dtype_matches_the_hardware(monkeypatch):
    from health_transformation_lab_nlp.llm_reader import pick_dtype
    monkeypatch.delenv("DENTAL_LLM_DTYPE", raising=False)
    assert pick_dtype(cuda=True, capability=(8, 6), total_gb=24) == "bfloat16"     # A10 (Databricks)
    assert pick_dtype(cuda=True, capability=(7, 5), total_gb=30) == "float32"      # Kaggle T4 x2
    assert pick_dtype(cuda=True, capability=(6, 0), total_gb=16) == "float16"      # P100: last resort
    assert pick_dtype(cuda=False, capability=None, total_gb=0) == "float32"        # CPU


def test_pick_dtype_can_be_overridden(monkeypatch):
    from health_transformation_lab_nlp.llm_reader import pick_dtype
    monkeypatch.setenv("DENTAL_LLM_DTYPE", "float16")
    assert pick_dtype(cuda=True, capability=(8, 0), total_gb=80) == "float16"


def test_local_weights_need_no_hugging_face_token(monkeypatch, tmp_path):
    # Kaggle: MedGemma comes from Kaggle Models and is converted to a local transformers folder (no HF_TOKEN)
    from health_transformation_lab_nlp.llm_reader import HFChat, make_backend
    for v in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("HF_HOME", str(tmp_path))
    entry = {"hf": "google/medgemma-1.5-4b-it", "gated": True, "modality": "multimodal"}
    with pytest.raises(RuntimeError, match="gated"):
        make_backend(entry, "hf")
    b = make_backend(entry, "hf", weights=str(tmp_path / "medgemma-hf"))
    assert isinstance(b, HFChat) and b.hf_id == str(tmp_path / "medgemma-hf") and b.modality == "multimodal"


def test_weights_reach_the_reader_from_make_rung(monkeypatch, tmp_path):
    from health_transformation_lab_nlp.registry import load_registry
    from health_transformation_lab_nlp.rungs import make_rung
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.setenv("HF_HOME", str(tmp_path))
    r = make_rung("medgemma-1.5-4b-it", load_registry(), backend_kind="hf", weights="/kaggle/temp/x")
    assert r.backend.hf_id == "/kaggle/temp/x"


class _Refused(Exception):
    def __init__(self, status):
        super().__init__(f"{status} Client Error")
        self.response = type("R", (), {"status_code": status})()


class _Api:
    def __init__(self, status=None):
        self.status, self.calls = status, []

    def auth_check(self, repo, token=None):
        self.calls.append((repo, token))
        if self.status:
            raise _Refused(self.status)


def test_hugging_face_access_is_checked_with_one_call_before_any_work(monkeypatch):
    # #230: an expired token failed only when the weights loaded, after the GPU and the study build, and again on retry
    from health_transformation_lab_nlp.llm_reader import check_hf_access
    monkeypatch.setenv("HF_TOKEN", "hf_good")
    api = _Api()
    check_hf_access("google/medgemma-1.5-4b-it", api=api)
    assert api.calls == [("google/medgemma-1.5-4b-it", "hf_good")]


@pytest.mark.parametrize("status, says", [(401, "expired or revoked"), (403, "no access"), (500, "could not be checked")])
def test_a_refused_hugging_face_token_fails_at_once_naming_it(monkeypatch, status, says):
    from health_transformation_lab_nlp.llm_reader import check_hf_access
    monkeypatch.setenv("HF_TOKEN", "hf_old")
    with pytest.raises(RuntimeError, match=says) as e:
        check_hf_access("google/medgemma-1.5-4b-it", api=_Api(status))
    assert "HF_TOKEN" in str(e.value) and "hf_token" in str(e.value) and "hf_old" not in str(e.value)


def test_a_missing_hugging_face_token_fails_without_a_call(monkeypatch, tmp_path):
    from health_transformation_lab_nlp.llm_reader import check_hf_access
    for v in ("HF_TOKEN", "HUGGING_FACE_HUB_TOKEN"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("HF_HOME", str(tmp_path))
    api = _Api()
    with pytest.raises(RuntimeError, match="HF_TOKEN is not set"):
        check_hf_access("google/medgemma-1.5-4b-it", api=api)
    assert api.calls == []


def test_the_reader_notebook_checks_the_token_before_building_the_study():
    nb = (REPO_ROOT / "databricks" / "notebooks" / "03_medgemma_reader.py").read_text()
    assert "check_hf_access(" in nb
    assert nb.index("check_hf_access(") < nb.index("10_build_study.py")
