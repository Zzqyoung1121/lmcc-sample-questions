#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Agent 的工具层与用量计量。

工具：read_file / write_file / bash，全部限制在工作区内。
用量：按题面统计请求次数与 Token，并实现 A/B/K 评分系数。
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

MAX_OUTPUT_TOKENS = 8192
REQUESTS_PER_MESSAGE = 4
BASH_TIMEOUT_S = 60
MAX_FILE_BYTES = 200_000

# 题面：A=100,000，B=160,000，K=50%
A_TOKENS = 100_000
B_TOKENS = 160_000
K_FACTOR = 0.5

USAGE_FILE = Path(__file__).resolve().parent / "usage.json"

# 固定内容：题面、来源说明、许可证、启动脚本、测试内容不可修改
READONLY = {"README.md", "来源说明.md", "LICENSE", "server.py"}


class ToolError(Exception):
    """工具调用失败（会作为观察结果回灌给模型）。"""


class Workspace:
    """把工具操作限制在项目根目录内。"""

    def __init__(self, root: Path):
        self.root = root.resolve()
        if not self.root.is_dir():
            raise SystemExit("工作区不存在：%s" % self.root)

    def _resolve(self, raw: str) -> Path:
        if not raw:
            raise ToolError("路径不能为空")
        p = (self.root / raw).resolve() if not os.path.isabs(raw) else Path(raw).resolve()
        try:
            p.relative_to(self.root)
        except ValueError:
            raise ToolError("拒绝访问工作区外的路径：%s" % raw)
        return p

    # ---------------- 三个工具
    def read_file(self, path: str) -> str:
        p = self._resolve(path)
        if not p.is_file():
            raise ToolError("文件不存在：%s" % path)
        if p.stat().st_size > MAX_FILE_BYTES:
            raise ToolError("文件过大（>%d 字节）：%s" % (MAX_FILE_BYTES, path))
        return p.read_text(encoding="utf-8", errors="replace")

    def write_file(self, path: str, content: str) -> str:
        p = self._resolve(path)
        if p.name in READONLY and p.parent == self.root:
            raise ToolError("该文件在题面中固定，不可修改：%s" % path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return "已写入 %s（%d 字符）" % (path, len(content))

    def bash(self, command: str) -> str:
        if not command or not command.strip():
            raise ToolError("命令不能为空")
        try:
            proc = subprocess.run(
                command, shell=True, cwd=str(self.root), timeout=BASH_TIMEOUT_S,
                capture_output=True, text=True, encoding="utf-8", errors="replace",
            )
        except subprocess.TimeoutExpired:
            raise ToolError("命令超过 %d 秒未结束，已终止" % BASH_TIMEOUT_S)
        out = (proc.stdout or "") + (proc.stderr or "")
        return "退出码 %d\n%s" % (proc.returncode, out[:8000])

    def run_tool(self, name: str, args: dict) -> str:
        if name == "read_file":
            return self.read_file(args.get("path", ""))
        if name == "write_file":
            return self.write_file(args.get("path", ""), args.get("content", ""))
        if name == "bash":
            return self.bash(args.get("command", ""))
        raise ToolError("未知工具：%s" % name)


def tool_schemas() -> list[dict]:
    """OpenAI 工具调用格式的工具定义。"""
    return [
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "读取工作区内的一个文本文件，返回其内容。",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string", "description": "相对工作区的路径"}},
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "把内容写入工作区内的文件（覆盖已有内容）。",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string", "description": "相对工作区的路径"},
                        "content": {"type": "string", "description": "完整的新文件内容"},
                    },
                    "required": ["path", "content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "bash",
                "description": "在工作区内执行一条命令行指令，返回输出。"
                               "（注意：命令由系统 shell 执行；Windows 下是 cmd，请用 dir 而不是 ls。）",
                "parameters": {
                    "type": "object",
                    "properties": {"command": {"type": "string", "description": "要执行的命令"}},
                    "required": ["command"],
                },
            },
        },
    ]


class Budget:
    """按题面统计请求次数与 Token，并给出用量系数。"""

    def __init__(self, max_requests: int = 80, max_requests_per_message: int = REQUESTS_PER_MESSAGE):
        self.max_requests = max_requests
        self.max_requests_per_message = max_requests_per_message
        self.requests = 0
        self.prompt_tokens = 0
        self.completion_tokens = 0
        self.last_usage: dict = {}

    @property
    def tokens(self) -> int:
        return self.prompt_tokens + self.completion_tokens

    def exhausted(self) -> bool:
        return self.requests >= self.max_requests or self.tokens >= B_TOKENS

    def record(self, usage: dict | None):
        usage = usage or {}
        self.requests += 1
        self.prompt_tokens += int(usage.get("prompt_tokens", 0) or 0)
        self.completion_tokens += int(usage.get("completion_tokens", 0) or 0)

    def factor(self) -> float:
        t = self.tokens
        if t <= A_TOKENS:
            return 1.0
        if t >= B_TOKENS:
            return K_FACTOR
        return 1.0 - K_FACTOR * (t - A_TOKENS) / (B_TOKENS - A_TOKENS)

    def final_score(self, raw_score: float) -> float:
        """题面：最终只四舍五入一次，保留两位小数。"""
        return round(raw_score * self.factor(), 2)

    def save(self):
        USAGE_FILE.write_text(json.dumps({
            "requests": self.requests,
            "promptTokens": self.prompt_tokens,
            "completionTokens": self.completion_tokens,
            "tokens": self.tokens,
            "factor": round(self.factor(), 4),
        }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def call_model(client, messages: list, tools: list, budget: Budget, model: str) -> dict:
    """调用模型。用量未知时明确报错，不按 0 记。"""
    resp = client.chat.completions.create(
        model=model,
        messages=messages,
        tools=tools,
        temperature=0.2,
        max_tokens=MAX_OUTPUT_TOKENS,
    )
    dumped = resp.model_dump()
    usage = dumped.get("usage")
    if not usage:
        raise SystemExit("模型未返回用量信息，按题面要求暂停核对（不记 0 Token）")
    budget.last_usage = usage
    return dumped
