"""Spec 041 US1 (#856): the bundle declares the agent-trace schema and an experiment whose traces are stored there.

The experiment's trace location cannot be changed after it is created, so its names are tested here. The Databricks
CLI reads `trace_location` from 1.9.0; CI and the deploy pin one version at or above it.
"""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
TRACES = ROOT / "databricks/resources/agent_traces.yml"
CATALOG = "${resources.catalogs.health_transformation_lab.name}"
ADMIN = "dental_omop_nlp_${bundle.target}_admin"
FIRST_CLI_WITH_TRACE_LOCATION = (1, 9, 0)
SETUP_CLI = re.compile(r"databricks/setup-cli@v(\d+)\.(\d+)\.(\d+)")


def _resources():
    return yaml.safe_load(TRACES.read_text())["resources"]


def test_the_trace_schema_is_declared_once_and_never_destroyed():
    schemas = _resources()["schemas"]
    assert set(schemas) == {"agent_trace"}
    sc = schemas["agent_trace"]
    assert sc["name"] == "ops_agent_trace" and sc["catalog_name"] == CATALOG
    assert sc["lifecycle"]["prevent_destroy"] is True
    assert "trace" in sc["comment"].lower() and "spec 041" in sc["comment"].lower()
    others = [p for p in (ROOT / "databricks").rglob("*.yml") if p != TRACES and "ops_agent_trace" in p.read_text()]
    assert others == [], f"ops_agent_trace is declared outside {TRACES.name}: {others}"


def test_the_schema_grants_modify_and_select_by_name():
    """Databricks: ALL_PRIVILEGES on the catalog is not enough for trace tables; MODIFY and SELECT are granted."""
    grants = _resources()["schemas"]["agent_trace"]["grants"]
    assert grants == [{"principal": ADMIN, "privileges": ["USE_SCHEMA", "CREATE_TABLE", "MODIFY", "SELECT"]}]


def test_the_experiment_stores_its_traces_in_the_schema_under_one_prefix():
    exps = _resources()["experiments"]
    assert set(exps) == {"coding_agent_runs"}
    exp = exps["coding_agent_runs"]
    assert exp["name"] == "/Shared/coding-agent-runs"
    assert exp["trace_location"] == {"uc_trace_location": {
        "catalog": CATALOG, "schema": "${resources.schemas.agent_trace.name}", "table_prefix": "coding_agent"}}
    assert exp["lifecycle"]["prevent_destroy"] is True


def test_ci_and_deploy_pin_one_cli_that_reads_trace_location():
    pins = set()
    for wf in ("ci.yml", "deploy.yml"):
        found = SETUP_CLI.findall((ROOT / ".github/workflows" / wf).read_text())
        assert found, f"{wf} does not pin databricks/setup-cli"
        pins |= {tuple(int(x) for x in v) for v in found}
    assert len(pins) == 1, f"ci.yml and deploy.yml pin different CLI versions: {sorted(pins)}"
    assert pins.pop() >= FIRST_CLI_WITH_TRACE_LOCATION


def test_the_bundle_includes_the_file():
    root = yaml.safe_load((ROOT / "databricks.yml").read_text())
    assert any(TRACES.relative_to(ROOT).match(inc) for inc in root["include"])
