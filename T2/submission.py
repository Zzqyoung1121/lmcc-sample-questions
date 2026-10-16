"""T2 括号序列判定 —— 数据处理函数（参考答案）。

只做格式清洗和标签复制，不做任何括号合法性判断。
"""


def process_data(records):
    """清洗并规范化原始记录，按原始顺序返回标准记录列表。"""
    if not isinstance(records, list):
        raise ValueError("records 必须是列表")

    prefix = "序列："
    tag_prefix = "[Valid]: "
    allowed_chars = "()"
    min_len = 2
    max_len = 12
    yes = "YES"
    no = "NO"

    cleaned = []
    seen = {}

    for record in records:
        # 规则 1：不是字典，或字段缺失/类型不符，一律跳过
        if not isinstance(record, dict):
            continue
        if "sequence" not in record or "valid" not in record:
            continue
        sequence = record["sequence"]
        valid = record["valid"]
        if not isinstance(sequence, str) or not isinstance(valid, str):
            continue

        # 规则 2：删除全部空白字符，再做字符与长度检查（不判合法性）
        normalized = "".join(ch for ch in sequence if not ch.isspace())
        if not (min_len <= len(normalized) <= max_len):
            continue
        if any(ch not in allowed_chars for ch in normalized):
            continue

        # 规则 3：标签去首尾空白并大写
        label = valid.strip().upper()
        if label not in (yes, no):
            continue

        item = {"input": prefix + normalized, "output": tag_prefix + label}

        # 规则 4：按 input 稳定去重；同一 input 不同 output 报错
        previous = seen.get(item["input"])
        if previous is None:
            seen[item["input"]] = item["output"]
            cleaned.append(item)
        elif previous != item["output"]:
            raise ValueError("同一 input 出现了不同标签：%s" % item["input"])

    return cleaned
