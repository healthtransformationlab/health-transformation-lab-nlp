# Hugging Face: the PerioBench datasets and the organisation page

Everything here is published to [huggingface.co/healthtransformationlab](https://huggingface.co/healthtransformationlab)
by GitHub Actions, never from a laptop, so every version matches a commit (spec 025). Everything published is
synthetic and CC BY 4.0. The files are the same as on Kaggle: `huggingface/publish.py` takes them from
`kaggle/publish.py`'s lists and checks, so the two platforms can't drift.

## What's on Hugging Face

| On Hugging Face | What it is | Files here |
|---|---|---|
| Dataset [`perio-bench-notes`](https://huggingface.co/datasets/healthtransformationlab/perio-bench-notes) | 3,484 training and 240 test notes, labelled with periodontal status; a `train` and a `test` split in the viewer, plus the review key, visits and clinics as extra configs | `publish.py`, `cards/notes.md`, `notebooks/perio_bench_quickstart.ipynb` |
| Dataset [`perio-bench-results`](https://huggingface.co/datasets/healthtransformationlab/perio-bench-results) | Every method's answers on the 240 test notes; opens on the leaderboard | `publish.py`, `cards/results.md` |
| Organisation page (the `README` Space) | The lab's goal, the three benchmarks, where to start | `cards/org.md` |

The cards in `cards/` become the pages. Edit them here, not on huggingface.co, or the next version overwrites your
edit.

## One-time setup (owner)

1. huggingface.co → **Settings → Access tokens → Create new token → Fine-grained**.
   - Name: `perio-bench-publish`.
   - Under **Repositories permissions**, choose the **healthtransformationlab** organisation and tick
     **Write access to contents/settings of all repos**. Tick nothing else, and nothing for your personal
     repositories.
   - Expiry: 90 days at most.
2. Copy it once into the GitHub environment **`dev`** as the secret **`HF_PUBLISH_TOKEN`**. (A secret named
   `HF_TOKEN` there is used instead when `HF_PUBLISH_TOKEN` isn't set, if it has the same write access.) (repository Settings →
   Environments → dev → Add environment secret). Never paste it anywhere else.
3. Write its expiry date in `ops/secrets_register.yaml` ("Hugging Face publish token").
4. Optional: upload a logo on the organisation's **Settings** page; the card can't set it.

## Publishing

Actions → **Publish datasets (Kaggle and Hugging Face)** → Run workflow, with `platform` set to `both` or
`huggingface`. With `dataset` set to `both`, it also publishes the organisation page, and on Kaggle the quickstart
notebook.

- **The token is checked first.** If it is missing, isn't a Hugging Face token, or can't write to the
  organisation, the run stops before any work and names the secret it read (`HF_PUBLISH_TOKEN`, or `HF_TOKEN`
  when that isn't set). Spaces, a line break, quotes or a pasted `NAME=` in front are ignored; anything else is
  described (its length, and whether it looks like a secret's name), never printed.
- **Each run is one commit per dataset**, named after the repository commit.
- **Files dropped from the list are deleted** from the dataset.

Preview a build locally (no upload, no token):

```bash
python huggingface/publish.py --dataset notes --out build/hf-notes --commit "$(git rev-parse HEAD)"
```
