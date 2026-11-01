---
pr: 239
branch: docs/237-recheck-deck-citations
title: "Re-check the decks' cited figures against their sources"
author: jcbowyer
reviewed_at: 2026-10-28
reviewer: coordinator review against the rubric's deck step (a two-string change and two register entries)
verdict: approve
---

# PR Review: Re-check the decks' cited figures against their sources

## Summary
The rubric's deck step (5), applied to the EDR problem slide: Eke et al. 2018 (PMID 29957185, read from PubMed on
2026-10-28) reports "42% of dentate US adults 30 years or older had periodontitis, with 7.8% having severe
periodontitis". The slide said "US adults 30+", a wider population than the source. It now says "with teeth" on the
slide and in the notes, and `docs/claims.yaml` records the quote and `checked: 2026-10-28`. Approve.

## Findings
None. The figures match the source exactly; only the population was narrowed to the source's.

## Checks
- `cd python && python -m pytest -q tests`: 962 passed, 15 skipped; decks rebuilt and match the builder.
- Scans: no secrets, PHI or organization claims (a published paper, cited).
- Not checkable from this session (hosts blocked): GlobalDentBench (arxiv.org), OpenAI's 40 million (openai.com),
  REDCap (projectredcap.org); they stay `checked: null` under #237.

## Update: the other sources, once their hosts were allowed (2026-10-28)
Re-checked against each source and recorded in `docs/claims.yaml` with `checked: 2026-10-28`:
- **GlobalDentBench** (arXiv 2605.24636v2), from the full paper:
  - Exact: 81.34% (multiple-choice), 22.34% (case-based), 12 models, 8,978 questions, 88 countries, 31.01% unsafe,
    4.51% S2 ("irreversible or life-threatening harm"), 14.15% (systemic health, pharmacology and safety) and 8.93%
    (anesthesia and emergencies), and "Gemini-3.1-Pro-Preview achieved the highest overall proficiency".
  - Wording narrowed to the source: the 81% is on multiple-choice questions "sourced from official qualification
    examinations", not "the dental licensing exam". The 22% is on questions "extracted from peer-reviewed clinical
    case reports", not "real patient cases". The pitch's problem slide and notes now say so.
- **PubHealthBench** (arXiv 2505.06046): "over 8000 questions". Exact.
- **REDCap** (projectredcap.org): "8,502 active partners in 167 countries". The slide's "nearly 8,000 institutions in
  163 countries" was out of date; it now says "over 8,500 institutions in 167 countries".
- **Gemini 3.1 Pro list price** (ai.google.dev, page updated 2026-10-28): $2 / $12 per 1M tokens. Added as tiers. The
  economics slide's frontier rows are now ranges across two vendors: ~$1,100–$5,500 for the note only, ~$260k–$1.2M
  for the whole record. The test recomputes both new tiers.

Not checked: OpenAI's 40 million a day. openai.com answers 403 to automated requests, and getting past a bot check
isn't appropriate, so it stays `checked: null`.

Left for the owner: the pitch cover's hook "It fails the real patient" is a fair summary of 22% on case-report
questions, but it is the strongest wording left on the decks.

Checks after the update: `cd python && python -m pytest -q tests` 964 passed, 15 skipped. Slide 5 rendered in
Chromium: no overflow, footer on one line.
