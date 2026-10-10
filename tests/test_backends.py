# lezio — Copyright (C) 2026 JustSalvin — https://github.com/JustSalvin/lezio
# GNU AGPL v3 with additional terms (section 7): see LICENSE and NOTICE.  SPDX-License-Identifier: AGPL-3.0-only
"""The LLM backends' tool loops against fake servers that speak each API: Anthropic (SSE stream), OpenAI
Responses, Chat Completions with Ollama's /api/ps. No model, key or network needed; the anthropic and
openai packages are (requirements-video.txt).

    .venv/bin/python tests/test_backends.py
    docker run --rm -v "$PWD":/app:ro python:3.14-slim sh -c \
        "pip install -q anthropic openai pillow && python /app/tests/test_backends.py"   # without installing
"""
import json
import os
import sys
import tempfile
import threading
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from lezio.agent.backends import AnthropicAPI, Local, OpenAIAPI  # noqa: E402
from lezio.agent.backends.base import Image, Task, Tool, ToolResult  # noqa: E402

PNG = Image(b"\xff\xd8\xff fake jpeg", "image/jpeg")
FAILS = []


def check(cond, label):
    print(("  ok   " if cond else "  FAIL ") + label)
    if not cond:
        FAILS.append(label)


# ------------------------------------------------------------------ fake server
class Fake:
    def __init__(self):
        self.requests = []      # (method, path, headers, body)
        self.script = []        # functions(body) -> (status, content_type, payload str)
        self.ps = None          # /api/ps answer
        self.models = ["gemma4:12b"]
        server = ThreadingHTTPServer(("127.0.0.1", 0), self.handler())
        self.port = server.server_address[1]
        threading.Thread(target=server.serve_forever, daemon=True).start()

    def handler(self):
        fake = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def send(self, status, ctype, payload):
                data = payload.encode()
                self.send_response(status)
                self.send_header("content-type", ctype)
                self.send_header("content-length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def do_GET(self):
                fake.requests.append(("GET", self.path, dict(self.headers), None))
                if self.path.endswith("/models"):
                    self.send(200, "application/json", json.dumps(
                        {"object": "list", "data": [{"id": m, "object": "model", "created": 0, "owned_by": "x"}
                                                    for m in fake.models]}))
                elif self.path == "/api/ps" and fake.ps is not None:
                    self.send(200, "application/json", json.dumps(fake.ps))
                else:
                    self.send(404, "application/json", "{}")

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["content-length"])))
                fake.requests.append(("POST", self.path, dict(self.headers), body))
                status, ctype, payload = fake.script.pop(0)(body)
                self.send(status, ctype, payload)
        return H

    def posts(self):
        return [r for r in self.requests if r[0] == "POST"]


def task(tools_log, done_on="finish", **kw):
    def look(args):
        tools_log.append(("look", args))
        return ToolResult(["page text", PNG])

    def finish(args):
        tools_log.append(("finish", args))
        return ToolResult(["Done."], done=True)
    events = []
    t = Task("test", "SYSTEM PROMPT", "USER PROMPT", [
        Tool("look", "Look at a page", {"type": "object", "properties": {"what": {"type": "string"}},
                                        "required": ["what"]}, look),
        Tool("finish", "Finish", {"type": "object", "properties": {}}, finish)],
        log_path=Path(tempfile.mkdtemp()) / "log.jsonl", on_event=lambda k, d: events.append((k, d)), **kw)
    return t, events


# ------------------------------------------------------------------ Anthropic
def sse(model, blocks, stop, usage_in=100):
    ev = [("message_start", {"type": "message_start", "message": {
        "id": "msg_1", "type": "message", "role": "assistant", "model": model, "content": [], "stop_reason": None,
        "stop_sequence": None, "usage": {"input_tokens": usage_in, "output_tokens": 1, "cache_read_input_tokens": 40,
                                         "cache_creation_input_tokens": 60}}})]
    for i, b in enumerate(blocks):
        if b["type"] == "text":
            ev += [("content_block_start", {"type": "content_block_start", "index": i,
                                            "content_block": {"type": "text", "text": ""}}),
                   ("content_block_delta", {"type": "content_block_delta", "index": i,
                                            "delta": {"type": "text_delta", "text": b["text"]}})]
        elif b["type"] == "thinking":
            ev += [("content_block_start", {"type": "content_block_start", "index": i,
                                            "content_block": {"type": "thinking", "thinking": "", "signature": ""}}),
                   ("content_block_delta", {"type": "content_block_delta", "index": i,
                                            "delta": {"type": "signature_delta", "signature": "SIG"}})]
        elif b["type"] == "tool_use":
            ev += [("content_block_start", {"type": "content_block_start", "index": i, "content_block": {
                "type": "tool_use", "id": b["id"], "name": b["name"], "input": {}}}),
                   ("content_block_delta", {"type": "content_block_delta", "index": i, "delta": {
                       "type": "input_json_delta", "partial_json": json.dumps(b["input"])}})]
        else:
            ev += [("content_block_start", {"type": "content_block_start", "index": i, "content_block": b})]
        ev.append(("content_block_stop", {"type": "content_block_stop", "index": i}))
    delta = {"stop_reason": stop, "stop_sequence": None}
    if stop == "refusal":
        delta["stop_details"] = {"type": "refusal", "category": "cyber", "explanation": "x"}
    ev += [("message_delta", {"type": "message_delta", "delta": delta, "usage": {"output_tokens": 30}}),
           ("message_stop", {"type": "message_stop"})]
    return lambda body: (200, "text/event-stream", "".join(f"event: {e}\ndata: {json.dumps(d)}\n\n" for e, d in ev))


def test_anthropic():
    print("anthropic-api")
    fake = Fake()
    os.environ["ANTHROPIC_BASE_URL"] = f"http://127.0.0.1:{fake.port}"
    os.environ["ANTHROPIC_API_KEY"] = "test-key"
    backend = AnthropicAPI({})
    backend.check()
    log = []
    t, events = task(log, model="sonnet", effort="high")
    fake.script = [
        sse("claude-sonnet-5-5", [{"type": "thinking"}, {"type": "text", "text": "Looking at it."},
                                  {"type": "tool_use", "id": "toolu_1", "name": "look", "input": {"what": "p1"}}],
            "tool_use"),
        sse("claude-sonnet-5-5", [{"type": "tool_use", "id": "toolu_2", "name": "look", "input": {}}], "tool_use"),
        sse("claude-sonnet-5-5", [{"type": "tool_use", "id": "toolu_3", "name": "finish", "input": {}}], "tool_use"),
    ]
    out = backend.run(t)
    check(out.done and not out.error, f"task done without error ({out.error!r})")
    check(out.turns == 3 and out.model == "claude-sonnet-5-5", f"turns {out.turns}, model {out.model}")
    check(log == [("look", {"what": "p1"}), ("finish", {})], f"handlers called: {log}")
    _, path, headers, b1 = fake.posts()[0]
    check(b1["model"] == "claude-sonnet-5-5" and b1["stream"] is True, "alias resolved, streaming request")
    check(b1["thinking"] == {"type": "adaptive"} and b1["output_config"] == {"effort": "high"}, "adaptive thinking + effort")
    check(b1.get("fallbacks") == "default" and "server-side-fallback-2026-07-01" in headers.get("anthropic-beta", ""),
          "fallbacks default + beta header")
    check(b1["cache_control"] == {"type": "ephemeral"} and b1["system"][0]["cache_control"] == {"type": "ephemeral"},
          "system prompt cached + automatic caching")
    check(b1["tools"][0] == {"name": "look", "description": "Look at a page", "input_schema": t.tools[0].schema},
          "tool definitions")
    b2 = fake.posts()[1][3]
    echo, results = b2["messages"][1], b2["messages"][2]
    check([c["type"] for c in echo["content"]] == ["thinking", "text", "tool_use"]
          and echo["content"][0]["signature"] == "SIG", "assistant turn echoed with the thinking block")
    r = results["content"][0]
    check(r["type"] == "tool_result" and r["tool_use_id"] == "toolu_1" and not r["is_error"], "tool_result for the call")
    check(r["content"][0] == {"type": "text", "text": "page text"} and r["content"][1]["type"] == "image"
          and r["content"][1]["source"]["media_type"] == "image/jpeg", "tool result: text + image block")
    r3 = fake.posts()[2][3]["messages"][4]["content"][0]
    check(r3["is_error"] and "Missing arguments for look: what" in r3["content"][0]["text"], "missing argument rejected")
    check(("rejected", ("look", "Missing arguments for look: what.")) in events, "rejected event")
    check(("model", "claude-sonnet-5-5") in events and ("tool", ("look", {"what": "p1"})) in events, "model/tool events")
    entries = [json.loads(line) for line in t.log_path.read_text().splitlines()]
    check([k for e in entries for k in e if k not in ("t", "task")][:4] == ["prompt", "usage", "text", "tool_use"],
          "log entries")
    check(out.extra["usage"]["cache_read"] == 120, f"usage summed: {out.extra['usage']}")

    # refusal, no fallbacks for older models, haiku without thinking
    t, _ = task([], model="claude-haiku-4-5", effort="low")
    fake.script = [sse("claude-haiku-4-5", [], "refusal")]
    out = backend.run(t)
    check("declined" in out.error and "cyber" in out.error and not out.done, f"refusal reported: {out.error!r}")
    b = fake.posts()[-1][3]
    check("thinking" not in b and "output_config" not in b and "fallbacks" not in b, "haiku: no thinking/effort/fallbacks")

    # fallback in the middle of an answer: only text before the fallback block is echoed
    t, _ = task([], model="opus")
    fake.script = [
        sse("claude-opus-4-8", [{"type": "thinking"}, {"type": "text", "text": "partial"},
                                {"type": "fallback", "from": {"model": "claude-opus-5-5"},
                                 "to": {"model": "claude-opus-4-8"}},
                                {"type": "tool_use", "id": "toolu_9", "name": "look", "input": {"what": "x"}}],
            "tool_use"),
        sse("claude-opus-4-8", [{"type": "tool_use", "id": "toolu_10", "name": "finish", "input": {}}], "tool_use")]
    try:
        out = backend.run(t)
        echoed = [c["type"] for c in fake.posts()[-1][3]["messages"][1]["content"]]
        check(out.done and echoed == ["text", "fallback", "tool_use"], f"fallback echo: {echoed} ({out.error!r})")
    except Exception:
        traceback.print_exc()
        check(False, "fallback block handled")

    # API errors become outcome.error
    t, _ = task([], model="sonnet")
    fake.script = [lambda body: (400, "application/json", json.dumps(
        {"type": "error", "error": {"type": "invalid_request_error", "message": "bad thing"}}))]
    out = backend.run(t)
    check(out.error == "Anthropic API error 400: bad thing", f"API error: {out.error!r}")


# ------------------------------------------------------------------ OpenAI Responses
def response(model, output, status="completed"):
    body = {"id": "resp_1", "object": "response", "created_at": 0, "status": status, "model": model,
            "output": output, "parallel_tool_calls": True, "tool_choice": "auto", "tools": [],
            "incomplete_details": {"reason": "max_output_tokens"} if status == "incomplete" else None,
            "usage": {"input_tokens": 100, "input_tokens_details": {"cached_tokens": 50}, "output_tokens": 20,
                      "output_tokens_details": {"reasoning_tokens": 5}, "total_tokens": 120}}
    return lambda b: (200, "application/json", json.dumps(body))


def fcall(cid, name, args):
    return {"type": "function_call", "id": "fc_" + cid, "call_id": cid, "name": name, "arguments": args,
            "status": "completed"}


def test_openai():
    print("openai-api")
    fake = Fake()
    os.environ["OPENAI_BASE_URL"] = f"http://127.0.0.1:{fake.port}/v1"
    os.environ["OPENAI_API_KEY"] = "test-key"
    backend = OpenAIAPI({})
    backend.check()
    log = []
    t, events = task(log, effort="xhigh")
    fake.script = [
        response("gpt-6.1-sol", [
            {"type": "reasoning", "id": "rs_1", "summary": [], "encrypted_content": "ENC"},
            {"type": "message", "id": "m1", "role": "assistant", "status": "completed",
             "content": [{"type": "output_text", "text": "Looking.", "annotations": []}]},
            fcall("call_1", "look", '{"what": "p1"}')]),
        response("gpt-6.1-sol", [fcall("call_2", "look", '{"what": ')]),
        response("gpt-6.1-sol", [fcall("call_3", "finish", "{}")]),
    ]
    out = backend.run(t)
    check(out.done and not out.error and out.turns == 3, f"task done ({out.error!r}, turns {out.turns})")
    check(log == [("look", {"what": "p1"}), ("finish", {})], f"handlers: {log}")
    b1 = fake.posts()[0][3]
    check(b1["model"] == "gpt-6.1-sol" and b1["instructions"] == "SYSTEM PROMPT" and b1["store"] is False
          and b1["include"] == ["reasoning.encrypted_content"] and b1["reasoning"] == {"effort": "xhigh"},
          "request: model, instructions, stateless, effort")
    check(b1["tools"][0]["type"] == "function" and b1["tools"][0]["parameters"] == t.tools[0].schema, "function tools")
    inp = fake.posts()[1][3]["input"]
    check([i.get("type", i.get("role")) for i in inp] == ["user", "reasoning", "message", "function_call",
                                                          "function_call_output"], f"input items: {inp}")
    check(inp[1].get("encrypted_content") == "ENC", "reasoning passed back encrypted")
    o = inp[4]
    check(o["call_id"] == "call_1" and o["output"][0] == {"type": "input_text", "text": "page text"}
          and o["output"][1]["image_url"].startswith("data:image/jpeg;base64,"), "function output: text + image")
    o2 = fake.posts()[2][3]["input"][-1]
    check(o2["call_id"] == "call_2" and "not valid JSON" in o2["output"], f"invalid JSON rejected: {o2['output']!r}")
    check(out.text == "Looking." and out.extra["usage"]["cache_read"] == 150, "text and usage")

    t, _ = task([])
    fake.script = [response("gpt-6.1-sol", [], status="incomplete")]
    out = backend.run(t)
    check("cut" in out.error and "max_output_tokens" in out.error, f"incomplete reported: {out.error!r}")
    t, _ = task([])
    fake.script = [lambda body: (429, "application/json", json.dumps(
        {"error": {"message": "slow down", "type": "rate_limit", "code": None, "param": None}}))] * 5
    out = backend.run(t)
    check(out.error == "OpenAI API error 429: slow down", f"API error: {out.error!r}")
    del os.environ["OPENAI_API_KEY"]
    try:
        backend.check()
        check(False, "missing key detected")
    except SystemExit as e:
        check("OPENAI_API_KEY" in str(e), "missing key detected")


# ------------------------------------------------------------------ local (Chat Completions)
def chat(model, content=None, calls=(), finish="tool_calls"):
    msg = {"role": "assistant", "content": content}
    if calls:
        msg["tool_calls"] = [{"id": cid, "type": "function", "function": {"name": n, "arguments": a}}
                             for cid, n, a in calls]
    body = {"id": "c1", "object": "chat.completion", "created": 0, "model": model,
            "choices": [{"index": 0, "message": msg, "finish_reason": finish if calls else "stop"}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 10, "total_tokens": 60}}
    return lambda b: (200, "application/json", json.dumps(body))


def test_local():
    print("local")
    fake = Fake()
    url = f"http://127.0.0.1:{fake.port}/v1"
    backend = Local({"url": url, "model": "gemma4:12b"})
    backend.check()
    log = []
    t, _ = task(log, model="gemma4:12b", effort="max")
    fake.ps = {"models": [{"name": "gemma4:12b", "model": "gemma4:12b", "context_length": 32768}]}
    fake.script = [chat("gemma4:12b", "Looking.", [("call_a", "look", '{"what":"p1"}')]),
                   chat("gemma4:12b", None, [(None, "look", "{oops")]),
                   chat("gemma4:12b", None, [("call_c", "finish", "")])]
    out = backend.run(t)
    check(out.done and not out.error and out.turns == 3, f"task done ({out.error!r})")
    check(log == [("look", {"what": "p1"}), ("finish", {})], f"handlers: {log}")
    b1 = fake.posts()[0][3]
    check(b1["messages"][0] == {"role": "system", "content": "SYSTEM PROMPT"} and b1["reasoning_effort"] == "high",
          "system message, effort max -> high")
    check(b1["tools"][1] == {"type": "function", "function": {"name": "finish", "description": "Finish",
                                                              "parameters": {"type": "object", "properties": {}}}},
          "function tools")
    m2 = fake.posts()[1][3]["messages"]
    check([m["role"] for m in m2] == ["system", "user", "assistant", "tool", "user"], f"roles: {[m['role'] for m in m2]}")
    check(m2[3] == {"role": "tool", "tool_call_id": "call_a", "content": "page text"}, "tool message (text)")
    check(m2[4]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,"), "pictures in a user message")
    m3 = fake.posts()[2][3]["messages"]
    check(m3[5]["tool_calls"][0]["id"] == "call_1_0" and m3[6]["tool_call_id"] == "call_1_0"
          and "not valid JSON" in m3[6]["content"], "missing call id generated, invalid JSON rejected")

    # no vision: a note instead of the pictures
    nb = Local({"url": url, "model": "gemma4:12b", "vision": False})
    t, _ = task([], model="gemma4:12b")
    fake.script = [chat("gemma4:12b", None, [("c1", "look", '{"what":"p"}')]),
                   chat("gemma4:12b", None, [("c2", "finish", "{}")])]
    out = nb.run(t)
    m = fake.posts()[-1][3]["messages"]
    check(out.done and [x["role"] for x in m][-1] == "tool" and "cannot see images" in m[-1]["content"],
          "vision off: note, no pictures")

    # Ollama context smaller than what lezio sends
    fake.ps = {"models": [{"name": "gemma4:12b", "model": "gemma4:12b", "context_length": 4096}]}
    t, _ = task([], model="gemma4:12b")
    t.system = "x" * 40000
    fake.script = [chat("gemma4:12b", "hi", [("c1", "finish", "{}")])]
    out = backend.run(t)
    check("context of 4096" in out.error and not out.done, f"context too small: {out.error!r}")

    # the model stops (text only); the answer cut by length
    fake.ps = None
    t, _ = task([], model="gemma4:12b")
    fake.script = [chat("gemma4:12b", "I am done.")]
    out = backend.run(t)
    check(not out.done and not out.error and out.text == "I am done.", "text-only answer ends the task")

    # check(): model missing, server down
    try:
        Local({"url": url, "model": "qwen9"}).check()
        check(False, "missing model detected")
    except SystemExit as e:
        check("ollama pull qwen9" in str(e) and "gemma4:12b" in str(e), "missing model detected")
    fake.models = ["gemma4:latest"]
    Local({"url": url, "model": "gemma4"}).check()
    check(True, "name without tag matches :latest")
    try:
        Local({"url": "http://127.0.0.1:9/v1"}).check()
        check(False, "server down detected")
    except SystemExit as e:
        check("No model server" in str(e), "server down detected")


for test in (test_anthropic, test_openai, test_local):
    try:
        test()
    except Exception:
        traceback.print_exc()
        FAILS.append(test.__name__)
print("\nFAILED: " + ", ".join(FAILS) if FAILS else "\nALL PASSED")
sys.exit(1 if FAILS else 0)
