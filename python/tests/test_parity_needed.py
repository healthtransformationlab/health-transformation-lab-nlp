"""CI runs R parity on a pull request only when a change can reach it (issue #152): .github/scripts/parity_needed.py
works out what make_parity_inputs.sh depends on and compares it with the changed files."""

import importlib.util

import pytest

from health_transformation_lab_nlp.paths import REPO_ROOT

_spec = importlib.util.spec_from_file_location("parity_needed", REPO_ROOT / ".github" / "scripts" / "parity_needed.py")
pn = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pn)


@pytest.fixture(scope="module")
def deps():
    return pn.dependencies(REPO_ROOT)


def test_the_pipeline_scripts_and_the_modules_they_import_are_dependencies(deps):
    assert "python/scripts/make_parity_inputs.sh" in deps
    assert "python/scripts/13_reliability.py" in deps                 # run by make_parity_inputs.sh
    assert "python/health_transformation_lab_nlp/reliability.py" in deps            # imported by it
    assert "python/health_transformation_lab_nlp/labels.py" in deps                 # imported through other modules
    assert "python/health_transformation_lab_nlp/__init__.py" in deps
    assert "python/health_transformation_lab_nlp/readme_results.py" in deps        # 36_judge_scorecard.py imports it


def test_modules_the_pipeline_never_imports_are_not_dependencies(deps):
    for path in ("python/health_transformation_lab_nlp/dashboards.py", "python/health_transformation_lab_nlp/grader_tables.py",
                 "python/scripts/35_readme_results.py"):
        assert path not in deps, path


@pytest.mark.parametrize("changed", [
    ["r/R/04_reliability.R"],
    ["python/health_transformation_lab_nlp/reliability.py"],
    ["data/datasets/ai_predictions_bert-base.csv"],
    ["eval/score.py"],
    ["python/pyproject.toml"],
    [".github/workflows/ci.yml"],
    [".github/scripts/parity_needed.py"],
    ["docs/results.md", "python/health_transformation_lab_nlp/labels.py"],      # one reaching file is enough
])
def test_a_change_parity_reads_runs_it(changed):
    assert pn.needed(changed, REPO_ROOT)


@pytest.mark.parametrize("changed", [
    [],
    ["README.md", "docs/edr/README.md"],
    ["python/tests/test_decks.py"],
    ["python/health_transformation_lab_nlp/dashboards.py", "databricks/dashboards/dq_grader.lvdash.json"],
    ["python/scripts/35_readme_results.py", "python/scripts/42_build_dashboards.py"],
    ["databricks/notebooks/10_load_results.py", "infra/azure/main.tf"],
])
def test_a_change_parity_never_reads_skips_it(changed):
    assert not pn.needed(changed, REPO_ROOT)


def test_ci_skips_parity_only_on_pull_requests_and_runs_it_weekly():
    import yaml
    wf = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text())
    job = wf["jobs"]["r-parity"]
    assert job["needs"] == "changes" and job["if"] == "needs.changes.outputs.parity == 'true'"
    step = wf["jobs"]["changes"]["steps"][-1]["run"]
    assert 'github.event_name }}" = "pull_request"' in step and "needed=true" in step   # everything else: full run
    assert wf[True]["schedule"]                                                            # the weekly full run


def test_the_package_it_follows_exists_and_is_reached(deps):
    # #187: after the rename the package path didn't exist, so no module was ever a dependency
    assert (REPO_ROOT / pn.PACKAGE / "__init__.py").exists()
    assert sum(p.startswith(pn.PACKAGE + "/") for p in deps) >= 10


# Issue #244: every PR reports every check, so the checks can be required on main. The Python tests always run: many
# of them read the docs (wording, citations, links, decks). On a docs-only PR the jobs docs can't affect (Postgres,
# Terraform, bundle) are skipped instead, and a skipped job counts as passing; any other change runs them.
@pytest.mark.parametrize("changed", [
    [],
    ["README.md"],
    ["docs/edr/README.md", "docs/img/pitch_deck_cover.png", "diagrams/d0_medallion_architecture.png",
     "diagrams/d1_study_process.drawio"],
    ["python/README.md", "pull_requests/pr-12-review.md"],
])
def test_docs_only_changes_skip_the_jobs(changed):
    assert not pn.code_changed(changed)


@pytest.mark.parametrize("changed", [
    ["python/health_transformation_lab_nlp/labels.py"],
    ["README.md", "databricks.yml"],
    [".github/workflows/ci.yml"],
    ["docs/build_decks.py"],                     # code that lives under docs/ is still code
    ["docs/edr/slides/04-results.html"],         # so are the slides the decks are built from
    ["diagrams/_build/gold_model.py"],
])
def test_any_other_change_runs_the_jobs(changed):
    assert pn.code_changed(changed)


def test_ci_runs_on_every_pull_request_and_skips_only_jobs_docs_cannot_affect():
    import yaml
    wf = yaml.safe_load((REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text())
    on = wf[True]
    assert "paths-ignore" not in (on["pull_request"] or {})        # docs-only PRs still report the checks
    assert "paths-ignore" in on["push"]                             # docs-only pushes to main still don't run CI
    assert wf["jobs"]["changes"]["outputs"]["code"]
    assert "if" not in wf["jobs"]["python"]                         # the docs are tested too
    for name in ("postgres", "azure-infra", "bundle"):
        job = wf["jobs"][name]
        assert job["needs"] == "changes", name
        assert job["if"] == "needs.changes.outputs.code == 'true'", name
    step = wf["jobs"]["changes"]["steps"][-1]["run"]
    assert "code=true" in step                                      # pushes, manual and weekly runs run everything
