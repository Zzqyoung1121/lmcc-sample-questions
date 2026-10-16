# LMCC 第二轮机考例题 · 本地练习包（T1 + T2）

由 `LMCC-机考三题例题文档.pdf`（《LMCC 第二轮例题 · 考生版》）整理而成，还原成可以直接动手做的题目。

**目录约定与官方例题包一致：`T1/T1`、`T2/T2` 是给考生的文件；上一级的同名文件是参考答案。**

## 三道题总览（本包只建了 T1 和 T2）

| 题目与模型 | 你需要完成的部分 | 可见测试点及分值 | 不可见测试点及分值 |
| --- | --- | --- | --- |
| **第一题 校园助手的信息分类**<br>Prompt 调优 · Qwen3-0.6B | 编写 System Prompt，并选择是否开启 thinking。只提交提示词和设置，无需编写模型调用代码。 | 5 点 × 10 分 = 50 分 | 5 点 × 10 分 = 50 分 |
| **第二题 括号序列判定**<br>LoRA 训练 · Qwen3-0.6B | 构造并标注 1 至 100 条括号序列；实现 `process_data(records)`；填写训练参数。提交数据、函数与参数三份文件，由平台进行 8GiB 显存配额内的训练。 | 函数 2 点 / 20 分<br>模型 4 点 / 40 分 = 60 分 | 模型 4 点 × 10 分 = 40 分 |
| 第三题 TodoMVC 作业安排<br>Vibe Coding · Qwen3.5-35B-A3B | 与考场极简编程 Agent 对话，实现科目设置、组合筛选、可见作业移动及刷新保存。 | 5 点 × 10 分 = 50 功能分 | 5 点 × 10 分 = 50 功能分 |

> **API 获取条件：第一题、第二题均确认提交后，才能获得 Qwen3.5-35B-A3B 的 API 使用权限。**
>
> 每题原始满分均为 100 分。可见测试会提供完整输入或操作、标准答案或预期结果及现场反馈；不可见测试在考试期间不展示，考试结束后统一评测锁定版本。
>
> - **第一题**：公开调试用于修改 Prompt；正式成绩在考后对全部 10 点统一评测。每点调用 3 次，至少 2 次正确才得 10 分。
> - **第二题**：2 个函数点训练前反馈，4 个公开模型点在训练完成、保存并重载后反馈；另 4 个模型点考后评测。
> - **第三题**：用量不超过 A=100,000 Token 时保留原分；从 A 到 B=160,000 Token 线性衰减，达到 B 时系数为 K=50%（暂定）。每点的两个子场景全部通过才得 10 分。

## 目录结构

```text
LMCC-机考例题/
├── README.md                    本文件
├── T1/
│   ├── T1/                      ← 考生文件（在这里作答）
│   │   ├── README.md            题面
│   │   ├── system_prompt.txt    【作答】System Prompt 正文（≤300 Token）
│   │   ├── config.json          【作答】thinking 开关
│   │   ├── evaluate.py          本地自测脚本
│   │   └── data/public_tests.json
│   ├── system_prompt.txt        参考答案
│   └── config.json              参考答案
└── T2/
    ├── T2/                      ← 考生文件（在这里作答）
    │   ├── README.md            题面
    │   ├── train.jsonl          【作答 1】1–100 条原始标注数据
    │   ├── submission.py        【作答 2】process_data(records)
    │   ├── training_params.json 【作答 3】五项训练参数
    │   ├── evaluate.py          本地自测
    │   ├── train_lora.py        可选：本地 LoRA 训练脚本
    │   └── data/
    │       ├── public_function_tests.json
    │       ├── extra_function_tests.json
    │       └── public_model_tests.json
    ├── train.jsonl              参考答案（100 条，标签已校验）
    ├── submission.py            参考答案
    └── training_params.json     参考答案
```

## 怎么练

**T1（不需要 GPU，需要模型或 API）**

```bash
cd T1/T1
python evaluate.py                                # 离线：查 Prompt 长度和格式
python evaluate.py --backend openai               # 调 OpenAI 兼容接口真实跑分
python evaluate.py --backend local --model <Qwen3-0.6B 路径>
```

**T2（函数部分不需要 GPU）**

```bash
cd T2/T2
python evaluate.py                                          # P01/P02 + 边界用例 + 数据/参数检查
python train_lora.py --model Qwen/Qwen3-0.6B --out ./lora_out   # 可选，需要 GPU + peft
python evaluate.py --model-tests --adapter ./lora_out        # M01–M04
```

想对照参考答案，把 `T2/` 下的 `train.jsonl`、`submission.py`、`training_params.json` 复制进 `T2/T2/` 再跑 `evaluate.py`，应当全部 PASS。

## 本包与原 PDF 的差异

- 原 PDF 只有题面文字，**没有配套文件**；本包按题面补齐了三份作答文件的模板、公开测试数据文件和本地评测脚本。
- `data/extra_function_tests.json` 是按题面第四条规则**自行补充**的边界用例，属于本地自测，不是官方公开测试点。
- 第三题（Vibe Coding）按要求未建。它依赖考场内的 Agent 环境，无法在本地还原。
