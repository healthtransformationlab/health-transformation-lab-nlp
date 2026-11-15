"""Docs that give the size of the study data, or results on it, say what the committed tables hold (#738). #635 did
docs/scoring.md and docs/standards.md (test_scoring_doc.py, test_standards_doc.py); this covers the rest, after #467
rebuilt the notes (223 review charts, 3,794 visits). A line that quotes the earlier build on purpose says
"before #467". SYNTHETIC data only: agreement with the generator's answer key, not clinical performance."""
import json
import re
import subprocess

import pandas as pd
import pytest

from health_transformation_lab_nlp.paths import DATASETS_DIR, REPO_ROOT

EARLIER = "before #467"
# "223 review charts", "the 240 synthetic review notes", "~240 reviewed charts", "240 held-out patients"
COUNT = re.compile(r"(?<![\d.])(\d[\d,]*) (?:synthetic )?(?:review(?:ed)? (?:charts?|notes|visits)|held-out patients)\b",
                   re.IGNORECASE)
# records of a moment, kept as written: specs and past reviews; the before-and-after table of presets.md; a dated plan;
# generated pages (results.md, the EDR summary; the gold data model, drawn from gold_model.py); and the rules files
RECORDS = ("specs/", "pull_requests/", "diagrams/", "docs/presets.md", "docs/plan.md", "docs/results.md",
           "docs/edr/README.md")
RULES_FILES = ("AGENTS.md", "CLAUDE.md")


def _read(rel: str) -> str:
    return (REPO_ROOT / rel).read_text(encoding="utf-8")


def _prose(rel: str) -> str:
    """The file with its line wrapping removed, so re-wrapping a paragraph can't fail a figure."""
    return " ".join(_read(rel).split())


def _markdown_files() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z", "*.md"], cwd=REPO_ROOT, capture_output=True, check=True).stdout
    return [f for f in out.decode().split("\0")
            if f and not f.startswith(RECORDS) and f.rsplit("/", 1)[-1] not in RULES_FILES]


def _row(rel: str, first_cell: str) -> str:
    rows = [line for line in _read(rel).splitlines() if line.startswith(f"| {first_cell} |")]
    assert len(rows) == 1, f"{rel}: expected one table row starting {first_cell!r}, found {len(rows)}"
    return rows[0]


@pytest.fixture(scope="module")
def key():
    return pd.read_csv(DATASETS_DIR / "answer_key" / "review_key.csv")


@pytest.fixture(scope="module")
def ladder():
    return pd.read_csv(DATASETS_DIR / "ladder" / "ladder_vs_truth.csv").set_index("method")


def _per_100(x: float) -> str:
    return f"{100 * x:.1f}"


# ---------- every count of review charts, notes or held-out patients ----------
def test_every_review_count_in_the_docs_is_the_answer_keys(key):
    wrong = []
    for rel in _markdown_files():
        for number, line in enumerate(_read(rel).splitlines(), start=1):
            if EARLIER in line:
                continue
            for m in COUNT.finditer(line):
                if int(m.group(1).replace(",", "")) != len(key):
                    wrong.append(f"{rel}:{number}: {m.group(0)!r}")
    assert not wrong, (f"the answer key has {len(key)} review charts; give that count, or say {EARLIER!r} on a line "
                       "that quotes the earlier build:\n" + "\n".join(wrong))


def test_the_guard_reads_counts_as_they_are_written():
    found = [m.group(1) for m in COUNT.finditer("on the 240 synthetic review notes, ~240 reviewed charts and "
                                                "240 held-out patients; 17 of the 223 review charts; 0.5 review notes")]
    assert found == ["240", "240", "240", "223"]


# ---------- docs/data_sources.md ----------
def test_data_sources_gives_each_files_row_count(key):
    train = pd.read_csv(DATASETS_DIR / "train.csv", usecols=["visit_id"])
    tasks = json.loads((DATASETS_DIR / "review_tasks.json").read_text())
    assert _row("docs/data_sources.md", "`data/datasets/train.csv`").startswith(
        f"| `data/datasets/train.csv` | {len(train):,} de-identified notes")
    assert _row("docs/data_sources.md", "`data/datasets/review_tasks.json`").startswith(
        f"| `data/datasets/review_tasks.json` | {len(tasks)} charts")
    assert _row("docs/data_sources.md", "`data/datasets/answer_key/review_key.csv`").startswith(
        f"| `data/datasets/answer_key/review_key.csv` | The same {len(key)} charts")


# ---------- docs/periodx.md ----------
def test_periodx_results_table_is_the_committed_tables(key):
    comp = pd.read_csv(DATASETS_DIR / "data_quality" / "completeness_patel2022.csv").set_index(["scale", "section"])
    ref, every = comp.loc["reference_set"], comp.loc["all_visits"]
    def pct(frame, col, sections):
        return " / ".join(f"{frame.loc[s, col]:.1f}%" for s in sections)
    page = "docs/periodx.md"
    assert f"This repo: synthetic, {len(key)} review charts" in _row(page, "Measure")
    assert f"| {pct(ref, 'pct_with_value', ('M1', 'M2', 'M3'))} |" in _row(page, "Section has a status (M1 / M2 / M3)")
    assert f"| {ref.loc['merged', 'pct_with_value']:.1f}% |" in _row(page, "Merged phenotype has a status")
    assert f"| {pct(ref, 'pct_decided', ('M1', 'M2', 'M3'))} |" in _row(page, "Visits decided by M1 / M2 / M3")
    scores = pd.read_csv(DATASETS_DIR / "periodx" / "confusion_scores.csv").set_index(["component", "class"])
    assert f"| {scores.loc[('diagnoser', 'pooled'), 'f1']:.2f} pooled" in _row(page, "Diagnoser F1")
    assert f"| {scores.loc[('extractor', 'pooled'), 'f1']:.2f} pooled" in _row(page, "Extractor F1")
    patel = next(line for line in _read("docs/results.md").splitlines() if "| `algorithm_patel2022` |" in line)
    acc, lo, hi = re.search(r"\*\*([\d.]+)\*\* \(([\d.]+)–([\d.]+)\)", patel).groups()
    assert f"| {acc} per 100 charts (95% CI {lo}–{hi})" in _row(page, "Phenotype, correct status")
    assert (f"On all {int(every.loc['M1', 'n_visits']):,} synthetic visits, the sections have a status on "
            f"{pct(every, 'pct_with_value', ('M1', 'M2', 'M3'))} of visits, and the merged phenotype on "
            f"{every.loc['merged', 'pct_with_value']:.1f}%") in _prose(page)
    s1 = scores.loc[("diagnoser", "periodontitis_stage_1")]
    assert f"finds no stage I ({int(s1['tp'])} of {int(s1['tp'] + s1['fn'])}" in _prose(page)


def test_periodx_bullets_count_the_review_notes(key):
    pv = pd.read_csv(DATASETS_DIR / "periodx_visits.csv")
    rev = key[["visit_id", "truth_status", "note_text"]].merge(pv, on="visit_id", how="left")
    no_status = rev[rev["periodx_note_label"].fillna("unknown") == "unknown"]
    no_stage = no_status[no_status["periodx_note_status"] == "periodontitis"]
    assert no_stage["note_text"].str.contains("bone loss", case=False).all()
    page = _prose("docs/periodx.md")
    assert (f"Of the {len(key)} review notes, {len(no_status)} get no status from the Extractor; {len(no_stage)} of "
            "them read as periodontitis with no stage") in page
    from health_transformation_lab_nlp.ladder_eval import grouped
    right = grouped(rev["algorithm_patel2022"]) == grouped(rev["truth_status"])
    by = rev["algorithm_patel2022_decided_by"]
    share = {s: f"{100 * (by == s).mean():.0f}%" for s in ("M1", "M2", "M3")}
    ok = {s: f"{100 * right[by == s].mean():.0f}%" for s in ("M1", "M2")}
    assert (f"The diagnosis codes decide {share['M1']} of the review charts and are right on {ok['M1']} of those, at "
            f"five status groups. The note decides {share['M2']} ({ok['M2']} right) and the chart {share['M3']} "
            f"({int(right[by == 'M3'].sum())} of {int((by == 'M3').sum())} right)") in page


# ---------- docs/medgemma.md ----------
def test_medgemma_field_accuracy_table_is_the_committed_file():
    want = pd.read_csv(DATASETS_DIR / "ladder" / "medgemma_field_accuracy.csv")
    lines = _read("docs/medgemma.md").splitlines()
    start = next(i for i, line in enumerate(lines) if line.startswith("| Run | Field | n | Accuracy"))
    got, run = [], None
    for line in lines[start + 2:]:
        if not line.startswith("|"):
            break
        cells = [c.strip() for c in line.strip("|").split("|")]
        run = cells[0].strip("`") or run
        got.append((run, cells[1], int(cells[2]), cells[3]))
    expected = [(r.run, r.field, int(r.n), f"{r.accuracy:.3f} ({r.ci_lo:.3f}-{r.ci_hi:.3f})")
                for r in want.itertuples()]
    assert sorted(got) == sorted(expected)


def test_medgemma_current_runs_are_the_ladders(ladder):
    vs = pd.read_csv(DATASETS_DIR / "ladder" / "medgemma_vs_bert.csv").set_index("method")
    diff = pd.read_csv(DATASETS_DIR / "ladder" / "medgemma_vs_bert_by_difficulty.csv").set_index(["method", "difficulty"])
    page = _prose("docs/medgemma.md")
    best = vs.loc["medgemma-1.5-4b-it", "reference"]
    for run in ("medgemma-1.5-4b-it", "medgemma-4b-it"):
        r, v = ladder.loc[run], vs.loc[run]
        registry = [line for line in _read("docs/medgemma.md").splitlines()
                    if line.startswith(f"| `{run}` |") and "**run**" in line]
        assert len(registry) == 1 and f"**run** on Kaggle: {_per_100(r['accuracy'])} of 100" in registry[0], run
        assert f"{_per_100(r['accuracy'])} of 100 (95% CI {_per_100(r['acc_lo'])}–{_per_100(r['acc_hi'])})" in page, run
        assert f"against `{best}` {v['diff_vs_ref']:.3f} ({v['diff_lo']:.3f} to {v['diff_hi']:.3f})" in page, run
        levels = " / ".join(f"{100 * diff.loc[(run, lv), 'accuracy']:.0f}%" for lv in ("L1", "L2", "L3"))
        assert f"L1 / L2 / L3 {levels}" in page, run
        assert f"gate pass {100 * v['gate_pass']:.1f}%" in page, run
    llama = ladder.loc["llama-3.3-70b-instruct", "accuracy"]
    assert (f"Llama 3.3 70B ({_per_100(llama)}) already scores higher than MedGemma 1.5 4B "
            f"({_per_100(ladder.loc['medgemma-1.5-4b-it', 'accuracy'])})") in page


def test_medgemma_extent_comparison_is_the_committed_runs():
    ref = pd.read_csv(DATASETS_DIR / "answer_key" / "reference_answers.csv")
    localized = set(ref.loc[ref["extent"] == "localized", "visit_id"])
    called = {}
    for run in ("medgemma-1.5-4b-it", "medgemma-4b-it"):
        d = pd.read_csv(DATASETS_DIR / f"llm_details_{run}.csv")
        d = d[d["visit_id"].isin(localized) & d["gate_ok"].astype(bool)]
        called[run] = int((d["extent"] == "generalized").sum())
    assert (f"4B called {called['medgemma-4b-it']} of the {len(localized)} localized cases generalized "
            f"(1.5 called {called['medgemma-1.5-4b-it']})") in _prose("docs/medgemma.md")


# ---------- docs/scoring.md: the Open Dental row ----------
def test_open_dental_row_names_where_each_size_comes_from():
    jobs = re.findall(r'n_patients:\s*"(\d+)"', _read("databricks/resources/jobs.yml"))
    assert len(jobs) == 1, "expected one n_patients in databricks/resources/jobs.yml (the open_dental_load job)"
    model = re.search(r'add_argument\("--patients", type=int, default=(\d+)',
                      _read("python/scripts/51_tooth_loss_model.py")).group(1)
    sample = len(pd.read_csv(DATASETS_DIR / "tooth_loss" / "patient.csv"))
    row = _row("docs/scoring.md", "Open Dental extract")
    for figure in (f"{int(jobs[0]):,}", f"{int(model):,}", f"{sample:,}"):
        assert figure in row, figure
    for name in ("`open_dental_load`", "`51_tooth_loss_model.py`", "`data/datasets/tooth_loss/`"):
        assert name in row, name
