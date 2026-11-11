"""028 AI5 (#669): the paper's graph-reach counts (scripts 63 and 64) on the competition's own development set. Only
the parts that differ from our own tasks are new here: a module under `src/`, a changed file read from GitHub at its
base commit, and the competition's own search tool, which goes from a symbol to its nearest nodes under the provided
embeddings. A row holds ids, counts and ranks, never the competition's text."""
import importlib.util

import numpy as np
import pytest

from health_transformation_lab_nlp.paths import REPO_ROOT

SOURCE = '''class Response:
    def json(self):
        return 1


def helper():
    return 2
'''
PATCH = '''diff --git a/src/pkg/models.py b/src/pkg/models.py
index 1111111..2222222 100644
--- a/src/pkg/models.py
+++ b/src/pkg/models.py
@@ -1,6 +1,6 @@
 class Response:
     def json(self):
-        return 1
+        return 2


 def helper():
diff --git a/docs/index.md b/docs/index.md
index 3333333..4444444 100644
--- a/docs/index.md
+++ b/docs/index.md
@@ -1 +1 @@
-old
+new
'''
GRAPH = {"directed": True, "multigraph": True, "graph": {},
         "nodes": [{"id": "pkg.models.Response", "name": "pkg.models.Response", "text": "class Response: ..."},
                   {"id": "pkg.models.Response.json", "name": "pkg.models.Response.json", "text": "def json(self): ..."},
                   {"id": "pkg.models.helper", "name": "pkg.models.helper", "text": "def helper(): ..."},
                   {"id": "pkg.api.get", "name": "pkg.api.get", "text": "def get(): ..."}],
         "edges": [{"source": "pkg.api.get", "target": "pkg.models.Response.json", "type": "calls", "key": 0}]}
TASK = {"instance_id": "pkg_1", "repo": "someone/pkg", "base_commit": "abc", "patch": PATCH,
        "problem_statement": "`get()` returns the wrong value", "hints_text": ""}   # a code span names it (script 63)


@pytest.fixture(scope="module")
def dr():
    spec = importlib.util.spec_from_file_location("devset_reach", REPO_ROOT / "python" / "scripts" /
                                                  "67_devset_graph_reach.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_a_module_under_src_or_a_package_root_is_found_by_its_graph_name(dr):
    modules = {"pkg.models", "pkg.api", "tutorial001_py310"}
    assert dr.resolve_module("src/pkg/models.py", modules) == "pkg.models"
    assert dr.resolve_module("pkg/api.py", modules) == "pkg.api"
    assert dr.resolve_module("docs_src/tutorial001_py310.py", modules) == "tutorial001_py310"
    assert dr.resolve_module("pkg/__init__.py", {"pkg"}) == "pkg"
    assert dr.resolve_module("docs/index.md", modules) is None and dr.resolve_module("tests/test_x.py", modules) is None


def test_a_changed_file_is_read_from_github_at_its_base_commit_once(dr, tmp_path):
    calls = []

    def fetch(url):
        calls.append(url)
        return SOURCE

    assert dr.fetch_source("someone/pkg", "abc", "src/pkg/models.py", tmp_path, fetch) == SOURCE
    assert dr.fetch_source("someone/pkg", "abc", "src/pkg/models.py", tmp_path, fetch) == SOURCE   # from the cache
    assert calls == ["https://raw.githubusercontent.com/someone/pkg/abc/src/pkg/models.py"]


def test_the_competitions_search_tool_goes_from_a_named_symbol_to_its_nearest_nodes(dr):
    vectors = {"a": np.array([1.0, 0.0]), "b": np.array([0.0, 1.0]), "c": np.array([0.9, 0.1])}
    assert dr.provided_rank({"a"}, {"c"}, vectors) == 1        # c is a's nearest node
    assert dr.provided_rank({"a"}, {"b"}, vectors) == 2
    assert dr.provided_rank({"c", "a"}, {"c"}, vectors) == 0   # the statement names an edited node itself
    assert dr.provided_rank({"zzz"}, {"c"}, vectors) is None    # a name the archive lacks: nothing to search from
    assert dr.provided_rank({"a"}, set(), vectors) is None


def test_a_row_counts_the_reach_and_holds_no_text(dr):
    ours = {"pkg.models.Response": np.array([1.0, 0.0]), "pkg.models.Response.json": np.array([0.0, 1.0]),
            "pkg.models.helper": np.array([0.7, 0.7]), "pkg.api.get": np.array([1.0, 0.0])}
    row = dr.reach_row(TASK, GRAPH, {"src/pkg/models.py": SOURCE}, provided=ours,
                       query=np.array([0.0, 1.0]), ours=ours)
    assert row == {"instance_id": "pkg_1", "graph_node_count": 4, "changed_file_count": 2, "graphed_file_count": 1,
                   "is_fix_in_graph": True, "edited_node_count": 1, "statement_node_count": 1,
                   "statement_to_fix_edge_count": 1, "edited_node_best_rank_num": 1,
                   "provided_edited_node_best_rank_num": 3}   # from get: Response (1.0), helper (0.71), then json
    assert all(not isinstance(v, str) or v == "pkg_1" for v in row.values())


def test_the_summary_partitions_the_tasks_as_the_paper_does(dr):
    rows = [dict(instance_id="a", is_fix_in_graph=False, edited_node_count=0, graph_node_count=10,
                 statement_to_fix_edge_count=None, edited_node_best_rank_num=None, provided_edited_node_best_rank_num=None),
            dict(instance_id="b", is_fix_in_graph=True, edited_node_count=0, graph_node_count=10,
                 statement_to_fix_edge_count=None, edited_node_best_rank_num=None, provided_edited_node_best_rank_num=None),
            dict(instance_id="c", is_fix_in_graph=True, edited_node_count=1, graph_node_count=10,
                 statement_to_fix_edge_count=0, edited_node_best_rank_num=3, provided_edited_node_best_rank_num=0),
            dict(instance_id="d", is_fix_in_graph=True, edited_node_count=1, graph_node_count=10,
                 statement_to_fix_edge_count=2, edited_node_best_rank_num=40, provided_edited_node_best_rank_num=5),
            dict(instance_id="e", is_fix_in_graph=True, edited_node_count=2, graph_node_count=10,
                 statement_to_fix_edge_count=None, edited_node_best_rank_num=1, provided_edited_node_best_rank_num=None),
            dict(instance_id="f", is_fix_in_graph=True, edited_node_count=1, graph_node_count=10,
                 statement_to_fix_edge_count=None, edited_node_best_rank_num=50, provided_edited_node_best_rank_num=7)]
    s = dr.summary(rows)
    assert (s["task_count"], s["outside_graph_count"], s["no_existing_node_count"], s["edit_node_count"]) == (6, 1, 1, 4)
    assert (s["named_count"], s["called_count"]) == (1, 1)
    assert (s["embedding_top1_count"], s["embedding_top10_count"]) == (1, 2)
    assert s["reached_count"] == 3                       # by name, call edge or embedding search (first ten)
    assert s["chance_top1"] == pytest.approx(0.1 + 0.1 + 0.2 + 0.1)


def test_the_competitions_tool_is_not_credited_with_what_the_statement_already_names(dr):
    """Rank 0 means the statement names an edited node itself, so the search found nothing: the summary counts only
    the finds beyond a name (first ten), and of those the ones names and call edges miss, with no total of both."""
    rows = [dict(instance_id=i, is_fix_in_graph=True, edited_node_count=1, graph_node_count=10,
                 statement_to_fix_edge_count=edge, edited_node_best_rank_num=None, provided_edited_node_best_rank_num=p)
            for i, edge, p in (("named", 0, 0), ("called", 2, 5), ("only_tool", None, 7), ("far", None, 40),
                               ("none", None, None))]
    s = dr.summary(rows)
    assert s["provided_top10_beyond_named_count"] == 2       # called and only_tool, not named (rank 0)
    assert s["provided_top10_beyond_name_or_call_count"] == 1  # only_tool
    assert "provided_top10_count" not in s


PLAIN = '''--- a/src/pkg/models.py
+++ b/src/pkg/models.py
@@ -1,6 +1,6 @@
 class Response:
     def json(self):
-        return 1
+        return 2
 
 
 def helper():
--- a/scripts/new_tool.py
+++ b/scripts/new_tool.py
@@ -0,0 +1,2 @@
+def main():
+    pass
--- a/pkg/old.py
+++ b/pkg/old.py
@@ -1,2 +0,0 @@
-def gone():
-    pass
'''


def test_the_competitions_plain_patches_get_git_headers_and_new_or_deleted_files_are_not_edits(dr):
    """The competition's patches start at `--- a/` (no `diff --git` line) and mark a new file only by an `@@ -0,0`
    hunk: script 63 needs the git header, and a new file has no base version to read."""
    git = dr.git_headers(PLAIN)
    assert dr.gc.changed_files(git) == ["src/pkg/models.py", "scripts/new_tool.py", "pkg/old.py"]
    assert set(dr.gc.changed_runs(git)) == {"src/pkg/models.py"}            # only the file modified in place
    assert "new file mode" in git and "deleted file mode" in git
    assert dr.git_headers(PATCH) == PATCH                                     # already git-style: unchanged
    row = dr.reach_row(dict(TASK, patch=PLAIN), GRAPH, {"src/pkg/models.py": SOURCE})
    assert (row["changed_file_count"], row["graphed_file_count"], row["edited_node_count"]) == (3, 1, 1)


def test_a_restarted_run_skips_the_tasks_already_done_and_keeps_their_rows(dr, tmp_path):
    """Embedding 129 graphs on a CPU takes hours, so each finished row is kept as it is made and a restart skips it."""
    path = tmp_path / "rows.jsonl"
    assert dr.load_done(path) == {}
    dr.append_row(path, {"instance_id": "a", "edited_node_count": 1, "edited_node_best_rank_num": None})
    dr.append_row(path, {"instance_id": "b", "edited_node_count": 0, "edited_node_best_rank_num": 3})
    done = dr.load_done(path)
    assert sorted(done) == ["a", "b"] and done["b"]["edited_node_best_rank_num"] == 3
    path.write_text(path.read_text() + '{"instance_id": "c", "edited')   # a line cut off when the run was stopped
    assert sorted(dr.load_done(path)) == ["a", "b"]


def test_the_vector_cache_is_saved_and_loaded_by_each_texts_hash(dr, tmp_path):
    cache = dr.TextCache()
    cache.update(zip(["def f():\n    return 1", "class A:\n    pass"], [np.ones(4, np.float32), np.zeros(4, np.float32)]))
    assert "def f():\n    return 1" in cache and "def g(): pass" not in cache
    path = tmp_path / "vectors.npz"
    cache.save(path)
    again = dr.TextCache.load(path)
    assert "class A:\n    pass" in again and np.array_equal(again["def f():\n    return 1"], np.ones(4, np.float32))
    assert dr.TextCache.load(tmp_path / "none.npz") == {}
