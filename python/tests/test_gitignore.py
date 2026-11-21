"""A machine's own Claude Code permission rules (for example, for a production database) live in
.claude/settings.local.json, never in the shared .claude/settings.json. The repo's .gitignore keeps that file out of
git on every machine, whatever the user's global gitignore says (#872)."""

import json
import subprocess

from health_transformation_lab_nlp.paths import REPO_ROOT


def test_claude_local_settings_are_ignored_by_the_repo_gitignore():
    # --no-index: ask about the rules, not whether the file happens to be tracked; core.excludesFile=/dev/null:
    # count only the repo's own .gitignore, not the user's global one.
    result = subprocess.run(
        ["git", "-c", "core.excludesFile=/dev/null", "check-ignore", "--no-index", "-q",
         ".claude/settings.local.json"],
        cwd=REPO_ROOT, capture_output=True, check=False,
    )
    assert result.returncode == 0, ".gitignore must list .claude/settings.local.json"


TEMPLATE = REPO_ROOT / ".claude" / "settings.local.example.json"
NEON_SIZE_RULE = 'Bash(psql "$NEON_DATABASE_URL" -Atc "select pg_size_pretty(pg_database_size(current_database()))")'


def test_local_settings_template_is_committed_and_lists_the_standard_rules():
    # The shared template each machine copies to .claude/settings.local.json, so local rules stay the same everywhere.
    tracked = subprocess.run(["git", "ls-files", "--error-unmatch", str(TEMPLATE)],
                             cwd=REPO_ROOT, capture_output=True, check=False)
    assert tracked.returncode == 0, ".claude/settings.local.example.json must be committed"
    allow = json.loads(TEMPLATE.read_text())["permissions"]["allow"]
    assert NEON_SIZE_RULE in allow


def test_claude_md_says_to_copy_the_template():
    assert "cp .claude/settings.local.example.json .claude/settings.local.json" in (REPO_ROOT / "CLAUDE.md").read_text()


def test_template_rules_name_exact_commands_without_wildcards():
    # A prefix rule ending in :* after free text (SQL) also matches "...; drop table x" or a trailing -f file.
    allow = json.loads(TEMPLATE.read_text())["permissions"]["allow"]
    assert [rule for rule in allow if ":*" in rule or rule.endswith("*)")] == []
