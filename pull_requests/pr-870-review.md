# PR 870 review: the README, the study page and the PerioBench deck explain the three tests

Closes #868. Range: `origin/feat/864-042-model-drivers-uc..feat/868-042-three-tests` (stacked on #869). Files:
`README.md` (the PerioBench section's table of the three tests), `docs/edr/README.md` ("The three tests"),
`docs/edr/slides/05-tests.html` (new) with slides 05-12 renumbered to 06-13, `docs/edr/deck.html` and
`docs/edr/full_text_and_notes.md` (rebuilt), `specs/042-model-drivers/` (US5, T020-T023).

Reviewed by the agent session that wrote it. Read it knowing that.

## Scans

- **Secrets:** none. Docs only.
- **Real data:** none. Every number is on synthetic data, and the pages say so.
- **Claims:** every headline number is copied from a committed result: phenotyping 203 of 223
  (`docs/model_drivers.md`); de-identification leaks 115 of 2,714 and damages 41 of 2,462 dental decoys
  (`docs/deidentification.md`); tooth loss AUC 0.89 and 0.90 on 469 held-out teeth (`docs/tooth_loss.md`, after
  #631, reproduced by #867's run).

## Findings (verified)

1. **The landing README stays at 80 lines** (`test_decks.py`). The table replaced prose rather than adding to it.
2. **"How BERT is used" is answered per test.** Tooth loss uses no BERT and no text, and the table says so. This was
   the question that started this story.
3. **The deck's footers and slide count follow the renumbering.** The website repo's copy may still say "12 slides"
   until the deck is copied there on merge.
4. **Two links point at pages from #874 (`docs/deid_drivers.md`) and #876 (`docs/tooth_loss_drivers.md`).** They
   resolve only once those merge, so this PR merges after both.

## Checks

- `pytest tests/test_decks.py tests/test_readme_results.py tests/test_model_drivers.py tests/test_wording.py`:
  103 passed.
- `python docs/build_decks.py edr`: rebuilt; slide 5 rendered standalone with the deck's CSS and fits.

## Verdict

Approve, merging after #874 and the tooth-loss PR. Docs and the deck only; nothing changes in any environment.
