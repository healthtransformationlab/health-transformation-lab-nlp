"""A machine's own Claude Code permission rules (for example, for a production database) live in
.claude/settings.local.json, never in the shared .claude/settings.json. The repo's .gitignore keeps that file out of
git on every machine, whatever the user's global gitignore says (#872)."""

import subprocess

from health_transformation_lab_nlp.paths import REPO_ROOT


def test_claude_local_settings_are_ignored_by_the_repo_gitignore():
    # --no-index: ask about the rules, not whether the file happens to be tracked; core.excludesFile=/dev/null:
    # count only the repo's own .gitignore, not the user's global one.
    result = subprocess.run(
        ["git", "-c", "core.excludesFile=/dev/null", "check-ignore", "--no-index", "-q",
         ".claude/settings.local.json"],
        cwd=REPO_ROOT, capture_output=True,
    )
    assert result.returncode == 0, ".gitignore must list .claude/settings.local.json"
