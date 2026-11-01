"""Issue #192, corrected by #204 (spec 024 US4): Patel et al. 2022 orders three sources, the structured diagnosis
section, then clinical notes, then periodontal charting, with no exam-form or PSR step, and never validated the
order against experts. The exam-form-first order (`algorithm_design`) is this repo's own; the paper's order is
`algorithm_patel2022`. The gum-measurements-first order (`algorithm_v0`) is the repo's own too."""

from health_transformation_lab_nlp.paths import REPO_ROOT

PAPER = "Patel et al., *Methods Inf Med* 2022"
# Wording that says more than the paper does: the exam-form-first order was never the paper's.
OVERCLAIMS = ("after Patel", "After Patel", "follows this order", "not yet checked", "matches in outline")


def _section(path, heading):
    text = (REPO_ROOT / path).read_text(encoding="utf-8")
    start = text.index(heading)
    end = text.find("\n#", start + len(heading))
    return text[start:end if end != -1 else None]


def _no_overclaim(text):
    found = [w for w in OVERCLAIMS if w in text]
    assert not found, f"says more than the paper does: {found}"


def _a2_row():
    rows = [r for r in (REPO_ROOT / "docs" / "action_items.md").read_text(encoding="utf-8").splitlines()
            if r.startswith("| A2 |")]
    assert len(rows) == 1
    return rows[0]


def test_the_rules_page_says_exam_form_first_is_the_repos_own():
    design = _section("docs/evidence_rules.md", "### Rules, exam form first")
    assert PAPER in design and "A2" in design
    assert "this repo's own" in design and "algorithm_patel2022" in design
    assert "diagnosis section" in design and "PSR" in design
    _no_overclaim(design)
    assert "this repo's own" in _section("docs/evidence_rules.md", "### Rules, gum measurements first")


def test_the_walkthrough_and_the_code_point_to_the_papers_order():
    walk = _section("docs/code_walkthrough.md", "## 5. Rule-based phenotype")
    assert PAPER in walk and "algorithm_patel2022" in walk and "repo's own" in walk
    _no_overclaim(walk)
    code = (REPO_ROOT / "python" / "health_transformation_lab_nlp" / "phenotype.py").read_text()
    comment = code[code.index("# Spec 005"):code.index("DESIGN_GROUPS")]
    assert "Patel et al. 2022" in comment and "Methods Inf Med" in comment
    assert "algorithm_patel2022" in comment and "repo's own" in comment
    _no_overclaim(comment)


def test_the_reference_says_what_the_paper_supports():
    ref = _section("docs/references.md", "4. **Patel JS, Brandon R")
    assert "algorithm_design" in ref and "phenotype.py" in ref and "algorithm_v0" in ref
    assert "algorithm_patel2022" in ref and "structured diagnosis section" in ref
    assert "PSR" in ref and "not validated" in ref
    for inconsistency in ("Table 1", "HbA1c", "F1"):
        assert inconsistency in ref
    _no_overclaim(ref)


def test_action_item_a2_records_the_check():
    row = _a2_row()
    assert "PMC9788909" in row and "algorithm_patel2022" in row and "repo's own" in row and "PSR" in row
    _no_overclaim(row)


def test_the_standards_page_does_not_credit_the_paper_with_the_design_order():
    rows = [r for r in (REPO_ROOT / "docs" / "standards.md").read_text(encoding="utf-8").splitlines()
            if "(`algorithm_design`)" in r]
    assert len(rows) == 1 and "repo's own" in rows[0]
    _no_overclaim(rows[0])
