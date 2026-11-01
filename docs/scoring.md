# How scoring works

PerioBench scores methods that find gum disease in dental records (phenotyping): each one reads a record and
answers with a periodontal status, healthy to periodontitis stage 4, under the 2017 AAP/EFP classification. This page
covers what a score means on synthetic records, and how real records would be scored. Spec 030 (#387). The definitions,
sources and reading orders side by side: [standards.md](standards.md). What makes a result defensible, and where this repo
stands: [evaluation_checklist.md](evaluation_checklist.md).

## Which records each number counts

The synthetic data has 1,200 patients and 4,343 visits. Different results count different parts of it, so two
numbers that look like they conflict usually count different records:

| Set | Records | What it counts | Used for |
|---|---:|---|---|
| All synthetic visits | 4,343 | every visit of every patient (`visits_structured.csv`) | the study data as a whole |
| Training notes | 3,484 | every visit of 960 patients | training the note-reading models (BERT and others) |
| Review charts (test set) | 240 | one visit each of the other 240 patients, held out, with the answer key (`review_key.csv`) | the review set every method answers |
| Scored review charts | 221 | the review charts from adults' visits on or after 2021-04-01, at five status groups (spec 032 US8, [presets](presets.md); `study.scored_review`) | **every method's score**: 215 vs 163, BERT, MedGemma, the leaderboard |
| Charted visits | 3,437 | the visits, of all 4,343, that have a gum chart | comparing the definitions (2017, CDC/AAP, ACES) and how often the record's parts agree ([standards.md](standards.md)) |
| Open Dental extract | 2,000 patients | a separate synthetic set in Open Dental's table format (spec 029) | the tooth-loss model, one row per tooth |

No patient is in both the training notes and the review charts. The other 619 visits of the 240 held-out patients
aren't used for training either, so a model never sees a held-out patient.

## On synthetic records: agreement with the synthetic answer key, not accuracy

The generator decides each synthetic patient's gum measurements first. It applies the repo's own 2017 rules
([`labels.py`](../python/health_transformation_lab_nlp/labels.py)) to those measurements to get the true status. Then
it writes the chart, the note, the codes and the radiograph reading from that status, with mistakes added on purpose.
The true status goes in an answer key (`data/datasets/answer_key/`) that no method sees.

That truth is right because we defined it, not because anyone checked it. A synthetic score is therefore
**agreement with the synthetic answer key**: how well a method recovers our rules through the noise we added. It is
**not accuracy** on real patients. It's still useful:
- it shows that the code works end to end;
- it compares methods under the same, known conditions;
- it shows how much worse each method does as records get messier.

It can't tell you how often a method is right about a real patient.

Two things make the gap bigger, and the leaderboard now shows both:
- **Some methods share the answer key's rules.** The keyword rules, the rules baseline, the rule phenotypes, the
  "+ stage 4 rule" hybrids, and the probing chart and radiograph read alone all turn measurements into a status with
  `labels.py`. They start with an advantage real records won't give them. The leaderboard marks them with **†**
  (`ladder_eval.uses_answer_key_rules`).
- **Some records can't be staged.** Staging needs attachment loss or bone loss. 13 of the 240 review charts have no
  probing chart and no radiograph, so they are `not_stageable` (`ladder_eval.stageable`). On all 13, the note states
  exactly the true status, because the generator wrote it there. So a method that copies the note looks right for
  free: the keyword rules get all 13. On a real record, a stated diagnosis without measurements can't be checked
  against anything. Each method's score on `stageable` and `not_stageable` records is in
  `data/datasets/ladder/ladder_by_stageable.csv`. R recomputes it in `r/tests/test_parity.R`.

## Do the scores hold on other test sets?

The 240 review charts are one draw (seed 42). `49_seed_stability.py` rebuilds the synthetic study with five seeds
(42, 1, 2, 3, 4) and rescores every method that needs no GPU. The seed-42 scores match the leaderboard exactly. Across
seeds, from `data/datasets/ladder/seed_stability_summary.csv`, out of 100 charts:
- rules, gum measurements first: 92–98;
- word counts plus X-ray: 77–81;
- keyword rules: 75–79;
- rules, exam form first: 72–79.

The order of methods holds, but any single score can move by a few points, so differences of a few points between
methods aren't meaningful on one draw. The note-reading models that need a GPU aren't repeated, and the
bootstrap intervals on the leaderboard stand in for them. Scores by age band and by clinic, for every method, are in
`ladder_by_age.csv` and `ladder_by_clinic.csv`, in the same folder; R recomputes both (spec 030 US2, #397).

## On real records: the acceptance test, against specialists

On real records nobody knows the true status. The recorded diagnosis code isn't it: it's often missing, or doesn't
fit the chart (a record mismatch, usually a coding or charting gap). So the repo uses the acceptance test OHDSI uses
for this ([process.md](process.md#validation-criterion-as-reliable-as-a-human-reviewer); Schuemie, Ostropolets et
al., *npj Digital Medicine* 2025):
1. **Several reviewers stage the same records independently.** They see the chart, radiographs, notes and codes, and
   apply the 2017 classification. The review form is in Label Studio (`labelstudio/chart_review.xml`).
2. **Their agreement with each other is the bar.** That's the mean Cohen's kappa over every pair of reviewers.
   Reviewers never agree perfectly.
3. **A method passes if it agrees with the reviewers at least as much as they agree with each other**
   (`reliability.agreement_vs_humans`, with a 95% paired bootstrap interval and a margin fixed beforehand).

A method is not compared with the reviewers' combined answer, because each reviewer helped make it, which would be
unfair to them.

- **`cannot_determine`:** when a record holds too little to stage, a reviewer can say so. Such records are reported
  apart, not counted as a status.
- **Today the reviewers are simulated**, to test the code. Every such file is named `simulated_*` and is not a result.
  No real review has happened.

## A low-cost reference for real records

A panel of paid specialists is the strongest reference, but there are cheaper steps that still mean something:
1. **A chart-derived reference on fully charted records.** Where a record has a complete probing chart and a
   radiograph, apply the 2017 rules to those measurements. Then score how well the rest of the record (note, codes,
   forms) agrees with that answer. This is the same logic as the synthetic answer key, but on real measurements, and
   it needs no reviewers. It can't score methods that read the chart itself; for those it is circular, as above.
2. **A small review by people already involved.** For example 50 records, two reviewers, each record staged
   independently. That's enough to estimate how well the two agree and to find where methods fail. It isn't enough to
   prove a method passes.
3. **Report the gap.** Set the synthetic score and the real one side by side, with the stageable split. The size of
   the gap is itself a finding about the data's quality.
