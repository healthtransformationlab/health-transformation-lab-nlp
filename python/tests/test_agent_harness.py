"""Spec 035 US1 (#543): a local runner for the competition's documented harness (HARNESS_README sections 5-8),
proven with scripted models. Every test builds a tiny git repo: a package with a bug, a test that catches it, and
the fix. The runner is ours, not the competition's evaluator; results are labelled so."""
import json
import subprocess
from pathlib import Path

import pytest

from health_transformation_lab_nlp import agent_harness as ah

BUGGY = "def add(a, b):\n    return a - b\n"
FIXED = "def add(a, b):\n    return a + b\n"
TEST = "from pkg.calc import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout


def write(repo: Path, rel: str, text: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)


def commit_all(repo: Path, msg: str) -> str:
    git(repo, "add", "-A")
    git(repo, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-q", "-m", msg)
    return git(repo, "rev-parse", "HEAD").strip()


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    write(r, "python/pkg/__init__.py", "")
    write(r, "python/pkg/calc.py", BUGGY)
    write(r, "python/pkg/util.py", "def helper(x):\n    return x\n")
    write(r, "python/pyproject.toml", "[project]\nname = 'pkg'\n")
    return r


@pytest.fixture
def task(repo):
    base = commit_all(repo, "base")
    write(repo, "python/pkg/calc.py", FIXED)
    write(repo, "python/tests/test_calc.py", TEST)
    commit_all(repo, "fix")
    patch = git(repo, "diff", base, "HEAD", "--", "python/pkg/calc.py")
    test_patch = git(repo, "diff", base, "HEAD", "--", "python/tests/")
    git(repo, "checkout", "-q", base)
    return {"instance_id": "t_1", "repo": "owner/pkg", "base_commit": base, "patch": patch, "test_patch": test_patch,
            "problem_statement": "add() subtracts", "hints_text": "", "created_at": "2026-11-01T00:00:00Z"}


@pytest.fixture
def session(repo, task, tmp_path):
    ws = ah.prepare_workspace(task, repo, tmp_path / "ws")
    return ah.Session(ws, ah.Budget(tool_calls=40, time_minutes=5, turns=60, command_timeout=30))


def call(session, name, **kw):
    return json.loads(ah.call_tool(session, name, kw))


# --- the workspace ---------------------------------------------------------------------------------------------

def test_the_workspace_is_the_base_commit_with_a_baseline_tag_and_no_later_history(session, task):
    ws = session.workdir
    assert (ws / "python/pkg/calc.py").read_text() == BUGGY
    assert git(ws, "rev-parse", "_swegemma_baseline").strip()
    assert git(ws, "rev-list", "--count", "HEAD").strip() == "1"            # no history comes along
    assert "__pycache__/" in (ws / ".git" / "info" / "exclude").read_text()


# --- the tools (HARNESS_README section 6) --------------------------------------------------------------------

def test_run_command_ok_and_error_shapes(session):
    ok = call(session, "run_command", command="echo hi")
    assert ok == {"status": "ok", "stdout": "hi\n", "stderr": "", "exit_code": 0}
    bad = call(session, "run_command", command="exit 3")
    assert bad["status"] == "error" and bad["error_type"] == "CommandError" and bad["details"]["exit_code"] == 3


def test_run_command_output_is_truncated_to_5000_characters(session):
    out = call(session, "run_command", command="python3 -c \"print('x' * 9000)\"")
    assert len(out["stdout"]) == 5000


def test_run_command_times_out_without_ending_the_session(session):
    session.budget.command_timeout = 1
    out = call(session, "run_command", command="sleep 5")
    assert out["error_type"] == "TimeoutExceeded" and not session.done


def test_read_file_slices_lines_and_caps_at_150(session):
    write(session.workdir, "big.py", "".join(f"line {i}\n" for i in range(1, 401)))
    r = call(session, "read_file", filepath="/workspace/big.py")
    assert (r["start_line"], r["end_line"], r["total_lines"], r["is_truncated"]) == (1, 150, 400, True)
    r = call(session, "read_file", filepath="big.py", start_line="10", end_line="12")   # strings are coerced
    assert r["content"] == "line 10\nline 11\nline 12\n" and not r["is_truncated"]


def test_paths_with_dot_dot_are_refused(session):
    r = call(session, "read_file", filepath="../outside.py")
    assert r["status"] == "error" and r["error_type"] == "ValidationError"


def test_edit_file_exact_then_flexible_and_unique(session):
    r = call(session, "edit_file", filepath="python/pkg/calc.py", old_string="a - b", new_string="a + b")
    assert r["strategy"] == "exact" and r["occurrences"] == 1 and "+    return a + b" in r["diff"]
    write(session.workdir, "f.py", "def f():\n    if x:\n        y = 1\n")
    r = call(session, "edit_file", filepath="f.py", old_string="if x:\n    y = 1", new_string="if x:\n    y = 2")
    assert r["strategy"] == "flexible" and (session.workdir / "f.py").read_text() == "def f():\n    if x:\n        y = 2\n"
    write(session.workdir, "g.py", "a = 1\na = 1\n")
    r = call(session, "edit_file", filepath="g.py", old_string="a = 1", new_string="a = 2")
    assert r["error_type"] == "FileEditError"
    r = call(session, "edit_file", filepath="g.py", old_string="a = 1", new_string="a = 2", allow_multiple="true")
    assert r["occurrences"] == 2


def test_edit_file_regex_tier_matches_across_spacing(session):
    write(session.workdir, "h.py", "x = foo( a,b )\n")
    r = call(session, "edit_file", filepath="h.py", old_string="x = foo(a, b)", new_string="x = foo(a, c)")
    assert r["strategy"] == "regex" and (session.workdir / "h.py").read_text() == "x = foo(a, c)\n"


def test_write_file_creates_parents(session):
    r = call(session, "write_file", filepath="new/dir/x.txt", content="hello")
    assert r == {"status": "ok", "filepath": "new/dir/x.txt", "size": 5}


def test_budget_counts_gated_tools_warns_and_stops(session):
    session.budget.tool_calls = 20
    for _ in range(9):
        call(session, "run_command", command="true")
    assert "budget_warning" not in call(session, "get_status")            # free; 11 remaining
    r = call(session, "run_command", command="true")
    assert "budget_warning" in r                                         # 10 remaining: every response warns
    assert "budget_warning" in call(session, "get_status")
    for _ in range(10):
        call(session, "run_command", command="true")
    r = call(session, "run_command", command="true")
    assert r["error_type"] == "BudgetExceeded"
    assert call(session, "submit_patch")["status"] == "ok"               # free, even with the budget spent


def test_submit_patch_takes_new_files_and_strips_protected_ones(session):
    call(session, "edit_file", filepath="python/pkg/calc.py", old_string="a - b", new_string="a + b")
    call(session, "write_file", filepath="python/pkg/new.py", content="X = 1\n")
    call(session, "write_file", filepath="python/tests/test_mine.py", content="def test(): pass\n")
    r = call(session, "submit_patch")
    assert r["status"] == "ok" and r["files_changed"] == 2
    assert "python/pkg/new.py" in session.submitted_patch and "test_mine" not in session.submitted_patch
    assert session.patch_submitted


def test_unknown_tool_is_an_error_not_a_crash(session):
    r = call(session, "rm_rf", path="/")
    assert r["status"] == "error" and r["error_type"] == "UnknownTool"


# --- the graph tools ---------------------------------------------------------------------------------------------

GRAPH = {"directed": True, "multigraph": True, "graph": {},
         "nodes": [{"id": "pkg.calc.add", "name": "pkg.calc.add", "text": "def add(a, b): ..."},
                   {"id": "pkg.util.helper", "name": "pkg.util.helper", "text": "def helper(x): ..."},
                   {"id": "pkg.calc.sub", "name": "pkg.calc.sub", "text": "def sub(a, b): ..."}],
         "edges": [{"source": "pkg.calc.add", "target": "pkg.util.helper", "type": "calls", "key": 0}]}


@pytest.fixture
def graph_session(session):
    import numpy as np
    session.graph = ah.CodeGraph(GRAPH, {"pkg.calc.add": np.array([1.0, 0.0]),
                                         "pkg.calc.sub": np.array([0.9, 0.1]),
                                         "pkg.util.helper": np.array([0.0, 1.0])})
    return session


def test_code_neighbors_resolve_short_names(graph_session):
    r = call(graph_session, "get_code_neighbors", node="calc.add")
    assert r["node"] == "pkg.calc.add" and r["neighbors"] == ["pkg.util.helper"] and r["count"] == 1


def test_similar_code_ranks_by_cosine(graph_session):
    r = call(graph_session, "search_similar_code", query="add", k="2")
    assert [x["node_name"] for x in r["results"]] == ["pkg.calc.sub", "pkg.util.helper"]


def test_code_subgraph_keeps_the_edges_between_the_nodes(graph_session):
    r = call(graph_session, "get_code_subgraph", nodes='["pkg.calc.add", "pkg.util.helper"]')
    assert r["edges"] == [{"from": "pkg.calc.add", "to": "pkg.util.helper", "type": "calls"}] and r["node_count"] == 2


def test_graph_tools_without_a_graph_say_so(session):
    assert call(session, "get_code_neighbors", node="x")["error_type"] == "NoGraph"


# --- the prompt (HARNESS_README section 5.2) --------------------------------------------------------------------

def test_the_initial_prompt_has_the_documented_sections(session, task):
    text = ah.build_agent_prompt(task, session, ["run_command", "read_file", "submit_patch"])
    assert text.startswith(f"You are evaluating a software engineering task for repository {task['repo']}.")
    assert "Problem Statement:\nadd() subtracts" in text and "## Hints:" not in text
    assert "## Task Budget" in text and "Tool calls allowance: 40 calls" in text
    assert "File view limit: 150 lines per read_file call" in text
    assert "## Code Intelligence Tools" not in text                      # no graph, no graph tools declared
    assert "## Workspace Layout" in text and "python" in text


def test_the_instruction_fills_the_documented_variables():
    assert ah.fill_instruction("Issue: {problem_description}\nHints: {hints}", {"problem_statement": "P",
                                                                                 "hints_text": "  H "}) == \
        "Issue: P\nHints: H"


# --- the loop, patch extraction and verification (sections 5.3, 8) ------------------------------------------------

def test_the_oracle_resolves_and_null_does_not(repo, task, tmp_path):
    good = ah.run_task(task, repo, ah.OracleModel(), ah.Budget(), tmp_path / "a")
    assert good["is_resolved"] is True and good["is_patch_submitted"] and good["reason_text"] == ""
    bad = ah.run_task(task, repo, ah.NullModel(), ah.Budget(), tmp_path / "b")
    assert bad["is_resolved"] is False and bad["agent_patch_bytes"] == 0 and bad["reason_text"] == "empty patch"


def test_a_patch_left_unsubmitted_is_still_taken(repo, task, tmp_path):
    class EditsButNeverSubmits:
        def step(self, messages, tools):
            if any(m.get("role") == "tool" for m in messages):
                return {"content": "done", "tool_calls": [], "finish_reason": "stop"}
            return {"content": "", "finish_reason": "tool_calls", "tool_calls": [
                {"id": "1", "name": "edit_file", "arguments": {"filepath": "python/pkg/calc.py",
                                                                "old_string": "a - b", "new_string": "a + b"}}]}
    row = ah.run_task(task, repo, EditsButNeverSubmits(), ah.Budget(), tmp_path / "c")
    assert row["is_resolved"] is True and row["is_patch_submitted"] is False


def test_three_text_only_turns_in_a_row_end_the_session(repo, task, tmp_path):
    class Chatty:
        calls = 0

        def step(self, messages, tools):
            Chatty.calls += 1
            return {"content": "thinking...", "tool_calls": [], "finish_reason": "stop"}
    row = ah.run_task(task, repo, Chatty(), ah.Budget(), tmp_path / "d")
    assert Chatty.calls == 4 and row["nudge_count"] == 3                  # the fourth text-only turn ends it


def test_a_test_file_edit_is_reset_before_verification(repo, task, tmp_path):
    class CheatsInTests:
        def step(self, messages, tools):
            if any(m.get("role") == "tool" for m in messages):
                return {"content": "", "finish_reason": "tool_calls",
                        "tool_calls": [{"id": "2", "name": "submit_patch", "arguments": {}}]}
            return {"content": "", "finish_reason": "tool_calls", "tool_calls": [
                {"id": "1", "name": "write_file", "arguments": {"filepath": "python/tests/test_calc.py",
                                                                 "content": "def test_add():\n    assert True\n"}}]}
    row = ah.run_task(task, repo, CheatsInTests(), ah.Budget(), tmp_path / "e")
    assert row["is_resolved"] is False                                   # the stripped test edit gains nothing


def test_the_run_row_is_labelled_as_our_harness(repo, task, tmp_path):
    row = ah.run_task(task, repo, ah.NullModel(), ah.Budget(), tmp_path / "f")
    assert row["harness_name"] == ah.HARNESS_NAME and "not the competition" in ah.HARNESS_NOTE
    assert set(ah.RUN_COLUMNS) == set(row)


def test_the_oracle_applies_a_patch_bigger_than_one_shell_argument(repo, tmp_path):
    """Linux caps one execve argument at 128 KB; a big reference patch can't go inside a bash -c string."""
    base = commit_all(repo, "base")
    write(repo, "python/pkg/calc.py", FIXED + "".join(f"# filler line {i:06d}\n" for i in range(9000)))
    write(repo, "python/tests/test_calc.py", TEST)
    commit_all(repo, "fix")
    patch = git(repo, "diff", base, "HEAD", "--", "python/pkg/calc.py")
    assert len(patch) > 140_000
    task = {"instance_id": "t_big", "repo": "owner/pkg", "base_commit": base, "patch": patch,
            "test_patch": git(repo, "diff", base, "HEAD", "--", "python/tests/"), "problem_statement": "p",
            "hints_text": "", "created_at": ""}
    row = ah.run_task(task, repo, ah.OracleModel(), ah.Budget(), tmp_path / "big")
    assert row["is_resolved"] is True and "_oracle" not in (row["reason_text"] or "")
