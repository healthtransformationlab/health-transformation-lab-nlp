# ADR 0010: a coding-agent run's own trace may reach telemetry in full; dental records never do

Date: 2026-11-16 · Status: accepted · Issue: #850

## Context

Since spec 014, no text reaches a span: `annotate()` and `forward_spans()` keep numbers and labels of at most 64
characters, and `AGENTS.md` says "Never put note text or row-level data in span attributes or logs." The rule was
written for dental records, and the coding agent's runs were put under it too (014 US6 to US8): a task's span holds
counts, and a tool call's span holds the tool's name and its timing.

That left a failed task undiagnosable from telemetry. What the agent read, each command, each edit, each tool's output
and the patch are only in the trace file inside a private Kaggle dataset, so every question started with a download.
On November 16, 2026 the owner asked: "Did you update our open telemetry to give us the data we need to diagnose none
of this is public you can make it an override setting but for these repos we can log everything except password".

What a coding-agent run holds is not what the rule protects:

- **The content is public code.** The tasks are issues and source files from public repositories (FastAPI, Rich,
  Requests and others), the model's own messages, and its patch. There is no patient, no note and no row of a dataset.
- **The store is private.** Application Insights is the owner's own resource; an agent session reads it with a
  read-only key (`ops/secrets_register.yaml`).
- **Hidden tasks never pass through it.** A leaderboard entry runs on the host's machines with no code of ours.

## Decision

- **One setting, `DENTAL_TELEMETRY_CONTENT`: `labels` (the default) or `full`.** Any other value stops the caller at
  once.
- **`full` applies to a coding-agent run's own trace only**, sent by `kaggle/forward_run_telemetry.py`: each step's
  message, tool calls with their arguments, the tool's output, token counts and times, and the task's patch and error
  text. The workflow that forwards a run asks for `full` by default.
- **Text reaches a span only through `telemetry.content_span`**, which scrubs every text value first
  (`telemetry.scrub`): token shapes (Kaggle, Hugging Face, GitHub, `sk-`, AWS), `Bearer` tokens, Azure connection-string
  keys, quoted values assigned to names such as `password` or `api_key`, and the values of the process's own secret
  environment variables. A secret is never logged, whatever the setting.
- **Dental-record code is unchanged, whatever the setting.** `annotate()`, `@traced` and `forward_spans()` still keep
  text only as a short label. Note text and row-level data never reach a span or a log.

## Consequences

- **Easier:** "why did task X fail in run Y" is one query (`agent_step` spans by `run_label` and `instance_id`), from an
  agent session or the portal, for runs already finished too, since the content comes from the trace files.
- **Harder:**
  - A scrubber works on shapes. A secret in a shape it doesn't know, with a name that doesn't say so, would be sent.
    The agent's sandbox is given no credentials, which is the real protection; the scrubber is the second one.
  - Ingestion grows from kilobytes to about 2 MB of text for a 33-task run. Ten full 129-task runs are about 0.1 GB
    against the 5 GB a month the workspace takes free (014 US3).
  - A run forwarded twice is there twice; `forward_id` tells the two apart.
- **The public repository shows how the content is sent, not the content.** Development-task text stays out of the
  repository as before.

## Revisit when

- A coding-agent run is given credentials, or runs on private code: `full` then needs an allowlist, not a scrubber.
- Ingestion nears the free allowance, or the competition ends (December 2, 2026): set the workflow's default to
  `labels`.
- A secret is found in a span: SEV1, rotate it, purge the rows, and add its shape to `scrub` with a test.
