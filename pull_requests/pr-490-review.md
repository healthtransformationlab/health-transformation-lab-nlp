---
pr: 490
branch: feat/355-028-embeddings-wheels
title: "028 US4: node embeddings with EmbeddingGemma and the Python 3.13 sandbox wheels (T010)"
author: jcbowyer
reviewed_at: 2026-11-03
reviewer: superpowers requesting-code-review subagent + coordinator verification
verdict: approve-with-nits
---

# PR Review: 028 US4: node embeddings with EmbeddingGemma and the Python 3.13 sandbox wheels (T010)

## Summary
The PR finishes spec 028 US4 by adding the last two parts of the competition's dataset layout: per-node
embeddings for each task's code graph, and the wheels for the Python 3.13 sandbox. `task_graph.embed_graph` and
`save_embeddings` write one `.npz` per task, with one 256-float32 unit vector per node keyed by node id. The
vectors come from `google/embeddinggemma-300m` at a pinned revision: cut from 768 dims to 256, then renormalised,
with each distinct node text encoded once. `wheel_requirements` and `wheel_download_command` download binary
wheels for 3.13. A real build ran: 115 `.npz` files and 23 wheels, all git-ignored, with the committed task files
unchanged. The first review round found two should-fix items: the token was checked after the expensive work, and
the secrets register didn't name the token's new use. Both are fixed in `2cb0a2f` and re-verified, along with
four nits. What remains are nits, so the verdict is approve-with-nits.

## Scope of Change
- Files changed: 7 (+208 / -8), no generated data committed
- Areas touched: python, docs, specs, ops
- Commits:
  - 53b5721 028 US4: node embeddings with EmbeddingGemma and the Python 3.13 sandbox wheels (T010)
  - 9cf2ebc Merge remote-tracking branch 'origin/main' into feat/355-028-embeddings-wheels
  - 2cb0a2f 028 US4: check the embedding token before any work, and record its new use (PR #490 review)
- Range reviewed: `5e4b45d..2cb0a2f`

## CI Status
| Check | Status |
|---|---|
| python, postgres, r-parity, bundle, pr-conventions | pending: no check runs had started on `2cb0a2f` when this was written |

## Secrets, PHI and Claims Scan
- **Secrets:** clean. No token values anywhere; the register names where `HF_TOKEN` lives, never its value.
- **PHI / real data:** clean. The embeddings are vectors of this repo's own source code, and no data is committed.
- **Organization claims:** clean. EmbeddingGemma is cited by paper (arXiv 2509.20354) and the Gemma terms link.
  Parity with the competition's own embedding model is stated as unverified.

## Strengths
- Encoding takes an injected `encode` function, so the tests run without the model. The truncation test would
  catch normalising before the cut, because column 300 holds 99.
- The text cache across graphs is effective: 50,064 nodes needed only 809 distinct encodes.
- The model revision is pinned, and the model's document prompt (`encode_document`) is used.
- Renormalising after the 256-dim cut is the right order. The reviewer checked that sentence-transformers' own
  `truncate_dim=256` leaves vectors with norm about 0.65.
- `@traced` is on every new public function, and their spans carry no text.
- The output format is checked against `competition_check.embedding_summary` and `OUR_VECTOR` through a
  round-trip test.

## Findings
### 🔴 Blocking (Critical)
None.

### 🟡 Should fix (Important, non-blocking)
Both are fixed in `2cb0a2f`:
1. **The token was checked after the expensive work** (`python/scripts/55_build_tasks.py`).
   - Before: `check_hf_access` ran inside `load_encoder`, after the GitHub crawl, the diffs and `--graphs`.
   - Fixed: `check_settings(embeddings=True)` now checks the `sentence_transformers` import and makes one cheap
     authenticated call before any work.
   - Verified: with `HF_TOKEN=` (empty), `python scripts/55_build_tasks.py --embeddings` fails at once, naming
     `HF_TOKEN`.
2. **The secrets register didn't name the token's new use** (`ops/secrets_register.yaml`).
   - Fixed: the Hugging Face token entry now names EmbeddingGemma and the Gemma terms, `55_build_tasks.py
     --embeddings` in `used_by`, and the new stop in `if_it_expires`.
   - Verified: the YAML loads.

### 🔵 Nits / suggestions (Minor)
Fixed in `2cb0a2f`:
3. `import tomllib` at module level broke the declared `requires-python = ">=3.10"`. It is now imported inside
   `wheel_requirements`.
4. A re-run left `.npz` files behind for tasks that have since been dropped. `write_embeddings` now deletes any
   `.npz` not in the current rows. `write_graphs` has the same older gap; leave it for a follow-up.
5. The dedup test didn't cover two nodes in one graph that share a text. It now has its own test.
7. sentence-transformers wasn't declared anywhere. There is now an `[embeddings]` extra
   (`sentence-transformers>=5`, `torch>=2.2`).

Open:
6. **Silent edge cases in `write_embeddings`.** All-zero vectors and texts truncated at 2048 tokens aren't
   counted. Today there are no zero vectors, and one of the 809 texts is 2049 tokens with the prompt.
   Suggestion: print both counts.
8. **Thin wheel test, and an undocumented glibc floor.** `test_wheel_download_command…` only asserts that
   `--platform` appears, not its values. numpy, duckdb and scipy resolved to manylinux_2_27/2_28 wheels, so the
   sandbox needs glibc 2.27 or newer; that isn't documented. Check it against the competition's image at T011.

## Repo-Rule Compliance
| Rule | Pass? | Notes |
|---|---|---|
| No secrets | Pass | scan clean |
| Synthetic only, no PHI | Pass | vectors of repo code only; nothing committed under `data/` |
| No organization claims; vendors cited | Pass | model paper and terms linked |
| Test first | Pass | 6 new tests failed with the change stashed, then passed; plus one review test |
| Python and R in parity | n/a | no labels, scoring, reliability or cost-effectiveness changed |
| Simulated is labelled simulated | n/a | real build, no dry-run figures |
| Seeds fixed | n/a | no sampling |
| Paths | Pass | `paths.REPO_ROOT` |
| Spec for big changes | Pass | spec 028 T010 ticked, with numbers |
| Prices | n/a | |
| Deck figures | n/a | |
| Commits | Pass | imperative subjects, bodies say why, co-author trailer |
| Docs | Pass | `docs/model_inventory.md` lists the model |
| Configuration | Pass | no new settings; existing `HF_TOKEN` checked before work |
| Secrets register | Pass | updated for the new use (after fix) |
| Idempotent writes | Pass | each `.npz` overwritten, stale ones removed, wheels folder rebuilt whole |
| Alerts | n/a | |

## Test Coverage
- Tested: the shape, dtype and unit norm of each vector; truncation before renormalising; dedup within one graph
  and across graphs through the cache; the name fallback for empty text; the npz round trip against
  `competition_check`; the wheel requirements taken from `pyproject.toml`; the shape of the wheel command.
- Not tested: the model call itself (exercised by the real build) and the script's flag wiring.
- Run locally:
  - `cd python && pytest -q tests`: 1616 passed, 31 skipped.
  - `ruff check` on the changed files: clean.
  - The real build `--graphs --embeddings --wheels` exited 0.

## Verdict
Approve with nits. The two should-fix items and four nits are fixed and re-verified. Nits 6 and 8 can follow, and
nit 8 is best checked against the competition's image at T011. Merge once CI is green on `2cb0a2f` or later.
