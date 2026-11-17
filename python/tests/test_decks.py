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


def test_the_tagline_is_on_the_readme_and_the_edr_cover():
    # #573: the lab's tagline, under the README title and on the EDR deck's cover slide
    from health_transformation_lab_nlp.paths import REPO_ROOT

    assert "Evidence you can check" in "\n".join((REPO_ROOT / "README.md").read_text().splitlines()[:3])
    assert "Evidence you can check" in (REPO_ROOT / "docs" / "edr" / "slides" / "01-cover.html").read_text()
    assert "Evidence you can check" in (REPO_ROOT / "docs" / "edr" / "deck.html").read_text()


def test_edr_cost_slides_put_quality_and_the_pass_bar_beside_each_cost():
    """#879: the owner asked "how do we know if the cheaper models are as good", and said the deck didn't make clear
    that PerioBench asks three questions. The main deck is short (cover to the ask, at most 7 slides, the rest after
    the drill-down divider); each question has its own cost slide whose rows give quality, with its 95% interval,
    beside cost, and which states the question's pass bar; a method not run on that question says "not run". Every
    quality figure on those slides is the one its results page reports."""
    slides = [(sid, section) for sid, section, _ in build_decks.slides(REPO_ROOT / "docs" / "edr")]
    sids = [sid for sid, _ in slides]
    assert "economics" not in sids, "the cost slide without quality is replaced by one per question"
    assert len(sids[:sids.index("drill")]) <= 7, "main deck: cover, problem, the three questions, three cost slides, ask"
    for sid in ("phenotyping-cost", "tooth-loss-cost", "deid-cost", "costing", "passes", "tooth-loss"):
        assert sid in sids, sid
    for sid in ("phenotyping-cost", "tooth-loss-cost", "deid-cost"):
        assert sids.index(sid) < sids.index("drill"), f"{sid} is in the main deck"
    text = {sid: " ".join(build_decks.visible_text(section)) for sid, section in slides}
    raw = dict(slides)
    for sid in ("phenotyping-cost", "tooth-loss-cost", "deid-cost"):
        for needed in ("Pass bar", "95%", "not run", "Synthetic"):
            assert needed in text[sid], f"edr/{sid}: '{needed}'"
    results = (REPO_ROOT / "docs" / "results.md").read_text(encoding="utf-8")
    tooth = (REPO_ROOT / "docs" / "tooth_loss.md").read_text(encoding="utf-8")
    pheno = re.findall(r"<b>(\d+\.\d)</b> \((\d+\.\d–\d+\.\d)\)", raw["phenotyping-cost"])
    assert len(pheno) >= 5
    for correct, ci in pheno:
        assert f"**{correct}** ({ci})" in results, f"phenotyping-cost: {correct} ({ci}) not in docs/results.md"
    deid = re.findall(r"<b>(\d+)</b> \((\d+\.\d)–(\d+\.\d) in 100\)", raw["deid-cost"])
    assert len(deid) >= 6
    for leaked, lo, hi in deid:
        assert f"{leaked} of 2,714 (95% range {lo}–{hi}%)" in results, f"deid-cost: {leaked} not in docs/results.md"
    auc = re.findall(r"<b>(0\.\d\d)</b> \((0\.\d\d)–(0\.\d\d)\)", raw["tooth-loss-cost"])
    assert len(auc) == 4
    held_out = re.search(r"\| AUC \(95% CI\) \|.*", tooth).group(0)
    for a, lo, hi in auc:
        assert f"{a} ({lo}-{hi})" in held_out, f"tooth-loss-cost: AUC {a} ({lo}-{hi}) not in docs/tooth_loss.md"
