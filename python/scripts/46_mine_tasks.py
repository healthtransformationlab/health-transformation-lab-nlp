"""Mine the repo's history into the task manifest (spec 028, US1), and backfill issues (US2).

    python scripts/46_mine_tasks.py                      # writes data/tasks/task_manifest.csv
    python scripts/46_mine_tasks.py --backfill-issues    # creates one closed, labelled issue per tier B/C candidate
    python scripts/46_mine_tasks.py --backfill-issues --dry-run

Needs the GitHub REST API through `gh` (GH_TOKEN) and the repo's history fetched (`git fetch --depth=1000 origin main`).
Every PR and first-parent commit on main is a row; candidates are the ones that change code and tests.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys

import pandas as pd

from health_transformation_lab_nlp import task_mine as tm
from health_transformation_lab_nlp import telemetry
from health_transformation_lab_nlp.paths import REPO_ROOT

REPO = "healthtransformationlab/health-transformation-lab-nlp"
OUT = REPO_ROOT / "data" / "tasks" / "task_manifest.csv"
MAIN = "origin/main"


def gh_api(path: str, method: str = "GET", payload: dict | None = None, paginate: bool = False) -> list | dict:
    """One REST call through `gh api`; with paginate=True, follows page=1,2,... until a short page."""
    if not paginate:
        cmd = ["gh", "api", "-X", method, path] + (["--input", "-"] if payload is not None else [])
        res = subprocess.run(cmd, input=json.dumps(payload) if payload is not None else None, capture_output=True,
                             text=True, check=True)
        return json.loads(res.stdout) if res.stdout.strip() else {}
    out, page = [], 1
    while True:
        res = subprocess.run(["gh", "api", f"{path}&page={page}"], capture_output=True, text=True, check=True)
        chunk = json.loads(res.stdout) if res.stdout.strip() else []
        out.extend(chunk)
        if len(chunk) < 100:
            return out
        page += 1


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO_ROOT, capture_output=True, text=True, check=True).stdout


def changed_files(base: str, head: str) -> list[str]:
    try:
        return [p for p in git("diff", "--name-only", base, head).splitlines() if p]
    except subprocess.CalledProcessError:
        return []


def first_parent_commits() -> list[dict]:
    out = git("log", MAIN, "--first-parent", "--format=%H%x1f%P%x1f%cI%x1f%s%x1f%b%x1e")
    rows = []
    for rec in out.split("\x1e"):
        if not rec.strip():
            continue
        sha, parents, ts, subject, body = (rec.strip("\n").split("\x1f") + [""] * 5)[:5]
        plist = parents.split()
        rows.append({"sha": sha, "parent_sha": plist[0] if plist else "", "parents": plist, "is_merge": len(plist) > 1,
                     "committed_ts": ts, "subject": subject, "body": body})
    return rows


def build_manifest() -> pd.DataFrame:
    prs = gh_api(f"repos/{REPO}/pulls?state=closed&per_page=100", paginate=True)
    merged = {p["merge_commit_sha"]: p for p in prs if p.get("merged_at")}
    by_number = {p["number"]: p for p in merged.values()}
    rows, seen_pr = [], set()
    for c in first_parent_commits():
        pr = merged.get(c["sha"])
        if pr is None and not c["is_merge"]:
            n = tm.pr_from_squash_subject(c["subject"])
            pr = by_number.get(n) if n else None
        if pr is not None:
            if pr["number"] in seen_pr:
                continue
            seen_pr.add(pr["number"])
            tier, issue = tm.tier_for_pr(pr["head"]["ref"], pr.get("body"))
            if tier == "tool":
                continue
            files = []
            if c["parent_sha"]:   # a merge commit's base is the PR's merge base (PR review #358, should-fix 1)
                mb = git("merge-base", *c["parents"][:2]).strip() if c["is_merge"] else None
                base, head, c["base_source"] = tm.diff_range(c["sha"], c["parents"], mb)
                c["base_sha"] = base
                files = changed_files(base, head)
            rows.append(tm.manifest_row(tier, pr, c, files, issue))
        elif not c["is_merge"] and c["parent_sha"]:
            files = changed_files(c["parent_sha"], c["sha"])
            rows.append(tm.manifest_row("C", None, c, files, None))
    df = pd.DataFrame(rows, columns=tm.MANIFEST_COLUMNS)
    dup = df.duplicated("instance_id", keep=False)   # two PRs that close the same issue: keep both, distinct ids
    df.loc[dup & df["pr_number"].notna(), "instance_id"] = (
        df.loc[dup & df["pr_number"].notna(), "instance_id"] + "_pr" + df.loc[dup & df["pr_number"].notna(), "pr_number"].astype(int).astype(str))
    df["spec_number"] = df["spec_number"].astype("string")
    df["pr_number"] = df["pr_number"].astype("Int64")
    if OUT.exists():   # keep issue numbers a previous backfill filled in
        old = pd.read_csv(OUT, dtype={"issue_number": "Int64", "spec_number": "string"}) \
                .drop_duplicates("instance_id").set_index("instance_id")["issue_number"]
        kept = df["instance_id"].map(old)
        df["issue_number"] = [n if not pd.isna(n) else (k if not pd.isna(k) else None)
                              for n, k in zip(df["issue_number"], kept)]
    return df


def ensure_label() -> None:
    labels = gh_api(f"repos/{REPO}/labels?per_page=100", paginate=True)
    if not any(lbl["name"] == "backfilled" for lbl in labels):
        gh_api(f"repos/{REPO}/labels", "POST", {"name": "backfilled", "color": "bfd4f2",
                                                "description": "Record created after the work merged (spec 028); text is the original PR/commit description, verbatim"})


def next_kind_numbers() -> dict[str, int]:
    """Highest n per `<spec> <kind>` key across existing issues, so new titles continue the count."""
    issues = gh_api(f"repos/{REPO}/issues?state=all&per_page=100", paginate=True)
    counts: dict[str, int] = {}
    for i in issues:
        if "pull_request" in i:
            continue
        m = tm.re.match(r"^(\d{3}) ([A-Z]+)(\d+):", i["title"])
        if m:
            key = f"{m.group(1)} {m.group(2)}"
            counts[key] = max(counts.get(key, 0), int(m.group(3)))
    return counts


def _pr_number(row) -> int | None:
    n = row["pr_number"]
    return None if pd.isna(n) else int(n)


def source_text(row: pd.Series, prs_by_number: dict) -> str:
    n = _pr_number(row)
    if n and n in prs_by_number:
        p = prs_by_number[n]
        return f"**{p['title']}**\n\n{p.get('body') or '(no description)'}"
    body = git("log", "-1", "--format=%B", row["merge_commit_sha"])
    return body


def backfill(df: pd.DataFrame, dry_run: bool) -> pd.DataFrame:
    ensure_label()
    prs = {p["number"]: p for p in gh_api(f"repos/{REPO}/pulls?state=closed&per_page=100", paginate=True)}
    counts = next_kind_numbers()
    todo = df[(df["tier_code"].isin(["B", "C"])) & df["is_candidate"] & df["issue_number"].isna()]
    print(f"{len(todo)} candidates without an issue")
    for idx, row in todo.iterrows():
        rec = row.to_dict()
        rec["pr_number"] = _pr_number(row)
        issue = tm.backfill_issue(rec, source_text(row, prs))
        counts[issue["title_key"]] = counts.get(issue["title_key"], 0) + 1
        title = f"{issue['title_key']}{counts[issue['title_key']]}: {issue['title_text']}"
        ref = f"PR #{rec['pr_number']}" if rec["pr_number"] else f"commit {row['merge_commit_sha'][:7]}"
        if dry_run:
            print(f"  would create: {title}  ← {ref}")
            continue
        created = gh_api(f"repos/{REPO}/issues", "POST", {"title": title, "body": issue["body"], "labels": issue["labels"]})
        n = created["number"]
        gh_api(f"repos/{REPO}/issues/{n}/comments", "POST",
               {"body": f"Closed on creation: the work merged in {ref} before this record existed (spec 028, backfilled)."})
        gh_api(f"repos/{REPO}/issues/{n}", "PATCH", {"state": "closed", "state_reason": "completed"})
        df.at[idx, "issue_number"] = n
        print(f"  #{n} {title}  ← {ref}")
    return df


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--backfill-issues", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    a = p.parse_args()
    telemetry.setup()
    telemetry.start_script("46_mine_tasks", data_label="public")
    df = build_manifest()
    df["issue_number"] = df["issue_number"].astype("Int64")
    if a.backfill_issues:
        df = backfill(df, a.dry_run)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT, index=False)
    c = df[df["is_candidate"]]
    print(f"{len(df)} rows → {OUT.relative_to(REPO_ROOT)}; candidates {len(c)}: "
          + ", ".join(f"tier {t} {n}" for t, n in c["tier_code"].value_counts().sort_index().items()))
    telemetry.end_script()
    return 0


if __name__ == "__main__":
    sys.exit(main())
