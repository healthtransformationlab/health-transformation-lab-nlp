"""Data locations. Local by default; on Databricks set DENTAL_DATA_ROOT to a
Volume path (e.g. /Volumes/main/dental/data) and everything follows."""

from __future__ import annotations

import os
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_ROOT = Path(os.environ.get("DENTAL_DATA_ROOT", REPO_ROOT / "data"))

SYNTHEA_CSV = Path(os.environ.get("DENTAL_SYNTHEA_CSV", REPO_ROOT / "synthea" / "output" / "csv"))
OMOP_DIR = DATA_ROOT / "omop"          # one parquet per CDM table
LABELS_DIR = DATA_ROOT / "labels"      # labeled notes + split
RESULTS_DIR = DATA_ROOT / "results"    # scorer output, one file per run
SAMPLES_DIR = REPO_ROOT / "data" / "samples"
MODELS_YAML = REPO_ROOT / "models.yaml"

# Study (chart review) paths
DATASETS_DIR = REPO_ROOT / "data" / "datasets"   # committed: synthetic, de-identified
JUDGE_DIR = DATASETS_DIR / "judge"                # spec 012: judge scorecard (committed)
REVIEW_DIR = DATA_ROOT / "review"                # Label Studio exports + parsed labels
RAW_DIR = DATA_ROOT / "raw"                      # notes WITH (fake) PHI; never committed
CORPUS_DIR = DATA_ROOT / "corpus"                # corpus sample, predictions, judgments
COSTS_YAML = REPO_ROOT / "costs.yaml"
EXTERNAL_DIR = REPO_ROOT / "data" / "external"   # committed public datasets (README each): always in the repo, not DENTAL_DATA_ROOT
DEID_DIR = DATA_ROOT / "deid"                    # de-id benchmark scores (no PHI); challenge notes go to RAW_DIR
TASKS_DIR = REPO_ROOT / "data" / "tasks"         # spec 028: the coding-agent task set (manifest, gates; big files git-ignored)
CONTRACTS_DIR = REPO_ROOT / "contracts"         # spec 038: ODCS data contracts for the gold tables (generated)
