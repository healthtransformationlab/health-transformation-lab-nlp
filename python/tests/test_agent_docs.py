"""AGENTS.md holds the rules every coding agent follows; CLAUDE.md imports it and adds only Claude Code's
own workflow, so the rules live in one place."""

from health_transformation_lab_nlp.paths import REPO_ROOT

AGENTS = REPO_ROOT / "AGENTS.md"
CLAUDE = REPO_ROOT / "CLAUDE.md"
RULES = ("Synthetic only. No PHI, ever.", "Python and R stay in parity.", "Test first.",
         "Label simulated output as simulated.", "never use\n  `mode: development`", "| Credential | Where it's made |")


def test_agents_md_has_every_shared_rule():
    text = AGENTS.read_text()
    for heading in ("## Ground rules", "## When a change needs a spec", "## Commands", "## Conventions"):
        assert heading in text, heading
    for rule in RULES:
        assert rule in text, rule


def test_claude_md_imports_agents_md_and_does_not_repeat_it():
    text = CLAUDE.read_text()
    assert "@AGENTS.md" in text.split("##")[0]                    # imported before any section
    for rule in RULES:
        assert rule not in text, rule                              # one copy only: AGENTS.md
    assert "Superpowers" in text and "/speckit-specify" in text     # Claude Code's own workflow stays here


def test_reviews_check_against_both_files():
    for f in (".claude/review-rubric.md", ".claude/commands/pr-review.md"):
        assert "AGENTS.md" in (REPO_ROOT / f).read_text(), f


AGENT_DIR = REPO_ROOT / "databricks" / "agents" / "chart_review"


def test_chart_review_agent_folder_has_its_own_agent_rules():
    """The Databricks chart review agent gets its own AGENTS.md (what it is, its tools, rules, evaluation),
    and a CLAUDE.md that imports it, because Claude Code reads nested CLAUDE.md files, not AGENTS.md."""
    text = (AGENT_DIR / "AGENTS.md").read_text()
    for heading in ("## What it is", "## Rules", "## Tools", "## Output", "## Evaluation", "## Deployment", "## Layout"):
        assert heading in text, heading
    assert "spec" in text.lower() and "agent:chart_review" in text          # needs a spec; how its results are named
    assert (AGENT_DIR / "CLAUDE.md").read_text().strip().splitlines()[-1] == "@AGENTS.md"
    assert "databricks/agents/chart_review/AGENTS.md" in AGENTS.read_text()  # the root file points to it


def test_agents_md_says_what_an_issue_holds_and_the_template_and_check_agree():
    """76 of the 93 tasks mined from this repository had tests that needed something the issue never gave (#700).
    The four parts of an issue are named once in AGENTS.md; the issue template and the pull-request check use the
    same names."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("pr_conventions", REPO_ROOT / ".github" / "scripts" / "pr_conventions.py")
    pc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pc)
    text = AGENTS.read_text()
    section = text[text.index("## What an issue says"):text.index("## Configuration and secrets")]
    template = (REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "work-item.md").read_text()
    assert pc.ISSUE_PARTS == ("Problem", "Done when", "Contract", "Read first")
    for part in pc.ISSUE_PARTS:
        assert f"**{part}:**" in section, part
        assert f"## {part}" in template, part
    assert "before the first commit" in section and "dated line" in section
    assert "data/tasks/screening/README.md" in section            # the reason is a committed count, not a memory
    assert pc.PARTS_SINCE in section.replace("November 14, 2026", pc.PARTS_SINCE)


def test_agents_md_puts_the_spec_and_the_data_contract_before_the_code():
    """The owner's additions to the issue rule (#700): an epic issue over a spec's user stories, the spec written
    and naming its story before the story's code, and a data contract (grain, columns, keys) for a table or file."""
    text = AGENTS.read_text()
    branches = text[text.index("## Branches and issues"):text.index("## What an issue says")]
    section = text[text.index("## What an issue says"):text.index("## Configuration and secrets")]
    assert "`EPIC`" in branches and "sub-issue" in branches
    assert "**Spec before code.**" in section and "plan.md" in section
    assert "grain" in section and "SQL and data names" in section
    template = (REPO_ROOT / ".github" / "ISSUE_TEMPLATE" / "work-item.md").read_text()
    assert "grain" in template
