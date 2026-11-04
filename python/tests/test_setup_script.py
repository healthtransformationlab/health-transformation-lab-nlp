"""databricks/setup/create_service_principal.sh and the workflows that sign in as its principal.
(The script itself needs a workspace; these check what can be checked without one.)"""

import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "databricks" / "setup" / "create_service_principal.sh"


def test_script_is_valid_bash_and_strict():
    text = SCRIPT.read_text()
    assert text.startswith("#!/usr/bin/env bash") and "set -euo pipefail" in text
    subprocess.run(["bash", "-n", str(SCRIPT)], check=True)


def test_script_grants_what_a_deploy_as_the_principal_needs():
    text = SCRIPT.read_text()
    for need in ("workspace-access", "databricks-sql-access",   # workspace APIs; warehouse lookup
                 "CREATE_CATALOG", "put-acl"):
        assert need in text, need
    # the bundle creates the catalog, schemas and volume (unity_catalog.yml); a catalog
    # made here first would make the deploy fail on "already exists"
    assert "catalogs create" not in text and "schemas create" not in text
    # the secret is made by hand and goes straight into GitHub: the script only prints the command
    code, printed = text.split("cat <<EOF")
    assert "service-principal-secrets-proxy" not in code and "service-principal-secrets-proxy create" in printed


@pytest.mark.skipif(not shutil.which("bash"), reason="no bash")
@pytest.mark.parametrize("target", ["dev", "uat", "prod"])
def test_script_reads_names_and_scope_from_the_bundle(target):
    """--print-config prints what the script would use for a target, without a workspace."""
    out = subprocess.run(["bash", str(SCRIPT), target, "--print-config"],
                         capture_output=True, text=True, check=True).stdout.split()
    b = yaml.safe_load((ROOT / "databricks.yml").read_text())
    v = {k: x.get("default") for k, x in b["variables"].items()}
    v.update(b["targets"][target].get("variables", {}))
    assert out == [f"dental_omop_nlp_{target}_sp", f"dental_omop_nlp_{target}_admin",
                   v["catalog"], v["hf_secret_scope"]]


def test_unknown_target_is_refused():
    r = subprocess.run(["bash", str(SCRIPT), "staging", "--print-config"], capture_output=True, text=True,
                       check=False)
    assert r.returncode != 0 and "staging" in r.stderr


@pytest.mark.parametrize("wf", ["ci.yml", "deploy.yml", "auth_check.yml"])
def test_workflows_read_host_and_client_id_as_variables(wf):
    """Host and client ID are identifiers (GitHub variables); only the client secret is a secret.
    A secret fallback keeps environments set up the older way working."""
    text = (ROOT / ".github" / "workflows" / wf).read_text()
    assert "${{ vars.DATABRICKS_HOST || secrets.DATABRICKS_HOST }}" in text
    assert "${{ vars.DATABRICKS_CLIENT_ID || secrets.DATABRICKS_CLIENT_ID }}" in text
    assert "${{ secrets.DATABRICKS_CLIENT_SECRET }}" in text


@pytest.mark.parametrize("wf", ["ci.yml", "deploy.yml"])
def test_databricks_steps_wait_for_the_client_secret(wf):
    """A host alone (set before the principal exists) must skip, not fail on sign-in."""
    text = (ROOT / ".github" / "workflows" / wf).read_text()
    assert "env.DATABRICKS_HOST != ''" not in text and "env.DATABRICKS_HOST == ''" not in text
    assert "env.DATABRICKS_CLIENT_SECRET != ''" in text


SIGNIN = ROOT / ".github" / "actions" / "databricks-signin" / "action.yml"


@pytest.mark.parametrize("wf", ["ci.yml", "deploy.yml", "auth_check.yml"])
def test_databricks_credentials_only_reach_the_cli_trimmed(wf):
    """Raw values never sit in a job's env; the sign-in action trims them before any databricks step."""
    doc = yaml.safe_load((ROOT / ".github" / "workflows" / wf).read_text())
    for name, job in doc["jobs"].items():
        steps = job.get("steps", [])
        uses_cli = [i for i, s in enumerate(steps) if "databricks " in s.get("run", "")]
        if not uses_cli:
            continue
        for scope in [job.get("env", {}), *(s.get("env", {}) for s in steps)]:
            assert not {"DATABRICKS_HOST", "DATABRICKS_CLIENT_ID", "DATABRICKS_CLIENT_SECRET"} & set(scope), name
        signin = [i for i, s in enumerate(steps) if s.get("uses") == "./.github/actions/databricks-signin"]
        assert signin and signin[0] < min(uses_cli), name


@pytest.mark.skipif(not shutil.which("bash"), reason="no bash")
def test_signin_action_strips_pasted_whitespace_and_masks_the_secret(tmp_path):
    """A value pasted from Windows ends in \\r\\n; sent as is, sign-in fails with invalid_client."""
    step = yaml.safe_load(SIGNIN.read_text())["runs"]["steps"][0]
    out = tmp_path / "github_env"
    r = subprocess.run(["bash", "-c", step["run"]], capture_output=True, text=True, check=True,
                       env={"PATH": "/usr/bin:/bin", "GITHUB_ENV": str(out),
                            "IN_HOST": " https://example.cloud.databricks.com/\r\n",
                            "IN_CLIENT_ID": "b0a70ecf-0000\r\n", "IN_CLIENT_SECRET": "dose123 \r\n"})
    assert dict(line.split("=", 1) for line in out.read_text().splitlines()) == {
        "DATABRICKS_HOST": "https://example.cloud.databricks.com",
        "DATABRICKS_CLIENT_ID": "b0a70ecf-0000", "DATABRICKS_CLIENT_SECRET": "dose123"}
    assert "::add-mask::dose123" in r.stdout


def test_actions_run_on_node_24():
    """checkout@v4 and setup-python@v5 run on Node 20, which GitHub has deprecated."""
    for wf in (ROOT / ".github" / "workflows").glob("*.yml"):
        text = wf.read_text()
        assert "actions/checkout@v4" not in text and "actions/setup-python@v5" not in text, wf.name


def test_merge_to_main_deploys_dev_and_uat_and_a_manual_run_only_its_target():
    """Spec 012 US1: dev stays current. A push deploys every environment (each still skips
    without its client secret); workflow_dispatch deploys the one target chosen."""
    doc = yaml.safe_load((ROOT / ".github" / "workflows" / "deploy.yml").read_text())
    job = doc["jobs"]["deploy"]
    matrix = job["strategy"]["matrix"]["target"]
    assert "workflow_dispatch" in matrix and "github.event.inputs.target" in matrix
    assert '["dev","uat"]' in matrix.replace(" ", "")
    assert job["strategy"]["fail-fast"] is False          # dev failing mustn't cancel uat
    assert job["environment"] == "${{ matrix.target }}" and job["env"]["TARGET"] == "${{ matrix.target }}"
    assert "deploy-${{ matrix.target }}" in str(job.get("concurrency", ""))


def test_deploy_uses_the_direct_engine_and_never_hides_a_state_migration():
    """unity_catalog.yml's catalog resource deploys only with the direct engine. Moving Terraform state over
    is a one-off manual step (docs/deployment.md), not a CI step whose failure is swallowed: a migrate that
    failed for a real reason would let the deploy treat the target as new and duplicate its jobs."""
    doc = yaml.safe_load((ROOT / ".github" / "workflows" / "deploy.yml").read_text())
    steps = doc["jobs"]["deploy"]["steps"]
    names = [s.get("name", "") for s in steps]
    assert not any("bundle deployment migrate" in s.get("run", "") for s in steps)
    for i, s in enumerate(steps):
        if "bundle validate" in s.get("run", "") or "bundle deploy " in s.get("run", "") or "bundle run" in s.get("run", ""):
            assert s.get("env", {}).get("DATABRICKS_BUNDLE_ENGINE") == "direct", names[i]
    assert "bundle deployment migrate" in (ROOT / "docs" / "deployment.md").read_text()


def test_deploy_adopts_a_catalog_made_by_hand_before_deploying():
    """Default Storage workspaces can't create a catalog through the API the bundle uses, so it's made
    with SQL CREATE CATALOG (docs/deployment.md) and the deploy binds it, once, with the direct engine."""
    doc = yaml.safe_load((ROOT / ".github" / "workflows" / "deploy.yml").read_text())
    steps = doc["jobs"]["deploy"]["steps"]
    names = [s.get("name", "") for s in steps]
    bind = next(i for i, s in enumerate(steps) if "bundle deployment bind health_transformation_lab health_transformation_lab" in s.get("run", ""))
    assert bind < names.index("Deploy") and "--auto-approve" in steps[bind]["run"]
    assert steps[bind].get("env", {}).get("DATABRICKS_BUNDLE_ENGINE") == "direct"


def test_every_workflow_can_be_started_by_hand():
    """Actions -> pick the workflow -> Run workflow: every workflow has a manual trigger."""
    for f in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        doc = yaml.safe_load(f.read_text())
        on = doc.get("on", doc.get(True))           # YAML 1.1 reads a bare `on:` key as True
        assert isinstance(on, dict) and "workflow_dispatch" in on, f.name


def test_workflow_names_say_what_they_do():
    """The Actions sidebar shows only `name` (no description), so it has to say what the workflow does:
    a few plain words, not a file-style id like "ci" or "auth_check"."""
    for f in sorted((ROOT / ".github" / "workflows").glob("*.yml")):
        name = yaml.safe_load(f.read_text())["name"]
        assert len(name.split()) >= 4 and "_" not in name and name[0].isupper(), (f.name, name)


def test_manual_runs_default_to_dev_the_only_environment_that_exists():
    """Only dev exists; uat and prod stay possible (they skip until their secret is set) but a manual run
    shouldn't default to one of them, and the deploy name shouldn't promise them."""
    for f in ("deploy.yml", "auth_check.yml"):
        doc = yaml.safe_load((ROOT / ".github" / "workflows" / f).read_text())
        on = doc.get("on", doc.get(True))
        assert on["workflow_dispatch"]["inputs"]["target"]["default"] == "dev", f
    name = yaml.safe_load((ROOT / ".github" / "workflows" / "deploy.yml").read_text())["name"]
    assert "dev" in name and "uat" not in name and "prod" not in name, name



def test_no_system_table_grants_are_needed():
    """#524: the doctor reads the Jobs API, so the system.lakeflow grant script (#504) is gone; on Free Edition
    no one we control could run it anyway (the metastore belongs to Databricks)."""
    assert not (ROOT / "databricks" / "setup" / "grant_system_tables.sh").exists()
    assert "grant_system_tables" not in SCRIPT.read_text()
