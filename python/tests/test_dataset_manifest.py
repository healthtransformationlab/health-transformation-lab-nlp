"""Spec 039 US2 (#708): every published dataset carries manifest.json, built from the files being published: its
version, the git commit, when it was built, and each file's SHA-256, size and row count."""
import hashlib
import json
import subprocess
from datetime import datetime

import pytest

from health_transformation_lab_nlp import dataset_version as dv
from health_transformation_lab_nlp.paths import REPO_ROOT

SLUG = "perio-bench-notes"


def _head() -> str:
    return subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO_ROOT, capture_output=True, text=True,
                          check=True).stdout.strip()


def _sample(tmp_path):
    folder = tmp_path / "ds"
    (folder / "ladder").mkdir(parents=True)
    (folder / "train.csv").write_text('visit_id,note_text\n1,a\n2,"b, with a comma\nand a line break"\n')
    (folder / "ladder" / "empty.csv").write_text("method_name\n")
    (folder / "tasks.jsonl").write_text('{"id": 1}\n\n{"id": 2}\n')
    (folder / "graph.npz").write_bytes(bytes(range(256)))
    (folder / "dataset-metadata.json").write_text("{}")   # Kaggle's metadata for the upload, not data
    return folder


def test_the_manifest_lists_every_file_with_its_hash_size_and_rows(tmp_path):
    folder, commit = _sample(tmp_path), _head()
    manifest = dv.build_manifest(folder, SLUG, commit)
    assert manifest["slug"] == SLUG
    assert manifest["version"] == dv.version(SLUG)
    assert manifest["git_commit_sha"] == commit
    assert datetime.fromisoformat(manifest["built_ts"]).utcoffset().total_seconds() == 0   # UTC
    assert set(manifest["files"]) == {"train.csv", "ladder/empty.csv", "tasks.jsonl", "graph.npz"}
    for path, entry in manifest["files"].items():
        data = (folder / path).read_bytes()
        assert entry["sha256"] == hashlib.sha256(data).hexdigest()
        assert entry["bytes"] == len(data)
    assert manifest["files"]["train.csv"]["row_count"] == 2          # the header and a quoted line break don't count
    assert manifest["files"]["ladder/empty.csv"]["row_count"] == 0
    assert manifest["files"]["tasks.jsonl"]["row_count"] == 2        # nor do blank lines
    assert "row_count" not in manifest["files"]["graph.npz"]


def test_write_manifest_puts_it_in_the_folder_and_never_lists_itself(tmp_path):
    folder, commit = _sample(tmp_path), _head()
    path = dv.write_manifest(folder, SLUG, commit)
    assert path == folder / "manifest.json"
    first = json.loads(path.read_text())
    assert "manifest.json" not in first["files"]
    again = json.loads(dv.write_manifest(folder, SLUG, commit).read_text())
    same = lambda m: {k: v for k, v in m.items() if k != "built_ts"}  # noqa: E731
    assert same(again) == same(first)   # rebuilding the same files changes only built_ts


@pytest.mark.parametrize("commit", ["", "HEAD", "not-a-sha", "abc12"])
def test_a_commit_that_is_not_a_git_sha_is_refused(tmp_path, commit):
    with pytest.raises(ValueError, match="git commit"):
        dv.build_manifest(_sample(tmp_path), SLUG, commit)
