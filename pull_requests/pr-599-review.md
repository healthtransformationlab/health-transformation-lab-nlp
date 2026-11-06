# PR #599 review: 034 BUG2, the published descriptions give 223 review notes (#598)

Reviewed against `.claude/review-rubric.md` and AGENTS.md.

| Check | Result |
|---|---|
| Issue and branch | `Closes #598`; branch `docs/598-034-review-count` |
| Test first | `test_published_descriptions_give_the_review_sets_own_size` failed before the change |
| Fix | five entries in `kaggle/dataset_docs.yaml` and the Hugging Face results card: 240 → 223 review notes; "13 of the 240 notes can't be staged" → 17 of 223 (`ladder_by_stageable.csv`) |
| Publish build | `kaggle/publish.py` builds both datasets with every file (6 and 38) and column (95 and 373) described |
| Tests | dataset-docs and publish tests pass; the full suite passes here except `test_digests.py`, which needs the `pipeline_doctor` package this container lacks (CI installs it) |

Nothing blocking.
