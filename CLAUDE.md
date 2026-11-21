# CLAUDE.md

@AGENTS.md

The rules above (in `AGENTS.md`) apply to every agent. This file adds Claude Code's own workflow.

## Organization names: never CareQuest

Never reference CareQuest anywhere in this repo: CareQuest Institute for Oral Health, CareQuest Innovation
Partners, their programs, people, data, plans or strategy. That covers code, docs, tests, data, slide decks, commit
messages, issues and pull requests, and disclaimers too: write "any employer or organization" instead. Content that
came from CareQuest work is made generic before it comes in, with nothing that identifies it.

This file is the only place the name may appear, to state this rule. An exception needs this section changed first,
naming the file and why. `python/tests/test_no_org_references.py` fails CI if the name appears in any other tracked
file.

## Workflow: Spec Kit + Superpowers

| Stage | Tool | Output |
|-------|------|--------|
| What and why | `/speckit-specify` (then `/speckit-clarify` if needed) | `specs/NNN-name/spec.md` |
| One issue per user story, then its branch | GitHub issue with its four parts: Problem, Done when, Contract, Read first (AGENTS.md, "What an issue says"); branch `<type>/<issue>-<slug>` (AGENTS.md, "Branches and issues") | issue `#n`, branch `feat/<n>-NNN-slug` |
| How, at feature level | `/speckit-plan`, `/speckit-tasks` (`/speckit-analyze` to cross-check) | `plan.md`, `tasks.md` in the same folder |
| Open design questions | Superpowers `brainstorming` | `docs/superpowers/specs/YYYY-MM-DD-topic-design.md` |
| Session plan | Superpowers `writing-plans`, then `executing-plans` or `subagent-driven-development` | `docs/superpowers/plans/YYYY-MM-DD-topic.md` |
| Each task | Superpowers `test-driven-development` | failing test → code → passing test |
| Before saying done | Superpowers `verification-before-completion` | commands run, output checked |
| Settings, secrets, writes | AGENTS.md "Configuration and secrets", "Failures, retries and reruns"; background in `docs/operations.md` | register updated, settings checked at start, writes idempotent |
| Open a PR | `/create-pr` (checks, opens the PR with `Closes #<issue>`, reviews it) | PR + `pull_requests/pr-<n>-review.md` |
| Before merge | `/pr-review <n>` (Superpowers `requesting-code-review`, rubric in `.claude/review-rubric.md`) | `pull_requests/pr-<n>-review.md` |

## Local permission rules

Rules that reach production (a database, a paid service) never go in the shared `.claude/settings.json`: it applies
to every agent and contributor. They go in each machine's `.claude/settings.local.json`, which git ignores. The
standard set is kept, reviewed, in `.claude/settings.local.example.json`; on a new machine, copy it once:

```
cp .claude/settings.local.example.json .claude/settings.local.json
```

Each rule names one exact command, never a prefix with `:*` after free text: `psql -Atc "select ...:*)"` would also
match `"select ...; drop table x"`, since psql runs every statement it's given. A rule worth having everywhere is added
to the template by pull request, then copied by hand on each machine.

## Setup for Superpowers

`.claude/settings.json` enables Superpowers from the official plugin
marketplace. If Claude Code reports it isn't installed, run once:

```
/plugin install superpowers@claude-plugins-official
```

or from Superpowers' own marketplace:

```
/plugin marketplace add obra/superpowers-marketplace
/plugin install superpowers@superpowers-marketplace
```

Spec Kit's skills are checked in under `.claude/skills/speckit-*`; no install
needed to use them. To refresh them to a newer Spec Kit:
`uvx --from git+https://github.com/github/spec-kit.git specify init --here --force --integration claude`.


## Times

When you tell the owner a time, in chat, in a status cell or in a message, write it in 12-hour form with AM or PM, in
UTC with Central time beside it: "12:02 AM UTC (6:02 PM Central)". The owner asked for this on November 17, 2026
("give all utc times in am pm all chats"). Files, logs, tables, commit messages and code keep ISO 8601 UTC.
