# PR #769 review: list every Kaggle column description for Kaggle's editor, and say why

Closes #694. Reviewed against `.claude/review-rubric.md` and AGENTS.md.

## Verdict
Nothing blocking in the code. It changes AGENTS.md, so it waits for the owner's "merge" (rule 6).

## Checks
- **Root cause:** the API drops the descriptions server-side (Kaggle/kaggle-cli#1207). The CLI does send them, in
  the metadata update and in each new version's upload request, and version 5 of `perio-bench-results`, published
  today, still reads 0.94. Nothing in this repository can make Kaggle keep them. So the fix is the route Kaggle does
  keep (its editor), made quick, plus the note that stops anyone chasing a gap here.
- **Test first:** `test_column_descriptions.py` failed before `kaggle/column_descriptions.py` existed. It checks every
  results column has a description and Kaggle's file name, that the task set lists its three CSVs without a full
  build, and that the page escapes text and has one Copy button per column.
- **No publish:** the script writes a local file and sends nothing.
- **Names:** files use `publish.kaggle_name` (#695), so the page matches Kaggle's file list.
- **AGENTS.md:** the added paragraph under "Publishing datasets" says where the descriptions go until the Kaggle issue
  closes, and how to redo them after a version that adds or renames a column.
