"""Spec 034 US1 (#533): every Kaggle dataset describes every file and column, with a cover, sources and an update
frequency (the parts of Kaggle's usability score our datasets lacked)."""
import importlib.util
import json
import shutil
import sys

import pytest

from health_transformation_lab_nlp.paths import REPO_ROOT, TASKS_DIR


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


sys.path.insert(0, str(REPO_ROOT / "kaggle"))
docs = _load("dataset_docs", REPO_ROOT / "kaggle" / "dataset_docs.py")
pub = _load("publish", REPO_ROOT / "kaggle" / "publish.py")

TASKS_SLUG = "health-transformation-lab-coding-agent-tasks"
ALL_SLUGS = [pub.DATASETS[n]["slug"] for n in sorted(pub.DATASETS)] + [TASKS_SLUG]


@pytest.mark.parametrize("name", sorted(pub.DATASETS))
def test_every_published_file_and_column_is_described(name):
    assert docs.missing(pub.DATASETS[name]["slug"], pub.files_of(name)) == []


def _task_files(tmp_path):
    """The task set's files as it publishes them: the committed CSVs, the sample rows as tasks.jsonl, and one of
    each built file (git-ignored, so stand-ins here)."""
    d = tmp_path / "t"
    d.mkdir()
    shutil.copyfile(TASKS_DIR / "tasks_sample.jsonl", d / "tasks.jsonl")
    files = {"tasks.jsonl": d / "tasks.jsonl", "tasks_excluded.csv": TASKS_DIR / "tasks_excluded.csv",
             "task_gates.csv": TASKS_DIR / "task_gates.csv"}
    for dest in ("snapshots/htlnlp_1.tgz", f"graphs/health-transformation-lab-nlp_{'a' * 40}.json",
                 f"embeddings/health-transformation-lab-nlp_{'a' * 40}.npz"):
        (d / dest).parent.mkdir(parents=True, exist_ok=True)
        (d / dest).write_bytes(b"x")
        files[dest] = d / dest
    return files


def test_every_task_set_file_and_column_is_described(tmp_path):
    assert docs.missing(TASKS_SLUG, _task_files(tmp_path)) == []


def test_an_undescribed_file_or_column_is_reported(tmp_path):
    p = tmp_path / "extra.csv"
    p.write_text("visit_id,brand_new_column\n1,2\n")
    assert docs.missing("perio-bench-notes", {"extra.csv": p}) == [
        "extra.csv: no file description", "extra.csv: column brand_new_column has no description"]


def test_resources_carry_a_description_for_each_file_and_column(tmp_path):
    files = _task_files(tmp_path)
    res = {r["path"]: r for r in docs.resources(TASKS_SLUG, files)}
    assert set(res) == set(files)
    assert all(r["description"] for r in res.values())
    fields = res["tasks.jsonl"]["schema"]["fields"]
    assert [f["name"] for f in fields] == list(json.loads(files["tasks.jsonl"].read_text().splitlines()[0]))
    assert all(f["description"] for f in fields)
    assert "schema" not in res[next(f for f in files if f.startswith("snapshots/"))]   # no columns in a .tgz


@pytest.mark.parametrize("slug", ALL_SLUGS)
def test_each_dataset_has_a_cover_sources_and_an_update_frequency(slug):
    meta = docs.dataset(slug)
    assert meta["expectedUpdateFrequency"] in docs.UPDATE_FREQUENCIES and meta["expectedUpdateFrequency"] != "not specified"
    assert "github.com/healthtransformationlab/health-transformation-lab-nlp" in meta["userSpecifiedSources"]
    cover = docs.cover(slug)
    assert cover.exists() and cover.suffix == ".png"
    from PIL import Image
    with Image.open(cover) as im:
        assert im.size == (1120, 560)                     # 2:1, as Kaggle crops covers


# --- publish.py sends them -------------------------------------------------------------------------------------

def test_the_build_carries_resources_sources_frequency_and_a_cover_beside_it(tmp_path):
    out = tmp_path / "notes"
    meta = pub.build("notes", out, "someone", "abc1234")
    assert {r["path"] for r in meta["resources"]} == set(pub.files_of("notes"))
    assert meta["userSpecifiedSources"] and meta["expectedUpdateFrequency"]
    side = pub.meta_dir(out)
    assert (side / "dataset-cover-image.png").exists()
    assert json.loads((side / "dataset-metadata.json").read_text()) == meta
    assert not list(out.glob("dataset-cover-image.*"))   # never uploaded as data


class FakeApi:
    def __init__(self, exists):
        self.exists, self.calls = exists, []

    def dataset_status(self, ref):
        if not self.exists:
            raise RuntimeError("404")

    def dataset_create_version(self, folder, message, dir_mode):
        self.calls.append(("version", folder))
        return type("R", (), {"status": "ok", "url": "u", "invalidTags": [], "error": None})()

    def dataset_create_new(self, folder, public, dir_mode):
        self.calls.append(("create", folder))
        return type("R", (), {"status": "ok", "url": "u", "invalidTags": [], "error": None})()

    def dataset_metadata_update(self, ref, path):
        self.calls.append(("metadata", ref, path))


@pytest.mark.parametrize("exists", [False, True])
def test_every_upload_then_sends_the_metadata_with_the_cover(tmp_path, exists):
    out = tmp_path / "notes"
    meta = pub.build("notes", out, "someone", "abc1234")
    api = FakeApi(exists)
    pub.upload(out, meta["id"], "m", api)
    assert [c[0] for c in api.calls] == ["version" if exists else "create", "metadata"]
    assert api.calls[-1] == ("metadata", meta["id"], str(pub.meta_dir(out)))


def test_metadata_only_sends_no_data(tmp_path):
    out = tmp_path / "notes"
    meta = pub.build("notes", out, "someone", "abc1234")
    api = FakeApi(True)
    pub.update_metadata(out, meta["id"], api)
    assert api.calls == [("metadata", meta["id"], str(pub.meta_dir(out)))]


def test_a_file_can_say_what_a_shared_column_name_means_in_it():   # #554: an LLM's grade is its answer
    assert "true" in docs.column_description("perio-bench-results", "train.csv", "grade").lower()
    answered = docs.column_description("perio-bench-results", "llm_details_medgemma-4b-it.csv", "grade")
    assert "answered" in answered.lower() and "true" not in answered.lower()
