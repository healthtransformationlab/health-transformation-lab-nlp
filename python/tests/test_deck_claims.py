"""Issue #207: every figure on a deck slide is in docs/claims.yaml with what kind of number it is and where it comes
from, measured figures are found in the repo file that reports them, derived costs recompute from their inputs, and
slides don't claim more than their sources show."""

import datetime
import importlib.util
import re

import pytest
import yaml

from health_transformation_lab_nlp.paths import REPO_ROOT

_spec = importlib.util.spec_from_file_location("build_decks", REPO_ROOT / "docs" / "build_decks.py")
build_decks = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(build_decks)

REGISTER = yaml.safe_load((REPO_ROOT / "docs" / "claims.yaml").read_text(encoding="utf-8"))
KINDS = {"measured", "cited", "derived", "illustrative", "proposal", "identifier"}
# a figure: money, a percent, hours, a multiple, millions, thousands ("20k"), a number of 3+ digits or with thousands
# commas, the count in "41 of 2,462", or a rate written "1 in 7" or "1-in-7" (#838). Prose is left alone: a year after
# "in" ("3 in 2026", so "1 in 2000" needs its comma), "2-in-1", and the end of a decimal ("2.5 in 10")
FIGURE = re.compile(r"\$[\d,.]+\s?[kKM]?|\d[\d,.]*\s?(?:%|h\b|×|M\b|million\b|billion\b)|\b\d+k\b|\b\d{1,3}(?:,\d{3})+\b|\b\d{3,}\b"
                    r"|\b\d+(?= of \d)|(?<![\d.,])\b\d+(?:\s+in\s+|[-\u2011]in[-\u2011])(?!(?:19|20)\d\d\b|1\b(?!,\d))\d[\d,]*\b")
ARXIV = re.compile(r"\b\d{4}\.\d{4,5}\b")
YEAR = re.compile(r"(?:19|20)\d\d")
# wording that claims more than any source can show; a slide says what was measured or priced instead. "never" is
# left out: the decks use it to describe an example answer ("it never asks about the medicine") or a rule a test
# enforces (simulated numbers are never shown as results)
ABSOLUTE = re.compile(r"\b(?:cheap\w*|always|any model|even the largest|guarantee[sd]?|zero cost|free of errors|"
                      r"no one tests|nothing tests|no scorecard checks|have to answer)\b", re.IGNORECASE)


def figures(section: str) -> set[str]:
    text = ARXIV.sub("", " ".join(build_decks.visible_text(section)))
    found = (" ".join(m.group(0).split()).rstrip(",.") for m in FIGURE.finditer(text))   # "1&nbsp;in&nbsp;7" is "1 in 7"
    return {f for f in found if not YEAR.fullmatch(f)}


def test_figures_include_n_in_m_rates_but_not_prose():
    """#838: "1 in 7" is a figure, so a slide that shows one needs a register entry; the pitch's "3 in 4" (#645)
    went unchecked because the pattern didn't see it. A number then "in" and a year or a word is prose, and so are
    "3-in-1" and the "5" of "2.5 in 10"."""
    assert figures("<p>1 in 3 answers; 1 in 11 did the same; a 1-in-7 risk; 1 in 1,000 visits; 41 of 2,462</p>") == \
        {"1 in 3", "1 in 11", "1-in-7", "1 in 1,000", "41", "2,462"}
    assert figures("<p>1&nbsp;in&nbsp;9 kept together, 1 in  12 typed twice, a 1\u2011in\u20115 risk</p>") == \
        {"1 in 9", "1 in 12", "1\u2011in\u20115"}
    assert figures("<p>It came out 3 in 2026 and runs 2 in the morning, 4 in total, in 12 models; a 3-in-1 tool; "
                   "2.5 in 10</p>") == set()


def deck_slides():
    for deck in sorted(build_decks.DECKS):
        for sid, section, notes in build_decks.slides(REPO_ROOT / "docs" / deck):
            yield deck, sid, section, notes


@pytest.mark.parametrize("deck,sid,section,notes", list(deck_slides()), ids=lambda v: v if isinstance(v, str) and len(v) < 30 else "")
def test_every_figure_on_a_slide_is_registered(deck, sid, section, notes):
    registered = {c["value"] for c in REGISTER.get(deck, {}).get(sid, [])}
    missing = sorted(figures(section) - registered)
    assert not missing, f"{deck}/{sid}: add to docs/claims.yaml: {missing}"


def test_register_entries_say_what_they_are_and_where_they_come_from():
    for deck, by_slide in REGISTER.items():
        if deck == "tiers":
            continue
        for sid, claims in by_slide.items():
            for c in claims:
                where = f"{deck}/{sid} {c.get('value')}"
                assert c.get("kind") in KINDS, where
                assert c.get("covers"), where                        # what the number is about, in words
                if c["kind"] == "cited":
                    assert c.get("source"), where
                    assert c.get("checked") is None or isinstance(c["checked"], datetime.date), where
                if c["kind"] == "measured":
                    path = REPO_ROOT / c["file"]
                    assert path.exists(), where
                    assert c.get("match", c["value"]) in path.read_text(encoding="utf-8"), f"{where} not in {c['file']}"
                if c["kind"] == "derived":
                    assert c.get("from"), where


def test_registered_slides_exist():
    real = {(deck, sid) for deck, sid, _, _ in deck_slides()}
    for deck, by_slide in REGISTER.items():
        if deck == "tiers":
            continue
        for sid in by_slide:
            assert (deck, sid) in real, f"docs/claims.yaml names {deck}/{sid}, which has no slide"


def test_the_pitch_cites_noharm_by_version_and_for_severe_errors():
    """#645: the harm slide gave 76.6%, a figure from the preprint's first two versions, as the share of "harmful
    errors" that were omissions. In those versions it is the share of severely harmful errors (of all harmful errors
    it is 50.2%), and the current version says "more than 80% of severe errors". "3 in 4" is not a figure the test
    above sees, so it was never in the register. The claim names the version read, and wherever the pitch gives the
    share it says severe."""
    claims = [c for c in REGISTER["pitch"].get("harm", []) if c["value"] == "80%"]
    assert len(claims) == 1, "docs/claims.yaml, pitch, harm: one entry for NOHARM's 80%"
    assert "arXiv 2512.01241v4" in claims[0]["source"], "name the version the figure was read in"
    assert "more than 80% of severe errors" in claims[0]["source"]
    assert isinstance(claims[0]["checked"], datetime.date)
    assert "severe" in claims[0]["covers"]
    share = re.compile(r"80\s?%|80 percent|76\.6")
    for deck, sid, section, notes in deck_slides():
        if deck != "pitch":
            continue
        said = " ".join(build_decks.visible_text(section)) + " " + notes
        for gone in ("3 in 4", "harmful AI errors", "most harmful errors", "of the harmful errors were omissions",
                     "1,100 real medical cases"):
            assert gone not in said, f"pitch/{sid}: '{gone}'"
        if sid == "harm":
            # a sentence that gives the share of errors (the footer's "The 80% is from NOHARM" only names the source)
            sentences = [t for t in re.split(r"(?<=[.?!:])\s+", said) if share.search(t) and "error" in t]
            assert len(sentences) >= 2, "pitch/harm: the slide and its notes both give the share"
            for sentence in sentences:
                assert "severe" in sentence, f"pitch/harm gives the share without saying severe: {sentence}"


def test_the_pitch_scopes_globaldentbench_rates_to_what_was_rated():
    """#840: GlobalDentBench's "1 in 7" (14.15%) is one discipline's rate, the one the paper calls Systemic Health,
    Pharmacology and Safety, not every answer that involves a medicine (anesthesia answers were 8.93%), and its
    "1 in 3" (31.01%) is of the answers to case questions, not of every answer. The slides said "Where medicines are
    involved" and "1 in 3 answers", and the problem slide's notes gave 4.51% as "about one in twenty"."""
    pitch = {sid: {"slide": " ".join(build_decks.visible_text(section)), "notes": notes}
             for deck, sid, section, notes in deck_slides() if deck == "pitch" and sid in ("problem", "harm")}
    for sid, parts in pitch.items():
        for where, text in parts.items():
            for wide in ("medicines are involved", "involving medicines", "conditions are involved"):
                assert wide not in text, f"pitch/{sid} {where}: '{wide}'"
            sentences = [t for t in re.split(r"(?<=[.?!])\s+", text) if "1 in 7" in t or "one in seven" in t]
            assert sentences, f"pitch/{sid}: the {where} give the 1 in 7"
            for sentence in sentences:
                assert "on medicines and medical conditions" in sentence.lower(), f"pitch/{sid} {where}: {sentence}"
    assert "1 in 3 of those answers was rated unsafe" in pitch["problem"]["slide"]
    # the safety ratings are the study's AI judge's: dentists checked its grading, not its safety ratings (#839)
    for needed in ("rated unsafe by the study's AI judge", "14.15 percent", "Systemic Health, Pharmacology and Safety",
                   "fewer than one in twenty"):
        assert needed in pitch["problem"]["notes"], f"pitch/problem notes: '{needed}'"
    assert "about one in twenty" not in pitch["problem"]["notes"], "4.51% is 1 in 22: say fewer than one in twenty"
    assert "of the answers to case questions" in pitch["harm"]["notes"]


def tier_cost(t: dict) -> float:
    """US dollars for a million visits: tokens per call x list price x calls per visit."""
    per_call = (t["in_tokens"] * t["usd_per_1m_in"] + t["out_tokens"] * t["usd_per_1m_out"]) / 1e6
    return per_call * t.get("calls", 1) * 1_000_000


@pytest.mark.parametrize("name", sorted(REGISTER["tiers"]))
def test_cost_tiers_recompute_from_tokens_and_list_prices(name):
    t = REGISTER["tiers"][name]
    assert t["price_source"] and isinstance(t["price_checked"], datetime.date), name
    assert t["tokens"] in {"measured", "assumed"}, name
    assert abs(tier_cost(t) - t["usd_per_1m_visits"]) <= 0.01 * t["usd_per_1m_visits"], name


@pytest.mark.parametrize("deck,sid,section,notes", list(deck_slides()), ids=lambda v: v if isinstance(v, str) and len(v) < 30 else "")
def test_slides_avoid_absolute_wording(deck, sid, section, notes):
    text = " ".join(build_decks.visible_text(section)) + " " + notes
    hit = ABSOLUTE.search(text)
    assert not hit, f"{deck}/{sid}: '{hit.group(0)}' claims more than a source can show; say what was measured or priced"
