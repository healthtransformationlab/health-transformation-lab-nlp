---
pr: 697
branch: chore/696-028-tasks-apache-option
title: "028 CHORE5: offer the task set under CC BY 4.0 or Apache 2.0"
author: jcbowyer
reviewed_at: 2026-11-12
reviewer: coordinator review of the diff against the rubric (no reviewer subagent: one sentence of a card, a decision record and one assertion, read line by line)
verdict: approve
---

# PR Review: 028 CHORE5: offer the task set under CC BY 4.0 or Apache 2.0 (#696)

Reviewed against `.claude/review-rubric.md` and AGENTS.md. Range: `1c724ac..ece1928`.

## Summary

The task set's card now offers its own material under CC BY 4.0 or, at the user's choice, the Apache License 2.0.
The competition it was entered in names Apache 2.0 as the licence type for winners; the owner chose to offer both
and keep Kaggle's licence field, and the paper's wording, at CC BY 4.0. ADR 0004 records the choice.

## Scans

| Scan | Result |
|---|---|
| Secrets | none in the diff |
| PHI or real data | none; no data file changes |
| Organisation claims | the competition's rule is quoted from its own rules page, with the date it was read; `test_no_org_references.py` passes |

## Checks

| Check | Result |
|---|---|
| Branch `chore/696-028-tasks-apache-option`, `Closes #696`; one sentence of a card, a decision record and a test, so no spec | ok |
| A licence is the owner's to choose. The owner was shown the rule's text and three choices on November 12, 2026 and picked "Offer both". A pull request that publishes outside the repository waits for the owner's word (AGENTS.md "Branches and issues", 6): given, for the card and for sending it | ok |
| The rule is quoted as Kaggle returns it for the Paper Track ("WINNER LICENSE TYPE Open Source Apache 2.0"; the winner-licence clause; the exemption for input data under an incompatible licence), not from memory | ok |
| The grant covers only what the owner can license: the task rows, graphs, embeddings and the card. The card keeps saying that the repository's own files inside the snapshots are MIT, as at those commits, and that third-party files keep their own licences (MACCROBAT, CC BY 4.0; the icon set, MIT) | ok |
| Kaggle's licence field is unchanged (`CC-BY-4.0` in `publish_tasks._meta`, still asserted by the test), so the paper's "Tasks (CC BY 4.0)" is true as submitted | ok |
| Decision and action item kept apart: the choice is ADR 0004 in the template's four parts, indexed in `docs/adr/README.md`; the issue is closed by this pull request | ok |
| Test first: the new assertion in `test_the_built_folder_holds_exactly_the_set_and_a_cc_by_card` failed on the card as it was and passes now | ok |
| "Publishing datasets": the card still says what the data is and how it was made, that it is not affiliated, and names the third-party files with their licences; nothing in it holds a `<` (#692's check passes) | ok |
| `pytest -q tests/test_kaggle_publish_tasks.py tests/test_kaggle_dataset_docs.py tests/test_wording.py tests/test_no_org_references.py tests/test_bench_order.py`: 86 passed | ok |
| Python and R parity, seeds, paths, prices, deck figures, secrets register, alerts, table writes, settings: not touched | n/a |
| Environments: none on merge. The card reaches Kaggle by a metadata-only run from `main` afterwards (no new version); what Kaggle then holds is read back | note |

Nothing blocking.

## Notes
- This is not legal advice and the review does not treat it as such: it checks that the card says what the owner
  chose, and that it claims no right over files the owner does not hold.
- The paper is not changed. It names CC BY 4.0, which stays one of the two licences on offer.
- AGENTS.md "Publishing datasets" still gives CC BY 4.0 as the default for a dataset. ADR 0004 says when to
  revisit that.
