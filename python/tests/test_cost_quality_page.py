"""#879: the interactive cost-against-quality page beside the PerioBench deck (docs/edr/cost_quality.html). The owner
asked for an interactive version of the deck's main picture to pan, zoom and drill into: the three questions, then
each method's score, 95% range, cost for a million notes, whether it was run, and its sources. Its data is embedded
in the page; every score is the one its results page reports, a method not run has no score, and the deck and the
website copy link to it."""

import importlib.util
import json
import re

import pytest

from health_transformation_lab_nlp.paths import REPO_ROOT

PAGE = REPO_ROOT / "docs" / "edr" / "cost_quality.html"
SLIDES = REPO_ROOT / "docs" / "edr" / "slides"


def data() -> dict:
    html = PAGE.read_text(encoding="utf-8")
    m = re.search(r'<script type="application/json" id="cost-quality-data">(.*?)</script>', html, re.DOTALL)
    assert m, "the page embeds its data as JSON with id cost-quality-data"
    return json.loads(m.group(1))


def methods(qid: str) -> list[dict]:
    return next(q for q in data()["questions"] if q["id"] == qid)["methods"]


def test_the_page_has_the_three_questions_in_the_deck_order():
    qs = data()["questions"]
    assert [q["id"] for q in qs] == ["phenotyping", "tooth_loss", "deid"]
    for q in qs:
        for key in ("name", "metric", "pass_bar", "score_source", "denominator"):
            assert q.get(key), f"{q['id']}: {key}"
        assert q["methods"], q["id"]


def test_a_method_not_run_never_has_a_score_and_a_run_one_always_has_its_range_and_sources():
    for q in data()["questions"]:
        for m in q["methods"]:
            where = f"{q['id']}/{m['name']}"
            assert m["status"] in {"run", "not run"}, where
            if m["status"] == "not run":
                assert m.get("score") is None and m.get("lo") is None and m.get("hi") is None, where
            else:
                assert all(isinstance(m.get(k), (int, float)) for k in ("score", "lo", "hi")), where
                assert m["lo"] <= m["score"] <= m["hi"], where
            assert m.get("cost_label") and m.get("cost_basis"), where
            assert m.get("cost_source") or m["cost_label"] in {"not priced"}, where


def test_phenotyping_scores_are_the_ones_docs_results_reports():
    results = (REPO_ROOT / "docs" / "results.md").read_text(encoding="utf-8")
    for m in methods("phenotyping"):
        if m["status"] == "run":
            row = next(line for line in results.splitlines() if f"`{m['code']}`" in line and line.startswith("|"))
            assert f"**{m['score']:.1f}** ({m['lo']:.1f}–{m['hi']:.1f})" in row, m["code"]
            assert row.split("|")[1].strip() == m["rank"], m["code"]
            assert m["could_rank_first"] == (m["rank"].split("–")[0] == "1"), m["code"]


def test_deid_scores_are_the_ones_docs_results_reports():
    results = (REPO_ROOT / "docs" / "results.md").read_text(encoding="utf-8")
    for m in methods("deid"):
        if m["status"] == "run":
            row = next(line for line in results.splitlines() if line.startswith(f"| {m['rank']} | `{m['code']}` |"))
            assert f"{m['count']:,} of 2,714 (95% range {m['lo']:.1f}–{m['hi']:.1f}%)" in row, m["code"]
            assert f"| {m['damaged']:,} of 2,462 |" in row, m["code"]
            assert abs(m["score"] - 100 * m["count"] / 2714) < 0.05, m["code"]
            assert m["could_rank_first"] == (m["rank"].split("–")[0] == "1"), m["code"]


def test_tooth_loss_scores_are_the_ones_docs_tooth_loss_reports():
    tooth = (REPO_ROOT / "docs" / "tooth_loss.md").read_text(encoding="utf-8")
    held_out = re.search(r"\| AUC \(95% CI\) \|.*", tooth).group(0)
    entry = re.search(r"the AUC is ([\d.]+) / ([\d.]+) \(completed\) and\s+([\d.]+) / ([\d.]+) \(completed \+ planned\)",
                      tooth)
    first_visit = [float(x) for x in entry.groups()]
    run = [m for m in methods("tooth_loss") if m["status"] == "run"]
    assert len(run) == 4
    for m, fv in zip(run, first_visit):
        assert f"{m['score']:.2f} ({m['lo']:.2f}-{m['hi']:.2f})" in held_out, m["name"]
        assert m["first_visit_auc"] == fv, m["name"]


@pytest.mark.parametrize("qid,slide", [("phenotyping", "04-phenotyping-cost.html"), ("tooth_loss", "05-tooth-loss-cost.html"),
                                       ("deid", "06-deid-cost.html")])
def test_the_page_and_the_slide_give_the_same_costs_and_link_each_other(qid, slide):
    html = (SLIDES / slide).read_text(encoding="utf-8")
    for m in methods(qid):
        if m["status"] != "run":
            continue        # not-run prices: the slide gives their range; each names its price source on the page
        assert m["cost_label"].replace("~", "") in html.replace("~", ""), f"{qid}: {m['cost_label']} not on {slide}"
    assert 'href="cost_quality.html' in html, f"{slide} links the interactive page"


def test_the_appendix_links_the_page_and_the_page_says_synthetic_and_names_its_sources():
    assert 'href="cost_quality.html' in (SLIDES / "10-costing.html").read_text(encoding="utf-8")
    html = PAGE.read_text(encoding="utf-8")
    for needed in ("Synthetic", "not affiliated", "not run", "illustrative", "docs/results.md", "docs/tooth_loss.md"):
        assert needed in html, needed
    assert re.search(r"<title>[^<]+</title>", html)


def test_the_website_copies_the_page_beside_the_deck():
    spec = importlib.util.spec_from_file_location("copy_decks_to_site",
                                                  REPO_ROOT / ".github" / "scripts" / "copy_decks_to_site.py")
    cd = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cd)
    assert cd.PAGES == {"docs/edr/cost_quality.html": "perio-bench/cost_quality.html"}
    wf = (REPO_ROOT / ".github" / "workflows" / "copy-decks-to-site.yml").read_text(encoding="utf-8")
    assert "- docs/edr/cost_quality.html" in wf and "perio-bench/cost_quality.html" in wf
