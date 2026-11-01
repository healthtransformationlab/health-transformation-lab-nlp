"""Reference 57 (Kookal et al. 2024, dental EHR data quality) is cited with what was checked, and spec 029 uses its
twelve checks between the bronze extract and the silver tooth table."""

from health_transformation_lab_nlp.paths import REPO_ROOT


def _entry(path, start, stop):
    text = (REPO_ROOT / path).read_text(encoding="utf-8")
    begin = text.index(start)
    return text[begin:text.index(stop, begin + len(start))]


def test_reference_57_is_the_2024_paper_checked_on_pubmed():
    ref = _entry("docs/references.md", "57. **Kookal KK", "\n\n")
    for fact in ("Walji MF", "J Public Health Dent 2024;84(3):242–250", "10.1111/jphd.12618", "PMID 38659337",
                 "PMC11499288", "spec 029"):
        assert fact in ref
    assert "2014–2108" in ref and "2014–2018" in ref          # the abstract's typo, noted


def test_spec_029_runs_the_twelve_checks_from_bronze_to_silver():
    spec = (REPO_ROOT / "specs" / "029-tooth-loss" / "spec.md").read_text(encoding="utf-8")
    fr = _entry("specs/029-tooth-loss/spec.md", "- **FR-009**", "\n### ")
    assert "Kookal et al. 2024" in fr and "references item 57" in fr
    for domain in ("completeness", "accuracy", "consistency"):
        assert domain in fr
    assert "CDT" in fr and "ICD-10-CM" in fr and "per office" in fr
    assert "Kookal et al. 2024" in (REPO_ROOT / "specs" / "029-tooth-loss" / "tasks.md").read_text()
    assert spec.count("#372") == 0                              # issue numbers only, not the PR
