"""Spec 044 US1 (#938, ADR 0014): AccessBench has three sections, oral first, and every question names one."""

import pytest

from health_transformation_lab_nlp import access_hard_items as ahi
from health_transformation_lab_nlp import access_phi_items as api
from health_transformation_lab_nlp import access_sections as sec
from health_transformation_lab_nlp.paths import REPO_ROOT


def test_three_sections_with_oral_first():
    assert sec.SECTIONS == ("oral", "medical", "mental")
    assert sec.FIRST_SECTION == "oral"


def test_every_current_question_is_oral():
    rows = api.load_items() + ahi.load_items()
    assert rows and {r["section_code"] for r in rows} == {"oral"}


@pytest.mark.parametrize("bad", [None, "", "dental", "Oral"])
def test_a_missing_or_unknown_section_is_refused(bad):
    row = dict(ahi.load_items()[0])
    if bad is None:
        row.pop("section_code")
    else:
        row["section_code"] = bad
    with pytest.raises(ValueError, match="section_code"):
        ahi.validate_item(row)
    with pytest.raises(ValueError, match="section_code"):
        sec.validate_section(row, "x")


def test_the_decision_and_the_readmes_say_oral_is_first():
    adr = (REPO_ROOT / "docs/adr/0014-accessbench-oral-medical-mental-sections.md").read_text()
    assert "oral" in adr and "medical" in adr and "mental" in adr
    bench = (REPO_ROOT / "benchmarks/access_bench/README.md").read_text()
    assert "## Sections" in bench and "medical" in bench and "mental" in bench
