# PR 273 review: name Databricks for Good in the pitch deck

Closes #272. Reviewed against `.claude/review-rubric.md` and AGENTS.md.

| Check | Result |
|---|---|
| Not affiliated: company described only as its public source describes it, with a citation | Pass: Databricks' own description is quoted, and the source is in the footer |
| No overclaim | Pass: it is called a "candidate, not yet contacted", and the notes say eligibility hasn't been checked |
| No organization references | Pass (`test_no_org_references.py`) |
| Wording ("diagnose" ban) | Pass (`test_wording.py`) |
| Benchmark names, not "the lab" | Pass (`test_decks.py`) |
| Generated decks rebuilt | Pass: `deck.html` and `full_text_and_notes.md` are regenerated |
| Layout | Pass: the ask slide ends at 920 px and the pilot slide at 914 px, both inside 1080 |

Tests: 114 passed. No data, metric or label changes, so no spec is needed.

Verdict: ready to merge once CI is green.
