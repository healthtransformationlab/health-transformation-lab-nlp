"""Issue #923: a deck's PowerPoint is built from its slide sources (docs/build_pptx.py): one PowerPoint slide per
HTML slide, in order, with the same heading and the speaker notes, and the committed file is current."""

import importlib.util
import re

import pytest

from health_transformation_lab_nlp.paths import REPO_ROOT

pptx = pytest.importorskip("pptx")


def _load(name):
    spec = importlib.util.spec_from_file_location(name, REPO_ROOT / "docs" / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


build_decks = _load("build_decks")
build_pptx = _load("build_pptx")


def _text(shape):
    return shape.text_frame.text if shape.has_text_frame else ""


@pytest.mark.parametrize("deck", sorted(build_pptx.PPTX_NAMES))
def test_pptx_has_one_slide_per_html_slide_with_heading_and_notes(deck):
    html_slides = list(build_decks.slides(REPO_ROOT / "docs" / deck))
    prs = build_pptx.build(deck)
    assert len(prs.slides) == len(html_slides)
    for slide, (sid, section, notes) in zip(prs.slides, html_slides):
        text = " ".join(_text(s) for s in slide.shapes)
        assert build_decks.heading(section, sid) in text, sid
        spoken = slide.notes_slide.notes_text_frame.text
        assert spoken == build_pptx.plain(notes), sid


@pytest.mark.parametrize("deck", sorted(build_pptx.PPTX_NAMES))
def test_committed_pptx_is_current(deck):
    path = REPO_ROOT / "docs" / deck / build_pptx.PPTX_NAMES[deck]
    assert path.exists(), f"run python docs/build_pptx.py {deck}"
    committed = pptx.Presentation(str(path))
    built = build_pptx.build(deck)
    stale = f"run python docs/build_pptx.py {deck}"
    assert len(committed.slides) == len(built.slides), stale
    for a, b in zip(committed.slides, built.slides):
        assert [_text(s) for s in a.shapes] == [_text(s) for s in b.shapes], stale
        assert a.notes_slide.notes_text_frame.text == b.notes_slide.notes_text_frame.text, stale


def test_access_deck_shows_no_answer_score_and_labels_its_numbers():
    # no live AccessBench run exists yet: a figure on a slide is a count of questions, simulated, or cited
    for sid, section, _ in build_decks.slides(REPO_ROOT / "docs" / "access"):
        text = " ".join(build_decks.visible_text(section))
        assert not re.search(r"\d+%", text), f"access/{sid} shows a percentage"


def test_access_deck_is_not_published_to_the_site():
    assert "access" not in build_decks.SITE_PAGES
    workflow = (REPO_ROOT / ".github" / "workflows" / "copy-decks-to-site.yml").read_text()
    assert "docs/access" not in workflow


def test_readme_has_accessbench_as_its_third_benchmark():
    readme = (REPO_ROOT / "README.md").read_text()
    assert "## 3. AccessBench (exploratory)" in readme and "Three benchmarks" in readme
    for link in ("benchmarks/access_bench/README.md", "docs/access/deck.html", "docs/access/full_text_and_notes.md",
                 "docs/access/access_bench.pptx"):
        assert f"]({link}" in readme, link
    assert readme.index("## 1. PerioBench") < readme.index("## 2. OralHealthBench") < readme.index("## 3. AccessBench")
