"""Build the folder `kaggle kernels push` sends: a notebook with its settings filled in, and kernel-metadata.json
(GPU and internet on; public, since it holds synthetic notes only and no token). Two jobs:

- medgemma (kaggle-medgemma.yml): the MedGemma reader, with MedGemma attached from Kaggle Models via
  model_sources. No Hugging Face token: a pushed notebook can't read Kaggle Secrets, so the rung's `kaggle:`
  model (models.yaml) is attached instead and kaggle/keras_to_hf.py converts it on Kaggle.
- encoders (kaggle-encoders.yml): the GPU encoders of spec 002 T017, the Databricks encoder_gpu job's work.
  Their weights are public on Hugging Face. Rungs and learning rates default to that job's (databricks.yml).
- quickstart (kaggle-publish.yml, spec 025): notebooks/perio_bench_quickstart.ipynb as is, attached to the
  two PerioBench datasets; no GPU, no internet.

    python kaggle/prepare_kernel.py --out build/kernel --username <kaggle user> [--rung ...] [--limit 10]
        [--shots 0] [--branch main] [--commit <sha>]
    python kaggle/prepare_kernel.py --job encoders --out build/kernel --username <kaggle user>
        [--rungs a,b] [--lr-overrides a=2e-5] [--epochs 3] [--max-len 256] [--limit 10] [--branch ...] [--commit ...]
        [--save-model modernbert-base+cw]

--limit 0 is the full run (FULL_RUN); any other number reads that many review notes as a test.
"""

import argparse
import json
import re
from pathlib import Path

import yaml
from keras_to_hf import kaggle_handle

HERE = Path(__file__).resolve().parent
JOBS = {   # notebook, slug, title: Kaggle derives the slug from the title, so keep them in step
    "medgemma": ("medgemma_reader.ipynb", "perio-bench-medgemma-reader", "perio bench medgemma reader"),
    "encoders": ("encoder_gpu.ipynb", "perio-bench-encoder-gpu", "perio bench encoder gpu"),
    # spec 025: the quickstart, as published; reads the two attached datasets, so no GPU and no internet
    "quickstart": ("../notebooks/perio_bench_quickstart.ipynb", "perio-bench-quickstart", "perio bench quickstart"),
}
QUICKSTART_DATASETS = ("perio-bench-notes", "perio-bench-results")


def bundle_default(name: str) -> str:
    """A databricks.yml variable's default: the Kaggle run uses the Databricks job's own settings."""
    return yaml.safe_load((HERE.parent / "databricks.yml").read_text())["variables"][name]["default"]


def settings(source: str, values: dict) -> str:
    """Rewrite the assignments in the notebook's settings cell; fail if one is missing."""
    for name, value in values.items():
        source, n = re.subn(rf"^{name} = [^#\n]*?(\s*(#.*)?)$", rf"{name} = {value}\1", source, flags=re.MULTILINE)
        if n != 1:
            raise SystemExit(f"settings cell has no single '{name} = ' line")
    return source


def quickstart(out: Path, username: str, notebook: str, slug: str, title: str) -> None:
    """The quickstart notebook unchanged, attached to both datasets (spec 025 US2)."""
    src = (HERE / notebook).resolve()
    out.mkdir(parents=True, exist_ok=True)
    (out / src.name).write_text(src.read_text())
    meta = {"id": f"{username}/{slug}", "title": title, "code_file": src.name, "language": "python",
            "kernel_type": "notebook", "is_private": False, "enable_gpu": False, "enable_tpu": False,
            "enable_internet": False, "dataset_sources": [f"{username}/{d}" for d in QUICKSTART_DATASETS],
            "competition_sources": [], "kernel_sources": [], "model_sources": []}
    (out / "kernel-metadata.json").write_text(json.dumps(meta, indent=1) + "\n")
    print(f"prepared {meta['id']}: the quickstart, attached to {', '.join(meta['dataset_sources'])}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--job", choices=sorted(JOBS), default="medgemma")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--username", required=True)
    ap.add_argument("--limit", type=int, default=10)
    ap.add_argument("--branch", default="main")
    ap.add_argument("--commit", default="", help="check out this commit of --branch (empty: its tip)")
    ap.add_argument("--rung", default="medgemma-1.5-4b-it", help="medgemma")
    ap.add_argument("--shots", type=int, default=0, help="medgemma")
    ap.add_argument("--rungs", default=None, help="encoders, comma-separated (default: databricks.yml)")
    ap.add_argument("--lr-overrides", default=None, help="encoders, rung=rate (default: databricks.yml)")
    ap.add_argument("--epochs", type=int, default=3, help="encoders")
    ap.add_argument("--max-len", type=int, default=256, help="encoders")
    ap.add_argument("--save-model", default="", help="encoders: the rung whose fine-tuned weights to keep (spec 020 US3)")
    a = ap.parse_args()
    notebook, slug, title = JOBS[a.job]
    if a.job == "quickstart":
        return quickstart(a.out, a.username, notebook, slug, title)

    values = {"BRANCH": json.dumps(a.branch), "COMMIT": json.dumps(a.commit), "TEST_NOTES": str(a.limit or 10),
              "FULL_RUN": str(a.limit == 0)}
    if a.job == "medgemma":
        model = kaggle_handle(a.rung)
        values |= {"RUNG": json.dumps(a.rung), "SHOTS": str(a.shots)}
        models, what = [model], f"rung={a.rung} ({model}) shots={a.shots}"
    else:
        rungs = a.rungs or bundle_default("encoder_gpu_rungs")
        lrs = bundle_default("encoder_gpu_lr") if a.lr_overrides is None else a.lr_overrides
        values |= {"RUNGS": json.dumps(rungs), "LR_OVERRIDES": json.dumps(lrs), "EPOCHS": str(a.epochs),
                   "MAX_LEN": str(a.max_len), "SAVE_MODEL": json.dumps(a.save_model)}
        models, what = [], (f"rungs={rungs} lr={lrs or 'default'} epochs={a.epochs}"
                            + (f" keeping {a.save_model}" if a.save_model else ""))

    nb = json.loads((HERE / notebook).read_text())
    cell = next(c for c in nb["cells"] if c["cell_type"] == "code" and "BRANCH =" in "".join(c["source"]))
    cell["source"] = settings("".join(cell["source"]), values).splitlines(keepends=True)
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / notebook).write_text(json.dumps(nb, indent=1) + "\n")
    meta = {"id": f"{a.username}/{slug}", "title": title, "code_file": notebook,
            "language": "python", "kernel_type": "notebook", "is_private": False, "enable_gpu": True,
            "enable_tpu": False, "enable_internet": True, "dataset_sources": [], "competition_sources": [],
            "kernel_sources": [], "model_sources": models}
    (a.out / "kernel-metadata.json").write_text(json.dumps(meta, indent=1) + "\n")
    print(f"prepared {meta['id']}: {what} "
          f"{'all review notes' if a.limit == 0 else f'{a.limit} notes'} from branch {a.branch}"
          f"{f' at {a.commit[:12]}' if a.commit else ''}")


if __name__ == "__main__":
    main()
