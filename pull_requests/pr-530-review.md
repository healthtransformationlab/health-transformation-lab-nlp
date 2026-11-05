---
pr: 530
branch: docs/527-audience-ask-impact
title: "000 DOCS6: say who each deck is for, what we ask them to do, and what changes"
author: claude (agent session)
reviewed_at: 2026-11-04
reviewer: read-only reviewer subagent + coordinator verification
verdict: approve-with-nits
---

# PR Review: 000 DOCS6: say who each deck is for, what we ask them to do, and what changes

## Summary
Adds a slide 2 to each deck: who it's for, what we ask them to do, and what changes. OralHealthBench's version
names the AI companies as the audience that has to act. PerioBench's version names the dental data teams,
researchers, gum specialists and AI builders. Later slides are renumbered, the decks rebuilt, the new `180` figure
registered, and the slide counts and slide references updated. The review found one Important wording overclaim and
three Minor items, all fixed on the branch. The decks rebuild to the committed files and the deck, claims, wording,
benchmark-order and no-org-name tests pass. Verdict: approve-with-nits. Merging copies the decks to the website, so
it waits for the owner's "merge" (AGENTS.md rule 6).

## Scope of Change
- Files changed: about 25 (two new slides, renamed slides, rebuilt decks, claims.yaml, two READMEs, spec 019, one comment)
- Areas touched: docs / specs / python (comment only)
- Commits: 3ca63ea 000 DOCS5: say who each deck is for, what we ask them to do, and what changes; 676dada merge main; plus the review-fix commit
- Range reviewed: `629d5a2..HEAD`

## CI Status
| Check | Status |
|---|---|
| python, postgres, r-parity, bundle, pr-conventions | pending on the latest push at the time of writing |

## Secrets, PHI and Claims Scan
- Secrets: clean.
- PHI / real data: clean. No real notes or names. Nothing from the conversation that prompted the change is in the repo.
- Organization claims: clean. The AI companies and benchmark owners are named only as audiences, and both footers
  say no one or no partner has been contacted.

## Strengths
- One table answers the three questions readers asked, with one concrete example.
- Footers match file positions in both decks, and notes that point to the "previous" or "next" slide still point to the right one.

## Findings
### 🔴 Blocking (Critical)
None.
### 🟡 Should fix (Important, non-blocking)
- `docs/pitch/slides/02-audience.html`: "Every model tested there is graded on them" stated as fact something that
  depends on the benchmark owners agreeing. The notes stated the companies' "duty" as fact. **Fixed:** "If they add
  them, ...", and "In my view they have a duty ...". Similarly `docs/edr/slides/02-audience.html`: "studied at
  scale" is now "could be studied at scale".
### 🔵 Nits / suggestions (Minor)
- `specs/019-grader-dashboards/spec.md:13,80`: the slide numbers were out of date after renumbering. **Fixed** (12, 13, 14).
- `docs/edr/slides/02-audience.html` footer: "no one named here" on a slide that names no one. **Fixed:** "no partner has been contacted".
- Website PR healthtransformationlab/healthtransformationlab.github.io#23 says "12 slides". Merge it with or after this PR.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets / PHI / org claims | ✅ | scans clean |
| Words (no diagnose wording) | ✅ | `test_wording.py` passes |
| Benchmark order | ✅ | `test_bench_order.py` passes |
| Deck figures | ✅ | `180` registered as a proposal; matches the ask slide |
| Spec for big changes | n/a | docs only; no dataset, metric or label change |
| Python and R parity | n/a | nothing scored changes |
| Commits | ✅ | imperative, body says why, co-author trailer |

## Test Coverage
- Full suite run locally: `python -m pytest -q -n auto tests`, 1949 passed and 32 skipped.
- After the fixes: the deck, claims, wording, benchmark-order and no-org-name tests, 132 passed.
- Both new slides were rendered at 1920×1080 and checked by eye.

## Verdict
approve-with-nits. All findings are fixed. Merge once CI is green and the owner says "merge", because merging publishes to the website.
