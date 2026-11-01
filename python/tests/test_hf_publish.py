"""Spec 025: the PerioBench datasets on Hugging Face (huggingface/publish.py), from spec 020's file lists."""

import importlib.util
import subprocess
import sys

import pandas as pd
import pytest
import yaml

from health_transformation_lab_nlp.paths import REPO_ROOT


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


kpub = _load("kaggle_publish", REPO_ROOT / "kaggle" / "publish.py")
hpub = _load("hf_publish", REPO_ROOT / "huggingface" / "publish.py")


def _build(tmp_path, name):
    out = tmp_path / name
    subprocess.run([sys.executable, str(REPO_ROOT / "huggingface" / "publish.py"), "--dataset", name, "--out", str(out),
                    "--commit", "abc1234"], check=True)
    return out


def _header(out):
    text = (out / "README.md").read_text(encoding="utf-8")
    assert text.startswith("---\n")
    head, body = text[4:].split("\n---\n", 1)
    return yaml.safe_load(head), body


@pytest.mark.parametrize("name", sorted(kpub.DATASETS))
def test_raw_holds_exactly_spec_020s_files(tmp_path, name):
    out = _build(tmp_path, name)
    raw = {p.relative_to(out / "raw").as_posix() for p in (out / "raw").rglob("*") if p.is_file()}
    assert raw == set(kpub.files_of(name))                       # FR-001: one list for both platforms
    extra = {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()} - {f"raw/{r}" for r in raw}
    assert extra <= {"README.md", "data/train.csv", "data/test.csv", "perio_bench_quickstart.ipynb"}


def test_notes_splits_share_columns_and_test_is_the_review_set(tmp_path):
    out = _build(tmp_path, "notes")
    train, test = pd.read_csv(out / "data" / "train.csv"), pd.read_csv(out / "data" / "test.csv")
    key = pd.read_csv(out / "raw" / "review_key.csv")
    assert list(train.columns) == list(test.columns)
    assert {"note_text", "label", "grade", "extent"} <= set(train.columns)
    assert len(test) == len(key) == 240 and set(test.visit_id) == set(key.visit_id)
    assert (test.set_index("visit_id").label == key.set_index("visit_id").truth_status).all()
    assert not set(train.visit_id) & set(test.visit_id)          # never train on the review notes


@pytest.mark.parametrize("name", sorted(kpub.DATASETS))
def test_card_header_parses_and_every_config_path_exists(tmp_path, name):
    out = _build(tmp_path, name)
    head, _ = _header(out)
    assert head["license"] == "cc-by-4.0" and head["language"] == ["en"]
    assert "synthetic" in head["tags"]
    defaults = [c for c in head["configs"] if c.get("default")]
    assert len(defaults) == 1
    for c in head["configs"]:
        files = c["data_files"] if isinstance(c["data_files"], list) else [{"path": c["data_files"]}]
        for f in files:
            matches = list(out.glob(f["path"]))
            assert matches, (c["config_name"], f["path"])
            assert not any(m.name.startswith("simulated_") for m in matches)


@pytest.mark.parametrize("name", sorted(kpub.DATASETS))
def test_card_starts_with_a_quick_start_and_carries_the_labels(tmp_path, name):
    _, body = _header(_build(tmp_path, name))
    start = body.index("## Quick start")
    assert start < body.index("## How it was made")
    assert f'"healthtransformationlab/perio-bench-{name}"' in body
    assert "colab.research.google.com/github/healthtransformationlab/health-transformation-lab-nlp" in body
    assert "kaggle.com/datasets/jcblearning/perio-bench-" in body                 # FR-002: links the other platform
    for label in ("Everything here is synthetic", "not affiliated", "not for clinical use", "CC BY 4.0"):
        assert label in body, label
    assert "abc1234" in body


def test_a_refused_build_stays_refused(monkeypatch):
    monkeypatch.setattr(hpub.kpub, "check", lambda name: (_ for _ in ()).throw(SystemExit("simulated row")))
    with pytest.raises(SystemExit, match="simulated row"):
        hpub.build("notes", REPO_ROOT / "build" / "never", "abc1234")


def test_upload_creates_public_then_commits_naming_the_commit(tmp_path):
    calls = []

    class Api:
        def create_repo(self, **kw):
            calls.append(("create", kw))

        def upload_folder(self, **kw):
            calls.append(("upload", kw))
            return "https://huggingface.co/datasets/healthtransformationlab/perio-bench-notes/commit/1"

    hpub.upload(tmp_path, "healthtransformationlab/perio-bench-notes", "Update (abc1234)", Api())
    (_, create), (_, up) = calls
    assert create == {"repo_id": "healthtransformationlab/perio-bench-notes", "repo_type": "dataset",
                      "private": False, "exist_ok": True}
    assert up["commit_message"] == "Update (abc1234)" and up["repo_type"] == "dataset"
    assert up["delete_patterns"] == hpub.DELETE and ".gitattributes" not in str(hpub.DELETE)   # dropped files go


def test_org_card_names_the_benchmarks_and_links_everything():
    card = hpub.org_card()
    head, body = card[4:].split("\n---\n", 1)
    assert yaml.safe_load(head)["sdk"] == "static"
    for text in ("PerioBench", "OralHealthBench", "AccessBench", "healthtransformationlab.org",
                 "github.com/healthtransformationlab", "perio-bench-notes", "perio-bench-results",
                 "Personal learning project", "synthetic"):
        assert text in body, text


def test_the_token_check_fails_fast_and_names_the_setting():
    with pytest.raises(SystemExit, match="HF_PUBLISH_TOKEN"):
        hpub.check_token("", whoami=lambda t: {})
    with pytest.raises(SystemExit, match="hf_"):
        hpub.check_token("abc", whoami=lambda t: {})
    with pytest.raises(SystemExit, match="can't write"):
        hpub.check_token("hf_x", whoami=lambda t: {"name": "someone", "orgs": [{"name": "other", "roleInOrg": "write"}]})
    ok = {"name": "someone", "orgs": [{"name": "healthtransformationlab", "roleInOrg": "admin"}]}
    assert hpub.check_token("hf_x", whoami=lambda t: ok) == "someone"
    scoped = {"auth": {"accessToken": {"role": "fineGrained", "fineGrained": {"scoped": [
        {"entity": {"type": "org", "name": "healthtransformationlab"}, "permissions": ["repo.content.read"]}]}}}}
    with pytest.raises(SystemExit, match="can't write"):                  # a read-only fine-grained token
        hpub.check_token("hf_x", whoami=lambda t: {**ok, **scoped})
    scoped["auth"]["accessToken"]["fineGrained"]["scoped"][0]["permissions"].append("repo.write")
    assert hpub.check_token("hf_x", whoami=lambda t: {**ok, **scoped}) == "someone"


def test_one_workflow_publishes_to_either_platform_and_checks_the_token_first():
    wf = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "kaggle-publish.yml").read_text())
    inputs = wf[True]["workflow_dispatch"]["inputs"]
    assert inputs["platform"]["options"] == ["both", "kaggle", "huggingface"]
    assert inputs["platform"]["default"] == "both"
    hf = wf["jobs"]["huggingface"]
    assert hf["environment"] == "dev" and "kaggle" in hf["if"]
    names = [s.get("name", "") for s in hf["steps"]]
    check = names.index("Check the Hugging Face token (value stays masked)")
    publish = next(i for i, n in enumerate(names) if n.startswith("Build and publish"))
    assert check < publish                                       # the setting is checked before any work
    run = hf["steps"][publish]["run"]
    assert "huggingface/publish.py" in run and "--upload" in run and "--org-card" in run
    assert "github.sha" in str(hf["steps"][publish]["env"])
    kg = "\n".join(s.get("run", "") for s in wf["jobs"]["kaggle"]["steps"])
    assert "prepare_kernel.py --job quickstart" in kg and "kaggle kernels status" in kg


def test_the_publish_token_is_in_the_secrets_register_with_its_scope():
    reg = yaml.safe_load((REPO_ROOT / "ops" / "secrets_register.yaml").read_text())["credentials"]
    tok = next(c for c in reg if "HF_PUBLISH_TOKEN" in c["stored_in"])
    assert "healthtransformationlab" in tok["scope"] and "write" in tok["scope"]
    assert tok["expires"] and "kaggle-publish.yml" in tok["used_by"]


def test_the_workflow_falls_back_to_hf_token_and_the_check_names_both():
    # issue #249: the owner's existing HF_TOKEN secret is used when HF_PUBLISH_TOKEN isn't set
    wf = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "kaggle-publish.yml").read_text())
    for step in wf["jobs"]["huggingface"]["steps"]:
        if "HF_PUBLISH_TOKEN" in str(step.get("env", {})):
            assert step["env"]["HF_PUBLISH_TOKEN"] == "${{ secrets.HF_PUBLISH_TOKEN || secrets.HF_TOKEN }}"
    for token, match in (("", "HF_PUBLISH_TOKEN or HF_TOKEN"), ("abc", "HF_PUBLISH_TOKEN or HF_TOKEN")):
        with pytest.raises(SystemExit, match=match):
            hpub.check_token(token, whoami=lambda t: {})
    reg = yaml.safe_load((REPO_ROOT / "ops" / "secrets_register.yaml").read_text())["credentials"]
    assert "HF_TOKEN" in next(c for c in reg if "HF_PUBLISH_TOKEN" in c["stored_in"])["stored_in"]


def test_the_token_check_forgives_paste_mistakes():
    # issue #255: a token pasted with a line break, quotes or as a NAME=value line is still the token
    ok = {"name": "someone", "orgs": [{"name": "healthtransformationlab", "roleInOrg": "admin"}]}
    seen = []
    for raw in (" hf_abc\n", '"hf_abc"', "'hf_abc'", "HF_PUBLISH_TOKEN=hf_abc", "HF_TOKEN = 'hf_abc'\r\n",
                '"HF_TOKEN=hf_abc"', "export HF_TOKEN=hf_abc"):
        assert hpub.clean_token(raw) == "hf_abc", raw
        assert hpub.check_token(raw, whoami=lambda t: seen.append(t) or ok) == "someone"
    assert set(seen) == {"hf_abc"}                               # Hugging Face only ever sees the cleaned token


def test_a_wrong_token_is_described_without_printing_it():
    # issue #255: say which secret was read and what the value looks like, never the value
    secret = "HF_TOKEN"
    with pytest.raises(SystemExit) as e:
        hpub.check_token(secret, whoami=lambda t: {}, source="HF_PUBLISH_TOKEN")
    msg = str(e.value)
    assert "HF_PUBLISH_TOKEN" in msg and "8 characters" in msg and "name" in msg
    with pytest.raises(SystemExit) as e:
        hpub.check_token("abcdefghijklmnopqrstuvwxyz0123456789", whoami=lambda t: {}, source="HF_TOKEN")
    msg = str(e.value)
    assert "from HF_TOKEN" in msg and "36 characters" in msg and "abcdef" not in msg
    with pytest.raises(SystemExit, match="Bearer"):
        hpub.check_token("Bearer hf_abc", whoami=lambda t: {})


def test_the_workflow_tells_the_check_which_secret_it_read():
    wf = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "kaggle-publish.yml").read_text())
    steps = [s for s in wf["jobs"]["huggingface"]["steps"] if "HF_PUBLISH_TOKEN" in str(s.get("env", {}))]
    assert steps
    for step in steps:
        assert step["env"]["HF_TOKEN_SOURCE"] == \
            "${{ secrets.HF_PUBLISH_TOKEN != '' && 'HF_PUBLISH_TOKEN' || 'HF_TOKEN' }}"
    check = next(s for s in steps if s["name"].startswith("Check the Hugging Face token"))
    assert "HF_TOKEN_SOURCE" in check["run"]
