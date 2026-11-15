"""Configuration, secrets, alert severity and failure-handling rules stay written down and usable (issue #70)."""

import datetime as dt
import re

import yaml

from health_transformation_lab_nlp.paths import REPO_ROOT

REGISTER = REPO_ROOT / "ops" / "secrets_register.yaml"
FIELDS = {"name", "what", "made_in", "scope", "stored_in", "used_by", "lifetime", "expires", "owner", "if_it_expires"}


def _register():
    return yaml.safe_load(REGISTER.read_text())["credentials"]


def _credential_rows(agents: str) -> list[str]:
    """The first cell of each row of AGENTS.md's credentials table, indented or not, without its header and rule
    line, and with backticks removed so "`gh` login" reads as the register's "gh login" (#785)."""
    lines = agents[agents.index("| Credential |"):].splitlines()[2:]     # the header and the |---| rule
    rows = []
    for line in lines:
        cells = line.strip()
        if not cells.startswith("|"):
            break                                                       # the table has ended
        rows.append(cells.strip("|").split("|")[0].strip().replace("`", ""))
    return rows


def _unregistered(rows: list[str], names: set[str]) -> list[str]:
    """The rows that name no credential in the register."""
    return [r for r in rows if not any(n in r for n in names)]


def test_every_credential_in_agents_md_is_in_the_register():
    rows = _credential_rows((REPO_ROOT / "AGENTS.md").read_text())
    assert rows and "Credential" not in rows, rows                    # the rows, not the header (#785)
    missing = _unregistered(rows, {c["name"] for c in _register()})
    assert not missing, f"AGENTS.md lists {missing} but ops/secrets_register.yaml doesn't"


def test_the_credentials_table_reader_finds_indented_rows_and_a_missing_credential():
    """The table sits indented under a bullet since 8cadc13, and the old reader then matched only its header, so
    the check above passed without looking at a row (#785)."""
    text = ("Intro.\n\n  | Credential | Where | Scope | Goes to |\n  |---|---|---|---|\n"
            "  | `a` token for x | x | y | z |\n  | b key (note) | x | y | z |\n\nAfter the table.\n")
    assert _credential_rows(text) == ["a token for x", "b key (note)"]   # backticks gone, header and rule skipped
    assert _unregistered(_credential_rows(text), {"a token"}) == ["b key (note)"]


def test_register_entries_say_when_they_expire_and_who_renews_them():
    for c in _register():
        assert FIELDS <= set(c), (c.get("name"), FIELDS - set(c))
        e = c["expires"]
        assert e in ("never", "unknown") or isinstance(e, dt.date), (c["name"], e)   # a date, never, or unknown


def test_register_holds_no_secret_values():
    text = REGISTER.read_text()
    for pattern in (r"dapi[0-9a-f]{20,}", r"hf_[A-Za-z0-9]{20,}", r"InstrumentationKey=[0-9a-f-]{20,}",
                    r"KGAT_[A-Za-z0-9]{10,}", r"[A-Za-z0-9+/]{40,}={0,2}"):
        assert not re.search(pattern, text), pattern


def test_agents_md_has_the_operations_rules():
    agents = (REPO_ROOT / "AGENTS.md").read_text()
    for heading in ("## Configuration and secrets", "## Alerts and severity", "## Failures, retries and reruns",
                    "## Ingestion and schema drift"):
        assert heading in agents, heading
    assert "docs/operations.md" in agents and "ops/secrets_register.yaml" in agents
    for sev in ("SEV1", "SEV2", "SEV3", "SEV4"):
        assert sev in agents, sev


def test_a_quota_is_raised_before_it_is_worked_around():
    """On November 11, 2026 Kaggle's weekly GPU hours ran out and a planned rerun moved to Colab. Nobody had checked
    that a Colab subscription linked to the Kaggle account adds hours on Kaggle itself (#698). The rule, the how-to
    with its source, and the action beside the budget stay written down."""
    agents = (REPO_ROOT / "AGENTS.md").read_text()
    rules = agents[agents.index("## Failures, retries and reruns"):agents.index("## Ingestion and schema drift")]
    assert "A quota or allowance that stops a run is raised before it is worked around" in rules
    assert "kaggle/README.md" in rules and "what was checked" in rules
    readme = (REPO_ROOT / "kaggle" / "README.md").read_text()
    how_to = readme[readme.index("## GPU hours"):readme.index("## When something fails")]
    for fact in ("Link to Colab", "15 or 30", "https://www.kaggle.com/product-announcements/575468",
                 "https://www.kaggle.com/docs/notebooks", "experimental", "Maximum weekly GPU quota"):
        assert fact in how_to, fact
    assert "[GPU hours](#gpu-hours)" in readme[readme.index("## When something fails"):]
    budgets = yaml.safe_load((REPO_ROOT / "ops" / "budgets.yaml").read_text())["budgets"]
    allowance = next(b for b in budgets if b["budget_name"] == "kaggle_gpu_allowance")
    assert "kaggle/README.md" in allowance["action_text"]


def test_operations_doc_cites_its_databricks_facts():
    doc = (REPO_ROOT / "docs" / "operations.md").read_text()
    for topic in ("Repair", "cleanSource", "schemaEvolutionMode", "rescuedDataColumn", "730 days", "digest"):
        assert topic in doc, topic
    assert doc.count("https://docs.databricks.com") >= 5


def test_review_rubric_checks_config_secrets_and_idempotency():
    rubric = (REPO_ROOT / ".claude" / "review-rubric.md").read_text()
    for rule in ("Configuration", "Secrets register", "Idempotent writes"):
        assert f"| {rule} |" in rubric, rule


def test_chart_review_agent_notebook_number_is_free():
    # 10_load_results.py took number 10 (spec 016)
    text = (REPO_ROOT / "databricks" / "agents" / "chart_review" / "AGENTS.md").read_text()
    assert "10_chart_review_agent.py" not in text


def test_no_register_value_is_cut_short_by_a_yaml_comment():
    """In YAML, a space and then # starts a comment, so `(issue #495)` silently drops the rest of the value (#499)."""
    from health_transformation_lab_nlp.paths import REPO_ROOT
    lines = (REPO_ROOT / "ops" / "secrets_register.yaml").read_text().splitlines()
    cut = [f"line {n}: {line.strip()[:80]}" for n, line in enumerate(lines, 1)
           if " #" in line and not line.lstrip().startswith("#")]
    assert not cut, "write 'issue 495', not '#495', inside a register value:\n" + "\n".join(cut)


def test_the_agents_longer_lived_workspace_token_is_a_recorded_decision():
    """The rule said 15 days at most; on November 15, 2026 the owner kept a one-year token for agent sessions (#749).
    The register's entry points to the decision record, and AGENTS.md says where the token lives and that the
    variable holds only a placeholder."""
    entry = next((c for c in _register() if c["name"] == "Workspace personal access token"), None)
    assert entry, "ops/secrets_register.yaml has no 'Workspace personal access token' entry"
    adr = re.search(r"ADR (\d{4})", entry["lifetime"])
    assert adr, entry["lifetime"]
    files = list((REPO_ROOT / "docs" / "adr").glob(f"{adr.group(1)}-*.md"))
    assert len(files) == 1 and "Status: accepted" in files[0].read_text(), files
    agents = (REPO_ROOT / "AGENTS.md").read_text().splitlines()
    row = next((line for line in agents if line.lstrip().startswith("| Workspace personal access token")), None)
    assert row, "AGENTS.md's credentials table has no 'Workspace personal access token' row"
    assert "network secret" in row and "placeholder" in row and f"ADR {adr.group(1)}" in row, row
