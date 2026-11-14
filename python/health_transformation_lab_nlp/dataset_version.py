"""One declared semantic version and changelog per published dataset (spec 039 US1, #707).

Each dataset in ``kaggle/dataset_docs.yaml`` declares, beside its files and columns:

- ``version``: ``MAJOR.MINOR.PATCH``;
- ``changelog``: one line per version, newest first, ``"X.Y.Z — what changed"``;
- ``schema_sha256``: the SHA-256 of its published file and column set, from ``kaggle/dataset_docs.py``'s
  ``schema_sha256``.

The semver rule:

- **MAJOR**: a breaking schema change: a column removed, renamed or retyped, or a file removed.
- **MINOR**: a new file or column.
- **PATCH**: values, rows or a fix, with no schema change.

``python/tests/test_kaggle_dataset_docs.py`` hashes what each dataset publishes and fails when the hash isn't the
declared ``schema_sha256``. So a file or column can't change without a new version, a changelog line and the new
hash, all in the same diff.
"""

from __future__ import annotations

import re
from functools import cache
from pathlib import Path

import yaml

from .paths import REPO_ROOT
from .telemetry import traced

DOCS = REPO_ROOT / "kaggle" / "dataset_docs.yaml"
SEMVER = re.compile(r"(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)")
LINE = re.compile(r"(\S+) — (\S.*)")
RULE = (
    "MAJOR for a removed, renamed or retyped column or a removed file; MINOR for a new file or column; "
    "PATCH for values, rows or a fix with no schema change"
)


@cache
def _shipped() -> dict:
    return yaml.safe_load(DOCS.read_text())["datasets"]


def _entry(slug: str, docs: Path | None) -> dict:
    datasets = _shipped() if docs is None else (yaml.safe_load(Path(docs).read_text()) or {}).get("datasets") or {}
    if slug not in datasets:
        raise KeyError(f"{slug}: not in {Path(docs or DOCS).name}")
    return datasets[slug] or {}


def _key(version: str) -> tuple[int, ...]:
    return tuple(int(part) for part in version.split("."))


@traced
def version(slug: str, *, docs: Path | None = None) -> str:
    """The dataset's declared semantic version."""
    declared = _entry(slug, docs).get("version")
    if not declared:
        raise ValueError(f"{slug}: no version declared")
    return str(declared)


@traced
def changelog(slug: str, *, docs: Path | None = None) -> list[str]:
    """The dataset's changelog, one line per version, newest first."""
    return [" ".join(str(line).split()) for line in _entry(slug, docs).get("changelog") or []]


@traced
def latest_change(slug: str, *, docs: Path | None = None) -> str:
    """The newest changelog line: what the current version changed."""
    lines = changelog(slug, docs=docs)
    if not lines:
        raise ValueError(f"{slug}: no changelog")
    return lines[0]


@traced
def problems(slug: str, *, schema_sha256: str | None = None, docs: Path | None = None) -> list[str]:
    """What's wrong with the dataset's version declaration; empty when nothing is. Given ``schema_sha256``, the hash
    of what the dataset publishes now, it also reports a published set that changed without a new version."""
    try:
        entry = _entry(slug, docs)
    except KeyError as exc:
        return [str(exc.args[0])]
    found = []
    declared = str(entry.get("version") or "")
    if not declared:
        found.append(f'{slug}: no version; declare version: "1.0.0" and its changelog line')
    elif not SEMVER.fullmatch(declared):
        found.append(f"{slug}: version {declared!r} is not MAJOR.MINOR.PATCH")
    lines = changelog(slug, docs=docs)
    if not lines:
        found.append(f'{slug}: no changelog; add one line per version, newest first: "X.Y.Z — what changed"')
    versions = []
    for line in lines:
        match = LINE.fullmatch(line)
        if match and SEMVER.fullmatch(match.group(1)):
            versions.append(match.group(1))
        else:
            found.append(f'{slug}: changelog line {line!r} is not "X.Y.Z — what changed"')
    if versions and SEMVER.fullmatch(declared) and versions[0] != declared:
        found.append(
            f"{slug}: version is {declared} but the top changelog line is for {versions[0]}; "
            "a new version needs its own changelog line, at the top"
        )
    if any(_key(newer) <= _key(older) for newer, older in zip(versions, versions[1:])):
        found.append(f"{slug}: changelog versions must go newest first, each higher than the one below it")
    stored = str(entry.get("schema_sha256") or "")
    if schema_sha256 is not None and schema_sha256 != stored:
        found.append(
            f"{slug}: its published files or columns changed (schema_sha256 {stored or 'missing'}, now "
            f"{schema_sha256}). Bump version ({RULE}), add its changelog line at the top, and set schema_sha256 "
            f"to {schema_sha256}."
        )
    return found
