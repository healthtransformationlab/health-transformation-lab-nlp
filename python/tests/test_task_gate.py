"""Spec 028 US3 (#453): our own fail-to-pass gate, following the competition harness's documented verification
(swegemma isn't distributed, #449). Each test builds a tiny git repo: a package with a bug, a test that catches
it, and a patch that fixes it."""

import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from health_transformation_lab_nlp import task_gate as tgate

BUGGY = "def add(a, b):\n    return a - b\n"
FIXED = "def add(a, b):\n    return a + b\n"
TEST = "from pkg.calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout


def commit_all(repo: Path, msg: str) -> str:
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", msg)
    return git(repo, "rev-parse", "HEAD").strip()


def write(repo: Path, rel: str, text: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def diff_of(repo: Path, base: str, paths: list[str]) -> str:
    return git(repo, "diff", base, "HEAD", "--", *paths)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    write(r, "python/pkg/__init__.py", "")
    write(r, "python/pkg/calc.py", BUGGY)
    write(r, "python/pyproject.toml", "[project]\nname = 'pkg'\n")
    return r


def make_task(repo: Path, fixed: str = FIXED, test: str = TEST, extra: dict | None = None) -> dict:
    """Commit the base, then the change; return a task row with patch and test_patch split like 55_build_tasks."""
    base = commit_all(repo, "base")
    write(repo, "python/pkg/calc.py", fixed)
    write(repo, "python/tests/test_calc.py", test)
    for rel, text in (extra or {}).items():
        write(repo, rel, text)
    commit_all(repo, "change")
    non_test = ["python/pkg/calc.py", *[p for p in (extra or {}) if not p.startswith("python/tests/")]]
    return {"instance_id": "t_1", "base_commit": base,
            "patch": diff_of(repo, base, non_test),
            "test_patch": diff_of(repo, base, ["python/tests/"])}


def worktrees(repo: Path) -> list[str]:
    return [ln for ln in git(repo, "worktree", "list", "--porcelain").splitlines() if ln.startswith("worktree ")]


def test_protected_paths_follow_the_harness_list():
    for p in ["python/tests/test_x.py", "pkg/x_test.py", "tests/helpers.py", "a/test/util.py", "testing/u.py",
              "conftest.py", "python/conftest.py", "python/pyproject.toml", "pytest.ini", "tox.ini", "setup.cfg",
              ".pytest.ini", "sitecustomize.py", "usercustomize.py", "lib/site.pth"]:
        assert tgate.is_protected(p), p
    for p in ["python/pkg/calc.py", "python/tests/data/x.csv", "docs/testing.md", "README.md", "latest.py"]:
        assert not tgate.is_protected(p), p


def test_strip_protected_drops_whole_file_blocks_and_names_them(repo):
    task = make_task(repo, extra={"python/pyproject.toml": "[project]\nname = 'pkg2'\n",
                                  "python/conftest.py": "import os\n"})
    stripped, removed = tgate.strip_protected(task["patch"])
    assert removed == ["python/conftest.py", "python/pyproject.toml"]
    assert "pyproject" not in stripped and "conftest" not in stripped
    assert "python/pkg/calc.py" in stripped


def test_targets_are_the_test_files_the_test_patch_touches():
    tp = textwrap.dedent("""\
        diff --git a/python/tests/test_a.py b/python/tests/test_a.py
        --- a/python/tests/test_a.py
        +++ b/python/tests/test_a.py
        @@ -1 +1 @@
        -x
        +y
        diff --git a/python/tests/conftest.py b/python/tests/conftest.py
        --- a/python/tests/conftest.py
        +++ b/python/tests/conftest.py
        @@ -1 +1 @@
        -x
        +y
        diff --git a/python/tests/test_gone.py b/python/tests/test_gone.py
        deleted file mode 100644
        --- a/python/tests/test_gone.py
        +++ /dev/null
        @@ -1 +0,0 @@
        -x
        """)
    assert tgate.target_tests(tp) == ["python/tests/test_a.py"]


def test_parse_junit_counts_passed(tmp_path):
    x = tmp_path / "r.xml"
    x.write_text('<?xml version="1.0"?><testsuites><testsuite name="pytest" tests="5" failures="1" errors="1" '
                 'skipped="1"></testsuite></testsuites>')
    assert tgate.parse_junit(x) == {"tests": 5, "passed": 2, "failures": 1, "errors": 1, "skipped": 1}
    assert tgate.parse_junit(tmp_path / "missing.xml") is None


def test_valid_task_fails_before_and_passes_after(repo):
    row = tgate.gate_task(make_task(repo), repo)
    assert row["instance_id"] == "t_1"
    assert row["fail_before"] is True and row["pass_after"] is True and row["is_valid"] is True
    assert row["reason_text"] == ""
    assert row["after_passed_count"] == 1 and row["target_count"] == 1
    assert row["before_seconds"] >= 0 and row["after_seconds"] >= 0
    assert worktrees(repo) == [f"worktree {repo}"]


def test_tests_already_passing_at_base_make_the_task_invalid(repo):
    row = tgate.gate_task(make_task(repo, test="def test_ok():\n    assert True\n"), repo)
    assert row["fail_before"] is False and row["is_valid"] is False
    assert "tests pass without the fix" in row["reason_text"]


def test_a_fix_that_does_not_fix_makes_the_task_invalid(repo):
    row = tgate.gate_task(make_task(repo, fixed="def add(a, b):\n    return a * b\n"), repo)
    assert row["fail_before"] is True and row["pass_after"] is False and row["is_valid"] is False
    assert "tests fail with the fix" in row["reason_text"]


def test_a_fix_only_in_a_protected_file_is_stripped_so_the_task_fails(repo):
    # the "fix" lives in conftest.py, which the harness strips: the tests must then fail with the patch
    base = commit_all(repo, "base")
    write(repo, "python/conftest.py", "import pkg.calc\npkg.calc.add = lambda a, b: a + b\n")
    write(repo, "python/tests/test_calc.py", TEST)
    commit_all(repo, "change")
    task = {"instance_id": "t_2", "base_commit": base, "patch": diff_of(repo, base, ["python/conftest.py"]),
            "test_patch": diff_of(repo, base, ["python/tests/"])}
    row = tgate.gate_task(task, repo)
    assert row["stripped_paths_text"] == "python/conftest.py"
    assert row["pass_after"] is False and row["is_valid"] is False


def test_no_target_tests_is_invalid_without_running(repo):
    task = make_task(repo)
    task["test_patch"] = ""
    row = tgate.gate_task(task, repo)
    assert row["is_valid"] is False and "no target tests" in row["reason_text"]


def test_a_patch_that_does_not_apply_is_named(repo):
    task = make_task(repo)
    task["patch"] = task["patch"].replace("-    return a - b", "-    return a / b")
    row = tgate.gate_task(task, repo)
    assert row["is_valid"] is False and "patch didn't apply" in row["reason_text"]


def test_no_tests_collected_after_the_fix_is_invalid(repo):
    # a target file with no tests: exit 5 before (non-zero) and after
    row = tgate.gate_task(make_task(repo, test="import pkg.calc\n"), repo)
    assert row["is_valid"] is False and "no tests collected" in row["reason_text"]


def test_timeout_is_named(repo):
    slow = "import time\nfrom pkg.calc import add\n\n\ndef test_add():\n    time.sleep(30)\n    assert add(2, 3) == 5\n"
    row = tgate.gate_task(make_task(repo, test=slow), repo, timeout=2)
    assert row["is_valid"] is False and "timeout" in row["reason_text"]
    assert worktrees(repo) == [f"worktree {repo}"]


def test_the_worktree_is_removed_even_when_a_run_raises(repo, monkeypatch, tmp_path):
    seen = []

    def boom(workdir, *a, **k):
        seen.append(Path(workdir))
        raise RuntimeError("boom")

    monkeypatch.setattr(tgate, "run_tests", boom)
    with pytest.raises(RuntimeError):
        tgate.gate_task(make_task(repo), repo)
    assert seen and not seen[0].exists()
    assert worktrees(repo) == [f"worktree {repo}"]


def test_runs_use_the_given_python(repo):
    row = tgate.gate_task(make_task(repo), repo, python=sys.executable)
    assert row["is_valid"] is True


# --- T007a (#502): gate failures stay out of the published set ---------------------------------------------

GATES = [{"instance_id": "htlnlp_1", "is_valid": True, "reason_text": ""},
         {"instance_id": "htlnlp_2", "is_valid": False, "reason_text": "fails with the fix (exit 1)"}]
TIERS = {"htlnlp_1": "A", "htlnlp_2": "B"}


def test_only_tasks_that_pass_both_gates_are_kept():
    tasks = [{"instance_id": "htlnlp_1"}, {"instance_id": "htlnlp_2"}, {"instance_id": "htlnlp_3"}]
    assert [t["instance_id"] for t in tgate.passing_tasks(tasks, GATES)] == ["htlnlp_1"]   # ungated is dropped too


def test_a_gate_failure_is_listed_with_its_tier_and_reason():
    assert tgate.gate_exclusions(GATES, TIERS) == [
        {"instance_id": "htlnlp_2", "tier_code": "B",
         "reason_text": tgate.GATE_EXCLUSION_PREFIX + "fails with the fix (exit 1)"}]


def test_merging_replaces_old_gate_rows_and_keeps_the_rest():
    existing = [{"instance_id": "htlnlp_91", "tier_code": "A", "reason_text": "patch names the organisation (#435)"},
                {"instance_id": "htlnlp_5", "tier_code": "C", "reason_text": tgate.GATE_EXCLUSION_PREFIX + "old"}]
    merged = tgate.merge_exclusions(existing, tgate.gate_exclusions(GATES, TIERS))
    assert [r["instance_id"] for r in merged] == ["htlnlp_2", "htlnlp_91"]   # sorted; htlnlp_5's old gate row gone


def test_a_gate_reason_is_never_empty():
    row = tgate.gate_exclusions([{"instance_id": "htlnlp_2", "is_valid": False, "reason_text": None}], TIERS)[0]
    assert row["reason_text"] == tgate.GATE_EXCLUSION_PREFIX + "invalid"


def test_a_stale_gate_row_for_a_task_no_longer_built_is_not_an_exclusion():   # PR #505 review
    assert tgate.gate_exclusions(GATES, TIERS, task_ids={"htlnlp_1"}) == []


def test_one_row_per_task_and_the_builders_reason_wins():   # PR #505 review
    own = [{"instance_id": "htlnlp_2", "tier_code": "B", "reason_text": "patch names the organisation (#435)"}]
    merged = tgate.merge_exclusions(own, tgate.gate_exclusions(GATES, TIERS))
    assert merged == own


def test_a_rebuild_carries_the_gate_rows_of_tasks_it_still_builds():   # PR #505 review
    existing = [{"instance_id": "htlnlp_2", "tier_code": "B", "reason_text": tgate.GATE_EXCLUSION_PREFIX + "x"},
                {"instance_id": "htlnlp_9", "tier_code": "C", "reason_text": tgate.GATE_EXCLUSION_PREFIX + "y"},
                {"instance_id": "htlnlp_91", "tier_code": "A", "reason_text": "names the organisation (#435)"}]
    assert tgate.carried_gate_rows(existing, {"htlnlp_1", "htlnlp_2"}) == existing[:1]


def test_the_task_set_folder_comes_from_paths():
    from health_transformation_lab_nlp import paths
    assert paths.TASKS_DIR == paths.REPO_ROOT / "data" / "tasks"


# --- spec 028 US6 (#641): only tasks the competition's evaluator vouches for are published ----------------------

def _v(iid, source, resolved, reason=""):
    return {"instance_id": iid, "patch_source_code": source, "is_resolved": resolved, "reason_text": reason}


VERIFICATION = [_v("htlnlp_1", "reference", True), _v("htlnlp_1", "empty", False, "tests fail"),
                _v("htlnlp_2", "reference", False, "tests read withheld files"), _v("htlnlp_2", "empty", False),
                _v("htlnlp_3", "reference", True), _v("htlnlp_3", "empty", True),       # passes with no fix
                _v("htlnlp_1", "gemma-4-e4b-it", False, "tests fail")]                  # an agent's row: ignored
FOUR = [{"instance_id": f"htlnlp_{i}"} for i in (1, 2, 3, 4)]


def test_only_tasks_the_competitions_evaluator_vouches_for_are_kept():
    assert [t["instance_id"] for t in tgate.evaluator_verified(FOUR, VERIFICATION)] == ["htlnlp_1"]


def test_each_task_the_evaluator_does_not_vouch_for_is_an_exclusion_with_its_reason():
    rows = tgate.evaluator_exclusions(FOUR, VERIFICATION, {"htlnlp_2": "B", "htlnlp_3": "A", "htlnlp_4": "C"})
    assert rows == [
        {"instance_id": "htlnlp_2", "tier_code": "B",
         "reason_text": tgate.EVALUATOR_EXCLUSION_PREFIX + "it does not resolve the reference patch: tests read withheld files"},
        {"instance_id": "htlnlp_3", "tier_code": "A",
         "reason_text": tgate.EVALUATOR_EXCLUSION_PREFIX + "it resolves an empty patch"},
        {"instance_id": "htlnlp_4", "tier_code": "C",
         "reason_text": tgate.EVALUATOR_EXCLUSION_PREFIX + "it has not been run on this task"}]


def test_the_verification_table_read_from_csv_is_understood():   # pandas gives "True"/"False" with keep_default_na
    as_text = [{**r, "is_resolved": str(r["is_resolved"])} for r in VERIFICATION]
    assert tgate.evaluator_verified(FOUR, as_text) == tgate.evaluator_verified(FOUR, VERIFICATION)


def test_merging_replaces_old_evaluator_rows_too_and_a_gate_failure_keeps_its_own_reason():
    existing = [{"instance_id": "htlnlp_7", "tier_code": "A", "reason_text": tgate.EVALUATOR_EXCLUSION_PREFIX + "old"},
                {"instance_id": "htlnlp_91", "tier_code": "A", "reason_text": "patch names the organisation (#435)"}]
    gate = tgate.gate_exclusions(GATES, TIERS)                                   # htlnlp_2 fails our gate
    unverified = tgate.evaluator_exclusions(FOUR, VERIFICATION, TIERS)          # htlnlp_2, 3 and 4
    merged = tgate.merge_exclusions(existing, gate + unverified)
    assert [r["instance_id"] for r in merged] == ["htlnlp_2", "htlnlp_3", "htlnlp_4", "htlnlp_91"]
    assert merged[0]["reason_text"].startswith(tgate.GATE_EXCLUSION_PREFIX)


def test_a_rebuild_carries_the_evaluator_rows_of_tasks_it_still_builds():
    existing = [{"instance_id": "htlnlp_2", "tier_code": "B", "reason_text": tgate.EVALUATOR_EXCLUSION_PREFIX + "x"},
                {"instance_id": "htlnlp_8", "tier_code": "B", "reason_text": tgate.EVALUATOR_EXCLUSION_PREFIX + "y"}]
    assert [r["instance_id"] for r in tgate.carried_gate_rows(existing, {"htlnlp_2"})] == ["htlnlp_2"]

