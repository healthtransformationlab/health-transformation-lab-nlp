"""An LLM (MedGemma by default) as a note reader: note in, status/grade/extent out.

Exploratory (spec 004, docs/medgemma.md). The reader is a rung like any other:
fit(train) picks optional few-shot examples, predict(test) returns (labels, None).
Per-note details (raw output, quote, gate, tokens, latency, fallback) are kept in
`.details` and written next to the predictions.

Safeguards
  - Residual PHI scan before anything is sent; a flagged note is never sent.
  - Quote gate: the answer must quote the note's own words (capitals and runs of
    whitespace may differ, #134; the judge's gates in judge.py still match exactly).
  - Any failure (bad JSON, unknown status, failed gate, backend error) falls back
    to the note_rules prediction and is flagged, so scores stay comparable and the
    failure rate is visible.

Backends
  hf         local transformers. Multimodal MedGemma 4B via AutoModelForImageTextToText,
             text-only 27B via AutoModelForCausalLM; optional LoRA adapter. Needs
             `pip install -e ".[llm]"`, a Hugging Face login that has accepted the
             HAI-DEF terms, and ideally a GPU.
  openai     any OpenAI-compatible chat endpoint: Databricks Model Serving, vLLM,
             Ollama (http://localhost:11434/v1). READER_BASE_URL, READER_API_KEY,
             READER_MODEL; without READER_BASE_URL it uses the Databricks workspace in
             DATABRICKS_HOST / DATABRICKS_TOKEN (Foundation Model endpoints).
  simulated  no model; errs at set rates by difficulty level. Dry runs only;
             output files are prefixed simulated_.
"""

from __future__ import annotations

import json
import logging
import os
import random
import time
import urllib.request
from typing import ClassVar

import pandas as pd

from .deid import residual_scan
from .judge import CRITERIA
from .labels import LABELS
from .telemetry import traced

log = logging.getLogger("health_transformation_lab_nlp")
GRADES = {"A", "B", "C"}
EXTENTS = {"localized", "generalized", "molar_incisor"}

_ANSWER = """Answer with JSON only:
{"status": one of healthy, gingivitis, periodontitis_stage_1, periodontitis_stage_2, \
periodontitis_stage_3, periodontitis_stage_4,
 "grade": "A" | "B" | "C" | null (null unless periodontitis),
 "extent": "localized" | "generalized" | "molar_incisor" | null (null unless periodontitis),
 "quote": "the exact sentence or phrase from the note that decides the status, copied verbatim",
 "rationale": "one sentence"}"""

PROMPTS = {  # v2: AAP worksheet rules via the shared CRITERIA
    "reader-v2": ("You are a periodontist reading a de-identified dental chart note. Classify the "
                  "patient's periodontal status at this visit under the 2017 AAP/EFP classification.\n\n"
                  + CRITERIA + "\n\n" + _ANSWER),
    "reader-v2-terse": ("Classify periodontal status from this dental note (2017 AAP/EFP).\n\n"
                        + CRITERIA + "\n\n" + _ANSWER),
}
DEFAULT_VARIANT = "reader-v2"
USER = "Note:\n<<<\n{note}\n>>>"

_FINDING_WORDS = ("CAL", "attachment", "bone loss", "RBL", "PD ", "probing", "BOP", "pocket")


# ---------------------------------------------------------------- prompt
@traced
def build_messages(note: str, examples: list[tuple[str, str]] | None = None,
                   variant: str = DEFAULT_VARIANT) -> list[dict]:
    msgs = [{"role": "system", "content": PROMPTS[variant]}]
    for ex_note, ex_answer in examples or []:
        msgs += [{"role": "user", "content": USER.format(note=ex_note)},
                 {"role": "assistant", "content": ex_answer}]
    return msgs + [{"role": "user", "content": USER.format(note=note)}]


def _decisive_line(note: str) -> str:
    """A verbatim line to quote in example answers: measured findings first
    (they outrank a written diagnosis), then a diagnosis line, then the first line."""
    lines = [ln.strip() for ln in note.splitlines() if ln.strip()]
    for ln in lines:
        if any(w.lower() in ln.lower() for w in _FINDING_WORDS):
            return ln
    for ln in lines:
        if "diagnos" in ln.lower() or ln.lower().startswith("dx"):
            return ln
    return lines[0] if lines else ""


@traced
def target_answer(note: str, status: str, grade: str = "NA", extent: str = "NA") -> str:
    perio = status.startswith("periodontitis")
    g = grade if perio and grade in GRADES else None
    e = extent if perio and extent in EXTENTS else None
    return json.dumps({"status": status, "grade": g, "extent": e, "quote": _decisive_line(note),
                       "rationale": "From the charted findings and diagnosis in the note."})


@traced
def pick_examples(train: pd.DataFrame, k: int, seed: int = 0) -> list[tuple[str, str]]:
    """k synthetic training notes per status, chosen by seed."""
    rng = random.Random(seed)
    out = []
    for lab in LABELS:
        pool = train.index[train["label"] == lab].tolist()
        for i in rng.sample(pool, min(k, len(pool))):
            r = train.loc[i]
            out.append((r["note_text"], target_answer(r["note_text"], lab, str(r.get("grade", "NA")),
                                                       str(r.get("extent", "NA")))))
    return out


@traced
def sft_records(train: pd.DataFrame, variant: str = DEFAULT_VARIANT) -> list[dict]:
    """Chat-format fine-tuning records in exactly the reader's prompt/answer format."""
    recs = []
    for _, r in train.iterrows():
        msgs = build_messages(r["note_text"], variant=variant)
        msgs.append({"role": "assistant", "content": target_answer(
            r["note_text"], r["label"], str(r.get("grade", "NA")), str(r.get("extent", "NA")))})
        recs.append({"messages": msgs})
    return recs


# ---------------------------------------------------------------- parse + gate
THOUGHT_START, THOUGHT_END = "<unused94>", "<unused95>"  # MedGemma 1.5 thinking markers


def _fold(text: str) -> str:
    return " ".join(text.split()).casefold()


@traced
def quote_in_note(quote: str, note: str) -> bool:
    """The quote is a run of the note's own words: capitals and runs of whitespace may differ, nothing else
    (#134: a lower-case copy of an upper-case diagnosis line is still the note's words). A respelled,
    shortened or corrected word, or a quote stitched from separate places, still fails."""
    q = _fold(quote or "")
    return bool(q) and q in _fold(note)


@traced
def parse_answer(raw: str, note: str) -> dict:
    out = {"status": None, "grade": "NA", "extent": "NA", "quote": "", "gate_ok": False, "error": ""}
    if THOUGHT_START in raw:
        if THOUGHT_END not in raw:
            out["error"] = "parse: thought not closed"
            return out
        raw = raw[raw.rindex(THOUGHT_END) + len(THOUGHT_END):]
    try:
        s = raw[raw.index("{"): raw.rindex("}") + 1]
        d = json.loads(s)
    except (ValueError, json.JSONDecodeError) as e:
        out["error"] = f"parse: {type(e).__name__}"
        return out
    status, quote = d.get("status"), (d.get("quote") or "").strip()
    out["quote"] = quote
    if status not in LABELS:
        out["error"] = f"bad status {status!r}"
        return out
    out["status"] = status
    if status.startswith("periodontitis"):
        out["grade"] = d.get("grade") if d.get("grade") in GRADES else "NA"
        out["extent"] = d.get("extent") if d.get("extent") in EXTENTS else "NA"
    if not quote_in_note(quote, note):
        out["error"] = "quote not in note"
        return out
    out["gate_ok"] = True
    return out


# ---------------------------------------------------------------- backends
class OpenAIChat:
    name, simulated = "openai", False

    def __init__(self, model: str | None = None, base_url: str | None = None, api_key: str | None = None,
                 max_tokens: int = 300, max_retries: int = 3, timeout: int = 120):
        self.model = model or os.environ["READER_MODEL"]
        host = os.environ.get("DATABRICKS_HOST", "").strip().rstrip("/")
        if not (base_url or os.environ.get("READER_BASE_URL")) and host:   # Databricks Foundation Model endpoints
            base_url = (host if host.startswith("http") else f"https://{host}") + "/serving-endpoints"
            api_key = api_key or os.environ.get("DATABRICKS_TOKEN")
        self.base_url = (base_url or os.environ["READER_BASE_URL"]).rstrip("/")
        self.api_key = api_key or os.environ.get("READER_API_KEY", "none")
        self.max_tokens, self.max_retries, self.timeout = max_tokens, max_retries, timeout

    def __call__(self, messages: list[dict], visit_id=None) -> dict:
        body = json.dumps({"model": self.model, "temperature": 0, "max_tokens": self.max_tokens,
                           "messages": messages}).encode()
        req = urllib.request.Request(f"{self.base_url}/chat/completions", data=body, method="POST",
                                     headers={"Authorization": f"Bearer {self.api_key}",
                                              "Content-Type": "application/json"})
        err = ""
        for attempt in range(self.max_retries):
            t0 = time.time()
            try:
                with urllib.request.urlopen(req, timeout=self.timeout) as r:
                    resp = json.loads(r.read())
                u = resp.get("usage", {})
                return {"raw": resp["choices"][0]["message"]["content"], "input_tokens": u.get("prompt_tokens", 0),
                        "output_tokens": u.get("completion_tokens", 0), "latency_s": time.time() - t0}
            except Exception as e:  # noqa: BLE001 - network, rate limit: retry, then report
                err = f"{type(e).__name__}: {e}"
                time.sleep(2 ** attempt)
        return {"raw": "", "input_tokens": 0, "output_tokens": 0, "latency_s": 0.0, "error": err}


@traced
def pick_dtype(cuda: bool, capability: tuple | None, total_gb: float) -> str:
    """Weights dtype for the hardware: bfloat16 where the GPU has it natively (compute capability 8.0+:
    A10, A100, H100); float32 where the GPUs together have 20 GB or more (Kaggle's T4 x2: Gemma models
    can overflow in float16); float16 only as a last resort; float32 on CPU. DENTAL_LLM_DTYPE overrides."""
    import os
    forced = os.environ.get("DENTAL_LLM_DTYPE", "").strip()
    if forced:
        return forced
    if not cuda:
        return "float32"
    if capability and tuple(capability) >= (8, 0):
        return "bfloat16"
    return "float32" if total_gb >= 20 else "float16"


def _hardware_dtype() -> str:  # pragma: no cover - needs torch
    import torch
    if not torch.cuda.is_available():
        return pick_dtype(False, None, 0)
    n = torch.cuda.device_count()
    total = sum(torch.cuda.get_device_properties(i).total_memory for i in range(n)) / 1e9
    dtype = pick_dtype(True, torch.cuda.get_device_capability(0), total)
    if dtype == "float16":
        log.warning("float16 on this GPU: Gemma models can overflow; choose 'GPU T4 x2' on Kaggle for float32")
    return dtype


class HFChat:  # pragma: no cover - needs model weights and the [llm] extra
    """Local transformers generation, greedy. Loads lazily on first call."""

    name, simulated = "hf", False

    def __init__(self, hf_id: str, modality: str = "multimodal", adapter: str | None = None,
                 max_new_tokens: int = 300, dtype: str = "auto", device_map: str = "auto", revision: str | None = None,
                 version: str | None = None):
        self.hf_id, self.modality, self.adapter, self.revision = hf_id, modality, adapter, revision
        self.version = version or revision     # what each run records: the Hugging Face commit or the Kaggle version
        self.max_new_tokens, self.dtype, self.device_map = max_new_tokens, dtype, device_map
        self.model = None

    def _load(self):
        import torch
        from transformers import (
            AutoModelForCausalLM,
            AutoModelForImageTextToText,
            AutoProcessor,
            AutoTokenizer,
        )
        dtype = _hardware_dtype() if self.dtype == "auto" else self.dtype
        print(f"loading {self.hf_id} as {dtype}, revision {self.revision or 'latest (not pinned)'}", flush=True)
        kw = {"torch_dtype": getattr(torch, dtype), "device_map": self.device_map}
        if self.modality == "multimodal":
            self.proc = AutoProcessor.from_pretrained(self.hf_id, revision=self.revision)
            self.model = AutoModelForImageTextToText.from_pretrained(self.hf_id, revision=self.revision, **kw)
        else:
            self.proc = AutoTokenizer.from_pretrained(self.hf_id, revision=self.revision)
            self.model = AutoModelForCausalLM.from_pretrained(self.hf_id, revision=self.revision, **kw)
        if self.adapter:
            from peft import PeftModel
            self.model = PeftModel.from_pretrained(self.model, self.adapter)
        self.model.eval()

    def __call__(self, messages: list[dict], visit_id=None) -> dict:
        import torch
        if self.model is None:
            self._load()
        msgs = messages if self.modality != "multimodal" else [
            {"role": m["role"], "content": [{"type": "text", "text": m["content"]}]} for m in messages]
        t0 = time.time()
        inputs = self.proc.apply_chat_template(msgs, add_generation_prompt=True, tokenize=True,
                                               return_dict=True, return_tensors="pt").to(self.model.device)
        n = inputs["input_ids"].shape[-1]
        tok = getattr(self.proc, "tokenizer", self.proc)
        think = tok.convert_tokens_to_ids(THOUGHT_START)
        # answer directly: a thought block would use up max_new_tokens before the JSON
        no_think = {"suppress_tokens": [think]} if think != tok.unk_token_id else {}
        with torch.inference_mode():
            out = self.model.generate(**inputs, max_new_tokens=self.max_new_tokens, do_sample=False, **no_think)
        gen = out[0][n:]
        return {"raw": self.proc.decode(gen, skip_special_tokens=True), "input_tokens": int(n),
                "output_tokens": len(gen), "latency_s": time.time() - t0}


class SimulatedReader:
    """Dry-run reader. Knows the generator truth; errs more on harder notes.
    Error rates are placeholders, not estimates of MedGemma."""

    name, simulated = "simulated", True
    ERROR_BY_LEVEL: ClassVar[dict[str, float]] = {"L1": 0.05, "L2": 0.12, "L3": 0.30}

    def __init__(self, truth: dict, level: dict | None = None, seed: int = 0):
        self.truth, self.level, self.rng = truth, level or {}, random.Random(seed)

    def __call__(self, messages: list[dict], visit_id=None) -> dict:
        note = messages[-1]["content"].removeprefix("Note:\n<<<\n").removesuffix("\n>>>")
        t = self.truth[visit_id]
        status = t
        if self.rng.random() < self.ERROR_BY_LEVEL.get(self.level.get(visit_id, "L2"), 0.12):
            i = LABELS.index(t)
            near = [LABELS[j] for j in (i - 1, i + 1) if 0 <= j < len(LABELS)]
            status = self.rng.choice(near if self.rng.random() < 0.8 else [x for x in LABELS if x != t])
        return {"raw": target_answer(note, status), "input_tokens": (len(PROMPTS[DEFAULT_VARIANT]) + len(note)) // 4,
                "output_tokens": 60, "latency_s": 0.0}


def _hf_token() -> str | None:
    """HF_TOKEN, or the token `huggingface-cli login` cached under HF_HOME (as huggingface_hub looks)."""
    if tok := os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN"):
        return tok
    home = os.environ.get("HF_HOME") or os.path.join(os.path.expanduser("~"), ".cache", "huggingface")
    path = os.environ.get("HF_TOKEN_PATH") or os.path.join(home, "token")
    if not os.path.exists(path):
        return None
    with open(path) as f:
        return f.read().strip() or None


_HF_TOKEN_FIX = ("make a new read token at huggingface.co -> Settings -> Access tokens (short lifetime), put it in "
                 "the Databricks secret scope health_transformation_lab, key hf_token, and record its expiry in "
                 "ops/secrets_register.yaml")


@traced
def check_hf_access(repo: str, api=None) -> None:
    """One cheap authenticated call before any work (AGENTS.md, #230): fails at once, naming HF_TOKEN, when the
    token is missing, refused (expired or revoked) or has no access to the gated repo. The token never appears
    in the message."""
    token = _hf_token()
    if not token:
        raise RuntimeError(f"HF_TOKEN is not set, so {repo} (gated) can't be read: {_HF_TOKEN_FIX}")
    if api is None:
        from huggingface_hub import HfApi
        api = HfApi()
    try:
        api.auth_check(repo, token=token)
    except Exception as e:  # noqa: BLE001 - any refusal or network error stops the run here, with the reason
        status = getattr(getattr(e, "response", None), "status_code", None)
        why = {401: "was refused by Hugging Face (expired or revoked)",
               403: f"has no access to {repo} (accept its terms on Hugging Face with the token's account)"}.get(
            status, f"could not be checked ({type(e).__name__}, status {status})")
        raise RuntimeError(f"HF_TOKEN {why}. To fix: {_HF_TOKEN_FIX}") from None


@traced
def make_backend(entry: dict, kind: str, **kw):
    if kind == "hf":
        weights = kw.get("weights")   # a local transformers folder (Kaggle: kaggle/keras_to_hf.py); no token needed
        if entry.get("gated") and not weights and not _hf_token():
            raise RuntimeError(f"{entry['hf']} is gated ({entry.get('license', 'see its model card')}): accept "
                               "the terms on its Hugging Face page, then set HF_TOKEN to a read token from that account")
        if weights:   # converted Kaggle Models weights: their Kaggle version is the pin, recorded with each run
            return HFChat(weights, entry.get("modality", "multimodal"), adapter=kw.get("adapter"),
                          version=entry.get("kaggle", "local weights"))
        return HFChat(entry["hf"], entry.get("modality", "multimodal"), adapter=kw.get("adapter"),
                      revision=entry.get("revision"))
    if kind == "openai":
        return OpenAIChat(model=kw.get("endpoint") or entry.get("endpoint"))
    raise ValueError(f"backend {kind!r} needs to be constructed directly (simulated needs the truth)")


@traced
def summarize_details(d: pd.DataFrame) -> dict:
    """One run's reliability and cost inputs from its llm_details file."""
    return {"gate_pass": d["gate_ok"].mean(), "fallback": d["fallback"].mean(),
            "input_tokens_mean": d["input_tokens"].mean(), "output_tokens_mean": d["output_tokens"].mean(),
            "latency_s_mean": d["latency_s"].mean()}


# ---------------------------------------------------------------- rung
class LLMReader:
    def __init__(self, model_id: str, backend=None, shots: int = 0, variant: str = DEFAULT_VARIANT,
                 seed: int = 0, entry: dict | None = None, backend_kind: str | None = None, **backend_kw):
        self.model_id, self.shots, self.variant, self.seed = model_id, shots, variant, seed
        self.backend = backend or make_backend(entry or {"hf": model_id},
                                               backend_kind or os.environ.get("READER_BACKEND", "hf"), **backend_kw)
        self.examples: list[tuple[str, str]] = []
        self.details = pd.DataFrame()

    @traced
    def fit(self, train: pd.DataFrame):
        self.examples = pick_examples(train, self.shots, self.seed) if self.shots and len(train) else []
        return self

    @traced
    def predict(self, test: pd.DataFrame):
        from .note_reader import read_note
        preds, rows = [], []
        for _, r in test.iterrows():
            note, vid = r["note_text"], r.get("visit_id")
            row = {"visit_id": vid, "model": self.model_id, "backend": self.backend.name,
                   "revision": getattr(self.backend, "version", None) or getattr(self.backend, "revision", None) or "",
                   "prompt_version": self.variant, "shots": self.shots, "input_tokens": 0, "output_tokens": 0,
                   "latency_s": 0.0, "raw": "", "status": None, "grade": "NA", "extent": "NA", "quote": "",
                   "gate_ok": False, "error": ""}
            if residual_scan(note):
                row["error"] = "residual PHI pattern: not sent"
            else:
                res = self.backend(build_messages(note, self.examples, self.variant), visit_id=vid)
                row.update({k: res.get(k, row[k]) for k in ("input_tokens", "output_tokens", "latency_s")})
                row["raw"] = (res.get("raw") or "")[:2000]
                if res.get("error"):
                    row["error"] = "backend: " + res["error"]
                else:
                    row.update(parse_answer(row["raw"], note))
            row["fallback"] = not row["gate_ok"]
            pred = row["status"] if row["gate_ok"] else read_note(note)
            row["pred"] = pred
            preds.append(pred)
            rows.append(row)
        self.details = pd.DataFrame(rows)
        return preds, None
