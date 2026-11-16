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
  (`telemetry.scrub`), and a test fails if anything but the forwarder calls it. The scrubber knows shapes and names:
  - token shapes (Kaggle, Hugging Face, GitHub, `sk-`, AWS, Databricks, Google, Slack, PyPI, GitLab, npm, Modal, JSON
    web tokens) and private-key blocks;
  - a value given to a telling name (`password`, `secret`, `token`, `api_key`, `private_key`, `credentials`, `auth`,
    `key`), quoted in code or JSON, or unquoted after a NAME in capitals (`export`, `.env`, `printenv`);
  - `--password` and `--token` options, `curl -u`, `Authorization`, `Bearer`, `X-API-Key` and `Cookie` headers,
    `scheme://user:password@host`, a secret in a query string, an Azure connection string's key;
  - the values of the forwarder's own secret environment variables.

  JSON (a tool call's arguments, an output written as JSON) is scrubbed leaf by leaf before it is written out, so a
  quoted secret is seen as it was typed (`telemetry.scrub_value`).
- **A secret is never meant to reach a span, whatever the setting, but a scrubber of shapes is not a proof.** What it
  cannot know is under "Harder" and in `docs/telemetry.md`.
- **Dental-record code is unchanged, whatever the setting.** `annotate()`, `@traced` and `forward_spans()` still keep
  text only as a short label. Note text and row-level data never reach a span or a log.

## Consequences

- **Easier:** "why did task X fail in run Y" is one query (`agent_step` spans by `run_label` and `instance_id`), from an
  agent session or the portal, for runs already finished too, since the content comes from the trace files.
- **Harder:**
  - A scrubber works on shapes and names. It lets through: a secret in a shape it has no rule for under a name that
    doesn't tell; a password that is one plain word (`"hunter"` reads as ordinary text, the price of leaving
    `"token_type": "bearer"` readable); an unquoted YAML or ini value with no digit in it; a secret encoded again
    (base64, URL-encoded). An independent review tried 78 realistic inputs against it: 61 leaked through the first
    version and none through this one, which is now the test (`python/tests/test_telemetry_content.py`).
  - It also redacts some ordinary text: a quoted value with a digit under a telling name
    (`token: "OAuth2Token"`), and the password part of an example URL such as `https://user:pass@example.com`.
  - What the agent's sandbox can see differs by platform. On Colab the kernel's environment is stripped of
    credentials by name (`kaggle/colab_official.py`); on Kaggle and Modal it is whatever the platform gives the
    process, which is why `NAME=value` lines and web tokens are scrubbed.
  - Ingestion grows from kilobytes to megabytes. Forwarding 21 tasks of one run (640 steps) to a file sent 1.96 MB
    of text (this session's check; the traces are development-task content and are not committed), so a 129-task
    run is about 12 MB and ten runs about 0.12 GB, against the 5 GB a month the workspace takes free (014 US3).
  - One item may be 64 KB. A step's three long texts are 8,000 characters each at most, which is under it for
    ordinary code and could pass it for text that is mostly non-Latin script.
  - A run forwarded twice is there twice; `forward_id` tells the two apart.
- **The public repository shows how the content is sent, not the content.** Development-task text stays out of the
  repository as before.

## Revisit when

- A coding-agent run is given credentials, or runs on private code: `full` then needs an allowlist, not a scrubber.
- Ingestion nears the free allowance, or the competition ends (December 2, 2026): set the workflow's default to
  `labels`.
- A secret is found in a span: SEV1, rotate it, purge the rows, and add its shape to `scrub` with a test.
