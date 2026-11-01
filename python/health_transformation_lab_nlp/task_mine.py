"""The repo's history as a coding-agent task set (spec 028): mining and tiering.

Pure functions over what git and the GitHub REST API return; the script `46_mine_tasks.py` does the IO.

    tier A   the change has an issue: branch `<type>/<issue>-<slug>` or "Closes #n" in the PR body
    tier B   a PR without an issue (session branches before the issue rule)
    tier C   a commit straight to main (no PR); the statement is its message and the spec story it names

A candidate task changes non-test code and files under python/tests/ (the competition's mining rule).

US3 (`55_build_tasks.py`): a candidate's diff splits into `patch` (everything outside python/tests/) and
`test_patch` (python/tests/); the statement and hints come from the tier's source, redacted like the manifest.
"""

from __future__ import annotations

import re

from .telemetry import traced

TYPES = ("feat", "fix", "docs", "data", "ci", "chore", "spec")
BRANCH_ISSUE = re.compile(r"^(?:" + "|".join(TYPES) + r")/(\d+)-")
BODY_ISSUE = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?|refs?)\s+#(\d+)\b", re.IGNORECASE)
SQUASH_SUBJECT = re.compile(r"\(#(\d+)\)\s*$")
SPEC_REF = re.compile(r"\bspec(?:s/)?\s*(\d{3})\b|\b(\d{3}) (?:US|AI|BUG|CHORE|DOCS)\d+\b", re.IGNORECASE)
TOOL_BRANCHES = ("dependabot/", "kaggle-results/")
# CLAUDE.md "Organization names": the name never appears in a tracked file, not even in an old branch name
# or title copied from history. Built the same way as python/tests/test_no_org_references.py.
_ORG = re.compile(r"\b" + "care" + r"[\s_-]?" + "quest" + r"s?\b", re.IGNORECASE)
REDACTED = "[org]"
PROTECTED = ("conftest.py", "pytest.ini", "pyproject.toml", "tox.ini", "setup.cfg", ".pytest.ini")
MANIFEST_COLUMNS = ["instance_id", "tier_code", "pr_number", "issue_number", "merge_commit_sha", "base_commit_sha",
                    "created_ts", "merged_ts", "branch_name", "title_text", "statement_source_code", "spec_number",
                    "changed_file_count", "is_code_changed", "is_tests_changed", "is_only_protected_fix",
                    "is_candidate", "base_commit_source_code"]
TEST_DIR = "python/tests/"
# The competition's tasks.jsonl fields, in its order (gemma-developer-agent docs/dataset-format.md).
TASK_FIELDS = ("instance_id", "repo", "base_commit", "problem_statement", "hints_text", "patch", "test_patch",
               "created_at")
STORY_REF = re.compile(r"\b(\d{3}) US(\d+)\b")


@traced
def redact(text: str | None) -> str:
    """Replace the organisation name CLAUDE.md forbids with `[org]`, wherever history mentions it."""
    return _ORG.sub(REDACTED, text or "")


@traced
def issue_from_branch(branch: str) -> int | None:
    m = BRANCH_ISSUE.match(branch or "")
    return int(m.group(1)) if m else None


@traced
def issue_from_body(body: str | None) -> int | None:
    m = BODY_ISSUE.search(body or "")
    return int(m.group(1)) if m else None


@traced
def pr_from_squash_subject(subject: str) -> int | None:
    m = SQUASH_SUBJECT.search(subject or "")
    return int(m.group(1)) if m else None


@traced
def spec_from_text(*texts: str | None) -> str | None:
    for t in texts:
        m = SPEC_REF.search(t or "")
        if m:
            return m.group(1) or m.group(2)
    return None


@traced
def is_test_path(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return "/tests/" in f"/{path}" or name.startswith("test_") or name.endswith("_test.py")


@traced
def classify_files(paths: list[str]) -> dict:
    """What the diff touches: code, tests, and whether the only non-test change is in a file the grader strips."""
    code = [p for p in paths if p.endswith(".py") and not is_test_path(p)]
    tests = [p for p in paths if p.endswith(".py") and is_test_path(p)]
    non_test = [p for p in paths if not is_test_path(p)]
    only_protected = bool(non_test) and all(p.rsplit("/", 1)[-1] in PROTECTED for p in non_test)
    return {"changed_file_count": len(paths), "is_code_changed": bool(code), "is_tests_changed": bool(tests),
            "is_only_protected_fix": only_protected,
            "is_candidate": bool(code) and bool(tests) and not only_protected}


@traced
def tier_for_pr(branch: str, body: str | None) -> tuple[str, int | None]:
    """A merged PR's tier and issue number."""
    if branch.startswith(TOOL_BRANCHES):
        return "tool", None
    issue = issue_from_branch(branch) or issue_from_body(body)
    return ("A", issue) if issue else ("B", None)


@traced
def instance_id(tier: str, pr_number: int | None, issue_number: int | None, sha: str) -> str:
    """`htlnlp_<issue>` when an issue exists, else `htlnlp_pr<n>`, else `htlnlp_c<7-char sha>`."""
    if issue_number:
        return f"htlnlp_{issue_number}"
    if pr_number:
        return f"htlnlp_pr{pr_number}"
    return f"htlnlp_c{sha[:7]}"


@traced
def manifest_row(tier: str, pr: dict | None, commit: dict, files: list[str], issue_number: int | None) -> dict:
    """One manifest row from a PR (REST shape) or a direct commit (`sha`, `parent_sha`, `committed_ts`,
    `subject`, `body`)."""
    f = classify_files(files)
    if pr is not None:
        title, body, created = pr["title"], pr.get("body") or "", pr["created_at"]
        merged, branch, number = pr.get("merged_at"), pr["head"]["ref"], pr["number"]
        source = "issue" if issue_number else "pr"
    else:
        title, body, created = commit["subject"], commit.get("body") or "", commit["committed_ts"]
        merged, branch, number = commit["committed_ts"], "", None
        source = "commit"
    return {"instance_id": instance_id(tier, number, issue_number, commit["sha"]), "tier_code": tier,
            "pr_number": number, "issue_number": issue_number, "merge_commit_sha": commit["sha"],
            "base_commit_sha": commit.get("base_sha") or commit["parent_sha"], "created_ts": created, "merged_ts": merged,
            "branch_name": redact(branch), "title_text": redact(title), "statement_source_code": source,
            "spec_number": spec_from_text(title, body, branch), **f,
            "base_commit_source_code": commit.get("base_source") or "parent"}


@traced
def backfill_issue(row: dict, body_text: str, kind: str = "CHORE") -> dict:
    """The issue to create for a tier B or C candidate: title key `<spec> <kind><n>: <title>` (n filled by the
    script), the contemporaneous text verbatim, the link, and the label. Nothing reworded."""
    spec = row.get("spec_number") or "000"
    ref = f"PR #{row['pr_number']}" if row.get("pr_number") else f"commit {row['merge_commit_sha'][:7]}"
    title = row["title_text"].strip()
    if row.get("pr_number"):
        title = SQUASH_SUBJECT.sub("", title).strip()
    head = (f"Backfilled record (spec 028): this issue was created after the work merged, so that every task in "
            f"the DataOps task set has an issue number. The text below is the original {ref} description, "
            f"verbatim; nothing was written after the fact.\n\n")
    return {"title_key": f"{spec} {kind}", "title_text": title, "labels": ["backfilled"],
            "body": head + f"**Source:** {ref} · merged {row.get('merged_ts')} · base `{row['base_commit_sha'][:7]}`"
                    f" · tier {row['tier_code']}\n\n---\n\n{body_text.strip()}\n"}


# --- US3: tasks.jsonl rows -----------------------------------------------------------------------------------

@traced
def diff_range(sha: str, parents: list[str], merge_base: str | None) -> tuple[str, str, str]:
    """`(base, head, source)` for a change on main. A squash or direct commit: its parent to itself. A merge
    commit: the PR's merge base to the PR head (second parent), so `patch` + `test_patch` applied to
    `base_commit` reproduce the PR's tree exactly (PR review #358, should-fix 1)."""
    if len(parents) > 1 and merge_base:
        return merge_base, parents[1], "merge_base"
    return parents[0], sha, "parent"


def _diff_path(header: str) -> str:
    return header.rstrip("\n").rsplit(" b/", 1)[-1]


@traced
def split_diff(diff: str) -> dict:
    """Split a unified diff into `patch` (files outside python/tests/) and `test_patch` (python/tests/), whole
    file blocks in order; nothing is dropped, so the two together hold every hunk."""
    blocks: list[str] = []
    cur: list[str] = []
    for line in diff.splitlines(keepends=True):
        if line.startswith("diff --git ") and cur:
            blocks.append("".join(cur))
            cur = []
        cur.append(line)
    if cur:
        blocks.append("".join(cur))
    out: dict = {"patch": "", "test_patch": "", "patch_files": [], "test_files": []}
    for b in blocks:
        path = _diff_path(b.split("\n", 1)[0])
        if path.startswith(TEST_DIR):
            out["test_patch"] += b
            out["test_files"].append(path)
        else:
            out["patch"] += b
            out["patch_files"].append(path)
    return out


@traced
def exclusion_reason(patch_files: list[str], test_files: list[str]) -> str | None:
    """Why a candidate is not a task, or None. A fix only in files the grader strips (runner config, test
    files) cannot be scored; a task also needs a non-test code change and a python/tests change."""
    non_test = [p for p in patch_files if not is_test_path(p)]
    stripped = all(p.rsplit("/", 1)[-1] in PROTECTED for p in non_test)
    if patch_files and stripped:
        return "fix only in grader-stripped files"
    if not any(p.endswith(".py") for p in non_test):
        return "no non-test code change"
    if not test_files:
        return "no python/tests change"
    return None


@traced
def story_ref(text: str | None) -> tuple[str, int] | None:
    """The spec user story a commit names (`028 US3`), or None."""
    m = STORY_REF.search(text or "")
    return (m.group(1), int(m.group(2))) if m else None


@traced
def story_section(spec_md: str, n: int) -> str:
    """The `### US<n>` section of a spec.md, up to the next heading of level 3 or above; "" when absent."""
    out: list[str] = []
    for line in spec_md.splitlines():
        if out:
            if re.match(r"^#{1,3} ", line):
                break
            out.append(line)
        elif re.match(rf"^### US{n}\b", line):
            out.append(line)
    return "\n".join(out).strip()


def _titled(item: dict | None) -> str:
    if not item:
        return ""
    return f"{(item.get('title') or '').strip()}\n\n{(item.get('body') or '').strip()}".strip()


def _joined(*parts: str | None, sep: str = "\n\n---\n\n") -> str:
    return sep.join(p.strip() for p in parts if p and p.strip())


@traced
def statement_and_hints(tier: str, issue: dict | None = None, pr: dict | None = None, review: str | None = None,
                        commit: dict | None = None, story: str | None = None, plan: str | None = None,
                        tasks: str | None = None) -> dict:
    """`problem_statement`, `hints_text` and `created_at` from the tier's contemporaneous source (spec 028):
    A the issue (hints: the PR and its review), B the PR (hints: the review), C the commit message and the spec
    story it names (hints: the spec's plan and tasks). Quoted as written; the organisation name is redacted."""
    if tier == "A" and issue:
        stmt, hints, created = _titled(issue), _joined(_titled(pr), review), issue.get("created_at")
    elif tier in ("A", "B") and pr:
        stmt, hints, created = _titled(pr), _joined(review), pr.get("created_at")
    else:
        commit = commit or {}
        stmt = _joined(commit.get("message"), story, sep="\n\n")
        hints, created = _joined(plan, tasks), commit.get("committed_ts")
    return {"problem_statement": redact(stmt), "hints_text": redact(hints), "created_at": created or ""}


@traced
def task_row(instance: str, repo: str, base_commit: str, text: dict, split: dict) -> dict:
    """One tasks.jsonl row: exactly the competition's fields, in its order."""
    values = {"instance_id": instance, "repo": repo, "base_commit": base_commit, **text, **split}
    return {k: values.get(k, "") for k in TASK_FIELDS}
