# PR 934 review: the owner's review of the AccessBench answer keys comes back into the repo

Closes #933. Range: `origin/main..feat/933-043-access-review`. Files: `python/health_transformation_lab_nlp/access_review.py`
(new), `python/scripts/80_access_review.py` (new), `python/tests/test_access_review.py` (new),
`docs/access_review_protocol.md` (new), `data/access_bench/review/answer_sample_587381582818833.json` (new),
`benchmarks/access_bench/README.md` (a link), `specs/043-access-llm-batch/` (US7).

Reviewed by the agent session that wrote it. Read it knowing that.

## Scans

- **Secrets:** none.
- **Real data:** none. The answer sample is 40 model answers to synthetic questions; the five privacy questions'
  planted names and numbers are invented, as in the item files.
- **Claims:** no score is published. The protocol says the review is an owner check by one reviewer, not an expert
  panel, and that the publishing bar is the owner's call, recorded in a decision record before part 2 is read.

## Findings (verified)

1. **Limits:** a review can push an item outside its 3–5 points or 1–3 red flags. The five privacy items already
   have three red flags, so a new riskiest-wrong-advice flag would break them. `apply_key_review` raises naming the
   item, and the script lists it for the owner and leaves it unchanged rather than failing the whole import.
2. **The judge stored only a count of points covered**, so agreement compares counts, not individual points. The
   protocol says so. Recording the judge's per-point verdicts would be a later change to `access_batch`.
3. **The import is idempotent:** `--write` rewrites the item files from the export each time, and a dry run changes
   nothing (tested).

4. **CI caught two things the targeted tests missed:**
   - `80_access_review.py` didn't set up telemetry (`test_telemetry_scripts`). It now calls `telemetry.setup()` and
     `start_script`.
   - The committed answer sample quoted a model saying "Diagnostic Tool" (`test_wording`). The sample now keeps
     each answer's ids, model, judge verdict and a SHA-256 of its text instead of the text, which agreement doesn't
     need. The full answers stay in the run's gold table. The wording check is unchanged.

## Checks

- `pytest tests/test_access_review.py tests/test_telemetry_calls.py tests/test_wording.py tests/test_no_org_references.py
  tests/test_bench_order.py tests/test_access_hard_items.py tests/test_access_phi_items.py tests/test_access_batch.py`:
  73 passed. The new tests failed (no module) before the code. After the CI fixes, `test_access_review.py`,
  `test_telemetry_scripts.py` and `test_wording.py`: 36 passed.

## Verdict

Approve, merging once CI is green. Nothing runs and nothing is published; the item files change only when the owner's
decisions are applied (T013).
