# Spec 035 US2 (#544): the Gemma agent on ONE task, on a Kaggle GPU, beside that task's bundle and the model only
# (kaggle/agent_bundle.py says why nothing else may be attached). Internet off. Writes /kaggle/working/result.json:
# the agent's patch, its counts, each turn's tokens and seconds, and the settings. The patch is verified elsewhere
# (python/scripts/60_kaggle_agent.py, in the sandbox), so this kernel never sees the task's tests.
# Measured with this repository's re-implementation of the competition's harness, NOT the competition's evaluator.
import glob
import json
import os
import sys
import time
import traceback
from pathlib import Path

OUT = Path("/kaggle/working/result.json")
result = {"started_ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
try:
    bundle = Path(glob.glob("/kaggle/input/**/task.json", recursive=True)[0]).parent
    sys.path.insert(0, str(bundle))
    from htl_agent import agent_harness as ah
    from htl_agent import gemma_agent as ga
    import numpy as np
    import torch

    task = json.loads((bundle / "task.json").read_text())
    cfg = json.loads((bundle / "agent.json").read_text())
    model_cfg = dict(cfg.get("model") or {})
    variant = model_cfg.pop("variant", "gemma-4-e4b-it")
    model_dir = Path(glob.glob(f"/kaggle/input/**/{variant}/**/config.json", recursive=True)[0]).parent
    result.update(instance_id=task["instance_id"], gpus=[torch.cuda.get_device_name(i)
                                                         for i in range(torch.cuda.device_count())])
    graph = None
    if (bundle / "graph.json").exists():
        vectors = dict(np.load(bundle / "embedding.npz")) if (bundle / "embedding.npz").exists() else {}
        graph = ah.CodeGraph(json.loads((bundle / "graph.json").read_text()), vectors)
    t = time.monotonic()
    model = ga.GemmaModel(str(model_dir), name=variant, **model_cfg)
    result["load_seconds"] = round(time.monotonic() - t, 1)
    row, patch = ah.agent_phase(task, bundle / "snapshot.tgz", model, ah.Budget(**cfg["budget"]), Path("/tmp/htl_work"),
                                cfg["instruction"], cfg["tools"], graph, sandboxed=False)
    result.update(row=row, patch=patch, turns=model.turns, history=model.history,
                  settings={"variant": variant, **model_cfg, "budget": cfg["budget"], "tools": cfg["tools"]})
except Exception as e:  # noqa: BLE001 - the failure goes in result.json, where the runner reads it
    result.update(error=f"{type(e).__name__}: {str(e)[:1000]}", trace=traceback.format_exc()[-3000:])
result["finished_ts"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
OUT.write_text(json.dumps(result, indent=1, default=str))
print(json.dumps({k: v for k, v in result.items() if k not in ("patch", "history", "trace")}, indent=1, default=str))
if "error" in result:
    print(result["trace"])
