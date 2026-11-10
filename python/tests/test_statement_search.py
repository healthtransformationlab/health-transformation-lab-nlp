"""Spec 028 (#662): does embedding search find the fix? Rank a task's graph nodes by similarity to its statement
and see where the nodes its fix edits land. The model is not loaded here: the ranking is tested on small vectors."""
import importlib.util

import numpy as np
import pytest

from health_transformation_lab_nlp.paths import REPO_ROOT


@pytest.fixture(scope="module")
def search():
    spec = importlib.util.spec_from_file_location(
        "statement_search", REPO_ROOT / "python" / "scripts" / "64_statement_search.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _unit(*xs):
    v = np.array(xs, dtype=np.float32)
    return v / np.linalg.norm(v)


VECTORS = {"pkg.a.near": _unit(1, 0.1, 0), "pkg.a.mid": _unit(1, 1, 0), "pkg.b.far": _unit(0, 1, 0),
           "pkg.b.opposite": _unit(-1, 0, 0)}
QUERY = _unit(1, 0, 0)


def test_the_best_rank_is_the_position_of_the_closest_edited_node(search):
    assert search.best_rank(QUERY, VECTORS, {"pkg.a.near"}) == 1
    assert search.best_rank(QUERY, VECTORS, {"pkg.b.far"}) == 3
    assert search.best_rank(QUERY, VECTORS, {"pkg.b.far", "pkg.a.mid"}) == 2   # the better of the two


def test_no_edited_node_or_no_vectors_gives_no_rank(search):
    assert search.best_rank(QUERY, VECTORS, set()) is None
    assert search.best_rank(QUERY, {}, {"pkg.a.near"}) is None


def test_an_edited_node_without_a_vector_is_an_error(search):
    with pytest.raises(SystemExit, match="pkg.c.missing"):   # the graph and its embeddings must hold the same nodes
        search.best_rank(QUERY, VECTORS, {"pkg.c.missing"})


def test_a_query_is_cut_to_the_nodes_dimensions_and_made_a_unit_vector(search):
    raw = np.array([[3.0, 4.0, 12.0, 99.0]])
    cut = search.unit_rows(raw, dims=3)
    assert cut.shape == (1, 3) and np.allclose(np.linalg.norm(cut, axis=1), 1.0)
    assert np.allclose(cut[0], np.array([3.0, 4.0, 12.0]) / 13.0)


def test_the_counts_are_split_by_whether_names_or_call_edges_already_found_the_fix(search):
    rows = [{"edited_node_best_rank_num": 1, "is_named_or_called": True},
            {"edited_node_best_rank_num": 4, "is_named_or_called": False},
            {"edited_node_best_rank_num": 30, "is_named_or_called": False},
            {"edited_node_best_rank_num": None, "is_named_or_called": False}]   # no edited node: not counted
    assert search.top_counts(rows) == {"all": {"tasks": 3, "top1": 1, "top5": 2, "top10": 2},
                                       "missed": {"tasks": 2, "top1": 0, "top5": 1, "top10": 1}}
