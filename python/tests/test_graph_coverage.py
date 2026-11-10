"""Spec 028 (#659): how much of a task's fix its code graph reaches. The graph has the package's functions, classes
and methods; a data repository's changes are often elsewhere (scripts, notebooks, pipeline configuration)."""
import importlib.util

import pytest

from health_transformation_lab_nlp.paths import REPO_ROOT


@pytest.fixture(scope="module")
def cov():
    spec = importlib.util.spec_from_file_location("graph_coverage", REPO_ROOT / "python" / "scripts" / "63_graph_coverage.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GRAPH = {"nodes": [{"id": "pkg.calc.add", "name": "pkg.calc.add", "text": "def add(a, b): ..."},
                   {"id": "pkg.io.Reader", "name": "pkg.io.Reader", "text": "class Reader: ..."},
                   {"id": "pkg.io.Reader.read", "name": "pkg.io.Reader.read", "text": "def read(self): ..."}],
         "edges": [{"source": "pkg.io.Reader.read", "target": "pkg.calc.add", "type": "calls", "key": 0}]}


def _patch(*paths):
    return "".join(f"diff --git a/{p} b/{p}\n--- a/{p}\n+++ b/{p}\n@@ -1 +1 @@\n-x\n+y\n" for p in paths)


def test_the_files_a_patch_changes_are_read_from_its_headers(cov):
    assert cov.changed_files(_patch("python/pkg/calc.py", "docs/a.md")) == ["python/pkg/calc.py", "docs/a.md"]


def test_a_graphs_modules_are_every_module_that_holds_a_node(cov):
    assert cov.graph_modules(GRAPH) == {"pkg.calc", "pkg.io"}   # a method's parent is a class, not a module


def test_a_fix_in_a_graphed_module_is_in_the_graph(cov):
    row = cov.coverage({"instance_id": "t_1", "patch": _patch("python/pkg/calc.py", "docs/a.md")}, GRAPH)
    assert row == {"instance_id": "t_1", "changed_file_count": 2, "graphed_file_count": 1, "is_fix_in_graph": True}


def test_a_fix_in_scripts_notebooks_or_a_new_module_is_outside_it(cov):
    row = cov.coverage({"instance_id": "t_2", "patch": _patch("python/scripts/10_build.py", "databricks/notebooks/01_run.py",
                                                              "python/pkg/new_module.py", "databricks/resources/jobs.yml")}, GRAPH)
    assert row["graphed_file_count"] == 0 and row["is_fix_in_graph"] is False and row["changed_file_count"] == 4


def test_a_class_or_function_name_is_not_taken_for_a_module(cov):
    # "pkg.io.Reader" is a class in pkg/io.py, not the module pkg/io/Reader.py
    row = cov.coverage({"instance_id": "t_3", "patch": _patch("python/pkg/io/Reader.py")}, GRAPH)
    assert row["is_fix_in_graph"] is False


# --- does the graph lead from what a statement names to what the fix edits? (#659) ---

SOURCE = (
    "import os\n"                      # 1
    "\n"                               # 2
    "LIMIT = 3\n"                      # 3
    "\n"                               # 4
    "def add(a, b):\n"                 # 5
    "    total = a + b\n"              # 6
    "    return total\n"               # 7
    "\n"                               # 8
    "class Reader:\n"                  # 9
    "    def read(self):\n"            # 10
    "        return add(1, 2)\n"       # 11
    "\n"                               # 12
    "    def close(self):\n"           # 13
    "        return None\n"            # 14
)


def _hunks(path, *hunks):
    return f"diff --git a/{path} b/{path}\n--- a/{path}\n+++ b/{path}\n" + "".join(hunks)


def test_a_patchs_runs_are_the_lines_it_removes_and_where_it_only_inserts(cov):
    patch = _hunks("python/pkg/calc.py",
                   "@@ -5,3 +5,3 @@\n def add(a, b):\n-    total = a + b\n+    total = b + a\n     return total\n",
                   "@@ -10,2 +10,3 @@\n     def read(self):\n+        pass\n         return add(1, 2)\n")
    assert cov.changed_runs(patch) == {"python/pkg/calc.py": [(5, [6]), (10, [])]}


def test_a_file_the_patch_adds_or_deletes_has_no_runs(cov):
    added = "diff --git a/python/pkg/new.py b/python/pkg/new.py\nnew file mode 100644\n--- /dev/null\n" \
            "+++ b/python/pkg/new.py\n@@ -0,0 +1,2 @@\n+def f():\n+    return 1\n"
    deleted = "diff --git a/python/pkg/old.py b/python/pkg/old.py\ndeleted file mode 100644\n--- a/python/pkg/old.py\n" \
              "+++ /dev/null\n@@ -1 +0,0 @@\n-x = 1\n"
    assert cov.changed_runs(added + deleted) == {}


def test_a_hunk_that_only_inserts_after_a_line_starts_below_it(cov):
    # "-7,0" means the new lines go in after old line 7
    patch = _hunks("python/pkg/calc.py", "@@ -7,0 +8,2 @@\n+\n+def sub(a, b): return a - b\n")
    assert cov.changed_runs(patch) == {"python/pkg/calc.py": [(7, [])]}


def test_a_changed_line_belongs_to_the_innermost_def_that_holds_it(cov):
    assert cov.edited_nodes([(5, [6])], SOURCE, "pkg.calc") == {"pkg.calc.add"}
    assert cov.edited_nodes([(10, [11])], SOURCE, "pkg.calc") == {"pkg.calc.Reader.read"}   # the method, not the class
    assert cov.edited_nodes([(8, [9])], SOURCE, "pkg.calc") == {"pkg.calc.Reader"}          # the class line itself


def test_a_module_level_change_edits_no_node(cov):
    assert cov.edited_nodes([(2, [3])], SOURCE, "pkg.calc") == set()


def test_lines_inserted_inside_a_def_edit_it_and_new_code_after_it_does_not(cov):
    assert cov.edited_nodes([(6, [])], SOURCE, "pkg.calc") == {"pkg.calc.add"}       # between two lines of add
    assert cov.edited_nodes([(7, [])], SOURCE, "pkg.calc") == set()                  # after add's last line
    assert cov.edited_nodes([(12, [])], SOURCE, "pkg.calc") == {"pkg.calc.Reader"}   # a new method between two


IDS = {"pkg.calc.add", "pkg.calc.score_records", "pkg.io.Reader", "pkg.io.Reader.read", "pkg.labels.Status"}


def test_a_statement_names_a_node_by_a_distinctive_identifier(cov):
    assert cov.named_nodes("score_records returns the wrong total", IDS) == {"pkg.calc.score_records"}
    assert cov.named_nodes("The Reader should add and read each row", IDS) == {"pkg.io.Reader"}   # add, read: words


def test_a_statement_names_a_node_by_an_inline_code_span_that_is_its_name(cov):
    assert cov.named_nodes("`add` drops a row", IDS) == {"pkg.calc.add"}
    # `Reader.read(path)` names the method by the span, and the class too: Reader is a distinctive identifier
    assert cov.named_nodes("`calc.add()` drops a row; `Reader.read(path)` too", IDS) == {
        "pkg.calc.add", "pkg.io.Reader.read", "pkg.io.Reader"}
    assert cov.named_nodes("`other.add` drops a row", IDS) == set()                    # another module's add
    assert cov.named_nodes("run `pytest -k add` to see it", IDS) == set()              # the span is not the name
    assert cov.named_nodes("```\nadd(1, 2)\n```", IDS) == set()                        # a code block is not a span


def test_the_distance_is_the_fewest_call_edges_in_either_direction(cov):
    graph = {"nodes": [{"id": i} for i in ("a", "b", "c", "d", "e")],
             "edges": [{"source": "a", "target": "b", "type": "calls"}, {"source": "c", "target": "b", "type": "calls"},
                       {"source": "d", "target": "e", "type": "imports"}]}
    assert cov.call_distance({"a"}, {"a", "c"}, graph) == 0
    assert cov.call_distance({"b"}, {"a"}, graph) == 1      # b is called by a
    assert cov.call_distance({"a"}, {"c"}, graph) == 2
    assert cov.call_distance({"d"}, {"e"}, graph) is None   # only `calls` edges count
    assert cov.call_distance(set(), {"a"}, graph) is None and cov.call_distance({"a"}, set(), graph) is None


def test_a_tasks_row_says_whether_the_graph_leads_from_statement_to_fix(cov):
    graph = {"nodes": [{"id": "pkg.calc.add"}, {"id": "pkg.calc.Reader"}, {"id": "pkg.calc.Reader.read"},
                       {"id": "pkg.calc.Reader.close"}],
             "edges": [{"source": "pkg.calc.Reader.read", "target": "pkg.calc.add", "type": "calls", "key": 0}]}
    patch = _hunks("python/pkg/calc.py", "@@ -5,3 +5,3 @@\n def add(a, b):\n-    total = a + b\n+    total = b + a\n     return total\n") \
        + _patch("python/scripts/10_build.py")
    task = {"instance_id": "t_9", "patch": patch, "problem_statement": "`read` returns 4", "hints_text": None}
    row = cov.localization(task, graph, {"python/pkg/calc.py": SOURCE})
    assert row == {"edited_node_count": 1, "statement_node_count": 1, "statement_to_fix_edge_count": 1,
                   "edited_node_text": "pkg.calc.add", "statement_node_text": "pkg.calc.Reader.read"}
    # the script it also changes is no module of the graph, so nothing there is read or counted
    assert cov.localization(task | {"problem_statement": "it is wrong"}, graph, {"python/pkg/calc.py": SOURCE})[
        "statement_to_fix_edge_count"] is None


def test_a_snapshot_gives_the_files_as_the_base_commit_had_them(cov, tmp_path):
    import io
    import tarfile
    with tarfile.open(tmp_path / "t_9.tgz", "w:gz") as tf:
        for name, body in (("./python/pkg/calc.py", SOURCE), ("./README.md", "x")):
            info = tarfile.TarInfo(name)
            info.size = len(body.encode())
            tf.addfile(info, io.BytesIO(body.encode()))
    assert cov.base_sources(tmp_path / "t_9.tgz", {"python/pkg/calc.py"}) == {"python/pkg/calc.py": SOURCE}
    with pytest.raises(SystemExit, match="python/pkg/gone.py"):
        cov.base_sources(tmp_path / "t_9.tgz", {"python/pkg/gone.py"})
