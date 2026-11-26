# Feature Specification: AccessBench sections (oral, medical, mental), oral first, with discount and voucher questions

**Feature Branch**: `feat/<issue>-044-...`, one per user story · **Created**: 2026-11-25 · **Status**: draft · **Epic**: #937

**Input**: The owner, 2026-11-25: "knowledge of discounts or voucher in mental and dental space — we should have oral and
medical sections of access bench with the primary focus on the first iteration as oral health but with a long term plan
to do full health oral, medical, mental". Decision record: [ADR 0014](../../docs/adr/0014-accessbench-oral-medical-mental-sections.md).

> Personal learning project, not affiliated. Every question is synthetic, written from public questions and official
> sources. We score whether an answer helps someone get care; we do not diagnose anyone.

## Why

AccessBench asks whether an AI answer helps someone actually get care. Getting care looks alike across oral, medical and
mental health: coverage, cost, appeals, travel, accommodations and, everywhere, knowing the discounts, vouchers and
low-cost programs that exist. The 15 questions so far are all oral health and none names its section, so a later
medical or mental set would mix into the oral scores. Cost is the barrier people name most, and no question yet tests
whether a model knows the low-cost routes or warns about traps such as deferred-interest medical credit cards.

## User stories

### US1 - Every question names its section, and results report by section (P1) #938

- Each item has `section_code` in (`oral`, `medical`, `mental`); the current 15 are `oral`.
- The batch writes it to `dim_access_question.section_code`; the READMEs say oral is built first and the others are
  planned.
- **Independent test:** an item without a valid section is refused; a simulated batch writes the section; the module
  says `oral` is first.

### US2 - The oral section gets a dental discount and voucher question set (P1) #939

- About six questions: dental school clinics, health-center sliding fees, free dental events, donated care for elderly
  or disabled people, discount plans (not insurance) and medical credit cards. Every fact and resource comes from an
  official or primary source opened when the item was written, with the date.
- The batch can score them (`fixture=discount_voucher`), and the owner's review covers them.
- **Independent test:** the file loads and validates; the batch scores it in simulated mode.

### US4 - The oral section gets a veterans' dental question set (P1) #979

- The owner, 2026-11-26: "We should add a separate oral health section targeted at veterans."
- About eight questions on VA dental care: the eligibility classes in 38 CFR 17.161 (a 100% service-connected rating or
  unemployability, former POWs, one-time care for the recently discharged who apply in time, homeless-program care,
  care tied to a service-connected condition, Veteran Readiness and Employment), VADIP for veterans enrolled in VA care,
  FEDVIP dental for military retirees, community care and travel pay.
- Veterans are a group of people, not a fourth health area: a question set in `oral`, reported on its own (ADR 0014
  unchanged). The batch scores it with `fixture=veteran_dental`.
- Drafted while the VA and eCFR pages were unreachable, so every item says its source is unopened
  (`source_verified_date` null) and no score of the set is published until the pages are checked and the owner has
  reviewed it.
- **Independent test:** the file loads and validates; a bad row is refused; the batch scores it in simulated mode.

### US3 - Medical and mental sections start with discount and voucher seeds (P3, planned) #940

- Seed questions for hospital financial assistance, prescription savings, 988, community mental health centers and
  sliding-scale therapy, each with one official source. No scored items until the oral review process has run once.

## Requirements

- **FR-001** `section_code` is required on every item and is one of three values; no other section without a new
  decision record.
- **FR-002** Every resource in an answer key, and every link in `evidence_urls`, is `https://` and was opened when the
  item was written; the check date is in `evidence_source`.
- **FR-003** Discount and voucher questions reward the right next step and a fallback, not a list of every program; the
  riskiest confident error is a red flag.
- **FR-004** Questions whose rules or prices can change are `knowledge_cutoff_sensitive: true`.
- **FR-005** Results are reported per section; scores from different sections are never pooled into one AccessBench
  number.

## Success criteria

- A simulated batch over `fixture=all` writes every question with its section.
- The README shows the oral section as built and the medical and mental sections as planned.
- The six discount and voucher questions pass the owner's review before any score of theirs is published.

## Out of scope

- Scored medical or mental questions (US3 only seeds them).
- Real patient data, ever.
