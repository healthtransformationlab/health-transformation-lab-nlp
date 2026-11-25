# ADR 0014: AccessBench covers oral, medical and mental health access, oral first

Date: 2026-11-25 · Status: accepted · Issue: #937

## Context

AccessBench asks whether an AI answer helps someone actually get care, not only whether its facts are right. Its 15
questions so far are all oral health: periodontal screening coverage and appeals, and access questions with planted
fake personal details. The barriers it tests (coverage, cost, appeals, travel, accommodations, low-cost programs) are
the same in medical and mental health care, and people ask AI about all three. The owner decided on 2026-11-25 that
AccessBench should cover all three, starting with oral health, and that knowing discounts and vouchers belongs in each.

## Decision

- AccessBench has three sections, `oral`, `medical` and `mental`, and every question names one (`section_code`).
- **Oral health is the first iteration.** It is built, reviewed and scored first. Medical and mental start as seed
  questions and become scored sets only after the oral review process (docs/access_review_protocol.md) has run once.
- **Discounts, vouchers and low-cost programs are a question set in every section**, starting with dental (spec 044 US2).
- Results are reported per section and never pooled into one AccessBench score.
- A fourth section needs a new decision record.

## Consequences

- Easier: one benchmark, one scoring method and one review process for all access questions; the medical and mental
  sets reuse the batch job, the gold tables and the review page.
- Harder: medical and mental questions need reviewers who know those systems (Medicare and Medicaid medical benefits,
  hospital financial assistance, mental health parity, crisis lines), which the owner check alone can't cover.
  Mental-health questions also need a safety rule for crisis situations before any is scored.
- AccessBench stays exploratory. Its README says which section is built and which are planned.

## Revisit when

- The oral section's review and first published scores are done: decide the order of medical and mental.
- OralHealthBench's scope overlaps a medical question: decide which benchmark owns it.
- An independent reviewer for medical or mental health is found, or isn't within six months.
