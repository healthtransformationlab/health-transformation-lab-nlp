# Feature Specification: what each task costs, and spending less

**Feature Branch**: `spec/568-036-cost-per-task`

**Created**: 2026-11-04

**Status**: Draft

**Input**: "What improvements can you make for cost and performance? Do we track how DBU cost, performance and
time are associated with tasks? If not, how can we add it, ideally with ways to optimize it with our AI coding
agent?"

## What exists today

| What | Tracked |
|---|---|
| LLM calls (reader, judge) | yes: `cost_usd` per answer, the `judge_cost` table, at the endpoint's list price |
| Databricks job runs | duration, but not cost. `fact_pipeline_run.cost_usd` exists, but the pipeline doctor (spec 027) fills it only from an optional span table, and nothing writes a cost there. So the `cost_ratio` signal is always empty and the `cost_anomaly` class (cost over 3x the trailing median) never fires. Nothing reads DBUs. |
| Coding-agent tasks (spec 035, Kaggle) | agent seconds, model seconds, model load seconds, the largest prompt. Per-turn tokens are kept in each run's output, but there are no totals, no GPU-hours, no share of the weekly allowance and no cost. |

This spec fills those gaps, then uses the numbers: the pipeline doctor recommends fixes, and the coding-agent run
spends its GPU allowance on the cheapest tasks first.

> Personal learning project, not affiliated. A cost that is estimated (a cloud-equivalent price for free Kaggle
> GPUs, a list price that isn't what anyone paid) is labelled as an estimate wherever it is shown.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Every Databricks job run carries its DBUs and cost (Priority: P1) #568

The owner opens the pipeline runs and sees, for each job run, the DBUs it used and what they cost at list price.
The doctor's cost signal compares each run with its trailing median, so a run costing three times the usual is
flagged as `cost_anomaly`.

**Why this priority**: the cost column and the cost signal already exist and are always empty. Filling them turns
on a check the doctor was designed with, and every later story compares against these numbers.

**Independent Test**: from a fixed set of billing-usage and list-price rows (no workspace needed), the runs come out
with the expected DBUs and cost, and a run at more than three times its trailing median is classed
`cost_anomaly`.

**Acceptance Scenarios**:

1. **Given** a job run with two usage records (two SKUs), **When** the doctor runs, **Then** the run's row holds
   the summed DBUs and the cost at each SKU's list price in effect when the usage happened.
2. **Given** a workspace that doesn't expose the billing tables, **When** the doctor runs, **Then** it warns once,
   naming the missing table, writes the runs with empty cost, and finishes (AGENTS.md: optional settings warn).
3. **Given** a run whose usage hasn't arrived yet (billing data lags), **When** the doctor runs, **Then** the cost
   stays empty and is filled on a later run, never zero.
4. **Given** a later doctor run over the same job runs, **When** it writes, **Then** each run has one row with the
   newest cost (idempotent, by run).

---

### User Story 2 - Every coding-agent task carries its tokens, GPU-hours and an estimated cost (Priority: P1) #569

The owner reads the agent run table and sees, per task:
- the tokens it used;
- how long its kernel held the GPU;
- the GPU-hours, and their share of the weekly Kaggle allowance;
- an estimated cloud-equivalent cost.

Before a full run, the owner sets a GPU-hour cap. The runner takes tasks cheapest first and stops at the cap,
saying how many tasks it ran and what is left.

**Why this priority**: the full Gemma run (spec 035 US2) is about 113 GPU runs and may need more than a week's
allowance. Without the cap and the numbers, that decision is a guess.

**Independent Test**: from saved kernel results (per-turn tokens and seconds, kernel start and end times), the
rows hold the expected totals, GPU-hours, allowance share and estimate. Against a fake Kaggle API, a run with a
cap stops before the task that would pass it.

**Acceptance Scenarios**:

1. **Given** a finished kernel, **When** its task is scored, **Then** its row holds total prompt tokens, total
   output tokens, kernel wall seconds, GPU-hours (wall time by number of GPUs), the share of the weekly allowance,
   and an estimated cost named as an estimate with its price, source and date.
2. **Given** a cap of N GPU-hours, **When** the runner starts, **Then** it orders tasks by expected cost (from
   earlier runs, else by patch and prompt size), and stops before the task whose expected cost would pass the cap.
3. **Given** a kernel that failed or timed out, **When** it is scored, **Then** its GPU time still counts towards
   the cap and the table: a failed run used the allowance too.
4. **Given** the rows, **When** the results load into gold, **Then** a table holds one row per task run with these
   columns, named by the repo's column rules.

---

### User Story 3 - The doctor recommends cost and duration fixes, and cost per resolved task is on a dashboard (Priority: P2) #570

When a pipeline's cost or duration drifts above its trailing median, the doctor records a SEV4 recommendation with
a specific action, such as:
- "the judge scorecard's model changed: compare cost per chart";
- "a step reran three times: check the retry setting";
- "the GPU job waited 20 minutes for a GPU: move it off the hour".

Each recommendation is written so that a coding-agent session can carry it out as a pull request, under the usual
merge rules. A dashboard and Genie view shows cost per resolved task by model, tier and settings, so the cheapest
model that resolves enough tasks can be picked from data.

**Why this priority**: it turns the numbers from US1 and US2 into actions, but needs them first.

**Independent Test**: from a fixed run history, a run at 2.5 times its median duration gets a SEV4 recommendation,
with an action from the runbook's allow-list, in the weekly digest. The view's query returns cost per resolved task
for the committed agent runs.

**Acceptance Scenarios**:

1. **Given** a run whose duration is more than twice its trailing median (and its cost isn't anomalous), **When**
   the doctor classifies it, **Then** it records a `duration_drift` recommendation at SEV4, with the action and
   the evidence (the run, the median, the ratio).
2. **Given** a `cost_anomaly` or `duration_drift` recommendation, **When** it is written, **Then** its action names
   a file and a setting to change (a job's retries, a cluster or GPU setting, a model in `models.yaml`), or says
   "investigate" when no rule fits.
3. **Given** such a recommendation, **When** a coding-agent session takes it, **Then** the PR follows AGENTS.md:
   one issue, its branch, its review file. A change that starts a run on limited compute or a paid endpoint waits
   for the owner's "merge".
4. **Given** the committed agent runs, **When** the view is opened, **Then** it shows tasks run, tasks resolved,
   GPU-hours and estimated cost per resolved task, by model, tier and settings, with "estimated" on the cost.

---

### Edge Cases

- A job run with no usage records (a skipped task, a run too short to bill): DBUs 0 only if billing says so; an
  absent record leaves the cost empty.
- A SKU with no list price for the run's date: cost empty, with a warning naming the SKU.
- Kaggle's weekly allowance varies by week and isn't read through the API: it is a declared setting, and the share
  is labelled with the allowance it assumed.
- A kernel queued before it got a GPU: queue time isn't GPU time. Only the kernel's own start-to-end time counts,
  and the queue time is recorded apart.
- A rerun of a task replaces its row (as the agent table does today); the cap counts every run's GPU time, reruns
  included.
- Simulated or calibration runs (`calib:`, `sim:`): their cost rows are labelled as such and never mixed into a
  model's cost per resolved task.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Every Databricks job run the doctor reads MUST carry its DBUs, and its cost at the list price in effect
  at usage time, when the workspace's billing data has them.
- **FR-002**: When billing data isn't available, the doctor MUST warn once, naming what is missing, and MUST NOT fail.
- **FR-003**: A cost MUST stay empty, not zero, when its usage or price is missing.
- **FR-004**: Every coding-agent task row MUST carry total prompt tokens, total output tokens, kernel wall seconds,
  queue seconds, GPU count, GPU-hours, the share of the weekly allowance, and an estimated cost.
- **FR-005**: The GPU price for the estimate and the weekly allowance MUST be declared once each, with their value,
  source, and the date they were read; every estimated cost MUST carry which price it used.
- **FR-006**: The agent runner MUST accept a GPU-hour cap, order tasks by expected cost, stop before passing the cap,
  and report what it ran and what is left.
- **FR-007**: Failed and timed-out kernels MUST count towards the cap and the table.
- **FR-008**: The doctor MUST classify duration drift (above twice the trailing median, no other class) as
  `duration_drift` at SEV4, and cost drift as `cost_anomaly` (existing bound), each with an action from the runbook's
  allow-list and the evidence.
- **FR-009**: Each recommendation MUST name the file and setting to change, or say "investigate".
- **FR-010**: The cost tables MUST load into gold and follow AGENTS.md "SQL and data names", with table and column
  comments (spec 034).
- **FR-011**: A dashboard and Genie view MUST show cost per resolved task by model, tier and settings, with
  estimated costs labelled.
- **FR-012**: Calibration and simulated runs MUST be labelled and kept out of a model's cost per resolved task.

### Key Entities

- **Job run cost**: one Databricks job run: its DBUs by SKU, its list-price cost, when the usage was read.
- **Agent task run**: one coding-agent task on one model with one set of settings: tokens, seconds, GPU-hours,
  allowance share, estimated cost, whether it resolved.
- **Price setting**: a GPU or DBU price: value, unit, source, date read.
- **Cost recommendation**: a doctor decision for cost or duration drift: the run, the evidence, the severity, the
  action, and whether the owner took it.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Where billing data is available, every Databricks job run from the last 30 days that has usage
  records shows a cost; none shows zero for missing data.
- **SC-002**: Every coding-agent task run from the Kaggle pilot onward shows its GPU-hours and estimated cost, and
  the sum of GPU-hours over a week can be compared with that week's allowance.
- **SC-003**: Before the full Gemma run, the owner can state its expected GPU-hours from the pilot. With a cap, the
  run uses no more than the cap plus one task's GPU time.
- **SC-004**: A pipeline whose run doubles in duration gets a SEV4 recommendation with a concrete action in the next
  weekly digest.
- **SC-005**: The owner can answer "which model resolves tasks for the least GPU time?" from one view, without
  reading run files.

## Assumptions

- **Billing data:** Databricks exposes DBU usage and list prices as system tables; whether Free Edition grants
  access to them is checked first (US1's first task), and the feature works with empty costs if it doesn't.
- **Kaggle allowance:** about 30 GPU-hours a week, and it varies by week. Kaggle's own pages are the source; third-party
  guides disagree on when it resets. Declared as a setting, never assumed exact.
- **GPU price:** the estimate uses a declared price per T4 GPU-hour, with its source and date. A cross-provider
  median ($0.69 per GPU-hour on Oct 26, 2026, getdeploying.com) is the starting value. It is an estimate of what the
  same work would cost on a cloud, not anything paid: Kaggle's GPUs are free to us.
- **Out of scope:**
  - reusing the KV cache across turns to speed the Gemma agent, a performance fix tracked under #544;
  - LLM endpoint costs, already tracked per answer;
  - acting on a recommendation automatically: a person or an agent session opens the PR.
