"""#812: per-task counts of the edit-fallback scripts' use, read from a run's traces (kaggle/skill_use_counts.py)."""
import importlib.util
import json

from health_transformation_lab_nlp.paths import REPO_ROOT

_spec = importlib.util.spec_from_file_location("skill_use_counts", REPO_ROOT / "kaggle" / "skill_use_counts.py")
suc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(suc)


def _task(tmp_path, calls, seconds=12.5):
    d = tmp_path / "working" / "tasks" / "t1"
    (d / "results" / "traces").mkdir(parents=True)
    steps = [{"step_id": 1, "source": "system", "message": "prompt"}]
    for i, (name, args, out) in enumerate(calls, start=2):
        steps.append({"step_id": i, "source": "agent", "tool_calls": [{"function_name": name, "arguments": args}],
                      "observation": {"content": out}})
    (d / "results" / "traces" / "trace_t1.json").write_text(json.dumps({"steps": steps}))
    (d / "result.json").write_text(json.dumps({"agent_phase_seconds": seconds}))
    return d


def test_each_use_of_the_scripts_is_counted(tmp_path):
    d = _task(tmp_path, [
        ("run_skill_script", {"skill_name": "edit-fallback", "file_path": "scripts/install.py"}, "installed"),
        ("run_command", {"command": "python3 /tmp/h/find.py total"}, "pkg/cart.py\n  12: def total"),
        ("read_file", {"filepath": "pkg/cart.py"}, "..."),
        ("edit_file", {"filepath": "pkg/cart.py"}, "Failed to replace: old_string not found."),
        ("run_command", {"command": "python3 /tmp/h/edit.py pkg/cart.py <<'EOF'"}, "NOTHING WRITTEN: closest lines"),
        ("run_command", {"command": "python3 /tmp/h/edit.py pkg/cart.py <<'EOF'"}, "REPLACE is already in the file"),
        ("edit_file", {"filepath": "pkg/cart.py"}, "Target string occurs 2 times in pkg/cart.py."),
    ])
    r = suc.count_task(d)
    assert (r["install_call_count"], r["install_with_args_count"]) == (1, 0)
    assert (r["find_call_count"], r["find_then_listed_read_count"]) == (1, 1)
    assert (r["edit_script_call_count"], r["edit_nothing_written_count"], r["edit_already_done_count"]) == (2, 1, 1)
    assert (r["edit_file_not_found_count"], r["edit_file_ambiguous_count"]) == (1, 1)
    assert (r["tool_call_count"], r["task_seconds"]) == (7, 12.5)


def test_a_call_with_arguments_and_an_edit_py_that_was_never_installed(tmp_path):
    d = _task(tmp_path, [
        ("run_skill_script", {"skill_name": "edit-fallback", "file_path": "scripts/install.py", "args": ["x"]}, "ok"),
        ("run_command", {"command": "python3 /tmp/h/edit.py a.py <<'EOF'"},
         "python3: can't open file '/tmp/h/edit.py': [Errno 2] No such file or directory"),
    ])
    r = suc.count_task(d)
    assert r["install_with_args_count"] == 1
    assert r["edit_script_call_count"] == 1 and r["edit_applied_count"] == 0, "a missing edit.py applied nothing"
    assert list(r) == suc.COLUMNS
