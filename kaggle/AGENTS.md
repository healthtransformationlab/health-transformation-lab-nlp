# kaggle/AGENTS.md

Rules for agents babysitting Colab or Kaggle competition runs for this repo
(spec 028, and the forwards in 014 US8 and 041 US2). Read the root `AGENTS.md`
first. Never type, paste or reveal a token or secret; never submit anything to
Kaggle; never edit a status spreadsheet unless the operator asks.

## Close what is done

Paid GPUs and open tabs are easy to leave running by accident. Treat finished
work as something to close, not something to leave green.

1. **One runtime per notebook URL.** Two tabs of the same Colab notebook often
   share one runtime. Matching "Executing" timers mean one run, not two. Prefer
   one tab with a live log; close a blank or duplicate view of the same session
   without using Disconnect (Disconnect would stop the shared runtime).
2. **A chunk finished, more still listed.** Leave the runtime alone. The
   notebook re-reads `kaggle/colab_official_run.json` and starts the next run
   itself. Do not disconnect between chunks. **Do** forward that finished chunk
   (next section) while the next one runs.
3. **The output says nothing is left to run** ("the run list says stop",
   "nothing new was listed", "releasing the GPU"). Forward every finished label
   that has not been forwarded yet. Then, in that tab only: Runtime →
   Disconnect and delete runtime, then close the tab. Tell the operator the
   labels that finished and the time (12-hour form, UTC with Central beside it).
4. **A dead tab** (Connecting / Disconnected / Reconnect for more than 5
   minutes with no advancing output, or a tab whose run stopped uploading and
   is not the live one): Disconnect and delete runtime in that tab, then close
   it. Do not Disconnect a tab that shares a runtime with a healthy live run.
5. **No A100 free, or compute units used up.** Stop. Tell the operator. Do not
   switch GPU.

## After every finished label: push the results

A Colab or Modal run only lands in a private Kaggle dataset
(`jcblearning/htlnlp-colab-official-<label>`). That is **not** enough. Until
something forwards it, Azure Application Insights and the Databricks MLflow
experiment have no record of the run. Agent babysitting sessions hold no
secrets for Databricks or App Insights, so the forwards are explicit steps —
do them as soon as a label prints `finished, kernel exit 0`, and again before
you disconnect the last tab.

### 1. Azure Application Insights (spec 014 US8)

```bash
gh workflow run forward-run-telemetry.yml \
  -f results_dataset=jcblearning/htlnlp-colab-official-<label> \
  -f label=<label> \
  -f platform=colab \
  -f content=full
```

Watch it: `gh run list --workflow=forward-run-telemetry.yml --limit 5`. It must
print `telemetry export: ok`. Never paste a connection string into chat.

### 2. Databricks / Unity Catalog traces (spec 041 US2)

Download the same results dataset (Kaggle API, read-only), then:

```bash
python kaggle/load_agent_traces.py <downloaded results dir> \
  --label <label> \
  --agent "<agent name>" \
  --model gemma-4-31b
```

Needs `DATABRICKS_HOST` and `DATABRICKS_TOKEN` (never ask for the token in
chat; use the session's existing env or the secrets register). Default
experiment: `/Shared/coding-agent-runs` (`AGENT_TRACE_EXPERIMENT`). Loading
twice is safe: each `trace_key` is written once. Prefer `--dry-run` first if
the session has not loaded this label before.

If this session cannot reach Databricks or cannot run the workflow, **stop and
tell the operator which labels still need both forwards**. Do not treat
"uploaded to Kaggle" as done.

### 3. Catch labels that were never pushed

Before ending a babysitting session (and any time the operator asks "did we
miss any"):

1. List finished labels on the run-list branch:
   `python kaggle/colab_status.py --branch data/849-028-colab-public-bundle`
   (or whichever branch the notebook reads).
2. List recent Azure forwards:
   `gh run list --workflow=forward-run-telemetry.yml --limit 50`
3. Any label whose Kaggle state is `finished` and that does not appear in a
   successful forward run (or in `/Shared/coding-agent-runs`) is a gap: forward
   it to Azure and load it into Databricks before you stop.

## Starting and watching

- Runtime → Change runtime type → the GPU the run list names (A100 means A100
  GPU, High-RAM off) → Save, then Runtime → Run all. Allow secrets access if
  asked; never type or paste a token.
- Read the run label the output prints. If two tabs of the same notebook print
  the same label, they are the same session: keep one, close the other without
  Disconnect.
- A run that stops with `resume_session` in the message needs that string on
  its entry in `kaggle/colab_official_run.json` on the branch the notebook
  reads. A session that already recorded the label as failed will not retry it
  until Runtime → Run all starts a **new** session (after the current chunk
  finishes, so progress is not thrown away).
