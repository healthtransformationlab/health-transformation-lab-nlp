Synthetic run folders for `python/tests/test_load_agent_traces.py` (spec 041 US2). Made up: no competition task
text, no real repository. `demo_101` is solved: a turn with two tool calls (the second's output comes back as its own
system step), a failed edit, a good edit and a submit. `demo_102` timed out with no patch after one turn that called no
tool. `demo_101`'s tool output holds `__FAKE_TOKEN__`: the test puts a fake token there in a temporary copy, so no
token-shaped text is committed, and checks the token never reaches a span.
