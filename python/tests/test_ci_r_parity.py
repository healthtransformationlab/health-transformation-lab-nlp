"""Issue #677: the R parity job can't hang for hours, and installing R survives a short fault of the package servers.

On November 11, 2026 the runner couldn't resolve Ubuntu's package servers: `setup-r` retried with no end in sight (one
run was cancelled after 100 minutes; the job had no timeout, so GitHub's six hours applied), and once the servers came
back a stale package list made it fail with a 404. These checks read the workflow itself.
"""
import yaml

from health_transformation_lab_nlp.paths import REPO_ROOT

WF = REPO_ROOT / ".github" / "workflows" / "ci.yml"


def _steps() -> tuple[dict, list[dict]]:
    job = yaml.safe_load(WF.read_text())["jobs"]["r-parity"]
    return job, job["steps"]


def _setup_r(steps: list[dict]) -> list[int]:
    return [i for i, s in enumerate(steps) if str(s.get("uses", "")).startswith("r-lib/actions/setup-r")]


def test_the_job_has_a_timeout_measured_in_minutes():
    job, _ = _steps()
    assert 0 < int(job["timeout-minutes"]) <= 30


def test_the_package_lists_are_refreshed_with_retries_before_r_is_installed():
    _, steps = _steps()
    first_setup = _setup_r(steps)[0]
    refresh = [s for s in steps[:first_setup] if "apt-get update" in str(s.get("run", ""))]
    assert refresh, "no apt-get update step before setup-r"
    assert "for " in refresh[0]["run"] and "sleep" in refresh[0]["run"], "the refresh is not retried"


def test_a_failed_install_of_r_is_tried_once_more_and_each_try_has_its_own_timeout():
    _, steps = _steps()
    first, *rest = _setup_r(steps)
    assert steps[first].get("continue-on-error") is True and steps[first].get("id")
    assert rest, "no second setup-r step"
    retry = steps[rest[0]]
    assert retry.get("if") == f"steps.{steps[first]['id']}.outcome == 'failure'"
    assert all(int(steps[i]["timeout-minutes"]) <= 10 for i in (first, rest[0]))
