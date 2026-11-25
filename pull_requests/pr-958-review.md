# PR 958 review: AccessBench answer keys v2 (045 US5, #957)

Reviewed against `.claude/review-rubric.md` and AGENTS.md.

## Verdict

Nothing blocking in the code. **This changes the benchmark's answer keys, so it waits for the owner's approval**
(the owner reviews the keys; spec 043 US7). Merge on the owner's "merge".

## Checked

- **Spec and issue:** spec 045 US5 names #957; plan and tasks updated.
- **Every change traced:** `docs/access_bench_key_v2.md` lists each item's change and which reviewers asked for it.
- **No claim beyond the evidence:** new sources are named but not opened (the session's network couldn't reach
  ecfr.gov, medicaid.gov, va.gov, medicare.gov or ada.gov); every changed item keeps `source_verified_date` null, and
  no link or phone number was added.
- **Validators:** every item has 3–4 positive points and 2–3 red flags; the new contrastive item validates.
- **Prompts:** a new test fails if any prompt contains "simulated", "MRN" or "under-21 pathway".
- **Privacy items:** the MRN was removed from TRV_PHI_001's prompt and planted details; it keeps a gated name and
  street.
- **Tests:** tests that pinned 10 screening items now read the count from the file.

## For the owner

- OH-08 (SCR_010) is removed here, as three of five reviewers and Claude recommend; say if you'd rather keep it.
- After merging, one live run on the open models grades the new keys; no run is started by this PR.
