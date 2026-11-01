"""Publishing the synthetic data and results as Kaggle datasets (spec 020, kaggle/publish.py)."""

import importlib.util
import json
import subprocess
import sys

import pytest

from health_transformation_lab_nlp.paths import REPO_ROOT

_spec = importlib.util.spec_from_file_location("publish", REPO_ROOT / "kaggle" / "publish.py")
pub = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pub)


def _build(tmp_path, name):
    out = tmp_path / name
    subprocess.run([sys.executable, str(REPO_ROOT / "kaggle" / "publish.py"), "--dataset", name, "--out", str(out),
                    "--username", "someone", "--commit", "abc1234"], check=True)
    return out, json.loads((out / "dataset-metadata.json").read_text())


@pytest.mark.parametrize("name", sorted(pub.DATASETS))
def test_listed_files_exist_and_are_neither_simulated_nor_external(name):
    files = pub.files_of(name)
    assert files
    for dest, src in files.items():
        assert src.exists(), src
        rel = src.relative_to(REPO_ROOT).as_posix()
        assert not src.name.startswith("simulated_"), rel
        assert not rel.startswith(("data/external/", "data/raw/")), rel
        assert not dest.startswith("/") and ".." not in dest


@pytest.mark.parametrize("name", sorted(pub.DATASETS))
def test_built_folder_holds_exactly_the_listed_files(tmp_path, name):
    out, _ = _build(tmp_path, name)
    built = {p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file()}
    assert built == set(pub.files_of(name)) | {"dataset-metadata.json"}


@pytest.mark.parametrize("name", sorted(pub.DATASETS))
def test_metadata_is_cc_by_with_a_card_and_kaggle_length_limits(tmp_path, name):
    _, meta = _build(tmp_path, name)
    assert meta["licenses"] == [{"name": "CC-BY-4.0"}]
    owner, slug = meta["id"].split("/")
    assert owner == "someone" and 6 <= len(slug) <= 50 and slug == slug.lower()
    assert 6 <= len(meta["title"]) <= 50 and 20 <= len(meta["subtitle"]) <= 80
    card = meta["description"].lower()
    for words in ("synthetic", "not affiliated", "not for clinical", "cc by 4.0", "github.com/healthtransformationlab/health-transformation-lab-nlp",
                  "abc1234"):
        assert words in card, words
    for f in pub.files_of(name):              # the card lists every file
        assert f"`{f}`" in meta["description"], f


def test_no_simulated_file_reaches_the_results_dataset():
    names = [d.split("/")[-1] for d in pub.files_of("results")]
    assert not [n for n in names if n.startswith("simulated_")]
    assert "ai_predictions_medgemma-1.5-4b-it.csv" in names


def test_workflow_uploads_through_publish_py_with_the_commit():
    text = (REPO_ROOT / ".github" / "workflows" / "kaggle-publish.yml").read_text()
    assert "kaggle/publish.py" in text and "--upload" in text and "github.sha" in text
    assert "kaggle datasets create" not in text      # the CLI prints a refused upload and exits 0: publish.py checks
    assert "environment: dev" in text


# ---- review of #126: partial or simulated files, and failed uploads that looked like successes

def _review_rows():
    import pandas as pd
    return len(pd.read_csv(pub.DATA / "answer_key" / "review_key.csv", usecols=["visit_id"]))


def test_every_prediction_file_is_a_full_run():
    # 11_ai_predict.py --limit N writes the same file name: a smoke test must never be published as a result
    import pandas as pd
    for dest, src in pub.files_of("results").items():
        if dest.startswith(("ai_predictions_", "llm_details_")):
            assert len(pd.read_csv(src)) == _review_rows(), dest


@pytest.mark.parametrize("name", sorted(pub.DATASETS))
def test_no_published_row_is_simulated(name):
    import pandas as pd
    for dest, src in pub.files_of(name).items():
        if src.suffix == ".csv":
            d = pd.read_csv(src, dtype=str)
            hit = d.apply(lambda c: c.str.startswith(("sim:", "calib:"), na=False)).any().any()
            assert not hit, dest


def test_build_refuses_a_partial_prediction_file(tmp_path, monkeypatch):
    bad = tmp_path / "ai_predictions_x.csv"
    bad.write_text("visit_id,pred\n1,healthy\n")
    monkeypatch.setattr(pub, "files_of", lambda name: {"ai_predictions_x.csv": bad})
    with pytest.raises(SystemExit, match="ai_predictions_x.csv"):
        pub.check("results")


class _Result:
    def __init__(self, status="ok", error="", invalid=None):
        self.status, self.error, self.invalidTags, self.url = status, error, invalid or [], "https://kaggle/x"


class _Api:
    def __init__(self, exists, result):
        self.exists, self.result, self.calls = exists, result, []

    def dataset_status(self, ref):
        if not self.exists:
            raise RuntimeError("404")
        return "ready"

    def dataset_create_new(self, folder, public, **kw):
        self.calls.append(("create", public, kw.get("dir_mode")))
        return self.result

    def dataset_create_version(self, folder, notes, **kw):
        self.calls.append(("version", notes, kw.get("dir_mode")))
        return self.result


def test_upload_creates_public_then_versions(tmp_path):
    api = _Api(False, _Result())
    assert pub.upload(tmp_path, "o/d", "note (abc)", api) == "https://kaggle/x"
    assert api.calls == [("create", True, "zip")]
    api = _Api(True, _Result())
    pub.upload(tmp_path, "o/d", "note (abc)", api)
    assert api.calls == [("version", "note (abc)", "zip")]


@pytest.mark.parametrize("result", [_Result("error", "bad licence"), None])
def test_upload_fails_when_kaggle_says_no(tmp_path, result):
    with pytest.raises(SystemExit, match="Kaggle"):
        pub.upload(tmp_path, "o/d", "n", _Api(True, result))


def test_invalid_tags_warn_but_do_not_fail(tmp_path, capsys):
    pub.upload(tmp_path, "o/d", "n", _Api(True, _Result(invalid=["model comparison"])))
    assert "model comparison" in capsys.readouterr().out


def test_datasets_and_collection_are_named_for_the_bench():
    """Spec 022: the Kaggle names follow perio_bench."""
    assert {k: d["slug"] for k, d in pub.DATASETS.items()} == {"notes": "perio-bench-notes",
                                                                   "results": "perio-bench-results"}
    readme = (REPO_ROOT / "kaggle" / "README.md").read_text()
    assert '"Health Transformation Lab: Perio Bench"' in readme and "perio-bench-note-classifier" in readme


def test_the_readme_does_not_ask_for_a_public_collection():
    """Issue #270: Kaggle offers no public setting for a collection; the README's table is the shared index."""
    readme = (REPO_ROOT / "kaggle" / "README.md").read_text()
    section = readme.split("## The collection", 1)[1].split("\n## ", 1)[0]
    assert "Make it public" not in section and "private" in section
    assert "What's on Kaggle" in section
