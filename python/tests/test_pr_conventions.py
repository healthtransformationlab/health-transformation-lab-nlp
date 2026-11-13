"""Branch names and issue links on pull requests (.github/scripts/pr_conventions.py, AGENTS.md)."""

import importlib.util

import pytest

from health_transformation_lab_nlp.paths import REPO_ROOT

_spec = importlib.util.spec_from_file_location("pr_conventions", REPO_ROOT / ".github" / "scripts" / "pr_conventions.py")
pc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pc)


@pytest.mark.parametrize("branch", [
    "feat/71-016-results-loader",       # issue 71, spec 016's user story
    "fix/72-volume-log-append",
    "docs/80-branch-naming",
    "data/81-nhanes-2015",
    "ci/82-pr-conventions",
    "chore/83-bump-kaggle-cli",
    "spec/84-017-pipeline-doctor",
    "feat/DENT-123-results-loader",     # a Jira key works too
])
def test_good_branch_names(branch):
    assert pc.branch_problems(branch) == []


@pytest.mark.parametrize("branch, why", [
    ("my-branch", "type"),
    ("feature/71-x", "type"),                       # feat, not feature
    ("feat/results-loader", "issue"),               # no ticket
    ("feat/71-Results_Loader", "lowercase"),
    ("feat/71-" + "x" * 50, "long"),
    ("003-radiograph-structured-data", "type"),     # Spec Kit's default: needs the type and issue
])
def test_bad_branch_names_say_why(branch, why):
    problems = pc.branch_problems(branch)
    assert problems and why in " ".join(problems).lower()


@pytest.mark.parametrize("branch", ["dependabot/pip/pandas-3.0", "kaggle-results/medgemma-1.5-4b-it-123"])
def test_branches_named_by_a_tool_are_allowed(branch):
    assert pc.branch_problems(branch) == []


def test_an_agent_sessions_claude_branch_is_not_allowed_and_says_what_to_do():
    # issue #116: sessions are assigned claude/<name>; the work moves to <type>/<issue>-<slug> (AGENTS.md rule 4)
    problems = pc.branch_problems("claude/focused-mccarthy-gy9rjp")
    assert problems and "<type>/<issue>-<slug>" in problems[0] and "AGENTS.md" in problems[0]


@pytest.mark.parametrize("body", ["Closes #71", "fixes #72.", "Part of the work.\n\nRefs #73", "Closes DENT-123", "Resolves #9"])
def test_issue_link_found(body):
    assert pc.issue_link(body)


@pytest.mark.parametrize("body", ["", None, "See issue 71", "#71 only mentioned", "Closes 71"])
def test_no_issue_link(body):
    assert not pc.issue_link(body)


def test_check_needs_an_issue_link_except_on_tool_branches():
    assert pc.check("feat/71-x", "Closes #71") == []
    assert any("issue" in p.lower() for p in pc.check("feat/71-x", ""))
    assert pc.check("kaggle-results/x-1", "") == []          # made by a workflow from a run, not a story
    assert pc.check("dependabot/pip/x", "") == []


def test_workflow_runs_the_check_on_every_pr_without_interpolating_text():
    import yaml
    text = (REPO_ROOT / ".github" / "workflows" / "pr-conventions.yml").read_text()
    wf = yaml.safe_load(text)
    on = wf.get("on", wf.get(True))
    assert "pull_request" in on and "edited" in on["pull_request"]["types"]
    run = " ".join(s.get("run", "") for s in wf["jobs"]["check"]["steps"])
    assert "pr_conventions.py" in run
    assert "${{" not in run              # branch and body reach the script via env, never pasted into shell


def test_rule_is_written_down_for_every_agent():
    agents = (REPO_ROOT / "AGENTS.md").read_text()
    assert "## Branches and issues" in agents and "Closes #" in agents
    assert "Branches and issues" in (REPO_ROOT / "CLAUDE.md").read_text()


# What an issue says (AGENTS.md, issue #700): the issue a pull request links has four parts, written before the work.
FULL = """## Problem
The loader drops rows with no clinic.

## Done when
- `load_results` keeps a row whose clinic is empty.

## Contract
- `load_results(path, keep_empty_clinic=True)`

## Read first
- specs/016-results-loader/spec.md, user story 2
"""


@pytest.mark.parametrize("body, number", [
    ("Closes #71", 71), ("Fixes #8 and more", 8), ("Refs #12: one part of the story", 12),
    ("Some text first.\n\nResolves #305", 305), ("Closes DENT-123", None), ("no link here", None), (None, None),
])
def test_the_linked_issue_number_is_read_from_the_description(body, number):
    assert pc.linked_issue_number(body) == number


def test_an_issue_with_the_four_parts_passes():
    assert pc.issue_problems(FULL, "2026-11-20T10:00:00Z") == []
    bold = FULL.replace("## Problem", "**Problem:**").replace("## Done when", "**Done when:**")
    assert pc.issue_problems(bold, "2026-11-20T10:00:00Z") == []          # a bold label works as well as a heading


@pytest.mark.parametrize("part", ["Problem", "Done when", "Contract", "Read first"])
def test_a_missing_part_is_named(part):
    without = "## ".join(block for block in FULL.split("## ") if not block.startswith(part))
    problems = pc.issue_problems(without, "2026-11-20T10:00:00Z")
    assert len(problems) == 1 and part in problems[0] and "AGENTS.md" in problems[0]


def test_issues_opened_before_the_rule_are_not_held_to_it():
    assert pc.issue_problems("Describes the problem in one paragraph.", "2026-11-13T23:59:59Z") == []
    assert pc.issue_problems("Describes the problem in one paragraph.", "2026-11-14T00:00:00Z") != []
    assert pc.issue_problems(None, "2026-11-20T10:00:00Z") != []            # an empty issue has none of the parts


def test_check_reports_the_issue_when_it_is_given():
    assert pc.check("feat/71-x", "Closes #71", issue=(FULL, "2026-11-20T10:00:00Z")) == []
    found = pc.check("feat/71-x", "Closes #71", issue=("Just a title.", "2026-11-20T10:00:00Z"))
    assert found and "Contract" in " ".join(found)
    assert pc.check("feat/71-x", "Closes #71") == []                         # no issue fetched: only branch and link
    assert pc.check("dependabot/pip/x", "", issue=("", "2026-11-20T10:00:00Z")) == []   # a tool's branch has no story


def test_workflow_lets_the_check_read_the_issue():
    import yaml
    wf = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "pr-conventions.yml").read_text())
    assert wf["permissions"].get("issues") == "read"
    env = {}
    for s in wf["jobs"]["check"]["steps"]:
        env.update(s.get("env") or {})
    assert "GITHUB_TOKEN" in env            # passed to the script, which reads the linked issue with it
