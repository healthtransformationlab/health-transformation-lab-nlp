"""Spec 039 US3 (#709): one release string, from the dataset's declaration (#707), is Kaggle's version note and Hugging
Face's commit message. A release is tagged data/<slug>-vX.Y.Z in git and on Hugging Face, and tagging it twice changes
nothing."""
import importlib.util
import re
import subprocess
import sys

import pytest
import yaml

from health_transformation_lab_nlp import dataset_version as dv
from health_transformation_lab_nlp.paths import REPO_ROOT


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


kpub = _load("kaggle_publish_for_release", REPO_ROOT / "kaggle" / "publish.py")
hpub = _load("hf_publish_for_release", REPO_ROOT / "huggingface" / "publish.py")
SLUG, COMMIT = "perio-bench-notes", "0123456789abcdef0123456789abcdef01234567"
SLUGS = ["perio-bench-notes", "perio-bench-results", "health-transformation-lab-coding-agent-tasks"]


class Git:
    """Stands in for git: a remote that may already hold the tag. Records each git subcommand run."""

    def __init__(self, remote_has=False):
        self.remote_has, self.calls = remote_has, []

    def __call__(self, cmd, **kw):
        self.calls.append(cmd[1])
        out = f"{'f' * 40}\t{cmd[-1]}\n" if cmd[1] == "ls-remote" and self.remote_has else ""
        return subprocess.CompletedProcess(cmd, 0, stdout=out, stderr="")


class HfApi:
    """Stands in for huggingface_hub.HfApi's tag calls."""

    def __init__(self, tags=()):
        self.tags, self.created = list(tags), []

    def list_repo_refs(self, repo_id, repo_type=None):
        return type("Refs", (), {"tags": [type("Ref", (), {"name": t})() for t in self.tags]})()

    def create_tag(self, repo_id, *, tag, repo_type=None, exist_ok=False):
        self.created.append((repo_id, tag, repo_type))
        self.tags.append(tag)


# --- the release string and the tag name ----------------------------------------------------------------------------

def test_the_release_message_names_the_version_the_change_and_the_commit():
    message = dv.release_message(SLUG, COMMIT)
    what = dv.latest_change(SLUG).split(" — ", 1)[1]
    assert message == f"v{dv.version(SLUG)} — {what} (0123456789ab)"
    assert message.count(dv.version(SLUG)) == 1   # the version isn't written twice


def test_a_commit_that_is_not_a_git_sha_has_no_release_message():
    with pytest.raises(ValueError, match="git commit"):
        dv.release_message(SLUG, "HEAD")


@pytest.mark.parametrize("slug", SLUGS)
def test_the_release_tag_is_a_well_formed_git_ref(slug):
    tag = dv.release_tag(slug)
    assert tag == f"data/{slug}-v{dv.version(slug)}"
    assert re.fullmatch(r"data/[a-z0-9-]+-v\d+\.\d+\.\d+", tag)
    assert subprocess.run(["git", "check-ref-format", f"refs/tags/{tag}"]).returncode == 0
    assert dv.git_tag_url(tag) == f"https://github.com/healthtransformationlab/health-transformation-lab-nlp/tree/{tag}"


# --- the same string on both platforms ------------------------------------------------------------------------------

def test_kaggle_and_hugging_face_get_the_same_release_string(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(kpub, "upload", lambda folder, ref, message, api: sent.append(("kaggle", message)) or "u")
    monkeypatch.setattr(hpub, "upload", lambda folder, repo, message, api, repo_type="dataset", **create:
                        sent.append(("hugging face", message)) or "u")
    kpub.publish("notes", tmp_path, {"id": f"someone/{SLUG}"}, COMMIT, api=None)
    hpub.publish_dataset("notes", tmp_path, COMMIT, api=None)
    note = dv.release_message(SLUG, COMMIT)
    assert sent == [("kaggle", note), ("hugging face", note)]


# --- tags: made once, then left alone -------------------------------------------------------------------------------

def test_a_new_git_tag_is_made_on_the_commit_and_pushed():
    git = Git()
    assert dv.create_git_tag("data/x-v1.0.0", COMMIT, run=git) is True
    assert git.calls == ["ls-remote", "tag", "push"]


def test_a_git_tag_the_remote_already_has_is_left_alone():
    git = Git(remote_has=True)
    assert dv.create_git_tag("data/x-v1.0.0", COMMIT, run=git) is False
    assert git.calls == ["ls-remote"]


def test_a_real_git_tag_pushed_twice_is_made_once(tmp_path):
    def git(*args, cwd):
        return subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True, text=True).stdout.strip()

    remote, work = tmp_path / "remote.git", tmp_path / "work"
    git("init", "--bare", "-q", str(remote), cwd=tmp_path)
    git("init", "-q", str(work), cwd=tmp_path)
    git("-c", "user.name=t", "-c", "user.email=t@example.org", "commit", "--allow-empty", "-q", "-m", "x", cwd=work)
    git("remote", "add", "origin", str(remote), cwd=work)
    commit = git("rev-parse", "HEAD", cwd=work)
    run = lambda cmd, **kw: subprocess.run(cmd, cwd=work, **kw)  # noqa: E731
    tag = "data/perio-bench-notes-v1.1.0"
    assert dv.create_git_tag(tag, commit, run=run) is True
    assert dv.create_git_tag(tag, commit, run=run) is False
    assert git("rev-parse", f"refs/tags/{tag}", cwd=remote) == commit


def test_the_hugging_face_tag_is_made_once():
    api, repo, tag = HfApi(), "healthtransformationlab/perio-bench-notes", "data/perio-bench-notes-v1.1.0"
    assert hpub.tag(api, repo, tag) is True
    assert hpub.tag(api, repo, tag) is False
    assert api.created == [(repo, tag, "dataset")]


def test_a_tagged_hugging_face_release_marks_both_places_and_prints_the_urls(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(hpub, "upload", lambda *a, **k: "u")
    git, api = Git(), HfApi()
    hpub.publish_dataset("notes", tmp_path, COMMIT, api, tag=True, run=git)
    tag = dv.release_tag(SLUG)
    assert api.created == [(hpub.repo_id("notes"), tag, "dataset")]
    assert git.calls == ["ls-remote", "tag", "push"]
    out = capsys.readouterr().out
    assert dv.release_message(SLUG, COMMIT) in out and dv.git_tag_url(tag) in out
    assert f"https://huggingface.co/datasets/{hpub.repo_id('notes')}/tree/data%2F" in out


def test_a_tagged_kaggle_release_makes_the_git_tag_and_prints_its_url(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(kpub, "upload", lambda *a, **k: "u")
    git = Git()
    kpub.publish("notes", tmp_path, {"id": f"someone/{SLUG}"}, COMMIT, None, tag=True, run=git)
    assert git.calls == ["ls-remote", "tag", "push"]
    out = capsys.readouterr().out
    assert dv.release_message(SLUG, COMMIT) in out and dv.git_tag_url(dv.release_tag(SLUG)) in out


def test_without_tag_no_tag_is_made(tmp_path, monkeypatch):
    monkeypatch.setattr(kpub, "upload", lambda *a, **k: "u")
    monkeypatch.setattr(hpub, "upload", lambda *a, **k: "u")
    git, api = Git(), HfApi()
    kpub.publish("notes", tmp_path, {"id": f"someone/{SLUG}"}, COMMIT, None, run=git)
    hpub.publish_dataset("notes", tmp_path, COMMIT, api, run=git)
    assert git.calls == [] and api.created == []


@pytest.mark.parametrize("script, args", [
    ("kaggle/publish.py", ["--dataset", "notes", "--username", "u", "--upload", "--metadata-only", "--tag"]),
    ("kaggle/publish.py", ["--dataset", "notes", "--username", "u", "--tag"]),
    ("kaggle/publish_tasks.py", ["--username", "u", "--upload", "--metadata-only", "--tag"]),
    ("huggingface/publish.py", ["--dataset", "notes", "--tag"]),
    ("huggingface/publish.py", ["--org-card", "--upload", "--tag"]),
])
def test_a_tag_without_a_new_version_fails_at_once(tmp_path, script, args):
    """A metadata refresh, a build that isn't uploaded and the organisation page make no version, so no tag."""
    done = subprocess.run([sys.executable, str(REPO_ROOT / script), "--out", str(tmp_path / "out"),
                           "--commit", COMMIT, *args], capture_output=True, text=True)
    assert done.returncode != 0 and "--tag marks a new version" in done.stderr   # our check, not an unknown option
    assert not (tmp_path / "out").exists()   # nothing was built


# --- the workflows ----------------------------------------------------------------------------------------------------

@pytest.mark.parametrize("workflow, job", [("kaggle-publish.yml", "kaggle"), ("kaggle-publish.yml", "huggingface"),
                                           ("kaggle-publish-tasks.yml", "publish")])
def test_each_publishing_job_tags_its_release_and_may_push_the_tag(workflow, job):
    wf = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / workflow).read_text())
    spec = wf["jobs"][job]
    assert spec["permissions"]["contents"] == "write"   # to push the tag
    run = next(s["run"] for s in spec["steps"] if "--upload" in s.get("run", "") and "publish" in s["run"])
    assert "--tag" in run
    if job != "huggingface":   # Hugging Face's --message is for the organisation page only
        assert "--message" not in run
        assert 'only="--metadata-only" || only="--tag"' in run   # a metadata refresh is never tagged
