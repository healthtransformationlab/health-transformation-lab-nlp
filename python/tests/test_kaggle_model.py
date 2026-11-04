"""Spec 020 US3 (#122): the class-weighted ModernBERT-base note classifier as a public Kaggle model. The encoder
notebook keeps one rung's fine-tuned weights, kaggle/publish_model.py builds the model and instance folder with a
card scored from the same run, and the encoder workflow publishes it after a full run."""

import importlib.util
import json
import re
import subprocess
import sys

import pandas as pd
import pytest
import yaml

from health_transformation_lab_nlp.labels import LABELS
from health_transformation_lab_nlp.paths import DATASETS_DIR, REPO_ROOT
from health_transformation_lab_nlp.rungs import HFEncoder

_spec = importlib.util.spec_from_file_location("publish_model", REPO_ROOT / "kaggle" / "publish_model.py")
pm = importlib.util.module_from_spec(_spec)
sys.modules["publish_model"] = pm
_spec.loader.exec_module(pm)

NB = REPO_ROOT / "kaggle" / "encoder_gpu.ipynb"
WF = REPO_ROOT / ".github" / "workflows" / "kaggle-encoders.yml"
SCRIPT = REPO_ROOT / "python" / "scripts" / "11_ai_predict.py"
COMMITTED = DATASETS_DIR / "ai_predictions_modernbert-base+cw.csv"   # the committed run of the same rung


@pytest.fixture
def PREDICTIONS(tmp_path):
    """A full run on the current review notes. The committed GPU run was made on the notes before the #467 rebuild
    (rerun pending), so the keyword rules' answers stand in for it, under the rung's file name."""
    path = tmp_path / "runs" / COMMITTED.name
    path.parent.mkdir()
    pd.read_csv(DATASETS_DIR / "ai_predictions_note_rules.csv").to_csv(path, index=False)
    return path


def test_the_committed_run_made_on_the_old_notes_is_refused(tmp_path):
    from health_transformation_lab_nlp import note_set
    if note_set.is_current(DATASETS_DIR, COMMITTED.name):
        pytest.skip("the GPU run has been redone on the current notes")
    with pytest.raises(SystemExit, match="full run"):
        pm.build(_model_dir(tmp_path), COMMITTED, tmp_path / "b", "someone", "abc")


def _code():
    return "\n".join("".join(c["source"]) for c in json.loads(NB.read_text())["cells"] if c["cell_type"] == "code")


def _model_dir(tmp_path, labels=LABELS):
    d = tmp_path / "model"
    d.mkdir()
    (d / "config.json").write_text(json.dumps({"model_type": "modernbert", "id2label": dict(enumerate(labels))}))
    (d / "model.safetensors").write_bytes(b"weights")
    (d / "tokenizer.json").write_text("{}")
    return d


# ---- keeping the weights ------------------------------------------------------------------------------------

def test_encoder_saves_its_model_and_tokenizer_in_transformers_format(tmp_path):
    saved = []

    class _Part:
        def __init__(self, name):
            self.name = name

        def save_pretrained(self, path):
            saved.append((self.name, str(path)))

    enc = HFEncoder("answerdotai/ModernBERT-base")
    enc.model, enc.tok = _Part("model"), _Part("tokenizer")
    enc.save(tmp_path / "out")
    assert saved == [("model", str(tmp_path / "out")), ("tokenizer", str(tmp_path / "out"))]


def test_training_script_can_keep_the_fine_tuned_weights():
    script = SCRIPT.read_text()
    assert '"--save-model"' in script and "model.save(" in script


def test_notebook_keeps_one_rungs_weights_as_output():
    code = _code()
    assert re.search(r'^SAVE_MODEL = ""', code, flags=re.MULTILINE)       # nothing kept unless asked
    assert "/kaggle/working/model" in code and "--save-model" in code
    assert '"--class-weight", "sqrt"' in code                             # "modernbert-base+cw" in RUNGS


def test_prepared_kernel_names_the_rung_to_keep(tmp_path):
    out = tmp_path / "kernel"
    subprocess.run([sys.executable, str(REPO_ROOT / "kaggle" / "prepare_kernel.py"), "--job", "encoders",
                    "--out", str(out), "--username", "someone", "--rungs", "modernbert-base+cw",
                    "--save-model", "modernbert-base+cw", "--limit", "0"], check=True)
    nb = json.loads((out / "encoder_gpu.ipynb").read_text())
    settings = "".join(next(c["source"] for c in nb["cells"] if "BRANCH =" in "".join(c["source"])))
    assert 'SAVE_MODEL = "modernbert-base+cw"' in settings and 'RUNGS = "modernbert-base+cw"' in settings


# ---- the model folder and its card -------------------------------------------------------------------------

def test_built_folder_is_an_apache_licensed_public_transformers_model(tmp_path, PREDICTIONS):
    out = tmp_path / "build"
    meta, inst = pm.build(_model_dir(tmp_path), PREDICTIONS, out, "someone", "abc123def456")
    assert {"config.json", "model.safetensors", "tokenizer.json", "model-metadata.json",
            "model-instance-metadata.json"} <= {p.name for p in out.iterdir()}
    assert meta["ownerSlug"] == "someone" and meta["slug"] == "perio-bench-note-classifier"
    assert meta["isPrivate"] is False
    assert inst["framework"] == "transformers" and inst["licenseName"] == "Apache 2.0"
    assert inst["instanceSlug"] == "modernbert-base-cw" and inst["modelSlug"] == meta["slug"]
    assert inst["externalBaseModelUrl"] == "https://huggingface.co/answerdotai/ModernBERT-base"
    assert len(meta["subtitle"]) <= 80 and 5 <= len(meta["title"]) <= 50


def test_card_gives_the_same_runs_scores_and_says_synthetic(tmp_path, PREDICTIONS):
    _, inst = pm.build(_model_dir(tmp_path), PREDICTIONS, tmp_path / "b", "someone", "abc123def456")
    pred = pd.read_csv(PREDICTIONS)
    truth = pd.read_csv(DATASETS_DIR / "answer_key" / "review_key.csv").set_index("visit_id")["truth_status"]
    correct = (pred.set_index("visit_id")["pred"].reindex(truth.index) == truth).mean()
    card = inst["overview"] + inst["usage"]
    assert f"{100 * correct:.1f}" in card
    assert "synthetic" in card.lower() and "not clinical performance" in card.lower()
    assert "abc123def456" in card and "ai_predictions_modernbert-base+cw.csv" in card
    assert all(lab in card for lab in LABELS)


def test_build_refuses_a_partial_run(tmp_path, PREDICTIONS):
    part = tmp_path / "ai_predictions_modernbert-base+cw.csv"
    pd.read_csv(PREDICTIONS).head(10).to_csv(part, index=False)
    with pytest.raises(SystemExit, match="full run"):
        pm.build(_model_dir(tmp_path), part, tmp_path / "b", "someone", "abc")


def test_build_refuses_simulated_predictions(tmp_path, PREDICTIONS):
    sim = tmp_path / "simulated_ai_predictions_modernbert-base+cw.csv"
    pd.read_csv(PREDICTIONS).to_csv(sim, index=False)
    with pytest.raises(SystemExit, match="simulated"):
        pm.build(_model_dir(tmp_path), sim, tmp_path / "b", "someone", "abc")


@pytest.mark.parametrize("broken", ["no weights", "other labels"])
def test_build_refuses_a_model_folder_that_is_not_this_classifier(tmp_path, broken, PREDICTIONS):
    d = _model_dir(tmp_path, labels=LABELS if broken == "no weights" else ["a", "b"])
    if broken == "no weights":
        (d / "model.safetensors").unlink()
    with pytest.raises(SystemExit):
        pm.build(d, PREDICTIONS, tmp_path / "b", "someone", "abc")


# ---- upload ------------------------------------------------------------------------------------------------

class _Resp:
    def __init__(self, error=""):
        self.error, self.url, self.id = error, "https://kaggle/m", 0 if error else 7


class _Api:
    def __init__(self, model=False, instance=False, resp=None):
        self.model, self.instance, self.resp, self.calls = model, instance, resp or _Resp(), []

    def model_get(self, ref):
        if not self.model:
            raise RuntimeError("404")

    def model_instance_get(self, ref):
        if not self.instance:
            raise RuntimeError("404")

    def model_create_new(self, folder):
        self.calls.append("model")
        return self.resp

    def model_update(self, folder):
        self.calls.append("model card")
        return self.resp

    def model_instance_update(self, folder):
        self.calls.append("instance card")
        return self.resp

    def model_instance_create(self, folder, **kw):
        self.calls.append(("instance", kw.get("dir_mode")))
        return self.resp

    def model_instance_version_create(self, ref, folder, notes, **kw):
        self.calls.append(("version", ref, notes))
        return self.resp


def test_upload_creates_the_model_and_instance_then_versions(tmp_path):
    assert pm.upload(tmp_path, "o/perio-bench-note-classifier", "modernbert-base-cw", "n (abc)", _Api()) \
        == "https://kaggle/m"
    api = _Api()
    pm.upload(tmp_path, "o/perio-bench-note-classifier", "modernbert-base-cw", "n (abc)", api)
    assert api.calls == ["model", ("instance", "zip")]
    api = _Api(model=True, instance=True)       # a new version also refreshes both cards: scores of this run
    pm.upload(tmp_path, "o/perio-bench-note-classifier", "modernbert-base-cw", "n (abc)", api)
    assert api.calls == ["model card", "instance card",
                         ("version", "o/perio-bench-note-classifier/transformers/modernbert-base-cw", "n (abc)")]


def test_upload_fails_when_kaggle_says_no(tmp_path):
    with pytest.raises(SystemExit, match="Kaggle"):
        pm.upload(tmp_path, "o/m", "i", "n", _Api(model=True, resp=_Resp("bad licence")))


# ---- the workflow ------------------------------------------------------------------------------------------

def test_workflow_publishes_the_model_only_after_a_full_run():
    wf = yaml.safe_load(WF.read_text())
    inputs = wf.get("on", wf.get(True))["workflow_dispatch"]["inputs"]
    assert inputs["save_model"]["default"] == ""
    text = WF.read_text()
    assert '--save-model "${{ inputs.save_model }}"' in text
    step = next(s for s in wf["jobs"]["run"]["steps"] if s.get("name", "").startswith("Publish the model"))
    assert "inputs.save_model != ''" in step["if"] and "inputs.limit == '0'" in step["if"]
    assert "kaggle/publish_model.py" in step["run"] and "--upload" in step["run"]
    # the card names the commit the notebook trained (saved_model.json), not this workflow run's
    assert '--commit "$commit"' in step["run"] and "github.sha" not in step["run"]
    assert 'rev-parse", "HEAD"' in _code() and '"commit": commit.strip()' in _code()
    artifact = next(s for s in wf["jobs"]["run"]["steps"] if "upload-artifact" in s.get("uses", ""))
    assert "!build/output/model" in artifact["with"]["path"]     # the weights go to Kaggle, not the artifact
