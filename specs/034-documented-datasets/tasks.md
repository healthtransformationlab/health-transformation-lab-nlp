# Tasks: documented datasets

**Tests**: required (test-first).

## US1 - Every Kaggle dataset describes its files and columns #533
- [x] T001 Failing tests: every published file and column has a description; the builds carry resources, sources, frequency and the cover; metadata-only sends no data
- [x] T002 `kaggle/dataset_docs.yaml` and `kaggle/dataset_docs.py`
- [x] T003 Covers: `kaggle/make_covers.py`, `kaggle/covers/*.png`
- [x] T004 `publish.py`, `publish_tasks.py`: send the metadata after each upload; `--metadata-only`; workflow inputs
- [x] T005 AGENTS.md: the rule for published datasets
- [ ] T006 Run the metadata-only updates and record the new scores

## US2 - Every Unity Catalog table has a table comment and column comments #534
- [x] T007 Failing tests, then `table_comments.apply` after every write (delta helpers; notebooks 01, 07, 10, 11, 12), `apply_all` in Load results after each deploy, and the LLM judge SQL's own table comment
