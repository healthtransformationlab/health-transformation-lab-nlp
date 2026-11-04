# Plan: documented datasets

## US1 (Kaggle)
- `kaggle/dataset_docs.yaml`: per dataset its sources, update frequency, cover and file descriptions (glob patterns);
  one shared column dictionary, plus per-file descriptions for columns named after methods or statuses.
- `kaggle/dataset_docs.py`: `resources(slug, files)` builds Kaggle's `resources` (path, description, schema fields)
  and `missing(slug, files)` lists what has no description. CSV columns come from the header, JSONL columns from
  the first row's keys.
- `kaggle/covers/<slug>.png`, drawn by `kaggle/make_covers.py` (seeded, Pillow), 1120 x 560.
- `kaggle/publish.py` and `kaggle/publish_tasks.py`: the metadata carries `resources`, `userSpecifiedSources` and
  `expectedUpdateFrequency`. A second folder holds the metadata and `dataset-cover-image.png`, so the image is never
  uploaded as data. After each upload, `api.dataset_metadata_update` sends them. `--metadata-only` sends only the
  metadata. For the task set it lists the files from Kaggle, since they are built in CI and git-ignored.
- Both publish workflows take a `metadata_only` input.
- Tests: every published file and column is described, the builds carry the new fields, and the metadata-only path
  never uploads data.

## US2 (Unity Catalog)
After every write, `table_comments.apply(spark, table)` runs `COMMENT ON TABLE` and `ALTER TABLE ... ALTER COLUMN ...
COMMENT` from the declarations (the delta helpers and each `saveAsTable` site call it); Load results runs
`apply_all` after every deploy. A failure warns and never fails the write.
