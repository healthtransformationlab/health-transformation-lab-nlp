# PR #606 review: show the tooth-level model on the study page

Closes #605. Reviewed against `.claude/review-rubric.md` and AGENTS.md.

## Verdict
Nothing blocking.

## Checks
- **Numbers:** they match `docs/tooth_loss.md` "Results (SYNTHETIC)": 6,000 patients and 88 held-out extractions,
  14 of them periodontal. AUC is 0.89–0.92. At 0.5, sensitivity is 0.57–0.71 and specificity 0.95–0.96.
- **Labelled synthetic:** every number is labelled SYNTHETIC, framed as agreement with the answer key, and makes no
  claim about any practice.
- **Wording:** the page says "lost to gum disease" and "recorded diagnosis item". It never says the model diagnoses.
  The wording tests pass.
- **Generated block:** untouched. The drill-down table and the sections around it are hand-written.
- **Links:** all three targets exist.
