"""Build a Hugging Face dataset folder from spec 020's file lists and, with --upload, publish it under the
healthtransformationlab organisation (spec 025). Used by .github/workflows/kaggle-publish.yml; CC BY 4.0.

    python huggingface/publish.py --dataset notes|results --out build/hf-notes --commit <sha>
        [--upload --message "Update from the repository"]
    python huggingface/publish.py --org-card --out build/hf-org --commit <sha> [--upload]

The files are kaggle/publish.py's (FR-001: one list for both platforms), passed through its check() and copied
under raw/. The notes also get data/train.csv and data/test.csv with one column set, so the dataset viewer and
load_dataset() show a train and a test split. README.md is the card: a YAML header (licence, task, tags, configs)
and the body from huggingface/cards/<name>.md. Uploading needs HF_PUBLISH_TOKEN, or the workflow passes HF_TOKEN in its place (a token with write
access to the organisation's repositories); check_token() checks it before any upload.
"""

import argparse
import importlib.util
import os
import re
import shutil
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
REPO = HERE.parent
ORG = "healthtransformationlab"
_spec = importlib.util.spec_from_file_location("kaggle_publish", REPO / "kaggle" / "publish.py")
kpub = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(kpub)

QUICKSTART = REPO / "notebooks" / "perio_bench_quickstart.ipynb"
# Columns both splits share: the note, its labels, what the clinician wrote, and the X-ray reading.
SPLIT_COLUMNS = ["visit_id", "person_id", "note_text", "label", "grade", "extent", "stated_status", "rad_present",
                 "rad_max_rbl_pct", "rad_mean_rbl_pct", "rad_share_teeth_rbl15", "rad_vertical_defects",
                 "rad_furcations", "rad_calculus_teeth", "rad_missing_teeth", "rad_is_bwx"]
HEADERS = {
    "notes": {"pretty_name": "PerioBench notes: synthetic dental notes labelled with periodontal status",
              "task_categories": ["text-classification"], "size_categories": ["1K<n<10K"],
              "configs": [{"config_name": "notes", "default": True,
                           "data_files": [{"split": "train", "path": "data/train.csv"},
                                          {"split": "test", "path": "data/test.csv"}]},
                          {"config_name": "review_key", "data_files": "raw/review_key.csv"},
                          {"config_name": "visits", "data_files": "raw/visits_structured.csv"},
                          {"config_name": "visits_truth", "data_files": "raw/visits_truth.csv"},
                          {"config_name": "clinics", "data_files": "raw/clinic_profiles.csv"}]},
    "results": {"pretty_name": "PerioBench results: what rules, encoders and LLMs answered on 240 review notes",
                "task_categories": ["text-classification"], "size_categories": ["1K<n<10K"],
                "configs": [{"config_name": "leaderboard", "default": True,
                             "data_files": "raw/ladder/ladder_vs_truth.csv"},
                            {"config_name": "predictions", "data_files": "raw/ladder/ladder_preds.csv"},
                            {"config_name": "probabilities", "data_files": "raw/ladder/ladder_proba.csv"},
                            {"config_name": "llm_details", "data_files": "raw/llm_details_*.csv"},
                            {"config_name": "judge_metrics", "data_files": "raw/judge/judge_metrics.csv"}]},
}
TAGS = ["synthetic", "dental", "periodontitis", "periodontal-disease", "clinical-nlp", "medical", "omop", "benchmark"]


def repo_id(name: str) -> str:
    return f"{ORG}/{kpub.DATASETS[name]['slug']}"


def splits(raw: Path, out: Path) -> None:
    """data/train.csv and data/test.csv (the 240 review notes) with the same columns."""
    import pandas as pd
    train = pd.read_csv(raw / "train.csv")
    test = pd.read_csv(raw / "review_key.csv").rename(
        columns={"truth_status": "label", "truth_grade": "grade", "truth_extent": "extent"})
    (out / "data").mkdir(parents=True, exist_ok=True)
    train[SPLIT_COLUMNS].to_csv(out / "data" / "train.csv", index=False)
    test[SPLIT_COLUMNS].to_csv(out / "data" / "test.csv", index=False)


def card(name: str, out: Path, commit: str) -> str:
    head = {"license": "cc-by-4.0", "language": ["en"], "tags": TAGS, **HEADERS[name]}
    files = sorted(p.relative_to(out).as_posix() for p in out.rglob("*") if p.is_file() and p.name != "README.md")
    table = "\n".join(f"| `{f}` | {kpub._rows(out / f) if f.endswith(('.csv', '.json')) else 'notebook'} |"
                      for f in files)
    body = (HERE / "cards" / f"{name}.md").read_text(encoding="utf-8").rstrip()
    return ("---\n" + yaml.safe_dump(head, sort_keys=False, allow_unicode=True) + "---\n\n" + body
            + "\n\n## Contents\n\n| File | Size |\n|---|---|\n" + table
            + f"\n\nPublished from commit `{commit}` of the repository.\n")


def build(name: str, out: Path, commit: str) -> Path:
    kpub.check(name)                                  # same refusals as Kaggle: simulated, partial, sim:/calib:
    if out.exists():
        shutil.rmtree(out)
    for dest, src in kpub.files_of(name).items():
        (out / "raw" / dest).parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(src, out / "raw" / dest)
    if name == "notes":
        splits(out / "raw", out)
        shutil.copyfile(QUICKSTART, out / QUICKSTART.name)
    (out / "README.md").write_text(card(name, out, commit), encoding="utf-8")
    return out


def org_card() -> str:
    head = {"title": "Health Transformation Lab", "emoji": "🦷", "colorFrom": "blue", "colorTo": "green",
            "sdk": "static", "pinned": False}
    return "---\n" + yaml.safe_dump(head, sort_keys=False, allow_unicode=True) + "---\n\n" + \
        (HERE / "cards" / "org.md").read_text(encoding="utf-8")


NAME_PREFIX = re.compile(r"^(export\s+)?[A-Za-z_][A-Za-z0-9_]*\s*=\s*")   # a NAME=value line pasted whole


def clean_token(raw: str) -> str:
    """The token without the usual paste mistakes: whitespace or a line break, quotes, a NAME= prefix (issue #255)."""
    token = NAME_PREFIX.sub("", raw.strip().strip("'\"").strip())   # quotes may wrap the token or the whole line
    return token.strip().strip("'\"").strip()


def describe_token(token: str) -> str:
    """What a token that isn't hf_... looks like, without any of its characters, so a log can say what went wrong."""
    shape = f"{len(token)} characters"
    if re.fullmatch(r"[A-Z][A-Z0-9_]*", token):
        return shape + ", all capitals: that looks like a secret's name, not its value"
    if token.lower().startswith("bearer "):
        return shape + ", starting with 'Bearer ': paste the token alone"
    return shape + ", not starting with hf_: is it a Hugging Face access token?"


def check_token(token: str, whoami, source: str = "HF_PUBLISH_TOKEN or HF_TOKEN") -> str:
    """Fail fast, naming the setting: missing, wrong shape, or unable to write to the organisation. Returns the user.
    `source` names the secret the token came from; the workflow passes it as HF_TOKEN_SOURCE."""
    token = clean_token(token)
    if not token:
        raise SystemExit(f"{source} is not set in the GitHub environment 'dev' (huggingface/README.md)")
    if not token.startswith("hf_"):
        raise SystemExit(f"{source} doesn't look like a Hugging Face token (it should start with hf_): the value "
                         f"from {source} is {describe_token(token)} (huggingface/README.md)")
    me = whoami(token)                                # one cheap authenticated call
    role = next((o.get("roleInOrg") for o in me.get("orgs", []) if o.get("name") == ORG), None)
    fine = (me.get("auth") or {}).get("accessToken", {}).get("fineGrained")
    scoped = [s for s in (fine or {}).get("scoped", []) if s.get("entity", {}).get("name") == ORG]
    if role not in ("admin", "write", "contributor") or (fine and not any(
            any("write" in p for p in s.get("permissions", [])) for s in scoped)):
        raise SystemExit(f"{source} can't write to the {ORG} organisation: give it write access to the "
                         "organisation's repositories (huggingface/README.md)")
    return me["name"]


DELETE = ["*.csv", "*.json", "*.ipynb", "*.md"]   # our files only: a file dropped from the list goes; .gitattributes stays


def upload(folder: Path, repo: str, message: str, api, repo_type: str = "dataset", **create) -> str:
    """Create the repository public if needed, then upload the folder as one commit; files no longer listed go."""
    api.create_repo(repo_id=repo, repo_type=repo_type, private=False, exist_ok=True, **create)
    url = api.upload_folder(repo_id=repo, repo_type=repo_type, folder_path=str(folder), commit_message=message,
                            delete_patterns=DELETE)
    print(f"published {repo}: {url}")
    return str(url)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", choices=sorted(kpub.DATASETS))
    ap.add_argument("--org-card", action="store_true", help="the organisation page (the README Space)")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--commit", required=True)
    ap.add_argument("--upload", action="store_true", help="publish it (needs HF_PUBLISH_TOKEN)")
    ap.add_argument("--message", default="Update from the repository")
    a = ap.parse_args()
    if not (a.dataset or a.org_card):
        ap.error("give --dataset or --org-card")
    if a.org_card:
        if a.out.exists():
            shutil.rmtree(a.out)
        a.out.mkdir(parents=True)
        (a.out / "README.md").write_text(org_card(), encoding="utf-8")
        repo, kind, create = f"{ORG}/README", "space", {"space_sdk": "static"}
    else:
        build(a.dataset, a.out, a.commit)
        repo, kind, create = repo_id(a.dataset), "dataset", {}
    print(f"prepared {repo} at {a.commit[:12]}")
    if a.upload:
        from huggingface_hub import HfApi
        token = clean_token(os.environ.get("HF_PUBLISH_TOKEN", ""))
        api = HfApi(token=token or None)
        check_token(token, whoami=lambda t: api.whoami(token=t),
                    source=os.environ.get("HF_TOKEN_SOURCE") or "HF_PUBLISH_TOKEN or HF_TOKEN")
        upload(a.out, repo, f"{a.message} ({a.commit[:12]})", api, kind, **create)


if __name__ == "__main__":
    sys.exit(main())
