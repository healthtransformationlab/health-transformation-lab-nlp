# Review: Colab babysitting relief (#888)

## What changed
1. Pro+ background execution is the documented default; keep-tab is fallback (AGENTS + notebook).
2. Fewer Colab nights / ADR 0011 note in AGENTS.
3. Multi-task Colab packs: default `--deadline-minutes` 180; refuse below 180 unless `--allow-short-deadline`. Kernel meta default 180.

## Dropped (2026-11-20)
Phone/`colab_watch.py`/ntfy: the owner keeps the laptop awake and checks via Cursor remote; a second watcher was not useful.

## Risk
Policy + deadline guard. Deadline change can break callers that relied on 45 without passing a value — that was the bug we are fixing.
