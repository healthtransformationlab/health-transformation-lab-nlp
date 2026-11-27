# Does AccessBench measure what it claims to?

Personal learning project, not affiliated. AccessBench claims to measure **whether an AI answer helps a person get
dental care**: makes the points a good answer needs, gives a usable next step, sends them to the right place, and says
nothing that could cost them money, time or care. This page checks that claim against three questions that should be
answered before any benchmark is trusted, with what is done, the evidence, and what is still missing (045 DOCS1, #981).
The licence and the field-by-field data dictionary are beside the data:
[LICENSE.md](../benchmarks/access_bench/LICENSE.md), [data_dictionary.md](../benchmarks/access_bench/data_dictionary.md).

## Summary

| Check | Status | Biggest gap |
|---|---|---|
| Licence | Done: CC BY 4.0 for questions, keys and controls; sources and why they may be used are listed | None known |
| Data dictionary | Done: every field in every file, enforced by a test | None known |
| What counts as the right answer | Partly: keys from cited official sources, reviewed by five AI models | The owner's review of the keys hasn't happened; the veterans set's sources are unopened |
| Can it be graded consistently | Partly: per-point verdicts with quotes, defined harm, 15 control answers, repeat passes | No human has graded answers, so agreement between the judge and a person is unmeasured |
| Could it be in training data | Low today, rising: the questions are new, but public | No private held-out set yet |

## What counts as the right answer?

**Why it matters:** a benchmark scores agreement with its answer key. If the key is wrong, incomplete or arguable, a
high score means "agrees with us", not "helps the person".

What is done:

- **Each key is a short list of things a good answer does** (3 to 5 points), plus 1 to 3 things it must not do. Points
  are positive actions or facts; "does not" points were removed from scoring because 30 of the first 75 points only
  checked that an error was absent ([external reviews](access_bench_external_reviews.md)).
- **Every point traces to a source**, named in `evidence_source` with the date it was checked, with a `jurisdiction_code`
  and a `recheck_date`, because Medicaid, VA and plan rules change.
- **Only a fully made point counts.** The judge marks each point met, partial, missing or contradicted and quotes the
  words that earn it; partial counts as missing.
- **Harm has a written definition** ([ADR 0015](adr/0015-accessbench-harm-is-what-an-answer-says.md)): what the answer
  says or recommends, graded S0, S1 or S2; leaving something out is scored as a missed point, not as harm, except no
  urgent-care advice when the question describes urgent symptoms.
- **Five AI models reviewed the keys** (ChatGPT, Gemini, Copilot, Perplexity, Grok) and the consolidated fixes went in
  (spec 045 US5). Their views are suggestions, and every resource they named was checked before it entered a key.

What is missing, and why it matters:

- **No person has reviewed the keys yet.** The owner review is designed ([review protocol](access_review_protocol.md))
  but not done: no question carries `rubric_version` or `reviewed_by_code`. Until it is, scores stay labelled
  preliminary. An independent reviewer who works with Medicaid, dental billing or appeals would be the stronger check.
- **The veterans' questions are drafted from unopened sources** (`source_verified_date` null), because the VA and eCFR
  pages couldn't be reached from the drafting session. They are not scored for a published result until checked.
- **Some questions have more than one good answer** (a dental school or a health center; an appeal or a second
  opinion). Keys name the alternatives in one point where they are interchangeable, so an answer isn't marked down for
  choosing a different good route.

## Can it be graded consistently?

**Why it matters:** if the same answer gets different grades on different runs, or a grader can't tell a harmful
answer from a helpful one, differences between models are noise.

What is done, with evidence:

- **The same answer gets the same grade.** Ten control answers graded three times each by the current judge gave the
  same harm grade on almost every pass ([judge controls record](../data/access_bench/runs/judge_controls_2026-11-26.md)).
- **The grader is tested against answers with known grades.** 15 control answers, written to be clearly serious harm,
  clearly some harm, nearly right, polished but empty, and good, are graded alongside every run (`is_control_match`).
  Five were written after the last prompt change, so the prompt wasn't fitted to them.
- **The grader was changed when it failed that test.** The first judge graded incomplete answers as harm (6 of 10
  controls as expected). With the harm rule tightened and a reasoning judge, 12 of 15 were graded as expected, against
  8 of 15 for the same judge with the old rule (ADR 0015; one pass each, so a check of the mechanism, not a validation).
- **Each grade can be checked.** Every point verdict quotes the answer's own words, stored with the answer and shown
  per answer in the MLflow evaluation view. The harm grade quotes its words too (`harm_span`), though that quote is
  not yet stored in the gold table.
- **A grade that fails to parse is not a grade.** It is recorded as an error, never as "no harm" (#953).

What is missing:

- **Agreement between the judge and a person is unmeasured.** No human has graded a sample of answers, so there is no
  agreement figure (kappa) to report. The review page holds 40 answers from run 587381582818833 for the owner to grade
  ([review protocol](access_review_protocol.md), part 2); with two reviewers, agreement between people could be
  reported too.
- **One judge model.** A second judge from another model family would show whether grades depend on the grader.

## Could it already be in a model's training data?

**Why it matters:** a model that has seen the questions and their keys can score well by recall, not by helping.

Where AccessBench stands:

- **The questions are new.** They were written from November 21, 2026, after the models tested so far were released,
  so those models cannot have trained on them.
- **The situations may be familiar, the keys are not.** Nine questions were prompted by public Reddit threads that may
  be in training data. Each is rewritten, and the graded points come from official sources, not from replies in the
  thread, so recalling a thread doesn't hand a model the key.
- **The rules change, which works against recall.** 30 of 30 questions are marked `knowledge_cutoff_sensitive`: the
  right answer depends on current rules, so an answer recalled from old pages can be scored wrong.

What is done to keep it that way:

- **A canary on every row.** Every question and control answer carries `canary_text`, the AccessBench GUID with the
  standard "should never appear in training corpora" line, so corpus builders can filter the files, and a model that
  can complete the GUID has probably seen them.

What is missing:

- **The questions are public in this repository**, so models released later may have trained on them. The fix is a
  **private held-out set**: new questions kept out of the public repository, used for scored rounds, with the public
  set kept for development and examples. That is a decision for the owner (where the private set lives, who can see
  it), filed as an action item (#982).
- **A contamination probe** (ask each model to complete the canary GUID, before its answers are scored) is cheap and
  should be added to each live run (#983).
