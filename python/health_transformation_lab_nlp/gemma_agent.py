"""Gemma 4 as the local harness's model (spec 035 US2, #544), in Gemma 4's own tool-call format.

    parse_reply(text, hit_limit)  a generated model turn as the harness wants it: {content, tool_calls, finish_reason}
    to_gemma_messages(messages)   the harness's OpenAI-style history in the shape Gemma 4's chat template renders
    GemmaModel(model_dir, ...)    transformers on a GPU (Kaggle's 2x T4); .step(messages, tools) is one turn

The format, from the chat template shipped with google/gemma-4 (read on Kaggle, Nov 2026):

- a call is `<|tool_call>call:NAME{key:value,...}<tool_call|>`; a string value sits between `<|"|>` delimiters,
  numbers, booleans and null are bare, lists are `[...]` and objects `{...}`
- the result goes back inside the same model turn, right after the call: the template renders an assistant
  message's `tool_responses` [{name, response}] as `<|tool_response>response:NAME{...}<tool_response|>`, and the
  model carries on from there; there is no separate tool turn
- thinking, when on, is `<|channel>thought ...<channel|>`, which the template strips from past turns

Only this module, agent_harness.py and task_gate.py go to Kaggle with a task (kaggle/agent_bundle.py); none of them
is changed by any task, so none holds an answer.
"""

from __future__ import annotations

import json
import re
import time

from .telemetry import traced

STR = '<|"|>'
CALL_OPEN, CALL_CLOSE = "<|tool_call>", "<tool_call|>"
STOP_STRINGS = ("<turn|>", "<|tool_response>", "<eos>")
_THOUGHT = re.compile(r"<\|channel>.*?(?:<channel\|>|$)", re.S)
_CALL = re.compile(r"<\|tool_call>call:([\w.\-]+)(.*?)<tool_call\|>", re.S)


class _Bad(ValueError):
    pass


def _value(s: str, i: int):
    if s.startswith(STR, i):
        j = s.find(STR, i + len(STR))
        if j < 0:
            raise _Bad("unclosed string")
        return s[i + len(STR):j], j + len(STR)
    if s.startswith("{", i):
        return _object(s, i)
    if s.startswith("[", i):
        out, i = [], i + 1
        while True:
            if s.startswith("]", i):
                return out, i + 1
            v, i = _value(s, i)
            out.append(v)
            if s.startswith(",", i):
                i += 1
            elif not s.startswith("]", i):
                raise _Bad("bad list")
    m = re.compile(r"[^,}\]]*").match(s, i)
    raw = m.group(0).strip()
    if not raw:
        raise _Bad("empty value")
    try:
        return json.loads(raw), m.end()
    except json.JSONDecodeError:
        return raw, m.end()


def _object(s: str, i: int):
    if not s.startswith("{", i):
        raise _Bad("expected {")
    out, i = {}, i + 1
    while True:
        if s.startswith("}", i):
            return out, i + 1
        if s.startswith(STR, i):
            key, i = _value(s, i)
        else:
            m = re.compile(r"[\w.\-]+").match(s, i)
            if not m:
                raise _Bad("bad key")
            key, i = m.group(0), m.end()
        if not s.startswith(":", i):
            raise _Bad("expected :")
        out[key], i = _value(s, i + 1)
        if s.startswith(",", i):
            i += 1
        elif not s.startswith("}", i):
            raise _Bad("expected , or }")


def _arguments(raw: str):
    """A call's arguments as a dict; the raw text when they can't be read, so the tool answers ValidationError."""
    raw = raw.strip()
    try:
        out, end = _object(raw, 0)
        if raw[end:].strip() == "":
            return out
    except _Bad:
        pass
    try:   # some turns write JSON, once or wrapped in the template's own braces
        inner = raw[1:-1].strip() if raw.startswith("{{") else raw
        out = json.loads(inner)
        if isinstance(out, dict):
            return out
    except json.JSONDecodeError:
        pass
    return raw


@traced
def parse_reply(text: str, hit_limit: bool) -> dict:
    """One generated turn: its text without thoughts or calls, its calls in order, and why it stopped ("length"
    when it ran out of tokens, so a cut-off call gets the harness's unclosed-call nudge)."""
    calls = [{"id": f"call-{n}", "name": m.group(1), "arguments": _arguments(m.group(2))}
             for n, m in enumerate(_CALL.finditer(text))]
    rest = _THOUGHT.sub("", _CALL.sub("", text))
    if "<channel|>" in rest:   # a thought whose opening marker wasn't generated (thinking off): drop up to its close
        rest = rest.rsplit("<channel|>", 1)[1]
    for s in STOP_STRINGS:
        rest = rest.replace(s, "")
    reason = "length" if hit_limit else ("tool_calls" if calls else "stop")
    return {"content": rest.strip(), "tool_calls": calls, "finish_reason": reason}


@traced
def to_gemma_messages(messages: list[dict]) -> list[dict]:
    """Each tool message folded into the assistant turn that made the call (as its tool_responses, with the tool's
    name), arguments as mappings, and past thoughts dropped."""
    out, names = [], {}
    for m in messages:
        if m["role"] == "tool":
            if not out or out[-1]["role"] != "assistant":
                out.append({"role": "assistant", "content": "", "tool_responses": []})
            try:
                resp = json.loads(m.get("content") or "")
            except json.JSONDecodeError:
                resp = m.get("content") or ""
            out[-1].setdefault("tool_responses", []).append(
                {"name": names.get(m.get("tool_call_id"), "unknown"), "response": resp})
            continue
        if m["role"] == "assistant":
            calls = []
            for c in m.get("tool_calls") or []:
                fn = c.get("function") or {}
                args = fn.get("arguments")
                if isinstance(args, str):
                    try:
                        args = json.loads(args) if args.strip() else {}
                    except json.JSONDecodeError:
                        pass
                names[c.get("id")] = fn.get("name") or "unknown"
                calls.append({"id": c.get("id"), "type": "function",
                              "function": {"name": fn.get("name") or "", "arguments": args}})
            # with calls, no text: the template renders text after the results and then closes the turn, where
            # the model carries on after a result; text before a call is commentary, the call is what counts
            a = {"role": "assistant", "content": "" if calls else _THOUGHT.sub("", m.get("content") or "").strip()}
            if calls:
                a["tool_calls"] = calls
            out.append(a)
            continue
        out.append({"role": m["role"], "content": m.get("content") or ""})
    return out


class GemmaModel:
    """Gemma 4 with transformers, on whatever GPUs there are (device_map auto). Keeps what each turn cost."""

    @traced
    def __init__(self, model_dir: str, name: str = "gemma-4-e4b-it", max_new_tokens: int = 2048,
                 temperature: float = 0.2, top_p: float = 0.95, thinking: bool = False, max_context: int = 32768,
                 max_memory: dict | None = None):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        self.name, self.thinking, self.max_context = name, thinking, max_context
        self.gen = {"max_new_tokens": max_new_tokens, "do_sample": temperature > 0, "temperature": temperature,
                    "top_p": top_p}
        self.tok = AutoTokenizer.from_pretrained(model_dir)
        if max_memory:   # JSON keys are strings; accelerate wants GPU numbers as ints
            max_memory = {int(k) if str(k).isdigit() else k: v for k, v in max_memory.items()}
        self.model = AutoModelForCausalLM.from_pretrained(model_dir, dtype=torch.float16, device_map="auto",
                                                          max_memory=max_memory)
        vocab = self.tok.get_vocab()
        self.stop_ids = [vocab[s] for s in STOP_STRINGS if s in vocab]
        self.turns: list[dict] = []
        self.history: list[dict] = []

    @traced
    def step(self, messages, tools):
        import torch
        self.history = messages   # the harness's list, kept for the run's transcript
        ids = self.tok.apply_chat_template(to_gemma_messages(messages), tools=tools, add_generation_prompt=True,
                                           return_tensors="pt", return_dict=True, enable_thinking=self.thinking)
        n_in = int(ids["input_ids"].shape[-1])
        if n_in > self.max_context:   # past what fits beside the KV cache: end the turn, the harness nudges
            self.turns.append({"prompt_tokens": n_in, "output_tokens": 0, "seconds": 0.0, "over_context": True})
            return {"content": "", "tool_calls": [], "finish_reason": "length"}
        ids = {k: v.to(self.model.device) for k, v in ids.items()}
        t = time.monotonic()
        with torch.no_grad():
            o = self.model.generate(**ids, **self.gen, eos_token_id=self.stop_ids or None)
        new = o[0][n_in:]
        text = self.tok.decode(new, skip_special_tokens=False)
        hit = len(new) >= self.gen["max_new_tokens"] and not any(text.rstrip().endswith(s) for s in STOP_STRINGS)
        self.turns.append({"prompt_tokens": n_in, "output_tokens": int(len(new)),
                           "seconds": round(time.monotonic() - t, 2)})
        return parse_reply(text, hit_limit=hit)
