---
pr: 873
branch: chore/872-gitignore-claude-local-settings
title: "000 CHORE48: ignore .claude/settings.local.json and add a shared template for local permission rules"
author: jcbowyer
reviewed_at: 2026-11-17
reviewer: coordinator review (the diff is 4 small files; no separate reviewer subagent), findings verified
verdict: approve
---

# PR Review: 000 CHORE48: ignore .claude/settings.local.json and add a shared template for local permission rules

## Summary
The PR makes the repo's own `.gitignore` ignore `.claude/settings.local.json`, adds a committed template of
machine-local permission rules (`.claude/settings.local.example.json`), and a `CLAUDE.md` section saying where such
rules go and to copy the template once per machine. The first version of the template held a prefix rule
(`... -Atc "select pg_size_pretty:*)`) that also matched any SQL after that prefix, including a write or a `drop`,
against a production database. That was a blocking finding and is fixed on the branch: the rule now names the exact
command, and a test rejects wildcard rules in the template. With that fix the verdict is approve. Because the PR
changes `CLAUDE.md` (the agents' rules), it waits for the owner's "merge" (AGENTS.md, rule 6).

## Scope of Change
- Files changed: 4 (+about 70 / -0)
- Areas touched: repo configuration (`.gitignore`, `.claude/`), docs (`CLAUDE.md`), python tests
- Commits:
  - 339a20a Ignore .claude/settings.local.json in the repo's .gitignore
  - 1c64944 Add a committed template for each machine's local permission rules
  - d04471d Pass check=False to the gitignore tests' git calls
  - (this review's commit) Pin the template's rule to one exact command
- Range reviewed: `a9dc17a..HEAD`

## CI Status
| Check | Status |
|---|---|
| check (PR conventions) | success on d04471d |
| python | in progress on d04471d at review time |
| python-databricks-runtime | queued on d04471d at review time |

## Secrets, PHI and Claims Scan
- Secrets: clean. The template names the variable `$NEON_DATABASE_URL`, never its value; no tokens, passwords or
  credentialed URLs in the diff.
- PHI / real data: clean. No data files touched.
- Organization claims: clean.

## Strengths
- The gitignore test turns off the user's global gitignore (`core.excludesFile=/dev/null`) and uses `--no-index`, so
  it checks the repo's own rule and would fail on a machine where only a global ignore hides the file.
- Production rules stay out of the shared `.claude/settings.json`, while the template keeps each machine's rules the
  same and reviewed.

## Findings
### 🔴 Blocking (Critical)
- **Fixed on the branch.** `.claude/settings.local.example.json`: the rule
  `Bash(psql "$NEON_DATABASE_URL" -Atc "select pg_size_pretty:*)` is a prefix match on free SQL text. psql runs
  every statement in a `-c` string ("If the command string contains multiple SQL commands, they are processed in a
  single transaction", psql documentation, option `-c`), so
  `psql "$NEON_DATABASE_URL" -Atc "select pg_size_pretty(1); drop table x"` matches the rule and would run against
  production without a prompt; so would a trailing `-f file.sql`. Verified by reading the rule against
  `psql --help` (`-c` and `-f` both run and exit in order). Fix: the rule is now the exact command
  `psql "$NEON_DATABASE_URL" -Atc "select pg_size_pretty(pg_database_size(current_database()))"`;
  `test_template_rules_name_exact_commands_without_wildcards` fails on any `:*` rule in the template; `CLAUDE.md`
  says why.

### 🟡 Should fix (Important, non-blocking)
None.

### 🔵 Nits / suggestions (Minor)
- A read-only database role in `NEON_DATABASE_URL` for agent sessions would be a second guard behind the exact rule.
  Out of scope here.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | ✅ | Variable name only |
| Synthetic only, no PHI | ✅ | No data touched |
| No organization claims; vendors cited | ✅ | |
| Test first | ✅ | Each test failed before its change |
| Python and R in parity | n/a | No labels, scoring, reliability or cost-effectiveness |
| Simulated is labelled simulated | n/a | |
| Seeds fixed | n/a | |
| Paths | ✅ | `REPO_ROOT` from `health_transformation_lab_nlp.paths` |
| Spec for big changes | n/a | Chore; issue #872 has its four parts and a dated change line |
| Prices | n/a | |
| Deck figures | n/a | |
| Commits | ✅ | Imperative subjects, bodies say why, co-author trailers |
| Docs | ✅ | `CLAUDE.md` section added |
| Configuration | ✅ | No new setting; `NEON_DATABASE_URL` is read only by a local rule. No environment changes |
| Secrets register | n/a | No credential made or newly used by a job |
| Idempotent writes | n/a | |
| Alerts | n/a | |

## Test Coverage
`python/tests/test_gitignore.py`: the repo's `.gitignore` ignores the local file; the template is committed and holds
the exact rule; no template rule is a wildcard; `CLAUDE.md` gives the copy command. Run locally: those tests with
`test_wording.py`, `test_no_org_references.py` and `test_bench_order.py` pass; `ruff check` clean. The full
`pytest -q tests` run was in progress locally at review time with no failures; CI's `python` check covers it.

## Verdict
Approve, with the blocking finding fixed on the branch. Merge waits for the owner's "merge", since the PR changes
`CLAUDE.md`, and for CI to be green on the latest commit.
