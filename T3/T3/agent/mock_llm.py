#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""一个最小的 OpenAI 兼容 mock 端点，用于在没有真实模型时验证 Agent 的工具链路。

它按固定脚本依次返回工具调用，不依赖任何模型：
    第 1 轮 -> read_file("src/model.js")
    第 2 轮 -> bash("ls src")
    第 3 轮 -> write_file(".agent-probe.txt", "ok")
    第 4 轮 -> 纯文本结束

用法：
    python mock_llm.py            # 默认 8000 端口
    python mock_llm.py --port 8123
"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

SCRIPT = [
    {"tool": "read_file", "args": {"path": "src/model.js"}},
    {"tool": "bash", "args": {"command": "ls src"}},
    {"tool": "write_file", "args": {"path": ".agent-probe.txt", "content": "ok"}},
    {"text": "已完成：读取了 model.js，列出了 src，并写入了探针文件。"},
]


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        body = json.loads(self.rfile.read(length) or b"{}")
        messages = body.get("messages", [])
        # 用「已经返回过几个 tool 结果」来决定下一步
        tool_results = sum(1 for m in messages if m.get("role") == "tool")
        step = SCRIPT[min(tool_results, len(SCRIPT) - 1)]

        if "tool" in step:
            message = {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call_%d" % tool_results,
                    "type": "function",
                    "function": {
                        "name": step["tool"],
                        "arguments": json.dumps(step["args"], ensure_ascii=False),
                    },
                }],
            }
        else:
            message = {"role": "assistant", "content": step["text"]}

        payload = {
            "id": "chatcmpl-mock",
            "object": "chat.completion",
            "model": body.get("model", "mock"),
            "choices": [{"index": 0, "message": message, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 100, "completion_tokens": 20, "total_tokens": 120},
        }
        data = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8000)
    args = ap.parse_args()
    srv = HTTPServer(("127.0.0.1", args.port), Handler)
    print("mock endpoint: http://127.0.0.1:%d/v1" % args.port, flush=True)
    srv.serve_forever()


if __name__ == "__main__":
    main()
