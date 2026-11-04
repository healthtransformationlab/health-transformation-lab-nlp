"""What a coding-agent task costs, and a cap on a run's share of the Kaggle GPU allowance (spec 036 US2, #569).

    load_settings(path)          ops/cost_settings.yaml: the allowance and the price, each with its source and date
    task_cost(seconds, gpus, s)  one task: allowance hours (session time, as Kaggle counts it), GPU-hours (session
                                 time by GPU count, as a cloud bills), and an estimated cost, named as an estimate
    expected_seconds(id, past)   a task's expected session time: its earlier run, else the median of runs so far
    plan_under_cap(ids, exp, h)  cheapest first, stopping before the task that would pass the cap

Cheapest first means the easiest tasks tend to run first, so a run stopped by its cap reports its resolution rate
over the tasks it ran, never over the whole set.
"""

from __future__ import annotations

import statistics
from pathlib import Path

from .paths import REPO_ROOT
from .telemetry import traced

SETTINGS = REPO_ROOT / "ops" / "cost_settings.yaml"
KEYS = ("kaggle_weekly_allowance_hours", "t4_usd_per_gpu_hour")
DEFAULT_SECONDS = 720.0   # the pilot's tasks held a session for 10 to 12 minutes (spec 035 T005)


@traced
def load_settings(path: Path = SETTINGS) -> dict:
    """Each setting with a positive value, a source and the date it was read; refused, naming it, otherwise."""
    import yaml
    s = yaml.safe_load(Path(path).read_text()) or {}
    for k in KEYS:
        v = s.get(k) or {}
        ok = isinstance(v.get("value"), (int, float)) and v["value"] > 0 and v.get("source") and v.get("read_date")
        if not ok:
            raise SystemExit(f"{Path(path).name}: {k} needs a positive value, a source and a read_date")
    return s


@traced
def task_cost(session_seconds: float | None, gpu_count: int, settings: dict) -> dict:
    price = settings["t4_usd_per_gpu_hour"]
    basis = (f"estimate: {price['value']} USD per T4 GPU-hour ({price['source']}, read {price['read_date']}); "
             "Kaggle's GPUs are free")
    if session_seconds is None:
        return {"session_seconds": None, "gpu_count": gpu_count, "allowance_hours": None,
                "kaggle_allowance_ratio": None, "gpu_hours": None, "estimated_cost_usd": None,
                "price_basis_text": basis}
    hours = session_seconds / 3600
    gpu_hours = hours * gpu_count
    return {"session_seconds": round(session_seconds, 1), "gpu_count": gpu_count, "allowance_hours": round(hours, 4),
            "kaggle_allowance_ratio": hours / settings["kaggle_weekly_allowance_hours"]["value"],
            "gpu_hours": round(gpu_hours, 4), "estimated_cost_usd": round(gpu_hours * price["value"], 4),
            "price_basis_text": basis}


@traced
def expected_seconds(instance_id: str, past: dict[str, float]) -> float:
    if instance_id in past:
        return past[instance_id]
    return statistics.median(past.values()) if past else DEFAULT_SECONDS


@traced
def plan_under_cap(ids: list[str], expected: dict[str, float], cap_hours: float | None,
                   used_hours: float = 0.0) -> tuple[list[str], list[str]]:
    """(to run, left): ids by expected time, cheapest first, taking each while the total stays within the cap."""
    order = sorted(ids, key=lambda i: expected.get(i, DEFAULT_SECONDS))   # stable: ties keep the caller's order
    if cap_hours is None:
        return order, []
    run, total = [], used_hours
    for n, i in enumerate(order):
        need = expected.get(i, DEFAULT_SECONDS) / 3600
        if total + need > cap_hours:
            return run, order[n:]
        run.append(i)
        total += need
    return run, []
