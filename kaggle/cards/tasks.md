# Coding-agent tasks from a data-pipeline repository

Software engineering tasks mined from the history of one open repository,
[health-transformation-lab-nlp](https://github.com/healthtransformationlab/health-transformation-lab-nlp) (Python
data pipelines, tests, Databricks jobs and docs for a synthetic dental-records benchmark). Each task is a real
change: the issue or pull-request text written at the time, the code patch, and the tests that went with it. The
files follow the Gemma 4 Developer Agent competition's dataset layout, so an agent built for that competition can
be run on a second kind of repository and the two compared.

This is a personal learning project, **not affiliated** with any employer, institution or company, nor with
Kaggle, Google or the competition's organisers. The tasks are code and text from the repository's public history,
**not for clinical use**. Its own data is synthetic, but each snapshot is the whole repository at that commit, so
most also carry the third-party files it keeps under `data/external/` (see the licence section).

## Verified with the competition's own evaluator

Every task here has been checked with the Gemma 4 Developer Agent competition's evaluator (`swegemma` 0.2.11, its
verification step in the subprocess sandbox): **it resolves the task's reference patch and does not resolve an
empty patch.** `swegemma_verification.csv` holds the verdict for every candidate, and `tasks_excluded.csv` names the
ones left out and why. Candidates were left out when their tests read files the snapshots withhold, when a test
starts a script that the evaluator's `PYTHONSAFEPATH=1` stops from importing a module beside it, or when a test
needs Postgres or R.

Each snapshot has one file its base commit did not: a root `conftest.py` that puts `python/` on the import path.
The evaluator puts the repository root there, and this repository's package is in `python/`; without the file every
test fails at import. Versions of this dataset before it was added (1 to 3) cannot be scored by the evaluator.

The evaluator verified the patches; it has not run an agent on these tasks. Its wheel comes from the Kaggle dataset
`metric/gemma-4-developer-agent-wheelhouse`.

## How it was made

`python/scripts/46_mine_tasks.py` lists every merged pull request and direct commit. `55_build_tasks.py` keeps
the changes that touch both code and `python/tests/`, writes each row and builds its snapshot, code graph and
embeddings. `57_gate_tasks.py` keeps only the tasks whose tests fail without the fix and pass with it, in our own check and in
the competition's evaluator (above).

- **Statements** are never rewritten. Each task carries a fidelity tier: A from the issue, B from the pull
  request, C from the commit message.
- **Snapshots** are the files at `base_commit` as a single commit in a fresh repository on `main`, so no later
  history comes along. Text naming one organisation the repository's rules forbid is replaced with `[org]`, and a
  task whose patch names it is left out. `data/external/maccrobat/course/` (a course's preprocessed files, received
  with no stated redistribution licence) is withheld from every snapshot, and the one task that added those files
  is left out; `withheld_paths` in the repository's `data/tasks/snapshot_index.csv` lists them.
- **Graphs and embeddings** are named as the competition's are: the repository's name, an underscore and the base
  commit. The graphs come from an AST walk of the package (NetworkX node-link JSON, `calls` edges). The embeddings
  give one 256-float vector per graph node, made with EmbeddingGemma (`google/embeddinggemma-300m`, cut from 768
  dimensions and renormalised).
  The competition doesn't name its embedding model, so similarity with its vectors is unverified.
- **Wheels are not included.** They are third-party packages under their own licences, and the competition's
  sandbox ships its own. `python scripts/55_build_tasks.py --wheels` downloads them for Python 3.13.

`tasks_excluded.csv` lists every candidate left out and why. `task_gates.csv` holds the gate result for each one.

## Licence and citation

The task rows, graphs, embeddings and this card are offered under CC BY 4.0 or, at your choice, under the Apache
License 2.0. Inside the snapshots, the repository's own files are under the MIT licence it carried at those commits
(the repository has been Apache 2.0 since November 2026), and third-party files keep their own licences, named in
the files beside them:

- `data/external/maccrobat/` (in most snapshots): MACCROBAT, 200 published, de-identified clinical case reports
  from PubMed Central. **Not synthetic.** CC BY 4.0, Caufield, J. Harry (2019), *MACCROBAT*, figshare,
  https://doi.org/10.6084/m9.figshare.9764942.v2. Its README lists the changes made. Its `course/` folder is
  withheld (above).
- `diagrams/_build/dbx_icons/`: an icon set under the MIT licence, with its own copyright in its `LICENSE`.

Please cite: Bowyer J., *health-transformation-lab-nlp*,
https://github.com/healthtransformationlab/health-transformation-lab-nlp.
