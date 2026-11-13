"""Check a pull request's branch name and issue link (the rule in AGENTS.md, "Branches and issues").

    <type>/<ticket>-<slug>      feat/71-016-results-loader, fix/72-volume-log-append, feat/DENT-123-loader
    type     feat fix docs data ci chore spec
    ticket   a GitHub issue number, or a Jira key (DENT-123)
    slug     lowercase words joined by '-', at most 40 characters; spec work starts with the spec number

Branches a tool names are allowed as they are: dependabot/*, kaggle-results/* (the Kaggle workflow's results
PRs). An agent session's assigned claude/* branch is not: the session moves its work to <type>/<issue>-<slug>
(AGENTS.md rule 4, issue #116). Every PR except dependabot's and kaggle-results' links its issue in the body:
"Closes #71" (or Fixes, Resolves, Refs; or a Jira key).

The issue itself is checked too (AGENTS.md, "What an issue says", issue #700): an issue opened from PARTS_SINCE on
has four parts, Problem, Done when, Contract and Read first, as headings or bold labels. Older issues pass as they
are. In CI the script reads the linked issue with GITHUB_TOKEN; without one it checks the branch and the link only.

Usage in CI: BRANCH=... BODY=... GITHUB_REPOSITORY=... GITHUB_TOKEN=... python .github/scripts/pr_conventions.py
"""

import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

TYPES = ("feat", "fix", "docs", "data", "ci", "chore", "spec")
TOOL_BRANCHES = ("dependabot/", "kaggle-results/")
NO_ISSUE_NEEDED = ("dependabot/", "kaggle-results/")
TICKET = r"(?:\d+|[A-Z][A-Z0-9]+-\d+)"
LINK = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?|refs?)\s+(?:#\d+|[A-Z][A-Z0-9]+-\d+)\b", re.IGNORECASE)
MAX_SLUG = 40
ISSUE_PARTS = ("Problem", "Done when", "Contract", "Read first")
PARTS_SINCE = "2026-11-14"          # issues opened from this day (UTC) carry the four parts
ISSUE_NUMBER = re.compile(r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?|refs?)\s+#(\d+)\b", re.IGNORECASE)


def branch_problems(branch: str) -> list[str]:
    if branch.startswith(TOOL_BRANCHES):
        return []
    if branch.startswith("claude/"):
        return [(f"'{branch}' is an agent session's assigned branch: open or find the issue, then push the work to "
                 "<type>/<issue>-<slug> and open the PR from there (AGENTS.md, Branches and issues, rule 4)")]
    kind, _, rest = branch.partition("/")
    if kind not in TYPES or not rest:
        return [f"start with a type and '/': one of {', '.join(TYPES)} (got '{branch}')"]
    m = re.fullmatch(rf"({TICKET})-(.+)", rest)
    if not m:
        return [f"put the issue number (or Jira key) after the type: {kind}/<issue>-<slug>"]
    slug = m.group(2)
    problems = []
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", slug):
        problems.append(f"slug must be lowercase words joined by '-' (got '{slug}')")
    if len(slug) > MAX_SLUG:
        problems.append(f"slug too long: {len(slug)} characters, at most {MAX_SLUG}")
    return problems


def issue_link(body: str | None) -> bool:
    return bool(body and LINK.search(body))


def linked_issue_number(body: str | None) -> int | None:
    """The first GitHub issue number the description links; None for a Jira key or no link."""
    m = ISSUE_NUMBER.search(body or "")
    return int(m.group(1)) if m else None


def issue_problems(issue_body: str | None, created_at: str | None) -> list[str]:
    """What an issue opened from PARTS_SINCE on is missing: a part counts when a line starts with its name, as a
    heading ('## Done when') or a bold label ('**Done when:**')."""
    if not created_at or created_at[:10] < PARTS_SINCE:
        return []
    text = issue_body or ""
    missing = [p for p in ISSUE_PARTS if not re.search(rf"(?im)^[ \t]*(?:#+[ \t]*|\*\*)?{re.escape(p)}\b", text)]
    if not missing:
        return []
    return [(f"the linked issue lacks: {', '.join(missing)}. Add the part to the issue as a dated line; an issue says "
             "what a test will check before the work starts (AGENTS.md, What an issue says)")]


def fetch_issue(repo: str, number: int, token: str) -> tuple[str, str]:
    """The issue's body and created_at from GitHub; one retry for a network blip, then the error."""
    req = urllib.request.Request(f"https://api.github.com/repos/{repo}/issues/{number}", headers={
        "Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json", "User-Agent": "pr-conventions"})
    for attempt in (1, 2):
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                d = json.load(r)
            return d.get("body") or "", d.get("created_at") or ""
        except (urllib.error.URLError, TimeoutError) as e:
            if isinstance(e, urllib.error.HTTPError) and e.code < 500 or attempt == 2:
                raise
            time.sleep(5)
    raise RuntimeError("unreachable")


def check(branch: str, body: str | None, issue: tuple[str, str] | None = None) -> list[str]:
    """Problems with the branch name, the issue link and, when the linked issue was read, the issue's four parts."""
    problems = branch_problems(branch)
    if branch.startswith(NO_ISSUE_NEEDED):
        return problems
    if not issue_link(body):
        problems.append("link the issue in the PR description: 'Closes #<issue>' (or Fixes, Refs, or a Jira key)")
    elif issue is not None:
        problems += issue_problems(*issue)
    return problems


if __name__ == "__main__":
    branch, body = os.environ.get("BRANCH", ""), os.environ.get("BODY", "")
    repo, token = os.environ.get("GITHUB_REPOSITORY", ""), os.environ.get("GITHUB_TOKEN", "")
    number, issue = linked_issue_number(body), None
    if number and repo and token and not branch.startswith(NO_ISSUE_NEEDED):
        try:
            issue = fetch_issue(repo, number, token)
        except Exception as e:  # noqa: BLE001 - the check says how it ended and fails: an unread issue is unchecked
            print(f"::error::could not read issue #{number} of {repo}: {type(e).__name__}: {e}")
            sys.exit(1)
    elif number:
        print(f"no GITHUB_TOKEN: issue #{number} was not read, only the branch name and the link are checked")
    found = check(branch, body, issue)
    for p in found:
        print(f"::error::{p}")
    if not found:
        print(f"'{branch}', its issue link{' and its issue' if issue else ''} follow AGENTS.md")
    sys.exit(1 if found else 0)
