"""028 AI9 (#687): the competition's evaluator loop on a Colab GPU, laid out as on Kaggle, so the same kernel code runs
there unchanged. These tests cover what can be checked without a GPU: where things are put, what the kernel's
environment holds (no credential, no way out), what comes back and where, and that the notebook holds no token."""
import importlib.util
import json

import pytest

from health_transformation_lab_nlp.paths import REPO_ROOT, TASKS_DIR

NOTEBOOK = REPO_ROOT / "kaggle" / "colab_official_agent.ipynb"


@pytest.fixture(scope="module")
def co():
    spec = importlib.util.spec_from_file_location("colab_official", REPO_ROOT / "kaggle" / "colab_official.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_inputs_sit_where_kaggle_mounts_them(co, tmp_path):
    """The kernel finds its bundle, wheels and model by searching /kaggle/input, so each is put where Kaggle puts it."""
    assert co.dataset_dir("jcblearning/htlnlp-official-graph", tmp_path) == tmp_path / "input" / "htlnlp-official-graph"
    assert co.model_dir(tmp_path, "google/gemma-4/Other/gemma-4-e4b-it-qat-w4a16-ct/2") == (
        tmp_path / "input" / "models" / "google" / "gemma-4" / "other" / "gemma-4-e4b-it-qat-w4a16-ct" / "2")
    with pytest.raises(SystemExit, match="owner/model/framework/variation/version"):
        co.model_dir(tmp_path, "google/gemma-4")


def test_the_kernel_gets_no_credential_and_no_way_out(co):
    """On Kaggle the kernels ran with internet off and no token in reach. A Colab machine has both, so the kernel's
    process, and every command the agent runs under it, starts without them."""
    env = co.kernel_env({"PATH": "/usr/bin", "HOME": "/root", "LD_LIBRARY_PATH": "/usr/lib64-nvidia",
                         "KAGGLE_API_TOKEN": "x", "KAGGLE_KEY": "x", "KAGGLE_USERNAME": "someone", "HF_TOKEN": "x",
                         "OPENAI_API_KEY": "x", "MY_SECRET": "x", "DB_PASSWORD": "x", "TBE_CREDS_ADDR": "172.28.0.1:8008",
                         "GCE_METADATA_HOST": "172.28.0.12", "COLAB_GPU": "1", "CUDA_VISIBLE_DEVICES": "0"})
    for gone in ("KAGGLE_API_TOKEN", "KAGGLE_KEY", "KAGGLE_USERNAME", "HF_TOKEN", "OPENAI_API_KEY", "MY_SECRET",
                 "DB_PASSWORD", "TBE_CREDS_ADDR", "GCE_METADATA_HOST"):
        assert gone not in env, gone
    assert env["PATH"] == "/usr/bin" and env["LD_LIBRARY_PATH"] == "/usr/lib64-nvidia" and env["CUDA_VISIBLE_DEVICES"] == "0"
    for proxy in ("HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy", "ALL_PROXY", "all_proxy"):
        assert env[proxy] == "http://127.0.0.1:9", proxy          # nothing listens there
    assert "127.0.0.1" in env["NO_PROXY"] and "localhost" in env["no_proxy"]   # the model server is on this machine
    assert env["PIP_NO_INDEX"] == "1" and env["HF_HUB_OFFLINE"] == "1"


def test_results_go_to_a_private_dataset_named_for_the_run(co, tmp_path):
    assert co.results_ref("jcblearning", "statement") == "jcblearning/htlnlp-colab-official-statement"
    with pytest.raises(SystemExit, match="label"):
        co.results_ref("jcblearning", "Has Spaces")
    meta = co.results_metadata("jcblearning", "smoke-143")
    assert meta["id"] == "jcblearning/htlnlp-colab-official-smoke-143" and 6 <= len(meta["title"]) <= 50
    assert "isPrivate" not in meta or meta["isPrivate"] is True


def test_what_comes_back_leaves_out_the_submission_copy_and_anything_large(co, tmp_path):
    out = tmp_path / "working"
    for rel, size in (("result.json", 10), ("telemetry.jsonl", 10), ("gpu_samples.csv", 10),
                      ("tasks/htlnlp_1/result.json", 10), ("tasks/htlnlp_1/trace.log", 10),
                      ("submission/agent.yaml", 10), ("submission/prompts/system.md", 10), ("big.bin", 2048)):
        p = out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(b"x" * size)
    kept = sorted(str(p.relative_to(out)) for p in co.files_to_return(out, max_bytes=1024))
    assert kept == ["gpu_samples.csv", "result.json", "tasks/htlnlp_1/result.json", "tasks/htlnlp_1/trace.log",
                    "telemetry.jsonl"]


def test_a_second_run_does_not_find_the_first_runs_bundle(co, tmp_path):
    """The kernel takes the first bundle under /kaggle/input: with two arms on one machine, the other's must go."""
    for name, marker in (("htlnlp-official-statement", "official_batch.json"), ("htlnlp-official-graph", "official_batch.json"),
                         ("htlnlp-official-htlnlp-143", "official_task.json"), ("gemma-4-developer-agent-wheelhouse", "x.whl")):
        d = tmp_path / "input" / name
        d.mkdir(parents=True)
        (d / marker).write_text("{}")
    keep = co.dataset_dir("jcblearning/htlnlp-official-graph", tmp_path)
    assert [d.name for d in co.stale_bundles(tmp_path, keep)] == ["htlnlp-official-htlnlp-143", "htlnlp-official-statement"]


def test_the_pins_are_the_versions_the_kaggle_arms_recorded(co):
    """The model server and the agent framework are installed from PyPI at the versions the competition's wheelhouse
    gave the Kaggle kernels, so the two environments differ in the machine, not in these."""
    recorded = json.loads((TASKS_DIR / "official_agent_runs" /
                           "gemma-4-e4b-it-qat-w4a16-ct_swegemma_graph_settings.json").read_text())["versions"]
    for package in ("vllm", "google-adk", "litellm"):
        assert f"{package}=={recorded[package]}" in co.PINS, package
    assert co.MODEL.lower() == "google/gemma-4/other/gemma-4-e4b-it-qat-w4a16-ct/2"
    assert co.WHEELHOUSE == "metric/gemma-4-developer-agent-wheelhouse"


def test_a_command_that_reaches_for_the_network_is_counted(co):
    """Nothing blocks the network at the machine's edge on Colab, so every command the agent ran is read afterwards."""
    assert co.network_command_count(["pytest -q tests", "git status", "python -c 'print(1)'"]) == 0
    assert co.network_command_count(["pip install requests", "curl -s https://example.org", "git clone https://x/y",
                                     "wget http://x", "python -m pip download foo", "git fetch origin"]) == 6
    assert co.network_command_count(["grep -rn 'https://' docs", "cat requirements.txt"]) == 0   # a URL read, not fetched


def _lists(*plans):
    """A stand-in for reading the branch: each read of the run list gives the next of `plans`, the last one for ever."""
    reads = {"n": 0}

    def get(name):
        assert name == "colab_official_run.json"
        reads["n"] += 1
        return json.dumps(plans[min(reads["n"], len(plans)) - 1])
    return get


def test_a_notebook_started_once_makes_the_runs_the_branch_lists_later(co, monkeypatch):
    """The owner taps Run all once, on a phone. The full arms may only start after the test run has been read and the
    plan registered, so the notebook keeps reading the branch's run list and makes what is added to it."""
    monkeypatch.setattr(co, "say", lambda message: None)
    smoke = {"label": "smoke-143", "bundle": "someone/htlnlp-official-htlnlp-143", "kernel_url": "https://example.org/k.py"}
    arm = {"label": "colab-statement", "bundle": "someone/htlnlp-official-colab-statement",
           "kernel_dataset": "someone/htlnlp-colab-kernel-colab-statement"}
    made, done = [], {"smoke-143": 0}
    why = co.follow(done, minutes=10, get=_lists({"runs": [smoke]}, {"runs": [smoke]}, {"runs": [smoke, arm]},
                                                 {"runs": [smoke, arm]}, {"runs": [smoke, arm], "stop": True}),
                    make=lambda *a: made.append(a) or 3, sleep=lambda s: None, clock=lambda: 0.0)
    assert made == [("colab-statement", "someone/htlnlp-official-colab-statement",
                     "someone/htlnlp-colab-kernel-colab-statement", None)]     # once, and the test run not again
    assert done == {"smoke-143": 0, "colab-statement": 3}
    assert "stop" in why


def test_stop_means_no_more_waiting_not_that_a_listed_run_is_dropped(co, monkeypatch):
    """A list that says stop still has every run it names made; a run is withdrawn by taking it off the list."""
    monkeypatch.setattr(co, "say", lambda message: None)
    made, done = [], {}
    why = co.follow(done, minutes=10, get=_lists({"runs": [{"label": "a-run", "bundle": "x/a"}, {"label": "b-run", "bundle": "x/b"}],
                                                  "stop": True}),
                    make=lambda label, *rest: made.append(label) or 0, sleep=lambda s: None, clock=lambda: 0.0)
    assert made == ["a-run", "b-run"] and "stop" in why


def test_following_ends_when_nothing_new_is_listed_in_time(co, monkeypatch):
    """A GPU that waits spends the account's compute units: the wait has an end."""
    monkeypatch.setattr(co, "say", lambda message: None)
    now = {"t": 0.0}
    made = []
    why = co.follow({"smoke-143": 0}, minutes=5, get=_lists({"runs": [{"label": "smoke-143", "bundle": "a/b"}]}),
                    make=lambda *a: made.append(a) or 0, sleep=lambda s: now.__setitem__("t", now["t"] + s),
                    clock=lambda: now["t"])
    assert made == [] and "nothing new" in why and 300 <= now["t"] <= 300 + co.POLL_SECONDS


def test_a_run_list_that_cannot_be_read_or_a_run_that_cannot_start_does_not_end_the_following(co, monkeypatch):
    monkeypatch.setattr(co, "say", lambda message: None)
    calls = {"n": 0}

    def get(name):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("the network blinked")
        return json.dumps({"runs": [{"label": "Bad Label", "bundle": "a/b"}, {"label": "ok-run", "bundle": "a/c"}],
                           "stop": calls["n"] > 3})

    def make(label, *rest):
        if label == "Bad Label":
            raise SystemExit("a run's label is lowercase")
        return 0
    done = {}
    co.follow(done, minutes=10, get=get, make=make, sleep=lambda s: None, clock=lambda: 0.0)
    assert done == {"Bad Label": 1, "ok-run": 0}


def test_a_run_is_made_once_in_a_session_and_then_the_branch_is_followed(co, monkeypatch):
    """The notebook's own loop calls `main` for each run its first reading listed; a run the following has already
    made is not made again."""
    made, followed, released = [], [], []
    monkeypatch.setattr(co, "say", lambda message: None)
    monkeypatch.setattr(co, "DONE", {})
    monkeypatch.setattr(co, "run_one", lambda label, *a: made.append(label) or 0)
    monkeypatch.setattr(co, "follow", lambda done, minutes: followed.append(dict(done)) or done.update({"b": 2}) or "stop")
    monkeypatch.setattr(co, "release", lambda: released.append(1))
    assert co.main("a", "x/y", kernel_url="https://example.org/k.py") == 0
    assert co.main("b", "x/z", kernel_url="https://example.org/k.py") == 2      # made while following: not again
    assert made == ["a"] and followed == [{"a": 0}] and released == [1]


def test_the_notebook_reads_its_token_from_colab_secrets_and_holds_none():
    nb = json.loads(NOTEBOOK.read_text())
    src = "\n".join("".join(c["source"]) for c in nb["cells"])
    assert 'userdata.get("KAGGLE_API_TOKEN")' in src and 'userdata.get("KAGGLE_USERNAME")' in src
    assert "KGAT_" not in src and "SEAL_KEY" not in src
    assert all(not c.get("outputs") for c in nb["cells"] if c["cell_type"] == "code")
    assert "colab_official.py" in src and "healthtransformationlab/health-transformation-lab-nlp" in src
    assert nb["metadata"]["accelerator"] == "GPU"


# --- the runner's side: preparing a Colab run and collecting what it sent back ------------------------------------

@pytest.fixture(scope="module")
def run():
    spec = importlib.util.spec_from_file_location("official_agent_run", REPO_ROOT / "kaggle" / "official_agent_run.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


RESULT = {"model_name": "gemma-4-e4b-it-qat-w4a16-ct", "harness_name": "swegemma (Evaluator.evaluate_task, subprocess sandbox)",
          "versions": {"swegemma": "0.2.11", "vllm": "0.19.1"},
          "server": {"gpus": ["NVIDIA A100-SXM4-40GB"], "tensor_parallel_size": 1, "dtype": "bfloat16"},
          "budgets": {"timeout_seconds": 120, "verification_timeout_seconds": 300, "max_tool_calls": 40,
                      "max_time_minutes": 5.0, "max_turns": 60},
          "generation_defaults": {"max_output_tokens": 16384, "thinking_config": {"thinking_budget": 4096}}}


def test_a_colab_run_is_named_so_its_three_private_datasets_cannot_be_taken_for_anything_else(run):
    """The sealed bundle, the keyed kernel file and the results each have their own private dataset, all under the
    prefixes the paper's rules check keeps out of the Writeup."""
    entry = run.colab_run_entry("someone", "colab-graph")
    assert entry == {"label": "colab-graph", "bundle": "someone/htlnlp-official-colab-graph",
                     "kernel_dataset": "someone/htlnlp-colab-kernel-colab-graph"}
    assert run.colab_results_ref("someone", "colab-graph") == "someone/htlnlp-colab-official-colab-graph"
    meta = run.colab_kernel_metadata("someone", "colab-graph")
    assert meta["id"] == "someone/htlnlp-colab-kernel-colab-graph" and 6 <= len(meta["title"]) <= 50


def test_the_settings_of_a_colab_run_say_what_differs_from_a_kaggle_kernel(run):
    s = run.settings_for(RESULT, seed=7, drawn=["a", "b"], pool_count=93, machine_shape=None, docker_image=None,
                         competition=None, agent_commit="abc123", tasks_per_kernel=2, colab=True)
    assert s["kernel"]["machine_shape_asked"] == "Colab, one GPU" and s["kernel"]["docker_image"] is None
    assert s["kernel"]["internet"] != False and "no credential" in s["kernel"]["internet"]   # noqa: E712
    assert any(n.startswith("All 2 tasks were given to one process on a Colab machine, each sealed until its turn")
               for n in s["notes"])
    assert not any("private, offline kernel" in n for n in s["notes"])
    assert any("from PyPI at the versions the Kaggle kernels recorded" in n for n in s["notes"])
    kaggle = run.settings_for(RESULT, seed=7, drawn=["a", "b"], pool_count=93, machine_shape="NvidiaL4",
                              docker_image="img", competition="c", agent_commit="abc123", tasks_per_kernel=2)
    assert kaggle["kernel"]["internet"] is False            # a Kaggle kernel's record is unchanged


def test_what_a_colab_run_sent_back_is_read_as_a_kernels_output(run, tmp_path):
    """The results dataset holds the kernel's folder under `working/` and the notebook's log beside it."""
    got = tmp_path / "downloaded"
    for rel in ("working/result.json", "working/tasks/htlnlp_1/result.json", "working/telemetry.jsonl", "colab.log"):
        p = got / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("{}")
    out = tmp_path / "output"
    run.colab_output(got, out)
    assert sorted(str(p.relative_to(out)) for p in out.rglob("*") if p.is_file()) == [
        "colab.log", "result.json", "tasks/htlnlp_1/result.json", "telemetry.jsonl"]
    with pytest.raises(SystemExit, match="no result.json"):
        run.colab_output(tmp_path / "empty", tmp_path / "output2")


def test_the_agents_commands_are_read_from_its_trace_for_any_reach_at_the_network(run):
    trace = {"steps": [{"tool_calls": [{"function_name": "run_command", "arguments": {"command": "pytest -q"}},
                                       {"function_name": "read_file", "arguments": {"path": "a.py"}}]},
                       {"tool_calls": [{"function_name": "run_command", "arguments": {"command": "pip install requests"}},
                                       {"function_name": "run_command", "arguments": {"cmd": "git status"}}]}]}
    assert run.trace_commands(trace) == ["pytest -q", "pip install requests", "git status"]
    assert run.network_audit({"a": trace, "b": {"steps": []}}) == {
        "command_count": 3, "network_command_count": 1, "instance_ids": ["a"]}
