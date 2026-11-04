"""A local runner for the Gemma 4 Developer Agent competition's documented harness (spec 035 US1, #543).

The competition's evaluator, swegemma, isn't distributed (#449). Its guide (HARNESS_README.md, read from the
competition's files and not committed) documents what it does, and this follows it:

    prepare_workspace  the task's files at base_commit as one commit, tagged _swegemma_baseline, with the
                       documented .git/info/exclude patterns (section 4.2)
    Session, Budget    tool-call, time and turn budgets; the budget warning when 10 or fewer calls remain (6, 7.1)
    call_tool          the 9 tools with their documented arguments, JSON results and limits (section 6)
    build_agent_prompt the initial user message's sections (5.2); fill_instruction the {problem_description}
                       and {hints} variables (5.1)
    run_agent          the multi-turn loop: submit_patch ends it; a turn with no tool call is nudged, and more
                       than 3 in a row end the session (5.3)
    extract_patch      git add -N . and git diff --binary _swegemma_baseline, protected files stripped (8.1)
    verify             a fresh workspace, the agent's patch, the test patch, the target tests (8.2), with
                       task_gate's pytest and JUnit check
    run_task           all of it for one task; one row of RUN_COLUMNS

Models implement step(messages, tools) -> {"content", "tool_calls": [{"id", "name", "arguments"}],
"finish_reason"}. Two scripted ones bound the runner: OracleModel replays the reference patch (should resolve
every task), NullModel submits nothing (should resolve none).

THIS IS NOT THE COMPETITION'S EVALUATOR. Differences we know of: no Docker sandbox (a temporary folder and
subprocesses, like swegemma's subprocess backend), no ADK, no context compaction, no sub-agents or skills, and
PYTHONPATH=<workspace>/python instead of an editable install. Every row says which harness made it.
"""

from __future__ import annotations

import difflib
import io
import json
import os
import re
import signal
import subprocess
import tarfile
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from . import task_gate as tgate
from .telemetry import traced

HARNESS_NAME = "htlnlp-harness-v1"
HARNESS_NOTE = ("Measured with this repository's re-implementation of the competition's documented harness "
                "(spec 035), not the competition's evaluator.")
MAX_STDOUT = 5000
MAX_FILE_LINES = 150
MAX_FILE_CHARS = 10000
MAX_NUDGES = 3
EXCLUDE = ["__pycache__/", "*.pyc", ".pytest_cache/", "*.egg-info/", "build/", "dist/", ".coverage"]
ALL_TOOLS = ["run_command", "read_file", "edit_file", "write_file", "get_status", "submit_patch",
             "get_code_neighbors", "search_similar_code", "get_code_subgraph"]
GRAPH_TOOLS = {"get_code_neighbors", "search_similar_code", "get_code_subgraph"}
FREE_TOOLS = {"get_status", "submit_patch"}
RUN_COLUMNS = ["instance_id", "harness_name", "model_name", "is_resolved", "is_patch_submitted", "agent_patch_bytes",
               "files_changed_count", "tool_call_count", "turn_count", "nudge_count", "agent_seconds",
               "verify_exit_code", "verify_passed_count", "verify_failed_count", "verify_error_count", "reason_text"]
_AUTHOR = {"GIT_AUTHOR_NAME": "harness", "GIT_AUTHOR_EMAIL": "harness@localhost",
           "GIT_COMMITTER_NAME": "harness", "GIT_COMMITTER_EMAIL": "harness@localhost",
           "GIT_AUTHOR_DATE": "2026-01-01T00:00:00Z", "GIT_COMMITTER_DATE": "2026-01-01T00:00:00Z"}


def _git(cwd: Path, *args: str, stdin: str | None = None) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-c", "commit.gpgsign=false", *args], cwd=cwd, input=stdin, capture_output=True,
                          text=True, check=False, env={**os.environ, **_AUTHOR})


# --- the workspace ------------------------------------------------------------------------------------------------

@traced
def prepare_workspace(task: dict, source: Path, dest: Path) -> Path:
    """The task's files at base_commit in `dest`, as one commit on main tagged _swegemma_baseline. `source` is a
    snapshot .tgz (files and .git at the archive root) or a git repository holding base_commit."""
    source, dest = Path(source), Path(dest)
    dest.mkdir(parents=True, exist_ok=False)
    if source.is_file():
        with tarfile.open(source) as t:
            t.extractall(dest, filter="tar")
    else:
        tar = subprocess.run(["git", "archive", "--format=tar", task["base_commit"]], cwd=source,
                             capture_output=True, check=True).stdout
        with tarfile.open(fileobj=io.BytesIO(tar)) as t:
            t.extractall(dest, filter="tar")
        _git(dest, "init", "-q", "-b", "main")
        _git(dest, "add", "-A", "-f")
        _git(dest, "commit", "-q", "--no-verify", "-m", f"Snapshot of {task['base_commit']}")
    exclude = dest / ".git" / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    with open(exclude, "a") as f:
        f.write("\n" + "\n".join(EXCLUDE) + "\n")
    _git(dest, "tag", "-f", "_swegemma_baseline")
    return dest


# --- budgets and the session ---------------------------------------------------------------------------------------

@dataclass
class Budget:
    """The submission's eval_config.yaml `evaluation:` budgets (gemma-developer-agent's values by default)."""
    tool_calls: int = 40
    time_minutes: float = 5.0
    turns: int = 60
    command_timeout: int = 120

    @classmethod
    @traced
    def from_eval_config(cls, path: Path) -> Budget:
        import yaml
        e = (yaml.safe_load(Path(path).read_text()) or {}).get("evaluation", {})
        return cls(tool_calls=int(e.get("max_tool_calls", 40)), time_minutes=float(e.get("max_time_minutes", 5.0)),
                   turns=int(e.get("max_turns", 60)), command_timeout=int(e.get("timeout_seconds", 120)))


@dataclass
class Session:
    workdir: Path
    budget: Budget = field(default_factory=Budget)
    graph: CodeGraph | None = None
    tool_calls_used: int = 0
    patch_submitted: bool = False
    submitted_patch: str = ""
    done: bool = False
    started: float = field(default_factory=time.monotonic)

    @traced
    def remaining_seconds(self) -> float:
        return self.budget.time_minutes * 60 - (time.monotonic() - self.started)

    @traced
    def remaining_calls(self) -> int:
        return self.budget.tool_calls - self.tool_calls_used


def _ok(**kw) -> dict:
    return {"status": "ok", **kw}


def _err(kind: str, message: str, **details) -> dict:
    out = {"status": "error", "error_type": kind, "error_message": message}
    if details:
        out["details"] = details
    return out


class _ToolError(Exception):
    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind


def _path(session: Session, filepath) -> Path:
    p = str(filepath or "").strip()
    for prefix in ("/workspace/", "/"):
        p = p.removeprefix(prefix)
    if not p or ".." in Path(p).parts:
        raise _ToolError("ValidationError", f"invalid path {filepath!r}: relative to /workspace, no '..'")
    return session.workdir / p


def _int(v, default=None):
    if v is None or v == "":
        return default
    return int(v)


def _bool(v) -> bool:
    return v is True or str(v).strip().lower() in ("true", "1", "yes")


# --- the tools (HARNESS_README section 6) ------------------------------------------------------------------------

def _run_command(s: Session, command: str) -> dict:
    timeout = min(s.budget.command_timeout, max(5, int(s.remaining_seconds())))
    env = {**os.environ, "PYTHONPATH": str(s.workdir / "python"), "PYTHONDONTWRITEBYTECODE": "1"}
    proc = subprocess.Popen(["/bin/bash", "-c", command], cwd=s.workdir, env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, start_new_session=True)
    try:
        out, err = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        return _err("TimeoutExceeded", f"command exceeded {timeout} seconds")
    out, err = out[:MAX_STDOUT], err[:MAX_STDOUT]
    if proc.returncode == 0:
        return _ok(stdout=out, stderr=err, exit_code=0)
    return _err("CommandError", f"exit code {proc.returncode}", stdout=out, stderr=err, exit_code=proc.returncode)


def _read_file(s: Session, filepath, start_line=None, end_line=None) -> dict:
    p = _path(s, filepath)
    if not p.is_file():
        raise _ToolError("FileNotFound", f"{filepath}: no such file")
    lines = p.read_text(errors="replace").splitlines(keepends=True)
    start = max(1, _int(start_line, 1))
    end = min(len(lines), _int(end_line, len(lines)))
    out, n, truncated = [], 0, False
    for i in range(start, end + 1):
        line = lines[i - 1]
        if len(out) >= MAX_FILE_LINES or n + len(line) > MAX_FILE_CHARS:
            truncated = True
            break
        out.append(line)
        n += len(line)
    return _ok(filepath=str(p.relative_to(s.workdir)), content="".join(out), start_line=start,
               end_line=start + len(out) - 1, total_lines=len(lines), is_truncated=truncated)


_DELIMS = re.compile(r"([()\[\]{}:<>=])")


def _regex_for(old: str) -> re.Pattern:
    tokens = [t for part in _DELIMS.split(old) for t in part.split()]
    return re.compile(r"\s*".join(re.escape(t) for t in tokens if t))


def _flexible(content: str, old: str, new: str) -> tuple[str, int] | None:
    lines = content.split("\n")
    want = [ln.strip() for ln in old.strip("\n").split("\n")]
    hits = [i for i in range(len(lines) - len(want) + 1)
            if [ln.strip() for ln in lines[i:i + len(want)]] == want]
    if not hits:
        return None
    new_lines = new.strip("\n").split("\n")
    first_indent = len(new_lines[0]) - len(new_lines[0].lstrip())
    out = lines[:]
    for i in reversed(hits):
        prefix = lines[i][: len(lines[i]) - len(lines[i].lstrip())]
        repl = [(prefix + ln[first_indent:] if ln[:first_indent].strip() == "" else prefix + ln.lstrip()) if ln
                else ln for ln in new_lines]
        out[i:i + len(want)] = repl
    return "\n".join(out), len(hits)


def _edit_file(s: Session, filepath, old_string="", new_string="", allow_multiple=False) -> dict:
    p = _path(s, filepath)
    if not p.is_file() or p.stat().st_size == 0:
        raise _ToolError("FileEditError", f"{filepath}: missing or empty")
    if not old_string:
        raise _ToolError("FileEditError", "old_string is empty")
    many = _bool(allow_multiple)
    before = p.read_text().replace("\r\n", "\n")
    old = old_string.replace("\r\n", "\n")
    after, count, strategy = None, before.count(old), "exact"
    if count:
        if count > 1 and not many:
            raise _ToolError("FileEditError", f"old_string matches {count} times; pass allow_multiple=true")
        after = before.replace(old, new_string) if many else before.replace(old, new_string, 1)
    if after is None:
        hit = _flexible(before, old, new_string)
        if hit:
            strategy, (after, count) = "flexible", hit
            if count > 1 and not many:
                raise _ToolError("FileEditError", f"old_string matches {count} times; pass allow_multiple=true")
    if after is None:
        rx = _regex_for(old)
        found = list(rx.finditer(before))
        if found:
            count, strategy = len(found), "regex"
            if count > 1 and not many:
                raise _ToolError("FileEditError", f"old_string matches {count} times; pass allow_multiple=true")
            after = rx.sub(lambda m: new_string, before, count=0 if many else 1)
    if after is None:
        raise _ToolError("FileEditError", "old_string not found (exact, flexible and regex)")
    p.write_text(after)
    rel = str(p.relative_to(s.workdir))
    diff = "".join(difflib.unified_diff(before.splitlines(keepends=True), after.splitlines(keepends=True),
                                        f"a/{rel}", f"b/{rel}"))
    return _ok(filepath=rel, occurrences=count, strategy=strategy, diff=diff[:MAX_STDOUT],
               is_truncated=len(diff) > MAX_STDOUT)


def _write_file(s: Session, filepath, content="") -> dict:
    p = _path(s, filepath)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content)
    return _ok(filepath=str(p.relative_to(s.workdir)), size=len(content.encode()))


@traced
def extract_patch(workdir: Path) -> str:
    """git add -N . then the diff from the baseline, with the protected files the grader strips removed (8.1)."""
    _git(workdir, "add", "-N", ".")
    diff = _git(workdir, "diff", "--binary", "_swegemma_baseline")
    if diff.returncode != 0:
        diff = _git(workdir, "diff", "--binary", "HEAD")
    return tgate.strip_protected(diff.stdout)[0]


def _submit_patch(s: Session) -> dict:
    s.submitted_patch = extract_patch(s.workdir)
    s.patch_submitted = True
    return _ok(patch_size=len(s.submitted_patch), files_changed=len(re.findall(r"(?m)^diff --git ", s.submitted_patch)))


def _get_status(s: Session) -> dict:
    return _ok(tool_calls_used=s.tool_calls_used, patch_submitted=s.patch_submitted,
               patch_size=len(s.submitted_patch), tool_calls_remaining=s.remaining_calls(),
               max_tool_calls=s.budget.tool_calls, time_seconds_remaining=round(s.remaining_seconds(), 1),
               max_time_minutes=s.budget.time_minutes,
               agent_elapsed_seconds=round(time.monotonic() - s.started, 1), max_turns=s.budget.turns,
               command_timeout_seconds=s.budget.command_timeout)


class CodeGraph:
    """A task's code graph (node-link JSON) and node embeddings, for the three graph tools (6.3)."""

    def __init__(self, graph: dict, vectors: dict | None = None):
        self.nodes = {n["id"]: n for n in graph.get("nodes", [])}
        self.edges = [(e["source"], e["target"], e.get("type", "")) for e in graph.get("edges", [])]
        self.vectors = {k: np.asarray(v, dtype=float) for k, v in (vectors or {}).items()}

    @traced
    def resolve(self, name: str) -> str | None:
        name = str(name).strip()
        if name in self.nodes:
            return name
        for test in (lambda n: any(n.endswith(sep + name) for sep in ".;/"),
                     lambda n: n.lower() == name.lower(),
                     lambda n: name.lower() in n.lower()):
            hits = sorted(n for n in self.nodes if test(n))
            if hits:
                return hits[0]
        return None


def _graph(s: Session) -> CodeGraph:
    if s.graph is None:
        raise _ToolError("NoGraph", "no code graph or embeddings for this repository")
    return s.graph


def _cap(items: list[str]) -> tuple[list[str], bool]:
    out, n = [], 0
    for it in items:
        if n + len(it) > MAX_STDOUT:
            return out, True
        out.append(it)
        n += len(it)
    return out, False


def _get_code_neighbors(s: Session, node, edge_type=None, max_neighbors=50) -> dict:
    g = _graph(s)
    name = g.resolve(node)
    if name is None:
        raise _ToolError("NodeNotFound", f"{node!r} matches no symbol")
    kind = (edge_type or "").lower()
    seen = []
    for a, b, t in g.edges:
        if kind and t.lower() != kind:
            continue
        other = b if a == name else a if b == name else None
        if other and other not in seen:
            seen.append(other)
    names, cut = _cap(seen[: _int(max_neighbors, 50)])
    return _ok(node=name, neighbors=names, count=len(seen), is_truncated=cut)


def _search_similar_code(s: Session, query, k=10) -> dict:
    g, k = _graph(s), _int(k, 10)
    name = g.resolve(query)
    if name is not None and name in g.vectors:
        q = g.vectors[name]
        scores = [(float(np.dot(q, v) / ((np.linalg.norm(q) * np.linalg.norm(v)) or 1)), n)
                  for n, v in g.vectors.items() if n != name]
    else:   # lexical token-overlap fallback for a keyword query
        words = set(re.findall(r"\w+", str(query).lower()))
        scores = [(len(words & set(re.findall(r"\w+", (n + " " + g.nodes[n].get("text", "")).lower())))
                   / (len(words) or 1), n) for n in g.nodes]
    top = sorted(scores, key=lambda x: (-x[0], x[1]))[:k]
    per = MAX_STDOUT // max(1, len(top))
    results, cut = [], False
    for score, n in top:
        code = g.nodes.get(n, {}).get("text", "")
        cut = cut or len(code) > per
        results.append({"node_name": n, "code": code[:per], "similarity": round(score, 4)})
    return _ok(query=str(query), results=results, count=len(results), is_truncated=cut)


def _get_code_subgraph(s: Session, nodes) -> dict:
    g = _graph(s)
    if isinstance(nodes, str):
        try:
            nodes = json.loads(nodes)
        except json.JSONDecodeError:
            nodes = [x.strip() for x in nodes.split(",")]
    names = [n for n in (g.resolve(x) for x in nodes or []) if n]
    keep = set(names)
    edges = [{"from": a, "to": b, "type": t} for a, b, t in g.edges if a in keep and b in keep]
    shown, cut = _cap(names)
    return _ok(nodes=shown, edges=edges[:200], node_count=len(names), edge_count=len(edges),
               is_truncated=cut or len(edges) > 200)


_TOOLS = {"run_command": _run_command, "read_file": _read_file, "edit_file": _edit_file,
          "write_file": _write_file, "get_status": _get_status, "submit_patch": _submit_patch,
          "get_code_neighbors": _get_code_neighbors, "search_similar_code": _search_similar_code,
          "get_code_subgraph": _get_code_subgraph}


@traced
def call_tool(session: Session, name: str, arguments: dict | None) -> str:
    """One tool call, budget-gated as documented; always a JSON string, never an exception."""
    fn = _TOOLS.get(name)
    if fn is None:
        return json.dumps(_err("UnknownTool", f"no tool named {name!r}"))
    if name not in FREE_TOOLS:
        if session.remaining_calls() <= 0:
            return json.dumps(_err("BudgetExceeded", "no tool calls left: call submit_patch"))
        session.tool_calls_used += 1
    try:
        out = fn(session, **(arguments or {}))
    except _ToolError as e:
        out = _err(e.kind, str(e))
    except TypeError as e:
        out = _err("ValidationError", str(e))
    except Exception as e:  # noqa: BLE001 - a tool failure goes back to the model, as ToolErrorPlugin does
        out = _err(type(e).__name__, str(e)[:500])
    if session.budget.tool_calls >= 20 and session.remaining_calls() <= 10:
        out["budget_warning"] = (f"Only {session.remaining_calls()} tool call(s) remaining ({session.tool_calls_used}/"
                                 f"{session.budget.tool_calls} used). Finalize your edits and call submit_patch soon.")
    return json.dumps(out)


_SCHEMAS = {
    "run_command": {"command": "string"}, "submit_patch": {}, "get_status": {},
    "read_file": {"filepath": "string", "start_line": "integer", "end_line": "integer"},
    "edit_file": {"filepath": "string", "old_string": "string", "new_string": "string", "allow_multiple": "boolean"},
    "write_file": {"filepath": "string", "content": "string"},
    "get_code_neighbors": {"node": "string", "edge_type": "string", "max_neighbors": "integer"},
    "search_similar_code": {"query": "string", "k": "integer"},
    "get_code_subgraph": {"nodes": "array"},
}
_REQUIRED = {"run_command": ["command"], "read_file": ["filepath"], "write_file": ["filepath", "content"],
             "edit_file": ["filepath", "old_string", "new_string"], "get_code_neighbors": ["node"],
             "search_similar_code": ["query"], "get_code_subgraph": ["nodes"]}


@traced
def tool_specs(names: list[str]) -> list[dict]:
    """OpenAI-style function definitions for the declared tools."""
    out = []
    for n in names:
        props = {k: ({"type": t, "items": {"type": "string"}} if t == "array" else {"type": t})
                 for k, t in _SCHEMAS[n].items()}
        out.append({"type": "function", "function": {"name": n, "description": f"swegemma tool {n} (spec 035)",
                                                       "parameters": {"type": "object", "properties": props,
                                                                      "required": _REQUIRED.get(n, [])}}})
    return out


# --- the prompt (5.1, 5.2) --------------------------------------------------------------------------------------

@traced
def fill_instruction(instruction: str, task: dict) -> str:
    hints = (task.get("hints_text") or "").strip()
    return instruction.replace("{problem_description}", task.get("problem_statement") or "").replace("{hints}", hints)


_PRUNE = {"docs", "docs_src", "tests", "examples", "benchmarks"}


def _layout(root: Path) -> list[str]:
    out = []
    for depth in (1, 2, 3):
        for p in sorted(root.glob("/".join(["*"] * depth))):
            rel = p.relative_to(root)
            parts = rel.parts
            if any(x.startswith(".") or x == "__pycache__" or x.endswith(".egg-info") for x in parts):
                continue
            if p.suffix == ".pyc" or (len(parts) > 1 and parts[0] in _PRUNE):
                continue
            out.append(str(rel) + ("/" if p.is_dir() else ""))
            if len(out) >= 200:
                return sorted(out)
    return sorted(out)


@traced
def build_agent_prompt(task: dict, session: Session, declared: list[str]) -> str:
    b = session.budget
    parts = [(f"You are evaluating a software engineering task for repository {task.get('repo', '')}.\n\n"
              f"Problem Statement:\n{task.get('problem_statement') or ''}")]
    if (task.get("hints_text") or "").strip():
        parts.append(f"## Hints:\n{task['hints_text']}")
    parts.append("## Task Budget (Session terminates when any budget is exhausted)\n"
                 f"- Time allowance: {b.time_minutes} minutes\n- Tool calls allowance: {b.tool_calls} calls\n"
                 f"- Max loop iterations: {b.turns} turns")
    rules = [(f"- Single command timeout: {b.command_timeout} seconds (commands exceeding this fail without ending "
              "the session)"), f"- Command output limit: {MAX_STDOUT} characters"]
    if "read_file" in declared:
        rules += [f"- File view limit: {MAX_FILE_LINES} lines per read_file call",
                  f"- File character limit: {MAX_FILE_CHARS} characters per read_file call"]
    rules.append("- Environment is offline (no network/PyPI access). All repository and test dependencies are "
                 "ALREADY pre-installed. Do NOT attempt to run pip install or download packages.")
    parts.append("## Execution Environment Rules\n" + "\n".join(rules))
    parts.append("## Instructions\n0. Work only under /workspace.\n1. Inspect the repository's existing conventions "
                 "before changing code.\n2. Make the change the problem statement asks for.\n3. Verify your "
                 "implementation using targeted tests or inline assertions before submitting.\n4. Call submit_patch "
                 "once complete.\n5. Then reply with a short final text response.")
    graph_tools = [t for t in declared if t in GRAPH_TOOLS]
    if session.graph is not None and graph_tools:
        lines = {"search_similar_code": "- `search_similar_code(query)`: Find functions/classes with similar "
                 "precomputed embeddings given a symbol name.",
                 "get_code_neighbors": "- `get_code_neighbors(node)`: Find callers and callees of a symbol node.",
                 "get_code_subgraph": "- `get_code_subgraph(nodes)`: Get the induced call subgraph connecting a list "
                 "of symbol nodes."}
        parts.append("## Code Intelligence Tools\nThis repository has pre-built code graph and embedding data indexed "
                     "by dotted symbol path (e.g. `pkg.module.Class.method`). Use these tools for fast, targeted "
                     "navigation:\n" + "\n".join(lines[t] for t in graph_tools))
    parts.append("## Workspace Layout\n" + "\n".join(_layout(session.workdir)))
    return "\n\n".join(parts)


# --- the loop (5.3) ---------------------------------------------------------------------------------------------

NUDGE = ("Please continue your work using the available tools, or call submit_patch when you have completed and "
         "verified your changes.")
NUDGE_LENGTH = ("Your previous response reached the token limit while thinking before a tool call was completed. Do "
                "NOT repeat your analysis in thought—keep reasoning under a few sentences and emit your next tool call "
                "immediately, or call submit_patch when you have completed and verified your changes.")


@traced
def run_agent(task: dict, session: Session, model, instruction: str = "", declared: list[str] | None = None) -> dict:
    """The multi-turn loop. Returns counts: turns, nudges, tool calls."""
    declared = declared or ALL_TOOLS
    if hasattr(model, "start"):
        model.start(task)
    messages = []
    if instruction:
        messages.append({"role": "system", "content": fill_instruction(instruction, task)})
    messages.append({"role": "user", "content": build_agent_prompt(task, session, declared)})
    specs, turns, nudges, consecutive = tool_specs(declared), 0, 0, 0
    while turns < session.budget.turns and session.remaining_seconds() > 0:
        turns += 1
        reply = model.step(messages, specs)
        calls = reply.get("tool_calls") or []
        messages.append({"role": "assistant", "content": reply.get("content") or "",
                         "tool_calls": [{"id": c["id"], "type": "function",
                                         "function": {"name": c["name"], "arguments": json.dumps(c["arguments"])}}
                                        for c in calls]})
        for c in calls:
            name = c["name"] if c["name"] in declared else f"undeclared:{c['name']}"
            result = call_tool(session, name, c.get("arguments") or {})
            messages.append({"role": "tool", "tool_call_id": c["id"], "content": result})
        if session.patch_submitted:
            break
        if calls:
            consecutive = 0
            if session.remaining_calls() <= 0:   # nothing left but submit_patch: the fallback takes the diff
                break
            continue
        consecutive += 1
        if consecutive > MAX_NUDGES:
            break
        nudges += 1
        reason = str(reply.get("finish_reason") or "").upper()
        messages.append({"role": "user", "content": NUDGE_LENGTH if ("LENGTH" in reason or "MAX_TOKENS" in reason)
                         else NUDGE})
    session.done = True
    return {"turn_count": turns, "nudge_count": nudges, "tool_call_count": session.tool_calls_used}


# --- verification (8.2) --------------------------------------------------------------------------------------------

def _apply_resilient(workdir: Path, patch: str) -> bool:
    for args in (["apply"], ["apply", "-3"], ["apply", "--ignore-space-change", "--ignore-whitespace"],
                 ["apply", "--recount"], ["apply", "-p0"]):
        if _git(workdir, *args, "--whitespace=nowarn", "-", stdin=patch).returncode == 0:
            return True
    return False


@traced
def verify(task: dict, agent_patch: str, source: Path, work: Path, timeout: int = tgate.DEFAULT_TIMEOUT) -> dict:
    """A fresh workspace at base_commit, the agent's patch (protected files stripped), the task's test files reset
    and its test patch applied, then the target tests: resolved iff exit 0, passed > 0, no failures or errors."""
    out = {"is_resolved": False, "verify_exit_code": None, "verify_passed_count": None, "verify_failed_count": None,
           "verify_error_count": None, "reason_text": ""}
    patch = tgate.strip_protected(agent_patch or "")[0]
    if not patch.strip():
        out["reason_text"] = "empty patch"
        return out
    ws = prepare_workspace(task, source, Path(work))
    if not _apply_resilient(ws, patch):
        out["reason_text"] = "agent patch didn't apply"
        return out
    if not tgate._apply(ws, task["test_patch"]):
        out["reason_text"] = "test_patch didn't apply over the agent patch"
        return out
    targets = tgate.target_tests(task["test_patch"])
    res = tgate.run_tests(ws, targets, timeout)
    j = res["junit"] or {}
    out.update(verify_exit_code=res["exit_code"], verify_passed_count=j.get("passed"),
               verify_failed_count=j.get("failures"), verify_error_count=j.get("errors"))
    if res["exit_code"] is None:
        out["reason_text"] = "verification timed out"
    elif res["exit_code"] == 0 and j.get("passed") and not j.get("failures") and not j.get("errors"):
        out["is_resolved"] = True
    else:
        out["reason_text"] = "tests fail with the agent's patch"
    return out


# --- one task ------------------------------------------------------------------------------------------------------

@traced
def run_task(task: dict, source: Path, model, budget: Budget, work: Path, instruction: str = "",
             declared: list[str] | None = None, graph: CodeGraph | None = None) -> dict:
    """Phase 1 (the agent in a workspace) and phase 2 (verification in a fresh one) for one task."""
    work = Path(work)
    session = Session(prepare_workspace(task, source, work / "agent"), budget, graph=graph)
    counts = run_agent(task, session, model, instruction, declared)
    patch = session.submitted_patch if session.patch_submitted else extract_patch(session.workdir)
    row = {"instance_id": task["instance_id"], "harness_name": HARNESS_NAME,
           "model_name": getattr(model, "name", type(model).__name__), "is_patch_submitted": session.patch_submitted,
           "agent_patch_bytes": len(patch.encode()), "files_changed_count": len(re.findall(r"(?m)^diff --git ", patch)),
           "agent_seconds": round(time.monotonic() - session.started, 2), **counts}
    row.update(verify(task, patch, source, work / "verify"))
    return {c: row.get(c) for c in RUN_COLUMNS}


# --- scripted models that bound the runner ------------------------------------------------------------------------

class OracleModel:
    """Replays the task's reference patch, then submits: should resolve every valid task. A calibration run, named
    calib:oracle. The patch goes through write_file then run_command (git apply), since Linux caps one command-line
    argument at 128 KB and some reference patches are bigger."""
    name = "calib:oracle"
    FILE = "_oracle.patch"

    @traced
    def start(self, task: dict) -> None:
        self.patch, self.turn = task["patch"].rstrip("\n") + "\n", 0

    @traced
    def step(self, messages, tools):
        self.turn += 1
        script = [("write_file", {"filepath": self.FILE, "content": self.patch}),
                  ("run_command", {"command": f"git apply --whitespace=nowarn {self.FILE} && rm {self.FILE}"}),
                  ("submit_patch", {})]
        if self.turn <= len(script):
            name, args = script[self.turn - 1]
            return {"content": "", "finish_reason": "tool_calls",
                    "tool_calls": [{"id": f"oracle-{self.turn}", "name": name, "arguments": args}]}
        return {"content": "Applied the reference patch.", "tool_calls": [], "finish_reason": "stop"}


class NullModel:
    """Submits without changing anything: should resolve none. A calibration run, named calib:null."""
    name = "calib:null"

    @traced
    def step(self, messages, tools):
        if not any(m.get("role") == "tool" for m in messages):
            return {"content": "", "finish_reason": "tool_calls",
                    "tool_calls": [{"id": "null-1", "name": "submit_patch", "arguments": {}}]}
        return {"content": "Submitted.", "tool_calls": [], "finish_reason": "stop"}


@traced
def load_graph(task: dict, graphs_dir: Path, embeddings_dir: Path) -> CodeGraph | None:
    """The task's graph and embeddings, by the competition's name (<repo name>_<base_commit>) or the instance id."""
    stems = [f"{task['repo'].split('/')[-1]}_{task['base_commit']}", task["instance_id"]]
    for stem in stems:
        g = Path(graphs_dir) / f"{stem}.json"
        if g.exists() and g.stat().st_size > 100:
            e = Path(embeddings_dir) / f"{stem}.npz"
            vectors = dict(np.load(e)) if e.exists() and e.stat().st_size > 100 else {}
            return CodeGraph(json.loads(g.read_text()), vectors)
    return None


@traced
def workspace_tmp() -> Path:
    return Path(tempfile.mkdtemp(prefix="htlnlp_harness_"))
