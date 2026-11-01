"""Our own fail-to-pass gate for the task set (spec 028, US3, #453).

The competition's evaluator (`swegemma eval --skip-agent-patch`) isn't distributed: no wheel among the
competition's files, and its docker/ and sandbox/ don't install it (#449). This follows the harness's documented
verification instead (HARNESS_README, as the competition's data page describes it):

    fail-to-pass  `test_patch` on `base_commit`, without the fix: the target tests must fail (non-zero exit)
    pass          `patch`, with protected files stripped, plus `test_patch`: the target tests exit 0 and the JUnit
                  XML shows passed > 0, failures == 0, errors == 0

Target tests are the test files `test_patch` touches, run as
`python -m pytest <targets> --junitxml=<tmp>.xml -q -p no:cacheprovider` with a timeout per run (300 s default).

Each task runs in a temporary `git worktree` at `base_commit`, with PYTHONPATH=<worktree>/python (the package was
renamed during the history, so the folder is added, not a package name), and the worktree is always removed.
It runs with the calling environment's Python and packages, not the competition's sandbox image, so a task that
passes here can still fail there (or the reverse) when a dependency differs.
"""

from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from pathlib import Path

from .telemetry import traced

RUNNER_CONFIGS = ("conftest.py", "pytest.ini", "pyproject.toml", "tox.ini", "setup.cfg", ".pytest.ini",
                  "sitecustomize.py", "usercustomize.py")
TEST_DIRS = ("tests", "test", "testing")
SOURCE_DIR = "python"           # added to PYTHONPATH in the worktree
DEFAULT_TIMEOUT = 300
GATE_COLUMNS = ["instance_id", "base_commit", "target_count", "fail_before", "pass_after", "is_valid", "reason_text",
                "before_exit_code", "after_exit_code", "after_passed_count", "after_failed_count",
                "after_error_count", "stripped_paths_text", "before_seconds", "after_seconds"]
_NO_TESTS = 5                   # pytest's exit code when nothing was collected


@traced
def is_protected(path: str) -> bool:
    """A file the harness strips from a submitted patch: test files and the runner's configuration."""
    parts = path.split("/")
    name = parts[-1]
    if name in RUNNER_CONFIGS or name.endswith(".pth"):
        return True
    if not name.endswith(".py"):
        return False
    return name.startswith("test_") or name.endswith("_test.py") or any(d in TEST_DIRS for d in parts[:-1])


def _blocks(diff: str) -> list[str]:
    out: list[str] = []
    cur: list[str] = []
    for line in diff.splitlines(keepends=True):
        if line.startswith("diff --git ") and cur:
            out.append("".join(cur))
            cur = []
        cur.append(line)
    if cur:
        out.append("".join(cur))
    return out


def _block_path(block: str) -> str:
    return block.split("\n", 1)[0].rstrip().rsplit(" b/", 1)[-1]


@traced
def strip_protected(patch: str) -> tuple[str, list[str]]:
    """The patch without the file blocks the harness strips, and the stripped paths (sorted)."""
    kept, removed = [], []
    for b in _blocks(patch):
        (removed if is_protected(_block_path(b)) else kept).append(b)
    return "".join(kept), sorted(_block_path(b) for b in removed)


@traced
def target_tests(test_patch: str) -> list[str]:
    """The test files (`test_*.py`, `*_test.py`) the test patch touches and leaves in place, in diff order."""
    out = []
    for b in _blocks(test_patch):
        path = _block_path(b)
        name = path.rsplit("/", 1)[-1]
        deleted = "\n+++ /dev/null" in b or "\ndeleted file mode" in b
        if name.endswith(".py") and (name.startswith("test_") or name.endswith("_test.py")) and not deleted:
            out.append(path)
    return out


@traced
def parse_junit(path: Path) -> dict | None:
    """Totals over every <testsuite> in a JUnit XML file; None when the file is missing or unreadable."""
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return None
    suites = [root] if root.tag == "testsuite" else root.iter("testsuite")
    t = {"tests": 0, "failures": 0, "errors": 0, "skipped": 0}
    for s in suites:
        for k in t:
            t[k] += int(s.get(k, 0) or 0)
    return {"tests": t["tests"], "passed": t["tests"] - t["failures"] - t["errors"] - t["skipped"],
            "failures": t["failures"], "errors": t["errors"], "skipped": t["skipped"]}


def _env(workdir: Path) -> dict:
    env = {k: v for k, v in os.environ.items() if not k.startswith("DENTAL_")}   # no data root from outside
    env["PYTHONPATH"] = str(workdir / SOURCE_DIR)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


@traced
def run_tests(workdir: Path, targets: list[str], timeout: int = DEFAULT_TIMEOUT, python: str = sys.executable) -> dict:
    """One pytest run of the targets at the worktree root: exit code (None on timeout), JUnit totals, seconds."""
    xml = Path(tempfile.mkstemp(suffix=".xml", prefix="gate_")[1])
    cmd = [python, "-m", "pytest", *targets, f"--junitxml={xml}", "-q", "-p", "no:cacheprovider"]
    start = time.monotonic()
    proc = subprocess.Popen(cmd, cwd=workdir, env=_env(workdir), stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL, start_new_session=True)
    try:
        code: int | None = proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)   # the whole group: pytest may have started children
        proc.wait()
        code = None
    seconds = round(time.monotonic() - start, 2)
    junit = parse_junit(xml) if code is not None else None
    xml.unlink(missing_ok=True)
    return {"exit_code": code, "junit": junit, "seconds": seconds}


def _git(repo: Path, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", *args], cwd=repo, input=stdin, capture_output=True, text=True,
                          check=False)


def _apply(workdir: Path, patch: str) -> bool:
    if not patch.strip():
        return True
    return _git(workdir, "apply", "--whitespace=nowarn", "-", stdin=patch).returncode == 0


def _reset(workdir: Path) -> None:
    _git(workdir, "reset", "-q", "--hard")
    _git(workdir, "clean", "-q", "-fdx")


@traced
def gate_task(task: dict, repo: Path, timeout: int = DEFAULT_TIMEOUT, python: str = sys.executable) -> dict:
    """Both phases for one task row (instance_id, base_commit, patch, test_patch); one gate row back."""
    repo = Path(repo)
    patch, stripped = strip_protected(task.get("patch") or "")
    targets = target_tests(task.get("test_patch") or "")
    row = {"instance_id": task["instance_id"], "base_commit": task["base_commit"], "target_count": len(targets),
           "fail_before": False, "pass_after": False, "is_valid": False, "reason_text": "",
           "before_exit_code": None, "after_exit_code": None, "after_passed_count": None,
           "after_failed_count": None, "after_error_count": None, "stripped_paths_text": ";".join(stripped),
           "before_seconds": None, "after_seconds": None}
    reasons: list[str] = []
    if not targets:
        row["reason_text"] = "no target tests in test_patch"
        return row
    parent = Path(tempfile.mkdtemp(prefix="gate_wt_"))
    workdir = parent / "wt"
    try:
        made = _git(repo, "worktree", "add", "-q", "--detach", str(workdir), task["base_commit"])
        if made.returncode != 0:
            row["reason_text"] = "base commit not found"
            return row
        # phase 1: test_patch only, the tests must fail
        if not _apply(workdir, task["test_patch"]):
            row["reason_text"] = "test_patch didn't apply"
            return row
        before = run_tests(workdir, targets, timeout, python)
        row["before_exit_code"], row["before_seconds"] = before["exit_code"], before["seconds"]
        if before["exit_code"] is None:
            reasons.append("timeout without the fix")
        elif before["exit_code"] == 0:
            reasons.append("tests pass without the fix")
        else:
            row["fail_before"] = True
        # phase 2: stripped patch then test_patch, the tests must pass
        _reset(workdir)
        if not _apply(workdir, patch):
            reasons.append("patch didn't apply")
        elif not _apply(workdir, task["test_patch"]):
            reasons.append("test_patch didn't apply over the patch")
        else:
            after = run_tests(workdir, targets, timeout, python)
            j = after["junit"] or {}
            row.update(after_exit_code=after["exit_code"], after_seconds=after["seconds"],
                       after_passed_count=j.get("passed"), after_failed_count=j.get("failures"),
                       after_error_count=j.get("errors"))
            if after["exit_code"] is None:
                reasons.append("timeout with the fix")
            elif after["exit_code"] == _NO_TESTS or (after["exit_code"] == 0 and not j.get("passed")):
                reasons.append("no tests collected")
            elif after["exit_code"] != 0 or j.get("failures") or j.get("errors"):
                reasons.append("tests fail with the fix")
            else:
                row["pass_after"] = True
        row["is_valid"] = row["fail_before"] and row["pass_after"]
        row["reason_text"] = "; ".join(reasons)
        return row
    finally:
        _git(repo, "worktree", "remove", "--force", str(workdir))
        shutil.rmtree(parent, ignore_errors=True)
        _git(repo, "worktree", "prune")
