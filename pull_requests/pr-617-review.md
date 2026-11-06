# PR #617 review: set the synthetic extract's tooth loss from published rates (spec 037)

Closes #610-#614. Reviewed against `.claude/review-rubric.md` and AGENTS.md.

## Verdict
Nothing blocking. It changes a dataset (the synthetic extract), and spec 037 came first.

## Checks
- **Synthetic only, no employer data.** The targets are published or public: Vehkalahti 2023 (reference 87), Suzuki
  2022 (reference 63), NHANES 2009-2014 public files (aggregates only, survey-weighted) and BRFSS 2022 through CDC's
  Chronic Disease Indicators (reference 88). No figure from any organization's own records is used.
- **Test first.** Each user story has a test that failed before its code: the rate, the share by age, the visit
  window, the NHANES counts and the state scaling. There are new unit tests for `missing_teeth_by_age` and the
  negative binomial shape.
- **Labelled simulated or synthetic.** Every number in the docs says SYNTHETIC. The data card marks the parameters
  set by measurement as placeholders and explains how each was set.
- **Honest results.** The missing-at-entry AUC drop (from about 0.93 to 0.60-0.67) is reported, with its cause, in
  `docs/tooth_loss.md`, on the study page and in the analysis plan's change log. It isn't hidden behind the
  held-out gain.
- **Relaxed tests, each with its reason in the test.**
  - 029 US7's 25-34 periodontal share is now held below 0.25, because the spec 006 mouth is out of scope.
  - The NHANES mean at 25-34 is within 30%.
  - The other-reason vs CAL check is now "not positive". A maximum over fewer charted sites runs lower, which
    is a measurement effect, not selection by CAL.
  - None of these weakens what the test guards against.
- **Python/R parity.** No label, scoring or reliability rule changed. The spec 029 tooth-status parity section
  passes on the regenerated inputs (0 differences).
- **Wording.** "Lost to periodontitis" and "recorded diagnosis" are used, never "diagnose". The bench order isn't
  touched.
- **Generated files.** `docs/site/data-quality.json`, the silver ERD and the parity inputs were regenerated with
  their scripts. `docs/edr/README.md` was edited only outside its generated block.

## Not blocking
- The extraction rate is flat by age. Reference 87's per-age figures would shape it once they're readable.
- The BRFSS state figures count teeth removed for decay or gum disease, and NHANES counts every absent tooth.
  This is stated, and BRFSS is used only as a ratio.
