"""The rule in AGENTS.md ("The benchmarks"): the benchmarks are always named in one order, PerioBench, then
OralHealthBench, then AccessBench, in any spelling (PerioBench, perio_bench, gold_oral_health_bench). A list that
names two of them out of order fails here, as test_wording.py does for wording. Past PR reviews in pull_requests/
are records and stay as written; the owner's own words quoted in a spec go in QUOTED."""

import re
import subprocess

import pytest

from health_transformation_lab_nlp import schemas
from health_transformation_lab_nlp.paths import REPO_ROOT

ORDER = ["PerioBench", "OralHealthBench", "AccessBench"]
NAMES = {"PerioBench": r"perio[ _-]?bench", "OralHealthBench": r"oral[ _-]?health[ _-]?bench",
         "AccessBench": r"access[ _-]?bench"}
LAYER = r"(?:(?:landing|bronze|silver|gold)_)?"
GAP = r"[^A-Za-z0-9]{0,12}(?:(?:and|or|then)[^A-Za-z0-9]{1,12})?"   # ", ", " and ", "`, `", " / ", " · "
OUT_OF_ORDER = re.compile("|".join(
    rf"\b{LAYER}{NAMES[later]}\b{GAP}{LAYER}{NAMES[earlier]}\b"
    for i, earlier in enumerate(ORDER) for later in ORDER[i + 1:]), re.IGNORECASE)
ALLOWED = {"python/tests/test_bench_order.py"}
# file: text on the line that marks it as someone's own words, quoted
QUOTED = {"specs/022-bench-schemas/spec.md": "**Input**"}


def _tracked_files():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=REPO_ROOT, capture_output=True, check=True).stdout
    return [f for f in out.decode().split("\0") if f]


def test_no_file_lists_the_benchmarks_out_of_order():
    hits = []
    for rel in _tracked_files():
        path = REPO_ROOT / rel
        if rel in ALLOWED or rel.startswith("pull_requests/") or not path.is_file():
            continue
        data = path.read_bytes()
        if b"\0" in data[:8192]:            # binary: images, archives
            continue
        for n, line in enumerate(data.decode("utf-8", "replace").splitlines(), 1):
            m = OUT_OF_ORDER.search(line)
            if m and not (rel in QUOTED and QUOTED[rel] in line):
                hits.append(f"{rel}:{n}: {m.group(0)}")
    assert not hits, "See AGENTS.md, 'The benchmarks': PerioBench, OralHealthBench, AccessBench:\n" + "\n".join(hits)


def test_agents_md_states_the_order():
    text = (REPO_ROOT / "AGENTS.md").read_text()
    section = text.split("## The benchmarks", 1)[1].split("\n## ", 1)[0]
    assert [section.index(f"**{name}") for name in ORDER] == sorted(section.index(f"**{name}") for name in ORDER)


def test_the_schemas_follow_the_order():
    # the benchmarks keep their order; other schema families (spec 029's opendental_perio) come after them
    assert [b for b in schemas.LAYERS if b.endswith("_bench")] == ["perio_bench", "oral_health_bench", "access_bench"]
    assert list(schemas.LAYERS)[:3] == ["perio_bench", "oral_health_bench", "access_bench"]


@pytest.mark.parametrize("text", [
    "OralHealthBench and PerioBench", "(OralHealthBench, PerioBench)", "access_bench and oral_health_bench",
    "`gold_access_bench`, `gold_oral_health_bench`", "AccessBench / PerioBench", "Access Bench or Perio Bench"])
def test_lists_out_of_order_are_caught(text):
    assert OUT_OF_ORDER.search(text)


@pytest.mark.parametrize("text", [
    "PerioBench and OralHealthBench", "perio_bench, oral_health_bench and access_bench",
    "OralHealthBench builds its questions from the patients PerioBench made",    # a sentence, not a list
    "OralHealthBench pitch: docs/pitch/"])
def test_lists_in_order_and_prose_pass(text):
    assert not OUT_OF_ORDER.search(text)
