"""Spec 033 US1 (#484): docs/synthetic_data.md lists every generator parameter with its value and either a checked
source (an item of docs/references.md, or the citation in the generator's own code) or the word "placeholder"."""

import dataclasses
import datetime as dt
import inspect
import re
import sys

import pytest

from health_transformation_lab_nlp import medical_record, open_dental, study, synthetic
from health_transformation_lab_nlp.paths import REPO_ROOT

CARD = REPO_ROOT / "docs" / "synthetic_data.md"
REFERENCES = REPO_ROOT / "docs" / "references.md"
COLUMNS = ["Parameter", "Value", "What it means", "Source", "Published figure", "Checked by"]

# the module-level constants the card must list, besides every field of open_dental.Params and every keyword
# argument of synthetic.draw_risk
CONSTANTS = {
    synthetic: ["_SEVERITY_WEIGHTS", "BASE_CAL_MM_PER_YEAR", "SMOKER_EXTRA", "DIABETES_EXTRA", "ONSET_PER_VISIT",
                "TREAT_PROB", "TREATED_RATE_FACTOR", "DIABETES_HBA1C", "DIABETES_OF_HBA1C"],
    study: ["CHARTED_SHARE", "CLINICIAN_DISAGREES", "N_CLINICS", "RECORD_ERROR_RATE", "REVIEW_STRATA",
            "ANALYSIS_MIN_AGE", "ANALYSIS_START_DATE"],
    open_dental: ["ENTRY_PERIO_SHARE_BY_AGE", "DIABETES_HBA1C"],
    medical_record: ["DIABETES_HBA1C", "UNCONTROLLED_HBA1C", "OR_TOLERANCE_LOG", "HYPERTENSION_CONTROL", "MEASURES"],
}


def _rows() -> dict[str, dict[str, str]]:
    """Every table row of the card whose first cell names a parameter in backticks, keyed by that name."""
    rows = {}
    for line in CARD.read_text().splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if not line.startswith("|") or len(cells) != len(COLUMNS) or not cells[0].startswith("`"):
            continue
        rows[cells[0].split("`")[1]] = dict(zip(COLUMNS, cells))
    return rows


def _declared() -> dict[str, object]:
    """Card name -> the value the code holds now."""
    out = {f"Params.{f.name}": f.default if f.default is not dataclasses.MISSING else f.default_factory()
           for f in dataclasses.fields(open_dental.Params)}
    for name, p in inspect.signature(synthetic.draw_risk).parameters.items():
        if p.default is not inspect.Parameter.empty:
            out[f"draw_risk({name})"] = p.default
    for module, names in CONSTANTS.items():
        short = module.__name__.rsplit(".", 1)[1]
        out.update({f"{short}.{n}": getattr(module, n) for n in names})
    for c in medical_record.CONDITIONS:
        out[f"medical_record.CONDITIONS[{c.column}]"] = (c.base_rates, c.odds_ratio)
    return out


def _numbers(value) -> list[str]:
    """The numbers in a value (nested tuples, dicts), as the card writes them."""
    if isinstance(value, bool) or value is None:
        return []
    if isinstance(value, (int, float)):
        return [f"{value:g}"]
    if isinstance(value, dt.date):
        return [value.isoformat()]
    if isinstance(value, dict):
        return [n for v in value.values() for n in _numbers(v)]
    if isinstance(value, (tuple, list)):
        return [n for v in value for n in _numbers(v)]
    return []


def _reference_items() -> set[str]:
    return set(re.findall(r"^(\d+)\. ", REFERENCES.read_text(), re.MULTILINE))


def test_the_card_exists_and_says_every_number_is_synthetic():
    text = CARD.read_text()
    assert "SYNTHETIC" in text
    assert "| " + " | ".join(COLUMNS) + " |" in text


@pytest.mark.parametrize("name", sorted(_declared()))
def test_every_declared_parameter_is_in_the_card(name):
    assert name in _rows(), f"docs/synthetic_data.md has no row for `{name}`"


@pytest.mark.parametrize("name", sorted(_declared()))
def test_every_parameter_has_a_source_or_says_placeholder(name):
    row = _rows().get(name)
    if row is None:
        pytest.skip("missing row is reported by the test above")
    source = row["Source"]
    items = re.findall(r"item (\d+)", source)
    assert "placeholder" in source.lower() or items or "cited in `" in source, \
        f"`{name}`: the source column names no references.md item, no code citation and no 'placeholder'"
    missing = set(items) - _reference_items()
    assert not missing, f"`{name}` cites docs/references.md items {sorted(missing)}, which don't exist"


@pytest.mark.parametrize("name", sorted(_declared()))
def test_the_card_gives_the_value_the_code_holds(name):
    row = _rows().get(name)
    if row is None:
        pytest.skip("missing row is reported by the test above")
    for n in _numbers(_declared()[name]):
        assert re.search(rf"(?<![\d.]){re.escape(n)}(?![\d])", row["Value"]), \
            f"`{name}`: the card's value '{row['Value']}' doesn't show {n}"


def test_the_detector_catches_a_row_without_a_source(tmp_path, monkeypatch):
    card = tmp_path / "card.md"
    card.write_text("| " + " | ".join(COLUMNS) + " |\n| `Params.n_patients` | 2000 | patients | | | |\n")
    monkeypatch.setattr(sys.modules[__name__], "CARD", card)
    assert _rows()["Params.n_patients"]["Source"] == ""
    with pytest.raises(AssertionError):
        test_every_parameter_has_a_source_or_says_placeholder("Params.n_patients")
