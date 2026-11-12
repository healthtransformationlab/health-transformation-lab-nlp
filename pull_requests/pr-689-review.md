# PR 689 review: record the owner's check of the 12 core-split verdicts no person had seen (#688)

Reviewed against `.claude/review-rubric.md` and AGENTS.md.

| Check | Result |
|---|---|
| Branch `data/688-028-core-split-owner-check`, `Closes #688`; issue titled `028 AI10: ...` and labelled `action-item` | ok |
| No spec: it fills in a column the core split already has under spec 028 and changes no rule, metric or label. The 17 tasks are the same 17 (`test_the_core_split_is_exactly_the_tasks_the_screen_of_all_93_passes`) | ok |
| Test first: both tests of `test_core_split.py` failed on the old file (the columns, and `owner_check_date` missing) and pass with the new one | ok |
| The owner's answer is quoted as written ("All 12 agree"), with the time and what was on the screen when it was given | ok |
| The record does not overstate the check: the README says the owner read summaries and not the test code, saw the AI's verdict first, and is one person; it still says the split is not validated by people in the sense of SWE-bench Verified | ok |
| Counts recomputed from the two files: 30 in the first screen, 5 of them in the core split, 12 more now, so 42 checked and 51 not; none of the 51 passes the screen | ok |
| `agent_screen_all.csv` is unchanged, so `test_task_screen.py` (the 30 the owner checked) still holds; the README says the two files' `is_owner_checked` now differ and why | ok |
| Column name and type: `owner_check_date` holds a calendar date (AGENTS.md "SQL and data names") | ok |
| Synthetic only, no PHI; wording and organisation checks: `pytest -q tests/test_core_split.py tests/test_task_screen.py tests/test_wording.py tests/test_no_org_references.py tests/test_bench_order.py`, 48 passed | ok |
| Publishes nothing and starts no run: `core_split.csv` is not among the Kaggle dataset's files, and nothing in `kaggle/` reads it | ok |
| The short list in the chat gave each of the AI's reasons in one sentence, shortened by the session, not in the screen's own words; the fuller sheet sent earlier had the screen's own text | note |
| The sheet itself is not committed. It can be rebuilt from `agent_screen_all.csv` (the two ratings and their reasons) and the published tasks (titles, statements, test names) | note |

Nothing blocking.

## Notes

- The agreement was given a minute or two after the short list was posted, by an owner working from a phone. It is
  what the README calls it: a check of the AI's reading, in summary. A reader who wants a rating made independently
  of the AI's verdict does not have one for any of the 93 tasks.
- The paper's wording follows in the `gemma-developer-agent` repository (Section 6 "Task fairness" and Section 7
  "AI screens"): "12 of the core split's 17 ... have AI ratings only" is no longer so.
- If the core split is ever added to the Kaggle dataset, `owner_check_date` needs its description in
  `kaggle/dataset_docs.yaml` in that pull request.
