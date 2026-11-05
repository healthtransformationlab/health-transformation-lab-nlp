"""#601: every ERD (gold, Open Dental silver, OMOP silver) is drawn in the owner's data-dictionary format
(dictionary_erd.py), and its entity view keeps the full view's layout with the details left out."""
import importlib.util
import sys
from itertools import pairwise
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
BUILD = ROOT / "diagrams" / "_build"
sys.path.insert(0, str(BUILD))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, BUILD / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


DIC = _load("dictionary_erd")
MODELS = {"gold": _load("gold_model"), "opendental": _load("opendental_silver_model"),
          "omop": _load("omop_silver_model")}


def _keys(m, table):
    """The columns an entity view keeps: keys, and every column a relationship joins on."""
    joined = {c for r in m.RELATIONSHIPS if r.parent == table for c in r.parent_cols}
    joined |= {c for r in m.RELATIONSHIPS if r.child == table for c in r.child_cols}
    return [c.name for c in m.TABLES[table].columns if "PK" in c.key or "FK" in c.key or c.name in joined]


def test_the_gold_model_declares_subject_areas_and_kinds():
    g = MODELS["gold"]
    grouped = [t for _, _, tables in g.GROUPS for t in tables]
    assert sorted(grouped) == sorted(g.TABLES), "each gold table in exactly one subject area"
    assert set(g.KINDS) == set(g.TABLES) and set(g.KINDS.values()) <= {"fact", "dimension", "summary"}
    assert all(g.KINDS[t] == "fact" for t in g.TABLES if t.startswith("fact_"))
    assert all(g.KINDS[t] == "dimension" for t in g.TABLES if t.startswith("dim_"))
    assert g.PHI == set() and isinstance(g.QUESTIONS, dict)


@pytest.mark.parametrize("name", list(MODELS))
def test_the_entity_view_keeps_the_full_views_layout(name):
    m = MODELS[name]
    full, entity = DIC.build(m), DIC.build(m, entity=True)
    assert entity.areas == full.areas, "same subject areas, same places"
    assert set(entity.tables) == set(full.tables) == set(m.TABLES)
    for t, (x, y, w, _) in full.tables.items():
        ex, ey, ew, eh = entity.tables[t]
        assert (ex, ey, ew) == (x, y, w), f"{t} moved in the entity view"
        assert eh <= full.tables[t][3]
    assert len(entity.routes) == len(m.RELATIONSHIPS)


@pytest.mark.parametrize("name", list(MODELS))
def test_the_entity_view_leaves_out_the_details(name):
    m = MODELS[name]
    entity = DIC.build(m, entity=True)
    for t in m.TABLES:
        assert entity.columns[t] == _keys(m, t), f"{t}: the entity view shows only its keys"
    xml = entity.xml("t")
    assert "not profiled yet" not in xml and "n_distinct" not in xml       # no profiles
    assert "Legend" in xml and "FACT" in xml


@pytest.mark.parametrize("name", list(MODELS))
def test_entity_lines_never_cross_a_table(name):
    d = DIC.build(MODELS[name], entity=True)
    for route in d.routes:
        for (x1, y1), (x2, y2) in pairwise(route):
            assert x1 == x2 or y1 == y2, "right angles only"
            lo_x, hi_x, lo_y, hi_y = min(x1, x2), max(x1, x2), min(y1, y2), max(y1, y2)
            for rx, ry, rw, rh in d.obstacles:
                assert not (lo_x < rx + rw - 1 and hi_x > rx + 1 and lo_y < ry + rh - 1 and hi_y > ry + 1)


def test_every_erd_file_is_in_the_dictionary_format():
    files = {"gold": ROOT / "diagrams" / "gold" / "source" / "gold_data_model",
             "opendental": ROOT / "diagrams" / "silver" / "source" / "opendental_silver",
             "omop": ROOT / "diagrams" / "silver" / "source" / "omop_silver"}
    for name, stem in files.items():
        m = MODELS[name]
        for view in ("full", "entity"):
            xml = Path(f"{stem}_{view}.drawio").read_text()
            assert "Legend" in xml, f"{stem}_{view}.drawio is not in the data-dictionary format"
            for title, _, _ in m.GROUPS:
                assert DIC._esc(title) in xml or title in xml, (stem, view, title)
        assert not Path(f"{stem}_dictionary.drawio").exists(), "the full view is the data dictionary now"
