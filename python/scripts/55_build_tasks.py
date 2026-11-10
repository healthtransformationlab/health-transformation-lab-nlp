"""Build `tasks.jsonl` from the task manifest, in the competition's format (spec 028, US3, #354).

    python scripts/55_build_tasks.py                 # data/tasks/tasks.jsonl (git-ignored), tasks_excluded.csv,
                                                     # tasks_sample.jsonl, and the manifest's base commits
    python scripts/55_build_tasks.py --sample 3
    python scripts/55_build_tasks.py --graphs        # also data/tasks/graphs/<instance_id>.json (US4, T009)
    python scripts/55_build_tasks.py --snapshots 2   # also the first N snapshots/<instance_id>.tgz (US4, T008;
                                                     # one commit of the base's files, no history, name redacted, #435)
    python scripts/55_build_tasks.py --graphs --embeddings   # also embeddings/<instance_id>.npz (US4, T010):
                                                     # EmbeddingGemma, 256 dims per graph node; needs HF_TOKEN with
                                                     # the Gemma licence accepted, and the [embeddings] extra
    python scripts/55_build_tasks.py --wheels        # also wheels/: the package's runtime, dev and tasks
                                                     # dependencies as Python 3.13 binary wheels (US4, T010)

For each candidate in data/tasks/task_manifest.csv: `base_commit` is the parent of a squash or direct commit, or
the PR's merge base for a merge commit (recorded in the manifest as `base_commit_source_code`); the diff from
`base_commit` to the change splits into `patch` (outside python/tests/) and `test_patch` (python/tests/); the
statement and hints come from the tier's source (issue, PR, or commit and spec story), redacted like the manifest.
A candidate whose fix lives only in files the grader strips, or that has no code or no python/tests change in
that range, is listed in tasks_excluded.csv instead.

NOT DONE HERE (T007): the two gates (fail-to-pass, pass) run in scripts/57_gate_tasks.py, our own check that
follows the competition harness's documented verification (#453; the evaluator itself, swegemma, was found
later, #636, and decides what is published: spec 028 US6); results in data/tasks/task_gates.csv. Rows here stay
ungated candidates: 57 writes the published set (tasks_gated.jsonl) without the ones that fail. This script keeps 57's rows in tasks_excluded.csv for the tasks it
still builds and removes tasks_gated.jsonl, so run 57 again before publishing (T007a, #502).

Needs the full history (`git fetch --unshallow origin`) and the GitHub REST API for issue and PR text (public
repo: works unauthenticated, 60 requests an hour; this script makes about five).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

import pandas as pd

from health_transformation_lab_nlp import task_gate as tgate
from health_transformation_lab_nlp import task_graph as tg
from health_transformation_lab_nlp import task_mine as tm
from health_transformation_lab_nlp import telemetry
from health_transformation_lab_nlp.paths import REPO_ROOT, TASKS_DIR

REPO = "healthtransformationlab/health-transformation-lab-nlp"
MANIFEST = TASKS_DIR / "task_manifest.csv"
OUT = TASKS_DIR / "tasks.jsonl"               # git-ignored: full patches, tens of MB
EXCLUDED = TASKS_DIR / "tasks_excluded.csv"
GATED = TASKS_DIR / "tasks_gated.jsonl"       # git-ignored: written by 57_gate_tasks.py, removed here
SAMPLE = TASKS_DIR / "tasks_sample.jsonl"     # committed: the smallest few rows, to show the format
REVIEWS = REPO_ROOT / "pull_requests"
GRAPHS = TASKS_DIR / "graphs"                 # git-ignored
EMBEDDINGS = TASKS_DIR / "embeddings"         # git-ignored
WHEELS = TASKS_DIR / "wheels"                 # git-ignored
SNAPSHOTS = TASKS_DIR / "snapshots"           # git-ignored
SNAPSHOT_INDEX = TASKS_DIR / "snapshot_index.csv"   # committed: base commit -> the snapshot's own head
PACKAGE, SOURCE_ROOT = "health_transformation_lab_nlp", "python/"


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout


def rest(path: str) -> list | dict:
    """One GitHub REST GET. Uses GH_TOKEN or GITHUB_TOKEN if set and valid; falls back to unauthenticated."""
    token = os.environ.get("GH_TOKEN") or os.environ.get("GITHUB_TOKEN")
    for auth in ([token, None] if token else [None]):
        req = urllib.request.Request(f"https://api.github.com/{path}", headers={"Accept": "application/vnd.github+json"})
        if auth:
            req.add_header("Authorization", f"Bearer {auth}")
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 401 and auth:
                print("warning: the GitHub token was refused (401); retrying unauthenticated", file=sys.stderr)
                continue
            raise
    raise RuntimeError("unreachable")


def check_settings(embeddings: bool = False) -> None:
    """AGENTS.md: check what the run needs before the work, and fail naming it. With --embeddings, that includes
    sentence-transformers and one cheap authenticated call for the gated model, before any mining or graphs."""
    if embeddings:
        try:
            import sentence_transformers  # noqa: F401 - only checked here; loaded in load_encoder
        except ImportError:
            sys.exit('--embeddings needs sentence-transformers and torch: pip install -e ".[embeddings]"')
        from health_transformation_lab_nlp.llm_reader import check_hf_access
        check_hf_access(tg.EMBED_MODEL)   # fails naming HF_TOKEN when it's missing or hasn't accepted the licence
    if not MANIFEST.exists():
        sys.exit(f"missing {MANIFEST.relative_to(REPO_ROOT)}: run scripts/46_mine_tasks.py first")
    if git("rev-parse", "--is-shallow-repository").strip() == "true":
        sys.exit("the clone is shallow: merge bases and old diffs need `git fetch --unshallow origin`")
    try:
        rest(f"repos/{REPO}")
    except (urllib.error.URLError, OSError) as e:
        sys.exit(f"GitHub REST API unreachable ({e}); issue and PR text come from it")


def all_issues_and_prs() -> dict[int, dict]:
    """Every issue and PR (the issues endpoint lists both, with title, body and created_at)."""
    out, page = {}, 1
    while True:
        chunk = rest(f"repos/{REPO}/issues?state=all&per_page=100&page={page}")
        out.update({i["number"]: i for i in chunk})
        if len(chunk) < 100:
            return out
        page += 1


def show(sha: str, path: str) -> str | None:
    try:
        return git("show", f"{sha}:{path}")
    except subprocess.CalledProcessError:
        return None


def spec_files(sha: str, spec: str) -> dict[str, str | None]:
    """spec.md, plan.md and tasks.md of `specs/<spec>-*` as they stood at `sha`."""
    dirs = [d for d in git("ls-tree", "--name-only", sha, "specs/").split() if d.startswith(f"specs/{spec}-")]
    if not dirs:
        return {"spec": None, "plan": None, "tasks": None}
    return {k: show(sha, f"{dirs[0]}/{k}.md") for k in ("spec", "plan", "tasks")}


def review_text(pr_number) -> str | None:
    if pd.isna(pr_number):
        return None
    p = REVIEWS / f"pr-{int(pr_number)}-review.md"
    return p.read_text() if p.exists() else None


def base_and_head(sha: str) -> tuple[str, str, str]:
    parents = git("rev-list", "--parents", "-n", "1", sha).split()[1:]
    merge_base = git("merge-base", parents[0], parents[1]).strip() if len(parents) > 1 else None
    return tm.diff_range(sha, parents, merge_base)


def text_for(row: pd.Series, items: dict[int, dict]) -> dict:
    tier = row["tier_code"]
    if tier in ("A", "B"):
        issue = items.get(int(row["issue_number"])) if tier == "A" and not pd.isna(row["issue_number"]) else None
        pr = items.get(int(row["pr_number"])) if not pd.isna(row["pr_number"]) else None
        return tm.statement_and_hints(tier, issue=issue, pr=pr, review=review_text(row["pr_number"]))
    sha = row["merge_commit_sha"]
    message = git("log", "-1", "--format=%B", sha)
    ref = tm.story_ref(message)
    files = spec_files(sha, ref[0]) if ref else {"spec": None, "plan": None, "tasks": None}
    story = tm.story_section(files["spec"], ref[1]) if ref and files["spec"] else None
    return tm.statement_and_hints("C", commit={"message": message, "committed_ts": git("log", "-1", "--format=%cI", sha).strip()},
                                  story=story, plan=files["plan"], tasks=files["tasks"])


def package_sources(sha: str) -> tuple[str, dict[str, str]]:
    """The package's name and every .py file of it as they stood at `sha` (it was renamed during the history)."""
    paths = git("ls-tree", "-r", "--name-only", sha, SOURCE_ROOT).split()
    package = tg.package_name(paths, SOURCE_ROOT) or PACKAGE
    prefix = f"{SOURCE_ROOT}{package}/"
    return package, {p: show(sha, p) or "" for p in paths if p.startswith(prefix) and p.endswith(".py")}


def write_graphs(rows: list[dict]) -> None:
    GRAPHS.mkdir(parents=True, exist_ok=True)
    sizes = []
    for r in rows:
        package, sources = package_sources(r["base_commit"])
        g = tg.build_graph(sources, package, SOURCE_ROOT,
                           {"repo": r["repo"], "base_commit": r["base_commit"], "instance_id": r["instance_id"],
                            "builder": "ast walk, spec 028 (55_build_tasks.py)"})
        path = GRAPHS / f"{r['instance_id']}.json"
        path.write_text(json.dumps(g))
        sizes.append((len(g["nodes"]), len(g["edges"]), path.stat().st_size))
    n = len(sizes)
    print(f"{n} graphs -> {GRAPHS.relative_to(REPO_ROOT)}; median nodes {sorted(s[0] for s in sizes)[n // 2]}, "
          f"edges {sorted(s[1] for s in sizes)[n // 2]}, {sum(s[2] for s in sizes) / 1e6:.0f} MB in all")


def load_encoder():
    """EmbeddingGemma at its pinned revision, as a texts -> (n, 768) function using the model's document prompt.
    The token and the library were checked in check_settings, before any other work."""
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(tg.EMBED_MODEL, revision=tg.EMBED_REVISION, device="cpu")
    return lambda texts: model.encode_document(texts, batch_size=16, convert_to_numpy=True)


def write_embeddings(rows: list[dict]) -> None:
    """One .npz per task from its graph (built first by --graphs), each distinct node text encoded once."""
    missing = [r["instance_id"] for r in rows if not (GRAPHS / f"{r['instance_id']}.json").exists()]
    if missing:
        sys.exit(f"--embeddings needs the graphs first ({len(missing)} missing, e.g. {missing[0]}): add --graphs")
    encode, cache = load_encoder(), {}
    keep = {f"{r['instance_id']}.npz" for r in rows}
    for old in EMBEDDINGS.glob("*.npz"):   # a task dropped since the last build leaves no file behind
        if old.name not in keep:
            old.unlink()
    for r in rows:
        g = json.loads((GRAPHS / f"{r['instance_id']}.json").read_text())
        tg.save_embeddings(tg.embed_graph(g, encode, cache=cache), EMBEDDINGS / f"{r['instance_id']}.npz")
    size = sum(p.stat().st_size for p in EMBEDDINGS.glob("*.npz"))
    print(f"{len(rows)} embeddings -> {EMBEDDINGS.relative_to(REPO_ROOT)} ({tg.EMBED_MODEL}@{tg.EMBED_REVISION[:12]}, "
          f"{tg.EMBED_DIMS} dims; {len(cache)} distinct node texts encoded; {size / 1e6:.0f} MB); parity with the "
          "competition's own embedding model is unverified (it isn't named)")


def write_wheels() -> None:
    """The sandbox's wheels, from this checkout's pyproject.toml (the dependencies today, not per base)."""
    reqs = tg.wheel_requirements((REPO_ROOT / "python" / "pyproject.toml").read_text())
    shutil.rmtree(WHEELS, ignore_errors=True)   # rebuilt whole, so re-runnable and no stale versions
    subprocess.run([sys.executable, "-m", *tg.wheel_download_command(reqs, WHEELS)], check=True)
    wheels = sorted(WHEELS.glob("*.whl"))
    print(f"{len(wheels)} wheels for Python {tg.WHEEL_PYTHON} -> {WHEELS.relative_to(REPO_ROOT)} "
          f"({sum(w.stat().st_size for w in wheels) / 1e6:.0f} MB) from: {', '.join(reqs)}")


def write_snapshots(rows: list[dict], limit: int) -> None:
    out = []
    for r in rows[:limit]:
        info = tg.snapshot(REPO_ROOT, r["base_commit"], SNAPSHOTS / f"{r['instance_id']}.tgz",
                           work_dir=SNAPSHOTS / "_work")
        out.append({"instance_id": r["instance_id"], **info})
        print(f"  snapshot {r['instance_id']}: one commit, {info['size_bytes'] / 1e6:.1f} MB, head "
              f"{info['snapshot_head_sha'][:12]} (base {info['base_commit'][:12]}), "
              f"{len([x for x in info['redacted_paths'].split(';') if x])} files redacted")
    shutil.rmtree(SNAPSHOTS / "_work", ignore_errors=True)
    new = pd.DataFrame(out)
    built = {r["instance_id"] for r in rows}
    for old_tgz in SNAPSHOTS.glob("*.tgz"):   # a task no longer built leaves no snapshot behind
        if old_tgz.stem not in built:
            old_tgz.unlink()
    if SNAPSHOT_INDEX.exists():   # keyed by instance_id: re-runs replace their own rows; dropped tasks go
        old = pd.read_csv(SNAPSHOT_INDEX, keep_default_na=False)
        old = old[old["instance_id"].isin(built) & ~old["instance_id"].isin(new["instance_id"])]
        new = pd.concat([old, new])
    new.sort_values("instance_id").to_csv(SNAPSHOT_INDEX, index=False)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--sample", type=int, default=3, help="rows in the committed tasks_sample.jsonl (smallest first)")
    ap.add_argument("--graphs", action="store_true", help="write one code graph per task (US4)")
    ap.add_argument("--snapshots", type=int, default=0, help="write snapshots for the first N tasks (US4)")
    ap.add_argument("--embeddings", action="store_true", help="write node embeddings from the graphs (US4, T010)")
    ap.add_argument("--wheels", action="store_true", help="download the Python 3.13 sandbox wheels (US4, T010)")
    a = ap.parse_args()
    check_settings(embeddings=a.embeddings)
    telemetry.setup()
    telemetry.start_script("55_build_tasks", data_label="public")

    manifest = pd.read_csv(MANIFEST, dtype={"spec_number": "string", "issue_number": "Int64", "pr_number": "Int64"})
    if "base_commit_source_code" not in manifest:
        manifest["base_commit_source_code"] = "parent"
    for idx, row in manifest.iterrows():   # the base each row's diff is taken from (PR review #358)
        base, _, source = base_and_head(row["merge_commit_sha"])
        manifest.at[idx, "base_commit_sha"], manifest.at[idx, "base_commit_source_code"] = base, source
    manifest[tm.MANIFEST_COLUMNS].to_csv(MANIFEST, index=False)

    items = all_issues_and_prs()
    rows, excluded = [], []
    for _, row in manifest[manifest["is_candidate"]].iterrows():
        base, head, _ = base_and_head(row["merge_commit_sha"])
        split = tm.split_diff(git("diff", "--binary", "--full-index", "--no-color", "--no-ext-diff", base, head))
        reason = tm.exclusion_reason(split["patch_files"], split["test_files"])
        if reason:
            excluded.append({"instance_id": row["instance_id"], "tier_code": row["tier_code"], "reason_text": reason})
            continue
        task = tm.task_row(row["instance_id"], REPO, base, text_for(row, items), split)
        reason = tm.org_exclusion_reason(task) or tm.withheld_exclusion_reason(task, tg.WITHHELD_PATHS)
        if reason:   # CLAUDE.md: never the organisation name (#435); no withheld file either (PR #515)
            excluded.append({"instance_id": row["instance_id"], "tier_code": row["tier_code"], "reason_text": reason})
            continue
        rows.append(task)

    rows.sort(key=lambda r: r["instance_id"])
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("".join(json.dumps(r) + "\n" for r in rows))   # overwritten whole: re-runnable
    previous = pd.read_csv(EXCLUDED, keep_default_na=False).to_dict("records") if EXCLUDED.exists() else []
    carried = tgate.carried_gate_rows(previous, {r["instance_id"] for r in rows})   # 57's rows (T007a, #502)
    pd.DataFrame(tgate.merge_exclusions(excluded, carried), columns=["instance_id", "tier_code", "reason_text"]) \
        .to_csv(EXCLUDED, index=False)
    GATED.unlink(missing_ok=True)   # the set changed: 57_gate_tasks.py writes the published set again
    leaked = [r["instance_id"] for r in rows if tm.names_org(json.dumps(r))]
    if leaked:   # statements and hints are redacted and naming rows excluded above, so this is a bug (#435)
        raise RuntimeError(f"{len(leaked)} rows still name the organisation CLAUDE.md forbids: {leaked[:5]}")
    sample = sorted(rows, key=lambda r: len(r["patch"]) + len(r["test_patch"]))[: a.sample]
    SAMPLE.write_text("".join(json.dumps(r) + "\n" for r in sorted(sample, key=lambda r: r["instance_id"])))

    tiers = manifest.set_index("instance_id")["tier_code"]
    counts = pd.Series([tiers[r["instance_id"]] for r in rows]).value_counts().sort_index()
    print(f"{len(rows)} ungated rows -> {OUT.relative_to(REPO_ROOT)} ({OUT.stat().st_size / 1e6:.1f} MB; "
          + ", ".join(f"tier {t} {n}" for t, n in counts.items()) + f"); {len(excluded)} excluded -> "
          f"{EXCLUDED.relative_to(REPO_ROOT)} (organisation name: {sum('#435' in e['reason_text'] for e in excluded)});"
          f" sample {len(sample)} -> {SAMPLE.relative_to(REPO_ROOT)}")
    print("gates NOT run here (T007): run scripts/57_gate_tasks.py; it writes the published set, tasks_gated.jsonl")
    if a.graphs:
        write_graphs(rows)
    if a.snapshots:
        write_snapshots(rows, a.snapshots)
    if a.embeddings:
        write_embeddings(rows)
    if a.wheels:
        write_wheels()
    telemetry.end_script()
    return 0


if __name__ == "__main__":
    sys.exit(main())
