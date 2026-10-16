#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T2 括号序列判定 —— 本地自测脚本（不参与提交）。

默认跑：
    1) 公开数据处理测试点 P01 / P02
    2) 按题面规则补充的边界用例 E01–E06
    3) train.jsonl 格式与规模检查 + 过一遍 process_data
    4) training_params.json 取值范围检查

加 --model-tests 才跑 M01–M04（需要 transformers + peft + 训练好的 LoRA）。

用法：
    python evaluate.py
    python evaluate.py --model-tests --model Qwen/Qwen3-0.6B --adapter ./lora_out
"""

from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import sys
from pathlib import Path

try:  # Windows 控制台默认可能是 GBK
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"

MAX_CODE_BYTES = 16 * 1024
MAX_TRAIN_BYTES = 256 * 1024
PUBLIC_MODEL_INPUTS = {"(()(()()))", "((())())()", "())(()())(", "((()())())("}


# ---------------------------------------------------------------- 加载
def load_module():
    path = HERE / "submission.py"
    if not path.exists():
        sys.exit("找不到 submission.py")
    spec = importlib.util.spec_from_file_location("t2_submission", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    if not hasattr(mod, "process_data"):
        sys.exit("submission.py 里没有定义 process_data")
    return mod


def load_json(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def is_valid_sequence(seq: str) -> bool:
    bal = 0
    for ch in seq:
        bal += 1 if ch == "(" else -1
        if bal < 0:
            return False
    return bal == 0


# ---------------------------------------------------------------- 函数测试
def check_point(process_data, pt):
    records = copy.deepcopy(pt["records"])
    expect_error = pt.get("expect_error")
    expected = pt.get("expected")
    try:
        got = process_data(records)
        err = None
    except ValueError as exc:
        got, err = None, exc
    except Exception as exc:  # noqa: BLE001
        return False, "抛出了非 ValueError 的异常：%r" % (exc,)

    if expect_error:
        if err is not None:
            return True, "按预期抛出 ValueError"
        return False, "期望抛出 %s，实际返回 %r" % (expect_error, got)
    if err is not None:
        return False, "不应抛异常，却抛出 %r" % (err,)
    if got == expected:
        return True, "返回与期望一致"
    return False, "期望 %s，实际 %s" % (
        json.dumps(expected, ensure_ascii=False),
        json.dumps(got, ensure_ascii=False),
    )


def run_function_tests(mod):
    public = load_json("public_function_tests.json")
    extra = load_json("extra_function_tests.json")

    print("=" * 72)
    print("第一部分：数据处理函数")
    print("=" * 72)
    score = 0
    for pt in public["points"]:
        ok, msg = check_point(mod.process_data, pt)
        score += pt["score"] if ok else 0
        print("[%s] %s（%d 分）— %s" % ("PASS" if ok else "FAIL", pt["id"], pt["score"], msg))
    print("-" * 72)
    print("公开函数点得分：%d / %d" % (score, sum(p["score"] for p in public["points"])))

    print()
    print("=" * 72)
    print("附加：按题面规则推导的边界用例（非官方测试点）")
    print("=" * 72)
    bad = 0
    for pt in extra["points"]:
        ok, msg = check_point(mod.process_data, pt)
        bad += 0 if ok else 1
        print("[%s] %s %s — %s" % ("PASS" if ok else "FAIL", pt["id"], pt["desc"], msg))
    if bad:
        print("\n有 %d 个边界用例未通过，建议对照题面第四条逐条检查。" % bad)
    return score, bad


# ---------------------------------------------------------------- 数据/参数
def run_data_checks(mod):
    print()
    print("=" * 72)
    print("第二部分：train.jsonl 与 training_params.json")
    print("=" * 72)

    ok_all = True
    path = HERE / "train.jsonl"
    if not path.exists():
        print("[FAIL] 找不到 train.jsonl")
        return

    raw_bytes = path.stat().st_size
    lines = [ln for ln in path.read_text(encoding="utf-8").splitlines() if ln.strip()]

    size_ok = raw_bytes <= MAX_TRAIN_BYTES
    ok_all &= size_ok
    print("[%s] 文件大小 %d B / 上限 %d B" % ("PASS" if size_ok else "FAIL", raw_bytes, MAX_TRAIN_BYTES))

    count_ok = 1 <= len(lines) <= 100
    ok_all &= count_ok
    print("[%s] 原始记录 %d 条（要求 1–100）" % ("PASS" if count_ok else "FAIL", len(lines)))

    records, parse_errors = [], []
    for i, ln in enumerate(lines, 1):
        try:
            obj = json.loads(ln)
        except Exception as exc:  # noqa: BLE001
            parse_errors.append((i, "不是合法 JSON：%s" % exc))
            continue
        if not isinstance(obj, dict):
            parse_errors.append((i, "不是 JSON 对象"))
            continue
        if not isinstance(obj.get("sequence"), str) or not isinstance(obj.get("valid"), str):
            parse_errors.append((i, "sequence / valid 必须是字符串"))
            continue
        records.append(obj)

    if parse_errors:
        ok_all = False
        for i, m in parse_errors[:10]:
            print("[FAIL] 第 %d 行：%s" % (i, m))
    else:
        print("[PASS] 每行都是合法 JSON 对象，且 sequence / valid 均为字符串")

    # 过一遍 process_data
    try:
        processed = mod.process_data(copy.deepcopy(records))
    except Exception as exc:  # noqa: BLE001
        print("[FAIL] process_data 在 train.jsonl 上抛异常：%r" % (exc,))
        return
    pcount_ok = 1 <= len(processed) <= 100
    ok_all &= pcount_ok
    print("[%s] 处理后保留 %d 条（训练要求 1–100）" % ("PASS" if pcount_ok else "FAIL", len(processed)))

    # 泄漏检查
    leak = [p["input"] for p in processed
            if p["input"].startswith("序列：") and p["input"][3:] in PUBLIC_MODEL_INPUTS]
    if leak:
        ok_all = False
        print("[FAIL] 训练集里出现了公开模型测试点的完整输入：%s" % leak)
    else:
        print("[PASS] 没有把 M01–M04 的完整输入放进训练集")

    # 标签自检（非官方判分，但标签不可靠直接毁掉训练）
    wrong = [p for p in processed
             if p["output"].endswith("YES") != is_valid_sequence(p["input"][3:])]
    if wrong:
        print("[WARN] 有 %d 条标签与括号序列的真实合法性不符，例如：" % len(wrong))
        for p in wrong[:5]:
            seq = p["input"][3:]
            print("       %s  你标的是 %s，实际应为 %s"
                  % (seq, p["output"][-3:], "YES" if is_valid_sequence(seq) else "NO"))
    else:
        print("[PASS] 全部标签与括号序列的真实合法性一致")
    ok_all &= not wrong

    # 覆盖度提示
    lens = sorted({len(p["input"]) - 3 for p in processed})
    bad_causes = 0
    for p in processed:
        if p["output"].endswith("NO"):
            seq = p["input"][3:]
            bal = 0
            neg = False
            for ch in seq:
                bal += 1 if ch == "(" else -1
                if bal < 0:
                    neg = True
            if neg and bal == 0:
                bad_causes += 1
    print("[i  ] 长度覆盖 %s；其中「数量相等但顺序错误」的不合法样本 %d 条"
          % (lens, bad_causes))
    if not bad_causes:
        print("       题面提醒：不要让「左右数量相等」成为判断合法的唯一线索，建议补几条这种样本。")

    # 参数检查
    print()
    ppath = HERE / "training_params.json"
    rules = {
        "epochs": ("int", 1, 12, None),
        "learningRate": ("float", 1e-5, 5e-4, None),
        "loraRank": ("int", None, None, {4, 8, 16}),
        "batchSize": ("int", 1, 1, None),
        "gradAccum": ("int", None, None, {4, 8, 16}),
    }
    try:
        params = json.loads(ppath.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        print("[FAIL] training_params.json 读取失败：%s" % exc)
        return
    for key, (kind, lo, hi, choices) in rules.items():
        if key not in params:
            ok_all = False
            print("[FAIL] %s 缺失" % key)
            continue
        val = params[key]
        if kind == "int" and not isinstance(val, int):
            ok_all = False
            print("[FAIL] %s 必须是整数，实际 %r" % (key, val))
            continue
        if kind == "float" and not isinstance(val, (int, float)):
            ok_all = False
            print("[FAIL] %s 必须是数字，实际 %r" % (key, val))
            continue
        if choices is not None and val not in choices:
            ok_all = False
            print("[FAIL] %s=%r 不在允许值 %s 内" % (key, val, sorted(choices)))
        elif lo is not None and not (lo <= val <= hi):
            ok_all = False
            print("[FAIL] %s=%r 超出范围 [%s, %s]" % (key, val, lo, hi))
        else:
            print("[PASS] %s=%r" % (key, val))

    print()
    print("=" * 72)
    print("本地自测结论：%s（公开模型测试 M01–M04 需要训练后另行运行）"
          % ("全部通过" if ok_all else "存在问题，见上方 FAIL/WARN"))
    print("=" * 72)


# ---------------------------------------------------------------- 模型测试
def run_model_tests(model_path, adapter_path):
    print()
    print("=" * 72)
    print("第三部分：公开模型测试点（需要训练好的 LoRA）")
    print("=" * 72)
    try:
        import torch  # type: ignore
        from peft import PeftModel  # type: ignore
        from transformers import AutoModelForCausalLM, AutoTokenizer  # type: ignore
    except Exception as exc:  # noqa: BLE001
        sys.exit("缺少依赖（需要 transformers + peft + torch）：%s" % exc)

    spec = load_json("public_model_tests.json")
    tok = AutoTokenizer.from_pretrained(model_path)
    net = AutoModelForCausalLM.from_pretrained(model_path, dtype=torch.float32)
    if adapter_path:
        net = PeftModel.from_pretrained(net, adapter_path)
    net.eval()

    score = 0
    for pt in spec["points"]:
        messages = [
            {"role": "system", "content": spec["system_prompt"]},
            {"role": "user", "content": pt["input"]},
        ]
        text = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        ids = tok(text, return_tensors="pt").to(net.device)
        with torch.no_grad():
            out = net.generate(**ids, do_sample=False,
                               max_new_tokens=spec.get("max_new_tokens", 128))
        got = tok.decode(out[0][ids["input_ids"].shape[1]:], skip_special_tokens=True).strip()
        ok = got == pt["answer"]
        score += pt["score"] if ok else 0
        print("[%s] %s 输入 %s -> %r（期望 %r）"
              % ("PASS" if ok else "FAIL", pt["id"], pt["input"], got, pt["answer"]))
    print("-" * 72)
    print("公开模型点得分：%d / %d" % (score, sum(p["score"] for p in spec["points"])))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model-tests", action="store_true", help="额外运行 M01–M04")
    ap.add_argument("--model", default="Qwen/Qwen3-0.6B", help="基座模型路径或 HF id")
    ap.add_argument("--adapter", default="", help="LoRA 输出目录")
    args = ap.parse_args()

    code_bytes = (HERE / "submission.py").stat().st_size
    print("[i ] submission.py 代码大小 %d B / 上限 %d B" % (code_bytes, MAX_CODE_BYTES))
    if code_bytes > MAX_CODE_BYTES:
        print("[FAIL] 超过 16KiB 限制")

    mod = load_module()
    run_function_tests(mod)
    run_data_checks(mod)
    if args.model_tests:
        run_model_tests(args.model, args.adapter)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
