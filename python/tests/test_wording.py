"""The rule in AGENTS.md ("Words"): we find gum disease in records, we don't diagnose. "Diagnosis" may name what a
dentist recorded (a diagnosis code), never what our rules, models or agents do. AGENTS.md, which states the rule, and
this test are the only files allowed the phrases; past PR reviews in pull_requests/ are records and stay as written;
a quote from a cited paper goes in QUOTED."""

import re
import subprocess

import pytest

from health_transformation_lab_nlp.paths import REPO_ROOT

SUBJECT = r"(?:we|AI|models?|rules?|agents?|LLMs?|BERT|readers?|classifiers?|algorithms?|tools?|systems?)"
PHRASES = re.compile(
    r"\b(misdiagnos\w*"
    r"|diagnostic (?:tools?|models?|agents?|AI)\b"   # not the Dental Diagnostic System terminology
    r"|(?:in)?(?:accurate|correct)(?:ly)? diagnos\w*"
    r"|diagnos\w* (?:accuracy|is accurate)"
    r"|(?:wrong|AI|automated|model-based) diagnos\w*"
    r"|" + SUBJECT + r" (?:can |to |that )?diagnos(?:e|es|ing)\b"
    r"|diagnosed by (?:the |a |our )?" + SUBJECT + r")",
    re.IGNORECASE)
ALLOWED = {"AGENTS.md", "python/tests/test_wording.py"}
# file: text on the line that marks it as a cited source's own words, or a record of how wording changed
QUOTED = {"docs/rag_and_vocabulary.md": "MedRAG",
          "specs/013-literature-methods/spec.md": "PheValuator",             # PheValuator's own term
          "specs/011-plain-results-metrics/spec.md": "ncorrect diagnosis",  # the spec's history of renaming it
          "python/tests/test_readme_results.py": "not in",                   # checks the old wording is gone
          "data/tasks/task_manifest.csv": "htlnlp_"}                         # a record of past PR titles, verbatim (spec 028)


def _tracked_files():
    out = subprocess.run(["git", "ls-files", "-z"], cwd=REPO_ROOT, capture_output=True, check=True).stdout
    return [f for f in out.decode().split("\0") if f]


def test_no_file_says_we_diagnose():
    hits = []
    for rel in _tracked_files():
        path = REPO_ROOT / rel
        if rel in ALLOWED or rel.startswith("pull_requests/") or not path.is_file():
            continue
        data = path.read_bytes()
        if b"\0" in data[:8192]:            # binary: images, archives
            continue
        for n, line in enumerate(data.decode("utf-8", "replace").splitlines(), 1):
            if PHRASES.search(line) and not (rel in QUOTED and QUOTED[rel] in line):
                hits.append(f"{rel}:{n}: {PHRASES.search(line).group(0)}")
    assert not hits, "See AGENTS.md, 'Words': reword these:\n" + "\n".join(hits)


def test_agents_md_states_the_rule():
    assert "## Words" in (REPO_ROOT / "AGENTS.md").read_text()


@pytest.mark.parametrize("text", [
    "the model diagnoses gum disease", "AI diagnosis of gum disease", "the rule diagnoses it", "BERT diagnoses",
    "we diagnose periodontitis", "diagnosed by the model", "automated diagnosis", "model-based diagnosis",
    "a diagnostic model", "a diagnostic tool", "incorrect diagnosis", "more accurate diagnosis", "misdiagnosis",
    "diagnostic accuracy"])
def test_phrases_that_say_we_diagnose_are_caught(text):
    assert PHRASES.search(text)


@pytest.mark.parametrize("text", [
    "diagnosis codes on completed procedures", "the recorded diagnosis", "the dentist's diagnosis",
    "diagnostic tooling", "Diagnosis: periodontitis stage III", "SNODENT, Dental Diagnostic System"])
def test_what_a_dentist_recorded_is_not_caught(text):
    assert not PHRASES.search(text)
