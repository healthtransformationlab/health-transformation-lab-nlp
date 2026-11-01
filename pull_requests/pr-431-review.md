---
pr: 431
branch: feat/203-024-stepwise-phenotype
title: "024 US3: the stepwise phenotype (diagnosis codes, then notes, then chart) scored like the other methods"
author: Claude Code (agent session for jcbowyer)
reviewed_at: 2026-11-01
reviewer: agent self-review against the rubric (no reviewer subagent available in this session) + coordinator verification
verdict: approve-with-nits
---

# PR Review: 024 US3: the Patel et al. 2022 stepwise phenotype, scored

## Summary
This adds `algorithm_patel2022`: diagnosis codes, then the PerioDx Extractor, then the PerioDx Diagnoser, with no
exam form. It is scored everywhere the other rule phenotypes are:
- the leaderboard;
- the reliability scripts;
- the order comparison, as one extra row;
- the DQ grader's gold table and dashboard.

The PR also adds completeness per section, and confusion scores with precision, recall and F1, each with an R twin.

Per-visit outputs go to a new `periodx_visits.csv`, and a full rebuild reproduces every committed dataset
byte for byte. The synthetic results sit beside the paper's figures in separate, labelled columns.

Verdict: approve with nits. It merges after #427 and #423.

## Scope of Change
- Files changed: about 35, excluding the US1/US2 commits and the origin/main merge. Generated data:
  `periodx_visits.csv` (4,343 rows), two small result CSVs, one added row in `phenotype_orders.csv`, the
  regenerated results pages, the dashboard JSON and the ERD sources.
- Areas touched: python, r, docs, specs, data, diagrams, databricks (dashboard JSON only)
- Commits:
  - 3ddade7 Add failing tests for the Patel et al. 2022 stepwise phenotype
  - d5aabde Score the Patel et al. 2022 stepwise phenotype like the other methods
  - 1e78cdb Merge origin/main (resolves `test_parity.R` and the ERD drawio, and renumbers the script 51 → 52 after #422)
- Range reviewed: `cd77442 (head of #427)..1e78cdb`

## CI Status
| Check | Status |
|---|---|
| python | pending at review time; local full suite green after the merge |
| r-parity | pending; the spec 024 blocks and the reliability/order sections pass locally under R |
| bundle, postgres | pending; no bundle or SQL changes beyond the dashboard JSON |

## Secrets, PHI and Claims Scan
- **Secrets:** clean.
- **PHI / real data:** clean. `periodx_visits.csv` holds statuses only (no note text), all synthetic.
- **Organization claims:** clean.
  - The paper's figures appear only in `docs/periodx.md`, each cited by figure, table or text, labelled "real
    records, one dental school", and in their own column (FR-007).
  - No synthetic number is called a replication.

## Strengths
- FR-010 is honoured and checked. `periodx_visits.csv` sits next to the study data, and spec 023's rebuild test now
  covers it. A rebuild in this session matched all 11 files.
- Script 18 keeps its 24 orderings and its selection. The paper's order is appended after selection and can't be
  picked, and the committed CSV gained exactly one row.
- Parity runs end to end on the real outputs: 4,343 visits (Diagnoser values and stepwise merge), completeness and
  confusion scores all match exactly in R.
- The results section explains the synthetic numbers, and each explanation was checked against the data:
  - stage I recall 0.02, from Fig. 2's PD ≥ 4 mm gate;
  - 53 of the 59 Extractor misses are unstaged "bone loss" notes;
  - M1 decides 70% of visits and is right on 65% of them.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
- **Stale committed simulated reliability files.**
  - The files: `data/review/simulated_reliability*/methods_vs_reviewers.csv`, `agreement_vs_humans.csv` and
    `by_level.csv`.
  - Verified: rerunning `13_reliability.py --simulated` adds `algorithm_patel2022`, and also 13 AI prediction files
    that are already on main but missing from these committed files.
  - The PR leaves them for CI's `make_parity_inputs.sh` to refresh. That keeps the diff to this story, and R
    parity reads the method through `with_patel2022_024` either way.
  - Suggested follow-up: refresh them in their own chore.
- **ERD PNGs.** `diagrams/gold/*.png` lack the new column, because draw.io and playwright aren't available here.
  The `.drawio`, `.mmd` and `data_model.md` sources are regenerated.
- **`readme_results._key`** adds the column only when `periodx_visits.csv` exists. Without the file,
  `phenotype_predictions` would raise a KeyError. The file is committed and built by `10_build_study.py`, so this is
  low risk.
- **`telemetry_levels.yaml`.** The new `periodx.*` entries sit just before `phenotype.coverage`, not in strict
  alphabetical order. `39_telemetry_levels.py` re-sorts the file on its next run (`manual: true` keeps the levels).
- **ruff.** 31 findings already on main remain in older touched files (`readme_results.py` ISC004/B023,
  `phenotype.py` SIM102, and others). None is on a changed line, and the new files are clean.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | |
| Synthetic only, no PHI | ✅ | statuses only, synthetic |
| No organization claims | ✅ | paper's figures cited and kept in their own column |
| Test first | ✅ | 3ddade7 before d5aabde; 14 new tests |
| Python and R in parity | ✅ | merge, Diagnoser on visits, completeness and confusion scores to 0 difference; the extra order row too |
| Simulated is labelled simulated | ✅ | results labelled synthetic / generator truth; the order row is scored against simulated reviewers in the `simulated_` folder |
| Seeds fixed | ✅ | no new randomness |
| Paths | ✅ | `DATASETS_DIR` |
| Spec for big changes | ✅ | T007–T010 ticked, T013 ticked with this review |
| SQL and data names | ✅ | `rules_patel2022_status_code` (`_code`, string), declared in `gold_names` and `gold_model` |
| Configuration | ✅ | no settings; the PR says no environment changes, and the gold column arrives with the next Load results |
| Idempotent writes | ✅ | CSV overwrite; the gold table is still overwritten by Load results |
| Words rule | ✅ | `test_wording.py` passes |
| Commits | ✅ | |

## Test Coverage
- `tests/test_phenotype_patel2022.py` (14 tests): order and sections, both acceptance scenarios, planned after
  completed, exam form never used, `visits_table` on hand rows, `section_completeness`, `confusion_scores` by hand
  (one-vs-rest, pooled, NaN precision), score_orders with an extra row, and the committed files.
- `test_grader_tables.py` expects the new column. `test_algorithms_doc.py` checks the 67.5 (61.3–73.3) row
  against results.md.
- Run locally after merging origin/main:
  - `python -m pytest -q tests`: 1412 passed, 15 skipped;
  - `35_readme_results.py --check`: up to date;
  - R spec 024 blocks: 0 differences.

## Verdict
Approve with nits. Merge after #423 and #427.
