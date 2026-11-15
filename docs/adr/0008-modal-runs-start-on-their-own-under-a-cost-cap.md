# ADR 0008: Modal runs start on their own under a cost cap; above it they wait for the owner

Date: 2026-11-15 · Status: accepted · Issue: #806

## Context

Modal is a paid GPU path for the competition's evaluator loop (#804, `.github/workflows/modal-agent.yml`). It is billed
by the second from the owner's Modal account, whose Starter plan includes 30 USD of credit a month. Each run's
`max_usd` already becomes Modal's own time limit, priced at the GPU plus the CPU and memory at their hard limits
(`kaggle/modal_official.py`), so a run cannot cost more than it says.

The first version said that starting the workflow was the owner's yes, but nothing in GitHub enforced it. The
environment `dev` has no approval rule, and the first trial was started from an agent session through GitHub's API.
On November 15, 2026, asked whether runs could be started for them, the owner answered: "Just automate with cap
approve if over some reasonable limit."

ADR 0007 keeps the Kaggle GPU pool as a reserve and makes Colab the default for GPU runs. It does not cover Modal.

## Decision

- **A Modal run starts on its own** (by hand, or from an agent session without asking) when both hold:
  - its `max_usd` is at most `modal_auto_max_usd` (5 USD: about 3.7 hours of an L4 at the limits' price);
  - this month's Modal spend (`modal billing summary`, `metered_cost`) plus `max_usd` is at most
    `modal_auto_monthly_usd` (25 USD).
- **Any other run waits for the owner.** That includes a run made when this month's spend cannot be read. It waits in
  a job using the GitHub environment `modal-approval` until the owner approves it in Actions.
- **The approval job refuses the run unless `modal-approval` has a required reviewer.** GitHub makes a missing
  environment on the spot with no rule, and such an environment must never let a run through.
- **The two limits are in `ops/cost_settings.yaml` and change only by pull request.** 25 USD a month keeps runs that
  start on their own inside the 30 USD credit, with 5 to spare for runs the owner approves.
- **Colab stays the default for GPU runs when cost matters (ADR 0007).** Modal is used when its speed or its starting
  without a person helps more than its price costs. Which runs those are is written down after the two-task trial
  (#804).

What does not change: one run at a time, the machine checked on a CPU before the GPU, the run list apart from Colab's,
and the open-network sign-off on the run's own branch (ADR 0005).

## Consequences

- Agent sessions can start small Modal runs without waiting for a person, and a month of them cannot spend past the
  credit.
- A larger run costs the owner one click in Actions. GitHub notifies the required reviewer when a run is waiting.
- The owner has to create `modal-approval` once, with themselves as required reviewer. Until then every over-limit run
  is refused, which is safe but blocks it.
- The monthly count is Modal's whole workspace, so other Modal use counts against it too.
- The prices behind the cap come from third-party pages until a run prints Modal's own (`modal billing rates`, logged
  by the workflow). The cap is only as good as they are.

## Revisit when

- The trial or later runs show the limits are too tight or too loose.
- Modal's prices or the plan's credit change.
- Runs need several GPUs at once, so that one run's `max_usd` no longer bounds what is spent at a time.
