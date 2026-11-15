"""028 AI15 (#804): the competition's evaluator loop on a Modal GPU, started from GitHub Actions. Modal is one more
machine with a GPU, so the run is kaggle/colab_official.py's `run_one`, read from the commit Actions checked out. These
tests cover what can be checked without Modal, Kaggle or a GPU: the choices, the dollar cap as Modal's time limit, the
credentials and the run's entry checked before anything starts, and that the run list comes from the checkout."""

import importlib.util
import json

import pytest
import yaml

from health_transformation_lab_nlp.paths import REPO_ROOT

WORKFLOW = REPO_ROOT / ".github" / "workflows" / "modal-agent.yml"
ENV_OK = {"MODAL_TOKEN_ID": "ak-abc123", "MODAL_TOKEN_SECRET": "as-def456", "KAGGLE_USERNAME": "jcblearning",
          "KAGGLE_API_TOKEN": "KGAT_x"}


def _load(name: str, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mo():
    return _load("modal_official", REPO_ROOT / "kaggle" / "modal_official.py")


@pytest.fixture
def checkout(tmp_path):
    """A checkout's kaggle/ folder: the helper as committed, and a run list with one acknowledged entry."""
    kaggle = tmp_path / "kaggle"
    kaggle.mkdir()
    (kaggle / "colab_official.py").write_text((REPO_ROOT / "kaggle" / "colab_official.py").read_text())
    runs = {"stop": False, "runs": [
        {"label": "modal-trial", "bundle": "jcblearning/htlnlp-official-modal-trial",
         "kernel_dataset": "jcblearning/htlnlp-colab-kernel-modal-trial", "gpu": "L4",
         "model": "google/gemma-4/other/gemma-4-e4b-it-qat-w4a16-ct/2", "network_open_acknowledged": True},
        {"label": "no-ack", "bundle": "jcblearning/x", "kernel_dataset": "jcblearning/y"}]}
    (kaggle / "colab_official_run.json").write_text(json.dumps(runs))
    return kaggle


def test_the_gpu_is_one_of_three_and_any_other_is_refused_by_name(mo):
    assert [mo.gpu_choice(g) for g in ("L4", "a10", "A100-40gb")] == ["L4", "A10", "A100-40GB"]
    with pytest.raises(SystemExit, match="L4, A10, A100-40GB"):
        mo.gpu_choice("H100")


def test_the_dollar_cap_becomes_modals_time_limit(mo):
    assert mo.timeout_seconds(5, 0.80) == 22500                     # 5 / 0.80 hours
    assert mo.timeout_seconds(1000, 0.80) == mo.MAX_TIMEOUT_SECONDS  # Modal's 24 hours at most
    with pytest.raises(SystemExit, match="max_usd"):
        mo.timeout_seconds(0.1, 0.80)                                # under 20 minutes: not enough for one task
    with pytest.raises(SystemExit, match="max_usd"):
        mo.timeout_seconds(0, 0.80)


def test_each_gpu_has_a_modal_price_with_its_source_and_date(mo):
    prices = mo.load_prices()
    assert set(prices) == set(mo.GPUS)
    for gpu, p in prices.items():
        assert p["value"] > 0 and p["source"] and p["read_date"], gpu


def test_missing_credentials_are_named_before_anything_starts(mo):
    assert mo.credential_problems(ENV_OK) == []
    assert mo.credential_problems({**ENV_OK, "KAGGLE_API_TOKEN": "", "KAGGLE_KEY": "k"}) == []   # either Kaggle name
    problems = " ".join(mo.credential_problems({"MODAL_TOKEN_SECRET": "as x"}))
    for name in ("MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET", "KAGGLE_USERNAME", "KAGGLE_API_TOKEN"):
        assert name in problems, name
    assert "as x" not in problems                                    # a value is never printed


def test_the_runs_entry_must_be_listed_and_accept_an_open_network(mo, checkout):
    assert mo.run_entry("modal-trial", checkout)["bundle"] == "jcblearning/htlnlp-official-modal-trial"
    with pytest.raises(SystemExit, match="not-listed"):
        mo.run_entry("not-listed", checkout)
    with pytest.raises(SystemExit, match="network_open_acknowledged"):
        mo.run_entry("no-ack", checkout)


def test_the_helper_reads_the_run_list_from_the_checkout_not_the_network(mo, checkout, monkeypatch):
    import urllib.request

    def no_network(*a, **k):
        raise AssertionError("the run list was fetched from the network")

    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    co = mo.point_at_checkout(mo.load_helper(checkout), checkout)
    assert co.listed_entry("modal-trial", sleep=lambda s: None)["gpu"] == "L4"
    assert co.listed_model("modal-trial", sleep=lambda s: None).endswith("gemma-4-e4b-it-qat-w4a16-ct/2")


def test_the_plan_gathers_every_problem_and_gives_the_time_limit(mo, checkout):
    plan = mo.plan("modal-trial", "L4", 5, ENV_OK, checkout)
    assert plan["timeout_seconds"] == mo.timeout_seconds(5, plan["usd_per_gpu_hour"])
    assert plan["gpu"] == "L4" and plan["bundle"].endswith("modal-trial") and plan["price_source"]
    with pytest.raises(SystemExit) as err:
        mo.plan("no-ack", "H100", 0, {}, checkout)
    for word in ("MODAL_TOKEN_ID", "network_open_acknowledged", "L4, A10, A100-40GB", "max_usd"):
        assert word in str(err.value), word


def test_preflight_writes_the_gpu_and_time_limit_for_the_next_step(mo, checkout, capsys):
    mo.cli(["preflight", "--label", "modal-trial", "--gpu", "L4", "--max-usd", "5"], env=ENV_OK, kaggle_dir=checkout)
    lines = capsys.readouterr().out.splitlines()
    assert "HTL_MODAL_GPU=L4" in lines and "HTL_MODAL_TIMEOUT=22500" in lines


def test_the_workflow_is_started_by_hand_checks_first_and_keeps_the_tokens_in_dev():
    wf = yaml.safe_load(WORKFLOW.read_text())
    triggers = wf.get("on", wf.get(True))
    assert set(triggers) == {"workflow_dispatch"}
    assert set(triggers["workflow_dispatch"]["inputs"]) == {"label", "gpu", "max_usd"}
    job = next(iter(wf["jobs"].values()))
    assert job["environment"] == "dev"
    text = WORKFLOW.read_text()
    assert "secrets.MODAL_TOKEN_ID" in text and "secrets.MODAL_TOKEN_SECRET" in text
    assert "modal==" in text                                         # a pinned version
    steps = [s.get("run", "") for s in job["steps"]]
    first_preflight = next(i for i, s in enumerate(steps) if "modal_official.py preflight" in s)
    first_run = next(i for i, s in enumerate(steps) if "modal run" in s)
    assert first_preflight < first_run and "--detach" in steps[first_run]
    assert "modal token info" in text                                # one cheap authenticated call before the run
    assert "echo $MODAL" not in text and 'echo "$MODAL' not in text


def test_the_modal_token_is_in_the_secrets_register():
    reg = yaml.safe_load((REPO_ROOT / "ops" / "secrets_register.yaml").read_text())["credentials"]
    entry = next(c for c in reg if "Modal" in c["name"])
    assert "MODAL_TOKEN_ID" in entry["stored_in"] and "MODAL_TOKEN_SECRET" in entry["stored_in"]
    assert "modal-agent.yml" in entry["used_by"] and entry["expires"]


def test_the_image_installs_the_same_packages_the_helper_pins(mo):
    co = _load("colab_official", REPO_ROOT / "kaggle" / "colab_official.py")
    assert mo.PINS == co.PINS
