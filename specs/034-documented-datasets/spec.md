# Feature Specification: every published dataset and every table explains itself

**Feature Branch**: `034-documented-datasets`

**Created**: 2026-11-04

**Status**: draft; US1 first

**Input**: The owner's screenshots of our three Kaggle datasets show usability scores of 6.47, 6.47 and 5.88. Kaggle
lists the same pending actions on each: upload an image, add file information, include column descriptors. No
Unity Catalog table or column has a comment either. The descriptions mostly exist already, in
`diagrams/_build/gold_model.py`, the cards and the code; they never reach the platforms.

> Personal learning project; synthetic data only. Descriptions say what a file or column holds and how it was made,
> never more than the data shows.

## User stories

### US1 - Every Kaggle dataset describes its files and columns, with a cover, sources and update frequency (P1) #533
Each dataset we publish on Kaggle (`perio-bench-notes`, `perio-bench-results`,
`health-transformation-lab-coding-agent-tasks`) sends, on every publish and on a metadata-only run:
- a description of every file;
- a description of every column of every CSV and JSONL file;
- a cover image;
- its sources (how it was made, with the repository link);
- an expected update frequency.

The descriptions live in one committed dictionary, `kaggle/dataset_docs.yaml`. A test fails when a published file
or column has none. AGENTS.md makes this the rule for any dataset published from this repository.

### US2 - Every Unity Catalog table the jobs write has a table comment and column comments (P1) #534
Each writer applies the table's comment (its grain) and its column comments from the declarations in
`diagrams/_build/gold_model.py` (and `opendental_silver_model.py`) after every write, so an overwrite can't drop
them. Tables with no declared columns get at least a table comment. A test fails when a written table has no
declared comment.

## Out of scope
A public notebook for the task set (Kaggle counts one): issue #535. New data.

## Constitution check
Synthetic data only; no metric, label or scoring change. Test-first. Honest descriptions: a column's text says what
it holds, as the code makes it.
