"""A pytest plugin for 68_trace_reach.py (028 AI6, #670): while each test runs, the package's functions that are called,
and the package's frames on each failure's traceback, by the code graph's names (`module.Class.method`). Written to
TRACE_OUT as JSON when the session ends; the package is TRACE_PACKAGE. Names only: no arguments, values or output.
With TRACE_MESSAGES=1 it also keeps, for each test that fails or cannot run, its id and the first line of its error
(028 AI7, #674: the failing test's report an agent can be given), with this machine's paths taken out."""
import json
import os
import re
import sys

import pytest

PACKAGE = os.environ.get("TRACE_PACKAGE", "")
OUT = os.environ.get("TRACE_OUT", "trace.json")
_called: set[str] = set()
_failures: list[list[str]] = []
_collection_errors: list[dict] = []
MESSAGES = os.environ.get("TRACE_MESSAGES") == "1"
_messages: list[dict] = []
_PATH = re.compile(r"\s*\((?:/|[A-Za-z]:\\)[^)]*\)")
_ERRORS = ((re.compile(r"ImportError: cannot import name '([^']+)' from '([^']+)'"), "ImportError", (1, 2)),
           (re.compile(r"AttributeError: module '([^']+)' has no attribute '([^']+)'"), "AttributeError", (2, 1)),
           (re.compile(r"ModuleNotFoundError: No module named '([^']+)'"), "ModuleNotFoundError", (None, 1)))


def first_line(text: str, limit: int = 300) -> str:
    """The first line of an error that says something, without a path of this machine."""
    line = next((ln.strip() for ln in str(text).splitlines() if ln.strip()), "")
    return _PATH.sub("", line).replace(os.getcwd() + os.sep, "")[:limit]


def _in_package(module: str) -> bool:
    return bool(PACKAGE) and (module == PACKAGE or module.startswith(PACKAGE + "."))


def graph_name(code, module: str) -> str | None:
    """`module.Class.method` as the graph names it; None for code the graph has no node for (a generator expression,
    a comprehension, a lambda, a module or class body run at import)."""
    parts = [p for p in code.co_qualname.split(".") if p != "<locals>"]
    if any(p.startswith("<") for p in parts):
        return None
    return f"{module}.{'.'.join(parts)}"


def _profile(frame, event, arg):
    if event == "call" and _in_package(module := frame.f_globals.get("__name__", "")):
        if (name := graph_name(frame.f_code, module)) is not None:
            _called.add(name)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_call(item):
    sys.setprofile(_profile)
    try:
        yield
    finally:
        sys.setprofile(None)


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    report = outcome.get_result()
    if MESSAGES and report.failed and report.when in ("setup", "call") and call.excinfo is not None:
        _messages.append({"kind_code": "FAILED" if report.when == "call" else "ERROR", "test_id": report.nodeid,
                          "message_text": first_line(call.excinfo.exconly(tryshort=True))})
    if report.when == "call" and report.failed and call.excinfo is not None:
        frames, tb = [], call.excinfo.tb
        while tb is not None:
            module = tb.tb_frame.f_globals.get("__name__", "")
            if _in_package(module) and (name := graph_name(tb.tb_frame.f_code, module)) is not None:
                frames.append(name)
            tb = tb.tb_next
        _failures.append(frames)


def pytest_collectreport(report):
    """A test file that cannot even be imported, usually because it imports a name the fix adds: the error's type,
    the missing name and its module, read from the report (names only)."""
    if report.failed:
        text = str(report.longrepr)
        if MESSAGES:
            errors = [ln[1:] for ln in text.splitlines() if ln.startswith("E ")]
            _messages.append({"kind_code": "ERROR", "test_id": report.nodeid,
                              "message_text": first_line(errors[-1] if errors else text)})
        for pattern, kind, (name_at, module_at) in _ERRORS:
            if m := pattern.search(text):
                _collection_errors.append({"error_type": kind, "missing_name": m.group(name_at) if name_at else None,
                                           "module": m.group(module_at)})
                break
        else:
            _collection_errors.append({"error_type": "other", "missing_name": None, "module": None})


def pytest_sessionfinish(session, exitstatus):
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump({"called": sorted(_called), "failure_frames": _failures, "collection_errors": _collection_errors,
                   "exit_status": int(exitstatus), **({"failure_messages": _messages} if MESSAGES else {})}, f)
