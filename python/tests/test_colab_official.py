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


def test_the_notebook_reads_its_token_from_colab_secrets_and_holds_none():
    nb = json.loads(NOTEBOOK.read_text())
    src = "\n".join("".join(c["source"]) for c in nb["cells"])
    assert 'userdata.get("KAGGLE_API_TOKEN")' in src and 'userdata.get("KAGGLE_USERNAME")' in src
    assert "KGAT_" not in src and "SEAL_KEY" not in src
    assert all(not c.get("outputs") for c in nb["cells"] if c["cell_type"] == "code")
    assert "colab_official.py" in src and "healthtransformationlab/health-transformation-lab-nlp" in src
    assert nb["metadata"]["accelerator"] == "GPU"
