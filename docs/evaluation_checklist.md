# Evaluation checklist: what makes a result defensible

The practices reviewers and examiners look for in a study that builds or tests a model on health records, with where
this repo stands on each (#395). There are two columns:
- **PerioBench:** finding gum disease in records (phenotyping) on the 240 review charts;
- **Tooth-loss model:** spec 029, whose plan is [analysis_plan.md](../specs/029-tooth-loss/analysis_plan.md).

Status: ✅ done · 🟡 partly done or planned · ❌ needs real data or a decision. Updated 2026-10-31.

| # | Practice | What it means | PerioBench | Tooth-loss model |
|---|---|---|---|---|
| 1 | **Write the plan first** | The question, data, outcome, metrics and comparisons are written down before any result, and changes are logged | 🟡 Specs 002, 005 and 030 set the method; not written as one locked plan | ✅ [analysis_plan.md](../specs/029-tooth-loss/analysis_plan.md), with a change log |
| 2 | **Follow a reporting checklist** | TRIPOD+AI for prediction models, RECORD for routinely collected records ([references](references.md) items 59, 60) | ❌ Not mapped yet | 🟡 The plan follows TRIPOD+AI's order; results will be reported against it |
| 3 | **A defensible reference standard** | What a method is compared with, and how much experts agree on it | ❌ Synthetic answer key and simulated reviewers only ([scoring.md](scoring.md)) | ❌ The label is the recorded diagnosis; a small expert check is plan section 13 |
| 4 | **Split by patient; the test set used once** | No patient in both training and testing | ✅ 240 held-out patients ([scoring.md](scoring.md#which-records-each-number-counts)) | 🟡 Planned: 70/30 by patient, stratified |
| 5 | **Test over time and at a second site** | Train on earlier years and test on later ones; then a second practice, unchanged | ❌ Needs real data | 🟡 Over time: planned. Second site: needs a second extract |
| 6 | **Uncertainty, and stability** | Confidence intervals; results that hold on other test sets or seeds | 🟡 Bootstrap intervals and rank ranges; seed stability planned | 🟡 Planned: patient-level bootstrap, 5 generator seeds |
| 7 | **Calibration** | When a method says 70%, it's right about 70% of the time | ✅ Calibration error per method | 🟡 Planned: intercept, slope, 10-bin table |
| 8 | **Simple baselines** | Show the method beats simple rules | ✅ Rules, word counts, each part of the record alone | 🟡 Planned: three baselines (plan section 8) |
| 9 | **Sensitivity analyses** | The answer survives reasonable changes | 🟡 Reading order (24 orders), stageable vs not ([scoring.md](scoring.md)) | 🟡 Planned: seven, one change each (plan section 12) |
| 10 | **Subgroups** | Results by age, sex, type of site, record completeness | 🟡 Stageable split and difficulty level; age and clinic planned | 🟡 Planned (plan section 11) |
| 11 | **Missing data, stated** | How much is missing and what the method does about it | ✅ Coverage per source; messy synthetic records (spec 029 US6) | ✅ Rules fixed (plan section 7); profile of any extract (`realism_profile`) |
| 12 | **Reproducible** | Same code and seed, same numbers; a second language agrees | ✅ Fixed seeds, committed data, Python/R parity tests | ✅ Same; tooth statuses already have R parity |
| 13 | **Honest limitations** | Say what the results don't show | ✅ [scoring.md](scoring.md), [standards.md](standards.md), the † mark on the leaderboard | 🟡 Plan section 16 |

## What needs someone other than this repo

- **A reference standard on real records (3):** reviewers, or the chart-derived reference in [scoring.md](scoring.md).
- **Real data over time and at a second site (5):** an extract from each practice, run inside its own secure
  environment.
- **The study lead's decisions:** age cut-off, study period, the diagnosis-codes step, and planned vs completed
  procedures. They're listed in [analysis_plan.md](../specs/029-tooth-loss/analysis_plan.md) and
  [action_items.md](action_items.md).
