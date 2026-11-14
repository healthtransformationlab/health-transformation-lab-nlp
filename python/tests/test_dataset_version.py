"""Spec 039 US1 (#707): every published dataset declares one semantic version and a changelog, newest first, in
kaggle/dataset_docs.yaml. The gate that a changed file or column set needs a new version is in
test_kaggle_dataset_docs.py, beside the file and column derivation it reuses."""
import pytest
import yaml

from health_transformation_lab_nlp import dataset_version as dv
from health_transformation_lab_nlp.paths import REPO_ROOT

SLUGS = sorted(yaml.safe_load((REPO_ROOT / "kaggle" / "dataset_docs.yaml").read_text())["datasets"])


@pytest.mark.parametrize("slug", SLUGS)
def test_every_dataset_declares_a_version_and_its_changelog(slug):
    assert dv.problems(slug) == []
    assert dv.latest_change(slug) == dv.changelog(slug)[0]
    assert dv.latest_change(slug).startswith(f"{dv.version(slug)} — ")


GOOD = {
    "version": "1.1.0",
    "changelog": ["1.1.0 — adds visits_truth.csv", "1.0.0 — first versioned release"],
    "schema_sha256": "a" * 64,
}


def _docs(tmp_path, **entry):
    path = tmp_path / "dataset_docs.yaml"
    path.write_text(yaml.safe_dump({"datasets": {"d": {**GOOD, **entry}}}, allow_unicode=True))
    return path


def test_a_well_formed_declaration_reads_back_with_no_problems(tmp_path):
    docs = _docs(tmp_path)
    assert dv.problems("d", docs=docs) == []
    assert dv.version("d", docs=docs) == "1.1.0"
    assert dv.changelog("d", docs=docs) == GOOD["changelog"]
    assert dv.latest_change("d", docs=docs) == "1.1.0 — adds visits_truth.csv"


@pytest.mark.parametrize(
    ("entry", "says"),
    [
        ({"version": None}, "no version"),
        ({"version": "1.1"}, "is not MAJOR.MINOR.PATCH"),
        ({"version": "v1.1.0"}, "is not MAJOR.MINOR.PATCH"),
        ({"version": "1.2.0"}, "top changelog line is for 1.1.0"),  # a bump with no changelog line
        ({"changelog": []}, "no changelog"),
        ({"changelog": ["1.1.0 adds visits_truth.csv", "1.0.0 — first versioned release"]}, "is not \"X.Y.Z — "),
        ({"changelog": ["1.1.0 — adds visits_truth.csv", "1.1.0 — first versioned release"]}, "newest first"),
        ({"version": "1.0.0", "changelog": ["1.0.0 — first versioned release", "1.1.0 — adds visits_truth.csv"]},
         "newest first"),
    ],
)
def test_a_bad_declaration_is_reported(tmp_path, entry, says):
    problems = dv.problems("d", docs=_docs(tmp_path, **entry))
    assert any(says in p for p in problems), problems


def test_a_published_set_that_changed_without_a_new_version_is_reported_with_the_semver_rule(tmp_path):
    docs = _docs(tmp_path)
    assert dv.problems("d", schema_sha256="a" * 64, docs=docs) == []
    (problem,) = dv.problems("d", schema_sha256="b" * 64, docs=docs)
    assert "published files or columns changed" in problem
    for part in ("MAJOR", "MINOR", "PATCH", "changelog", "b" * 64):
        assert part in problem


def test_an_undeclared_dataset_is_reported_not_raised(tmp_path):
    assert dv.problems("not-a-dataset", docs=_docs(tmp_path)) == ["not-a-dataset: not in dataset_docs.yaml"]
    with pytest.raises(KeyError):
        dv.version("not-a-dataset", docs=_docs(tmp_path))
