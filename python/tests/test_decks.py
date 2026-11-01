"""The slide decks (docs/<deck>/slides/, built by docs/build_decks.py) and the landing page that links them
(issue #100): the built files match their slides, every figure slide names its source, and the landing README
offers the two paths."""

import importlib.util
import re

import pytest

from health_transformation_lab_nlp.paths import REPO_ROOT

_spec = importlib.util.spec_from_file_location("build_decks", REPO_ROOT / "docs" / "build_decks.py")
build_decks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_decks)


@pytest.mark.parametrize("deck", sorted(build_decks.DECKS))
def test_built_deck_and_full_text_match_the_slides(deck):
    html, md = build_decks.render(deck)
    folder = REPO_ROOT / "docs" / deck
    stale = f"run python docs/build_decks.py ({deck})"
    assert (folder / "deck.html").read_text(encoding="utf-8") == html, stale
    assert (folder / "full_text_and_notes.md").read_text(encoding="utf-8") == md, stale


@pytest.mark.parametrize("deck", sorted(build_decks.DECKS))
def test_every_slide_has_speaker_notes(deck):
    for sid, _, notes in build_decks.slides(REPO_ROOT / "docs" / deck):
        assert notes, f"{deck}/{sid} has no <aside> notes"


def test_edr_deck_labels_its_numbers_synthetic_or_cites_them():
    # a dry run is never a result: every EDR slide with a figure says synthetic, illustrative, or names a source
    for sid, section, _ in build_decks.slides(REPO_ROOT / "docs" / "edr"):
        text = " ".join(build_decks.visible_text(section))
        if re.search(r"\d+ of \d+|\d+%|\d h\b|\$", text):
            assert re.search(r"[Ss]ynthetic|[Ii]llustrative|simulated|dry run|et al\.|GlobalDentBench|consensus", text), sid


def test_landing_readme_offers_two_paths_each_with_an_executive_and_a_detailed_route():
    readme = (REPO_ROOT / "README.md").read_text()
    assert "Personal learning project" in readme and "DISCLAIMER.md" in readme
    for link in ("docs/edr/deck.html", "docs/edr/README.md", "docs/pitch/deck.html", "docs/pitch/README.md"):
        assert f"]({link}" in readme, link
    assert len(readme.splitlines()) <= 80                     # a landing page, not the study


@pytest.mark.parametrize("deck", sorted(build_decks.DECKS))
def test_deck_pages_one_slide_at_a_time_with_a_way_home(deck):
    # issue #178: a reveal.js deck at a pinned version, a link back to the site on every slide, every slide in
    # the jump menu with its notes kept for the speaker view, and links off the site in a new tab
    html, _ = build_decks.render(deck)
    assert re.search(r"reveal\.js@\d+\.\d+\.\d+/dist/reveal\.js", html)
    assert f'class="home" href="{build_decks.SITE}/"' in html
    ids = [sid for sid, _, _ in build_decks.slides(REPO_ROOT / "docs" / deck)]
    assert re.findall(r'<option value="([^"]+)">', html) == ids
    assert html.count('<aside class="notes">') == len(ids)
    assert 'href="' + build_decks.REPO + '" target="_blank" rel="noopener"' in html
    assert html.count('integrity="sha384-') == 3 and html.count('crossorigin="anonymous"') == 3


def test_deck_disclaimer_is_never_cut_off():
    # the synthetic-data line wraps on a narrow screen instead of ending in an ellipsis (PR #179 review)
    rule = re.search(r"\.disclaimer\{[^}]*\}", build_decks.HEAD).group(0)
    assert "nowrap" not in rule and "ellipsis" not in rule and "height" not in rule


@pytest.mark.parametrize("deck", sorted(build_decks.DECKS))
def test_deck_has_labelled_previous_and_next_buttons(deck):
    # issue #206: reveal's small bottom-right arrows were hard to see and hit; the nav bar has labelled buttons
    # beside the slide picker, and reveal's arrows sit large at the slide's edges
    html, _ = build_decks.render(deck)
    assert re.search(r'<button id="deck-prev" aria-label="Previous slide"[^>]*>‹<span class="lbl"> Previous</span>', html)
    assert re.search(r'<button id="deck-next" aria-label="Next slide"[^>]*><span class="lbl">Next </span>›', html)
    assert html.index('id="deck-prev"') < html.index('id="deck-jump"') < html.index('id="deck-next"')
    assert "Reveal.prev()" in html and "Reveal.next()" in html
    assert "isFirstSlide()" in html and "isLastSlide()" in html     # disabled at either end
    assert "controlsLayout:'edges'" in html
    assert re.search(r"\.reveal \.controls\{[^}]*font-size", html)
    # PR #211 review: on a phone the labels and the GitHub link give way, so the pager and Notes stay on screen
    assert re.search(r"@media \(max-width:560px\)\{[^}]*\.topnav \.pager \.lbl[^}]*display:none", html)


@pytest.mark.parametrize("deck", sorted(build_decks.DECKS))
def test_slides_name_the_benchmark_not_the_lab(deck):
    # issue #264: "the lab" alone doesn't tell a reader what it is; a slide or its notes names the benchmark
    # (PerioBench, OralHealthBench) or the agent it means. "Health Transformation Lab", the name, is fine.
    for sid, section, notes in build_decks.slides(REPO_ROOT / "docs" / deck):
        text = " ".join(build_decks.visible_text(section)) + " " + notes
        hit = re.search(r"\bthe lab\b", text, re.IGNORECASE)
        assert not hit, f"{deck}/{sid}: '{text[max(0, hit.start() - 40):hit.end() + 40]}'"


def test_no_overstated_absolutes_about_the_world():
    # issue #274: gum disease is hard to count consistently, not impossible; claims are scoped ("we found no ...")
    import re
    files = [*(REPO_ROOT / "docs").glob("*/slides/*.html"), REPO_ROOT / "README.md"]
    for f in files:
        text = f.read_text(encoding="utf-8")
        for phrase in (r"nobody can (count|study)", r"nobody publishes", r"nobody has measured",
                       r"nobody at this size", r"can't be linked to diabetes"):
            assert not re.search(phrase, text, flags=re.I), (f.name, phrase)
