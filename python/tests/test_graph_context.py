"""028 AI7 (#674), the graph arm: graph-guided retrieval done for the agent before it starts. The context lists the
nodes the statement names, the nodes one call edge from those, and the nodes nearest the statement by embedding
search. It is built from the statement and the graph alone, never from the fix or the tests, so unlike the failing
test's report it is a condition a deployed agent could have. The committed table holds counts, never the text."""
import importlib.util

import numpy as np
import pytest

from health_transformation_lab_nlp.paths import REPO_ROOT


@pytest.fixture(scope="module")
def gcx():
    spec = importlib.util.spec_from_file_location("graph_context", REPO_ROOT / "python" / "scripts" / "72_graph_context.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


GRAPH = {"nodes": [{"id": i, "name": i.rsplit(".", 1)[-1], "text": ""}
                   for i in ("pkg.mod.helper", "pkg.mod.total", "pkg.mod.Box", "pkg.mod.Box.check", "pkg.api.get")],
         "edges": [{"source": "pkg.api.get", "target": "pkg.mod.helper", "type": "calls", "key": 0},
                   {"source": "pkg.mod.total", "target": "pkg.mod.helper", "type": "calls", "key": 0}]}
MODULES = {"pkg.mod", "pkg.api"}


def test_the_nearest_nodes_are_ranked_by_cosine_similarity(gcx):
    vectors = {"a": np.array([1.0, 0.0]), "b": np.array([0.6, 0.8]), "c": np.array([0.0, 1.0])}
    assert gcx.top_nodes(np.array([1.0, 0.0]), vectors, 2) == ["a", "b"]
    assert gcx.top_nodes(np.array([0.0, 1.0]), vectors, 5) == ["c", "b", "a"]


def test_neighbours_are_one_call_edge_from_a_named_node_either_way(gcx):
    assert gcx.neighbours({"pkg.mod.helper"}, GRAPH, limit=8) == ["pkg.api.get", "pkg.mod.total"]
    assert gcx.neighbours({"pkg.mod.helper", "pkg.api.get"}, GRAPH, limit=8) == ["pkg.mod.total"]   # not the named ones
    assert gcx.neighbours({"pkg.mod.helper"}, GRAPH, limit=1) == ["pkg.api.get"]
    assert gcx.neighbours(set(), GRAPH, limit=8) == []


def test_a_node_is_shown_with_the_file_that_holds_it(gcx):
    assert gcx.node_path("pkg.mod.Box.check", MODULES) == "python/pkg/mod.py"
    assert gcx.node_path("pkg.api.get", MODULES) == "python/pkg/api.py"
    assert gcx.node_path("other.thing", MODULES) is None


def test_the_context_lists_what_the_statement_names_their_neighbours_and_the_nearest_nodes(gcx):
    text = gcx.graph_context(["pkg.mod.helper"], ["pkg.api.get", "pkg.mod.total"],
                             ["pkg.mod.Box.check", "pkg.mod.helper"], MODULES)
    assert text.splitlines() == [
        "Graph retrieval for this issue (computed from the issue text and this repository's code graph alone):",
        "Named in the issue: pkg.mod.helper (python/pkg/mod.py)",
        "One call away from those: pkg.api.get (python/pkg/api.py); pkg.mod.total (python/pkg/mod.py)",
        "Nearest to the issue text by embedding search:",
        "1. pkg.mod.Box.check (python/pkg/mod.py)",
        "2. pkg.mod.helper (python/pkg/mod.py)"]


def test_a_statement_that_names_nothing_gets_the_search_alone_and_no_nodes_is_no_context(gcx):
    lines = gcx.graph_context([], [], ["pkg.mod.total"], MODULES).splitlines()
    assert lines[1] == "Nearest to the issue text by embedding search:" and len(lines) == 3
    assert gcx.graph_context([], [], [], MODULES) == ""


def test_the_context_is_built_without_the_fix_and_the_row_alone_says_whether_it_listed_an_edited_node(gcx):
    import inspect
    assert "edited" not in inspect.signature(gcx.graph_context).parameters       # the text never sees the answer
    row = gcx.shape_row("t1", ["pkg.mod.helper"], ["pkg.api.get"], ["pkg.mod.Box.check"], "x" * 40,
                        edited={"pkg.mod.Box.check"})
    assert row == {"instance_id": "t1", "named_node_count": 1, "neighbour_node_count": 1, "similar_node_count": 1,
                   "context_chars": 40, "is_edited_node_listed": True}
    assert gcx.shape_row("t2", [], [], ["pkg.mod.total"], "x", edited=set())["is_edited_node_listed"] is None
    assert gcx.shape_row("t3", [], [], ["pkg.mod.total"], "x", edited={"pkg.mod.helper"})["is_edited_node_listed"] is False


def test_a_task_whose_graph_is_empty_still_gets_a_context_that_says_so(gcx):
    """Every task of the arm has the retrieval after its hints; for an empty graph the retrieval's answer is that."""
    assert gcx.context_or_empty("") == (
        "Graph retrieval for this issue (computed from the issue text and this repository's code graph alone):\n"
        "The code graph at this commit holds no functions or classes.")
    assert gcx.context_or_empty("some context") == "some context"
