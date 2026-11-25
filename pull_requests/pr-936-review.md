# PR 936 review: answers score higher for specific, correct resources, and their links are checked

Closes #935. Range: `origin/main..feat/935-043-resource-scoring`. Files: `access_resources.py` (new),
`access_keypoint_judge.py` (prompt v2), `access_batch.py`, `access_review.py`, both item validators, `gold_names.py`,
`gold_model.py` with the rebuilt diagrams and regenerated contract, `scripts/81_external_review_prompt.py` (new),
`benchmarks/access_bench/prompts/external_review.md` (new), `docs/access_review_protocol.md`, the tests, and
`specs/043-access-llm-batch/` (US8).

Reviewed by the agent session that wrote it. Read it knowing that.

## Scans

- **Secrets:** none. The link check sends one HEAD (or GET) per link with a plain user agent, and no credentials.
- **Real data:** none.
- **Claims:** no score is published. The external review prompt says that a model's reply is a suggestion, and tells
  the model never to invent a link or number.

## Findings (verified)

1. **A refused robot isn't a broken link:** 401, 403 and 429 count as unchecked, and so do timeouts. Only 4xx/5xx
   otherwise, or a host that doesn't exist, counts as broken. That way a bot-blocking agency site doesn't mark a
   correct answer as inventing a contact.
2. **Backward compatible:** a v1 verdict (no `resource_level`) still parses, leaving the new fields null. The new
   gold columns are added with `mergeSchema`, so old rows read null. Simulated runs leave the level null and check no
   links.
3. **Contracts are generated:** the first hand edit of the ODCS file failed `test_data_contracts`. It was
   regenerated with `scripts/73_build_contracts.py`.
4. **ChatGPT's review (2026-11-25) arrived during this work.** It proposes a 0–4 resource scale that adds fit and a
   fallback, validation beyond "the link opens", and separate scores for models with and without internet access.
   This PR keeps the owner's 0–3 scale. Those points are in the review spreadsheet's comparison tab for the owner to
   decide, and the protocol notes them.

## Checks

- 17 test files covering the AccessBench modules, gold model, contracts, diagrams, telemetry and wording: 234 passed.
  The new tests failed before the code.

## Verdict

Approve, merging once CI is green. Nothing runs and nothing is published; the next live run uses judge v2.
