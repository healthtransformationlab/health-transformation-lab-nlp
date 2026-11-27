"""045 DOCS1 (#981): AccessBench has a licence, a data dictionary that covers every field, and a canary on every row."""

import json
import re

import pytest

from health_transformation_lab_nlp import access_sections
from health_transformation_lab_nlp.paths import REPO_ROOT

BENCH = REPO_ROOT / "benchmarks" / "access_bench"
FILES = sorted((BENCH / "items").glob("*.jsonl")) + sorted((BENCH / "controls").glob("*.jsonl"))


def _rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")]


def _documented():
    """Field names in the first column of the dictionary's tables: `| `name` | ...`."""
    text = (BENCH / "data_dictionary.md").read_text(encoding="utf-8")
    return set(re.findall(r"^\| `([a-z_]+)` \|", text, flags=re.M))


def test_the_licence_covers_questions_keys_and_controls_and_names_its_sources():
    text = (BENCH / "LICENSE.md").read_text(encoding="utf-8")
    assert "CC BY 4.0" in text and "creativecommons.org/licenses/by/4.0" in text
    for words in ("questions", "answer keys", "control answers", "Reddit", "public domain", "Apache"):
        assert words in text, words


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_every_field_in_every_file_is_in_the_data_dictionary(path):
    fields = set()
    for r in _rows(path):
        fields |= set(r)
        for res in r.get("resources") or []:
            fields |= set(res)
    missing = fields - _documented()
    assert not missing, f"{path.name}: describe {sorted(missing)} in data_dictionary.md"


@pytest.mark.parametrize("path", FILES, ids=lambda p: p.name)
def test_every_row_carries_the_canary(path):
    assert all(r.get("canary_text") == access_sections.CANARY_TEXT for r in _rows(path)), path.name


def test_the_canary_is_a_guid_and_the_validity_page_answers_the_three_questions():
    assert re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", access_sections.CANARY_TEXT)
    text = (REPO_ROOT / "docs" / "access_bench_validity.md").read_text(encoding="utf-8")
    for heading in ("What counts as the right answer", "Can it be graded consistently",
                    "Could it already be in a model's training data"):
        assert heading in text, heading
