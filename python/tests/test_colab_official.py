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
    process starts without them. That is all this shows. The evaluator starts each of the agent's commands from a
    short list of environment names of its own: no credential is on it, and neither are the proxies set here, so a
    command can reach the network (found by the review of #690). The commands are read for that afterwards."""
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
    # that the dataset is private is the upload's to say (dataset_create_new(public=False)): tested with `upload`


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


def test_a_finished_runs_results_are_sent_until_kaggle_takes_them(co, monkeypatch):
    """Kaggle refuses a new version of a dataset while it is still taking the last one in. A finished arm is hours of
    GPU time, so its last upload is tried again, and the GPU is not given back while a run's results are only on it."""
    monkeypatch.setattr(co, "say", lambda message: None)
    calls = {"n": 0}

    def busy_twice():
        calls["n"] += 1
        if calls["n"] < 3:
            raise RuntimeError("the dataset is still being processed")
    assert co.send_until_taken(busy_twice, tries=5, wait_seconds=1, sleep=lambda s: None) is True
    assert calls["n"] == 3

    def never():
        calls["n"] += 1
        raise RuntimeError("refused")
    calls["n"] = 0
    assert co.send_until_taken(never, tries=4, wait_seconds=1, sleep=lambda s: None) is False
    assert calls["n"] == 4


def test_the_gpu_is_kept_while_a_runs_results_are_only_on_the_machine(co, monkeypatch, tmp_path):
    made, released, said = [], [], []
    monkeypatch.setattr(co, "say", said.append)
    monkeypatch.setattr(co, "LOG", tmp_path / "htl_colab.log")
    monkeypatch.setattr(co, "DONE", {})
    monkeypatch.setattr(co, "run_one", lambda label, *a: made.append(label) or 0)
    monkeypatch.setattr(co, "follow", lambda done, minutes: "stop")
    monkeypatch.setattr(co, "release", lambda: released.append(1))
    (tmp_path / "htl_not_sent_colab-graph").write_text("")           # an arm whose last upload never went through
    co.main("a", "x/y", kernel_url="https://example.org/k.py")
    assert released == [] and any("colab-graph" in s and "not" in s for s in said)
    (tmp_path / "htl_not_sent_colab-graph").unlink()
    monkeypatch.setattr(co, "DONE", {})
    co.main("b", "x/z", kernel_url="https://example.org/k.py")
    assert released == [1]


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
    assert s["kernel"]["internet"] != False and "no credential" in s["kernel"]["internet"]
    assert "could reach the network" in s["kernel"]["internet"]   # the proxies do not reach the agent's commands
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
        "command_count": 3, "network_command_count": 1, "instance_ids": ["a"],
        "tool_call_count": 4, "network_tool_call_count": 1, "tool_call_instance_ids": ["a"]}


def test_the_notebooks_code_is_hidden_so_a_stray_tap_on_a_phone_cannot_change_it():
    """The owner runs this from a phone. A letter typed into the cell by a stray tap stopped the first run with a
    NameError before anything started, so the cell is a form: Colab shows its title and a play button, not its code."""
    nb = json.loads(NOTEBOOK.read_text())
    code = [c for c in nb["cells"] if c["cell_type"] == "code"]
    assert len(code) == 1
    assert code[0]["metadata"].get("cellView") == "form"
    assert "".join(code[0]["source"]).startswith("#@title ")
    compile("".join(code[0]["source"]), "cell", "exec")   # the title is a comment: the cell is still plain Python


# --- what the first test run on Colab showed (#687): /kaggle/input is read-only there, and its Python is 3.13 --------

def _kernel(*names):
    import ast
    src = (REPO_ROOT / "kaggle" / "official_agent_kernel.py").read_text()
    ns: dict = {}
    exec("import glob, json, os, re, shutil, sys\nfrom pathlib import Path\n", ns)   # noqa: S102 - our own kernel's code
    for node in ast.parse(src).body:
        if isinstance(node, ast.FunctionDef) and node.name in names:
            exec(ast.get_source_segment(src, node), ns)                              # noqa: S102
    return ns


def test_the_kernel_looks_for_its_inputs_where_it_is_told():
    """Colab mounts its own read-only /kaggle/input, so a Colab run puts the inputs elsewhere and says where. On
    Kaggle nothing is said and the kernel looks where Kaggle mounts them."""
    src = (REPO_ROOT / "kaggle" / "official_agent_kernel.py").read_text()
    assert 'INPUT = Path(os.environ.get("HTL_INPUT", "/kaggle/input"))' in src
    code = "\n".join(line.split("#")[0] for line in src.splitlines())
    assert code.count('"/kaggle/input') == 1, "every search starts from INPUT, not from a path written out again"


def test_a_wheel_built_for_another_python_is_left_out_and_the_rest_install(tmp_path):
    """The competition's wheelhouse is built for Kaggle's Python 3.12. Nine of its 41 wheels are compiled for 3.12
    alone; on Colab's 3.13 pip refuses the whole install if they are named. On 3.12 every wheel still installs."""
    fits = _kernel("wheel_fits")["wheel_fits"]
    for name in ("swegemma-0.2.11-py3-none-any.whl", "astor-0.8.1-py2.py3-none-any.whl",
                 "interegular-0.3.3-py37-none-any.whl", "bitsandbytes-0.46.1-py3-none-manylinux_2_24_x86_64.whl",
                 "vllm-0.19.1-cp38-abi3-manylinux_2_31_x86_64.whl",
                 "safetensors-0.8.0-cp310-abi3-manylinux_2_17_x86_64.manylinux2014_x86_64.whl"):
        assert fits(name, (3, 12)) and fits(name, (3, 13)), name
    only_312 = "xgrammar-0.2.5.post1-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl"
    assert fits(only_312, (3, 12)) and not fits(only_312, (3, 13))
    assert not fits("vllm-0.19.1-cp314-abi3-manylinux_2_31_x86_64.whl", (3, 13))     # abi3 from a later Python
    src = (REPO_ROOT / "kaggle" / "official_agent_kernel.py").read_text()
    assert 'result["wheels_left_out"]' in src                                        # and the run says which


def test_a_colab_run_keeps_its_inputs_and_output_out_of_kaggles_folders(co):
    """Colab's own /kaggle/input cannot be written to: the inputs and the output go under /content, laid out the same
    way, and the kernel is told where both are."""
    assert str(co.KAGGLE).startswith("/content/")
    env = co.kernel_paths(co.KAGGLE)
    assert env == {"HTL_INPUT": str(co.KAGGLE / "input"), "HTL_OUT": str(co.KAGGLE / "working")}


# --- a Colab session can drop (the owner runs it from a phone): an arm picks up where it stopped (#687) -----------

def test_a_batch_that_starts_again_keeps_the_tasks_it_finished_and_runs_the_rest(tmp_path):
    """On Kaggle a kernel starts with an empty output folder and nothing is found. On Colab the helper gives a run
    its own earlier output back, and the kernel then runs only what was not run. A task that was skipped, or had no
    answer from the model server, was not run and is run."""
    earlier = _kernel("earlier_runs")["earlier_runs"]
    assert earlier(tmp_path, ["a", "b"]) == {}                              # a first start: nothing there
    for iid, one in {"a": {"instance_id": "a", "patch": "diff", "llm_call_count": 7, "tool_call_count": 9},
                     "b": {"instance_id": "b", "is_skipped": True, "skip_reason_text": "the kernel's time budget ran out"},
                     "c": {"instance_id": "c", "llm_call_count": 0, "agent_error": "Connection error."},
                     "d": {"instance_id": "d", "llm_call_count": 0, "agent_error": "the prompt names an unset variable"},
                     "e": {"instance_id": "e", "error": "ValueError: a task that broke in the kernel"}}.items():
        (tmp_path / "tasks" / iid).mkdir(parents=True)
        (tmp_path / "tasks" / iid / "result.json").write_text(json.dumps(one))
    (tmp_path / "tasks" / "f").mkdir()                                       # in flight when the session dropped
    (tmp_path / "tasks" / "g").mkdir()
    (tmp_path / "tasks" / "g" / "result.json").write_text('{"instance_id": "g", "pat')   # cut off mid-write
    kept = earlier(tmp_path, ["a", "b", "c", "d", "e", "f", "g", "h"])
    assert sorted(kept) == ["a", "d", "e"]                                   # run, whatever came of it: kept as it was
    assert kept["a"]["patch"] == "diff" and kept["a"]["is_resumed"] is True
    src = (REPO_ROOT / "kaggle" / "official_agent_kernel.py").read_text()
    assert "runs: dict = earlier_runs(OUT, meta[\"instance_ids\"])" in src


def test_a_run_reads_what_its_own_earlier_start_left_on_kaggle(co, tmp_path):
    assert co.earlier_output(tmp_path) == ("fresh", 0)                       # no such dataset, or nothing in it
    work = tmp_path / "working"
    for iid in ("a", "b"):
        (work / "tasks" / iid).mkdir(parents=True)
        (work / "tasks" / iid / "result.json").write_text("{}")
    (work / "tasks" / "c").mkdir()                                           # in flight: no result yet
    assert co.earlier_output(tmp_path) == ("partial", 2)
    (work / "result.json").write_text(json.dumps({"error": "ModuleNotFoundError: docker", "finished_ts": "t"}))
    assert co.earlier_output(tmp_path) == ("partial", 2)                     # its kernel ended on an error: go on
    (work / "result.json").write_text(json.dumps({"finished_ts": "2026-11-12T03:00:00Z", "runs": {}}))
    assert co.earlier_output(tmp_path) == ("finished", 2)                    # nothing to do: not run a second time


def test_an_earlier_starts_telemetry_is_kept_beside_the_new_starts(co, tmp_path):
    """The kernel opens its GPU samples and its spans afresh each start; what an earlier start wrote is set aside
    under its own name, and the runner reads the parts as one."""
    (tmp_path / "gpu_samples.csv").write_text("timestamp,gpu_index,utilization_pct,memory_used_mb,power_w\n1,0,50,100,60\n")
    (tmp_path / "telemetry.jsonl").write_text('{"name": "first"}\n')
    co.set_aside_parts(tmp_path)
    assert not (tmp_path / "gpu_samples.csv").exists() and not (tmp_path / "telemetry.jsonl").exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == ["gpu_samples_before_1.csv", "telemetry_before_1.jsonl"]
    (tmp_path / "gpu_samples.csv").write_text("timestamp,gpu_index,utilization_pct,memory_used_mb,power_w\n2,0,70,100,65\n")
    co.set_aside_parts(tmp_path)
    assert (tmp_path / "gpu_samples_before_2.csv").exists() and (tmp_path / "gpu_samples_before_1.csv").exists()


def test_the_runner_reads_the_parts_of_a_resumed_runs_telemetry_as_one(run, tmp_path):
    head = "timestamp,gpu_index,utilization_pct,memory_used_mb,power_w\n"
    (tmp_path / "gpu_samples_before_1.csv").write_text(head + "1,0,50,100,60\n")
    (tmp_path / "gpu_samples_before_2.csv").write_text(head + "2,0,55,100,61\n")
    (tmp_path / "gpu_samples.csv").write_text(head + "3,0,70,100,65\n")
    (tmp_path / "telemetry_before_1.jsonl").write_text('{"name": "first"}\n')
    (tmp_path / "telemetry.jsonl").write_text('{"name": "second"}\n')
    run.merge_parts(tmp_path)
    assert (tmp_path / "gpu_samples.csv").read_text() == head + "1,0,50,100,60\n2,0,55,100,61\n3,0,70,100,65\n"
    assert (tmp_path / "telemetry.jsonl").read_text() == '{"name": "first"}\n{"name": "second"}\n'
    run.merge_parts(tmp_path)                                               # a second collection changes nothing
    assert (tmp_path / "gpu_samples.csv").read_text().count("timestamp") == 1


def _fake_colab(co, monkeypatch, tmp_path, state):
    """`run_one` with everything outside this file stood in for: no GPU, no pip, no Kaggle."""
    import subprocess
    import sys
    import types
    calls = {"uploads": [], "fetched": 0}
    monkeypatch.setattr(co, "LOG", tmp_path / "content" / "htl_colab.log")
    monkeypatch.setattr(co, "KAGGLE", tmp_path / "content" / "htl_kaggle")
    monkeypatch.setattr(co, "run", lambda command, **k: subprocess.CompletedProcess(command, 0, "", ""))
    monkeypatch.setattr(co, "upload", lambda api, user, label, out, note: calls["uploads"].append(note))
    monkeypatch.setattr(co, "send_until_taken", lambda send, **k: (send(), True)[1])
    monkeypatch.setattr(co, "listed_entry", lambda label: {"label": label, "network_open_acknowledged": True})

    def restore(api, user, label, out, resume_session=None):
        if isinstance(state, BaseException):
            raise state
        return state
    monkeypatch.setattr(co, "restore", restore)

    def fetch(*a, **k):
        calls["fetched"] += 1
        raise RuntimeError("the test stops here: nothing is downloaded")
    monkeypatch.setattr(co, "fetch", fetch)
    monkeypatch.setattr(co, "listed_model", lambda label: co.MODEL)   # the run list is not read in these tests
    api = types.SimpleNamespace(authenticate=lambda: None, dataset_list=lambda **k: [])
    kaggle_mod = types.ModuleType("kaggle.api.kaggle_api_extended")
    kaggle_mod.KaggleApi = lambda: api
    for name, mod in (("kagglehub", types.ModuleType("kagglehub")), ("kaggle", types.ModuleType("kaggle")),
                      ("kaggle.api", types.ModuleType("kaggle.api")), ("kaggle.api.kaggle_api_extended", kaggle_mod)):
        monkeypatch.setitem(sys.modules, name, mod)
    return calls


def test_a_run_that_already_finished_is_not_made_again_and_nothing_is_uploaded_over_it(co, monkeypatch, tmp_path):
    """A new version of a Kaggle dataset replaces its files. A notebook started again must not put an empty output
    over an arm's finished results."""
    calls = _fake_colab(co, monkeypatch, tmp_path, ("finished", 93))
    assert co.run_one("colab-statement", "x/y", kernel_dataset="x/k", user="someone") == 0
    assert calls == {"uploads": [], "fetched": 0}


def test_a_run_whose_earlier_output_cannot_be_read_stops_without_uploading_over_it(co, monkeypatch, tmp_path):
    calls = _fake_colab(co, monkeypatch, tmp_path, SystemExit("someone/htlnlp-colab-official-colab-graph exists and could not be read"))
    assert co.run_one("colab-graph", "x/y", kernel_dataset="x/k", user="someone") == 1
    assert calls == {"uploads": [], "fetched": 0}
    assert not list((tmp_path / "content").glob("htl_not_sent_*"))          # nothing on the machine is worth keeping it for


def test_a_run_that_goes_on_sends_a_first_note_and_its_log_however_it_ends(co, monkeypatch, tmp_path):
    calls = _fake_colab(co, monkeypatch, tmp_path, ("partial", 40))
    assert co.run_one("colab-graph", "x/y", kernel_dataset="x/k", user="someone") == 1    # the stand-in fetch stopped it
    assert calls["fetched"] == 1 and calls["uploads"] == ["started", "finished, kernel exit 1"]


# --- Kaggle's whole-dataset download answers "not found" for the arms' 1.2 GB bundles (#687) -----------------------

class _FakeFiles:
    """A stand-in for the Kaggle client: files listed a page at a time, and each downloaded on its own."""
    def __init__(self, names, zipped=(), flat=False):
        self.names, self.zipped, self.pages, self.whole, self.flat = list(names), set(zipped), 0, 0, flat

    def dataset_list_files(self, ref, page_token=None, page_size=20):
        import types
        self.pages += 1
        start = int(page_token or 0)
        chunk = self.names[start:start + 2]
        nxt = str(start + 2) if start + 2 < len(self.names) else ""
        return types.SimpleNamespace(files=[types.SimpleNamespace(name=n) for n in chunk], next_page_token=nxt)

    def dataset_download_file(self, ref, file_name, path=None, quiet=True, **k):
        import zipfile
        from pathlib import Path
        base = Path(file_name).name
        where = Path(path) / (base if self.flat else file_name)   # the client writes <path>/<name>, folders and all
        where.parent.mkdir(parents=True, exist_ok=True)
        if file_name in self.zipped:                      # Kaggle hands some files over zipped
            with zipfile.ZipFile(where.with_name(base + ".zip"), "w") as z:
                z.writestr(base, "text of " + file_name)
        else:
            where.write_text("text of " + file_name)

    def dataset_download_files(self, ref, path=None, unzip=True, quiet=True):
        self.whole += 1
        raise RuntimeError("404 Client Error: Not Found for url: .../DownloadDataset")


def test_a_dataset_whose_whole_download_is_refused_is_fetched_file_by_file(co, monkeypatch, tmp_path):
    """The first arm stopped twice on Kaggle's "not found" for its bundle's whole download, though the dataset was
    ready and each of its files could be had. Each file then goes where its name says, zipped or not."""
    monkeypatch.setattr(co, "say", lambda message: None)
    api = _FakeFiles(["official_batch.json", "sealed/a.bin", "sealed/b.bin", "submission/agent.yaml",
                      "submission/prompts/system.md"], zipped=["submission/agent.yaml"])
    co.download_dataset(api, "someone/htlnlp-official-colab-statement", tmp_path / "bundle")
    got = sorted(str(p.relative_to(tmp_path / "bundle")) for p in (tmp_path / "bundle").rglob("*") if p.is_file())
    assert got == ["official_batch.json", "sealed/a.bin", "sealed/b.bin", "submission/agent.yaml",
                   "submission/prompts/system.md"]
    assert (tmp_path / "bundle" / "submission" / "agent.yaml").read_text() == "text of submission/agent.yaml"
    assert api.whole == 1 and api.pages == 3              # the whole download was tried once; every page was read
    assert not (tmp_path / "bundle" / "sealed" / "sealed").exists()          # no folder inside its own name
    flat = _FakeFiles(["official_batch.json", "sealed/a.bin"], flat=True)    # a client that writes bare file names
    co.download_dataset(flat, "someone/x", tmp_path / "flat")
    assert sorted(str(p.relative_to(tmp_path / "flat")) for p in (tmp_path / "flat").rglob("*") if p.is_file()) == [
        "official_batch.json", "sealed/a.bin"]


def test_a_run_made_again_under_a_new_name_keeps_its_own_results(co):
    """A notebook does not make a run twice in one session. A run that stopped before it began is listed again as
    `<label>-try<n>`: the notebook takes it for a new run, and its results still go where the arm's go."""
    assert co.base_label("colab-statement-try2") == "colab-statement"
    assert co.base_label("colab-graph-try12") == "colab-graph"
    assert co.base_label("colab-statement") == "colab-statement"
    assert co.base_label("retry-statement") == "retry-statement"
    assert co.results_ref("someone", co.base_label("colab-graph-try2")) == "someone/htlnlp-colab-official-colab-graph"


# --- two notebook sessions made the first arm at once, on two GPUs (#687) ------------------------------------------

SMI_A100 = "name, memory.total [MiB], driver_version\nNVIDIA A100-SXM4-40GB, 40960 MiB, 580.82.07\n"
SMI_L4 = "name, memory.total [MiB], driver_version\nNVIDIA L4, 23034 MiB, 580.82.07\n"


def test_the_machines_gpu_is_read_from_what_nvidia_smi_printed(co):
    assert co.gpu_name(SMI_A100) == "NVIDIA A100-SXM4-40GB"
    assert co.gpu_name(SMI_L4) == "NVIDIA L4"
    assert co.gpu_name("") == "" and co.gpu_name("name, memory.total [MiB], driver_version\n") == ""


def test_a_run_that_names_its_gpu_is_made_only_on_a_machine_that_has_it(co):
    """The run list offers a run to every session that reads it. Two sessions read it, and both made the first arm.
    An entry can name the GPU it is for, so each session makes only its own second arm."""
    assert co.is_for_this_gpu("A100", "NVIDIA A100-SXM4-40GB") and co.is_for_this_gpu("a100", "NVIDIA A100-SXM4-40GB")
    assert co.is_for_this_gpu("L4", "NVIDIA L4")
    assert not co.is_for_this_gpu("A100", "NVIDIA L4") and not co.is_for_this_gpu("L4", "NVIDIA A100-SXM4-40GB")
    assert not co.is_for_this_gpu("L4", "NVIDIA L40S")                       # a whole name, not the start of another
    assert co.is_for_this_gpu(None, "NVIDIA L4") and co.is_for_this_gpu("", "Tesla T4")   # no GPU named: made anywhere
    assert co.is_for_this_gpu("A100", "")                # a GPU that could not be read does not stop a run


def test_a_run_looks_up_the_gpu_its_entry_names(co, monkeypatch):
    """A session that began before entries could name a GPU hands a run only its label, bundle and kernel, so the run
    reads its own entry. A list that cannot be read does not stop a run."""
    monkeypatch.setattr(co, "say", lambda message: None)
    plan = {"runs": [{"label": "colab-statement-try2", "bundle": "x/s"},
                     {"label": "colab-graph-try2", "bundle": "x/g", "gpu": "A100"},
                     {"label": "colab-graph-l4", "bundle": "x/g", "gpu": "L4"}]}
    assert co.listed_gpu("colab-graph-try2", get=_lists(plan)) == "A100"
    assert co.listed_gpu("colab-graph-l4", get=_lists(plan)) == "L4"
    assert co.listed_gpu("colab-statement-try2", get=_lists(plan)) is None
    assert co.listed_gpu("not-listed", get=_lists(plan)) is None
    calls = {"n": 0}

    def blinks(name):
        calls["n"] += 1
        if calls["n"] < 3:
            raise OSError("the network blinked")
        return json.dumps(plan)
    assert co.listed_gpu("colab-graph-l4", get=blinks, sleep=lambda s: None) == "L4"       # read again, then found

    def never(name):
        raise OSError("down")
    assert co.listed_gpu("colab-graph-l4", get=never, sleep=lambda s: None) is None


def _with_gpu(co, monkeypatch, smi: str, wanted):
    import subprocess
    monkeypatch.setattr(co, "run", lambda command, **k: subprocess.CompletedProcess(
        command, 0, smi if command[0] == "nvidia-smi" else "", ""))
    monkeypatch.setattr(co, "listed_entry",
                        lambda label: {"label": label, "gpu": wanted, "network_open_acknowledged": True})


def test_a_run_for_another_gpu_is_not_made_here_and_touches_nothing(co, monkeypatch, tmp_path):
    """The L4 session must not take the A100 session's second arm: it would be given that arm's unfinished output and
    go on from it. Nothing is restored, fetched or uploaded, and the earlier run's output on this machine stays put."""
    calls = _fake_colab(co, monkeypatch, tmp_path, ("partial", 40))
    _with_gpu(co, monkeypatch, SMI_L4, "A100")
    said = []
    monkeypatch.setattr(co, "say", said.append)
    earlier = tmp_path / "content" / "htl_kaggle" / "working"
    earlier.mkdir(parents=True)
    (earlier / "result.json").write_text("{}")
    assert co.run_one("colab-graph-try2", "x/y", kernel_dataset="x/k", user="someone") == 0
    assert calls == {"uploads": [], "fetched": 0}
    assert (earlier / "result.json").exists()                                # not set aside
    assert any("A100" in s and "NVIDIA L4" in s and "not made here" in s for s in said)


def test_a_run_for_this_gpu_or_for_any_gpu_is_made(co, monkeypatch, tmp_path):
    calls = _fake_colab(co, monkeypatch, tmp_path, ("fresh", 0))
    _with_gpu(co, monkeypatch, SMI_L4, "L4")
    assert co.run_one("colab-graph-l4", "x/y", kernel_dataset="x/k", user="someone") == 1   # the stand-in fetch stopped it
    assert calls["fetched"] == 1 and calls["uploads"] == ["started", "finished, kernel exit 1"]
    calls = _fake_colab(co, monkeypatch, tmp_path, ("fresh", 0))
    _with_gpu(co, monkeypatch, SMI_A100, None)
    assert co.run_one("colab-statement-try2", "x/y", kernel_dataset="x/k", user="someone") == 1
    assert calls["fetched"] == 1


def test_the_l4_sessions_second_arm_goes_to_a_dataset_of_its_own(co):
    assert co.results_ref("someone", co.base_label("colab-graph-l4")) == "someone/htlnlp-colab-official-colab-graph-l4"
    assert co.results_ref("someone", co.base_label("colab-graph-try2")) == "someone/htlnlp-colab-official-colab-graph"


def test_the_run_list_gives_each_session_its_own_second_arm():
    plan = json.loads((REPO_ROOT / "kaggle" / "colab_official_run.json").read_text())
    by_label = {r["label"]: r for r in plan["runs"]}
    assert by_label["colab-graph-try2"]["gpu"] == "A100" and by_label["colab-graph-l4"]["gpu"] == "L4"
    assert by_label["colab-graph-l4"]["bundle"] == by_label["colab-graph-try2"]["bundle"]            # the same sealed tasks
    assert by_label["colab-graph-l4"]["kernel_dataset"] == by_label["colab-graph-try2"]["kernel_dataset"]
    assert "gpu" not in by_label["colab-statement-try2"]          # both sessions were already making it


def test_the_report_arm_is_listed_for_the_session_that_made_the_registered_pair_and_after_it():
    """Addendum 3 (#687): the failing test's report as a third arm on the same machine as the pair. It is listed last,
    for the A100 alone, with a bundle and results of its own: the L4 session passes it by."""
    plan = json.loads((REPO_ROOT / "kaggle" / "colab_official_run.json").read_text())
    labels = [r["label"] for r in plan["runs"]]
    report = plan["runs"][labels.index("colab-report")]
    assert labels.index("colab-report") > labels.index("colab-graph-try2")
    assert report["gpu"] == "A100"
    assert report["bundle"].endswith("/htlnlp-official-colab-report")
    assert report["kernel_dataset"].endswith("/htlnlp-colab-kernel-colab-report")
    assert "model" not in report                                    # the E4B arms name no model: they get the default
    assert len({r["bundle"] for r in plan["runs"]}) == 3            # one sealed bundle per text given with the task


E2B = "google/gemma-4/other/gemma-4-e2b-it-qat-w4a16-ct/2"


def test_a_run_entry_can_name_its_model_and_one_that_names_none_gets_e4b(co, monkeypatch):
    """028 AI12 (#748): the kernel serves the one model the submission declares and looks for it under the inputs, so
    an E2B arm needs the E2B model mounted. An entry names its model; the E4B arms' entries name none and keep E4B."""
    monkeypatch.setattr(co, "say", lambda message: None)
    plan = {"runs": [{"label": "colab-statement-try2", "bundle": "x/s"},
                     {"label": "colab-e2b-statement", "bundle": "x/e", "gpu": "A100", "model": E2B}]}
    assert co.listed_model("colab-e2b-statement", get=_lists(plan)) == E2B
    assert co.listed_model("colab-statement-try2", get=_lists(plan)) == co.MODEL
    assert co.listed_model("not-listed", get=_lists(plan)) == co.MODEL
    assert co.MODEL == "google/gemma-4/other/gemma-4-e4b-it-qat-w4a16-ct/2"   # the default is unchanged
    calls = {"n": 0}

    def blinks(name):
        calls["n"] += 1
        if calls["n"] < 3:
            raise OSError("the network blinked")
        return json.dumps(plan)
    assert co.listed_model("colab-e2b-statement", get=blinks, sleep=lambda s: None) == E2B   # read again, then found


def test_a_run_list_that_cannot_be_read_stops_the_run_rather_than_guess_its_model(co, monkeypatch):
    """Guessing E4B for an E2B arm would load a model the submission does not declare. Unlike the GPU, which a run
    can do without, the model must be known."""
    monkeypatch.setattr(co, "say", lambda message: None)

    def never(name):
        raise OSError("down")
    with pytest.raises(SystemExit, match="which model colab-e2b-statement is for"):
        co.listed_model("colab-e2b-statement", get=never, sleep=lambda s: None)


def test_a_bad_model_handle_in_the_run_list_stops_the_run(co, monkeypatch):
    monkeypatch.setattr(co, "say", lambda message: None)
    plan = {"runs": [{"label": "colab-e2b-statement", "bundle": "x/e", "model": "google/gemma-4"}]}
    with pytest.raises(SystemExit, match="owner/model/framework/variation/version"):
        co.listed_model("colab-e2b-statement", get=_lists(plan))


def test_a_run_downloads_and_mounts_the_model_its_entry_names(co, monkeypatch, tmp_path):
    """`fetch` puts the named model where Kaggle mounts it, and `run_one` hands it the model its entry names."""
    import types
    monkeypatch.setattr(co, "say", lambda message: None)
    asked = []

    def model_download(handle):
        asked.append(handle)
        got = tmp_path / "cache" / handle.split("/")[3]
        got.mkdir(parents=True)
        (got / "config.json").write_text("{}")
        return str(got)
    hub = types.SimpleNamespace(model_download=model_download)
    for ref in (co.WHEELHOUSE, "x/htlnlp-official-colab-e2b-statement"):
        (co.dataset_dir(ref, tmp_path)).mkdir(parents=True)
        (co.dataset_dir(ref, tmp_path) / "f").write_text("")
    monkeypatch.setattr(co, "LOG", tmp_path / "htl_colab.log")
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen", lambda url, timeout=60: types.SimpleNamespace(read=lambda: b"# k"))
    listing = types.SimpleNamespace(files=[types.SimpleNamespace(name="f", total_bytes=0)], next_page_token="")
    api = types.SimpleNamespace(dataset_list_files=lambda ref, page_token=None, page_size=20: listing)
    co.fetch(api, hub, "x/htlnlp-official-colab-e2b-statement", None, "https://example.org/k.py", root=tmp_path,
             handle=E2B)
    assert asked == [E2B]
    assert (co.model_dir(tmp_path, E2B) / "config.json").exists()
    assert not co.model_dir(tmp_path).exists()                      # the E4B model is not fetched for an E2B run


def test_run_one_passes_the_listed_model_to_fetch(co, monkeypatch, tmp_path):
    calls = _fake_colab(co, monkeypatch, tmp_path, ("fresh", 0))
    _with_gpu(co, monkeypatch, SMI_A100, "A100")
    seen = []

    def fetch(*a, **k):
        seen.append(k.get("handle"))
        raise RuntimeError("the test stops here: nothing is downloaded")
    monkeypatch.setattr(co, "fetch", fetch)
    monkeypatch.setattr(co, "listed_model", lambda label: E2B if label == "colab-e2b-statement" else co.MODEL)
    assert co.run_one("colab-e2b-statement", "x/y", kernel_dataset="x/k", user="someone") == 1
    assert co.run_one("colab-report", "x/y", kernel_dataset="x/k", user="someone") == 1
    assert co.run_one("colab-report", "x/y", kernel_dataset="x/k", user="someone", model=E2B) == 1   # given outright
    assert seen == [E2B, co.MODEL, E2B]
    assert calls["uploads"][0] == "started"


def test_the_superseded_e2b_colab_arm_is_not_listed():
    """028 AI12 (#748): the E2B arm was listed for Colab, then moved to Kaggle before any session made it. A notebook
    makes every run the list names, whatever `stop` says, so the entry is gone, not merely stopped."""
    plan = json.loads((REPO_ROOT / "kaggle" / "colab_official_run.json").read_text())
    assert "colab-e2b-statement" not in [r["label"] for r in plan["runs"]]
    assert plan.get("stop") is True


def test_a_colab_run_can_be_read_from_one_version_of_its_dataset_and_only_from_the_session_meant(run):
    """Two sessions uploaded to one dataset in turn, so "the latest version" is whichever sent last. An arm is read
    from a version by number, and only if that version's log opens with the session it is meant to be."""
    assert run.colab_results_url("someone/htlnlp-colab-official-colab-statement") == (
        "https://www.kaggle.com/datasets/someone/htlnlp-colab-official-colab-statement")
    assert run.colab_results_url("someone/htlnlp-colab-official-colab-statement/31") == (
        "https://www.kaggle.com/datasets/someone/htlnlp-colab-official-colab-statement/versions/31")
    log = "[01:17:24Z] run colab-statement: bundle x\n[01:17:24Z] $ nvidia-smi\nNVIDIA A100-SXM4-40GB\n[02:04:33Z] starting the kernel\n"
    assert run.colab_session(log) == "01:17:24"
    assert run.colab_session("no stamp here\n") is None
    run.check_colab_session(log, "01:17:24")                                # the session meant: nothing happens
    run.check_colab_session(log, None)                                      # none named: nothing is checked
    with pytest.raises(SystemExit, match="00:37:11"):
        run.check_colab_session(log, "00:37:11")


def test_once_merged_the_notebook_and_the_helper_read_main(co):
    """The runs of #687 were made from their feature branch, which goes when it is merged. On `main` the notebook and
    the helper read `main`, and the run list says stop, so a notebook opened there makes nothing and gives its GPU
    back. A later run is listed on a branch of its own, with both pointed at that branch while it is made (this test
    fails there until the branch's last commit points them back and sets stop: it is not mergeable before)."""
    code = "".join("".join(c["source"]) for c in json.loads(NOTEBOOK.read_text())["cells"] if c["cell_type"] == "code")
    assert 'BRANCH = "main"' in code
    assert co.BRANCH_FILES.endswith("/refs/heads/main/kaggle/")
    assert json.loads((REPO_ROOT / "kaggle" / "colab_official_run.json").read_text()).get("stop") is True


def test_the_committed_colab_settings_say_the_agents_commands_could_reach_the_network():
    """The five Colab runs' settings files said the proxies kept the run from the network. They were set on the
    kernel's process and did not reach the agent's commands (the review of #690), so each file says so, and keeps the
    audit that read every command."""
    runs = TASKS_DIR / "official_agent_runs"
    for label in ("colab-statement", "colab-graph", "colab-report", "colab-statement-l4", "colab-graph-l4"):
        s = json.loads((runs / f"gemma-4-e4b-it-qat-w4a16-ct_swegemma_{label}_settings.json").read_text())
        assert "could reach the network" in s["kernel"]["internet"], label
        assert "no credential" in s["kernel"]["internet"], label
        assert s["network_audit"]["traced_task_count"] == 93, label
        assert any(n.startswith("Corrected on November 12, 2026") for n in s["notes"]), label


# --- #691: the helper's quiet failures, each with a stand-in for Kaggle and the machine, never the real thing ------

class _HttpError(Exception):
    """What the Kaggle client raises for an HTTP answer: requests' HTTPError carries the response."""
    def __init__(self, code):
        import types
        super().__init__(f"{code} Client Error")
        self.response = types.SimpleNamespace(status_code=code)


class _FakeKaggle:
    """A stand-in for the Kaggle client's dataset calls: each dataset is a dict of file name -> bytes."""
    def __init__(self, datasets=None, status_error=None, version_answer=("ok", ""), new_answer=("ok", ""),
                 version_raises=None, truncate=()):
        self.datasets = {k: dict(v) for k, v in (datasets or {}).items()}
        self.status_error, self.version_answer, self.new_answer = status_error, version_answer, new_answer
        self.version_raises, self.truncate = version_raises, set(truncate)
        self.calls, self.staged = [], []

    def dataset_status(self, ref):
        self.calls.append(("status", ref))
        if self.status_error is not None:
            raise self.status_error
        if ref not in self.datasets:
            raise _HttpError(404)
        return "ready"

    username = "someone"   # whose token this is, as Kaggle reports it after checking the token

    def get_config_value(self, name):
        return self.username if name == "username" else None

    def dataset_list(self, user=None, search=None, mine=False, page=1, **k):
        """The token owner's own datasets (`mine`) whose slug holds `search`, private ones included, 20 to a page as
        kaggle 2.2.5 asks for them; or the error or odd answer set for the listing."""
        import types
        self.calls.append(("datasets", mine, search, page))
        if getattr(self, "list_error", None) is not None:
            raise self.list_error
        if hasattr(self, "list_answer"):
            return self.list_answer
        rows = [types.SimpleNamespace(ref=r) for r in getattr(self, "decoys", []) + sorted(self.datasets)
                if mine and r.split("/")[0].lower() == self.username.lower()
                and (search or "").lower() in r.split("/")[-1].lower()]
        return rows[(page - 1) * 20: page * 20]

    def _take(self, folder):
        from pathlib import Path
        files = {str(p.relative_to(folder)): p.read_bytes() for p in Path(folder).rglob("*") if p.is_file()}
        self.staged.append(files)
        return files

    def dataset_create_version(self, folder, version_notes=None, **k):
        import types
        self.calls.append(("version", version_notes))
        if self.version_raises is not None:
            raise self.version_raises
        self._take(folder)
        return types.SimpleNamespace(status=self.version_answer[0], error=self.version_answer[1], invalidTags=[])

    def dataset_create_new(self, folder, public=True, **k):
        import types
        self.calls.append(("new", public))
        self._take(folder)
        return types.SimpleNamespace(status=self.new_answer[0], error=self.new_answer[1], invalidTags=[])

    def dataset_list_files(self, ref, page_token=None, page_size=20):
        import types
        self.calls.append(("list", ref))
        return types.SimpleNamespace(files=[types.SimpleNamespace(name=n, total_bytes=len(b))
                                            for n, b in sorted(self.datasets[ref].items())], next_page_token="")

    def dataset_download_files(self, ref, path=None, unzip=True, quiet=True):
        from pathlib import Path
        self.calls.append(("download", ref))
        for name, data in self.datasets[ref].items():
            p = Path(path) / name
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data[: len(data) // 2] if ref in self.truncate else data)


def _on_machine(co, monkeypatch, tmp_path):
    """The helper's paths under tmp_path, its log quiet, and no waiting."""
    monkeypatch.setattr(co, "LOG", tmp_path / "content" / "htl_colab.log")
    monkeypatch.setattr(co, "KAGGLE", tmp_path / "content" / "htl_kaggle")
    monkeypatch.setattr(co, "say", lambda message: None)
    (tmp_path / "content").mkdir(parents=True, exist_ok=True)


# 1. A refused last upload must not be reported as sent.

def test_an_upload_kaggle_answers_with_an_error_is_not_taken(co, monkeypatch, tmp_path):
    """The client answers some refusals with a status of "error" and no exception. Either form is a refusal, so the
    last upload is tried again, and the GPU is kept when no try is taken."""
    _on_machine(co, monkeypatch, tmp_path)
    out = tmp_path / "content" / "htl_kaggle" / "working"
    out.mkdir(parents=True)
    (out / "result.json").write_text("{}")
    ref = "someone/htlnlp-colab-official-colab-graph"
    for api in (_FakeKaggle(new_answer=("error", "refused")),                               # a new dataset, refused
                _FakeKaggle({ref: {}}, version_answer=("error", "still processing")),       # a new version, refused
                _FakeKaggle({ref: {}}, version_raises=RuntimeError("409 Conflict"))):       # a refusal that raises
        with pytest.raises(Exception):
            co.upload(api, "someone", "colab-graph", out, "finished, kernel exit 0")
        assert co.send_until_taken(lambda: co.upload(api, "someone", "colab-graph", out, "finished"),
                                   tries=2, wait_seconds=0, sleep=lambda s: None) is False
    refused_version = _FakeKaggle({ref: {}}, version_raises=RuntimeError("409 Conflict"))
    with pytest.raises(Exception):
        co.upload(refused_version, "someone", "colab-graph", out, "finished")
    assert not any(c[0] == "new" for c in refused_version.calls)     # a refused version is not sent as a new dataset


def test_an_upload_kaggle_takes_is_sent_to_a_private_dataset_and_leaves_no_copy_behind(co, monkeypatch, tmp_path):
    _on_machine(co, monkeypatch, tmp_path)
    out = tmp_path / "content" / "htl_kaggle" / "working"
    (out / "tasks" / "a").mkdir(parents=True)
    (out / "tasks" / "a" / "result.json").write_text('{"patch": "diff"}')
    api = _FakeKaggle()
    co.upload(api, "someone", "colab-graph", out, "started")
    assert ("new", False) in api.calls                                        # private
    assert "working/tasks/a/result.json" in api.staged[0] and "session.json" in api.staged[0]
    assert json.loads(api.staged[0]["session.json"])["session_id"] == co.session_id()
    assert not (tmp_path / "content" / "htl_upload").exists()                 # the staged copy is removed
    api2 = _FakeKaggle({"someone/htlnlp-colab-official-colab-graph": {}})
    co.upload(api2, "someone", "colab-graph", out, "still running")
    assert ("version", "still running") in api2.calls


# 3. A status call that fails is not "nothing to resume", and a session resumes only its own upload.

def _uploaded(session, tasks=("a", "b"), finished=False):
    files = {f"working/tasks/{i}/result.json": b'{"patch": "x"}' for i in tasks}
    if finished:
        files["working/result.json"] = json.dumps({"finished_ts": "2026-11-12T03:00:00Z", "runs": {}}).encode()
    if session is not None:
        files["session.json"] = json.dumps({"session_id": session}).encode()
    return files


def test_a_status_call_that_fails_stops_the_run_and_only_a_missing_dataset_is_a_fresh_start(co, monkeypatch, tmp_path):
    _on_machine(co, monkeypatch, tmp_path)
    out = tmp_path / "content" / "htl_kaggle" / "working"
    assert co.restore(_FakeKaggle(), "someone", "colab-graph", out, sleep=lambda s: None) == ("fresh", 0)
    for failure in (ConnectionError("the network blinked"), _HttpError(500), _HttpError(401)):
        with pytest.raises(SystemExit, match="could not tell"):
            co.restore(_FakeKaggle(status_error=failure), "someone", "colab-graph", out, sleep=lambda s: None)


def test_a_403_for_a_dataset_the_owner_does_not_have_is_a_fresh_start_and_any_doubt_still_stops(co, monkeypatch,
                                                                                                 tmp_path):
    """#815: Kaggle answers 403, not 404, for a private dataset that does not exist, so a run with a new label stopped
    before its first upload. After a 403, the token owner's own datasets, every page of them, say whether it is
    there; anything less than a full answer from the owner's own token still stops the run."""
    _on_machine(co, monkeypatch, tmp_path)
    out = tmp_path / "content" / "htl_kaggle" / "working"
    ref = "someone/htlnlp-colab-official-colab-graph"
    absent = _FakeKaggle({"someone/htlnlp-colab-official-colab-graph-l4": {}}, status_error=_HttpError(403))
    assert co.restore(absent, "someone", "colab-graph", out, sleep=lambda s: None) == ("fresh", 0)
    assert ("datasets", True, "htlnlp-colab-official-colab-graph", 1) in absent.calls   # its own list was read
    there = _FakeKaggle({ref: _uploaded(co.session_id())}, status_error=_HttpError(403))
    there.decoys = [f"someone/htlnlp-colab-official-colab-graph-arm{i:02d}" for i in range(25)]   # past page one
    assert co.dataset_exists(there, ref, sleep=lambda s: None) is True          # found on page two: never fresh
    assert ("datasets", True, "htlnlp-colab-official-colab-graph", 2) in there.calls
    upper = _FakeKaggle({"Someone/HTLNLP-colab-official-colab-graph": {}}, status_error=_HttpError(403))
    upper.username = "SOMEONE"
    assert co.dataset_exists(upper, ref, sleep=lambda s: None) is True          # Kaggle's names ignore case
    doubts = []
    other = _FakeKaggle(status_error=_HttpError(403))
    other.username = "someone-else"                                              # another account's token: cannot see
    doubts.append(other)
    broken = _FakeKaggle(status_error=_HttpError(403))
    broken.list_error = ConnectionError("the network blinked")
    doubts.append(broken)
    for answer in (None, [type("Row", (), {"ref": "htlnlp-colab-official-colab-graph"})()]):   # no answer; odd form
        odd = _FakeKaggle(status_error=_HttpError(403))
        odd.list_answer = answer
        doubts.append(odd)
    endless = _FakeKaggle(status_error=_HttpError(403))
    endless.decoys = [f"someone/htlnlp-colab-official-colab-graph-arm{i:04d}" for i in range(20 * co.LISTING_PAGES)]
    doubts.append(endless)                                                       # more pages than it reads
    for api in doubts:
        with pytest.raises(SystemExit, match="could not tell"):
            co.restore(api, "someone", "colab-graph", out, sleep=lambda s: None)
        assert sum(c[0] == "status" for c in api.calls) == 3                     # tried again before stopping
    assert co.is_forbidden(_HttpError(403)) and not co.is_forbidden(_HttpError(404))
    assert co.is_forbidden(RuntimeError("403 Client Error: Forbidden for url")) and not co.is_forbidden(_HttpError(401))


def test_a_session_resumes_its_own_upload_and_another_sessions_only_when_named(co, monkeypatch, tmp_path):
    """Two sessions on one GPU model, or a run list that cannot be read, would each take the other's upload for its
    own. Each upload says which session sent it, and a session goes on only from its own, or from the one the run's
    entry names (`resume_session`), after a session that dropped."""
    _on_machine(co, monkeypatch, tmp_path)
    out = tmp_path / "content" / "htl_kaggle" / "working"
    ref = "someone/htlnlp-colab-official-colab-graph"
    mine = co.session_id()
    assert mine == co.session_id()                                           # one id for the machine's whole session
    state = co.restore(_FakeKaggle({ref: _uploaded(mine)}), "someone", "colab-graph", out, sleep=lambda s: None)
    assert state == ("partial", 2) and (out / "tasks" / "a" / "result.json").exists()
    assert not (tmp_path / "content" / "htl_restore").exists()               # the downloaded copy is removed
    for other in ("20261112T003711Z-abcd1234", None):                         # another session's, or one from before
        with pytest.raises(SystemExit, match="resume_session"):
            co.restore(_FakeKaggle({ref: _uploaded(other)}), "someone", "colab-graph", out, sleep=lambda s: None)
    named = co.restore(_FakeKaggle({ref: _uploaded("20261112T003711Z-abcd1234")}), "someone", "colab-graph", out,
                       resume_session="20261112T003711Z-abcd1234", sleep=lambda s: None)
    assert named == ("partial", 2)
    done = co.restore(_FakeKaggle({ref: _uploaded("20261112T003711Z-abcd1234", finished=True)}), "someone",
                      "colab-graph", out, sleep=lambda s: None)
    assert done == ("finished", 2)                                           # a finished run is not made again by anyone


# 4. A bundle folder that is not empty is not complete.

def test_a_bundle_that_stopped_part_way_is_downloaded_again(co, monkeypatch, tmp_path):
    import shutil
    _on_machine(co, monkeypatch, tmp_path)
    monkeypatch.setattr(co, "WHEELHOUSE", "metric/wheels")
    bundle = {"official_batch.json": b"{}", "sealed/a.bin": b"A" * 64, "sealed/b.bin": b"B" * 64}
    api = _FakeKaggle({"metric/wheels": {"w-1.0-py3-none-any.whl": b"w" * 10}, "someone/htlnlp-official-x": bundle,
                       "someone/kernel-x": {"official_agent_kernel.py": b"print(1)"}})
    root = tmp_path / "content" / "htl_kaggle"
    dest = co.dataset_dir("someone/htlnlp-official-x", root)
    (dest / "sealed").mkdir(parents=True)
    (dest / "official_batch.json").write_bytes(b"{}")
    (dest / "sealed" / "a.bin").write_bytes(b"A" * 10)                       # cut short; b.bin never came
    co.fetch(api, None, "someone/htlnlp-official-x", "someone/kernel-x", None, root=root, with_model=False)
    assert ("download", "someone/htlnlp-official-x") in api.calls
    assert (dest / "sealed" / "a.bin").read_bytes() == b"A" * 64 and (dest / "sealed" / "b.bin").exists()
    api.calls.clear()
    co.fetch(api, None, "someone/htlnlp-official-x", "someone/kernel-x", None, root=root, with_model=False)
    assert ("download", "someone/htlnlp-official-x") not in api.calls        # complete: not downloaded again
    broken = _FakeKaggle(api.datasets, truncate=["someone/htlnlp-official-x"])
    shutil.rmtree(dest)
    with pytest.raises(SystemExit, match="sealed/a.bin"):
        co.fetch(broken, None, "someone/htlnlp-official-x", "someone/kernel-x", None, root=root, with_model=False)


# 5. An earlier run's output is sent, then removed, never set aside on the machine.

def test_an_earlier_runs_output_is_removed_once_it_is_on_kaggle(co, monkeypatch, tmp_path):
    calls = _fake_colab(co, monkeypatch, tmp_path, ("fresh", 0))
    work = tmp_path / "content" / "htl_kaggle" / "working"
    (work / "tasks" / "a").mkdir(parents=True)
    (work / "tasks" / "a" / "result.json").write_text('{"patch": "the first arm"}')
    (tmp_path / "content" / "htl_working_label").write_text("colab-statement")   # its results reached Kaggle
    seen = []

    def fetch(*a, **k):   # what is on the machine when this run's inputs are fetched, before its kernel starts
        seen.append((work / "tasks" / "a").exists() or bool(list(work.parent.glob("working_before_*"))))
        raise RuntimeError("the test stops here")
    monkeypatch.setattr(co, "fetch", fetch)
    co.run_one("colab-graph", "x/y", kernel_dataset="x/k", user="someone")
    assert seen == [False]
    assert not (work / "tasks" / "a").exists()
    assert not list((tmp_path / "content" / "htl_kaggle").glob("working_before_*"))


def test_an_earlier_runs_output_that_never_reached_kaggle_is_sent_first_and_kept_if_it_cannot_be(co, monkeypatch, tmp_path):
    _fake_colab(co, monkeypatch, tmp_path, ("fresh", 0))
    sent = []
    monkeypatch.setattr(co, "upload", lambda api, user, label, out, note: sent.append(label))
    work = tmp_path / "content" / "htl_kaggle" / "working"
    (work / "tasks" / "a").mkdir(parents=True)
    (work / "tasks" / "a" / "result.json").write_text("{}")
    (tmp_path / "content" / "htl_working_label").write_text("colab-statement")
    (tmp_path / "content" / "htl_not_sent_colab-statement").write_text("")
    co.run_one("colab-graph", "x/y", kernel_dataset="x/k", user="someone")
    assert sent[0] == "colab-statement" and not (work / "tasks" / "a").exists()
    assert not (tmp_path / "content" / "htl_not_sent_colab-statement").exists()
    calls = _fake_colab(co, monkeypatch, tmp_path, ("fresh", 0))
    monkeypatch.setattr(co, "send_until_taken", lambda send, **k: False)
    (work / "tasks" / "a").mkdir(parents=True)
    (work / "tasks" / "a" / "result.json").write_text("{}")
    (tmp_path / "content" / "htl_working_label").write_text("colab-statement")
    (tmp_path / "content" / "htl_not_sent_colab-statement").write_text("")
    assert co.run_one("colab-graph", "x/y", kernel_dataset="x/k", user="someone") == 1
    assert (work / "tasks" / "a" / "result.json").exists() and calls["fetched"] == 0   # kept, and no run over it


def test_a_finished_runs_output_leaves_the_machine_once_kaggle_has_it(co, monkeypatch, tmp_path):
    calls = _fake_colab(co, monkeypatch, tmp_path, ("partial", 1))
    work = tmp_path / "content" / "htl_kaggle" / "working"

    def restore(api, user, label, out, resume_session=None):
        (out / "tasks" / "a").mkdir(parents=True)
        (out / "tasks" / "a" / "result.json").write_text("{}")
        return "partial", 1
    monkeypatch.setattr(co, "restore", restore)
    co.run_one("colab-graph", "x/y", kernel_dataset="x/k", user="someone")
    assert calls["uploads"][-1].startswith("finished") and not work.exists()


def test_a_tool_call_naming_a_path_under_content_is_counted_outside_the_workspace(run):
    trace = {"steps": [{"tool_calls": [
        {"function_name": "read_file", "arguments": {"path": "/content/htl_kaggle/working_before_x/tasks/a/result.json"}},
        {"function_name": "run_command", "arguments": {"command": "ls /content"}},
        {"function_name": "read_file", "arguments": {"path": "docs/content/guide.md"}},
        {"function_name": "read_file", "arguments": {"path": "src/contents.py"}}]}]}
    assert run.trace_counts(trace)["outside_workspace_call_count"] == 2


# 2. A stop from the notebook's button ends the kernel and the uploader.

def test_a_kernel_starts_in_a_process_group_of_its_own_without_a_credential(co, monkeypatch, tmp_path):
    import os
    import time
    _on_machine(co, monkeypatch, tmp_path)
    monkeypatch.setenv("KAGGLE_API_TOKEN", "x")
    kernel = tmp_path / "k.py"
    kernel.write_text("import os, time\nopen('env.txt', 'w').write(','.join(sorted(os.environ)))\ntime.sleep(60)\n")
    out = tmp_path / "out"
    out.mkdir()
    with (tmp_path / "log").open("a") as log:
        proc = co.start_kernel(kernel, out, log)
    try:
        assert os.getpgid(proc.pid) == proc.pid                               # its own group, ended as one
        for _ in range(200):
            if (out / "env.txt").exists() and (out / "env.txt").read_text():
                break
            time.sleep(0.05)
        assert "KAGGLE_API_TOKEN" not in (out / "env.txt").read_text().split(",")
    finally:
        co.end_process_group(proc, grace_seconds=2)
    assert proc.poll() is not None


def test_a_stop_during_the_wait_ends_the_kernels_process_group_and_the_uploader(co, monkeypatch, tmp_path):
    """The notebook's stop button raises KeyboardInterrupt in the wait. The kernel's processes and the uploader must
    end with it, or the uploader goes on sending `working/`, by then the next run's, to this run's dataset."""
    import subprocess
    import threading
    import time
    _on_machine(co, monkeypatch, tmp_path)
    pidfile = tmp_path / "child.pid"
    proc = subprocess.Popen(["sh", "-c", f"sleep 300 & echo $! > {pidfile}; wait"], start_new_session=True)
    for _ in range(200):
        if pidfile.exists() and pidfile.read_text().strip():
            break
        time.sleep(0.05)
    child = int(pidfile.read_text())
    stop = threading.Event()
    uploader = threading.Thread(target=lambda: stop.wait(300), daemon=True)
    uploader.start()

    def interrupted(seconds):
        raise KeyboardInterrupt
    with pytest.raises(KeyboardInterrupt):
        co.wait_for_kernel(proc, stop, uploader, sleep=interrupted, grace_seconds=2)
    assert stop.is_set() and not uploader.is_alive() and proc.poll() is not None

    def gone(pid):
        try:
            with open(f"/proc/{pid}/stat") as f:
                return f.read().rsplit(")", 1)[1].split()[0] in ("Z", "X")
        except OSError:
            return True
    for _ in range(200):
        if gone(child):
            break
        time.sleep(0.05)
    assert gone(child), "the kernel's child process outlived the stop"


# 6. The network is open to the agent's commands: no run starts unless its entry says the operator accepts that.

def test_a_run_whose_entry_does_not_accept_an_open_network_is_not_started(co, monkeypatch, tmp_path):
    calls = _fake_colab(co, monkeypatch, tmp_path, ("fresh", 0))
    said = []
    monkeypatch.setattr(co, "say", said.append)
    for entry in ({"label": "colab-graph"}, {"label": "colab-graph", "network_open_acknowledged": "yes"}, None):
        monkeypatch.setattr(co, "listed_entry", lambda label, e=entry: e)
        assert co.run_one("colab-graph", "x/y", kernel_dataset="x/k", user="someone") == 1
        assert calls == {"uploads": [], "fetched": 0}
    assert any("network_open_acknowledged" in s for s in said)
    assert co.network_open_acknowledged({"network_open_acknowledged": True})


def test_the_committed_run_list_does_not_accept_an_open_network_for_any_run():
    """Accepting an open network is a decision for a later run's own branch (docs/adr/0005), not a default."""
    plan = json.loads((REPO_ROOT / "kaggle" / "colab_official_run.json").read_text())
    assert not any(r.get("network_open_acknowledged") for r in plan["runs"])
    assert (REPO_ROOT / "docs" / "adr" / "0005-colab-runs-need-the-open-network-accepted.md").exists()


# 7. The audit reads every tool call, with wider words.

def test_the_audit_counts_what_the_word_list_missed(co):
    for missed in ("python -c 'import socket; socket.create_connection((\"x\", 80))'", "pip -q install requests",
                   "python -m pip --quiet install foo", "git -C repo pull", "git -c http.proxy= fetch origin",
                   "uv pip install foo", "python -c 'import http.client'", "bash -c 'cat < /dev/tcp/x/80'",
                   "huggingface-cli download org/model", "python -c 'import aiohttp'"):
        assert co.network_command_count([missed]) == 1, missed
    for innocent in ("pytest -q tests", "git status", "git -C repo log --oneline", "grep -rn 'https://' docs",
                     "pip list", "pip show requests", "python -c 'print(1)'"):
        assert co.network_command_count([innocent]) == 0, innocent


def test_the_audit_reads_every_tool_call_not_only_run_command(run):
    """A script written and then run, and run_skill_script, were outside an audit of run_command alone."""
    skill = {"skill": "s", "script": "curl -s https://example.org"}
    trace = {"steps": [{"tool_calls": [
        {"function_name": "write_file", "arguments": {"path": "fetch.py", "content": "import socket\nsocket.socket()\n"}},
        {"function_name": "run_command", "arguments": {"command": "python fetch.py"}},
        {"function_name": "run_skill_script", "arguments": skill}]}]}
    assert run.trace_commands(trace) == ["python fetch.py", json.dumps(skill)]
    audit = run.network_audit({"a": trace})
    assert audit["network_command_count"] == 1                               # the skill's script
    assert audit["tool_call_count"] == 3 and audit["network_tool_call_count"] == 2   # and the written script
    assert audit["tool_call_instance_ids"] == ["a"]


# 8. The runner checks its Colab options together.

def test_the_runner_refuses_colab_options_that_do_not_go_together(run):
    base = {"colab": True, "batch": True, "label": "colab-x", "collect": False, "colab_session": None,
            "colab_results": None}
    run.check_colab_options(**base)
    run.check_colab_options(**{**base, "collect": True, "colab_session": "01:17:24",
                               "colab_results": "someone/htlnlp-colab-official-colab-x/3"})
    run.check_colab_options(**{**base, "colab": False, "label": None})
    for kwargs, option in (({"batch": False}, "--batch"), ({"label": None}, "--label"),
                           ({"collect": True}, "--colab-session"),
                           ({"colab": False, "colab_session": "01:17:24"}, "--colab-session"),
                           ({"colab": False, "colab_results": "a/b"}, "--colab-results"),
                           ({"collect": False, "colab_session": "01:17:24"}, "--collect")):
        with pytest.raises(SystemExit, match=option):
            run.check_colab_options(**{**base, **kwargs})
    import inspect
    lines = [line.split("#")[0].strip() for line in inspect.getsource(run.main).splitlines()]   # and checks them first
    called = [n for n, line in enumerate(lines) if line.startswith("check_colab_options(a.colab, a.batch, a.label")]
    assert called and called[0] < next(n for n, line in enumerate(lines) if "KaggleApi()" in line)


def test_a_multi_task_colab_batch_refuses_a_deadline_below_180(run):
    """#888: the old 45-minute default cut multi-task Colab packs short; refuse below 180 unless opted in."""
    base = {"colab": True, "batch": True, "collect": False, "task_count": 2, "deadline_minutes": 45.0,
            "allow_short_deadline": False}
    with pytest.raises(SystemExit, match="below 180"):
        run.check_colab_deadline(**base)
    run.check_colab_deadline(**{**base, "deadline_minutes": 180.0})
    run.check_colab_deadline(**{**base, "allow_short_deadline": True})
    run.check_colab_deadline(**{**base, "task_count": 1})          # a single-task pack may stay short
    run.check_colab_deadline(**{**base, "colab": False})           # Kaggle kernels keep their own deadlines
    run.check_colab_deadline(**{**base, "collect": True})          # collect does not start a pack


# Smaller.

def test_a_kernel_that_stopped_itself_is_not_finished_and_the_rest_can_be_resumed(co, tmp_path):
    """Its 255-minute deadline, or two unanswered tasks, mark the rest skipped: the run goes on from there."""
    work = tmp_path / "working"
    (work / "tasks" / "a").mkdir(parents=True)
    (work / "tasks" / "a" / "result.json").write_text("{}")
    for why in ("the kernel's time budget ran out", "stopped: two tasks in a row had no answer from the model server"):
        (work / "result.json").write_text(json.dumps({"finished_ts": "t", "runs": {
            "a": {"instance_id": "a"}, "b": {"instance_id": "b", "is_skipped": True, "skip_reason_text": why}}}))
        assert co.earlier_output(tmp_path) == ("partial", 1), why


def test_a_colab_runs_settings_name_the_wheels_left_out(run):
    s = run.settings_for(RESULT, seed=7, drawn=["a"], pool_count=93, machine_shape=None, docker_image=None,
                         competition=None, agent_commit="abc", tasks_per_kernel=1, colab=True)
    note = next(n for n in s["notes"] if n.startswith("Run on a Colab machine"))
    assert "as on Kaggle" not in note and "wheels_left_out" in note


def test_the_notebook_claims_no_session_length_without_a_source():
    text = "".join("".join(c["source"]) for c in json.loads(NOTEBOOK.read_text())["cells"])
    assert "24 hours" not in text


# --- a development-set batch on Colab (028, #780): the competition's files fetched, not mounted --------------------

DEV_IDS = ["fastapi_2", "rich_7"]
DEV_TASKS = [{"instance_id": "fastapi_1", "repo": "fastapi/fastapi", "base_commit": "aaa"},
             {"instance_id": "fastapi_2", "repo": "fastapi/fastapi", "base_commit": "bbb"},
             {"instance_id": "rich_7", "repo": "Textualize/rich", "base_commit": "ccc"}]


def _competition(extra=()):
    """The competition's files as Kaggle lists them (names as the real listing gives them), each a few bytes."""
    files = {"HARNESS_README.md": b"the harness", "tasks.jsonl": "".join(json.dumps(t) + "\n" for t in DEV_TASKS).encode(),
             "sandbox/setup.py": b"setup", "wheels/pytest-8.3.4-py3-none-any.whl": b"w" * 9,
             "wheels/rich-15.0.0-py3-none-any.whl": b"r" * 7, "docker/Dockerfile": b"FROM x",
             "sample_submission/agent.yaml": b"name: x", **dict(extra)}
    for t in DEV_TASKS:
        stem = f"{t['repo'].split('/')[1]}_{t['base_commit']}"
        files[f"snapshots/{t['instance_id']}.tgz"] = t["instance_id"].encode() * 20
        files[f"graphs/{stem}.json"] = b"{}"
        files[f"embeddings/{stem}.npz"] = b"vectors"
    return files


class _FakeCompetition:
    """The Kaggle client's competition calls: files listed a page at a time, each downloaded on its own, some
    handed over zipped. It knows nothing of a token: none is needed to stand in for Kaggle."""
    def __init__(self, files, zipped=(), slug="gemma-4-developer-agent"):
        self.files, self.zipped, self.slug, self.downloaded, self.pages = dict(files), set(zipped), slug, [], 0

    def competition_list_files(self, competition, page_token=None, page_size=20):
        import types
        assert competition == self.slug
        self.pages += 1
        names = sorted(self.files)
        start = int(page_token or 0)
        nxt = str(start + 3) if start + 3 < len(names) else ""
        return types.SimpleNamespace(next_page_token=nxt, files=[
            types.SimpleNamespace(name=n, total_bytes=len(self.files[n])) for n in names[start:start + 3]])

    def competition_download_file(self, competition, file_name, path=None, quiet=True, **k):
        import zipfile
        from pathlib import Path
        assert competition == self.slug and quiet
        self.downloaded.append(file_name)
        where = Path(path) / file_name
        where.parent.mkdir(parents=True, exist_ok=True)
        if file_name in self.zipped:
            with zipfile.ZipFile(where.with_name(where.name + ".zip"), "w") as z:
                z.writestr(where.name, self.files[file_name])
        else:
            where.write_bytes(self.files[file_name])


def test_a_development_batch_takes_only_its_own_tasks_snapshots_graphs_and_embeddings(co):
    """The snapshots are 21.5 GB for all 129 tasks: a batch takes its own tasks' files, and what every task needs
    (the harness guide, tasks.jsonl, the tests' wheels and the sandbox's setup), never the docker files or the
    sample submission, which the kernel does not read."""
    listing = [(n, len(b)) for n, b in _competition().items()]
    picked = co.competition_files(listing, DEV_TASKS, DEV_IDS)
    assert [n for n, _ in picked] == sorted([
        "HARNESS_README.md", "tasks.jsonl", "sandbox/setup.py", "wheels/pytest-8.3.4-py3-none-any.whl",
        "wheels/rich-15.0.0-py3-none-any.whl", "snapshots/fastapi_2.tgz", "snapshots/rich_7.tgz",
        "graphs/fastapi_bbb.json", "graphs/rich_ccc.json", "embeddings/fastapi_bbb.npz", "embeddings/rich_ccc.npz"])
    by_id = co.competition_files(listing + [("graphs/rich_7.json", 2)], DEV_TASKS, DEV_IDS)
    assert "graphs/rich_7.json" in [n for n, _ in by_id]        # a graph named for the task, as the kernel also reads
    with pytest.raises(SystemExit, match="rich_9"):
        co.competition_files(listing, DEV_TASKS, ["rich_9"])     # not in tasks.jsonl
    no_snapshot = [(n, s) for n, s in listing if n != "snapshots/rich_7.tgz"]
    with pytest.raises(SystemExit, match="snapshots/rich_7.tgz"):
        co.competition_files(no_snapshot, DEV_TASKS, DEV_IDS)


def test_the_competitions_files_are_fetched_where_the_kernel_finds_them_and_logged(co, monkeypatch, tmp_path):
    """No competition is mounted on a Colab machine: its files are fetched with the notebook's Kaggle token and laid
    out as Kaggle mounts them, where the kernel's own search finds them, and the log says so, never the token."""
    monkeypatch.setenv("KAGGLE_API_TOKEN", "KGAT_sentinel_never_logged")
    said = []
    monkeypatch.setattr(co, "say", said.append)
    root = tmp_path / "htl_kaggle"
    api = _FakeCompetition(_competition(), zipped=["tasks.jsonl", "snapshots/rich_7.tgz"])
    comp = co.fetch_competition_files(api, "gemma-4-developer-agent", DEV_IDS, root)
    assert comp == root / "input" / "competitions" / "gemma-4-developer-agent"
    got = sorted(str(p.relative_to(comp)) for p in comp.rglob("*") if p.is_file())
    assert got == sorted(n for n, _ in co.competition_files(
        [(n, len(b)) for n, b in _competition().items()], DEV_TASKS, DEV_IDS))
    assert (comp / "snapshots" / "rich_7.tgz").read_bytes() == b"rich_7" * 20       # unzipped where its name says
    assert not list(comp.rglob("*.zip"))
    assert api.pages == len(_competition()) // 3 + 1                                # every page of the listing read
    assert _kernel("find_competition")["find_competition"](root / "input") == comp  # the kernel's own search
    log = "\n".join(said)
    assert "gemma-4-developer-agent" in log and "2 tasks" in log and "11 files" in log
    assert "KGAT_sentinel_never_logged" not in log
    api.downloaded.clear()
    co.fetch_competition_files(api, "gemma-4-developer-agent", DEV_IDS, root)
    assert api.downloaded == []                                  # complete at the listed sizes: nothing fetched again


def test_another_batchs_tasks_do_not_stay_beside_this_ones(co, monkeypatch, tmp_path):
    """A second batch on the same machine must not leave the first one's snapshots within the agent's reach, and a
    file cut short is fetched again."""
    monkeypatch.setattr(co, "say", lambda message: None)
    root = tmp_path / "htl_kaggle"
    api = _FakeCompetition(_competition())
    comp = co.fetch_competition_files(api, "gemma-4-developer-agent", ["fastapi_1"], root)
    (comp / "tasks.jsonl").write_bytes(b"cut")
    api.downloaded.clear()
    co.fetch_competition_files(api, "gemma-4-developer-agent", DEV_IDS, root)
    assert "tasks.jsonl" in api.downloaded and "snapshots/fastapi_1.tgz" not in api.downloaded
    assert not (comp / "snapshots" / "fastapi_1.tgz").exists() and not (comp / "graphs" / "fastapi_aaa.json").exists()
    assert (comp / "snapshots" / "fastapi_2.tgz").exists() and (comp / "snapshots" / "rich_7.tgz").exists()


def test_the_fetch_step_reads_no_credential_itself(co):
    """The notebook hands the token to the Kaggle client through the environment; the fetch step never reads it."""
    import inspect
    for fn in (co.fetch_competition_files, co.competition_files, co.listed_competition_files):
        src = inspect.getsource(fn)
        assert "environ" not in src and "TOKEN" not in src


def test_a_development_batchs_bundle_has_the_competition_fetched_beside_it(co, monkeypatch, tmp_path):
    """`fetch` reads the bundle's order: a development batch (`"source": "competition"`) has the competition's
    files for its tasks fetched; a batch of the published tasks does not."""
    _on_machine(co, monkeypatch, tmp_path)
    monkeypatch.setattr(co, "WHEELHOUSE", "metric/wheels")

    class Both(_FakeKaggle, _FakeCompetition):
        def __init__(self, datasets, files):
            _FakeKaggle.__init__(self, datasets)
            _FakeCompetition.__init__(self, files, slug="gemma-4-developer-agent")

    order = {"instance_ids": DEV_IDS, "source": "competition", "competition": "gemma-4-developer-agent"}
    datasets = {"metric/wheels": {"w-1.0-py3-none-any.whl": b"w"},
                "someone/htlnlp-official-devset-x": {"official_batch.json": json.dumps(order).encode(),
                                                     "submission/agent.yaml": b"name: a"},
                "someone/htlnlp-official-x": {"official_batch.json": b'{"instance_ids": ["htlnlp_1"]}'},
                "someone/kernel-x": {"official_agent_kernel.py": b"print(1)"}}
    root = tmp_path / "content" / "htl_kaggle"
    api = Both(datasets, _competition())
    co.fetch(api, None, "someone/htlnlp-official-devset-x", "someone/kernel-x", None, root=root, with_model=False)
    comp = root / "input" / "competitions" / "gemma-4-developer-agent"
    assert sorted(p.name for p in (comp / "snapshots").iterdir()) == ["fastapi_2.tgz", "rich_7.tgz"]
    api = Both(datasets, _competition())
    co.fetch(api, None, "someone/htlnlp-official-x", "someone/kernel-x", None, root=root, with_model=False)
    assert api.downloaded == []                                  # a published batch: no competition file


# --- the runner's side of a development-set batch on Colab (#780) --------------------------------------------------

def _dev_args(tmp_path, collect=False):
    import subprocess
    import types
    sub = tmp_path / "sub"
    sub.mkdir(exist_ok=True)
    (sub / "agent.yaml").write_text("name: a\n")
    # 028 BUG10 (#808): push records HEAD; collect needs a git agent checkout (or --agent-commit)
    if not (sub / ".git").exists():
        subprocess.run(["git", "init", "-q", "-b", "main"], cwd=sub, check=True)
        subprocess.run(["git", "add", "-A"], cwd=sub, check=True)
        subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@e", "commit", "-q", "-m", "a"],
                       cwd=sub, check=True)
    work = tmp_path / "work" / "devset-colab-x"
    if collect:
        work.mkdir(parents=True, exist_ok=True)
        sha = subprocess.run(["git", "-C", str(sub), "rev-parse", "HEAD"], capture_output=True, text=True,
                             check=True).stdout.strip()
        (work / "agent_commit_sha.txt").write_text(sha + "\n", encoding="utf-8")
    return types.SimpleNamespace(
        seed=7, source="competition", label="colab-x", collect=collect, colab=True, colab_results=None,
        colab_session="01:02:03" if collect else None, reuse_output=False, order_of_ids=None, work=tmp_path / "work",
        dataset=tmp_path / "dataset", agent_dir=sub, deadline_minutes=600.0, telemetry=False, outside_sample=False,
        no_table=False, sample=2, machine_shape="NvidiaL4", docker_image="img", competition="gemma-4-developer-agent",
        note=[], context_note=None, sample_method=None, kernel_minutes=45, agent_commit=None)


class _NoKernel:
    """A Kaggle client on which pushing a kernel fails the test: a Colab batch pushes none."""
    def kernels_push(self, *a, **k):
        raise AssertionError("a Colab batch pushes no Kaggle kernel")

    def kernels_status(self, *a, **k):
        raise AssertionError("a Colab batch waits for no Kaggle kernel")


def test_a_development_batch_for_colab_uploads_the_order_and_the_kernel_file_and_pushes_no_kernel(run, monkeypatch,
                                                                                                tmp_path, capsys):
    import pandas as pd
    sent = {}

    def upload(api, folder, ref):
        from pathlib import Path
        sent[ref] = {str(p.relative_to(folder)): p.read_text() for p in Path(folder).rglob("*") if p.is_file()}
    monkeypatch.setattr(run, "_upload_bundle", upload)
    run.check_colab_options(True, True, "colab-x", False, None, None)       # --colab is accepted for this batch
    run.check_arm_options("colab-x", None, True, True)
    a = _dev_args(tmp_path)
    assert run.run_batch(a, _NoKernel(), "someone", DEV_IDS, {}, {}, {}, pd) == 0
    order = json.loads(sent["someone/htlnlp-official-devset-colab-x"]["official_batch.json"])
    assert order["source"] == "competition" and order["competition"] == "gemma-4-developer-agent"
    assert sorted(order["instance_ids"]) == sorted(DEV_IDS)
    assert not any(k.startswith(("sealed/", "snapshots/")) for k in sent["someone/htlnlp-official-devset-colab-x"])
    kernel = sent["someone/htlnlp-colab-kernel-devset-colab-x"]["official_agent_kernel.py"]
    assert 'SEAL_KEY = ""' not in kernel                                     # the keyed copy, in its private dataset
    assert not (a.work / "devset-colab-x" / "kernel").exists()              # and not left on this machine
    entry = json.loads(capsys.readouterr().out.split("kaggle/colab_official_run.json:\n", 1)[1].splitlines()[0])
    assert entry == {"label": "devset-colab-x", "bundle": "someone/htlnlp-official-devset-colab-x",
                     "kernel_dataset": "someone/htlnlp-colab-kernel-devset-colab-x"}


def test_a_development_batch_collected_from_colab_writes_its_own_devset_table(run, monkeypatch, tmp_path):
    import pandas as pd
    monkeypatch.setattr(run, "OUT_DIR", tmp_path / "tables")
    monkeypatch.setattr(run, "REPO_ROOT", tmp_path)                       # the table's path is printed from here
    runs = {i: {"instance_id": i, "patch": "diff", "tool_call_count": 3, "llm_call_count": 2,
                "budgets": RESULT["budgets"], "generation_defaults": RESULT["generation_defaults"],
                "verification": {"is_resolved": i == "rich_7", "test_exit_code": 0 if i == "rich_7" else 1}}
            for i in DEV_IDS}
    result = {**{k: v for k, v in RESULT.items() if k not in ("budgets", "generation_defaults")},
              "finished_ts": "2026-11-16T03:00:00Z", "runs": runs}

    class Uploaded(_NoKernel):
        def dataset_download_files(self, ref, path=None, unzip=True, quiet=True):
            from pathlib import Path
            assert ref == "someone/htlnlp-colab-official-devset-colab-x"
            (Path(path) / "working").mkdir(parents=True)
            (Path(path) / "working" / "result.json").write_text(json.dumps(result))
            (Path(path) / "colab.log").write_text("[01:02:03Z] run devset-colab-x\n")

    a = _dev_args(tmp_path, collect=True)
    assert run.run_batch(a, Uploaded(), "someone", DEV_IDS, {}, {i: "x" for i in DEV_IDS}, {}, pd) == 0
    table = tmp_path / "tables" / "gemma-4-e4b-it-qat-w4a16-ct_swegemma_devset-colab-x.csv"
    rows = pd.read_csv(table)
    assert sorted(rows.instance_id) == sorted(DEV_IDS) and rows.is_resolved.sum() == 1
    assert rows.kaggle_kernel_url.str.contains("htlnlp-colab-official-devset-colab-x").all()
    settings = json.loads(table.with_name(table.stem + "_settings.json").read_text())
    assert settings["kernel"]["machine_shape_asked"] == "Colab, one GPU"
    assert settings["kernel"]["competition_attached"] == "gemma-4-developer-agent"
    assert any("fetched onto the Colab machine" in n for n in settings["notes"])
    assert not any("The kernel attached the competition" in n for n in settings["notes"])


def test_after_a_403_the_username_falls_back_to_the_environment_and_every_doubt_says_why(co, monkeypatch, tmp_path):
    """#815 on Modal: the 403 check stopped with no reason given. The token's username falls back to KAGGLE_USERNAME
    (trimmed) when the client's config has none, and each undecided answer logs why, with lengths only."""
    _on_machine(co, monkeypatch, tmp_path)
    lines = []
    monkeypatch.setattr(co, "say", lines.append)
    ref = "someone/htlnlp-colab-official-colab-graph"
    no_config = _FakeKaggle(status_error=_HttpError(403))
    no_config.username = None
    monkeypatch.setenv("KAGGLE_USERNAME", " someone\n")
    assert co.dataset_exists(no_config, ref, sleep=lambda s: None) is False      # read from the environment
    monkeypatch.delenv("KAGGLE_USERNAME")
    other = _FakeKaggle(status_error=_HttpError(403))
    other.username = "someone-else"
    assert co.listed_as_own(other, ref) is None
    broken = _FakeKaggle(status_error=_HttpError(403))
    broken.list_error = ConnectionError("the network blinked")
    assert co.listed_as_own(broken, ref) is None
    said = "\n".join(lines)
    assert "after a 403: the token's username (12 characters) is not the dataset owner's (7 characters)" in said
    assert "after a 403: listing the owner's datasets failed (ConnectionError" in said
    assert "someone-else" not in said


def test_huggingface_hub_is_pinned_below_2_for_the_pinned_transformers(co):
    """#819 on Modal: an unpinned huggingface-hub resolved to 2.4.0, and transformers 5.13.1 (vLLM 0.19.1's) refused
    to import ("huggingface-hub>=1.5.0,<2.0 is required"), so vLLM never started. Pinned beside the rest."""
    assert "huggingface-hub>=1.5.0,<2.0" in co.PINS


def test_the_notebook_runs_without_a_kaggle_username_secret(monkeypatch):
    """#827: Colab stopped on a missing KAGGLE_USERNAME secret (a notebook opened from a new branch path is a new
    notebook to Colab's Secrets). The username is no secret, so it falls back to jcblearning; a missing token still
    stops, saying how to add it."""
    import os
    import sys
    import types
    nb = json.loads(NOTEBOOK.read_text())
    cell = "".join(next(c for c in nb["cells"] if c["cell_type"] == "code")["source"])
    head = cell.split("REPO =", 1)[0]   # the secrets part, before anything is fetched

    class SecretNotFoundError(Exception):
        pass

    secrets = {"KAGGLE_API_TOKEN": "x"}

    def get(name):
        if name not in secrets:
            raise SecretNotFoundError(name)
        return secrets[name]

    colab = types.ModuleType("google.colab")
    colab.userdata = types.SimpleNamespace(get=get)
    google = types.ModuleType("google")
    google.colab = colab
    monkeypatch.setitem(sys.modules, "google", google)
    monkeypatch.setitem(sys.modules, "google.colab", colab)
    monkeypatch.delenv("KAGGLE_USERNAME", raising=False)
    monkeypatch.delenv("KAGGLE_API_TOKEN", raising=False)
    exec(head, {})
    assert os.environ["KAGGLE_USERNAME"] == "jcblearning"
    secrets.clear()
    with pytest.raises(SystemExit, match="KAGGLE_API_TOKEN"):
        exec(head, {})
