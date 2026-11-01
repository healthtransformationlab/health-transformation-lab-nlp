# ADR 0003: The data-quality report is a static page, not a FastAPI app

Date: 2026-11-01 · Status: accepted · Issue: #365 (also #366, #367)

## Context

Issues #365–#367 planned the Perio DQ Monitor as its own app: a FastAPI backend querying the gold tables on a
Databricks SQL warehouse, a React front end, one app serving every bench, and a Databricks App with a service
principal and a warehouse.

The owner chose a simpler route: generate the numbers as a JSON file in this repo and publish a static page, so it
costs almost nothing to host. That is now built: `dq_site.build()` (`python/scripts/50_dq_site.py`) writes
`docs/site/data-quality.json` from the same tables the Databricks EHR DQ grader reads, and the website's
`data-quality/` page (React from a CDN, no build step) reads it straight from this repo's `main` on GitHub Pages.
Tests tie the JSON to the grader's definitions, so the page and the dashboard show the same numbers.

## Decision

Keep the data-quality report as a static page fed by a committed JSON file. Don't build the FastAPI app, the
multi-bench report server, or the Databricks App. Close #365, #366 and #367 as not planned.

## Consequences

- **Easier:** nothing to run, secure or pay for. There's no warehouse, no service principal and no app credential
  to rotate. The page is public and works on a phone.
- **Easier:** the numbers are versioned with the code that makes them. A change shows up in the PR as a JSON diff.
- **Harder:** the page shows what is committed, not live data. It refreshes when `50_dq_site.py` is rerun and
  merged.
- **Harder:** it only suits synthetic or published numbers. Real records could never be published this way.

## Revisit when

- the report must show real records, which need access control a public static page can't give; or
- the numbers must update more often than a commit can carry; or
- OralHealthBench or AccessBench need interactive reports a static file can't serve.
