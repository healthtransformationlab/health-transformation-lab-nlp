# PR 820 review: after a 403, fall back to KAGGLE_USERNAME and say why it stops

Closes #819. Reviewed against `.claude/review-rubric.md` and AGENTS.md.

- Behaviour: the only decision change is the username fallback; a 403 with any doubt still stops the run (the existing #815 test passes unchanged).
- Logging: lengths and exception kinds only; the test asserts the other account's name is not printed. No credential is read into a message.
- Tests first: the new test failed on main's helper and passes here; 102 passed across the Colab and Modal suites.
- Rules: no compute, publish or rule change: an agent may merge it when green.

Nothing blocking.
