# PR 844 review: Modal runs may spend 42 USD a month without approval

Closes #843. Range: `origin/main..chore/843-028-modal-monthly-42`. One file: `ops/cost_settings.yaml` (3 lines).

## Scans

- **Secrets:** none.
- **PHI / real data:** none.
- **Organization claims:** none. Modal's figures (13.59 USD used, 30 USD credit, 42.50 USD usage limit) are from the owner's own billing page, November 16.

## Findings (verified)

- 🔵 Nit: `kaggle/README.md` line 168 and ADR 0008 line 24 still give the monthly limit as 25 USD. They were already stale after #825 (35). Not changed here; the file is the declaration, and the docs name the key.

Nothing blocking or should-fix.

## Compliance

| Rule | Result |
|---|---|
| No secrets | ✅ |
| Configuration | ✅ one declaration, changed by pull request; the PR says only the Modal cost gate reads it |
| Prices | ✅ the source line says who asked, when and why |
| Test first | n/a: a value change; `test_modal_official.py` reads the limits from the file, 25 passed |
| Commits | ✅ |
| Others | n/a |

## Checks

- `pytest -q tests/test_modal_official.py`: 25 passed.

## Verdict

Ready when CI is green. It changes a spending rule, so the owner merges it.
