"""028 AI7 (#674): the failing test's report an agent can be given. A test-first repository has its failing test
before the fix; its report is the failing tests' ids with the first line of each error, and the public functions
those tests called (what the repository's OpenTelemetry spans record). The plugin keeps messages only when asked,
the report is short, and the committed table holds counts, never the text."""
import importlib.util
import json
import subprocess
import sys

import pytest

from health_transformation_lab_nlp.paths import REPO_ROOT

SCRIPTS = REPO_ROOT / "python" / "scripts"


@pytest.fixture(scope="module")
def fr():
    spec = importlib.util.spec_from_file_location("failure_report", SCRIPTS / "69_failure_report.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _run(tmp_path, messages):
    pkg = tmp_path / "python" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("def old(n):\n    return n + 1\n")
    tests = tmp_path / "python" / "tests"
    tests.mkdir()
    (tests / "test_new.py").write_text("from pkg.mod import new_thing\n\ndef test_it():\n    assert new_thing()\n")
    (tests / "test_old.py").write_text("from pkg.mod import old\n\ndef test_old():\n    assert old(1) == 3, 'old(1) must be 3'\n")
    out = tmp_path / "trace.json"
    env = {"PATH": "/usr/bin:/bin", "PYTHONPATH": f"{tmp_path / 'python'}:{SCRIPTS}", "TRACE_PACKAGE": "pkg",
           "TRACE_OUT": str(out), "HOME": str(tmp_path)}
    if messages:
        env["TRACE_MESSAGES"] = "1"
    subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "_trace_plugin",
                    "--continue-on-collection-errors", "tests/test_new.py", "tests/test_old.py"],
                   cwd=tmp_path / "python", capture_output=True, text=True, env=env, check=False)
    return json.loads(out.read_text())


def test_the_plugin_keeps_each_failures_first_line_only_when_asked(tmp_path):
    assert "failure_messages" not in _run(tmp_path / "off", messages=False)        # names only, as before
    trace = _run(tmp_path / "on", messages=True)
    assert trace["failure_messages"] == [
        {"kind_code": "ERROR", "test_id": "tests/test_new.py",
         "message_text": "ImportError: cannot import name 'new_thing' from 'pkg.mod'"},
        {"kind_code": "FAILED", "test_id": "tests/test_old.py::test_old",
         "message_text": "AssertionError: old(1) must be 3"}]
    assert str(tmp_path) not in json.dumps(trace["failure_messages"])              # no path of this machine


TRACE = {"called": ["pkg.mod.total", "pkg.mod.helper", "pkg.mod._private"], "exit_status": 1,
         "failure_messages": [{"kind_code": "ERROR", "test_id": "tests/test_new.py",
                               "message_text": "ImportError: cannot import name 'new_thing' from 'pkg.mod'"},
                              {"kind_code": "FAILED", "test_id": "tests/test_old.py::test_old",
                               "message_text": "AssertionError: old(1) must be 3"}]}


def test_the_report_lists_the_failures_and_the_public_functions_called(fr):
    text = fr.failure_context(TRACE)
    assert text.splitlines() == [
        "Failing test report (this repository's tests for the change, run on this commit before any fix):",
        "- ERROR python/tests/test_new.py - ImportError: cannot import name 'new_thing' from 'pkg.mod'",
        "- FAILED python/tests/test_old.py::test_old - AssertionError: old(1) must be 3",
        "Public functions these tests called before failing (what the repository's OpenTelemetry spans record): "
        "pkg.mod.helper, pkg.mod.total"]
    assert "_private" not in text


def test_a_long_report_is_cut_to_a_few_failures_and_functions_and_says_how_many_it_left_out(fr):
    many = {"called": [f"pkg.mod.f{n:02d}" for n in range(30)],
            "failure_messages": [{"kind_code": "FAILED", "test_id": f"tests/test_x.py::test_{n}",
                                  "message_text": f"AssertionError: {n:02d} " + "x" * 400} for n in range(20)]}
    text = fr.failure_context(many, max_failures=3, max_functions=4, max_message_chars=60)
    lines = text.splitlines()
    assert len([line for line in lines if line.startswith("- FAILED")]) == 3
    assert "(and 17 more distinct errors)" in lines
    assert all(len(line) <= 60 + len("- FAILED python/tests/test_x.py::test_19 - ") for line in lines[1:4])
    assert lines[-1].endswith("pkg.mod.f00, pkg.mod.f01, pkg.mod.f02, pkg.mod.f03 (and 26 more)")


def test_tests_that_fail_before_calling_anything_get_no_functions_line_and_no_failure_is_no_report(fr):
    only_import = {"called": [], "failure_messages": TRACE["failure_messages"][:1]}
    assert len(fr.failure_context(only_import).splitlines()) == 2
    assert fr.failure_context({"called": ["pkg.mod.total"], "failure_messages": []}) == ""


def test_the_committed_row_holds_counts_and_never_the_report(fr):
    row = fr.shape_row("t1", TRACE, fr.failure_context(TRACE))
    assert row == {"instance_id": "t1", "test_exit_code": 1, "failing_test_count": 1, "errored_test_count": 1,
                   "traced_function_count": 2, "context_chars": len(fr.failure_context(TRACE)), "is_import_error": True}
    assert all(not isinstance(v, str) or v == "t1" for v in row.values())


def test_the_report_text_is_never_written_inside_the_repository(fr, tmp_path):
    with pytest.raises(SystemExit, match="outside the repository"):
        fr.check_out_path(REPO_ROOT / "data" / "tasks" / "contexts.jsonl")
    fr.check_out_path(tmp_path / "contexts.jsonl")


def test_the_package_is_found_in_a_snapshot_whatever_it_was_called_then(fr, tmp_path):
    for name in ("dental_omop_nlp", "health_transformation_lab_nlp"):
        root = tmp_path / name
        (root / "python" / name).mkdir(parents=True)
        (root / "python" / name / "__init__.py").write_text("")
        (root / "python" / "tests").mkdir()
        (root / "python" / "tests" / "__init__.py").write_text("")
        assert fr.tr.package_of(root) == name


def test_tests_that_fail_the_same_way_share_one_line(fr):
    """A parametrized test that fails eight times with one error is one line, so ten lines hold ten different errors."""
    same = {"called": [], "failure_messages": [
        {"kind_code": "FAILED", "test_id": f"tests/test_p.py::test_skip[changed{n}]",
         "message_text": "AttributeError: module 'parity_needed' has no attribute 'code_changed'"} for n in range(8)]
        + [{"kind_code": "FAILED", "test_id": "tests/test_p.py::test_other", "message_text": "AssertionError: bundle"}]}
    assert fr.failure_context(same).splitlines()[1:] == [
        "- FAILED python/tests/test_p.py::test_skip[changed0] (and 7 more tests with this error) - AttributeError: "
        "module 'parity_needed' has no attribute 'code_changed'",
        "- FAILED python/tests/test_p.py::test_other - AssertionError: bundle"]
    row = fr.shape_row("t", same, fr.failure_context(same))
    assert row["failing_test_count"] == 9                      # the count is of tests, not of lines


def test_a_path_under_the_snapshot_is_given_from_its_root(tmp_path):
    """An error that names a missing file shows it from the repository's root, not from this machine's temp folder."""
    root = tmp_path / "repo"
    (root / "python" / "tests").mkdir(parents=True)
    (root / "python" / "tests" / "test_file.py").write_text(
        "from pathlib import Path\n\ndef test_reads():\n"
        "    (Path(__file__).resolve().parents[2] / 'ops' / 'register.yaml').read_text()\n")
    out = tmp_path / "trace.json"
    subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "_trace_plugin",
                    "tests/test_file.py"], cwd=root / "python", capture_output=True, text=True, check=False,
                   env={"PATH": "/usr/bin:/bin", "PYTHONPATH": f"{root / 'python'}:{SCRIPTS}", "TRACE_PACKAGE": "pkg",
                        "TRACE_OUT": str(out), "HOME": str(tmp_path), "TRACE_MESSAGES": "1", "TRACE_ROOT": str(root)})
    message = json.loads(out.read_text())["failure_messages"][0]["message_text"]
    assert message == "FileNotFoundError: [Errno 2] No such file or directory: 'ops/register.yaml'"
