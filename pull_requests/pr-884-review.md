# PR 884 review: official_verify fails loudly on missing modules (#883)

Reviewed against `AGENTS.md` and `.conventions/AGENTS-common.md`.

| Check | Result |
|---|---|
| One issue, branch `fix/883-verify-missing-module`, `Closes #883` | yes |
| Test first | `test_verify_env_guard.py` covers the mark, the error field, a clean set, and that `official_verify.py` calls the guard before printing a resolve total |
| Contract | any `No module named` in `error` or `output_tail` → exit 2; JSONL still written; no resolve print |
| Secrets / PHI | none |
| Docs | none required for this fix |

## Findings

Nothing blocking. The guard is string-matched on `No module named` only (as the owner asked); other environment faults still look like ordinary fails until named the same way.
