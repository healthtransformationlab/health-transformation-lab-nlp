"""028 AI6 (#670): does the failing test's trace lead to the fix? The plugin records, while a task's failing tests
run, the package's functions that are called and the package's frames on each failure's traceback, by the graph's
names; the script counts how often an edited node is among them. A row holds ids, counts and booleans, no text."""
import importlib.util
import json
import site
import subprocess
import sys

import pytest

from health_transformation_lab_nlp.paths import REPO_ROOT

SCRIPTS = REPO_ROOT / "python" / "scripts"


def plugin_env(home, out, *roots, **more) -> dict:
    """The small environment a plugin subprocess runs in: nothing of the caller's but the import path it names, with
    HOME in a temp folder. PYTHONUSERBASE keeps this interpreter's own user site in reach: where packages were
    installed with pip's user scheme (the deploy job), pytest itself is there (028 BUG6, #679)."""
    return {"PATH": "/usr/bin:/bin", "PYTHONPATH": ":".join([*map(str, roots), str(SCRIPTS)]), "TRACE_PACKAGE": "pkg",
            "TRACE_OUT": str(out), "HOME": str(home), "PYTHONUSERBASE": site.getuserbase(), **more}


@pytest.fixture(scope="module")
def tr():
    spec = importlib.util.spec_from_file_location("trace_reach", SCRIPTS / "68_trace_reach.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_the_plugin_records_called_functions_and_the_failures_frames_by_graph_names(tmp_path):
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text(
        "def helper(x):\n    return x + 1\n\n"
        "def total(xs):\n    def inner(v):\n        return helper(v)\n    return sum(inner(v) for v in xs)\n\n"
        "class Box:\n    def check(self, n):\n        assert n > 0, 'n must be positive'\n        return n\n\n"
        "def _private():\n    return 0\n")
    (tmp_path / "test_mod.py").write_text(
        "from pkg.mod import Box, total, _private\n\n"
        "def test_total():\n    assert total([1, 2]) == 5\n\n"
        "def test_box():\n    _private()\n    Box().check(-1)\n")
    out = tmp_path / "trace.json"
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "_trace_plugin",
                        "test_mod.py"], cwd=tmp_path, capture_output=True, text=True,
                       env=plugin_env(tmp_path, out, tmp_path))
    assert r.returncode == 1, r.stdout + r.stderr                 # test_box fails, test_total passes
    trace = json.loads(out.read_text())
    assert set(trace["called"]) == {"pkg.mod.helper", "pkg.mod.total", "pkg.mod.total.inner", "pkg.mod.Box.check",
                                    "pkg.mod._private"}
    assert trace["failure_frames"] == [["pkg.mod.Box.check"]]     # the package's frames only, innermost last
    assert trace["exit_status"] == 1


def test_only_public_functions_count_as_what_the_spans_record(tr):
    assert tr.public({"pkg.mod.helper", "pkg.mod._private", "pkg.mod.Box.check", "pkg.mod._Box.check",
                      "pkg.mod.total.inner"}) == {"pkg.mod.helper", "pkg.mod.Box.check", "pkg.mod.total.inner"}


GRAPH = {"directed": True, "multigraph": True, "graph": {},
         "nodes": [{"id": i, "name": i, "text": ""} for i in ("pkg.mod.helper", "pkg.mod.total", "pkg.mod.Box.check",
                                                               "pkg.api.get")],
         "edges": [{"source": "pkg.api.get", "target": "pkg.mod.helper", "type": "calls", "key": 0}]}


def test_a_row_says_whether_the_trace_or_the_traceback_reaches_an_edited_node(tr):
    trace = {"called": ["pkg.mod.total", "pkg.mod.helper", "pkg.mod._private", "pkg.mod.total.inner"],
             "failure_frames": [["pkg.mod.Box.check"]], "exit_status": 1}
    row = tr.trace_row("t1", trace, GRAPH, {"pkg.mod.helper"})
    assert row == {"instance_id": "t1", "test_exit_code": 1, "traced_node_count": 2, "failure_frame_count": 1,
                   "is_edited_in_trace": True, "is_edited_on_traceback": False, "traceback_to_fix_edge_count": None}
    row = tr.trace_row("t2", trace, GRAPH, {"pkg.mod.Box.check"})
    assert row["is_edited_on_traceback"] is True and row["traceback_to_fix_edge_count"] == 0
    assert row["is_edited_in_trace"] is False                      # Box.check raised before it returned: on the traceback
    assert all(not isinstance(v, str) or v in ("t1", "t2") for v in row.values())


def test_the_summary_counts_tasks_the_trace_reaches_and_what_the_statement_reached(tr):
    rows = [dict(instance_id="a", is_edited_in_trace=True, is_edited_on_traceback=True, traced_node_count=4,
                 traceback_to_fix_edge_count=0, test_exit_code=1),
            dict(instance_id="b", is_edited_in_trace=True, is_edited_on_traceback=False, traced_node_count=40,
                 traceback_to_fix_edge_count=None, test_exit_code=1),
            dict(instance_id="c", is_edited_in_trace=False, is_edited_on_traceback=False, traced_node_count=0,
                 traceback_to_fix_edge_count=None, test_exit_code=2)]
    s = tr.summary(rows, reached_by_statement={"a", "c"})
    assert (s["task_count"], s["trace_count"], s["traceback_count"]) == (3, 2, 1)
    assert s["trace_not_statement_count"] == 1                     # b: the trace reaches it, the statement does not
    assert s["median_traced_node_count"] == 4
    assert s["collection_error_count"] == 1                        # c never ran a test (exit code 2)


def test_the_plugin_records_a_test_that_cannot_import_the_name_it_needs(tmp_path):
    """A failing test that imports a name the fix adds never runs (exit code 2): the failure report then names the
    missing name and its module, which the plugin keeps (names only)."""
    pkg = tmp_path / "pkg"
    pkg.mkdir()
    (pkg / "__init__.py").write_text("")
    (pkg / "mod.py").write_text("def old():\n    return 1\n")
    (tmp_path / "test_new.py").write_text("from pkg.mod import new_thing\n\ndef test_it():\n    assert new_thing()\n")
    out = tmp_path / "trace.json"
    r = subprocess.run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-p", "_trace_plugin",
                        "test_new.py"], cwd=tmp_path, capture_output=True, text=True,
                       env=plugin_env(tmp_path, out, tmp_path))
    assert r.returncode == 2, r.stdout + r.stderr
    trace = json.loads(out.read_text())
    assert trace["collection_errors"] == [{"error_type": "ImportError", "missing_name": "new_thing", "module": "pkg.mod"}]


def test_an_import_error_is_read_against_the_fix(tr):
    patch = ("diff --git a/python/pkg/mod.py b/python/pkg/mod.py\n--- a/python/pkg/mod.py\n+++ b/python/pkg/mod.py\n"
             "@@ -1,2 +1,5 @@\n def old():\n     return 1\n+\n+def new_thing():\n+    return 2\n")
    trace = {"called": [], "failure_frames": [], "exit_status": 2,
             "collection_errors": [{"error_type": "ImportError", "missing_name": "new_thing", "module": "pkg.mod"}]}
    row = tr.import_columns(trace, patch)
    assert row == {"is_import_error": True, "is_missing_name_added_by_fix": True, "is_error_module_changed_by_fix": True}
    assert tr.import_columns({"exit_status": 1}, patch) == {"is_import_error": False, "is_missing_name_added_by_fix":
                                                            False, "is_error_module_changed_by_fix": False}


def test_the_summary_says_what_the_trace_and_the_import_errors_each_add_to_the_statement(tr):
    """028 BUG4 (#672): the report's gain over the statement was once credited to the trace alone. The summary now
    splits it: tasks only the trace reaches, tasks only an import error reaches, and the two together."""
    def row(i, trace=False, traceback=False, name=False, module=False):
        return dict(instance_id=i, is_edited_in_trace=trace, is_edited_on_traceback=traceback, traced_node_count=1,
                    traceback_to_fix_edge_count=None, test_exit_code=2 if (name or module) else 1,
                    is_import_error=name or module, is_missing_name_added_by_fix=name,
                    is_error_module_changed_by_fix=module)
    rows = [row("a", trace=True),                 # the statement reaches it too
            row("b", trace=True),                 # only the trace
            row("c", module=True),                # only an import error naming a module the fix changes
            row("d", name=True, module=True),     # an import error, and the statement reaches it too
            row("e")]                             # neither
    s = tr.summary(rows, reached_by_statement={"a", "d", "not_in_rows"})
    assert s["trace_not_statement_count"] == 1                 # b
    assert s["import_error_not_statement_count"] == 1          # c
    assert s["report_count"] == 4                              # a, b, c, d
    assert s["report_not_statement_count"] == 2                # b, c
    assert s["statement_count"] == 2                           # a, d: only tasks among the rows count
    assert s["statement_or_report_count"] == 4                 # a, b, c, d


def test_a_plugin_subprocess_keeps_this_interpreters_own_packages(tmp_path):
    """028 BUG6 (#679): the deploy job installs with pip's user scheme, so pytest is in the user site under HOME. The
    plugin's tests move HOME to a temp folder; their subprocess must still be told where the user base is."""
    env = plugin_env(tmp_path, tmp_path / "trace.json", tmp_path)
    assert env["HOME"] == str(tmp_path) and env["TRACE_OUT"] == str(tmp_path / "trace.json")
    seen = subprocess.run([sys.executable, "-c", "import site; print(site.getuserbase())"], env=env,
                          capture_output=True, text=True, check=True).stdout.strip()
    assert seen == site.getuserbase()
