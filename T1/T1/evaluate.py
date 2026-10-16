#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T1 校园助手的信息分类 —— 本地自测脚本（不参与提交）。

用法：
    python evaluate.py                                # 离线检查（默认）
    python evaluate.py --backend openai               # OpenAI 兼容接口
    python evaluate.py --backend local --model <dir>  # 本地 Qwen3-0.6B 权重
    python evaluate.py --assemble                     # 只打印送进模型的完整消息

环境变量（openai 后端）：
    OPENAI_BASE_URL   例如 https://api.example.com/v1
    OPENAI_API_KEY
    T1_MODEL          模型名，默认 Qwen3-0.6B
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.request
from pathlib import Path

try:  # Windows 控制台默认可能是 GBK
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

HERE = Path(__file__).resolve().parent
PROMPT_FILE = HERE / "system_prompt.txt"
CONFIG_FILE = HERE / "config.json"
TESTS_FILE = HERE / "data" / "public_tests.json"

ALLOWED = {"[Route]: ACCOUNT", "[Route]: BILLING", "[Route]: OTHER"}


def load_submission():
    if not PROMPT_FILE.exists():
        sys.exit("找不到 system_prompt.txt")
    prompt = PROMPT_FILE.read_text(encoding="utf-8").strip()
    thinking = False
    if CONFIG_FILE.exists():
        try:
            cfg = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
            thinking = bool(cfg.get("thinking", False))
        except Exception as exc:  # noqa: BLE001
            sys.exit("config.json 不是合法 JSON：%s" % exc)
    return prompt, thinking


def load_tests():
    data = json.loads(TESTS_FILE.read_text(encoding="utf-8"))
    return data


def count_tokens(prompt: str) -> tuple[int | None, str]:
    """优先用本地已有的 Qwen 分词器精确计数，否则退回粗估（不联网）。"""
    name = os.environ.get("T1_TOKENIZER", "")
    if name:
        try:
            from transformers import AutoTokenizer  # type: ignore
            tok = AutoTokenizer.from_pretrained(name, local_files_only=True)
            return len(tok.encode(prompt, add_special_tokens=False)), "Qwen 分词器（%s）" % name
        except Exception as exc:  # noqa: BLE001
            print("[i ] 没能加载本地分词器 %s：%s" % (name, exc))
    # 经验值：Qwen 对中文约 1.5 字/token，英文约 4 字符/token
    cjk = len(re.findall(r"[\u4e00-\u9fff]", prompt))
    other = len(prompt) - cjk
    return int(cjk / 1.5 + other / 4) + 1, "粗估（设 T1_TOKENIZER 指向本地分词器可精确计数）"


def check_prompt(prompt: str, limit: int) -> bool:
    ok = True
    print("=" * 68)
    print("System Prompt 离线检查")
    print("=" * 68)
    if not prompt:
        print("[X] Prompt 为空，平台会在调用前直接拒绝")
        return False
    n, how = count_tokens(prompt)
    flag = "OK" if n is not None and n <= limit else "X "
    print("[%s] 长度：%d Token / 上限 %d（%s）" % (flag, n, limit, how))
    if n is not None and n > limit:
        ok = False
    bad = sorted({ln.strip() for ln in prompt.splitlines()
                  if ln.strip().startswith("[Route]:") and ln.strip() not in ALLOWED})
    if bad:
        print("[X ] Prompt 里出现了非法的输出行：%s" % bad)
        ok = False
    else:
        print("[OK] Prompt 中出现的 [Route]: 行都合法")
    print("[i ] 字符数 %d，行数 %d" % (len(prompt), len(prompt.splitlines())))
    return ok


def build_messages(system_prompt: str, user_input: str, thinking: bool):
    system = system_prompt
    if thinking:
        system = system + "\n\n可以先用  thinking...<｜end▁of▁thinking｜> 形式进行思考，但最终回答必须严格遵守上面的输出格式。"
    return [
        {"role": "system", "content": system},
        {"role": "user", "content": user_input},
    ]


def call_openai(messages, model, thinking):
    base = (os.environ.get("OPENAI_BASE_URL") or "").rstrip("/")
    key = os.environ.get("OPENAI_API_KEY") or ""
    if not base:
        sys.exit("未设置 OPENAI_BASE_URL")
    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.0,
        "max_tokens": 768,
    }
    if thinking:
        payload["enable_thinking"] = True
    req = urllib.request.Request(
        base + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": "Bearer " + key},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"] or ""


_LOCAL = {}


def call_local(messages, model_path, thinking):
    import torch  # type: ignore
    from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore
    if not _LOCAL:
        tok = AutoTokenizer.from_pretrained(model_path)
        net = AutoModelForCausalLM.from_pretrained(model_path, dtype=torch.float32)
        net.eval()
        _LOCAL["tok"], _LOCAL["net"] = tok, net
    tok, net = _LOCAL["tok"], _LOCAL["net"]
    text = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    ids = tok(text, return_tensors="pt").to(net.device)
    with torch.no_grad():
        out = net.generate(**ids, do_sample=False, max_new_tokens=768)
    return tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True)


def strip_thinking(text: str) -> str:
    return re.sub(r"(?s) thinking.*?<｜end▁of▁thinking｜>", "", text).strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["offline", "openai", "local"], default="offline")
    ap.add_argument("--model", default=os.environ.get("T1_MODEL", "Qwen3-0.6B"))
    ap.add_argument("--repeat", type=int, default=1,
                    help="每个点调用几次；正式规则是 3 次里至少 2 次正确")
    ap.add_argument("--assemble", action="store_true",
                    help="只打印送进模型的完整 system 消息，用于检查拼接结果")
    args = ap.parse_args()

    prompt, thinking = load_submission()
    tests = load_tests()
    limit = tests.get("max_prompt_tokens", 300)
    check_prompt(prompt, limit)

    if args.assemble:
        print("\n" + "=" * 68 + "\n送给模型的 system 消息\n" + "=" * 68)
        print(build_messages(prompt, "（用户输入放这里）", thinking)[0]["content"])
        return 0
    if args.backend == "offline":
        print("\n离线模式结束。加 --backend openai 或 --backend local 才能真正跑分。")
        return 0
    if args.backend == "local" and args.model == "Qwen3-0.6B":
        sys.exit("--backend local 需要 --model 指向本地权重目录或 HF id")

    print("\n" + "=" * 68)
    print("公开测试点（%s 后端，每点 %d 次）" % (args.backend, args.repeat))
    print("=" * 68)
    print("%-5s %-6s %-9s %s" % ("点", "结果", "模型答案", "输入"))
    total = 0
    for pt in tests["points"]:
        hits = 0
        outs = []
        for _ in range(args.repeat):
            msgs = build_messages(prompt, pt["input"], thinking)
            if args.backend == "openai":
                raw = call_openai(msgs, args.model, thinking)
            else:
                raw = call_local(msgs, args.model, thinking)
            got = strip_thinking(raw)
            outs.append(got)
            if got == pt["answer"]:
                hits += 1
        need = 2 if args.repeat >= 3 else 1
        passed = hits >= need
        total += pt["score"] if passed else 0
        print("%-5s %-6s %-9s %s" % (
            pt["id"],
            "PASS" if passed else "FAIL",
            repr(outs[0])[:40],
            pt["input"][:28],
        ))
        if not passed:
            print("      期望: %r  实际: %r" % (pt["answer"], outs[0]))
    print("-" * 68)
    print("公开点得分：%d / %d（隐藏点 50 分考后统一评测）"
          % (total, sum(p["score"] for p in tests["points"])))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
