#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T3 考场极简编程 Agent（本地版）。

题面要求：Agent 具备 read_file、write_file、bash 三个工具，
可以在本题离线工作区读取和修改文件、执行项目内命令。

本实现是**自造的本地复刻**（考场用的是 Qwen3.5-35B-A3B + 平台自研 Agent）。
模型通过 OpenAI 兼容接口接入，默认指向本机 vLLM / Ollama / LM Studio 之类
暴露的端点，可用 --base-url / --model 覆盖。

用法：
    python run_agent.py                      # 交互式对话
    python run_agent.py --once "你的第一句话"   # 只跑一轮，便于脚本化

限额（按题面）：
    * 每次模型输出最多 8192 Token
    * 每条学生消息最多触发 4 次模型请求
    * 整题最多 80 次请求
    * 单条工具命令最长 60 秒
    * 工作区不能联网（工具层不做网络拦截，靠题目约束）
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

from agent import Budget, ToolError, Workspace, call_model, tool_schemas  # noqa: E402

SYSTEM_PROMPT = """你是考场里的极简编程 Agent，帮助考生改造一个 TodoMVC 小项目。

你可以使用三个工具：
- read_file(path)：读取工作区内的文件
- write_file(path, content)：写入工作区内的文件（会覆盖）
- bash(command)：在工作区内执行命令

规则：
1. 只能修改工作区内的文件；工作区外的路径会被拒绝。
2. 考生只能通过与你对话来修改项目，你要主动读代码、定位问题、动手改。
3. 改完以后简要说明你改了什么文件、改了什么行为。
4. 不要编造文件内容，先 read_file 看清楚再改。
5. 用中文回答。
"""


def run_turn(client, messages, workspace, budget, tools_schema, model, verbose=True):
    """执行一条学生消息引发的若干次模型请求 + 工具调用。"""
    for _ in range(budget.max_requests_per_message):
        if budget.exhausted():
            print("[余额已用尽] 停止模型调用，保留当前作品。")
            return messages
        raw = call_model(client, messages, tools_schema, budget, model)
        budget.record(budget.last_usage)
        msg = raw["choices"][0]["message"]
        messages.append(msg)

        calls = msg.get("tool_calls") or []
        if not calls:
            if verbose and msg.get("content"):
                print("\nAgent：%s\n" % msg["content"])
            return messages

        for call in calls:
            fn = call["function"]["name"]
            try:
                args = json.loads(call["function"]["arguments"] or "{}")
            except json.JSONDecodeError as exc:
                result = "参数不是合法 JSON：%s" % exc
            else:
                try:
                    result = workspace.run_tool(fn, args)
                except ToolError as exc:
                    result = "工具错误：%s" % exc
            if verbose:
                print("  [工具] %s(%s) -> %s" % (
                    fn, json.dumps(args, ensure_ascii=False)[:120], str(result)[:200]))
            messages.append({
                "role": "tool",
                "tool_call_id": call.get("id", fn),
                "content": str(result)[:8000],
            })
    return messages


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-url", default=os.environ.get("LLM_BASE_URL", "http://127.0.0.1:8000/v1"))
    ap.add_argument("--model", default=os.environ.get("LLM_MODEL", "Qwen3-35B"))
    ap.add_argument("--api-key", default=os.environ.get("LLM_API_KEY", "EMPTY"))
    ap.add_argument("--workspace", default=str(Path(__file__).resolve().parents[1] / "project"))
    ap.add_argument("--max-requests", type=int, default=80, help="整题请求上限")
    ap.add_argument("--once", default="", help="只跑一轮，内容是这句话")
    args = ap.parse_args()

    workspace = Workspace(Path(args.workspace))
    budget = Budget(max_requests=args.max_requests)
    from openai import OpenAI  # 延迟导入，便于无依赖时给出清晰提示
    client = OpenAI(base_url=args.base_url, api_key=args.api_key)

    print("工作区：%s" % workspace.root)
    print("模型：%s @ %s" % (args.model, args.base_url))
    print("请求上限：%d，每条消息最多 %d 次模型请求\n" % (
        budget.max_requests, budget.max_requests_per_message))

    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if args.once:
        messages.append({"role": "user", "content": args.once})
        run_turn(client, messages, workspace, budget, tool_schemas(), args.model)
        budget.save()
        return 0

    while True:
        try:
            line = input("你：").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not line:
            continue
        if line in ("/quit", "/exit"):
            break
        messages.append({"role": "user", "content": line})
        run_turn(client, messages, workspace, budget, tool_schemas(), args.model)
    budget.save()
    print("用量：%d 次请求，%d Token" % (budget.requests, budget.tokens))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
