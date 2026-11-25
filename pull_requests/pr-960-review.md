# PR 960 review: AccessBench deck leads with the problem (044 DOCS1, #959)

Reviewed against `.claude/review-rubric.md` and AGENTS.md.

## Verdict

Nothing blocking. **It publishes the deck to the website on merge, so it waits for the owner's "merge".**

## Checked

- **Every figure sourced:** `test_deck_claims` passes. Cited figures carry source and checked date:
  - OpenAI's 40 million a day and 1.6 to 1.9 million insurance messages a week, already cited in the pitch deck;
  - JAMA Netw Open 2026, 10.3% daily AI use, PMID 41563755, abstract read today;
  - Dent Traumatol 2026 meta-analysis, 65%–79% pooled accuracy, PMID 42581485, abstract read today;
  - GlobalDentBench's 1 in 3, scoped to "rated unsafe by the study's AI judge" on case questions.
- **Measured figures:** these come from run 608662392694095, summarised in `data/access_bench/runs/run_608662392694095.md` from the gold table. The deck labels them preliminary (one AI judge).
- **No overclaiming:**
  - OpenAI's figures are labelled as OpenAI's own.
  - The survey is described as a nonprobability internet panel in the notes.
  - The deck says ChatGPT, Claude and Gemini are not in this run.
  - The disclaimer now says scores are preliminary.
- **Wording, org names and benchmark order:** tests pass.
- **Visual check:** each slide was rendered at 1920×1080 and nothing overflows.

## Not blocking

- The findings cover four open models; the headline comparison the owner wants (ChatGPT, Claude, Gemini) needs the next step.
