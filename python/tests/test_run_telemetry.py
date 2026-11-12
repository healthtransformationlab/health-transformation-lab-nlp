"""036 US2 (#569) and 028 AI4 (#668): what a kernel's spans and GPU samples say about each task. Time is rolled up
by code section as self time, so each second is counted once; tokens come from the model calls; each task carries
its GPU-hours, its energy and an estimated cost at a declared price. Counts and names only, never a prompt or reply."""
import importlib.util

import pytest

from health_transformation_lab_nlp.paths import REPO_ROOT


@pytest.fixture(scope="module")
def rt():
    spec = importlib.util.spec_from_file_location("run_telemetry", REPO_ROOT / "python" / "scripts" / "71_run_telemetry.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _span(name, sid, parent, start, end, **attributes):
    return {"name": name, "context": {"trace_id": "0xt", "span_id": sid}, "parent_id": parent,
            "start_time": f"2026-11-11T13:00:{start:06.3f}Z", "end_time": f"2026-11-11T13:00:{end:06.3f}Z",
            "attributes": attributes}


SPANS = [
    _span("official_agent_kernel.task", "t", None, 0, 30, instance_id="task_1"),
    _span("invocation", "i", "t", 2, 28),
    _span("call_llm", "l1", "i", 2, 12),
    _span("generate_content openai//kaggle/input/models/x", "g1", "l1", 3, 11,
          **{"gen_ai.usage.input_tokens": 900, "gen_ai.usage.output_tokens": 100}),
    _span("execute_tool read_file", "r1", "i", 12, 13, **{"gen_ai.tool.name": "read_file"}),
    _span("execute_tool code_analyzer", "a1", "i", 13, 23, **{"gen_ai.tool.name": "code_analyzer"}),
    _span("invoke_agent code_analyzer", "a2", "a1", 13, 23),
    _span("call_llm", "l2", "a2", 14, 22),
    _span("generate_content openai//kaggle/input/models/x", "g2", "l2", 14, 22,
          **{"gen_ai.usage.input_tokens": 500, "gen_ai.usage.output_tokens": 50}),
    _span("compact_events token_threshold", "c1", "i", 23, 24),
]


def test_a_span_is_named_for_its_code_section(rt):
    assert rt.section_of("generate_content openai//kaggle/input/models/x") == "model call"
    assert rt.section_of("call_llm") == "model call"
    assert rt.section_of("execute_tool read_file") == "tool read_file"
    assert rt.section_of("invoke_agent code_analyzer") == "agent code_analyzer"
    assert rt.section_of("compact_events token_threshold") == "context compaction"
    assert rt.section_of("official_agent_kernel.task") == "harness"
    assert rt.section_of("invocation") == "agent loop"
    assert rt.section_of("something new") == "other"


def test_time_is_rolled_up_as_self_time_so_each_second_is_counted_once(rt):
    rows = {r["section_name"]: r for r in rt.task_sections(SPANS)}
    assert {r["instance_id"] for r in rows.values()} == {"task_1"}
    assert rows["model call"]["self_seconds"] == pytest.approx(18.0)        # 10 + 8, the sub-agent's call included
    assert rows["model call"]["span_count"] == 2                           # calls, not their two spans each
    assert (rows["model call"]["input_token_count"], rows["model call"]["output_token_count"]) == (1400, 150)
    assert rows["tool read_file"]["self_seconds"] == pytest.approx(1.0)
    assert rows["tool code_analyzer"]["self_seconds"] == pytest.approx(0.0)   # all of it is its children's
    assert rows["agent code_analyzer"]["self_seconds"] == pytest.approx(2.0)  # 10 - the 8 of its model call
    assert rows["harness"]["self_seconds"] == pytest.approx(4.0)              # 30 - the 26 of the agent loop
    assert sum(r["self_seconds"] for r in rows.values()) == pytest.approx(30.0)   # the task's whole time, once
    assert all(not isinstance(v, str) or k in ("instance_id", "section_name") for r in rows.values() for k, v in r.items())


def test_the_rollup_gives_each_sections_share_of_all_tasks_time(rt):
    other = [dict(s, context={"trace_id": "0xu", "span_id": s["context"]["span_id"] + "u"},
                  parent_id=(s["parent_id"] + "u") if s["parent_id"] else None,
                  attributes={**s["attributes"], **({"instance_id": "task_2"} if s["name"].endswith(".task") else {})})
             for s in SPANS]
    roll = {r["section_name"]: r for r in rt.rollup(rt.task_sections(SPANS + other))}
    assert roll["model call"]["task_count"] == 2 and roll["model call"]["span_count"] == 4
    assert roll["model call"]["self_seconds"] == pytest.approx(36.0)
    assert roll["model call"]["time_share_pct"] == pytest.approx(60.0)
    assert sum(r["time_share_pct"] for r in roll.values()) == pytest.approx(100.0, abs=0.05)   # rounded to 0.01


def test_each_task_carries_its_gpu_hours_energy_and_an_estimated_cost(rt):
    rows = rt.gpu_rows({"task_1": {"gpu_sample_count": 84, "avg_gpu_utilization_pct": 92.37,
                                   "max_gpu_memory_used_mb": 20559.0, "gpu_energy_wh": 7.05}},
                       {"task_1": 103.2}, gpu_count=4, usd_per_gpu_hour=0.5, price_basis_text="a declared price")
    assert rows == [{"instance_id": "task_1", "task_seconds": 103.2, "gpu_count": 4,
                     "gpu_hours": pytest.approx(0.1147, abs=1e-4), "avg_gpu_utilization_pct": 92.37,
                     "max_gpu_memory_used_mb": 20559.0, "gpu_energy_wh": 7.05,
                     "estimated_cost_usd": pytest.approx(0.0573, abs=1e-4), "price_basis_text": "a declared price"}]


def test_every_gpu_the_kernels_ran_on_has_a_declared_price(rt):
    """036 US2 (#569): the runs under the competition's evaluator used four L4s, and their GPU time is priced the
    way the T4 baseline's is: from a declared price with its source and the date it was read. Until November 11,
    2026 only the T4 had one, so `estimated_cost_usd` was empty for every L4 run."""
    for name in ("Tesla T4", "NVIDIA L4", "NVIDIA A100-SXM4-40GB"):   # the A100: the Colab pair of November 12 (#687)
        price, basis = rt.declared_price(name)
        assert price is not None and price > 0, f"no price declared for {name}"
        assert "getdeploying.com" in basis and "read 2026-" in basis and "Kaggle's GPUs are free" in basis


def test_a_colab_runs_estimate_does_not_say_its_gpu_was_free(rt):
    """The Colab pair (#687) ran on the owner's Colab subscription, which is paid for, in compute units and not by the
    GPU-hour. Its estimate is still what the same GPU time would rent for, and it says where the run was made."""
    colab = {"kernel": {"machine_shape_asked": "Colab, one GPU"}}
    kaggle = {"kernel": {"machine_shape_asked": "NvidiaL4x4"}}
    assert rt.where_text(kaggle) == "Kaggle's GPUs are free" and rt.where_text({}) == "Kaggle's GPUs are free"
    assert "Colab" in rt.where_text(colab) and "free" not in rt.where_text(colab)
    price, basis = rt.declared_price("NVIDIA A100-SXM4-40GB", rt.where_text(colab))
    assert price == pytest.approx(1.87) and "compute units" in basis and "Kaggle's GPUs are free" not in basis
    none, why = rt.declared_price("NVIDIA H100", rt.where_text(colab))
    assert none is None and "no price declared for NVIDIA H100" in why and "Kaggle" not in why


def test_a_gpu_with_no_declared_price_gets_no_estimate_and_says_why(rt):
    price, basis = rt.declared_price("NVIDIA A100")
    assert price is None and "no price declared for NVIDIA A100" in basis
