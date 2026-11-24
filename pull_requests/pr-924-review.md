# PR 924 review: AccessBench is the README's third top-level benchmark, with its own deck and PowerPoint

Closes #923. Range: `origin/main..docs/923-043-access-bench-deck`. Files: `README.md`, `docs/build_decks.py` (deck
`access`), `docs/build_pptx.py` (new), `docs/access/` (new: 7 slides, `deck.html`, `full_text_and_notes.md`,
`access_bench.pptx`), `python/tests/test_pptx.py` (new), `python/pyproject.toml` (`python-pptx` in `dev`).

Reviewed by the agent session that wrote it. Read it knowing that.

## Scans

- **Secrets:** none.
- **Real data:** none. The slides describe the committed synthetic items. The privacy slide names the planted
  details only by kind; no planted value is quoted.
- **Claims:** no answer score appears, because no live run exists, and `test_pptx.py` keeps percentages off the deck.
  Every program fact on a slide comes from an item's own `evidence_source`: CMS on optional adult Medicaid dental,
  42 CFR 411.15(i), and the ADA/IHS D0180 coding guidance. The 2030 goal is labelled the owner's own stretch goal, as
  in the seeds file.

## Findings (verified)

1. **The scoring slide first said "one red flag fails the answer".** That is not in the code:
   `access_keypoint_judge.score_verdict` returns the share of key points covered, plus the red flags hit and a harm
   grade. Fixed to say the score is the share covered, and that the access gate (from the AccessBench README) passes
   only with key points met and no red flag.
2. **The landing README's 80-line limit** (`test_decks.py`) held only after tightening. The "How the two paths
   connect" section is now a clause in the OralHealthBench paragraph ("built from PerioBench's synthetic OMOP
   patients") and in the intro line ("tested the same way"). Nothing else was removed.
3. **"The lab" on a slide** failed `test_slides_name_the_benchmark_not_the_lab`. Reworded.
4. **The PowerPoint layout** was checked by rendering it with LibreOffice. Long headings wrapped into the body at
   56 px and slide 3's bullets ran into the band; the heading and bullet sizes were reduced. The HTML slides were
   rendered in Chromium at 1920 x 1080 with no overflow.
5. **Not published:** `SITE_PAGES` and `copy-decks-to-site.yml` are unchanged, and a test pins that. Merging doesn't
   touch the website, so it doesn't wait for the owner under rule 6.

## Compliance

- Issue #923 has its four parts, written before the first commit. Branch `docs/923-043-access-bench-deck`;
  `Closes #923`.
- Test first: `test_pptx.py` failed (no `build_pptx.py`) before the code.
- Benchmark order: PerioBench, OralHealthBench, AccessBench everywhere (`test_bench_order.py`).

## Checks

- `pytest tests/test_pptx.py tests/test_decks.py tests/test_wording.py tests/test_bench_order.py
  tests/test_no_org_references.py tests/test_copy_decks_to_site.py`: 84 passed.
- Every test that reads `README.md`: 493 passed.

## Verdict

Approve. Docs, a deck and a dev dependency. No environment changes.
