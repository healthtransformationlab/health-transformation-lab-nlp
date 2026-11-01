---
pr: 261
branch: docs/237-openai-40m-check
title: "Record OpenAI's 40 million as checked, via the reporting of its January 2026 data"
author: jcbowyer
reviewed_at: 2026-10-29
reviewer: coordinator review against the rubric's deck step (one register entry)
verdict: approve
---

# PR Review: Record OpenAI's 40 million as checked

## Summary
The last `checked: null` entry in `docs/claims.yaml`. openai.com refuses automated requests, so the figure was read
through the reporting of OpenAI's January 2026 data: Axios (an exclusive, 2026-01-05, headline corrected to say the
figure is global), Medical Economics (2026-01-07), Gizmodo and The Decoder all give more than 40 million people a day,
worldwide, and 1.6 to 1.9 million health-insurance messages a week, matching the slide and its notes. A summary from
another AI model the owner pasted gave "1.5 to 2 million" for the insurance figure; the reporting confirms the deck's
1.6 to 1.9 million, so nothing on the slide changes. The entry names the route and says the data is OpenAI's own,
not independently verified. Approve.

## Checks
- `cd python && python -m pytest -q tests`: run before commit (see the PR).
- No slide text changes; no secrets, PHI or organization claims.
