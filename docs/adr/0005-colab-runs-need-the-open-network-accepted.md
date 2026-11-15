# ADR 0005: A Colab run starts only when its entry accepts an open network

Date: 2026-11-15 · Status: accepted · Issue: #691

## Context

The Colab helper (`kaggle/colab_official.py`) runs the competition's evaluator loop on a Colab GPU. On Kaggle the
kernels ran with internet off. On Colab nothing blocks the network at the machine: the proxies the helper sets on
the kernel's process do not reach the agent's commands, because the evaluator starts each command from its own
short list of environment names (`_SAFE_ENV_KEYS`), which holds no proxy. The review of pull request 690 found this
after the runs of #687 (item 6 of #691). For those runs a reading of every tool call found nothing fetched
(`data/tasks/official_agent_runs/README.md`).

The real fix is to block the network at the machine for the kernel's process group (a network namespace or a
firewall rule), and to test that with a command run through the evaluator's own sandbox. That needs a real Colab
machine with root. It cannot be built or tested offline, and #691 forbids starting a GPU run to try it.

## Decision

Until the block exists and is tested, the helper refuses to start a run unless the run's entry in
`kaggle/colab_official_run.json` says, in so many words, that the operator accepts an open network:
`"network_open_acknowledged": true`. Without that key, or with any value but `true`, or when the run list cannot be
read, the run stops before anything is installed, restored, fetched or uploaded, and the log says why
(`network_open_acknowledged` and `NETWORK_REFUSAL` in the helper).

The key is set on the run's own branch, never on `main`, where the run list says stop. A test checks that no
committed entry sets it. A run made this way says in its settings that the network was open (`COLAB_INTERNET`), and
its commands and tool calls are read afterwards (`network_audit`).

Item 6 of #691 is documented and guarded by this decision, not fixed.

## Consequences

- A later run cannot start with an open network by accident: someone has to write that they accept it.
- A run list that cannot be read stops a run, where before the run went ahead.
- What an open network allows (a fetched fix, an installed package) is caught only afterwards, by the audit, not
  prevented.

## Revisit when

The helper blocks the network at the machine for the kernel's process group, with a test that a command run
through the evaluator's sandbox cannot reach a host. Then the key is no longer needed and this decision is
superseded.
