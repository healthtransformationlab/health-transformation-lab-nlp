"""Check spec 028's task set against the Gemma 4 Developer Agent competition's own files (#439).

    python scripts/56_competition_check.py --out /tmp/competition    # list, download the small files, report

Lists the competition's files through the Kaggle API, downloads only what competition_check.select_files picks
(the harness guide, docker/, sandbox/, sample_submission/, any swegemma / adk-* wheel, and the smallest snapshot
with its graph and embedding), and prints MATCHES / DIFFERS / FOUND lines against the formats task_graph writes,
plus where the harness installs swegemma. Run by .github/workflows/kaggle-competition-check.yml; keeps nothing.

Needs KAGGLE_USERNAME and KAGGLE_API_TOKEN (or KAGGLE_KEY), and the account must have joined the competition
(Kaggle -> the competition -> Join Competition), or the listing is refused.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from health_transformation_lab_nlp import competition_check as cc
from health_transformation_lab_nlp import telemetry


def check_settings() -> None:
    """Fail at once, naming the setting, before any network call (AGENTS.md, configuration)."""
    missing = [n for n, ok in (("KAGGLE_USERNAME", os.environ.get("KAGGLE_USERNAME")),
                               ("KAGGLE_API_TOKEN or KAGGLE_KEY",
                                os.environ.get("KAGGLE_API_TOKEN") or os.environ.get("KAGGLE_KEY"))) if not ok]
    if missing:
        sys.exit(f"missing setting(s): {', '.join(missing)} (GitHub environment dev)")


def list_files(api) -> list[tuple[str, int]]:
    """Every competition file as (name, bytes), following page tokens."""
    out, token = [], None
    while True:
        r = api.competition_list_files(cc.COMPETITION, page_token=token, page_size=200)
        for f in getattr(r, "files", None) or []:
            size = getattr(f, "total_bytes", None) or getattr(f, "totalBytes", None) or 0
            out.append((f.name if hasattr(f, "name") else str(f), int(size)))
        token = getattr(r, "next_page_token", None) or getattr(r, "nextPageToken", None)
        if not token:
            return out


def download(api, name: str, out: Path) -> Path:
    """One file to out/<name>: the client keeps the folder layout, and unzip=True undoes the zip Kaggle wraps large
    files in (kaggle 2.2.5, _resolve_download_path)."""
    out.mkdir(parents=True, exist_ok=True)
    api.competition_download_file(cc.COMPETITION, name, path=str(out), quiet=True, unzip=True)
    return out / name


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, required=True, help="scratch folder for the downloads")
    a = ap.parse_args()
    check_settings()
    telemetry.setup()
    telemetry.start_script("56_competition_check", data_label="public")
    from kaggle.api.kaggle_api_extended import KaggleApi  # needs the credentials, checked above

    api = KaggleApi()
    api.authenticate()
    try:
        listing = list_files(api)
    except Exception as e:  # noqa: BLE001 - the one cheap authenticated call; its error names the fix
        sys.exit(f"Kaggle refused the file listing for {cc.COMPETITION} ({type(e).__name__}: {str(e)[:200]}). "
                 "Join the competition with the account behind KAGGLE_API_TOKEN (accept its rules) and rerun.")
    total = sum(s for _, s in listing)
    print(f"{len(listing)} files, {total / 1e9:.2f} GB in {cc.COMPETITION}")
    for folder in sorted({n.split("/")[0] for n, _ in listing if "/" in n}):
        rows = [(n, s) for n, s in listing if n.startswith(folder + "/")]
        print(f"  {folder}/: {len(rows)} files, {sum(s for _, s in rows) / 1e6:.0f} MB")

    picked = cc.select_files(listing)
    print(f"downloading {len(picked)} files, {sum(s for n, s in listing if n in picked) / 1e6:.0f} MB")
    paths = {n: download(api, n, a.out) for n in picked}

    theirs = {"harness_wheels": [n for n in picked if n.startswith("wheels/")]}
    for n, p in paths.items():
        if n.startswith("snapshots/") and p.exists():
            theirs["snapshot"] = cc.snapshot_layout(p)
        elif n.startswith("graphs/") and p.exists():
            theirs["graph"] = cc.graph_summary(p)
        elif n.startswith("embeddings/") and p.exists():
            theirs["embedding"] = cc.embedding_summary(p)
    print("\n== compared with spec 028's formats")
    for line in cc.compare_with_ours(theirs):
        print(line)
    print("\n== how the harness gets swegemma (docker/, sandbox/, HARNESS_README.md lines naming it)")
    for n, p in paths.items():
        if p.exists() and (n.startswith(("docker/", "sandbox/")) or n == "HARNESS_README.md") and p.stat().st_size < 2e6:
            for i, line in enumerate(p.read_text(errors="replace").splitlines(), 1):
                if "swegemma" in line.lower() and ("pip" in line.lower() or "install" in line.lower()
                                                   or "COPY" in line or "wheel" in line.lower()):
                    print(f"  {n}:{i}: {line.strip()[:200]}")
    print("\n== sample_submission/")
    for n in picked:
        if n.startswith("sample_submission/"):
            print(f"  {n}")
    telemetry.end_script()
    return 0


if __name__ == "__main__":
    sys.exit(main())
