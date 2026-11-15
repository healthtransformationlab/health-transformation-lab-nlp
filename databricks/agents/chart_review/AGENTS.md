# AGENTS.md: chart review agent (Databricks)

Rules for any coding agent working in `databricks/agents/chart_review/`. The repo-wide rules in the root
[`AGENTS.md`](../../../AGENTS.md) apply first; this file adds what is specific to this agent.

> **Status: specified, not built.** Nothing here runs yet. The spec is
> [`specs/015-chart-review-agent/spec.md`](../../../specs/015-chart-review-agent/spec.md); next come
> `plan.md` and `tasks.md` (`/speckit-plan`, `/speckit-tasks`), then the failing tests, then the code. Check Databricks APIs against the current Databricks
> documentation when building; the names below describe intent.

## What it is

An LLM agent on Databricks that reads one synthetic visit's **whole record** and answers the same
question as every other method: *healthy, gingivitis, or periodontitis stage 1–4?* Unlike the trained
models, which read only the note, it can look up each evidence type, apply that type's rule from
[`docs/evidence_rules.md`](../../../docs/evidence_rules.md), weigh the parts against each other when they
disagree (a stale exam form against a measured probing chart), and say why, quoting the record.

It is one more method in the comparison, not a replacement for the answer key or the rule phenotypes:
it is scored on the same review charts with the same code, and its results appear as
`agent:chart_review` in the full results table.

## Rules

- **Synthetic only.** It reads the synthetic study tables in the gold schema and nothing else. Notes go
  to the model only after de-identification and the leak gate, as for the LLM judge.
- **Every claim quotes the record.** Each piece of evidence it uses comes with a verbatim quote or the
  exact field value; the quote gate in `health_transformation_lab_nlp.judge` checks it. An answer whose quotes fail is
  scored as *no answer*, never repaired.
- **Rules come from the code, not the prompt.** Tools return what the repo's readers say
  (`health_transformation_lab_nlp.sources`, `note_reader`, `labels`, `radiograph`); the agent decides only when they
  disagree or say nothing. Don't restate the rules in the prompt, where they can drift from the code.
- **It may abstain.** "No answer" is a valid output when the record can't support a status; it is
  counted as such, never coerced into a guess.
- **Metrics are computed in code.** Scoring uses `readme_results` and `judge_scorecard`, never the LLM.
  Python and R stay in parity for anything added to scoring.
- **Cost is printed and capped before running**, as `07_judge_scorecard.py` does: token estimate, US$ at
  the endpoint's list price, stop above `max_usd`.
- **Label the output.** Results are `agent:chart_review` (or `sim:chart_review` for a simulated dry run)
  and are LLM output, said so wherever they're shown.
- **Names are identical in every target** (root `AGENTS.md`): no `dev_` prefixes, no `mode: development`.
- **Configuration is checked first** (root `AGENTS.md`, "Configuration and secrets"): with the endpoint
  variable `none` the job skips with a message; an endpoint that is set but doesn't answer one cheap call
  fails before any visit is read, naming the variable.
- **Writes are idempotent**: results for a run replace that run's rows (keyed by run id and `visit_id`),
  so a repair re-run never doubles them.
- **Severity of its failures**: a quote-gate failure rate above the threshold, or any note reaching the
  model without passing the leak gate, is SEV1 (stop the run); an endpoint error that retries clear is SEV3;
  cost above `max_usd` stops the run before it starts (SEV2 if it happens in a scheduled run).

## Tools

Unity Catalog functions in `health_transformation_lab.gold_perio_bench`, so the agent, SQL and the Playground
all call the same code. Each is a thin wrapper over a tested function in `python/health_transformation_lab_nlp/`.

| Tool | Returns | Wraps |
|---|---|---|
| `visit_evidence(visit_id)` | Every evidence type for the visit, raw: exam form, procedure and diagnosis codes (planned and done), probing chart summary, X-ray reading, de-identified note | the study tables |
| `read_evidence(evidence_type, value)` | The status that type's rule gives, or `unknown` | `sources.READERS`, `note_reader.read_note`, `labels.label_chart`, `radiograph.read_radiograph` |
| `evidence_rule(evidence_type)` | The plain-words rule and what the type can't tell | the matching section of `docs/evidence_rules.md` |

No tool writes anything. The agent never sees the answer key.

## Output

One JSON object per visit, validated before it's kept:

```json
{"visit_id": 0, "status": "periodontitis_stage_2 | ... | no_answer",
 "evidence": [{"type": "probing_chart", "says": "periodontitis_stage_2", "quote": "max CAL 4 mm"}],
 "deciding_evidence": "probing_chart", "why": "one sentence"}
```

## Evaluation

- The review charts against the generator's truth, with every phenotyping metric the README uses
  (correct, incorrectly assigned / ruled out, incorrect stage, no answer, unsafe errors, by note
  difficulty) and its rank among all methods.
- Next to the two rule phenotypes (*gum measurements first*, *exam form first*): it only earns its cost if
  it beats them, or matches them while explaining itself.
- The LLM judge's agreement with its answers, reported as LLM judgment, as for every other method.
- Each run is an MLflow experiment run with one trace per visit, tagged with `git_commit`.

## Deployment

- A job in `databricks/resources/` deployed by the bundle like every other; runs on demand.
- The model behind it is a pay-per-token serving endpoint set by a bundle variable (default `none`, which
  skips it), with AI Gateway usage tracking and rate limits on that endpoint.
- Logged with MLflow and registered in Unity Catalog as `health_transformation_lab.gold_perio_bench.chart_review_agent`
  only if it passes the same acceptance test as the other models.

## Layout

Planned; add each file with its tests, under the spec.

| Path | What |
|---|---|
| `databricks/agents/chart_review/AGENTS.md` | This file |
| `databricks/agents/chart_review/CLAUDE.md` | Imports this file for Claude Code |
| `databricks/agents/chart_review/agent.py` | The agent: prompt, tool calls, output validation (MLflow agent interface) |
| `databricks/agents/chart_review/tools.sql` | `CREATE FUNCTION` statements for the Unity Catalog tools |
| `databricks/notebooks/11_chart_review_agent.py` | Job notebook: cost check, run on the review charts, save, score |
| `python/health_transformation_lab_nlp/chart_review.py` | Testable logic: evidence gathering, output schema, quote checks, scoring hookup |
| `python/tests/test_chart_review.py` | Tests, with a simulated agent so no endpoint is needed |
| `r/R/` | R twin of anything added to scoring |
