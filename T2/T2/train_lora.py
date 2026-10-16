#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""T2 括号序列判定 —— 可选的本地 LoRA 训练脚本。

考试平台上模型安装、训练代码和显存调度都由平台提供，**你不必自己写训练程序**。
这个脚本只是为了让你在本地把整条链路跑通：train.jsonl -> process_data -> LoRA -> M01–M04。

依赖（本地安装）：
    pip install torch transformers peft accelerate

用法：
    python train_lora.py --model Qwen/Qwen3-0.6B --out ./lora_out
    python evaluate.py --model-tests --model Qwen/Qwen3-0.6B --adapter ./lora_out

显存：0.6B 模型 + LoRA + batchSize=1 约 2–3GiB，8GiB 配额够用。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

# 平台固定系统提示词（只读，不能修改）
SYSTEM_PROMPT = (
    "判断序列是否合法：从左到右任意前缀左括号数不能少于右括号，最终两者数目相等。"
    "合法只输出[Valid]: YES，否则只输出[Valid]: NO，冒号后一个半角空格，不加解释。"
)


def load_process_data():
    spec = importlib.util.spec_from_file_location("t2_submission", HERE / "submission.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.process_data


def load_records():
    lines = [ln for ln in (HERE / "train.jsonl").read_text(encoding="utf-8").splitlines() if ln.strip()]
    return [json.loads(ln) for ln in lines]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="Qwen/Qwen3-0.6B")
    ap.add_argument("--out", default=str(HERE / "lora_out"))
    ap.add_argument("--max-length", type=int, default=512, help="题面：每条最多 512 Token")
    args = ap.parse_args()

    try:
        import torch  # type: ignore
        from peft import LoraConfig, get_peft_model  # type: ignore
        from transformers import (AutoModelForCausalLM, AutoTokenizer,  # type: ignore
                                  Trainer, TrainingArguments)
    except Exception as exc:  # noqa: BLE001
        sys.exit("缺少依赖（pip install torch transformers peft accelerate）：%s" % exc)

    params = json.loads((HERE / "training_params.json").read_text(encoding="utf-8"))
    records = load_records()
    processed = load_process_data()(records)
    if not 1 <= len(processed) <= 100:
        sys.exit("process_data 处理后只剩 %d 条，训练要求 1–100 条" % len(processed))

    tok = AutoTokenizer.from_pretrained(args.model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    samples = []
    for item in processed:
        prompt_msgs = [{"role": "system", "content": SYSTEM_PROMPT},
                       {"role": "user", "content": item["input"]}]
        prompt_text = tok.apply_chat_template(prompt_msgs, tokenize=False, add_generation_prompt=True)
        full_text = prompt_text + item["output"] + (tok.eos_token or "")
        prompt_ids = tok(prompt_text, add_special_tokens=False)["input_ids"]
        full = tok(full_text, add_special_tokens=False, truncation=True,
                   max_length=args.max_length)["input_ids"]
        labels = list(full)
        for i in range(min(len(prompt_ids), len(labels))):
            labels[i] = -100          # 只在答案部分计算 loss
        samples.append({"input_ids": full, "labels": labels,
                        "attention_mask": [1] * len(full)})

    def collate(batch):
        width = max(len(b["input_ids"]) for b in batch)
        out = {"input_ids": [], "labels": [], "attention_mask": []}
        for b in batch:
            pad = width - len(b["input_ids"])
            out["input_ids"].append(b["input_ids"] + [tok.pad_token_id] * pad)
            out["labels"].append(b["labels"] + [-100] * pad)
            out["attention_mask"].append(b["attention_mask"] + [0] * pad)
        return {k: torch.tensor(v, dtype=torch.long) for k, v in out.items()}

    net = AutoModelForCausalLM.from_pretrained(args.model, dtype=torch.float32)
    net = get_peft_model(net, LoraConfig(
        r=params["loraRank"],
        lora_alpha=params["loraRank"] * 2,
        lora_dropout=0.0,
        bias="none",
        task_type="CAUSAL_LM",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
    ))
    net.print_trainable_parameters()
    use_cuda = torch.cuda.is_available()
    print("设备：%s，样本数：%d" % ("CUDA" if use_cuda else "CPU（会很慢）", len(samples)))

    targs = TrainingArguments(
        output_dir=args.out,
        num_train_epochs=params["epochs"],
        learning_rate=params["learningRate"],
        per_device_train_batch_size=params["batchSize"],
        gradient_accumulation_steps=params["gradAccum"],
        lr_scheduler_type="cosine",
        warmup_ratio=0.1,
        logging_steps=1,
        save_strategy="no",
        report_to=[],
        fp16=use_cuda,
        remove_unused_columns=False,
        dataloader_pin_memory=False,
    )
    Trainer(model=net, args=targs, train_dataset=samples, data_collator=collate).train()
    net.save_pretrained(args.out)
    tok.save_pretrained(args.out)
    print("LoRA 已保存到 %s" % args.out)
    print("下一步：python evaluate.py --model-tests --model %s --adapter %s" % (args.model, args.out))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
