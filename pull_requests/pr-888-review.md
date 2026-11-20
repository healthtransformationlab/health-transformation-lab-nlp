# Review: Colab babysitting relief (#888)

## What changed
1. Pro+ background execution is the documented default; keep-tab is fallback (AGENTS + notebook).
2. `kaggle/colab_watch.py` polls status, ntfy on stale/finished, writes status JSON (+ mirrors to ideas panel).
3. Fewer Colab nights / ADR 0011 note in AGENTS.
4. Multi-task Colab packs: default `--deadline-minutes` 180; refuse below 180 unless `--allow-short-deadline`. Kernel meta default 180.

## Risk
Policy + tooling. Watcher is read-only on Kaggle. Deadline change can break callers that relied on 45 without passing a value — that was the bug we are fixing.
