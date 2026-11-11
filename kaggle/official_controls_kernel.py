# The competition's own verification on its development tasks, with the reference patch and with an empty patch
# (028 AI4, #668; kaggle/official_controls_run.py). CPU, internet off; the competition, the evaluator's wheelhouse and
# a bundle with the submission, kaggle/official_verify.py and the ids attached; no model. Verifies from the
# competition's own folder, where the tests' wheels and setup script sit beside tasks.jsonl. Writes
# /kaggle/working/verdicts_<kind>.jsonl and result.json.
import glob
import importlib
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from pathlib import Path

for _k, _v in {"MLFLOW_DISABLE_AGENT_HINT": "1", "OTEL_SDK_DISABLED": "true", "LITELLM_TELEMETRY": "False"}.items():
    os.environ[_k] = _v
OUT = Path(os.environ.get("HTL_OUT", "/kaggle/working"))


def install_wheelhouse() -> Path:
    """As kaggle/official_agent_kernel.py installs it (the starter notebook's cell 2): every wheel, no dependencies."""
    wheelhouse = Path(glob.glob("/kaggle/input/**/swegemma-*.whl", recursive=True)[0]).parent
    for pattern in ("/usr/local/lib/python*/dist-packages/*cutlass*.pth", "/usr/local/lib/python*/site-packages/*cutlass*.pth"):
        for pth in glob.glob(pattern):
            try:
                os.unlink(pth)
            except OSError:
                pass
    tmp = Path("/tmp/wheelhouse")
    tmp.mkdir(parents=True, exist_ok=True)
    for w in wheelhouse.glob("*.whl"):
        if "cutlass" in w.name.lower():
            continue
        name = w.name.replace("cu128", "+cu128") if ("cu128" in w.name and "+" not in w.name) else w.name
        if not (tmp / name).exists():
            try:
                os.symlink(w, tmp / name)
            except OSError:
                shutil.copyfile(w, tmp / name)
    wheels = sorted(str(w) for w in tmp.glob("*.whl"))
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", "--no-deps", "--force-reinstall", *wheels], check=True)
    importlib.invalidate_caches()
    return wheelhouse


def find_competition(root: Path = Path("/kaggle/input")) -> Path:
    """As kaggle/official_agent_kernel.py finds it: the folder with HARNESS_README.md, tasks.jsonl and snapshots/."""
    for readme in sorted(glob.glob(str(Path(root) / "**" / "HARNESS_README.md"), recursive=True)):
        folder = Path(readme).parent
        if (folder / "tasks.jsonl").is_file() and (folder / "snapshots").is_dir():
            return folder
    raise SystemExit(f"no competition attached under {root}")


def main() -> None:
    result = {"started_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    try:
        bundle = Path(glob.glob("/kaggle/input/**/controls.json", recursive=True)[0]).parent
        meta = json.loads((bundle / "controls.json").read_text())
        t = time.monotonic()
        result["wheelhouse"] = str(install_wheelhouse())
        result["install_seconds"] = round(time.monotonic() - t, 1)
        comp = find_competition()
        result["competition_folder"] = str(comp)
        sub = OUT / "submission"
        shutil.rmtree(sub, ignore_errors=True)
        shutil.copytree(bundle / "submission", sub)
        for kind in meta["kinds"]:
            t = time.monotonic()
            r = subprocess.run([sys.executable, str(bundle / "official_verify.py"), "--tasks", str(comp / "tasks.jsonl"),
                                "--snapshots-dir", str(comp / "snapshots"), "--submission-dir", str(sub),
                                "--results-dir", str(OUT / f"results_{kind}"), "--patch", kind,
                                "--task-ids", *meta["instance_ids"], "--concurrency", str(meta.get("concurrency", 3)),
                                "--out", str(OUT / f"verdicts_{kind}.jsonl")],
                               capture_output=True, text=True, cwd=OUT, env={**os.environ, "TAIL": "400"})   # a short tail, to diagnose
            result[kind] = {"returncode": r.returncode, "seconds": round(time.monotonic() - t, 1),
                            "stdout_tail": r.stdout[-600:], "stderr_tail": r.stderr[-2000:]}
            print(json.dumps({kind: {k: v for k, v in result[kind].items() if k != "stderr_tail"}}), flush=True)
    except BaseException as e:  # noqa: BLE001 - the failure goes in result.json, where the runner reads it
        result.update(error=f"{type(e).__name__}: {str(e)[:1500]}", trace=traceback.format_exc()[-4000:])
    finally:
        shutil.rmtree(OUT / "submission", ignore_errors=True)
        for kind in ("oracle", "null"):            # the extracted workspaces and logs stay on Kaggle
            shutil.rmtree(OUT / f"results_{kind}", ignore_errors=True)
    result["finished_ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "result.json").write_text(json.dumps(result, indent=1, default=str))
    print(json.dumps({k: v for k, v in result.items() if k != "trace"}, indent=1, default=str))


if __name__ == "__main__":
    main()
