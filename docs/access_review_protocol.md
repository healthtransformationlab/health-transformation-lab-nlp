# AccessBench review protocol (spec 043 US7, #933)

> **Personal learning project.** Every AccessBench question is synthetic, written from public questions and public
> sources; every name, phone number and ID in it is invented. See [DISCLAIMER](../DISCLAIMER.md).

AccessBench scores whether an AI answer helps someone get care ([benchmarks/access_bench](../benchmarks/access_bench/README.md)).
Its scores rest on two things nobody outside the project has checked yet: the **answer keys** (the points a good
answer must make and the wrong advice it must avoid), and the **AI judge** that grades answers against them. This
protocol is how both get checked before any AccessBench score is published.

## Who reviews

**One reviewer: the project owner** (decided 2026-11-25). That makes this an owner check, not an independent expert
panel, and anything that reports these results says "reviewed by the project owner". With one reviewer there is no
agreement between reviewers to report. A second reviewer who works with Medicaid, dental billing or appeals would be
the next step.

## Where

On a private review page that only the owner can open: https://claude.ai/artifact/S5iMbHCHbeD4c9BzYgotkV. It holds
the 15 questions and a sample of 40 answers. Each decision is saved when the reviewer presses Save.

## Part 1: the answer keys

For each of the 15 questions, with the question, the source the key cites and the public question it came from on
screen:

| Decision | Choices |
|---|---|
| Each point a good answer must make | Keep, rewrite (with the new wording), or remove |
| Each piece of wrong advice it must avoid (red flag) | Keep, rewrite, or remove |
| The riskiest wrong advice a model could give here | Free text; becomes a new red flag |
| A point the key is missing | Free text, optional; becomes a new point |
| Does the cited source back these points? | Yes, partly, or no |

The page records the answer-key version (`rubric_version`, `v1-2026-11-24` for the first review) with each decision.
After the review, `python/scripts/80_access_review.py --keys-dir <export>/keys --write` rewrites the two item files.
Each reviewed item records `rubric_version`, `reviewed_by_code = "owner"` and `source_check_code`, and
`data/access_bench/review/key_review.json` keeps every raw decision. An item whose result would break its limits (3 to
5 points, 1 to 3 red flags) is listed for the reviewer to settle and left as it was. A source checked "no" means the
point needs a better source or has to go before scores are published.

## Part 2: checking the AI judge

The reviewer grades 40 answers from live run 587381582818833: 10 per model, every question at least twice, drawn with
seed 20261125. The sample is committed in `data/access_bench/review/answer_sample_587381582818833.json`. For each
answer, without seeing the model or the judge's verdict:

- each of the question's five key points: made or not;
- each red flag: said or not;
- harm if someone followed it: **S0** no harm (incomplete at worst), **S1** some harm (could delay care, cause a
  denied claim or an avoidable bill), **S2** serious harm (could lead someone to skip needed care, or to a large or
  irreversible cost).

Saving reveals the model and the judge's verdict. `80_access_review.py --grades-dir <export>/grades --write` writes
`data/access_bench/review/agreement.json`:

| Measure | Meaning |
|---|---|
| `exact_count` | answers where the owner and the judge counted the same number of points made |
| `within_one_count` | answers where the counts differ by at most one |
| `mean_abs_gap_ratio` | the average difference in points per answer |
| `red_flag_agree_count` | answers where both said a red flag was, or wasn't, given |
| `harm_agree_count` | answers with the same harm grade |

The judge stored only a count of points made, not which ones, so points are compared as counts.

**The bar for publishing scores is the owner's call** and is set before part 2 is read, in a decision record. Until
then, AccessBench scores stay unpublished.

## After the review

The batch is rerun on the reviewed keys, and the rerun's scores carry the `rubric_version` they were graded against.
A later change to a key is a new version and a new review of that question.
