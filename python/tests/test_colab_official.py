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

    def restore(api, user, label, out):
        if isinstance(state, BaseException):
            raise state
        return state
    monkeypatch.setattr(co, "restore", restore)

    def fetch(*a, **k):
        calls["fetched"] += 1
        raise RuntimeError("the test stops here: nothing is downloaded")
    monkeypatch.setattr(co, "fetch", fetch)
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
    monkeypatch.setattr(co, "listed_gpu", lambda label: wanted)


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
    assert labels.index("colab-report") > labels.index("colab-graph-try2") and labels[-1] == "colab-report"
    assert report["gpu"] == "A100"
    assert report["bundle"].endswith("/htlnlp-official-colab-report")
    assert report["kernel_dataset"].endswith("/htlnlp-colab-kernel-colab-report")
    assert len({r["bundle"] for r in plan["runs"]}) == 3            # one sealed bundle per text given with the task


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
