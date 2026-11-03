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

## How it was made

`python/scripts/46_mine_tasks.py` lists every merged pull request and direct commit. `55_build_tasks.py` keeps
the changes that touch both code and `python/tests/`, writes each row and builds its snapshot, code graph and
embeddings. `57_gate_tasks.py` keeps only the tasks whose tests fail without the fix and pass with it. That check
is our own, following the competition harness's documented verification in our Python 3.13 environment, not the
competition's sandbox (spec 028 in the repository).

- **Statements** are never rewritten. Each task carries a fidelity tier: A from the issue, B from the pull
  request, C from the commit message.
- **Snapshots** are the files at `base_commit` as a single commit in a fresh repository on `main`, so no later
  history comes along. Text naming one organisation the repository's rules forbid is replaced with `[org]`, and a
  task whose patch names it is left out.
- **Graphs and embeddings** are named `<repo name>_<base_commit>`, as the competition's are. The graphs come from
  an AST walk of the package (NetworkX node-link JSON, `calls` edges). The embeddings give one 256-float vector per
  graph node, made with EmbeddingGemma (`google/embeddinggemma-300m`, cut from 768 dimensions and renormalised).
  The competition doesn't name its embedding model, so similarity with its vectors is unverified.
- **Wheels are not included.** They are third-party packages under their own licences, and the competition's
  sandbox ships its own. `python scripts/55_build_tasks.py --wheels` downloads them for Python 3.13.

`tasks_excluded.csv` lists every candidate left out and why. `task_gates.csv` holds the gate result for each one.

## Licence and citation

CC BY 4.0 for the task rows, graphs, embeddings and this card. Inside the snapshots, the repository's own files
are under its MIT licence, and third-party files keep their own licences, named in the files beside them:

- `data/external/maccrobat/` (in most snapshots): MACCROBAT, 200 published, de-identified clinical case reports
  from PubMed Central. **Not synthetic.** CC BY 4.0, Caufield, J. Harry (2019), *MACCROBAT*, figshare,
  https://doi.org/10.6084/m9.figshare.9764942.v2. Its README lists the changes made.
- `diagrams/_build/dbx_icons/`: an icon set under the MIT licence, with its own copyright in its `LICENSE`.

Please cite: Bowyer J., *health-transformation-lab-nlp*,
https://github.com/healthtransformationlab/health-transformation-lab-nlp.
