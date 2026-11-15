"""028 AI15 (#804): the competition's evaluator loop on a Modal GPU, started from GitHub Actions. Modal is one more
machine with a GPU, so the run is kaggle/colab_official.py's `run_one`, reading Modal's own run list from the commit
Actions checked out. These tests cover what can be checked without Modal, Kaggle or a GPU: the choices, the dollar cap
as Modal's time limit, the credentials, the run's entry and the machine checked before a GPU starts, and, with a
stand-in for the `modal` package, the image and the functions the module defines."""

import importlib.util
import io
import json
import re
import sys
import types

import pytest
import yaml

from health_transformation_lab_nlp.paths import REPO_ROOT

KAGGLE = REPO_ROOT / "kaggle"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "modal-agent.yml"
ENV_OK = {"MODAL_TOKEN_ID": "ak-abc123", "MODAL_TOKEN_SECRET": "as-def456", "KAGGLE_USERNAME": "jcblearning",
          "KAGGLE_API_TOKEN": "KGAT_x"}
TRIAL = {"label": "modal-trial", "bundle": "jcblearning/htlnlp-official-modal-trial",
         "kernel_dataset": "jcblearning/htlnlp-colab-kernel-modal-trial",
         "model": "google/gemma-4/other/gemma-4-e4b-it-qat-w4a16-ct/2", "network_open_acknowledged": True}


def _load(name: str, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture(scope="module")
def mo():
    with pytest.MonkeyPatch.context() as mp:
        mp.setitem(sys.modules, "modal", None)          # as on a machine without Modal, even where it is installed
        return _load("modal_official", KAGGLE / "modal_official.py")


@pytest.fixture
def checkout(tmp_path):
    """A checkout's kaggle/ folder: the helper as committed, Modal's run list, and a Colab list Modal must not read."""
    kaggle = tmp_path / "kaggle"
    kaggle.mkdir()
    (kaggle / "colab_official.py").write_text((KAGGLE / "colab_official.py").read_text())
    runs = {"runs": [
        TRIAL,
        {**TRIAL, "label": "no-ack", "network_open_acknowledged": None},
        {**TRIAL, "label": "names-gpu", "gpu": "L4"},
        {**TRIAL, "label": "no-kernel", "kernel_dataset": None},
        {**TRIAL, "label": "Bad_Label"}]}
    (kaggle / "modal_official_run.json").write_text(json.dumps(runs))
    colab = {"stop": False, "runs": [{**TRIAL, "label": "modal-trial", "gpu": "T4", "model": "colab/model"}]}
    (kaggle / "colab_official_run.json").write_text(json.dumps(colab))
    return kaggle


def test_the_gpu_is_one_of_three_and_any_other_is_refused_by_name(mo):
    assert [mo.gpu_choice(g) for g in ("L4", "a10", "A100-40gb")] == ["L4", "A10", "A100-40GB"]
    with pytest.raises(SystemExit, match="L4, A10, A100-40GB"):
        mo.gpu_choice("H100")


def test_the_dollar_cap_becomes_modals_time_limit(mo):
    assert mo.timeout_seconds(5, 0.80) == 22500                     # 5 / 0.80 hours
    assert mo.timeout_seconds(1000, 0.80) == mo.MAX_TIMEOUT_SECONDS  # Modal's 24 hours at most
    assert mo.MIN_TIMEOUT_SECONDS == 30 * 60
    for too_little in (0.3, 0, -1, "nan", "inf", "five"):
        with pytest.raises(SystemExit, match="max_usd"):
            mo.timeout_seconds(too_little, 0.80)


def test_the_hourly_price_counts_the_cpu_and_memory_at_their_hard_limits(mo):
    cores, mib = mo.CPU_CORES[1], mo.MEMORY_MIB[1]
    assert mo.hourly_usd(0.80, 0.05, 0.01) == pytest.approx(0.80 + cores * 0.05 + mib / 1024 * 0.01)
    assert mo.CPU_CORES[0] <= mo.CPU_CORES[1] and mo.MEMORY_MIB[0] <= mo.MEMORY_MIB[1]


def test_each_price_has_its_source_and_date(mo):
    prices = mo.load_prices()
    assert set(prices) == set(mo.GPUS)
    for name, p in {**prices, **mo.load_side_prices()}.items():
        assert p["value"] > 0 and p["source"] and p["read_date"], name


def test_missing_credentials_are_named_before_anything_starts(mo):
    assert mo.credential_problems(ENV_OK) == []
    assert mo.credential_problems({**ENV_OK, "KAGGLE_API_TOKEN": "", "KAGGLE_KEY": "k"}) == []   # either Kaggle name
    problems = " ".join(mo.credential_problems({"MODAL_TOKEN_SECRET": "as x"}))
    for name in ("MODAL_TOKEN_ID", "MODAL_TOKEN_SECRET", "KAGGLE_USERNAME", "KAGGLE_API_TOKEN"):
        assert name in problems, name
    assert "as x" not in problems                                    # a value is never printed


def test_each_kaggle_credential_reaches_the_machine_under_its_own_name(mo):
    assert mo.kaggle_secret_names(ENV_OK) == ["KAGGLE_USERNAME", "KAGGLE_API_TOKEN"]
    assert mo.kaggle_secret_names({"KAGGLE_USERNAME": "u", "KAGGLE_API_TOKEN": "", "KAGGLE_KEY": "k"}) == \
        ["KAGGLE_USERNAME", "KAGGLE_KEY"]


def test_the_runs_entry_is_in_modals_own_list_with_its_kernel_and_no_gpu(mo, checkout):
    assert mo.run_entry("modal-trial", checkout)["bundle"] == TRIAL["bundle"]
    for label, word in (("not-listed", "modal_official_run.json"), ("no-ack", "network_open_acknowledged"),
                        ("names-gpu", "names a gpu"), ("no-kernel", "kernel_dataset")):
        with pytest.raises(SystemExit, match=word):
            mo.run_entry(label, checkout)


def test_the_helper_reads_modals_list_from_the_checkout_not_colabs_or_the_network(mo, checkout, monkeypatch):
    import urllib.request

    def no_network(*a, **k):
        raise AssertionError("the run list was fetched from the network")

    monkeypatch.setattr(urllib.request, "urlopen", no_network)
    co = mo.point_at_checkout(mo.load_helper(checkout), checkout)
    entry = co.listed_entry("modal-trial", sleep=lambda s: None)
    assert entry["kernel_dataset"] == TRIAL["kernel_dataset"] and not entry.get("gpu")   # not the Colab list's T4
    assert co.listed_model("modal-trial", sleep=lambda s: None) == TRIAL["model"]


def test_the_plan_gathers_every_problem_and_gives_the_time_limit(mo, checkout):
    plan = mo.plan("modal-trial", "L4", 5, ENV_OK, checkout)
    side = mo.load_side_prices()
    hourly = mo.hourly_usd(plan["usd_per_gpu_hour"], side["cpu"]["value"], side["memory"]["value"])
    assert plan["timeout_seconds"] == mo.timeout_seconds(5, hourly) < mo.timeout_seconds(5, plan["usd_per_gpu_hour"])
    assert plan["gpu"] == "L4" and plan["kernel_dataset"] == TRIAL["kernel_dataset"] and plan["price_source"]
    with pytest.raises(SystemExit) as err:
        mo.plan("no-ack", "H100", 0, {}, checkout)
    for word in ("MODAL_TOKEN_ID", "network_open_acknowledged", "L4, A10, A100-40GB", "max_usd"):
        assert word in str(err.value), word
    with pytest.raises(SystemExit, match="lowercase letters"):
        mo.plan("Bad_Label", "L4", 5, ENV_OK, checkout)


def test_preflight_writes_the_gpu_and_time_limit_for_the_next_step(mo, checkout, capsys):
    p = mo.cli(["preflight", "--label", "modal-trial", "--gpu", "L4", "--max-usd", "5"], env=ENV_OK,
               kaggle_dir=checkout)
    lines = capsys.readouterr().out.splitlines()
    assert lines == ["HTL_MODAL_GPU=L4", f"HTL_MODAL_TIMEOUT={p['timeout_seconds']}"]


def test_a_new_run_waits_while_an_earlier_one_is_still_going(mo, capsys):
    listing = [{"app_id": "ap-1", "description": mo.APP_NAME, "state": "stopped"},
               {"app_id": "ap-2", "description": "something-else", "state": "ephemeral (detached)"}]
    mo.cli(["busy"], stdin=io.StringIO(json.dumps(listing)))
    assert "no Modal run is going" in capsys.readouterr().out
    listing.append({"app_id": "ap-3", "description": mo.APP_NAME, "state": "ephemeral (detached)"})
    with pytest.raises(SystemExit, match="ap-3.*modal app stop"):
        mo.cli(["busy"], stdin=io.StringIO(json.dumps(listing)))


def test_the_machine_check_names_each_thing_missing(mo):
    class Done:
        def __init__(self, code):
            self.returncode, self.stderr = code, "unshare: write failed /proc/self/uid_map"

    ok = mo.machine_problems(which=lambda t, path=None: f"/usr/bin/{t}", run=lambda *a, **k: Done(0),
                             find_spec=lambda n: object(), version=(3, 13))
    assert ok == []
    bad = mo.machine_problems(which=lambda t, path=None: None if t == "git" else f"/usr/bin/{t}",
                              run=lambda *a, **k: Done(1), find_spec=lambda n: None if n == "vllm" else object(),
                              version=(3, 11))
    text = " ".join(bad)
    for word in ("no git", "Python 3.11", "vllm", "user namespace"):
        assert word in text, word


class _Image:
    def __init__(self, steps):
        self.steps = steps

    def __getattr__(self, name):
        return lambda *a, **k: _Image(self.steps + [(name, a, k)])


def _fake_modal(calls):
    class App:
        def __init__(self, name, image=None):
            self.name, self.image, self.functions = name, image, {}
            calls["app"] = self

        def function(self, **kw):
            def wrap(f):
                self.functions[f.__name__] = kw
                f.remote = lambda *a: calls.setdefault("order", []).append(f.__name__) or f(*a)
                return f
            return wrap

        def local_entrypoint(self):
            def wrap(f):
                self.entrypoint = f
                return f
            return wrap

    return types.SimpleNamespace(
        App=App,
        Image=types.SimpleNamespace(from_registry=lambda tag, **k: _Image([("from_registry", (tag,), k)])),
        Secret=types.SimpleNamespace(from_local_environ=lambda names: ("secret", tuple(names))))


@pytest.fixture
def with_modal(monkeypatch):
    calls = {}
    monkeypatch.setitem(sys.modules, "modal", _fake_modal(calls))
    for name, value in {"HTL_MODAL_GPU": "A10", "HTL_MODAL_TIMEOUT": "3600", "KAGGLE_USERNAME": "u",
                        "KAGGLE_API_TOKEN": "", "KAGGLE_KEY": "k"}.items():
        monkeypatch.setenv(name, value)
    mod = _load("modal_official_on_modal", KAGGLE / "modal_official.py")
    return mod, calls


def test_the_image_has_git_procps_python_313_and_the_pins_and_ends_with_the_files(with_modal):
    mod, calls = with_modal
    steps = calls["app"].image.steps
    names = [s[0] for s in steps]
    assert steps[0] == ("from_registry", (mod.BASE_IMAGE,), {"add_python": "3.13"}) and "devel" in mod.BASE_IMAGE
    assert {"git", "procps"} <= set(steps[names.index("apt_install")][1])
    assert steps[names.index("pip_install")][1] == mod.PINS
    assert names[-2:] == ["add_local_file", "add_local_file"]      # Modal wants added files last
    assert {str(s[1][1]).rsplit("/", 1)[-1] for s in steps[-2:]} == {mod.HELPER, mod.RUN_LIST}


def test_the_gpu_function_has_the_limits_no_retries_and_only_the_kaggle_names_set(with_modal):
    mod, calls = with_modal
    gpu_fn, check_fn = calls["app"].functions["run_on_gpu"], calls["app"].functions["check_machine"]
    assert gpu_fn["gpu"] == "A10" and gpu_fn["timeout"] == 3600 and gpu_fn["retries"] == 0
    assert gpu_fn["cpu"] == mod.CPU_CORES and gpu_fn["memory"] == mod.MEMORY_MIB and gpu_fn["max_containers"] == 1
    assert gpu_fn["secrets"] == [("secret", ("KAGGLE_USERNAME", "KAGGLE_KEY"))]
    assert "gpu" not in check_fn and "secrets" not in check_fn       # the machine check: a CPU, no credentials


def test_the_machine_is_checked_before_the_gpu_and_a_lack_stops_it(with_modal, monkeypatch):
    mod, calls = with_modal
    p = {"label": "modal-trial", "bundle": "b", "kernel_dataset": "k", "kernel_url": "https://x", "model": "m", "gpu": "A10",
         "timeout_seconds": 3600, "max_usd": 5.0, "usd_per_hour_at_limits": 1.6, "price_source": "s"}
    monkeypatch.setattr(mod, "plan", lambda *a, **k: p)
    ran = []
    helper = types.SimpleNamespace(run_one=lambda *a, **k: ran.append((a, k)) or 0)
    monkeypatch.setattr(mod, "load_helper", lambda d: helper)
    monkeypatch.setattr(mod, "point_at_checkout", lambda co, d: co)
    monkeypatch.setattr(mod, "machine_problems", lambda: ["no git on the machine"])
    with pytest.raises(SystemExit, match="no GPU was started"):
        calls["app"].entrypoint("modal-trial", "A10", "5")
    assert calls["order"] == ["check_machine"] and ran == []
    monkeypatch.setattr(mod, "machine_problems", list)
    calls["app"].entrypoint("modal-trial", "A10", "5")
    assert calls["order"][-2:] == ["check_machine", "run_on_gpu"]
    assert ran == [(("modal-trial", "b", "k", None), {"model": "m"})]   # the kernel from its dataset, never a URL
    monkeypatch.setattr(mod, "plan", lambda *a, **k: {**p, "timeout_seconds": 60})
    with pytest.raises(SystemExit, match="preflight first"):
        calls["app"].entrypoint("modal-trial", "A10", "5")


def test_the_workflow_is_started_by_hand_and_checks_everything_before_the_run():
    wf = yaml.safe_load(WORKFLOW.read_text())
    triggers = wf.get("on", wf.get(True))
    assert set(triggers) == {"workflow_dispatch"}
    assert set(triggers["workflow_dispatch"]["inputs"]) == {"label", "gpu", "max_usd"}
    job = next(iter(wf["jobs"].values()))
    assert job["environment"] == "dev"
    assert job["env"]["MODAL_TOKEN_ID"] == "${{ secrets.MODAL_TOKEN_ID }}"
    assert job["env"]["MODAL_TOKEN_SECRET"] == "${{ secrets.MODAL_TOKEN_SECRET }}"
    assert {"KAGGLE_USERNAME", "KAGGLE_API_TOKEN", "KAGGLE_KEY"} <= set(job["env"])
    runs = [s.get("run", "") for s in job["steps"]]
    assert any('"modal==1.6.4"' in r for r in runs)                  # a pinned version

    def first(word):
        return next(i for i, r in enumerate(runs) if word in r)

    order = [first(w) for w in ("modal_official.py preflight", "kaggle kernels list", "modal token info",
                                "modal_official.py busy", "modal run")]
    assert order == sorted(order) and "--detach" in runs[order[-1]]
    assert [i for i, r in enumerate(runs) if "GITHUB_ENV" in r] == [order[0]]   # no credential written to a file
    secret_value = re.compile(r"echo[^\n]*\$\{?(MODAL_TOKEN|KAGGLE_API_TOKEN|KAGGLE_KEY)")
    assert not any(secret_value.search(r) for r in runs)            # names in messages, never values


def test_modals_run_list_is_committed_apart_from_colabs():
    runs = json.loads((KAGGLE / "modal_official_run.json").read_text())["runs"]
    assert all(r.get("network_open_acknowledged") is True and not r.get("gpu") for r in runs)


def test_the_modal_token_is_in_the_secrets_register():
    reg = yaml.safe_load((REPO_ROOT / "ops" / "secrets_register.yaml").read_text())["credentials"]
    entry = next(c for c in reg if "Modal" in c["name"])
    assert "MODAL_TOKEN_ID" in entry["stored_in"] and "MODAL_TOKEN_SECRET" in entry["stored_in"]
    assert "modal-agent.yml" in entry["used_by"] and entry["expires"]


def test_the_image_installs_the_same_packages_the_helper_pins(mo):
    co = _load("colab_official", KAGGLE / "colab_official.py")
    assert mo.PINS == co.PINS
