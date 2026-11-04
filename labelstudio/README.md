# Label Studio setup

**Rule: only de-identified text goes into Label Studio.** The tasks file
`data/datasets/review_tasks.json` is built only from notes that passed the
final de-identification check (the "leak gate" in `study.py`: any note where a known identifier
survived is held back). With real data, Label Studio runs inside the approved
secure environment and still receives only de-identified notes.

## 1. Run Label Studio locally (synthetic data)

```bash
pip install label-studio            # or: docker run -it -p 8080:8080 -v $(pwd)/ls-data:/label-studio/data heartexlabs/label-studio:latest
label-studio start                  # opens http://localhost:8080
```

## 2. One project per reviewer

Independent staging is the point of the reliability study, so each reviewer
gets their own project and can't see anyone else's answers:

1. *Create Project* → name it `perio-review-<reviewer>`.
2. *Labeling Setup* → *Custom template* → paste `chart_review.xml`.
3. *Import* → `data/datasets/review_tasks.json` (223 charts).
4. Share the project with that reviewer only.
5. Give every reviewer `docs/labeling_protocol.md` before they start.

(One shared project with several annotators per task also works if your
Label Studio edition supports task overlap settings. Separate projects work on
every edition.)

## 3. Export and import

When a reviewer finishes: *Export* → *JSON*. Then:

```bash
cd python
python scripts/12_import_review.py reviewer1.json reviewer2.json reviewer3.json reviewer4.json
python scripts/13_reliability.py            # or, in R: Rscript r/R/04_reliability.R
```

## 4. Dry run without reviewers

```bash
python scripts/12_import_review.py --simulate 4
python scripts/13_reliability.py --simulated
```

Simulated files are named `simulated_*`, and the output says so. They test the
plumbing. They are not results.

## What the config captures

| Field | Type | Used for |
|-------|------|----------|
| `status` | single choice (6 + cannot_determine) | reliability, consensus gold |
| `grade`, `extent` | single choice | secondary outcomes |
| `decided_by` | multi choice of the evidence types (note, exam form, procedure codes and diagnoses completed/planned, probing chart, radiograph) | which evidence types reviewers trust → the rule-based algorithm |
| `conflict` | yes/no | how often evidence types disagree, per reviewer |
| `confidence` | 1–5 rating | stratify agreement by confidence |
| `evidence` | span labels on the note | training and scoring entity extraction |
| `comment` | free text | qualitative review |

# De-identification review projects (spec 008)

Two more projects, separate from chart review. Protocol for annotators:
[`docs/deid_review_protocol.md`](../docs/deid_review_protocol.md).

| Project | Config | Tasks (from `30_deid_review_tasks.py`) | Shows |
|---|---|---|---|
| `deid-gold-<annotator>` | `deid_gold.xml` | `data/raw/deid_gold_tasks.json` | the **original** note; mark every identifier |
| `deid-qa-<reviewer>` | `deid_qa.xml` | `data/raw/deid_qa_tasks.json` | the **de-identified** note; does anything still identify? |

**The gold project shows identified notes.** On synthetic data the identifiers are fake. On real
data it runs only inside the approved secure environment, and it's the one exception to the rule at
the top of this file. The task files live in `data/raw/` and are never committed, the QA tasks
included, because a leak is PHI. `data/raw/deid_qa_key.json` holds the true leaks: don't import it.

```bash
cd python
python scripts/30_deid_review_tasks.py --engine regex_v2+guard --n-gold 60 --n-qa 100
# Label Studio: one project per person, paste the config, import the tasks file
python scripts/31_deid_review_import.py --gold ann1.json ann2.json --qa qa1.json qa2.json
python scripts/31_deid_review_import.py --simulate 3      # dry run: simulated_* files, not results
```

**Pre-annotations.** Gold tasks carry the engine's spans as Label Studio *predictions*: accept, fix,
delete, add. The engine can't tell a patient from a doctor, so names and places load as
`PHI_UNSPECIFIED`; re-label every one. About 20% of gold tasks (seeded) have no pre-annotation;
comparing annotators' recall on those with the rest shows how much the engine anchors them.
QA tasks pre-mark residual-scan hits as `LEAK`.

| Output (`data/deid/review/`) | What it says |
|---|---|
| `gold_agreement.csv` | entity F1 between each pair of annotators, exact span, with and without category |
| `gold_annotator_recall.csv` | each annotator against the generator's spans, aided vs unaided (synthetic only) |
| `gold_engine_scores.csv` | each engine against the human consensus (characters half or more annotators marked) and against the generator |
| `qa_summary.csv` | share of notes with a leak (Wilson 95% CI), pooled and per reviewer; over-redaction; against the key, sensitivity, specificity, share of leaks highlighted |
