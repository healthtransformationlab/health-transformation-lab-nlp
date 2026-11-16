# PR 851 review: a coding-agent run's full trace reaches Azure when DENTAL_TELEMETRY_CONTENT=full (#850)

Reviewed against `AGENTS.md`, `CLAUDE.md` and `.claude/review-rubric.md`. A separate read-only reviewer went through
`origin/main...8f4142b` first, told to look hardest at the scrubber; the author session reproduced each finding,
fixed it in `511af35`, and reran the reviewer's own probes. The reviewer could not read the issue, the PR text or CI
(its GitHub connection failed), so those rows are the author session's.

## Scans

| Scan | Result |
|---|---|
| Secrets | clean: the test "secrets" are made up and written in pieces; no credential, connection string or application id is added |
| PHI / real data | none: no task text, trace content or patch from a run is committed |
| Organization claims | none |

## Compliance

| Rule | Result |
|---|---|
| Issue with its four parts before the first commit; branch `feat/850-014-agent-trace-content`; `Closes #850` | ok |
| Spec before code: spec 014 US9 names #850, plan.md has its section | ok |
| Test first | ok for the feature (13 and 6 failures before the code). The review's fixes were written with their tests in one step, not test first; the reviewer had already reproduced each failure |
| One declaration per setting, checked before work | ok: `DENTAL_TELEMETRY_CONTENT`, read by `telemetry.content_level()`, a wrong value stops the forwarder before any file is read |
| Settings change by pull request, environments named | ok: `dev` only, the forward workflow's `content` input, `full` by default |
| Decision in an ADR | ok: ADR 0010, indexed |
| Dental-record paths send no text | ok: `annotate()`, `@traced`, `forward_spans()` never read the setting; a test holds it, and another fails if anything but the forwarder calls `content_span` |
| Names follow "SQL and data names" | ok: `_text`, `_name`, `_num`, `_count`, `_seconds`, `_id`, `is_` |
| Changes a rule in `AGENTS.md` | yes: the owner asked for the exception and said "merge" on November 16 |

## Findings and what was done

**Blocking, fixed.**

- **B1. A double-quoted secret inside a tool call's arguments, or inside an output written as JSON, was sent as it
  was.** `step_attrs` wrote arguments with `json.dumps`, so the quote before the secret became `\"` and the
  quoted-value rule did not match. Fixed twice over: `_text` now scrubs JSON leaf by leaf before writing it
  (`telemetry.scrub_value`), and every quote rule reads a quote as written or as JSON escapes it.
  `test_a_secret_inside_a_tool_call_or_a_json_output_is_redacted` runs it through `main()`.

**Should fix, fixed.**

- **S1, S2. 61 of 78 realistic inputs leaked** (unquoted `NAME=value`, `printenv` lines, YAML, `--password`,
  credentials in URLs, private keys, web tokens, `Authorization: Basic`, eleven vendors' token shapes, the names
  `key`, `private_key`, `passphrase`, `pwd`, `credentials`, `auth`). `scrub` was rewritten around those cases:
  0 of the reviewer's 78 leak now, and 54 of them are parametrized tests.
- **S3. Ordinary code was redacted** (`"token_type": "bearer"`, `tokenUrl="/token"`, `task-refactor-…` read as an
  `sk-` key, prose after "Bearer"). A value that reads as ordinary is now left: 24 of the reviewer's 25 lines are
  unchanged, and 28 lines are tests. The one still changed, `token: "OAuth2Token"`, is recorded in a test.
- **S4. One odd file aborted the forwarding part-way.** Each task is now read inside its own guard; a bad one is
  named with the kind of error and the rest is sent.
- **S5. Text in a numeric field reached the run span's status and the public Actions log** through the exception's
  message. Numbers go through `_number`, which gives 0 for anything else, and the guard prints the kind of error,
  never its message.
- **S6. The kernel's own spans had no `forward_id`.** `forward_spans` takes the forwarding's labels as `extra`.
- **S7. "A secret is never logged, whatever the setting" overstated the code.** `AGENTS.md`, the ADR and
  `docs/telemetry.md` now say what the scrubber knows and list what it cannot.
- **S8. Nine regressions no test caught.** Tests added for each: the option against the setting both ways, the
  task's times, each connection-string key, each GitHub prefix, `secret` and `passwd` as names, `Bearer` in any
  case, the environment-name rule, the per-task flush, a malformed trace.

**Nits.**

| Nit | Done |
|---|---|
| N1. `main()` left the setting changed in the process | fixed: put back in a `finally`, tested |
| N2. A failed per-task flush still printed `telemetry export: ok` | fixed, tested |
| N3. `scrub` went quadratic on a repeated telling word (40 s for 100,000 characters) | fixed: every name tail is bounded; seven long inputs are held to 2 s each and take under 0.2 s |
| N4. The environment-value pass redacted ordinary values and missed JSON-escaped ones | fixed: the name must hold the word between underscores, the value be 12 characters or more, and the JSON-escaped form is replaced too. A base64 or URL-encoded copy still passes, and the docs say so |
| N5. Without `started_unix` a task was stamped at forwarding time | fixed: its first and last step's times |
| N6, N7. The queries missed steps with several tools and doubled rows of a run forwarded twice | fixed in `docs/telemetry.md`: `has`, and a `latest` forwarding |
| N8. A task that failed in the kernel read `agent_error_code: none` | fixed, tested |
| N9. "Only through `content_span`" was a convention | now a test |
| N10. Uncited figures | the 8,192 and 64 KB limits cite Azure Monitor's service limits (read November 16); the size figure is restated as what one forwarding to a file sent, and says the traces are not in the repository |

**Left open, and said in the docs.**

- **A scrubber of shapes is not a proof.** It lets through a secret in an unknown shape under a name that doesn't
  tell, a password that is one plain word, an unquoted YAML value with no digit, and a secret encoded again.
- **Old runs.** Whether Application Insights keeps the original time of a step forwarded days after its run was not
  checked; it needs data sent. The first forwardings after the merge are of runs a few hours old.
- **The lint findings** in `telemetry.py` (`I001`, `S110`) are on `main` already and CI does not run the linter.

## Checks

- Locally on `511af35`: the telemetry, docs, wording, organization-name, bench-order and PR-convention tests, 272
  passed, 1 skipped. The whole suite passed on the first commit (2,865 passed, 37 skipped, 12 min 54 s).
- The reviewer's probes, rerun after the fix: 0 of 78 inputs leak; 1 of 25 ordinary lines changed; the forwarder
  probes behave as the findings asked.
- A real run forwarded to a file (21 tasks, nothing sent): 640 steps, 8 parts, the longest attribute 8,000
  characters, no span without `forward_id`, 20 redactions, all the password of an example URL in a task about URL
  highlighting.
- CI on the head commit: read before merging. The `bundle` job failed once on `8f4142b` while downloading the
  Databricks CLI (`curl: (22) ... 403`), before any of this change ran.

## Verdict

Approve after the fixes. It starts no run and spends nothing. Once merged, a forwarded development run sends its
steps to the dev Application Insights resource; the owner asked for that and said "merge".
