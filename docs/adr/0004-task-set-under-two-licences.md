# ADR 0004: The coding-agent task set is offered under CC BY 4.0 or Apache 2.0

Date: 2026-11-12 · Status: accepted · Issue: #696

## Context

The task set (`health-transformation-lab-coding-agent-tasks` on Kaggle, spec 028) was published under CC BY 4.0,
the licence "Publishing datasets" in `AGENTS.md` gives for our datasets. It was entered in the Gemma 4 Developer
Agent competition's Paper Track, whose rules name another licence for winners: "WINNER LICENSE TYPE Open Source
Apache 2.0", and ask a winner to license "your winning Submission and the source code used to generate the
Submission under an Open Source Initiative-approved license [...] that in no event limits commercial use" (the
competition's rules page, read on November 12, 2026). Input data under an incompatible licence is exempt.

The code is Apache 2.0 in both repositories. CC BY 4.0 allows commercial use, but it is a licence for data and
text and is not one the Open Source Initiative lists, so a reader of the rule could ask whether the dataset meets
it. The paper, as submitted, says "Tasks (CC BY 4.0)".

## Decision

The owner chose on November 12, 2026, from three options (offer both; leave it; switch the listing to Apache 2.0):

- The task rows, graphs, embeddings and the card are offered under CC BY 4.0 or, at the user's choice, under the
  Apache License 2.0. The card says so.
- Kaggle's licence field stays CC BY 4.0. It holds one licence, and the paper names that one.
- Nothing inside the snapshots changes licence: the repository's own files there are MIT, as at those commits,
  and third-party files keep their own (MACCROBAT is CC BY 4.0).
- The other two datasets (`perio-bench-notes`, `perio-bench-results`) are not part of this decision.

## Consequences

- A user who needs an open-source software licence has one, and a user who wants the usual data licence keeps it.
- Two licences to state wherever the task set's licence is stated. The card is the one place that must say both;
  a test fails if it stops.
- Attribution is asked under either licence: CC BY 4.0 by its terms, Apache 2.0 through its notice requirements.

## Revisit when

- The competition's sponsor asks for a different form of the grant.
- The task set is published anywhere whose licence field takes one value that is not CC BY 4.0.
- "Publishing datasets" in `AGENTS.md` changes its default licence.
