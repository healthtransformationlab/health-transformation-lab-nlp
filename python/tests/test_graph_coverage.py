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
